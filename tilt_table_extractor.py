"""
tilt_table_extractor.py
Server-side extraction of clinical data from REDCap tilt table test PDFs,
and generation of the HealthTrack flowing-narrative report.

No external APIs used — all processing is local.

REDCap PDF format notes (from real PDF analysis):
- All checkbox/radio options are ALWAYS printed regardless of selection state.
  The PDF is flattened — no AcroForm fields, and all rects are fill=False.
  Multi-select checkbox values cannot be reliably determined from text alone.
- Checkbox detection uses pdf2image + PIL pixel analysis: each option's
  checkbox region (to the left of the label text) is cropped and checked
  for pixel darkness. A marked checkbox has significantly more dark pixels.
- Text fields (MRN, demographics, duration, frequency etc.) use consistent
  label text that we can match with targeted regexes.
- For checkbox groups whose option labels collide (e.g. yes/no questions,
  Page 7 result fields with shared "Normal/POTS/..." labels), each field
  defines an `anchor` phrase that scopes the OCR search to a sub-region
  of the page words.

Output format: a flowing narrative under three headings:
  Summary — multi-paragraph human-readable text covering every captured field
  Conclusion — one sentence per the Page 7 result fields
  Recommendation — diagnosis-specific clinical recommendation

Any field that cannot be confidently extracted is rendered as [undetermined].
"""

import re
import pdfplumber
import io
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Standard placeholder
# ─────────────────────────────────────────────────────────────

_UNDETERMINED = "[undetermined]"


def _undetermined():
    return _UNDETERMINED


def _has(val):
    """True if val is a real (non-undetermined, non-None, non-empty) value."""
    if val is None:
        return False
    s = str(val).strip()
    if not s:
        return False
    return s != _UNDETERMINED


def _field(text, *patterns, label="field"):
    """
    Try each regex pattern in order; return first non-empty match group(1),
    or [undetermined] on failure.
    """
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if m:
            val = m.group(1).strip()
            if val and val.lower() not in ("", "n/a", "none", "unknown", "______"):
                return val
    return _UNDETERMINED


# ─────────────────────────────────────────────────────────────
# Checkbox OCR detection (pdf2image + PIL pixel analysis)
# ─────────────────────────────────────────────────────────────

# Each entry defines a checkbox group:
#   options       — exact label text(s) printed in the REDCap PDF
#   multi         — True for multi-select, False for radio
#   display_map   — optional: matched label → human-readable value in the report
#   anchor        — optional: phrase that must appear before the option labels
#                   (used to scope when option labels are reused elsewhere on the page)
#   stop_anchor   — optional: phrase that bounds the search range from above
_CHECKBOX_FIELDS = {
    # ── Page 2: Presentation history ─────────────────────────
    "no_warning_syncope": {
        "anchor": "No warning syncope",
        "stop_anchor": "Known initiating life event",
        "options": ["Frequent", "Rare", "Never"],
        "multi": False,
    },
    "initiating_life_event": {
        "anchor": "Known initiating life event",
        "stop_anchor": "If YES, was it a medical",
        "options": ["No", "Yes"],
        "multi": False,
    },
    "event_was_medical": {
        "anchor": "If YES, was it a medical illness",
        "stop_anchor": "If YES, was it surgical",
        "options": ["No", "Yes"],
        "multi": False,
    },
    "event_was_surgical": {
        "anchor": "If YES, was it surgical",
        "stop_anchor": "If YES, was it an emotional",
        "options": ["No", "Yes"],
        "multi": False,
    },
    "event_was_emotional": {
        "anchor": "If YES, was it an emotional",
        "options": ["No", "Yes"],
        "multi": False,
    },

    # ── Page 3: Activity & triggers ──────────────────────────
    "posture": {
        "anchor": "Usual Posture",
        "stop_anchor": "Does change in posture",
        "options": ["Standing", "Sitting", "Lying down", "No association with posture"],
        "display_map": {
            "Standing": "standing",
            "Sitting": "sitting",
            "Lying down": "lying down",
            "No association with posture": "no consistent posture",
        },
        "multi": False,
    },
    "posture_change_provokes": {
        "anchor": "change in posture from lying",
        "stop_anchor": "Are symptoms better lying",
        "options": ["No", "Yes"],
        "multi": False,
    },
    "better_lying_down": {
        "anchor": "Are symptoms better lying down",
        "stop_anchor": "Describe any Symptom Triggers",
        "options": ["No", "Yes"],
        "multi": False,
    },
    "triggers": {
        "anchor": "Describe any Symptom Triggers",
        "stop_anchor": "Describe associated symptoms",
        "options": [
            "Needle or blood test", "Acute pain or injury", "Emotional Stress",
            "Known Dehydration", "Febrile illness", "Hot environment",
            "Toilet (voiding)", "Eating (or after)", "During driving",
        ],
        "multi": True,
    },
    "symptoms": {
        "anchor": "Describe associated symptoms",
        "stop_anchor": "syncope during exercise",
        "options": [
            "Nausea", "Vomiting", "Sweating", "Visual changes/disturbances",
            "Pallor/paleness", "Seizure activity", "Urinary Incontinence",
            "Bowel Incontinence", "Fatigue post event", "Hearing loss",
        ],
        "multi": True,
    },
    "syncope_during_exercise": {
        "anchor": "syncope during exercise",
        "stop_anchor": "syncope after exercise",
        "options": ["No", "Yes"],
        "multi": False,
    },
    "syncope_after_exercise": {
        "anchor": "syncope after exercise",
        "stop_anchor": "correlation with the menstrual",
        "options": ["No", "Yes"],
        "multi": False,
    },
    "menstrual_correlation": {
        "anchor": "correlation with the menstrual",
        "stop_anchor": "you experience palpitations",
        "options": ["No", "Yes"],
        "multi": False,
    },
    "palpitations": {
        "anchor": "you experience palpitations",
        "stop_anchor": "If Yes, were they",
        "options": ["No", "Yes"],
        "multi": False,
    },
    "palpitation_type": {
        "anchor": "If Yes, were they",
        "stop_anchor": "Anything else you have observed",
        "options": ["fast", "slow", "stronger", "irregular"],
        "multi": True,
    },

    # ── Page 4: Other medical history ────────────────────────
    "family_hx_cardiac": {
        # Q30 — anchor on Q30's first option (unique on page)
        "anchor": "Sudden Cardiac Death",
        "stop_anchor": "Have you been diagnosed",
        "options": [
            "Sudden Cardiac Death", "Cardiomyopathy",
            "Family members with cardiac devices", "Other",
        ],
        "multi": True,
    },
    "conditions": {
        # Q31 + Q32 + Q35 collapsed into one comorbidities group
        "anchor": "Have you been diagnosed",
        "stop_anchor": "formal diagnosis of",
        "options": [
            "Chronic fatigue", "Brain Fogging", "Joint Hyper-mobility",
            "Fibromyalgia or other pain syndrome", "Frequent headaches or migraine",
            "MCAS - mast cell activation syndrome",
            "High blood pressure", "Asthma", "Diabetes",
            "Coronary heart disease", "Valvular heart disease",
        ],
        "multi": True,
    },
    "gi_diagnosis": {
        # Q33
        "anchor": "formal diagnosis of",
        "stop_anchor": "suffer from the following",
        "options": ["Oesophageal Dysmotility", "Gastroperesis/early satiety", "IBS"],
        "multi": True,
    },
    "gi_symptoms": {
        # Q34
        "anchor": "suffer from the following",
        "stop_anchor": "diagnosis of Anxiety",
        "options": [
            "Constipation only", "Diarrhoea only",
            "Alternating constipation and diarrhoea",
            "Bloating", "Abdominal pain/cramping",
        ],
        "multi": True,
    },
    "mental_health": {
        # Q35 — separated out from conditions
        "anchor": "diagnosis of Anxiety",
        "stop_anchor": "Negative chronotropes",
        "options": [
            "Anxiety", "Depression",
            "ADHD - Attention deficit hyperactivity disorder",
            "Autism", "Other mental health",
        ],
        "multi": True,
    },
    "negative_chronotropes": {
        # Q36
        "anchor": "Negative chronotropes",
        "stop_anchor": "Anti-depressant",
        "options": ["No", "Beta blocker", "Ivabradine"],
        "multi": True,
    },
    "antidepressants": {
        # Q37
        "anchor": "Anti-depressant",
        "stop_anchor": "Fludrocortisone",
        "options": ["SSRI", "Tricyclic", "SNRI"],
        "multi": True,
    },
    "fludrocortisone_status": {
        # Q38
        "anchor": "Fludrocortisone",
        "stop_anchor": "Midodrine",
        "options": ["Current", "Discontinued", "Never taken"],
        "multi": False,
    },
    "midodrine_status": {
        # Q39 — last on page so no stop_anchor needed
        "anchor": "Midodrine",
        "options": ["Current", "Discontinued", "Never taken"],
        "multi": False,
    },

    # ── Page 6: Investigations ───────────────────────────────
    "investigations": {
        "options": [
            "ECG", "Holter Monitor", "ECHO", "Stress Test", "Loop recorder",
            "EP study", "Coronary Angiogram", "CT or MRI Brain", "EEG", "Carotid Doppler",
        ],
        "multi": True,
    },

    # ── Page 7: Final results ────────────────────────────────
    "test_type": {
        "anchor": "Type of test",
        "stop_anchor": "Control Results",
        "options": ["Isuprenaline", "Isoprenaline", "GTN", "Passive only"],
        "multi": False,
    },
    "control_result_raw": {
        "anchor": "Control Results",
        "stop_anchor": "Phase 2 results",
        "options": [
            "Normal", "POTS", "Postural Hypotension",
            "Vasovagal syncope", "Vasovagal presyncope", "Mixed",
        ],
        "multi": False,
    },
    "phase2_result_raw": {
        "anchor": "Phase 2 results",
        "stop_anchor": "Symptom Correlation",
        "options": [
            "Normal", "POTS", "Postural Hypotension",
            "Vasovagal syncope", "Vasovagal presyncope", "Mixed",
        ],
        "multi": False,
    },
    "symptom_correlation": {
        "anchor": "Symptom Correlation",
        "stop_anchor": "Results Conclusion",
        "options": [
            "Symptoms correlate with baseline",
            "Symptoms that are different to baseline",
            "No symptoms",
        ],
        "multi": False,
    },
}


def _build_word_text(words):
    """Return (joined_text, char_to_word_idx_map) for a list of pdfplumber words."""
    parts = []
    char_to_word = {}
    pos = 0
    for i, w in enumerate(words):
        if i > 0:
            parts.append(" ")
            pos += 1
        text = w["text"]
        for c in range(len(text)):
            char_to_word[pos + c] = i
        parts.append(text)
        pos += len(text)
    return "".join(parts), char_to_word


def _find_anchor_word_index(words, phrase):
    """
    Find first word index where the anchor phrase begins.
    Phrase is matched as a regex against the joined word text;
    whitespace and hyphens between phrase tokens are tolerated.
    """
    tokens = re.findall(r"[A-Za-z0-9]+", phrase)
    if not tokens:
        return None
    pat = r"\b" + r"[\s\-]+".join(re.escape(t) for t in tokens) + r"\b"

    text, char_to_word = _build_word_text(words)
    m = re.search(pat, text, re.IGNORECASE)
    if not m:
        return None
    return char_to_word.get(m.start())


def _find_option_position(words, option_text, start_idx=0, end_idx=None):
    """
    Locate an option label within a slice of the page word list.
    Returns (x0, top, bottom) of the first matching word, or None.

    Matching: strip trailing blanks/underscores, take the first two tokens of
    length ≥ 2. The first token must equal a normalised word; if a second
    token exists, it must appear within the next four words (loose proximity).
    """
    if end_idx is None:
        end_idx = len(words)

    clean = re.sub(r"[\s_]+$", "", option_text).strip().lower()
    raw_tokens = [t for t in clean.split() if len(t) >= 2][:2]
    if not raw_tokens:
        return None

    # Normalize tokens (strip non-alphanumerics for comparison)
    tokens = [re.sub(r"[^a-z0-9]", "", t) for t in raw_tokens]

    for i in range(start_idx, end_idx):
        wt = re.sub(r"[^a-z0-9]", "", words[i]["text"].lower())
        if wt == tokens[0]:
            if len(tokens) > 1:
                nearby = []
                for k in range(i + 1, min(i + 5, end_idx)):
                    nt = re.sub(r"[^a-z0-9]", "", words[k]["text"].lower())
                    if nt:
                        nearby.append(nt)
                if tokens[1] not in nearby:
                    continue
            return (words[i]["x0"], words[i]["top"], words[i]["bottom"])

    return None


def _ocr_checkboxes(pdf_bytes):
    """
    Render each PDF page (120 DPI to fit Render Starter memory budget) and
    determine checkbox state by pixel-darkness analysis of the small region
    immediately left of each option label.

    An unchecked REDCap box shows only a thin border outline (very few dark
    pixels). A checked box contains a filled mark (significantly more dark
    pixels).

    Returns dict mapping field_name → formatted string value, or None for
    fields where the options couldn't be located on any page.
    """
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        logger.warning("pdf2image not installed — checkbox OCR unavailable")
        return {}

    DPI = 120
    SCALE = DPI / 72.0           # PDF points → image pixels
    DARK_THRESHOLD = 160         # pixel value below this counts as "dark"
    MARKED_RATIO = 0.18          # fraction of dark pixels that implies a mark

    found_checked = {f: [] for f in _CHECKBOX_FIELDS}
    found_on_page = {f: set() for f in _CHECKBOX_FIELDS}

    # Poppler may not be on the server's PATH (homebrew / Render image variations).
    import shutil
    poppler_path = None
    for candidate in ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
        if shutil.which("pdftoppm", path=candidate):
            poppler_path = candidate
            break

    try:
        images = convert_from_bytes(pdf_bytes, dpi=DPI, poppler_path=poppler_path)
    except Exception as e:
        logger.warning("pdf2image conversion failed: %s", e)
        return {}

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page, img in zip(pdf.pages, images):
            words = page.extract_words(x_tolerance=5, y_tolerance=5)

            for field_name, cfg in _CHECKBOX_FIELDS.items():
                # Determine search range using anchor + optional stop_anchor
                start_idx = 0
                end_idx = len(words)

                if cfg.get("anchor"):
                    ai = _find_anchor_word_index(words, cfg["anchor"])
                    if ai is None:
                        continue  # anchor not on this page, skip field
                    start_idx = ai
                    if cfg.get("stop_anchor"):
                        sub_words = words[start_idx + 1:]
                        si = _find_anchor_word_index(sub_words, cfg["stop_anchor"])
                        if si is not None:
                            end_idx = start_idx + 1 + si

                for option in cfg["options"]:
                    pos = _find_option_position(words, option, start_idx=start_idx, end_idx=end_idx)
                    if pos is None:
                        continue

                    x0, y0, y1 = pos
                    found_on_page[field_name].add(option)

                    # Checkbox sits immediately left of the label text.
                    # REDCap checkbox: ~9pt square, ~2-3pt gap before text.
                    # We crop the INNER region of the box (skipping its 1px border)
                    # so that empty boxes don't read as "marked" purely from their
                    # outline — at 120 DPI a full crop is otherwise dominated by
                    # border ink (~17%, just under the marked threshold).
                    y_h = max(1.0, y1 - y0)
                    y_mid = (y0 + y1) / 2.0
                    cb_x0 = max(0.0, x0 - 13)
                    cb_x1 = max(0.0, x0 - 5)
                    cb_y0 = max(0.0, y_mid - y_h * 0.30)
                    cb_y1 = min(page.height, y_mid + y_h * 0.30)

                    px0, px1 = int(cb_x0 * SCALE), int(cb_x1 * SCALE)
                    py0, py1 = int(cb_y0 * SCALE), int(cb_y1 * SCALE)

                    if px1 <= px0 or py1 <= py0:
                        continue

                    crop = img.crop((px0, py0, px1, py1))
                    gray = crop.convert("L")
                    pixels = list(gray.getdata())
                    if not pixels:
                        continue

                    dark_count = sum(1 for p in pixels if p < DARK_THRESHOLD)
                    if dark_count / len(pixels) >= MARKED_RATIO:
                        if option not in found_checked[field_name]:
                            found_checked[field_name].append(option)

    # Build result strings
    results = {}
    for field_name, cfg in _CHECKBOX_FIELDS.items():
        if not found_on_page[field_name]:
            results[field_name] = None  # caller will use [undetermined]
            continue

        display_map = cfg.get("display_map", {})
        selected = [display_map.get(opt, opt) for opt in found_checked[field_name]]

        if not selected:
            results[field_name] = "none reported"
        elif not cfg["multi"]:
            results[field_name] = selected[0]
        else:
            results[field_name] = _join_and(selected)

    return results


# ─────────────────────────────────────────────────────────────
# PDF text extraction
# ─────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_bytes):
    """Extract all text from a PDF given as bytes, preserving layout."""
    text_parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


# ─────────────────────────────────────────────────────────────
# Field extraction
# ─────────────────────────────────────────────────────────────

def extract_fields(text, ocr_results=None):
    """
    Parse REDCap PDF text into a structured dict of clinical fields.
    Any unconfident field is the [undetermined] string.

    ocr_results: optional dict from _ocr_checkboxes(); its values replace the
                 [undetermined] placeholder for checkbox fields when present.
    """
    d = {}
    ocr = ocr_results or {}

    # ── Patient demographics ──────────────────────────────────
    d["first_name"] = "<HMS-Patient_FirstName>"

    d["mrn"] = _field(
        text,
        r"(?:Eastern\s+Health\s+)?MRN[:\s#]*([0-9A-Za-z\-]+)",
        r"(?:Medical\s+Record\s+Number|URN)[:\s]*([0-9A-Za-z\-]+)",
        label="MRN"
    )

    d["dob"] = _field(
        text,
        r"Date\s+of\s+birth\s+([\d/\-\.]+)",
        r"D(?:ate\s+of\s+)?[Bb]irth[:\s]+([\d/\-\.]+)",
        label="DOB"
    )

    d["age"] = _field(
        text,
        r"Age\s+\(years?\)\s+(\d{1,3})",
        r"\bAge[:\s]+(\d{1,3})\b",
        label="age"
    )

    d["sex"] = _field(
        text,
        r"\bSex\s+(Female|Male)\b",
        r"\bSex[:\s]+(Female|Male|Non-binary|Other)\b",
        label="sex"
    )

    d["height"] = _field(
        text,
        r"Height\s+\(cm\)\s+([\d.]+)",
        r"Height[:\s]+([\d.]+\s*(?:cm|m))",
        label="height"
    )

    d["weight"] = _field(
        text,
        r"Weight\s+\(kilogram[^)]*\)\s+([\d.]+)",
        r"Weight[:\s]+([\d.]+\s*(?:kg|lbs?))",
        label="weight"
    )

    d["bmi"] = _field(
        text,
        r"\bBMI\s+([\d.]+)",
        label="BMI"
    )

    # ── Symptom onset ─────────────────────────────────────────
    _DUR_VAL = r"(______|\d+(?:\.\d+)?)"
    _DUR_UNIT = r"(______|Years?|Months?|Weeks?|Days?)"
    onset_m = re.search(
        r"Symptom\s+onset\s+\([^)]+\)\s+" + _DUR_VAL + r"\s+" + _DUR_UNIT
        + r"(?:\s+" + _DUR_VAL + r"\s+" + _DUR_UNIT + r")?",
        text, re.IGNORECASE
    )
    d["duration_number"] = None
    d["duration_unit"] = None
    d["presyncope_duration_number"] = None
    d["presyncope_duration_unit"] = None
    if onset_m:
        sn, su = onset_m.group(1), onset_m.group(2)
        pn, pu = onset_m.group(3), onset_m.group(4)
        if sn and sn != "______" and su and su != "______":
            d["duration_number"] = sn
            d["duration_unit"] = _normalise_unit(su.lower())
        if pn and pn != "______" and pu and pu != "______":
            d["presyncope_duration_number"] = pn
            d["presyncope_duration_unit"] = _normalise_unit(pu.lower())

    # ── Frequency ─────────────────────────────────────────────
    _FREQ_COUNT = r"(______|\d+(?:-\d+)?)"
    _FREQ_UNIT = r"(______|Month|Week|Day|Year)"
    freq_m = re.search(
        r"Frequency\s+of\s+events\s+\([^)]+\)\s+" + _FREQ_COUNT + r"\s+" + _FREQ_UNIT
        + r"(?:\s+" + _FREQ_COUNT + r"\s+" + _FREQ_UNIT + r")?",
        text, re.IGNORECASE
    )
    d["frequency"] = None
    d["presyncope_frequency"] = None
    if freq_m:
        sc, su = freq_m.group(1), freq_m.group(2)
        pc, pu = freq_m.group(3), freq_m.group(4)
        if sc and sc != "______" and su and su != "______":
            d["frequency"] = _unit_to_frequency(su, sc)
        if pc and pc != "______" and pu and pu != "______":
            d["presyncope_frequency"] = _unit_to_frequency(pu, pc)

    # ── Episode counts ────────────────────────────────────────
    ep_m = re.search(
        r"Number\s+of\s+episodes\s+in\s+the\s+last\s+month\??\s+(______|\d+)(?:\s+(______|\d+))?",
        text, re.IGNORECASE
    )
    d["syncope_episodes_last_month"] = None
    d["presyncope_episodes_last_month"] = None
    if ep_m:
        s = ep_m.group(1)
        p = ep_m.group(2) if ep_m.group(2) else None
        if s and s != "______":
            d["syncope_episodes_last_month"] = s
        if p and p != "______":
            d["presyncope_episodes_last_month"] = p

    # ── Most recent date ──────────────────────────────────────
    d["most_recent_date"] = _field(
        text,
        r"Date\s+of\s+most\s+recent\s+episode\??\s+([\d]{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
        r"Most\s+[Rr]ecent[:\s]+([\d/\-\.]+(?:\s+\d{4})?)",
        label="most_recent_episode_date"
    )

    # ── Initiating life event free text ───────────────────────
    ile_m = re.search(
        r"Known\s+initiating\s+life\s+event\?[^\n]*\n?[^\n]*Yes\s+([\w][^\n]{2,80}?)(?:\n|If\s+YES)",
        text, re.IGNORECASE
    )
    d["initiating_event_detail"] = ile_m.group(1).strip() if ile_m else None

    # ── Menstrual correlation free text ───────────────────────
    mc_m = re.search(
        r"correlation\s+with\s+the\s+menstrual\s+cycle\?[^\n]*\n?[^\n]*Yes\s+([\w][^\n]{2,80}?)(?:\n|Do\s+you)",
        text, re.IGNORECASE
    )
    if mc_m:
        candidate = mc_m.group(1).strip()
        if candidate and "_" not in candidate and not candidate.startswith("__"):
            d["menstrual_detail"] = candidate
        else:
            d["menstrual_detail"] = None
    else:
        d["menstrual_detail"] = None

    # ── Other observations free text (page 3 final question) ─
    # The label runs across two lines and is followed by underscores; if
    # any user-supplied text is present it appears between the underscores
    # and the page footer. Reject anything matching the REDCap footer pattern.
    obs_m = re.search(
        r"Anything\s+else\s+you\s+have\s+observed[^\n]*?(?:\n[^\n]*?)?_+\s*([^\n_][^\n]{2,200}?)(?:\n|$)",
        text, re.IGNORECASE
    )
    if obs_m:
        candidate = obs_m.group(1).strip()
        if (
            candidate
            and "projectredcap" not in candidate.lower()
            and not re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}", candidate)
            and "_" not in candidate[:30]
        ):
            d["other_observations"] = candidate
        else:
            d["other_observations"] = None
    else:
        d["other_observations"] = None

    # ── Family history Q29 (free text after Yes) ─────────────
    # The detail may appear on the same line as the question, OR on a following
    # line (REDCap wraps "Yes <detail>" beneath "No" when the answer is yes).
    fh_yes_m = re.search(
        r"Family\s+history\s+of\s+hypotension[^?]*\?\s*"
        r"(?:No\s*)?"
        r"Yes\s+([^\n]+?)(?:\n\s*30\)|\n\s*Family\s+history\s+of\.\.\.|\n)",
        text, re.IGNORECASE | re.DOTALL
    )
    if fh_yes_m:
        detail = fh_yes_m.group(1).strip()
        if detail and "_" not in detail and detail.lower() not in ("", "n/a"):
            d["family_history"] = f"remarkable for {detail}"
        else:
            d["family_history"] = "unremarkable"
    elif re.search(r"Family\s+history\s+of\s+hypotension[^?]*\?\s*No\s*\n", text, re.IGNORECASE):
        d["family_history"] = "unremarkable"
    else:
        d["family_history"] = None

    # ── Other medications free text (Q40) ─────────────────────
    om_m = re.search(
        r"List\s+any\s+other\s+relevant\s+medications\s+([^\n]+?)(?:\n|$)",
        text, re.IGNORECASE
    )
    if om_m:
        val = om_m.group(1).strip()
        if val and not val.startswith("_") and val.lower() not in ("none", "n/a", "nil"):
            d["other_medications"] = val
        else:
            d["other_medications"] = None
    else:
        d["other_medications"] = None

    # ── Investigation free-text comments (page 6) ────────────
    inv_comm_m = re.search(
        r"Additional\s+comments\s*\n?\s*([^\n_][^\n]{2,200}?)(?:\n|$)",
        text, re.IGNORECASE
    )
    d["investigation_comments"] = inv_comm_m.group(1).strip() if inv_comm_m else None

    # ── Page 7 free text fields ───────────────────────────────
    d["baseline_rhythm"] = _field(
        text,
        r"Baseline\s+Rhythm\s+([^\n]+?)\s+Recovery\s+Blood",
        r"Baseline\s+Rhythm\s+([^\n]+)",
        label="baseline_rhythm"
    )
    if d["baseline_rhythm"] == _UNDETERMINED:
        d["baseline_rhythm"] = None
    elif d["baseline_rhythm"].startswith("_"):
        d["baseline_rhythm"] = None

    # Results Conclusion is a free-text box. In a blank PDF it shows only
    # underscores, then "Results table" heading. We capture only NON-underscore
    # NON-heading content. Reject if candidate is "Results table" or starts
    # with whitespace/underscores only.
    rc_m = re.search(
        r"Results\s+Conclusion\s*\n_+\s*\n([^\n]+)",
        text, re.IGNORECASE
    )
    if rc_m:
        cand = rc_m.group(1).strip()
        if (
            cand
            and not cand.lower().startswith("results table")
            and not cand.startswith("_")
            and "projectredcap" not in cand.lower()
        ):
            d["results_conclusion"] = cand
        else:
            d["results_conclusion"] = None
    else:
        d["results_conclusion"] = None

    # ── OCR-derived fields ────────────────────────────────────
    # Each OCR field name in d takes precedence; None means [undetermined]
    for k in (
        "no_warning_syncope", "initiating_life_event",
        "event_was_medical", "event_was_surgical", "event_was_emotional",
        "posture", "posture_change_provokes", "better_lying_down",
        "triggers", "symptoms",
        "syncope_during_exercise", "syncope_after_exercise",
        "menstrual_correlation", "palpitations", "palpitation_type",
        "family_hx_cardiac",
        "conditions", "gi_diagnosis", "gi_symptoms", "mental_health",
        "negative_chronotropes", "antidepressants",
        "fludrocortisone_status", "midodrine_status",
        "investigations",
        "test_type", "control_result_raw", "phase2_result_raw",
        "symptom_correlation",
    ):
        d[k] = ocr.get(k)

    # ── Tilt drug — derive from OCR test_type ─────────────────
    tt = (d.get("test_type") or "").lower()
    if "isuprenaline" in tt or "isoprenaline" in tt:
        d["tilt_drug"] = "Isoprenaline"
    elif "gtn" in tt:
        d["tilt_drug"] = "GTN"
    elif "passive" in tt:
        d["tilt_drug"] = None  # passive only — no drug
    else:
        d["tilt_drug"] = "__unknown__"  # marker for downstream

    # ── BP/HR table ───────────────────────────────────────────
    d["baseline_hr"] = _extract_numeric(text, r"Baseline\s+Heart\s+Rate\s+(\d+)")
    d["baseline_bp"] = _field(
        text,
        r"Baseline\s+Blood\s+Pressure\s+(\d+/\d+)",
        r"Baseline\s+Blood\s+Pressure\s+(\d{2,3})\b",
        label="baseline_BP"
    )
    if d["baseline_bp"] == _UNDETERMINED:
        d["baseline_bp"] = None

    d["recovery_hr"] = _extract_numeric(text, r"Recovery\s+Heart\s+Rate\s+(\d+)")
    rec_bp_raw = re.search(r"Recovery\s+Blood\s+Pressure\s+([\d/]+)", text, re.I)
    d["recovery_bp"] = rec_bp_raw.group(1) if rec_bp_raw else None

    d["control_readings"] = _extract_phase_readings(text, "Control")
    d["phase2_readings"] = _extract_phase_readings(text, "Phase 2")

    # ── Clinician notes ───────────────────────────────────────
    ctrl_note_m = re.search(
        r"^(?!Any\s+symptoms)(?!Phase)([A-Z][^\n]{9,120}?)[ \t]+Control[ \t]+\d+[ \t]+minute\b",
        text, re.IGNORECASE | re.MULTILINE
    )
    d["control_notes"] = ctrl_note_m.group(1).strip() if ctrl_note_m else ""

    p2_note_m = re.search(
        r"Any\s+symptoms\?[^\n]*\n([^\n]+)\n\s*Phase\s+2\s+10\s+minute",
        text, re.IGNORECASE
    )
    if p2_note_m:
        raw_note = p2_note_m.group(1)
        raw_note = re.sub(r"\s*projectredcap\.org\s*", " ", raw_note)
        clean_tokens = [t for t in raw_note.split() if not re.search(r"\d", t)]
        d["phase2_notes"] = " ".join(clean_tokens).strip()
    else:
        d["phase2_notes"] = ""

    # ── Phase 2 stop minute ───────────────────────────────────
    last_p2_min = None
    for pm in re.finditer(r"Phase\s+2\s+(\d+)\s+minute\s+(\d{2,3})\s+(\d{2,3})", text, re.I):
        last_p2_min = int(pm.group(1))
    d["phase2_stop_minute"] = last_p2_min

    # ── Calculated tilt results (used as fallback narrative) ──
    d["control_result_calc"] = _calculate_control_result(d)
    d["control_tolerance"] = _infer_tolerance(text, "control", d)
    d["control_symptom_severity"] = _infer_severity(text, "control")

    d["phase2_result_calc"] = _calculate_phase2_result(d)
    d["phase2_tolerance"] = _infer_tolerance(text, "phase 2", d)

    return d


# ─────────────────────────────────────────────────────────────
# Unit normalisers
# ─────────────────────────────────────────────────────────────

def _normalise_unit(raw):
    r = raw.lower().rstrip("s") + "s"
    if r in ("years", "months", "weeks", "days"):
        return r
    return raw


def _unit_to_frequency(unit_str, count_str=None):
    mapping = {
        "month": "monthly", "week": "weekly",
        "day": "daily", "year": "yearly"
    }
    unit_lower = unit_str.lower()
    word = mapping.get(unit_lower, "infrequently")

    if count_str and str(count_str) not in ("1", "", "______"):
        singular = {"month": "month", "week": "week", "day": "day", "year": "year"}
        return f"{count_str} times per {singular.get(unit_lower, unit_lower)}"
    return word


# ─────────────────────────────────────────────────────────────
# BP / HR extraction
# ─────────────────────────────────────────────────────────────

def _extract_numeric(text, pattern):
    m = re.search(pattern, text, re.IGNORECASE)
    try:
        return int(m.group(1)) if m else None
    except (ValueError, AttributeError):
        return None


def _extract_phase_readings(text, phase_label):
    """Extract (systolic_bp, hr) tuples from results table for a given phase."""
    if phase_label.lower() == "control":
        block_pat = (
            r"Control\s+Tilting.*?"
            r"(?=Phase\s+2|Phase\s+Stage|$)"
        )
    else:
        block_pat = (
            r"Phase\s+2\s+Phase\s+2\s+Baseline.*?"
            r"(?=Phase\s+Stage|Results\s+Conclusion|$)"
        )

    bm = re.search(block_pat, text, re.DOTALL | re.IGNORECASE)
    block = bm.group(0) if bm else ""

    readings = []
    for m in re.finditer(r"(\d{2,3})\s+(\d{2,3})\s*$", block, re.MULTILINE):
        sbp, hr = int(m.group(1)), int(m.group(2))
        if 40 <= sbp <= 250 and 20 <= hr <= 250:
            readings.append((sbp, hr))

    return readings


# ─────────────────────────────────────────────────────────────
# Tilt result calculation from numeric data (fallback for narrative)
# ─────────────────────────────────────────────────────────────

_RESULT_POTS = "POTS"
_RESULT_VVS = "Vasovagal"
_RESULT_OI = "Orthostatic intolerance"
_RESULT_OH = "Postural hypotension"
_RESULT_NORMAL = "Normal"
_RESULT_NOT_REACHED = "not_reached"


def _calculate_control_result(d):
    """Apply criteria to control phase BP/HR readings — returns short label."""
    readings = d.get("control_readings", [])
    baseline_hr = d.get("baseline_hr")
    age = _safe_int(d.get("age"))

    if not readings or baseline_hr is None:
        return None

    max_hr = max(hr for _, hr in readings)
    hr_rise = max_hr - baseline_hr

    pots_threshold = 40 if (age and 12 <= age <= 19) else 30
    if hr_rise >= pots_threshold:
        return _RESULT_POTS

    if hr_rise >= 20:
        return _RESULT_OI

    baseline_sbp = _extract_systolic(d.get("baseline_bp"))
    if baseline_sbp:
        min_sbp = min(sbp for sbp, _ in readings)
        sbp_drop = baseline_sbp - min_sbp
        min_hr = min(hr for _, hr in readings)
        if sbp_drop > 20 or min_hr < 50:
            return _RESULT_VVS

    return _RESULT_NORMAL


def _calculate_phase2_result(d):
    readings = d.get("phase2_readings", [])
    if not readings:
        return _RESULT_NOT_REACHED

    baseline_sbp = readings[0][0] if readings else None
    baseline_hr = readings[0][1] if readings else None
    age = _safe_int(d.get("age"))

    if len(readings) < 2:
        return None

    subsequent = readings[1:]
    max_hr = max(hr for _, hr in subsequent)
    min_sbp = min(sbp for sbp, _ in subsequent)
    min_hr = min(hr for _, hr in subsequent)
    hr_rise = max_hr - baseline_hr if baseline_hr else 0
    sbp_drop = baseline_sbp - min_sbp if baseline_sbp else 0

    if sbp_drop > 20 or min_hr < 50:
        return _RESULT_VVS

    pots_threshold = 40 if (age and 12 <= age <= 19) else 30
    if hr_rise >= pots_threshold:
        return _RESULT_POTS

    if hr_rise >= 20:
        return _RESULT_OI

    return _RESULT_NORMAL


def _infer_tolerance(text, phase, d):
    if phase == "control":
        notes = d.get("control_notes", "")
        section_pat = r"Any\s+symptoms\?(.{0,200}?)(?:Phase\s+2|Phase\s+Stage|$)"
    else:
        notes = d.get("phase2_notes", "")
        section_pat = r"Any\s+symptoms\?(.{0,400}?)(?:Results\s+Conclusion|$)"

    sm = re.search(section_pat, text, re.DOTALL | re.IGNORECASE)
    section = (sm.group(1) if sm else "") + " " + (notes or "")

    no_loc = bool(re.search(r"\bno\s+loc\b|\bno\s+loss\s+of\s+consciousness\b|\bdid\s+not\s+(?:lose|faint)\b", section, re.I))

    syncope_words = r"\b(?:synco(?:pe|ped)|lost\s+consciousness|(?<!no\s)loc\b)\b"
    presync_words = r"\b(?:presyncope|pre-syncope|near.syncope|very\s+pale|pale|dizz|light.?head|near\s+faint|almost\s+faint|vision\s+loss)\b"

    had_syncope = bool(re.search(syncope_words, section, re.I)) and not no_loc
    had_presync = bool(re.search(presync_words, section, re.I))

    if phase == "phase 2":
        readings = d.get("phase2_readings", [])
        if len(readings) >= 2:
            subsequent = readings[1:]
            min_sbp = min(sbp for sbp, _ in subsequent)
            min_hr = min(hr for _, hr in subsequent)
            if not no_loc and (min_sbp < 55 or min_hr < 40):
                had_syncope = True
            elif min_sbp < 75:
                had_presync = True

    if had_syncope and had_presync:
        return "experienced presyncope and syncope"
    elif had_syncope:
        return "experienced syncope"
    elif had_presync:
        return "experienced presyncope"
    else:
        return "tolerated the test well"


def _infer_severity(text, phase):
    if phase == "control":
        section_pat = r"Any\s+symptoms\?(.{0,300}?)(?:Phase\s+2|Phase\s+Stage|$)"
    else:
        section_pat = r"Any\s+symptoms\?(.{0,400}?)(?:Results\s+Conclusion|$)"

    sm = re.search(section_pat, text, re.DOTALL | re.IGNORECASE)
    section = sm.group(1) if sm else ""

    if re.search(r"\bsevere\b", section, re.I):
        return "severe"
    if re.search(r"\bmoderate\b", section, re.I):
        return "moderate"
    if re.search(r"\bmild\b|\bminimal\b", section, re.I):
        return "mild"
    if re.search(r"\bno\s+(?:symptom|complaint|dizzin)\b|\bnil\s+symptoms\b|\bwell\b|\basymptomatic\b", section, re.I):
        return "no"
    return "mild"


# ─────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────

def _extract_systolic(bp_str):
    if not bp_str:
        return None
    m = re.match(r"(\d+)", str(bp_str))
    return int(m.group(1)) if m else None


def _safe_int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _join_and(items):
    items = [str(i) for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def _val(v):
    """Render a field value for inline narrative use; [undetermined] if missing."""
    if v is None:
        return _UNDETERMINED
    s = str(v).strip()
    if not s:
        return _UNDETERMINED
    return s


def _trim_trailing_period(s):
    """Strip a trailing period so callers can safely append one of their own."""
    if not s:
        return s
    return s.rstrip().rstrip(".").rstrip()


# Medical acronyms/abbreviations that must remain uppercase mid-sentence
_KEEP_UPPER = {
    "pots", "ibs", "ecg", "echo", "eeg", "mri", "ct", "ep",
    "ssri", "snri", "adhd", "mcas", "gtn", "ocp", "oi",
}


def _sentence_case_list(text):
    """
    Lowercase a comma/and-joined OCR label string, preserving known medical
    acronyms and all-uppercase abbreviations of ≤5 chars.

    'Emotional Stress, Known Dehydration' → 'emotional stress, known dehydration'
    'ECG, ECHO and Stress Test'           → 'ECG, ECHO and stress test'
    'POTS, IBS'                           → 'POTS, IBS'
    """
    if not text:
        return text

    def _fix_word(w):
        # Preserve any attached punctuation (commas, semicolons)
        punct_tail = ""
        core = w
        while core and core[-1] in ",.;:":
            punct_tail = core[-1] + punct_tail
            core = core[:-1]
        core_lower = core.lower()
        if core_lower in _KEEP_UPPER:
            return core + punct_tail          # keep original casing
        if core.upper() == core and 1 < len(core) <= 5:
            return core + punct_tail          # short all-caps token — keep
        # Lowercase the first character
        lowered = core[0].lower() + core[1:] if core else core
        return lowered + punct_tail

    return " ".join(_fix_word(w) for w in text.split())


def _yn(v):
    """Map Yes/No selection (or None) to lowercase 'yes'/'no'/[undetermined]."""
    if not _has(v):
        return _UNDETERMINED
    s = str(v).strip().lower()
    if s in ("yes", "y"):
        return "yes"
    if s in ("no", "n"):
        return "no"
    return _UNDETERMINED


# ─────────────────────────────────────────────────────────────
# Narrative composers — each returns one or more sentences
# ─────────────────────────────────────────────────────────────

def _compose_demographics(f):
    age = _val(f.get("age"))
    sex = _val(f.get("sex"))
    height = _val(f.get("height"))
    weight = _val(f.get("weight"))
    bmi = _val(f.get("bmi"))
    sex_str = sex.lower() if _has(sex) else _UNDETERMINED
    return (
        f"{age}-year-old {sex_str}. "
        f"Height {height} cm, weight {weight} kg, BMI {bmi}."
    )


def _compose_history(f):
    parts = []
    fn = f.get("first_name", "<HMS-Patient_FirstName>")

    dur_n, dur_u = f.get("duration_number"), f.get("duration_unit")
    pre_dur_n, pre_dur_u = f.get("presyncope_duration_number"), f.get("presyncope_duration_unit")
    freq = f.get("frequency")
    pre_freq = f.get("presyncope_frequency")

    if _has(dur_n) and _has(dur_u):
        s = f"{fn} reports a {dur_n}-{dur_u.rstrip('s')} history of syncope"
        if _has(freq):
            s += f", occurring {freq}"
        s += "."
        parts.append(s)
    else:
        parts.append(f"No syncope history was reported.")

    if _has(pre_dur_n) and _has(pre_dur_u):
        s = f"Presyncope symptoms have been present for {pre_dur_n} {pre_dur_u}"
        if _has(pre_freq):
            s += f", occurring {pre_freq}"
        s += "."
        parts.append(s)
    elif _has(pre_freq):
        parts.append(f"Presyncope symptoms occur {pre_freq}.")
    else:
        parts.append("No presyncope history was reported.")

    sync_ep = f.get("syncope_episodes_last_month")
    pre_ep = f.get("presyncope_episodes_last_month")
    recent = f.get("most_recent_date")

    if _has(sync_ep) and _has(pre_ep):
        ep_clause = f"There have been {sync_ep} syncope and {pre_ep} presyncope episodes in the last month"
    elif _has(sync_ep):
        ep_clause = f"There have been {sync_ep} syncope episodes in the last month"
    elif _has(pre_ep):
        ep_clause = f"There have been {pre_ep} presyncope episodes in the last month"
    else:
        ep_clause = f"Episode count over the last month was not recorded ({_UNDETERMINED})"

    if _has(recent):
        ep_clause += f", with the most recent episode on {recent}."
    else:
        ep_clause += f"; date of the most recent episode is {_UNDETERMINED}."
    parts.append(ep_clause)

    # Warning before syncope — frame as high-risk feature presence/absence
    nws = f.get("no_warning_syncope")
    if _has(nws):
        nws_l = str(nws).lower()
        if nws_l == "never":
            parts.append("No high-risk syncope features: episodes are always preceded by warning symptoms.")
        elif nws_l == "rare":
            parts.append("Episodes occasionally occur without prior warning.")
        elif nws_l == "frequent":
            parts.append("High-risk syncope features present: episodes frequently occur without prior warning.")
        else:
            parts.append(f"Frequency of episodes without warning: {nws}.")
    else:
        parts.append(f"Presence of high-risk syncope features (episodes without warning): {_UNDETERMINED}.")

    # Initiating event
    ile = f.get("initiating_life_event")
    detail = f.get("initiating_event_detail")
    if _yn(ile) == "yes":
        if _has(detail):
            parts.append(f"A known initiating life event was reported: {_trim_trailing_period(detail)}.")
        else:
            parts.append("A known initiating life event was reported (no further detail).")
        # Sub-categorisation
        sub = []
        if _yn(f.get("event_was_medical")) == "yes":
            sub.append("medical illness")
        if _yn(f.get("event_was_surgical")) == "yes":
            sub.append("surgical or trauma")
        if _yn(f.get("event_was_emotional")) == "yes":
            sub.append("emotional trauma")
        if sub:
            parts.append(f"The event was characterised as: {_join_and(sub)}.")
    elif _yn(ile) == "no":
        parts.append("No known initiating life event was reported.")
    else:
        parts.append(f"Initiating life event status: {_UNDETERMINED}.")

    return " ".join(parts)


def _compose_postural(f):
    parts = []
    posture = f.get("posture")
    if _has(posture):
        parts.append(f"Symptoms typically occur with {posture}.")
    else:
        parts.append(f"Usual posture at symptom onset: {_UNDETERMINED}.")

    pcp = _yn(f.get("posture_change_provokes"))
    bld = _yn(f.get("better_lying_down"))

    if pcp == "yes":
        parts.append("Postural change from lying or sitting to standing provokes symptoms.")
    elif pcp == "no":
        parts.append("Postural change from lying or sitting to standing does not provoke symptoms.")
    else:
        parts.append(f"Whether postural change provokes symptoms is {_UNDETERMINED}.")

    if bld == "yes":
        parts.append("Symptoms improve when lying down.")
    elif bld == "no":
        parts.append("Symptoms are not reported to improve when lying down.")
    else:
        parts.append(f"Whether lying down improves symptoms is {_UNDETERMINED}.")

    return " ".join(parts)


def _compose_triggers(f):
    """Triggers + exercise syncope + menstrual correlation."""
    parts = []
    triggers = _sentence_case_list(f.get("triggers"))
    if _has(triggers) and triggers != "none reported":
        parts.append(f"Reported symptom triggers include {triggers}.")
    elif triggers == "none reported":
        parts.append("No specific symptom triggers were reported.")
    else:
        parts.append(f"Symptom triggers: {_UNDETERMINED}.")

    sde = _yn(f.get("syncope_during_exercise"))
    sae = _yn(f.get("syncope_after_exercise"))
    if sde == "no" and sae == "no":
        parts.append("No exercise-related syncope was reported.")
    elif sde == "yes" or sae == "yes":
        ex_parts = []
        if sde == "yes":
            ex_parts.append("during exercise")
        if sae == "yes":
            ex_parts.append("after exercise")
        parts.append(f"Exercise-related syncope was reported {_join_and(ex_parts)}.")
    else:
        parts.append(f"Exercise-related syncope: {_UNDETERMINED}.")

    mc = _yn(f.get("menstrual_correlation"))
    md = f.get("menstrual_detail")
    if mc == "yes":
        if _has(md):
            parts.append(f"A correlation with the menstrual cycle was observed: {_trim_trailing_period(md)}.")
        else:
            parts.append("A correlation with the menstrual cycle was observed.")
    elif mc == "no":
        parts.append("No correlation with the menstrual cycle was reported.")
    else:
        parts.append(f"Menstrual cycle correlation: {_UNDETERMINED}.")

    obs = f.get("other_observations")
    if _has(obs):
        parts.append(f"Other observations: {_trim_trailing_period(obs)}.")

    return " ".join(parts)


def _compose_symptoms(f):
    """Associated symptoms + palpitations."""
    parts = []
    symptoms = _sentence_case_list(f.get("symptoms"))
    palp = _yn(f.get("palpitations"))
    palp_type = _sentence_case_list(f.get("palpitation_type"))

    if _has(symptoms) and symptoms != "none reported":
        sym_str = symptoms
    elif symptoms == "none reported":
        sym_str = None
    else:
        sym_str = None

    if palp == "yes":
        if _has(palp_type) and palp_type != "none reported":
            palp_str = f"palpitations ({palp_type})"
        else:
            palp_str = "palpitations"
    elif palp == "no":
        palp_str = None
    else:
        palp_str = None

    # Build sentence(s) — keep OCR-formatted symptom string intact, append palpitations cleanly
    if sym_str and palp_str:
        parts.append(f"Associated symptoms include {sym_str}, and {palp_str}.")
    elif sym_str:
        parts.append(f"Associated symptoms include {sym_str}.")
    elif palp_str:
        parts.append(f"Associated symptoms: {palp_str} reported.")
    elif symptoms == "none reported" and palp == "no":
        parts.append("No associated symptoms or palpitations were reported.")
    else:
        parts.append(f"Associated symptoms: {_UNDETERMINED}.")

    return " ".join(parts)


def _compose_medical_history(f):
    """Comorbidities, GI, mental health, and family history grouped together."""
    parts = []

    # Comorbid conditions (Q31 + Q32)
    cond = _sentence_case_list(f.get("conditions"))
    if _has(cond) and cond != "none reported":
        parts.append(f"Comorbid conditions include {cond}.")
    elif cond == "none reported":
        parts.append("No comorbid conditions were reported.")
    else:
        parts.append(f"Comorbid conditions: {_UNDETERMINED}.")

    # GI (Q33 + Q34)
    gi_dx = _sentence_case_list(f.get("gi_diagnosis"))
    gi_sx = _sentence_case_list(f.get("gi_symptoms"))
    gi_parts = []
    if _has(gi_dx) and gi_dx != "none reported":
        gi_parts.append(gi_dx)
    if _has(gi_sx) and gi_sx != "none reported":
        gi_parts.append(gi_sx)
    if gi_parts:
        parts.append(f"Gastrointestinal history: {'; '.join(gi_parts)}.")
    elif gi_dx == "none reported" and gi_sx == "none reported":
        parts.append("No gastrointestinal conditions or symptoms were reported.")
    else:
        pass  # Omit GI line if genuinely undetermined — avoid noise

    # Mental health (Q35)
    mh = _sentence_case_list(f.get("mental_health"))
    if _has(mh) and mh != "none reported":
        parts.append(f"Mental health diagnoses include {mh}.")
    elif mh == "none reported":
        parts.append("No mental health diagnoses were reported.")
    # else: omit if undetermined

    # Family history (Q29 + Q30)
    fh = f.get("family_history")
    fhc = f.get("family_hx_cardiac")
    fh_parts = []
    if _has(fh):
        fh_parts.append(f"hypotension/fainting/POTS: {fh}")
    if _has(fhc) and fhc != "none reported":
        fh_parts.append(f"cardiac: {fhc}")
    if fh_parts:
        parts.append(f"Family history — {'; '.join(fh_parts)}.")
    elif fh == "unremarkable" and (not _has(fhc) or fhc == "none reported"):
        parts.append("Family history is unremarkable.")
    else:
        parts.append(f"Family history: {_UNDETERMINED}.")

    return " ".join(parts)


def _compose_medications(f):
    """List only medications the patient is currently taking or has used relevantly."""
    nc = f.get("negative_chronotropes")
    ad = f.get("antidepressants")
    fl = f.get("fludrocortisone_status")
    md_status = f.get("midodrine_status")
    om = f.get("other_medications")

    current = []  # things they ARE on now
    previous = []  # things they HAVE taken but stopped

    # Negative chronotropes (Q36) — only include if actually on something
    if _has(nc):
        nc_l = nc.lower()
        if "beta blocker" in nc_l or "ivabradine" in nc_l:
            current.append(nc)
        # "No" → not on any, omit silently

    # Antidepressants (Q37) — only include if on something
    if _has(ad) and ad != "none reported":
        current.append(ad)

    # Fludrocortisone (Q38)
    if _has(fl):
        fl_l = fl.lower()
        if "current" in fl_l:
            current.append("fludrocortisone")
        elif "discontinued" in fl_l:
            previous.append("fludrocortisone (discontinued)")

    # Midodrine (Q39)
    if _has(md_status):
        md_l = md_status.lower()
        if "current" in md_l:
            current.append("midodrine")
        elif "discontinued" in md_l:
            previous.append("midodrine (discontinued)")

    # Other medications (Q40)
    if _has(om):
        current.append(_trim_trailing_period(om))

    sentence_parts = []
    if current:
        sentence_parts.append(f"Current medications: {_join_and(current)}.")
    if previous:
        sentence_parts.append(f"Previously trialled: {_join_and(previous)}.")
    if not current and not previous:
        sentence_parts.append("No relevant current medications were reported.")

    return " ".join(sentence_parts)


def _compose_investigations(f):
    inv = f.get("investigations")
    comm = f.get("investigation_comments")
    parts = []
    if _has(inv) and inv != "none reported":
        parts.append(f"Prior investigations include {inv}.")
    elif inv == "none reported":
        parts.append("No prior investigations were recorded.")
    else:
        parts.append(f"Prior investigations: {_UNDETERMINED}.")
    if _has(comm):
        parts.append(f"Additional investigation notes: {_trim_trailing_period(comm)}.")
    return " ".join(parts)


def _compose_test(f):
    parts = []
    fn = f.get("first_name", "<HMS-Patient_FirstName>")

    # Test type
    drug = f.get("tilt_drug")
    test_type = f.get("test_type")
    if drug == "Isoprenaline":
        test_str = "an isoprenaline-provoked tilt table test"
    elif drug == "GTN":
        test_str = "a GTN-provoked tilt table test"
    elif drug is None and _has(test_type) and "passive" in test_type.lower():
        test_str = "a passive tilt table test (no pharmacological provocation)"
    else:
        test_str = f"a tilt table test ({_UNDETERMINED} provocation)"
    parts.append(f"{fn} underwent {test_str}.")

    # Baseline vitals
    bp = f.get("baseline_bp") or _UNDETERMINED
    hr = f.get("baseline_hr")
    hr_str = str(hr) if hr is not None else _UNDETERMINED
    rhythm = f.get("baseline_rhythm")
    rhythm_str = f", baseline rhythm {rhythm}" if _has(rhythm) else ""
    parts.append(f"Baseline observations were BP {bp} mmHg, HR {hr_str} bpm{rhythm_str}.")

    # Control phase
    ctrl_calc = f.get("control_result_calc")
    ctrl_tol = f.get("control_tolerance")
    ctrl_sev = f.get("control_symptom_severity") or "mild"
    ctrl_notes = f.get("control_notes", "")
    if ctrl_calc == _RESULT_POTS:
        ctrl_desc = "an HR rise meeting POTS criteria (≥30 bpm, or ≥40 bpm aged 12–19)"
    elif ctrl_calc == _RESULT_OI:
        ctrl_desc = "a sustained HR rise of ≥20 bpm without meeting POTS criteria"
    elif ctrl_calc == _RESULT_VVS:
        ctrl_desc = "a fall in systolic BP of >20 mmHg and/or HR <50 bpm"
    elif ctrl_calc == _RESULT_NORMAL:
        ctrl_desc = "no significant haemodynamic change"
    else:
        ctrl_desc = _UNDETERMINED
    sev_phrase = f"{ctrl_sev} symptoms" if ctrl_sev != "no" else "no symptoms"
    parts.append(f"During the control phase, {ctrl_desc} was observed; {fn} {ctrl_tol or _UNDETERMINED} with {sev_phrase}.")
    if ctrl_notes and not ctrl_notes.startswith("[REVIEW") and not ctrl_notes.startswith(_UNDETERMINED):
        note_clean = ctrl_notes.rstrip()
        if not note_clean.endswith((".", "!", "?")):
            note_clean += "."
        parts.append(f"Control phase clinician note: {note_clean}")

    # Phase 2
    p2_calc = f.get("phase2_result_calc")
    p2_tol = f.get("phase2_tolerance")
    p2_notes = f.get("phase2_notes", "")
    stop_min = f.get("phase2_stop_minute")
    stop_str = ""
    if stop_min and stop_min < 10:
        stop_str = f" The phase 2 protocol was terminated at {stop_min} {'minute' if stop_min == 1 else 'minutes'}."
    if p2_calc == _RESULT_NOT_REACHED:
        parts.append("Phase 2 pharmacological provocation was not administered." + stop_str)
    elif drug is None and (_has(test_type) and "passive" in test_type.lower()):
        parts.append(f"No pharmacological provocation was administered (passive tilt only); {fn} {p2_tol or _UNDETERMINED}." + stop_str)
    else:
        if p2_calc == _RESULT_POTS:
            p2_desc = "an HR rise meeting POTS criteria"
        elif p2_calc == _RESULT_OI:
            p2_desc = "a sustained HR rise of ≥20 bpm without meeting POTS criteria"
        elif p2_calc == _RESULT_VVS:
            p2_desc = "a fall in systolic BP of >20 mmHg and/or HR <50 bpm"
        elif p2_calc == _RESULT_NORMAL:
            p2_desc = "no significant haemodynamic change"
        else:
            p2_desc = _UNDETERMINED
        drug_str = drug if drug else "the provocation agent"
        parts.append(f"Following administration of {drug_str}, {p2_desc} was observed; {fn} {p2_tol or _UNDETERMINED}." + stop_str)
    if p2_notes and not p2_notes.startswith("[REVIEW") and not p2_notes.startswith(_UNDETERMINED):
        note_clean = p2_notes.rstrip()
        if not note_clean.endswith((".", "!", "?")):
            note_clean += "."
        parts.append(f"Phase 2 clinician note: {note_clean}")

    # Recovery vitals
    rec_bp = f.get("recovery_bp")
    rec_hr = f.get("recovery_hr")
    rec_bp_str = rec_bp if rec_bp else "not recorded"
    rec_hr_str = str(rec_hr) if rec_hr is not None else "not recorded"
    parts.append(f"Recovery observations were BP {rec_bp_str} mmHg, HR {rec_hr_str} bpm.")

    # Symptom correlation
    sc = f.get("symptom_correlation")
    if _has(sc):
        sc_l = sc.lower()
        if "correlate" in sc_l and "different" not in sc_l:
            parts.append("Symptoms experienced during the test correlated with the patient's baseline symptoms.")
        elif "different" in sc_l:
            parts.append("Symptoms experienced during the test were different to the patient's baseline symptoms.")
        elif "no symptom" in sc_l:
            parts.append("No symptoms were experienced during the test.")
        else:
            parts.append(f"Symptom correlation with baseline: {sc}.")
    else:
        parts.append(f"Symptom correlation with baseline: {_UNDETERMINED}.")

    # Free-text results conclusion
    rc = f.get("results_conclusion")
    if _has(rc):
        parts.append(f"Clinician's results conclusion: {_trim_trailing_period(rc)}.")

    return " ".join(parts)


# ─────────────────────────────────────────────────────────────
# Conclusion + Recommendation
# ─────────────────────────────────────────────────────────────

def _normalise_result_label(raw):
    """
    Map a raw Page 7 selection (e.g. "Vasovagal syncope") to a canonical key
    used by conclusion/recommendation logic. Returns None if undetermined.
    """
    if not _has(raw):
        return None
    s = str(raw).strip().lower()
    if "pots" in s:
        return "POTS"
    if "postural hypotension" in s or "orthostatic hypotension" in s:
        return "OH"
    if "vasovagal syncope" in s:
        return "VVS"
    if "vasovagal presyncope" in s:
        return "VVP"
    if "mixed" in s:
        return "MIXED"
    if "normal" in s:
        return "NORMAL"
    return None


def _compose_conclusion(f):
    """
    Build a one-sentence conclusion based on Page 7 result fields.
    Falls back to calculated results if Page 7 fields are undetermined.
    Returns (conclusion_sentence, diagnosis_key) where diagnosis_key drives
    the recommendation choice.
    """
    ctrl_raw = f.get("control_result_raw")
    p2_raw = f.get("phase2_result_raw")

    ctrl_key = _normalise_result_label(ctrl_raw)
    p2_key = _normalise_result_label(p2_raw)

    # Fallback: use calculated result labels when Page 7 fields are missing
    if ctrl_key is None:
        cc = f.get("control_result_calc")
        if cc == _RESULT_POTS:
            ctrl_key = "POTS"
        elif cc == _RESULT_VVS:
            ctrl_key = "VVS"
        elif cc == _RESULT_OI:
            ctrl_key = "OH"  # OI grouped with OH for recommendation purposes
        elif cc == _RESULT_NORMAL:
            ctrl_key = "NORMAL"

    if p2_key is None:
        pc = f.get("phase2_result_calc")
        if pc == _RESULT_POTS:
            p2_key = "POTS"
        elif pc == _RESULT_VVS:
            p2_key = "VVS"
        elif pc == _RESULT_OI:
            p2_key = "OH"
        elif pc == _RESULT_NORMAL:
            p2_key = "NORMAL"
        elif pc == _RESULT_NOT_REACHED:
            p2_key = "NOT_REACHED"

    # Decide overall diagnosis. Positive findings take priority over normal.
    priority = ["POTS", "OH", "VVS", "VVP", "MIXED"]
    keys_present = [k for k in (ctrl_key, p2_key) if k in priority]
    if keys_present:
        # Pick the highest-priority positive finding
        diagnosis = next(k for k in priority if k in keys_present)
    elif ctrl_key == "NORMAL" and p2_key in ("NORMAL", "NOT_REACHED", None):
        diagnosis = "NORMAL"
    elif ctrl_key in ("NORMAL", None) and p2_key == "NORMAL":
        diagnosis = "NORMAL"
    else:
        diagnosis = "UNDETERMINED"

    sentence_map = {
        "POTS": "Conclusion: Positive study for POTS.",
        "OH": "Conclusion: Positive study for orthostatic hypotension.",
        "VVS": "Conclusion: Positive study for vasovagal syncope.",
        "VVP": "Conclusion: Positive study for vasovagal presyncope.",
        "MIXED": "Conclusion: Positive study for mixed response.",
        "NORMAL": "Conclusion: Negative study.",
        "UNDETERMINED": f"Conclusion: {_UNDETERMINED}.",
    }
    return sentence_map[diagnosis], diagnosis


def _compose_recommendation(diagnosis):
    rec_map = {
        "POTS": (
            "Recommendation: Increase fluid intake, target 3L per day. Regular exercise. "
            "Consider addition of fludrocortisone, midodrine, ivabradine."
        ),
        "OH": (
            "Recommendation: Increase fluid intake, target 3L per day. Regular exercise. "
            "Consider addition of fludrocortisone, midodrine, ivabradine."
        ),
        "VVS": (
            "Recommendation: Avoid known triggers. Counter-pressure manoeuvres at symptom onset. "
            "Increase fluid and salt intake. Consider midodrine if symptoms persist despite "
            "conservative measures."
        ),
        "VVP": (
            "Recommendation: Avoid known triggers. Counter-pressure manoeuvres at symptom onset. "
            "Increase fluid and salt intake. Consider midodrine if symptoms persist despite "
            "conservative measures."
        ),
        "MIXED": (
            "Recommendation: Avoid known triggers. Counter-pressure manoeuvres at symptom onset. "
            "Increase fluid and salt intake. Consider midodrine if symptoms persist despite "
            "conservative measures."
        ),
        "NORMAL": "Recommendation: No specific intervention indicated based on this study.",
        "UNDETERMINED": f"Recommendation: {_UNDETERMINED} — to be completed by clinician.",
    }
    return rec_map.get(diagnosis, rec_map["UNDETERMINED"])


# ─────────────────────────────────────────────────────────────
# Report builder
# ─────────────────────────────────────────────────────────────

def build_report(fields):
    """
    Populate the HealthTrack report from extracted fields.
    Output is one flowing narrative under 'Summary', then 'Conclusion'
    and 'Recommendation' single-line headings.
    Returns (report_text: str, undetermined_count: int).
    """
    summary_blocks = [
        _compose_demographics(fields),
        _compose_history(fields),
        _compose_postural(fields),
        _compose_triggers(fields),
        _compose_symptoms(fields),
        _compose_medical_history(fields),
        _compose_medications(fields),
        _compose_investigations(fields),
        _compose_test(fields),
    ]
    summary_text = "\n\n".join(b.strip() for b in summary_blocks if b and b.strip())

    conclusion_sentence, diagnosis_key = _compose_conclusion(fields)
    recommendation_sentence = _compose_recommendation(diagnosis_key)

    full_report = (
        "Summary\n"
        f"{summary_text}\n\n"
        f"{conclusion_sentence}\n\n"
        f"{recommendation_sentence}"
    )

    undetermined_count = len(re.findall(re.escape(_UNDETERMINED), full_report))
    return full_report, undetermined_count


# ─────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────

def llm_cleanup_report(report_text, api_key):
    """
    Optional post-processing step: pass the deterministic report through GPT-4o-mini
    for grammar and prose cleanup. Clinical facts, values, and [undetermined] markers
    are never modified — the system prompt enforces this strictly.

    Returns the cleaned report on success, or the original report if the API call
    fails (network error, quota, invalid key, etc.).

    NOTE: calling this function sends the report text (including patient data such
    as age, sex, clinical findings) to the OpenAI API. The caller is responsible
    for ensuring this is appropriate for their clinical context and privacy obligations.
    """
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        system_prompt = (
            "You are a clinical documentation assistant helping format a tilt table test report "
            "for a physiotherapy electronic medical record.\n\n"
            "Your task: improve the grammar, sentence flow and readability of the report text "
            "provided by the user.\n\n"
            "Rules you must follow without exception:\n"
            "1. Do NOT add, remove or change any clinical facts, numbers, diagnoses, dates, "
            "medications, measurements or values.\n"
            "2. Do NOT add any clinical interpretations, opinions or recommendations not already "
            "present in the text.\n"
            "3. Keep the three section headings (Summary, Conclusion:, Recommendation:) exactly "
            "as-is — same capitalisation, same position.\n"
            "4. Keep every [undetermined] placeholder as the exact literal string [undetermined].\n"
            "5. Keep <HMS-Patient_FirstName> exactly as-is.\n"
            "6. Normalise capitalisation: common nouns and condition names that appear "
            "mid-sentence should be lowercase (e.g. 'emotional stress', 'brain fogging', "
            "'chronic fatigue'). Preserve medical acronyms in uppercase: POTS, IBS, ECG, "
            "ECHO, EEG, MRI, CT, EP, SSRI, SNRI, ADHD, MCAS, GTN, OCP.\n"
            "7. Return only the cleaned report text — no preamble, no explanation."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": report_text},
            ],
            temperature=0.1,
            max_tokens=2500,
        )
        cleaned = response.choices[0].message.content.strip()
        if not cleaned:
            return report_text
        # Strip trailing whitespace from each line (GPT sometimes adds markdown
        # double-space line breaks) and normalise multiple blank lines.
        lines = [line.rstrip() for line in cleaned.splitlines()]
        return "\n".join(lines)

    except Exception as e:
        logger.warning("LLM grammar cleanup failed: %s — returning original report", e)
        return report_text


def process_pdf(pdf_bytes):
    """
    Main entry point. Takes raw PDF bytes, returns (report_text, undetermined_count).
    """
    try:
        text = extract_text_from_pdf(pdf_bytes)
        logger.debug("Extracted %d characters from PDF", len(text))
    except Exception as e:
        logger.error("PDF extraction failed: %s", e)
        raise ValueError(f"Could not read PDF: {e}")

    ocr_results = _ocr_checkboxes(pdf_bytes)
    logger.debug("Checkbox OCR results: %s", ocr_results)

    fields = extract_fields(text, ocr_results)
    report, undetermined_count = build_report(fields)
    return report, undetermined_count

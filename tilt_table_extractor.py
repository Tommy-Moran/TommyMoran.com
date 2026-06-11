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
            "Standing": "standing posture",
            "Sitting": "seated posture",
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
        "display_map": {
            "Gastroperesis/early satiety": "gastroparesis/early satiety",
            "Oesophageal Dysmotility": "oesophageal dysmotility",
        },
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

    # Attempt to extract last name from common REDCap name field formats.
    # Try broadest variety of label/format combinations first.
    d["last_name"] = _field(
        text,
        # "Surname Smith" or "Patient surname Smith" (space-separated, no colon — REDCap flattened)
        r"(?:Patient\s+)?[Ss]urname\s+([A-Za-z''\-]{2,})",
        # "Last name: Smith" or "Last Name Smith"
        r"[Ll]ast\s+[Nn]ame[:\s]+([A-Za-z''\-]{2,})",
        # "Family name Smith" or "Family Name: Smith"
        r"[Ff]amily\s+[Nn]ame[:\s]+([A-Za-z''\-]{2,})",
        # "Name: Smith, John" or "Patient Name Smith," — last name before comma
        r"(?:Patient\s+)?Name[:\s]+([A-Za-z''\-]{2,})\s*,",
        # "Participant: Smith, John"
        r"Participant[:\s]+([A-Za-z''\-]{2,})\s*,",
        label="last_name"
    )
    # Title-case the extracted name (REDCap may store it all-caps or all-lowercase)
    if d["last_name"] and d["last_name"] != _UNDETERMINED:
        d["last_name"] = d["last_name"].capitalize()
    else:
        d["last_name"] = None

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
    """Convert a count + unit to a qualitative frequency word: daily/weekly/monthly/rarely."""
    unit_lower = unit_str.lower()

    count = 1
    if count_str and count_str not in ("", "______"):
        try:
            count = int(count_str)
        except (ValueError, TypeError):
            count = 1

    # Approximate weekly rate for bucketing
    per_week = {
        "day": count * 7,
        "week": count,
        "month": count / 4.33,
        "year": count / 52,
    }.get(unit_lower, count)

    if per_week >= 6:
        return "daily"
    if per_week >= 1:
        return "weekly"
    if per_week >= 0.2:
        return "monthly"
    return "rarely"


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


def _lc_first(s):
    """Lowercase the first character of a string (for free-text inserted mid-sentence)."""
    if not s:
        return s
    return s[0].lower() + s[1:]


def _patient_ref(f):
    """Return 'Mr/Ms/Mx LastName' based on extracted name and sex, or the HMS placeholder."""
    last = f.get("last_name")
    sex = f.get("sex", "")
    if _has(last):
        sex_l = str(sex).lower()
        if sex_l == "male":
            title = "Mr"
        elif sex_l == "female":
            title = "Ms"
        else:
            title = "Mx"
        return f"{title} {last}"
    return "<HMS-Patient_FirstName>"


def _max_hr_rise_control(f):
    """Return peak HR rise (bpm) during the control phase, or None."""
    readings = f.get("control_readings", [])
    baseline_hr = f.get("baseline_hr")
    if not readings or baseline_hr is None:
        return None
    max_hr = max(hr for _, hr in readings)
    return max_hr - baseline_hr


def _max_hr_rise_phase2(f):
    """Return peak HR rise during phase 2 relative to phase 2 baseline reading, or None."""
    readings = f.get("phase2_readings", [])
    if len(readings) < 2:
        return None
    baseline_hr = readings[0][1]
    subsequent = readings[1:]
    max_hr = max(hr for _, hr in subsequent)
    return max_hr - baseline_hr


def _vvs_subtype(readings, baseline_sbp):
    """
    Determine VVS subtype from a sequence of (sbp, hr) readings.
    Returns 'bp_first' if SBP drops >20 before HR drops below 50,
    'hr_first' otherwise.
    """
    bp_drop_idx = None
    hr_drop_idx = None
    for i, (sbp, hr) in enumerate(readings):
        if bp_drop_idx is None and baseline_sbp and (baseline_sbp - sbp) > 20:
            bp_drop_idx = i
        if hr_drop_idx is None and hr < 50:
            hr_drop_idx = i
    if bp_drop_idx is not None and hr_drop_idx is not None:
        return "bp_first" if bp_drop_idx <= hr_drop_idx else "hr_first"
    if bp_drop_idx is not None:
        return "bp_first"
    return "hr_first"


# Medical acronyms/abbreviations that must remain uppercase mid-sentence
_KEEP_UPPER = {
    "pots", "ibs", "ecg", "eeg", "mri", "ct", "ep",
    "ssri", "snri", "adhd", "mcas", "gtn", "ocp", "oi",
}

# Words that look like acronyms (all-caps, short) but must be lowercase
_FORCE_LOWER = {"echo"}

# Proper nouns that must always be title-cased
_KEEP_TITLE = {"holter"}


def _sentence_case_list(text):
    """
    Lowercase a comma/and-joined OCR label string, preserving known medical
    acronyms and all-uppercase abbreviations of ≤5 chars.

    'Emotional Stress, Known Dehydration' → 'emotional stress, known dehydration'
    'ECG, ECHO and Stress Test'           → 'ECG, echo and stress test'
    'POTS, IBS'                           → 'POTS, IBS'
    'HOLTER MONITOR'                      → 'Holter monitor'
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
        if core_lower in _FORCE_LOWER:
            return core_lower + punct_tail    # force lowercase
        if core_lower in _KEEP_UPPER:
            return core + punct_tail          # keep original casing
        if core_lower in _KEEP_TITLE:
            return core_lower[0].upper() + core_lower[1:] + punct_tail  # force title case
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

    dur_n, dur_u = f.get("duration_number"), f.get("duration_unit")
    pre_dur_n, pre_dur_u = f.get("presyncope_duration_number"), f.get("presyncope_duration_unit")
    freq = f.get("frequency")
    pre_freq = f.get("presyncope_frequency")

    # Syncope history — zero or missing duration = no overt syncope
    has_syncope_dur = _has(dur_n) and _has(dur_u) and str(dur_n).strip() not in ("0", "")
    if has_syncope_dur:
        s = f"Syncope symptoms for {dur_n} {dur_u}"
        if _has(freq):
            s += f", occurring {freq}"
        s += "."
        parts.append(s)
    else:
        parts.append("No overt syncope.")

    # Presyncope history — zero or missing duration handled similarly
    has_presync_dur = _has(pre_dur_n) and _has(pre_dur_u) and str(pre_dur_n).strip() not in ("0", "")
    if has_presync_dur:
        s = f"Presyncope symptoms for {pre_dur_n} {pre_dur_u}"
        if _has(pre_freq):
            s += f", occurring {pre_freq}"
        s += "."
        parts.append(s)
    elif _has(pre_freq):
        parts.append(f"Presyncope symptoms occurring {pre_freq}.")
    # else: omit silently — no presyncope to report

    # Warning syncope — template phrasing
    nws = f.get("no_warning_syncope")
    if _has(nws):
        nws_l = str(nws).lower()
        if nws_l == "never":
            parts.append("Never experiences high risk syncope.")
        elif nws_l == "rare":
            parts.append("Rarely experiences high risk syncope.")
        elif nws_l == "frequent":
            parts.append("Frequently experiences high risk syncope.")
        else:
            parts.append(f"High risk syncope frequency: {nws}.")
    else:
        parts.append(f"High risk syncope frequency: {_UNDETERMINED}.")

    # Initiating event — template phrasing; lowercase free-text detail
    ile = f.get("initiating_life_event")
    detail = f.get("initiating_event_detail")
    if _yn(ile) == "yes":
        sub = []
        if _yn(f.get("event_was_medical")) == "yes":
            sub.append("medical illness")
        if _yn(f.get("event_was_surgical")) == "yes":
            sub.append("surgical or trauma")
        if _yn(f.get("event_was_emotional")) == "yes":
            sub.append("emotional trauma")
        if _has(detail):
            context = _lc_first(_trim_trailing_period(detail))
        elif sub:
            context = _join_and(sub)
        else:
            context = "a known event"
        parts.append(f"Symptom onset occurred in the context of {context}.")
    elif _yn(ile) == "no":
        parts.append("No clear precipitating illness/factors identified.")
    else:
        parts.append(f"Precipitating illness/factors: {_UNDETERMINED}.")

    return " ".join(parts)


def _compose_postural(f):
    parts = []
    posture = f.get("posture")
    if _has(posture):
        parts.append(f"Symptoms typically occur in the {str(posture).lower()}.")
    else:
        parts.append(f"Usual posture at symptom onset: {_UNDETERMINED}.")

    pcp = _yn(f.get("posture_change_provokes"))
    bld = _yn(f.get("better_lying_down"))

    if pcp == "yes":
        parts.append("Change in posture from lying/seated to standing provokes symptoms.")
    elif pcp == "no":
        parts.append("Change in posture from lying/seated to standing does not provoke symptoms.")
    else:
        parts.append(f"Whether postural change provokes symptoms is {_UNDETERMINED}.")

    if bld == "yes":
        parts.append("Symptoms improve when lying down.")
    elif bld == "no":
        parts.append("Symptoms unaffected by lying down.")
    else:
        parts.append(f"Whether lying down improves symptoms is {_UNDETERMINED}.")

    return " ".join(parts)


def _compose_triggers(f):
    """Triggers + exercise syncope + menstrual correlation."""
    parts = []
    triggers = _sentence_case_list(f.get("triggers"))
    if _has(triggers) and triggers != "none reported":
        parts.append(f"Common triggers include: {triggers}.")
    elif triggers == "none reported":
        parts.append("No specific symptom triggers were reported.")
    else:
        parts.append(f"Symptom triggers: {_UNDETERMINED}.")

    # Only report exercise syncope if it was actually present
    sde = _yn(f.get("syncope_during_exercise"))
    sae = _yn(f.get("syncope_after_exercise"))
    if sde == "yes" or sae == "yes":
        ex_parts = []
        if sde == "yes":
            ex_parts.append("during exercise")
        if sae == "yes":
            ex_parts.append("after exercise")
        parts.append(f"Exercise-related syncope reported {_join_and(ex_parts)}.")

    # Only report menstrual correlation if present
    mc = _yn(f.get("menstrual_correlation"))
    md = f.get("menstrual_detail")
    if mc == "yes":
        if _has(md):
            parts.append(f"Menstrual cycle correlation: {_lc_first(_trim_trailing_period(md))}.")
        else:
            parts.append("A correlation with the menstrual cycle was observed.")

    obs = f.get("other_observations")
    if _has(obs):
        parts.append(f"Other observations: {_lc_first(_trim_trailing_period(obs))}.")

    return " ".join(parts)


def _compose_symptoms(f):
    """Associated symptoms + palpitations — palpitations come first, no duplication."""
    symptoms_raw = _sentence_case_list(f.get("symptoms"))
    palp = _yn(f.get("palpitations"))
    palp_type = _sentence_case_list(f.get("palpitation_type"))

    # Build palpitations string (comes first per user requirement)
    if palp == "yes":
        palp_str = (f"palpitations ({palp_type})"
                    if (_has(palp_type) and palp_type != "none reported")
                    else "palpitations")
    else:
        palp_str = None

    # Strip "palpitations" from the OCR symptoms string to avoid duplication
    if _has(symptoms_raw) and symptoms_raw != "none reported":
        clean_symp = re.sub(r',?\s*palpitations?\b', '', symptoms_raw, flags=re.I)
        clean_symp = clean_symp.strip().strip(',').strip()
    else:
        clean_symp = None

    # Assemble: palpitations first, then the rest
    feature_parts = []
    if palp_str:
        feature_parts.append(palp_str)
    if clean_symp:
        feature_parts.append(clean_symp)

    if feature_parts:
        return f"Common associated features include: {', '.join(feature_parts)}."
    if symptoms_raw == "none reported" and palp == "no":
        return "No associated features were reported."
    return f"Associated features: {_UNDETERMINED}."


def _compose_medical_history(f):
    """
    All condition categories (associated conditions, GI, mental health) merged into
    one flat 'Associated conditions include:' list, followed by family history.
    """
    parts = []

    # Collect every condition item into a single flat list
    all_items = []

    def _add(field_val):
        v = _sentence_case_list(field_val)
        if _has(v) and v != "none reported":
            # Split "a, b and c" back to individual items, strip blanks
            for item in re.split(r',\s*|\s+and\s+', v):
                item = item.strip()
                if item:
                    all_items.append(item)

    _add(f.get("conditions"))
    _add(f.get("mental_health"))

    # GI: any GI condition/symptom → single "suspected IBS" entry
    gi_diag = _sentence_case_list(f.get("gi_diagnosis"))
    gi_symp = _sentence_case_list(f.get("gi_symptoms"))
    if ((_has(gi_diag) and gi_diag != "none reported") or
            (_has(gi_symp) and gi_symp != "none reported")):
        all_items.append("suspected IBS")

    cond_raw = f.get("conditions")
    cond_none = (_sentence_case_list(cond_raw) == "none reported")

    if all_items:
        parts.append(f"Associated conditions include: {', '.join(all_items)}.")
    elif cond_none:
        parts.append("No associated conditions were reported.")
    else:
        parts.append(f"Associated conditions: {_UNDETERMINED}.")

    # Family history — template format
    fh = f.get("family_history")
    fhc = f.get("family_hx_cardiac")
    if fh == "unremarkable" and (not _has(fhc) or fhc == "none reported"):
        parts.append("Family history is unremarkable.")
    elif _has(fh) and fh != "unremarkable":
        parts.append(f"Family history is {fh} with hypotension/fainting.")
    elif _has(fhc) and fhc != "none reported":
        parts.append(f"Family history is remarkable for {fhc} with POTS.")
    else:
        parts.append(f"Family history: {_UNDETERMINED}.")

    return "\n".join(parts)


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
        parts.append(f"Significant investigation results (as per patient): {inv}.")
    elif inv == "none reported":
        parts.append("Significant investigation results (as per patient): none reported.")
    else:
        parts.append(f"Significant investigation results (as per patient): {_UNDETERMINED}.")
    if _has(comm):
        parts.append(f"Additional investigation notes: {_trim_trailing_period(comm)}.")
    return " ".join(parts)


def _compose_test(f):
    """
    Produces two concise tilt interpretation sentences matching the HealthTrack
    template format, separated by a blank line:
      "Baseline tilt interpretation: [phrase]."
      "[Drug] tilt interpretation: [phrase]."
    """
    pr = _patient_ref(f)
    drug = f.get("tilt_drug")
    test_type = f.get("test_type")

    # Build bracketed symptom list from the patient's associated features survey data
    # e.g. "(dizziness, fatigue)" or "(palpitations (SVT), nausea)"
    symp_raw = _sentence_case_list(f.get("symptoms"))
    palp = _yn(f.get("palpitations"))
    palp_type = _sentence_case_list(f.get("palpitation_type"))
    symp_items = []
    if palp == "yes":
        symp_items.append(
            f"palpitations ({palp_type})" if (_has(palp_type) and palp_type != "none reported")
            else "palpitations"
        )
    if _has(symp_raw) and symp_raw != "none reported":
        clean = re.sub(r',?\s*palpitations?\b', '', symp_raw, flags=re.I).strip().strip(',').strip()
        if clean:
            symp_items.append(clean)
    symp_suffix = f" ({', '.join(symp_items)})" if symp_items else ""

    def _interp_phrase(result_calc, readings, baseline_sbp, hr_rise):
        fam = f"familiar symptoms{symp_suffix}"
        if result_calc == _RESULT_POTS:
            rise_str = f" with heart rate increase by {hr_rise} bpm" if hr_rise is not None else ""
            return f"positive for a POTS response{rise_str} and {pr} experienced {fam}"
        if result_calc == _RESULT_OI:
            return f"positive for orthostatic intolerance and {pr} experienced {fam}"
        if result_calc == _RESULT_VVS:
            subtype = _vvs_subtype(readings, baseline_sbp)
            if subtype == "bp_first":
                return (
                    f"positive for a vasovagal response with blood pressure drop prior to "
                    f"bradycardia and {pr} experienced {fam}"
                )
            return (
                f"positive for a vasovagal response with bradycardia occurring prior to "
                f"blood pressure drop and {pr} experienced {fam}"
            )
        if result_calc == _RESULT_NORMAL:
            return "normal"
        return _UNDETERMINED

    # Baseline tilt interpretation
    ctrl_calc = f.get("control_result_calc")
    ctrl_readings = f.get("control_readings", [])
    baseline_sbp = _extract_systolic(f.get("baseline_bp"))
    ctrl_hr_rise = _max_hr_rise_control(f)
    ctrl_phrase = _interp_phrase(ctrl_calc, ctrl_readings, baseline_sbp, ctrl_hr_rise)
    baseline_line = f"Baseline tilt interpretation: {ctrl_phrase}."

    # Clinician control notes (appended inline if present)
    ctrl_notes = f.get("control_notes", "")
    if ctrl_notes and not ctrl_notes.startswith("[REVIEW") and not ctrl_notes.startswith(_UNDETERMINED):
        note_clean = ctrl_notes.rstrip()
        if not note_clean.endswith((".", "!", "?")):
            note_clean += "."
        baseline_line += " " + note_clean

    paragraphs = [baseline_line]

    # Phase 2 / drug tilt interpretation
    p2_calc = f.get("phase2_result_calc")
    is_passive = (drug is None and _has(test_type) and "passive" in str(test_type).lower())

    if p2_calc not in (None, _RESULT_NOT_REACHED) and not is_passive:
        p2_readings = f.get("phase2_readings", [])
        p2_baseline_sbp = p2_readings[0][0] if p2_readings else None
        p2_subsequent = p2_readings[1:] if len(p2_readings) > 1 else []
        p2_hr_rise = _max_hr_rise_phase2(f)
        p2_phrase = _interp_phrase(p2_calc, p2_subsequent, p2_baseline_sbp, p2_hr_rise)

        if drug == "Isoprenaline":
            drug_label = "Isoprenaline"
        elif drug == "GTN":
            drug_label = "GTN"
        else:
            drug_label = "Pharmacological"

        drug_line = f"{drug_label} tilt interpretation: {p2_phrase}."

        p2_notes = f.get("phase2_notes", "")
        if p2_notes and not p2_notes.startswith("[REVIEW") and not p2_notes.startswith(_UNDETERMINED):
            note_clean = p2_notes.rstrip()
            if not note_clean.endswith((".", "!", "?")):
                note_clean += "."
            drug_line += " " + note_clean

        paragraphs.append(drug_line)

    # Free-text results conclusion from clinician
    rc = f.get("results_conclusion")
    if _has(rc):
        paragraphs.append(f"Clinician's results conclusion: {_trim_trailing_period(rc)}.")

    return "\n".join(paragraphs)


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
        "POTS": "Conclusions: Positive study for POTS.",
        "OH": "Conclusions: Positive study for orthostatic hypotension.",
        "VVS": "Conclusions: Positive study for vasovagal syncope.",
        "VVP": "Conclusions: Positive study for vasovagal presyncope.",
        "MIXED": "Conclusions: Positive study for mixed response.",
        "NORMAL": "Conclusions: Negative study.",
        "UNDETERMINED": f"Conclusions: {_UNDETERMINED}.",
    }
    return sentence_map[diagnosis], diagnosis


def _compose_recommendation(diagnosis):
    rec_map = {
        "POTS": (
            "Recommendations: Blood pressure support with fluid intake of >3 litres per day "
            "and high salt diet. "
            "Modified exercise program for postural retraining. "
            "Consider low dose fludrocortisone if symptoms persist despite optimisation of "
            "conservative measures."
        ),
        "OH": (
            "Recommendations: Blood pressure support with fluid intake of >3 litres per day "
            "and high salt diet. "
            "Modified exercise program for postural retraining. "
            "Consider low dose fludrocortisone if symptoms persist despite optimisation of "
            "conservative measures."
        ),
        "VVS": (
            "Recommendations: Avoid known triggers. Counter-pressure manoeuvres at symptom onset. "
            "Increase fluid and salt intake. Consider midodrine if symptoms persist despite "
            "optimisation of conservative measures."
        ),
        "VVP": (
            "Recommendations: Avoid known triggers. Counter-pressure manoeuvres at symptom onset. "
            "Increase fluid and salt intake. Consider midodrine if symptoms persist despite "
            "optimisation of conservative measures."
        ),
        "MIXED": (
            "Recommendations: Avoid known triggers. Counter-pressure manoeuvres at symptom onset. "
            "Increase fluid and salt intake. Consider midodrine if symptoms persist despite "
            "optimisation of conservative measures."
        ),
        "NORMAL": "Recommendations: No specific intervention indicated based on this study.",
        "UNDETERMINED": f"Recommendations: {_UNDETERMINED} — to be completed by clinician.",
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
    regular_blocks = [
        _compose_history(fields),
        _compose_postural(fields),
        _compose_triggers(fields),
        _compose_symptoms(fields),
        _compose_medical_history(fields),
        _compose_medications(fields),
        _compose_investigations(fields),
    ]
    regular_text = "\n".join(b.strip() for b in regular_blocks if b and b.strip())

    tilt_text = _compose_test(fields)

    conclusion_sentence, diagnosis_key = _compose_conclusion(fields)
    # Split "Conclusions: text" into heading + body on separate lines
    if ": " in conclusion_sentence:
        conc_head, conc_body = conclusion_sentence.split(": ", 1)
        conclusion_block = f"{conc_head}:\n{conc_body}"
    else:
        conclusion_block = conclusion_sentence

    # Append consistency statement for positive diagnoses
    _POSITIVE_DIAGNOSES = {"POTS", "OH", "VVS", "VVP", "MIXED"}
    if diagnosis_key in _POSITIVE_DIAGNOSES:
        conclusion_block += "\nClinical history is consistent with this diagnosis."

    recommendation_sentence = _compose_recommendation(diagnosis_key)
    # Split "Recommendations: text" into heading + one sentence per line
    if ": " in recommendation_sentence:
        rec_head, rec_body = recommendation_sentence.split(": ", 1)
        rec_sentences = [s.strip() for s in rec_body.split(". ") if s.strip()]
        rec_sentences = [(s if s.endswith(".") else s + ".") for s in rec_sentences]
        recommendation_block = rec_head + ":\n" + "\n".join(rec_sentences)
    else:
        recommendation_block = recommendation_sentence

    full_report = (
        "Summary\n"
        f"{regular_text}\n\n"
        f"{tilt_text}\n\n"
        f"{conclusion_block}\n\n"
        f"{recommendation_block}"
    )

    undetermined_count = len(re.findall(re.escape(_UNDETERMINED), full_report))
    return full_report, undetermined_count


# ─────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────

def llm_cleanup_report(report_text, anthropic_api_key=None, openai_api_key=None):
    """
    Optional post-processing step: pass the deterministic report through an LLM
    for grammar and prose cleanup. Claude Sonnet is preferred; falls back to
    GPT-4o-mini if only an OpenAI key is available.

    Clinical facts, values, and [undetermined] markers are never modified —
    the system prompt enforces this strictly.

    Returns the cleaned report on success, or the original report if the API
    call fails (network error, quota, invalid key, etc.).

    NOTE: calling this function sends the report text (including patient data such
    as age, sex, clinical findings) to the API provider. The caller is responsible
    for ensuring this is appropriate for their clinical context and privacy obligations.
    """
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
        "3. Keep the three section headings (Summary, Conclusions:, Recommendations:) exactly "
        "as-is — same capitalisation, each on its own line.\n"
        "4. Keep every [undetermined] placeholder as the exact literal string [undetermined].\n"
        "5. Keep any 'Mr/Ms/Mx [Name]' patient references exactly as-is. Also keep "
        "<HMS-Patient_FirstName> exactly as-is if it appears.\n"
        "6. Normalise capitalisation: common nouns and condition names that appear "
        "mid-sentence should be lowercase (e.g. 'emotional stress', 'brain fog', "
        "'chronic fatigue'). Preserve medical acronyms in uppercase: POTS, IBS, ECG, "
        "ECHO, EEG, MRI, CT, EP, SSRI, SNRI, ADHD, MCAS, GTN, OCP.\n"
        "7. Return only the cleaned report text — no preamble, no explanation."
    )

    def _normalise_output(text):
        lines = [line.rstrip() for line in text.splitlines()]
        return "\n".join(lines)

    # Prefer Claude Sonnet
    if anthropic_api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_api_key)
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2500,
                system=system_prompt,
                messages=[{"role": "user", "content": report_text}],
            )
            cleaned = message.content[0].text.strip()
            if cleaned:
                return _normalise_output(cleaned)
        except Exception as e:
            logger.warning("Claude LLM cleanup failed: %s — trying OpenAI fallback", e)

    # Fallback: OpenAI GPT-4o-mini
    if openai_api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)
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
            if cleaned:
                return _normalise_output(cleaned)
        except Exception as e:
            logger.warning("OpenAI LLM cleanup failed: %s — returning original report", e)

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

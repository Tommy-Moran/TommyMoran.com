"""
tilt_table_extractor.py
Server-side extraction of clinical data from REDCap tilt table test PDFs,
and generation of the HealthTrack bracket-notation report.

No external APIs used — all processing is local.

REDCap PDF format notes (from real PDF analysis):
- All checkbox/radio options are ALWAYS printed regardless of selection state.
  The PDF is flattened — no AcroForm fields, and all rects are fill=False.
  Multi-select checkbox values cannot be reliably determined from text alone,
  so those fields output [REVIEW] placeholders.
- Text fields (MRN, demographics, duration, frequency etc.) use consistent
  label text that we can match with targeted regexes.
- Tilt results are calculated from the BP/HR numeric table rather than
  trying to read the radio button selection.
"""

import re
import pdfplumber
import io
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _field(text, *patterns, label="field"):
    """
    Try each regex pattern in order; return first non-empty match group(1),
    or a [REVIEW: label] placeholder on failure.
    """
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if m:
            val = m.group(1).strip()
            if val and val.lower() not in ("", "n/a", "none", "unknown", "______"):
                return val
    return f"[REVIEW: {label}]"


def _review(label):
    return f"[REVIEW: {label}]"


def _review_list(label, options):
    """Return a review placeholder that includes the available options."""
    opts = " / ".join(options)
    return f"[REVIEW: {label} — options: {opts}]"


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

def extract_fields(text):
    """
    Parse REDCap PDF text into a structured dict of clinical fields.
    Any unconfident field is a [REVIEW: ...] string.
    """
    d = {}

    # ── Patient demographics ──────────────────────────────────

    # REDCap exports "Last Name Barclay" — no first name in the PDF.
    # HealthTrack substitutes <HMS-Patient_FirstName> itself; we leave it as-is.
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

    # ── Syncope duration ──────────────────────────────────────
    # REDCap label: "Symptom onset (how many w,m,y ago?)  5 Years  5 Years"
    # First value = syncope, second = presyncope
    onset_m = re.search(
        r"Symptom\s+onset\s+\([^)]+\)\s+(\d+(?:\.\d+)?)\s+(Years?|Months?|Weeks?|Days?)"
        r"(?:\s+(\d+(?:\.\d+)?)\s+(Years?|Months?|Weeks?|Days?))?",
        text, re.IGNORECASE
    )
    if onset_m:
        d["duration_number"] = onset_m.group(1)
        raw_unit = onset_m.group(2).lower()
        d["duration_unit"] = _normalise_unit(raw_unit)
        # Presyncope duration (second value)
        if onset_m.group(3):
            d["presyncope_duration_number"] = onset_m.group(3)
            d["presyncope_duration_unit"] = _normalise_unit(onset_m.group(4).lower())
    else:
        d["duration_number"] = _review("syncope_duration_number")
        d["duration_unit"] = _review("syncope_duration_unit")

    # ── Syncope & presyncope frequency ───────────────────────
    # REDCap label: "Frequency of events (how many per w/m/y?)  10 Month  7 Week"
    # First value = syncope frequency, second = presyncope
    freq_m = re.search(
        r"Frequency\s+of\s+events\s+\([^)]+\)\s+(\d+)\s+(Month|Week|Day|Year)"
        r"(?:\s+(\d+)\s+(Month|Week|Day|Year))?",
        text, re.IGNORECASE
    )
    if freq_m:
        d["frequency"] = _unit_to_frequency(freq_m.group(2))
        if freq_m.group(3):
            d["presyncope_frequency"] = _unit_to_frequency(freq_m.group(4))
        else:
            d["presyncope_frequency"] = d["frequency"]
    else:
        # Fallback: look for plain frequency words
        freq_raw = _field(
            text,
            r"Frequency[:\s]+(daily|weekly|monthly|infrequently|occasionally|rarely)",
            label="syncope_frequency"
        ).lower()
        freq_map = {
            "daily": "daily", "weekly": "weekly", "monthly": "monthly",
            "infrequently": "infrequently", "occasionally": "infrequently",
            "rarely": "infrequently"
        }
        d["frequency"] = freq_map.get(freq_raw, freq_raw)
        d["presyncope_frequency"] = d["frequency"]

    # ── Episode counts ────────────────────────────────────────
    # REDCap label: "Number of episodes in the last month?  10  30"
    # First number = syncope, second = presyncope
    ep_m = re.search(
        r"Number\s+of\s+episodes\s+in\s+the\s+last\s+month\??\s+(\d+)(?:\s+(\d+))?",
        text, re.IGNORECASE
    )
    if ep_m:
        d["episodes_last_month"] = ep_m.group(1)
    else:
        d["episodes_last_month"] = _review("episodes_last_month")

    # ── Most recent date ──────────────────────────────────────
    # REDCap label: "Date of most recent episode?  18/3/26" (value far right, same line)
    d["most_recent_date"] = _field(
        text,
        r"Date\s+of\s+most\s+recent\s+episode\??\s+([\d]{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
        r"Most\s+[Rr]ecent[:\s]+([\d/\-\.]+(?:\s+\d{4})?)",
        r"Last\s+[Ee]pisode[:\s]+([\d/\-\.]+)",
        label="most_recent_episode_date"
    )

    # ── Posture ───────────────────────────────────────────────
    # NOTE: All options always printed in REDCap PDF.
    # Use [REVIEW] since we can't detect selection from flattened PDF.
    d["posture"] = _review_list(
        "posture",
        ["standing posture", "supine posture", "both standing and supine postures"]
    )

    # ── Triggers ─────────────────────────────────────────────
    # Multi-select checkbox — cannot determine selection from flattened PDF.
    d["triggers"] = _review_list(
        "triggers",
        ["needle/blood test", "acute pain/injury", "emotional stress",
         "prolonged standing", "prolonged sitting", "hot environment",
         "exercise", "eating a meal", "upon waking", "alcohol consumption", "other: ___"]
    )

    # ── Associated symptoms ───────────────────────────────────
    d["symptoms"] = _review_list(
        "symptoms",
        ["nausea", "vomiting", "sweating", "visual changes", "hearing changes",
         "palpitations", "chest pain", "dyspnoea", "fatigue post event",
         "no associated symptoms"]
    )

    # ── Associated conditions ─────────────────────────────────
    d["conditions"] = _review_list(
        "conditions",
        ["autism spectrum disorder", "anxiety", "depression", "migraine",
         "brain fog", "chronic fatigue", "hypermobility",
         "postural orthostatic tachycardia syndrome", "no associated conditions"]
    )

    # ── Family history ────────────────────────────────────────
    # REDCap label: "Family history of hypotension/fainting/POTS? No"
    # or "Yes  [detail]".  In the flattened PDF, REDCap prints all options;
    # "No" appears first if it is selected, "Yes ___" if yes is selected.
    # We look for a filled detail after "Yes" to confirm a positive answer.
    fh_yes_m = re.search(
        r"Family\s+history\s+of\s+hypotension[^?\n]*\?[^\n]*Yes\s+([\w][\w\s,/\-]{2,}?)(?:\n|Family|\d{2}/)",
        text, re.IGNORECASE
    )
    if fh_yes_m:
        detail = fh_yes_m.group(1).strip()
        if detail and "_" not in detail:
            d["family_history"] = f"remarkable for {detail} with hypotension/fainting"
        else:
            # "Yes ______" means blank — treat as unremarkable
            d["family_history"] = "unremarkable"
    elif re.search(r"Family\s+history\s+of\s+hypotension[^?\n]*\?\s*No\b", text, re.IGNORECASE):
        d["family_history"] = "unremarkable"
    else:
        d["family_history"] = _review("family_history")

    # ── Prior investigations ──────────────────────────────────
    # Multi-select checkbox — use [REVIEW] since we can't detect selection.
    d["investigations"] = _review_list(
        "prior_investigations",
        ["normal 12-lead ECG", "normal TTE", "Holter monitor",
         "implantable loop recorder", "no prior investigations"]
    )

    # ── Tilt test drug ────────────────────────────────────────
    # REDCap label: "Type of test  Isuprenaline / GTN / Passive only"
    # NOTE: Isuprenaline is the spelling used in this REDCap instance.
    drug_raw = _field(
        text,
        r"Type\s+of\s+test\s+(Isuprenaline|Isoprenaline|GTN|Passive\s+only)",
        r"(?:Drug|Agent|Medication\s+used)[:\s]+(Isuprenaline|Isoprenaline|GTN|glyceryl|isoproterenol|Passive)",
        label="tilt_drug"
    )
    if re.search(r"isuprenaline|isoprenaline|isoproterenol", drug_raw, re.I):
        d["tilt_drug"] = "Isoprenaline"
    elif re.search(r"gtn|glyceryl", drug_raw, re.I):
        d["tilt_drug"] = "GTN"
    elif re.search(r"passive", drug_raw, re.I):
        d["tilt_drug"] = None  # No drug — passive tilt only
    else:
        d["tilt_drug"] = drug_raw  # [REVIEW]

    # ── BP/HR table extraction ────────────────────────────────
    d["baseline_hr"]  = _extract_numeric(text, r"Baseline\s+Heart\s+Rate\s+(\d+)")
    d["baseline_bp"]  = _field(text, r"Baseline\s+Blood\s+Pressure\s+(\d+/\d+)", label="baseline_BP")
    d["recovery_hr"]  = _extract_numeric(text, r"Recovery\s+Heart\s+Rate\s+(\d+)")
    d["recovery_bp"]  = _field(text, r"Recovery\s+Blood\s+Pressure\s+(\d+/\d+)", label="recovery_BP")

    d["control_readings"]  = _extract_phase_readings(text, "Control")
    d["phase2_readings"]   = _extract_phase_readings(text, "Phase 2")

    # ── Clinician symptom notes ───────────────────────────────
    # Clinician notes: lines like "Fighting to stay awake. No dizziness.  Control 10 minute 100 97"
    # Exclude "Any symptoms?" lines (the row header) and lines starting with "Phase".
    # REDCap sometimes overlaps the footer timestamp with the note on the last data page,
    # producing corrupted text — we still scan for clinical keywords in that garbled line.
    # Control notes: "Fighting to stay awake. No dizziness.  Control 10 minute 100 97"
    # Use [ \t]+ (not \s+) before "Control" so we don't cross line boundaries.
    ctrl_note_m = re.search(
        r"^(?!Any\s+symptoms)(?!Phase)([A-Z][^\n]{9,120}?)[ \t]+Control[ \t]+\d+[ \t]+minute\b",
        text, re.IGNORECASE | re.MULTILINE
    )
    d["control_notes"] = ctrl_note_m.group(1).strip() if ctrl_note_m else ""

    # Phase 2 note: appears on its own line between the "Any symptoms?" row and the next timepoint.
    # The footer timestamp often overlaps this line, producing corrupted text — capture anyway.
    p2_note_m = re.search(
        r"Any\s+symptoms\?[^\n]*\n([^\n]+?)[ \t]+Phase[ \t]+2[ \t]+10[ \t]+minute",
        text, re.IGNORECASE
    )
    d["phase2_notes"] = p2_note_m.group(1).strip() if p2_note_m else ""

    # ── Tilt results — calculated from numeric data ───────────
    d["control_result"]   = _calculate_control_result(d)
    d["control_tolerance"] = _infer_tolerance(text, "control", d)
    d["control_symptom_severity"] = _infer_severity(text, "control")

    d["phase2_result"]    = _calculate_phase2_result(d)
    d["phase2_tolerance"] = _infer_tolerance(text, "phase 2", d)

    return d


# ─────────────────────────────────────────────────────────────
# Unit normalisers
# ─────────────────────────────────────────────────────────────

def _normalise_unit(raw):
    """'years' / 'year' / 'Years' → 'years' etc."""
    r = raw.lower().rstrip("s") + "s"  # pluralise
    if r in ("years", "months", "weeks", "days"):
        return r
    return raw


def _unit_to_frequency(unit_str):
    """'Month' → 'monthly', 'Week' → 'weekly' etc."""
    mapping = {
        "month": "monthly", "week": "weekly",
        "day":   "daily",   "year": "yearly"
    }
    return mapping.get(unit_str.lower(), "infrequently")


# ─────────────────────────────────────────────────────────────
# BP / HR extraction
# ─────────────────────────────────────────────────────────────

def _extract_numeric(text, pattern):
    """Return int from first matching group, or None."""
    m = re.search(pattern, text, re.IGNORECASE)
    try:
        return int(m.group(1)) if m else None
    except (ValueError, AttributeError):
        return None


def _extract_phase_readings(text, phase_label):
    """
    Extract (systolic_bp, hr) tuples from the results table for a given phase.
    Returns list of (systolic: int, hr: int) or empty list.

    REDCap format:
      Control tilting   Control tilting  105  82
      Control 1 minute  100  98
      ...
      Phase 2 Phase 2 Baseline   90  122
      Phase 2 tilting   70  130
    """
    if phase_label.lower() == "control":
        block_pat = (
            r"Control\s+Tilting.*?"          # start at "Control Tilting"
            r"(?=Phase\s+2|Phase\s+Stage|$)" # end before Phase 2 or end of text
        )
    else:
        block_pat = (
            r"Phase\s+2\s+Phase\s+2\s+Baseline.*?"
            r"(?=Phase\s+Stage|Results\s+Conclusion|$)"
        )

    bm = re.search(block_pat, text, re.DOTALL | re.IGNORECASE)
    block = bm.group(0) if bm else ""

    # Each data row: "... NNN  NNN" where first is systolic, second HR
    # Rows may be: "Control 1 minute  100  98" or "Phase 2 tilting  70  130"
    readings = []
    for m in re.finditer(r"(\d{2,3})\s+(\d{2,3})\s*$", block, re.MULTILINE):
        sbp, hr = int(m.group(1)), int(m.group(2))
        # Sanity check (plausible vital signs)
        if 40 <= sbp <= 250 and 20 <= hr <= 250:
            readings.append((sbp, hr))

    return readings


# ─────────────────────────────────────────────────────────────
# Tilt result calculation from numeric data
# ─────────────────────────────────────────────────────────────

def _calculate_control_result(d):
    """
    Apply POTS / orthostatic intolerance / vasovagal / normal criteria
    to the control phase BP/HR readings.
    """
    readings = d.get("control_readings", [])
    baseline_hr = d.get("baseline_hr")
    age = _safe_int(d.get("age"))

    if not readings or baseline_hr is None:
        return _review("control_tilt_result")

    max_hr = max(hr for _, hr in readings)
    hr_rise = max_hr - baseline_hr

    # POTS criteria: sustained HR rise ≥30bpm (≥40bpm aged 12–19)
    pots_threshold = 40 if (age and 12 <= age <= 19) else 30
    if hr_rise >= pots_threshold:
        return (
            "positive for a POTS response with an increase in heart rate of "
            ">30bpm (or >40bpm in those aged 12-19)"
        )

    # Orthostatic intolerance: sustained HR rise ≥20bpm without meeting POTS
    if hr_rise >= 20:
        return (
            "positive for orthostatic intolerance with a sustained increase "
            "in HR without meeting POTS criteria"
        )

    # Vasovagal in control: systolic BP drop >20mmHg from baseline
    baseline_sbp = _extract_systolic(d.get("baseline_bp"))
    if baseline_sbp:
        min_sbp = min(sbp for sbp, _ in readings)
        sbp_drop = baseline_sbp - min_sbp
        min_hr = min(hr for _, hr in readings)
        if sbp_drop > 20 or min_hr < 50:
            return (
                "positive for a vasovagal response with a drop in systolic "
                "BP >20mmHg and/or HR <50bpm"
            )

    return "normal"


def _calculate_phase2_result(d):
    """
    Apply criteria to phase 2 readings.
    Phase 2 baseline BP is the reference point.
    """
    readings = d.get("phase2_readings", [])
    if not readings:
        return _review("phase2_tilt_result")

    baseline_sbp = readings[0][0] if readings else None  # First reading = phase 2 baseline
    baseline_hr  = readings[0][1] if readings else None
    age = _safe_int(d.get("age"))

    if len(readings) < 2:
        return _review("phase2_tilt_result")

    subsequent = readings[1:]
    max_hr  = max(hr for _, hr in subsequent)
    min_sbp = min(sbp for sbp, _ in subsequent)
    min_hr  = min(hr for _, hr in subsequent)
    hr_rise = max_hr - baseline_hr if baseline_hr else 0
    sbp_drop = baseline_sbp - min_sbp if baseline_sbp else 0

    # Vasovagal: BP drop >20mmHg and/or HR <50bpm
    if sbp_drop > 20 or min_hr < 50:
        return (
            "positive for a vasovagal response with a drop in systolic "
            "BP >20mmHg and/or HR <50bpm"
        )

    # POTS
    pots_threshold = 40 if (age and 12 <= age <= 19) else 30
    if hr_rise >= pots_threshold:
        return (
            "positive for a POTS response with an increase in heart rate of "
            ">30bpm (or >40bpm in those aged 12-19)"
        )

    # Orthostatic intolerance
    if hr_rise >= 20:
        return (
            "positive for orthostatic intolerance with a sustained increase "
            "in HR without meeting POTS criteria"
        )

    return "normal"


def _infer_tolerance(text, phase, d):
    """Infer patient experience from clinician notes and numeric data."""
    if phase == "control":
        notes = d.get("control_notes", "")
        section_pat = r"Any\s+symptoms\?(.{0,200}?)(?:Phase\s+2|Phase\s+Stage|$)"
    else:
        notes = d.get("phase2_notes", "")
        section_pat = r"Any\s+symptoms\?(.{0,400}?)(?:Results\s+Conclusion|$)"

    sm = re.search(section_pat, text, re.DOTALL | re.IGNORECASE)
    section = (sm.group(1) if sm else "") + " " + (notes or "")

    # Check clinician notes for explicit denial of syncope first
    no_loc = bool(re.search(r"\bno\s+loc\b|\bno\s+loss\s+of\s+consciousness\b|\bdid\s+not\s+(?:lose|faint)\b", section, re.I))

    syncope_words = r"\b(?:synco(?:pe|ped)|lost\s+consciousness|(?<!no\s)loc\b)\b"
    presync_words = r"\b(?:presyncope|pre-syncope|near.syncope|very\s+pale|pale|dizz|light.?head|near\s+faint|almost\s+faint)\b"

    had_syncope = bool(re.search(syncope_words, section, re.I)) and not no_loc
    had_presync = bool(re.search(presync_words, section, re.I))

    # For phase 2, also infer from BP/HR data
    if phase == "phase 2":
        readings = d.get("phase2_readings", [])
        if len(readings) >= 2:
            subsequent = readings[1:]
            min_sbp = min(sbp for sbp, _ in subsequent)
            min_hr  = min(hr for _, hr in subsequent)
            # If no_loc confirmed, significant BP drop still implies presyncope
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
    """Infer symptom severity from clinician notes."""
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
    if re.search(r"\bno\s+(?:symptom|complaint|dizzin)\b|\bwell\b|\basymptomatic\b", section, re.I):
        return "no"
    return "mild"  # default if notes present but severity not specified


# ─────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────

def _extract_systolic(bp_str):
    """'95/50' → 95"""
    if not bp_str:
        return None
    m = re.match(r"(\d+)/", str(bp_str))
    return int(m.group(1)) if m else None


def _safe_int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────
# HealthTrack report template builder
# ─────────────────────────────────────────────────────────────

def _join_and(items):
    items = [str(i) for i in items]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def build_report(fields):
    """
    Populate the HealthTrack template from extracted fields.
    Returns (report_text: str, review_count: int).
    """
    lines = []
    review_count = 0

    def add(label, text):
        lines.append(f"[{label.upper()}]\n{text}\n")

    def tally(text):
        nonlocal review_count
        review_count += len(re.findall(r"\[REVIEW:", text))
        return text

    fn = fields.get("first_name", "<HMS-Patient_FirstName>")

    # ── Summary ───────────────────────────────────────────────
    dur_num  = fields.get("duration_number",  _review("duration_number"))
    dur_unit = fields.get("duration_unit",    _review("duration_unit"))
    freq     = fields.get("frequency",        _review("syncope_frequency"))
    episodes = fields.get("episodes_last_month", _review("episodes_last_month"))
    recent   = fields.get("most_recent_date", _review("most_recent_date"))
    pre_freq = fields.get("presyncope_frequency", _review("presyncope_frequency"))

    summary = tally(
        f"Syncope symptoms for {dur_num} {dur_unit}, occurring {freq}. "
        f"Presyncope symptoms occurring {pre_freq}. "
        f"{episodes} episodes in the last month, most recently {recent}."
    )
    add("Summary", summary)

    # ── Posture ───────────────────────────────────────────────
    add("Posture", tally(
        f"Symptoms typically occur in the {fields.get('posture', _review('posture'))}."
    ))

    # ── Triggers ─────────────────────────────────────────────
    add("Triggers", tally(fields.get("triggers", _review("triggers"))))

    # ── Associated features ───────────────────────────────────
    add("Associated Features", tally(fields.get("symptoms", _review("symptoms"))))

    # ── Associated conditions ─────────────────────────────────
    add("Associated Conditions", tally(fields.get("conditions", _review("conditions"))))

    # ── Family history ────────────────────────────────────────
    fh = fields.get("family_history", _review("family_history"))
    add("Family History", tally(f"Family history {fh}."))

    # ── Investigations ────────────────────────────────────────
    add("Investigations", tally(
        f"Prior investigations: {fields.get('investigations', _review('prior_investigations'))}."
    ))

    # ── Baseline vital signs ──────────────────────────────────
    baseline_hr = fields.get("baseline_hr")
    baseline_bp = fields.get("baseline_bp", _review("baseline_BP"))
    recovery_hr = fields.get("recovery_hr")
    recovery_bp = fields.get("recovery_bp", _review("recovery_BP"))
    vitals_text = (
        f"Baseline BP {baseline_bp}, HR {baseline_hr if baseline_hr else _review('baseline_HR')} bpm. "
        f"Recovery BP {recovery_bp}, HR {recovery_hr if recovery_hr else _review('recovery_HR')} bpm."
    )
    add("Baseline Vital Signs", tally(vitals_text))

    # ── Control phase result ──────────────────────────────────
    ctrl_result   = fields.get("control_result",   _review("control_tilt_result"))
    ctrl_tol      = fields.get("control_tolerance", _review("control_tolerance"))
    ctrl_severity = fields.get("control_symptom_severity", "mild")
    ctrl_notes    = fields.get("control_notes", "")

    ctrl_text = tally(
        f"The tilt table test demonstrated {ctrl_result} during the control phase. "
        f"{fn} {ctrl_tol} with {ctrl_severity} symptoms."
    )
    if ctrl_notes and not ctrl_notes.startswith("[REVIEW"):
        ctrl_text += f" Clinician notes: {ctrl_notes}"
    add("Baseline Tilt Results (Control Phase)", ctrl_text)

    # ── Phase 2 result ────────────────────────────────────────
    drug      = fields.get("tilt_drug", _review("tilt_drug"))
    p2_result = fields.get("phase2_result",   _review("phase2_tilt_result"))
    p2_tol    = fields.get("phase2_tolerance", _review("phase2_tolerance"))
    p2_notes  = fields.get("phase2_notes", "")

    if drug is None:
        # Passive tilt only
        p2_text = tally(
            f"No pharmacological provocation was administered (passive tilt only). "
            f"{fn} {p2_tol}."
        )
    else:
        p2_text = tally(
            f"Following administration of {drug}, {p2_result} was observed. "
            f"{fn} {p2_tol}."
        )
    if p2_notes and not p2_notes.startswith("[REVIEW"):
        p2_text += f" Clinician notes: {p2_notes}"
    add("Phase 2 Tilt Results", p2_text)

    # ── Conclusions ───────────────────────────────────────────
    conclusion = _generate_conclusion(
        ctrl_result, p2_result, fields.get("tilt_drug")
    )
    add("Conclusions", tally(conclusion))

    # ── Recommendations ───────────────────────────────────────
    add("Recommendations", "[RECOMMENDATIONS — to be completed by clinician]")

    full_report = "\n".join(lines)
    return full_report, review_count


_RESULT_POTS  = "positive for a POTS response"
_RESULT_VVS   = "positive for a vasovagal response"
_RESULT_OI    = "positive for orthostatic intolerance"
_RESULT_NORMAL = "normal"


def _generate_conclusion(ctrl, p2, drug):
    ctrl_normal = ctrl == _RESULT_NORMAL
    p2_normal   = p2 == _RESULT_NORMAL or drug is None

    if ctrl_normal and p2_normal:
        return (
            "The tilt table test was negative, with no evidence of orthostatic intolerance, "
            "POTS, or vasovagal syncope provoked during either the control or pharmacological "
            "phase. These findings do not exclude a clinical diagnosis of syncope."
        )

    # POTS in either phase
    has_pots = ctrl.startswith(_RESULT_POTS) or p2.startswith(_RESULT_POTS)
    if has_pots:
        phase = "control" if ctrl.startswith(_RESULT_POTS) else "pharmacological"
        return (
            f"The tilt table test demonstrated a positive POTS response during the {phase} phase. "
            "This is consistent with postural orthostatic tachycardia syndrome and warrants "
            "further evaluation and management."
        )

    # Vasovagal in either phase
    has_vvs = ctrl.startswith(_RESULT_VVS) or p2.startswith(_RESULT_VVS)
    if has_vvs:
        phase = "control" if ctrl.startswith(_RESULT_VVS) else "pharmacological"
        return (
            f"The tilt table test demonstrated a positive vasovagal response during the {phase} phase. "
            "This is consistent with neurally-mediated syncope."
        )

    # Orthostatic intolerance
    has_oi = ctrl.startswith(_RESULT_OI) or p2.startswith(_RESULT_OI)
    if has_oi:
        return (
            "The tilt table test demonstrated orthostatic intolerance without meeting full "
            "POTS criteria. Clinical correlation and further evaluation are recommended."
        )

    return _review("clinical_conclusion")


# ─────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────

def process_pdf(pdf_bytes):
    """
    Main entry point. Takes raw PDF bytes, returns (report_text, review_count).
    """
    try:
        text = extract_text_from_pdf(pdf_bytes)
        logger.debug("Extracted %d characters from PDF", len(text))
    except Exception as e:
        logger.error("PDF extraction failed: %s", e)
        raise ValueError(f"Could not read PDF: {e}")

    fields = extract_fields(text)
    report, review_count = build_report(fields)
    return report, review_count

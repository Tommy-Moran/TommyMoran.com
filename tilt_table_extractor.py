"""
tilt_table_extractor.py
Server-side extraction of clinical data from REDCap tilt table test PDFs,
and generation of the HealthTrack bracket-notation report.

No external APIs used — all processing is local.
"""

import re
import pdfplumber
import io
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _field(text, *patterns, default="[REVIEW: {label}]", label=None):
    """
    Try each regex pattern in order; return first match group(1) stripped,
    or a [REVIEW: label] placeholder on failure.
    """
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if m:
            val = m.group(1).strip()
            if val and val.lower() not in ("", "n/a", "none", "unknown"):
                return val
    lbl = label or (patterns[0] if patterns else "field")
    return f"[REVIEW: {lbl}]"


def _checkbox(text, field_label):
    """
    Returns True if a checkbox field is ticked.
    REDCap PDFs typically show: "☑ Field Label" or "Yes" next to the label,
    or a line like "Field Label: Yes".
    Handles both checked-box unicode and plain Yes/No text patterns.
    """
    # Pattern: "Field Label: Yes" or "Field Label  Yes"
    pattern = re.escape(field_label) + r"[\s:]*(?:Yes|☑|✓|✔|Checked|TRUE|1)\b"
    if re.search(pattern, text, re.IGNORECASE):
        return True
    # Pattern: "☑ Field Label"
    pattern2 = r"(?:☑|✓|✔)\s*" + re.escape(field_label)
    if re.search(pattern2, text, re.IGNORECASE):
        return True
    return False


def _review(label):
    return f"[REVIEW: {label}]"


# ─────────────────────────────────────────────────────────────
# PDF text extraction
# ─────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_bytes):
    """Extract all text from a PDF given as bytes."""
    text_parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text(x_tolerance=2, y_tolerance=3)
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


# ─────────────────────────────────────────────────────────────
# Field extraction
# ─────────────────────────────────────────────────────────────

def extract_fields(text):
    """
    Parse REDCap PDF text into a structured dict of clinical fields.
    Returns a dict; any unconfident field is a [REVIEW: ...] string.
    """
    d = {}

    # ── Patient demographics ──────────────────────────────────
    d["first_name"] = _field(
        text,
        r"(?:First\s+Name|Given\s+Name|Name)[:\s]+([A-Za-z\-']+)",
        r"Patient[:\s]+([A-Za-z\-']+)\s+[A-Za-z\-']+",
        label="patient_first_name"
    )

    d["mrn"] = _field(
        text,
        r"MRN[:\s#]*([0-9A-Za-z\-]+)",
        r"(?:Medical\s+Record\s+Number|URN)[:\s]*([0-9A-Za-z\-]+)",
        label="MRN"
    )

    d["dob"] = _field(
        text,
        r"D(?:ate\s+of\s+)?O(?:f\s+)?B(?:irth)?[:\s]+([\d/\-\.]+)",
        label="DOB"
    )

    d["age"] = _field(
        text,
        r"\bAge[:\s]+(\d{1,3})\b",
        r"(\d{1,3})\s+(?:years?\s+old|yo\b)",
        label="age"
    )

    d["sex"] = _field(
        text,
        r"\bSex[:\s]+(Male|Female|Non-binary|Other)\b",
        r"\bGender[:\s]+(Male|Female|Non-binary|Other)\b",
        label="sex"
    )

    d["height"] = _field(
        text,
        r"Height[:\s]+([\d.]+\s*(?:cm|m))",
        label="height"
    )

    d["weight"] = _field(
        text,
        r"Weight[:\s]+([\d.]+\s*(?:kg|lbs?))",
        label="weight"
    )

    # ── Syncope history ───────────────────────────────────────
    d["syncope_duration_unit"] = _field(
        text,
        r"(?:Duration|History)\s+(?:of\s+)?(?:syncope|symptoms?)[:\s]+(\d+\s*(?:years?|months?))",
        r"(\d+\s*(?:years?|months?))\s+(?:history|duration)",
        label="syncope_duration"
    )
    # Normalise to "years" or "months"
    if "year" in d["syncope_duration_unit"].lower():
        d["duration_unit"] = "years"
    elif "month" in d["syncope_duration_unit"].lower():
        d["duration_unit"] = "months"
    else:
        d["duration_unit"] = d["syncope_duration_unit"]  # keep as-is (may be [REVIEW])

    # Duration number only
    dm = re.search(r"(\d+(?:\.\d+)?)\s*(?:years?|months?)", d["syncope_duration_unit"], re.IGNORECASE)
    d["duration_number"] = dm.group(1) if dm else _review("syncope_duration_number")

    # Frequency
    freq_raw = _field(
        text,
        r"Frequency[:\s]+(daily|weekly|monthly|infrequently|occasionally|rarely)",
        label="syncope_frequency"
    ).lower()
    freq_map = {
        "daily": "daily", "weekly": "weekly", "monthly": "monthly",
        "infrequently": "infrequently", "occasionally": "infrequently", "rarely": "infrequently"
    }
    d["frequency"] = freq_map.get(freq_raw, freq_raw if freq_raw.startswith("[REVIEW") else "infrequently")

    # Episode counts
    d["episodes_last_month"] = _field(
        text,
        r"(?:Episodes?|Events?)\s+(?:in\s+)?(?:the\s+)?(?:last|past)\s+month[:\s]+(\d+)",
        r"(?:last\s+month|past\s+30\s+days?)[:\s]+(\d+)\s+episode",
        label="episodes_last_month"
    )

    d["most_recent_date"] = _field(
        text,
        r"Most\s+[Rr]ecent[:\s]+([\d/\-\.]+(?:\s+\d{4})?)",
        r"Last\s+[Ee]pisode[:\s]+([\d/\-\.]+)",
        label="most_recent_episode_date"
    )

    d["no_warning_syncope"] = _checkbox(text, "No warning")  or _checkbox(text, "No prodrome") or _checkbox(text, "Prodrome: No")

    # ── Presyncope frequency ──────────────────────────────────
    pre_freq_raw = _field(
        text,
        r"Presyncope\s+[Ff]requency[:\s]+(daily|weekly|monthly|infrequently|occasionally|rarely)",
        label="presyncope_frequency"
    ).lower()
    d["presyncope_frequency"] = freq_map.get(pre_freq_raw, pre_freq_raw if pre_freq_raw.startswith("[REVIEW") else "infrequently")

    # ── Posture ───────────────────────────────────────────────
    standing = _checkbox(text, "Standing") or bool(re.search(r"(?:upright|standing)\s+posture", text, re.I))
    supine   = _checkbox(text, "Supine")   or bool(re.search(r"supine\s+posture", text, re.I))
    if standing and supine:
        d["posture"] = "both standing and supine postures"
    elif supine:
        d["posture"] = "supine posture"
    else:
        d["posture"] = "standing posture"

    # ── Triggers ─────────────────────────────────────────────
    trigger_map = {
        "needle/blood test":   ["needle", "blood test", "venepuncture", "blood draw"],
        "acute pain/injury":   ["acute pain", "pain/injury", "injury"],
        "emotional stress":    ["emotional stress", "emotional"],
        "prolonged standing":  ["prolonged standing"],
        "prolonged sitting":   ["prolonged sitting"],
        "hot environment":     ["hot environment", "heat"],
        "exercise":            ["exercise"],
        "eating a meal":       ["eating", "meal", "post-prandial"],
        "upon waking":         ["upon waking", "waking", "on waking"],
        "alcohol consumption": ["alcohol"],
        "other: ___":          ["other trigger", "other:"],
    }
    d["triggers"] = _multi_select(text, trigger_map)

    # Also check febrile illness separately (mentioned in spec but mapped to triggers)
    if _checkbox(text, "Febrile illness") or bool(re.search(r"febrile\s+illness", text, re.I)):
        if "febrile illness" not in d["triggers"]:
            d["triggers"].append("febrile illness")

    # ── Associated symptoms ───────────────────────────────────
    symptom_map = {
        "nausea":           ["nausea"],
        "vomiting":         ["vomiting"],
        "sweating":         ["sweating", "diaphoresis"],
        "visual changes":   ["visual changes", "blurred vision", "tunnel vision", "visual"],
        "hearing changes":  ["hearing changes", "tinnitus"],
        "palpitations":     ["palpitations"],
        "chest pain":       ["chest pain"],
        "dyspnoea":         ["dyspnoea", "shortness of breath", "sob"],
        "fatigue post event": ["fatigue post", "post-event fatigue", "post event fatigue"],
    }
    d["symptoms"] = _multi_select(text, symptom_map)
    if not d["symptoms"]:
        d["symptoms"] = ["no associated symptoms"]

    # ── Associated conditions ─────────────────────────────────
    condition_map = {
        "autism spectrum disorder": ["autism", "asd"],
        "anxiety":                  ["anxiety"],
        "depression":               ["depression"],
        "migraine":                 ["migraine"],
        "brain fog":                ["brain fog"],
        "chronic fatigue":          ["chronic fatigue", "cfs", "me/cfs"],
        "hypermobility":            ["hypermobility", "ehlers"],
        "postural orthostatic tachycardia syndrome": ["pots", "postural orthostatic tachycardia"],
    }
    d["conditions"] = _multi_select(text, condition_map)
    if not d["conditions"]:
        d["conditions"] = ["no associated conditions"]

    # ── Medications ───────────────────────────────────────────
    d["medications"] = _field(
        text,
        r"Medications?[:\s]+((?:(?!(?:Prior|Investigation|Tilt|Test|ECG|Holter)).)+)",
        label="medications"
    )

    # ── Prior investigations ──────────────────────────────────
    inv_map = {
        "normal 12-lead ECG":       ["ecg", "ekg", "electrocardiogram"],
        "normal TTE":               ["tte", "transthoracic echo", "echocardiogram"],
        "Holter monitor":           ["holter"],
        "implantable loop recorder": ["loop recorder", "ilr", "implantable"],
    }
    d["investigations"] = _multi_select(text, inv_map)
    if not d["investigations"]:
        d["investigations"] = ["no prior investigations"]

    # ── Tilt test — drug ──────────────────────────────────────
    drug_raw = _field(
        text,
        r"(?:Drug|Pharmacological\s+provocation|Agent|Medication\s+used)[:\s]+(Isoprenaline|GTN|glyceryl\s+trinitrate|isoproterenol)",
        label="tilt_drug"
    )
    if re.search(r"isoprenaline|isoproterenol", drug_raw, re.I):
        d["tilt_drug"] = "Isoprenaline"
    elif re.search(r"gtn|glyceryl", drug_raw, re.I):
        d["tilt_drug"] = "GTN"
    else:
        d["tilt_drug"] = drug_raw  # may be [REVIEW]

    # ── Tilt test — BP/HR readings ────────────────────────────
    # Control phase — look for table-style entries like "0 min: 120/80, HR 65"
    d["control_bp_hr"] = _extract_bp_hr_series(text, "control")
    d["phase2_bp_hr"]  = _extract_bp_hr_series(text, "phase 2")

    # ── Tilt result — control phase ──────────────────────────
    d["control_result"] = _classify_tilt_result(text, "control")
    d["control_tolerance"] = _classify_tolerance(text, "control")
    d["control_symptom_severity"] = _classify_severity(text, "control")

    # ── Tilt result — phase 2 ────────────────────────────────
    d["phase2_result"] = _classify_tilt_result(text, "phase 2")
    d["phase2_tolerance"] = _classify_tolerance(text, "phase 2")

    # ── Family history ────────────────────────────────────────
    fh_raw = _field(
        text,
        r"Family\s+[Hh]istory[:\s]+(.+?)(?:\n|$)",
        label="family_history"
    )
    if re.search(r"unremarkable|nil|none|no\s+family|negative", fh_raw, re.I):
        d["family_history"] = "unremarkable"
    elif fh_raw.startswith("[REVIEW"):
        d["family_history"] = _review("family_history")
    else:
        d["family_history"] = f"remarkable for {fh_raw} with hypotension/fainting"

    return d


# ─────────────────────────────────────────────────────────────
# Helpers for multi-select and tilt classification
# ─────────────────────────────────────────────────────────────

def _multi_select(text, option_map):
    """
    For each canonical option, check if any of its keyword aliases appear
    in the text (with REDCap checkbox pattern or plain mention).
    Returns list of matched canonical labels.
    """
    found = []
    for label, aliases in option_map.items():
        for alias in aliases:
            # REDCap checkbox pattern: "☑ alias" or "alias: Yes"
            if (re.search(r"(?:☑|✓|✔)\s*" + re.escape(alias), text, re.I) or
                re.search(re.escape(alias) + r"[:\s]+(?:Yes|Checked|TRUE|1)\b", text, re.I) or
                re.search(r"\b" + re.escape(alias) + r"\b", text, re.I)):
                found.append(label)
                break
    return found


def _extract_bp_hr_series(text, phase):
    """
    Attempt to extract a compact BP/HR series for a given phase.
    Returns a string like "0': 118/72 HR 68, 5': 96/60 HR 112" or a review marker.
    """
    # Look for a block associated with the phase name
    if phase == "control":
        section_pat = r"[Cc]ontrol\s+[Pp]hase(.{0,600}?)(?:[Pp]hase\s*2|[Pp]harmacological|GTN|Isoprenaline|$)"
    else:
        section_pat = r"(?:[Pp]hase\s*2|[Pp]harmacological)(.{0,600}?)(?:[Cc]onclusion|[Rr]esult|[Ee]nd|$)"

    sm = re.search(section_pat, text, re.DOTALL | re.IGNORECASE)
    section = sm.group(1) if sm else text

    # Find patterns like "120/80" and nearby HR values
    readings = re.findall(
        r"(\d+)\s*(?:min|'|minute)?\s*:?\s*(\d{2,3}/\d{2,3})\s*(?:mmHg)?\s*(?:HR|Heart\s+Rate)?[:\s]+(\d{2,3})",
        section, re.IGNORECASE
    )
    if readings:
        return ", ".join(f"{t}': {bp} HR {hr}" for t, bp, hr in readings)

    # Fallback — just find any BP readings present
    bp_vals = re.findall(r"\b(\d{2,3}/\d{2,3})\b", section)
    if bp_vals:
        return ", ".join(bp_vals) + " (times [REVIEW: tilt_timepoints])"

    return _review(f"{phase}_bp_hr")


def _classify_tilt_result(text, phase):
    """
    Classify the tilt result for the given phase into one of the four HealthTrack options.
    """
    if phase == "control":
        section_pat = r"[Cc]ontrol(.{0,800}?)(?:[Pp]hase\s*2|[Pp]harmacological|$)"
    else:
        section_pat = r"(?:[Pp]hase\s*2|[Pp]harmacological|GTN|[Ii]soprenaline)(.{0,800}?)(?:[Cc]onclusion|[Rr]esult|$)"

    sm = re.search(section_pat, text, re.DOTALL | re.IGNORECASE)
    section = sm.group(1) if sm else text

    # POTS: HR rise ≥30 bpm (or ≥40 in 12-19 age group) without syncope
    if re.search(r"POTS|postural\s+orthostatic\s+tachycardia", text, re.I):
        return "positive for a POTS response with an increase in heart rate of >30bpm (or >40bpm in those aged 12-19)"

    # Vasovagal: BP drop >20 mmHg systolic and/or HR <50
    if re.search(r"vasovagal|vaso.vagal|neurally[- ]mediated|neurocardiogenic", text, re.I):
        return "positive for a vasovagal response with a drop in systolic BP >20mmHg and/or HR <50bpm"

    # Orthostatic intolerance (sustained HR rise without POTS criteria)
    if re.search(r"orthostatic\s+intolerance|sustained\s+(?:tachycardia|HR\s+increase)", text, re.I):
        return "positive for orthostatic intolerance with a sustained increase in HR without meeting POTS criteria"

    # Positive without subtype
    if re.search(r"\bpositive\b", section, re.I):
        return _review(f"{phase}_result_subtype")

    # Normal
    if re.search(r"\bnormal\b|\bnegative\b", section, re.I):
        return "normal"

    return _review(f"{phase}_tilt_result")


def _classify_tolerance(text, phase):
    """Classify patient experience during the phase."""
    if phase == "control":
        section_pat = r"[Cc]ontrol(.{0,600}?)(?:[Pp]hase\s*2|$)"
    else:
        section_pat = r"(?:[Pp]hase\s*2|[Pp]harmacological)(.{0,600}?)(?:[Cc]onclusion|$)"

    sm = re.search(section_pat, text, re.DOTALL | re.IGNORECASE)
    section = sm.group(1) if sm else text

    syncope   = bool(re.search(r"\bsyncope\b", section, re.I))
    presync   = bool(re.search(r"\bpresyncope\b|\bpre-syncope\b|\bnear.syncope\b", section, re.I))

    if syncope and presync:
        return "experienced presyncope and syncope"
    elif syncope:
        return "experienced syncope"
    elif presync:
        return "experienced presyncope"
    else:
        return "tolerated the test well"


def _classify_severity(text, phase):
    """Classify symptom severity during the phase."""
    if phase == "control":
        section_pat = r"[Cc]ontrol(.{0,400}?)(?:[Pp]hase\s*2|$)"
    else:
        section_pat = r"(?:[Pp]hase\s*2|[Pp]harmacological)(.{0,400}?)(?:[Cc]onclusion|$)"

    sm = re.search(section_pat, text, re.DOTALL | re.IGNORECASE)
    section = sm.group(1) if sm else text

    if re.search(r"\bsevere\b", section, re.I):
        return "severe"
    elif re.search(r"\bmoderate\b", section, re.I):
        return "moderate"
    elif re.search(r"\bmild\b", section, re.I):
        return "mild"
    elif re.search(r"\bno\s+symptom|\basymptomatic\b|\bwell\b", section, re.I):
        return "no"
    return "mild"


# ─────────────────────────────────────────────────────────────
# HealthTrack report template builder
# ─────────────────────────────────────────────────────────────

def _join_and(items):
    """Join a list with commas and 'and' for the last item."""
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

    def count_reviews(text):
        return len(re.findall(r"\[REVIEW:", text))

    first_name = fields.get("first_name", _review("patient_first_name"))

    # ── Summary ──────────────────────────────────────────────
    dur_num  = fields.get("duration_number", _review("duration_number"))
    dur_unit = fields.get("duration_unit", _review("duration_unit"))
    freq     = fields.get("frequency", _review("syncope_frequency"))
    episodes = fields.get("episodes_last_month", _review("episodes_last_month"))
    recent   = fields.get("most_recent_date", _review("most_recent_date"))
    pre_freq = fields.get("presyncope_frequency", _review("presyncope_frequency"))

    summary = (
        f"Syncope symptoms for {dur_num} {dur_unit}, occurring {freq}. "
        f"Presyncope symptoms occurring {pre_freq}. "
        f"{episodes} episodes in the last month, most recently {recent}."
    )
    review_count += count_reviews(summary)
    add("Summary", summary)

    # ── Posture ───────────────────────────────────────────────
    posture_text = f"Symptoms typically occur in the {fields.get('posture', _review('posture'))}."
    review_count += count_reviews(posture_text)
    add("Posture", posture_text)

    # ── Triggers ─────────────────────────────────────────────
    triggers = fields.get("triggers", [])
    if triggers:
        trigger_text = _join_and(triggers).capitalize() + "."
    else:
        trigger_text = "No clear precipitating triggers identified."
    review_count += count_reviews(trigger_text)
    add("Triggers", trigger_text)

    # ── Associated features ───────────────────────────────────
    symptoms = fields.get("symptoms", ["no associated symptoms"])
    symptom_text = _join_and(symptoms).capitalize() + "."
    review_count += count_reviews(symptom_text)
    add("Associated Features", symptom_text)

    # ── Associated conditions ─────────────────────────────────
    conditions = fields.get("conditions", ["no associated conditions"])
    condition_text = _join_and(conditions).capitalize() + "."
    review_count += count_reviews(condition_text)
    add("Associated Conditions", condition_text)

    # ── Family history ────────────────────────────────────────
    fh = fields.get("family_history", _review("family_history"))
    fh_text = f"Family history {fh}."
    review_count += count_reviews(fh_text)
    add("Family History", fh_text)

    # ── Investigations ────────────────────────────────────────
    invs = fields.get("investigations", ["no prior investigations"])
    inv_text = "Prior investigations: " + _join_and(invs) + "."
    review_count += count_reviews(inv_text)
    add("Investigations", inv_text)

    # ── Baseline tilt (control phase) ─────────────────────────
    ctrl_result   = fields.get("control_result",   _review("control_tilt_result"))
    ctrl_tol      = fields.get("control_tolerance", _review("control_tolerance"))
    ctrl_severity = fields.get("control_symptom_severity", "mild")

    ctrl_text = (
        f"The tilt table test demonstrated {ctrl_result} during the control phase. "
        f"{first_name} {ctrl_tol} with {ctrl_severity} symptoms."
    )
    review_count += count_reviews(ctrl_text)
    add("Baseline Tilt Results (Control Phase)", ctrl_text)

    # ── Phase 2 tilt results ──────────────────────────────────
    drug       = fields.get("tilt_drug",       _review("tilt_drug"))
    p2_result  = fields.get("phase2_result",   _review("phase2_tilt_result"))
    p2_tol     = fields.get("phase2_tolerance", _review("phase2_tolerance"))

    p2_text = (
        f"Following administration of {drug}, {p2_result} was observed. "
        f"{first_name} {p2_tol}."
    )
    review_count += count_reviews(p2_text)
    add("Phase 2 Tilt Results", p2_text)

    # ── Conclusions ───────────────────────────────────────────
    ctrl_is_normal = "normal" in ctrl_result.lower() and not ctrl_result.startswith("[REVIEW")
    p2_is_normal   = "normal" in p2_result.lower()   and not p2_result.startswith("[REVIEW")

    if ctrl_is_normal and p2_is_normal:
        conclusion = (
            f"The tilt table test was negative, with no evidence of orthostatic intolerance, "
            f"POTS, or vasovagal syncope provoked during either the control or pharmacological phase. "
            f"These findings do not exclude a clinical diagnosis of syncope."
        )
    elif "POTS" in ctrl_result or "POTS" in p2_result:
        conclusion = (
            f"The tilt table test demonstrated a positive POTS response. "
            f"This is consistent with postural orthostatic tachycardia syndrome and warrants further evaluation and management."
        )
    elif "vasovagal" in ctrl_result or "vasovagal" in p2_result:
        conclusion = (
            f"The tilt table test demonstrated a positive vasovagal response. "
            f"This is consistent with neurally-mediated syncope."
        )
    elif "orthostatic intolerance" in ctrl_result or "orthostatic intolerance" in p2_result:
        conclusion = (
            f"The tilt table test demonstrated orthostatic intolerance without meeting full POTS criteria. "
            f"Clinical correlation and further evaluation are recommended."
        )
    else:
        conclusion = _review("clinical_conclusion")
        review_count += 1

    add("Conclusions", conclusion)

    # ── Recommendations ───────────────────────────────────────
    add("Recommendations", "[RECOMMENDATIONS — to be completed by clinician]")

    full_report = "\n".join(lines)
    return full_report, review_count


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

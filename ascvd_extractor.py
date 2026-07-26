"""
ascvd_extractor.py
Server-side extraction of ASCVD risk-calculator inputs from a GP referral
letter PDF (unstructured free text, unlike the REDCap tilt table forms).

No external APIs used — all processing is local via pdfplumber.

Every extracted field is "best effort": referral letters vary hugely in
layout and wording, so each field is returned alongside a `found` flag.
The frontend always shows extracted values as editable and flags any
field that could not be confidently determined for manual entry — nothing
here is treated as authoritative.
"""

import re
import io
import logging
from datetime import datetime

import pdfplumber

logger = logging.getLogger(__name__)


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
# Reference data
# ─────────────────────────────────────────────────────────────

_ANTIHYPERTENSIVES = [
    "amlodipine", "perindopril", "ramipril", "irbesartan", "candesartan",
    "telmisartan", "losartan", "valsartan", "olmesartan", "indapamide",
    "hydrochlorothiazide", "chlorthalidone", "metoprolol", "atenolol",
    "bisoprolol", "carvedilol", "spironolactone", "eplerenone", "prazosin",
    "hydralazine", "doxazosin", "lercanidipine", "felodipine", "diltiazem",
    "verapamil", "enalapril", "lisinopril", "captopril", "nebivolol",
    "clonidine", "methyldopa",
]

_CHOL_MMOL_TO_MGDL = 38.67


def _to_mmol(value):
    """Given a raw numeric cholesterol value, return it in mmol/L.
    Referral letters occasionally quote US-style mg/dL; anything above 20
    is almost certainly mg/dL (mmol/L values sit roughly 2-10)."""
    if value is None:
        return None
    if value > 20:
        return round(value / _CHOL_MMOL_TO_MGDL, 2)
    return round(value, 2)


def _first_match(text, patterns, flags=re.IGNORECASE):
    for pat in patterns:
        m = re.search(pat, text, flags)
        if m:
            return m
    return None


# ─────────────────────────────────────────────────────────────
# Field extraction
# ─────────────────────────────────────────────────────────────

def extract_fields(text):
    """
    Parse free-text GP referral content into ASCVD risk-calculator inputs.
    Returns a dict of {field: {"value": ..., "found": bool}}.
    """
    result = {}

    # ── Name (display only, never used in the risk calculation) ──
    name_m = _first_match(text, [
        r"Re[:\t ]+(?:Mr|Mrs|Ms|Miss|Mx|Dr)?\.? *([A-Z][A-Za-z'\-]+(?: +[A-Z][A-Za-z'\-]+){0,2})",
        r"Patient[:\t ]+([A-Z][A-Za-z'\-]+(?: +[A-Z][A-Za-z'\-]+){0,2})",
        r"Dear\s+Dr[^,\n]*,\s*\n*(?:Re[:\t ]+)?([A-Z][A-Za-z'\-]+(?: +[A-Z][A-Za-z'\-]+){0,2})",
    ])
    result["patient_name"] = {"value": name_m.group(1).strip() if name_m else None, "found": bool(name_m)}

    # ── Title (used as a sex fallback) ──
    title_m = re.search(r"\b(Mr|Mrs|Ms|Miss)\.?\s+[A-Z]", text)
    title_sex = None
    if title_m:
        title_sex = "male" if title_m.group(1) == "Mr" else "female"

    # ── Date of birth ──
    dob_m = _first_match(text, [
        r"D(?:ate)?\s*of\s*[Bb]irth[:\s]*([\d]{1,2}[/\-\.][\d]{1,2}[/\-\.][\d]{2,4})",
        r"\bDOB[:\s]*([\d]{1,2}[/\-\.][\d]{1,2}[/\-\.][\d]{2,4})",
    ])
    dob_str = dob_m.group(1) if dob_m else None
    result["dob"] = {"value": dob_str, "found": bool(dob_str)}

    # ── Age ──
    age_val = None
    age_m = _first_match(text, [
        r"\bAge[:\s]+(\d{1,3})\b",
        r"\b(\d{1,3})\s*(?:yo|y\.?o\.?|years?[\s\-]old)\b",
        r"\b(\d{1,3})\s*[-]?\s*year[-\s]old\b",
    ])
    if age_m:
        try:
            candidate = int(age_m.group(1))
            if 0 < candidate < 120:
                age_val = candidate
        except ValueError:
            pass

    if age_val is None and dob_str:
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y"):
            try:
                dob_dt = datetime.strptime(dob_str, fmt)
                today = datetime.now()
                age_val = today.year - dob_dt.year - (
                    (today.month, today.day) < (dob_dt.month, dob_dt.day)
                )
                break
            except ValueError:
                continue

    result["age"] = {"value": age_val, "found": age_val is not None}

    # ── Sex ──
    sex_val = None
    sex_m = _first_match(text, [
        r"\bSex[:\s]+(Male|Female)\b",
        r"\bGender[:\s]+(Male|Female)\b",
    ])
    if sex_m:
        sex_val = sex_m.group(1).lower()
    else:
        shorthand_m = re.search(r"\b\d{1,3}\s*([MF])\b(?!\w)", text)
        if shorthand_m:
            sex_val = "male" if shorthand_m.group(1) == "M" else "female"
        elif re.search(r"\b\d{1,3}[-\s]?year[-\s]old\s+(man|male)\b", text, re.IGNORECASE):
            sex_val = "male"
        elif re.search(r"\b\d{1,3}[-\s]?year[-\s]old\s+(woman|female|lady)\b", text, re.IGNORECASE):
            sex_val = "female"
        elif title_sex:
            sex_val = title_sex
    result["sex"] = {"value": sex_val, "found": sex_val is not None}

    # ── Systolic blood pressure ──
    sbp_val = None
    bp_m = _first_match(text, [
        r"(?:Blood\s*[Pp]ressure|BP)\b(?:[\s:]+[A-Za-z']{2,12}){0,2}[\s:]+(\d{2,3})\s*/\s*(\d{2,3})",
    ])
    if bp_m:
        try:
            candidate = int(bp_m.group(1))
            if 60 <= candidate <= 260:
                sbp_val = candidate
        except ValueError:
            pass
    result["systolic_bp"] = {"value": sbp_val, "found": sbp_val is not None}

    # ── Total cholesterol ──
    tc_m = _first_match(text, [
        r"Total\s*[Cc]holesterol[:\s]+([\d.]+)",
        r"\bTC[:\s]+([\d.]+)",
        r"\bChol(?:esterol)?[:\s]+([\d.]+)",
    ])
    tc_val = None
    if tc_m:
        try:
            tc_val = _to_mmol(float(tc_m.group(1)))
        except ValueError:
            pass
    result["total_chol_mmol"] = {"value": tc_val, "found": tc_val is not None}

    # ── HDL cholesterol ──
    hdl_m = _first_match(text, [
        r"HDL(?:[\s\-]?[Cc](?:hol(?:esterol)?)?)?[:\s]+([\d.]+)",
    ])
    hdl_val = None
    if hdl_m:
        try:
            hdl_val = _to_mmol(float(hdl_m.group(1)))
        except ValueError:
            pass
    result["hdl_chol_mmol"] = {"value": hdl_val, "found": hdl_val is not None}

    # ── LDL cholesterol (display only — not used in the Pooled Cohort Equations) ──
    ldl_m = _first_match(text, [
        r"LDL(?:[\s\-]?[Cc](?:hol(?:esterol)?)?)?[:\s]+([\d.]+)",
    ])
    ldl_val = None
    if ldl_m:
        try:
            ldl_val = _to_mmol(float(ldl_m.group(1)))
        except ValueError:
            pass
    result["ldl_chol_mmol"] = {"value": ldl_val, "found": ldl_val is not None}

    # ── Smoking status ──
    smoker_val = None
    if re.search(r"\b(?:never\s+smoked|non[-\s]?smoker|nonsmoker|lifelong\s+non[-\s]?smoker)\b", text, re.IGNORECASE):
        smoker_val = False
    elif re.search(r"\b(?:ex[-\s]?smoker|former\s+smoker|quit\s+smoking|stopped\s+smoking)\b", text, re.IGNORECASE):
        smoker_val = False
    elif re.search(r"\b(?:current\s+smoker|smokes?\s+\d|pack[-\s]?year|active\s+smoker)\b", text, re.IGNORECASE):
        smoker_val = True
    elif re.search(r"\bsmoker\b", text, re.IGNORECASE):
        smoker_val = True
    result["smoker"] = {"value": smoker_val, "found": smoker_val is not None}

    # ── Diabetes ──
    diabetes_val = None
    if re.search(r"\bno\s+(?:history\s+of\s+)?diabetes\b|\bnon[-\s]?diabetic\b|\bnot\s+diabetic\b", text, re.IGNORECASE):
        diabetes_val = False
    elif re.search(
        r"\b(?:type\s*2\s*diabetes|type\s*ii\s*diabetes|t2dm|dm2|diabetes\s*mellitus|known\s+diabetic|diabetic\b)\b",
        text, re.IGNORECASE
    ):
        diabetes_val = True
    result["diabetes"] = {"value": diabetes_val, "found": diabetes_val is not None}

    # ── Treated hypertension (medication list scan + explicit phrasing) ──
    treated_val = None
    if re.search(r"\b(?:treated\s+hypertension|hypertension.{0,20}on\s+treatment|on\s+antihypertensive)\b", text, re.IGNORECASE):
        treated_val = True
    else:
        for drug in _ANTIHYPERTENSIVES:
            if re.search(r"\b" + re.escape(drug) + r"\b", text, re.IGNORECASE):
                treated_val = True
                break
    if treated_val is None and re.search(r"\bno\s+(?:history\s+of\s+)?hypertension\b|\bnormotensive\b", text, re.IGNORECASE):
        treated_val = False
    result["on_bp_treatment"] = {"value": treated_val, "found": treated_val is not None}

    return result


def process_pdf(pdf_bytes):
    """Extract ASCVD fields from a GP referral PDF. Returns (fields_dict, found_count)."""
    text = extract_text_from_pdf(pdf_bytes)
    if not text.strip():
        raise ValueError("No extractable text found in this PDF. It may be a scanned image — please enter values manually.")

    fields = extract_fields(text)
    found_count = sum(1 for f in fields.values() if f["found"])
    return fields, found_count

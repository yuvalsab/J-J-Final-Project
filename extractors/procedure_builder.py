# path: bp/pro/extractors/procedure_builder.py
import re
from datetime import datetime

# ------------------ helpers ------------------

def _safe(d, *path, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def _as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]

def _first_non_null(*vals, default=None):
    for v in vals:
        if v not in (None, "", [], {}, "null", "NULL", "N/A", "n/a", "na", "-"):
            return v
    return default

def _strip_html(x):
    if x is None:
        return None
    s = str(x)
    # remove simple HTML tags
    return re.sub(r"<[^>]+>", "", s).strip()

def _to_dt(x):
    """Parse many date & datetime formats. Return datetime or None."""
    if x in (None, "", "null", "NULL", "N/A", "n/a", "na", "-"):
        return None
    s = str(x).strip()

    fmts = (
        # date + time
        "%d-%b-%Y %H:%M:%S",   # 25-Jul-2025 18:31:49
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        # date only
        "%d-%b-%Y",            # 25-Jul-2025
        "%d %b %Y",            # 25 Jul 2025
        "%b %d, %Y",           # Jul 25, 2025
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
    )
    for f in fmts:
        try:
            return datetime.strptime(s, f)
        except Exception:
            pass
    return None  # אם לא הצליח לפרש, נשאיר None

_num_re = re.compile(r"[-+]?\d*\.?\d+")
def _to_int(x):
    """Extract int even from strings like '1' / '1,234' / '<span>106</span>'."""
    if x in (None, "", "null", "NULL", "N/A", "n/a", "na", "-"):
        return None
    s = _strip_html(x).replace(",", " ").strip()
    m = _num_re.search(s)
    if not m:
        return None
    try:
        return int(float(m.group()))
    except Exception:
        return None

def _to_float(x):
    if x in (None, "", "null", "NULL", "N/A", "n/a", "na", "-"):
        return None
    s = _strip_html(x).replace(",", " ").strip()
    m = _num_re.search(s)
    if not m:
        return None
    try:
        return float(m.group())
    except Exception:
        return None

def _size_to_gb(x):
    """
    Parse '29.38 GB' / '4615 MB' / '1024 KB' → float in GB.
    Keeps None if cannot parse.
    """
    if x in (None, "", "null", "NULL", "N/A", "n/a", "na", "-"):
        return None
    s = _strip_html(x)
    m = _num_re.search(s)
    if not m:
        return None
    val = float(m.group())
    unit = s[m.end():].strip().upper()  # text after number
    if unit.startswith("GB"):
        return val
    if unit.startswith("MB"):
        return val / 1024.0
    if unit.startswith("KB"):
        return val / (1024.0 * 1024.0)
    # no unit → assume GB
    return val

def _normalize_catheters(arr):
    """
    Ensure cathetersUsed is a list of dicts with expected keys.
    connectionTimes is a list (kept as-is; items can be dicts with connect/disConnect).
    """
    out = []
    seen = set()
    for c in _as_list(arr):
        if isinstance(c, dict):
            cid = c.get("catheterID") or c.get("catheter_id")
            key = cid or id(c)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "catheterID": cid,
                "name": c.get("name"),
                "partNumber": c.get("partNumber"),
                "lotNumber": c.get("lotNumber"),
                "connectionTimes": _as_list(c.get("connectionTimes")),
            })
        else:
            # plain string → at least preserve the ID
            s = str(c).strip()
            if not s:
                continue
            if s in seen:
                continue
            seen.add(s)
            out.append({
                "catheterID": s,
                "name": None,
                "partNumber": None,
                "lotNumber": None,
                "connectionTimes": [],
            })
    return out

# ------------------ builder ------------------

def build_procedure_document(j):
    case = _safe(j, "caseOverview", default={})
    mapdet = _safe(j, "mappingAndProcedureDetails", default={})
    abldet = _safe(j, "ablationDetails", default={})
    spa = _safe(j, "systemPerformanceAndErrorAnalysis", default={})

    # מצבים שבהם אותו שדה מופיע גם בטופ-לבל וגם ב-caseOverview
    procedure_date_raw = _first_non_null(_safe(case, "procedureDate"), _safe(j, "procedureDate"))
    findings_raw = _first_non_null(_safe(case, "findings", default=[]), _safe(j, "findings", default=[]))
    features_in_use_raw = _first_non_null(_safe(case, "featuresInUse"), _safe(j, "featuresInUse"))
    licences_raw = _first_non_null(_safe(case, "licences"), _safe(j, "licences"))
    targeted_chamber_raw = _first_non_null(_safe(case, "targetedChamber"), _safe(j, "targetedChamber"))
    primary_arr_raw = _first_non_null(_safe(case, "primaryArrhythmia"), _safe(j, "primaryArrhythmia"))
    secondary_arr_raw = _first_non_null(_safe(case, "secondaryArrhythmia"), _safe(j, "secondaryArrhythmia"))
    catheters_used_raw = _first_non_null(_safe(case, "cathetersUsed", default=[]), _safe(j, "cathetersUsed", default=[]))

    # uniqueErrors – יכול להיות מחרוזת עם HTML בטופ-לבל, וגם אובייקט מפורט בתוך spa
    unique_errors_top = _safe(j, "uniqueErrors")
    unique_errors_obj = _safe(spa, "uniqueErrors")

    # גדלים – נשמור גם את הטקסט המקורי וגם Float ב-GB
    study_size_str = _safe(j, "studySize")
    error_size_str = _safe(j, "errorReportSize")
    study_size_gb = _size_to_gb(study_size_str)
    error_size_gb = _size_to_gb(error_size_str)

    doc = {
        "Procedur_id": _first_non_null(_safe(j, "studyUID"), _safe(j, "lightningName")),
        "projectName": _safe(j, "projectName"),
        "cartoVersion": _safe(j, "cartoVersion"),
        "Country": _safe(j, "country"),
        "hospitalName": _safe(j, "hospitalName"),
        "workstationNumber": _safe(j, "workstationNumber"),
        "workstationModel": _safe(j, "workstationModel"),
        "generators": _safe(j, "generators"),
        "piuNum": _safe(j, "piuNum"),
        "lpNum": _safe(j, "lpNum"),

        "installDate": _to_dt(_safe(j, "installDate")),
        "uploadDate": _to_dt(_safe(j, "uploadDate")),
        "analysisDate": _to_dt(_safe(j, "analysisDate")),

        "lightningName": _safe(j, "lightningName"),
        "lightningDescription": _safe(j, "lightningDescription"),
        "studyLocation": _safe(j, "studyLocation"),

        "studyUID": _safe(j, "studyUID"),

        # נשמר גם מקור המחרוזת וגם ערך מספרי ב-GB
        "studySize": study_size_str,
        "studySizeGB": study_size_gb,

        "errorReportSize": error_size_str,
        "errorReportSizeGB": error_size_gb,

        "studiesCount": _to_int(_safe(j, "studiesCount")),

        "findings": _as_list(findings_raw),
        "procedureDate": _to_dt(procedure_date_raw),

        "cathetersUsed": _normalize_catheters(catheters_used_raw),

        "targetedChamber": targeted_chamber_raw,
        "primaryArrhythmia": primary_arr_raw.strip() if isinstance(primary_arr_raw, str) else primary_arr_raw,
        "secondaryArrhythmia": secondary_arr_raw.strip() if isinstance(secondary_arr_raw, str) else secondary_arr_raw,

        "featuresInUse": features_in_use_raw,
        "licences": licences_raw,

        "numberOfMapsCreated": _to_int(_safe(mapdet, "numberOfMapsCreated")),
        "totalPointsCollected": _to_int(_safe(mapdet, "totalPointsCollected")),
        "procedureTime": _safe(mapdet, "procedureTime"),

        "numberOfAblationSessions": _to_int(_safe(abldet, "numberOfAblationSessions")),
        # "4.70 minutes" → נשאיר מחרוזת; אם תרצי – אפשר לפרק בהמשך לדקות float
        "totalAblationTime": _safe(abldet, "totalAblationTime"),
        "ablationType": _safe(abldet, "ablationType"),

        "Crash/Error Data": _safe(spa, "crashErrorData"),
        "Complaint ID": _safe(spa, "complaintID"),
        "Complaint Description": _safe(spa, "complaintDescription"),
        "Complaint From ECM": _safe(spa, "complaintFromECM"),
        "Screen Recordings": _safe(spa, "screenRecordings", default=[]),
        "User Bookmarks": _safe(spa, "userBookmarks", default=[]),

        # uniqueErrors:
        # - אם יש ערך טופ-לבל כמספר בתוך HTML → נהפוך ל-int בשדה ייעודי
        # - וגם נשמור את האובייקט המפורט אם קיים
        "uniqueErrors": unique_errors_obj if isinstance(unique_errors_obj, dict) else _strip_html(unique_errors_obj),
        "uniqueErrorsCount": _to_int(unique_errors_top),

        "unclosedErrors": _safe(spa, "unclosedErrors", default=[]),

        "schemaVersion": 2,
    }

    return doc

import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo


JST = ZoneInfo("Asia/Tokyo")
UTC = timezone.utc

def _ensure_aware(dt, assume_tz=UTC):
    """Return an aware datetime. If dt is naive, attach assume_tz."""
    if not isinstance(dt, datetime):
        return dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=assume_tz)
    return dt

def _to_jst(dt):
    """Convert any datetime (naive→assume UTC) to JST."""
    if not isinstance(dt, datetime):
        return dt
    return _ensure_aware(dt, UTC).astimezone(JST)

def _fmt_dt(dt, tz="JST", fmt="%Y-%m-%d %H:%M"):
    """Format a datetime in JST (default) or UTC ('UTC')."""
    if not isinstance(dt, datetime):
        return str(dt)
    if tz.upper() == "JST":
        return _to_jst(dt).strftime(fmt)
    elif tz.upper() == "UTC":
        return _ensure_aware(dt, UTC).astimezone(UTC).strftime(fmt)
    else:
        return _ensure_aware(dt, UTC).astimezone(ZoneInfo(tz)).strftime(fmt)

def _human_hours(td: timedelta | None) -> str:
    if td is None:
        return "n/a"
    secs = td.total_seconds()
    sign = "-" if secs < 0 else ""
    h = abs(secs) / 3600.0
    return f"{sign}{h:.2f} h"

def _get_raw_info(info):
    """Safely extract a raw prompt string from diverse shapes."""
    if isinstance(info, dict) and "raw" in info:
        return info["raw"]
    raw = getattr(info, "raw", None)
    if isinstance(raw, str):
        return raw
    return str(info)

def _split_prompts(raw: str):
    """
    From a Stable Diffusion-style 'raw' infotext, return (positive, negative)
    and strip trailing metadata (Steps/Sampler/Size/Model/VAE/ControlNet/Refiner/Version...).
    """
    if not isinstance(raw, str):
        return str(raw), ""

    # Find "Negative prompt:" marker (case-insensitive)
    m = re.search(r'(?i)\bnegative\s*prompt\s*:\s*', raw)
    if not m:
        pos = raw.strip().rstrip(", ")
        return pos, ""

    pos = raw[:m.start()].strip().rstrip(", ")
    rest = raw[m.end():]

    meta_pat = re.compile(
        r'\n\s*(?:'
        r'Steps|Sampler|Schedule type|CFG scale|Seed|Size|Model(?: hash)?|'
        r'VAE(?: hash)?|Denoising strength|Masked content|'
        r'Soft inpainting(?:.*)?|ControlNet\s*\d*|Refiner(?:.*)?|'
        r'Refiner switch at|Version'
        r')\s*:',
        re.IGNORECASE | re.DOTALL
    )
    mm = meta_pat.search(rest)
    neg = (rest[:mm.start()] if mm else rest).strip().rstrip(", ")
    return pos, neg

def _is_no_pano_error(e: Exception) -> bool:
    """Normalize various 'no panorama available' messages."""
    s = str(e).lower()
    return ("no panoramas on or before" in s) or ("no outdoor pano on/before" in s)


def dateConverter(data):
    """
    Parse the user's date/time and return BOTH:
      - target_dt_utc_naive: datetime (naive) interpreted as UTC (for existing pipelines)
      - target_dt_jst:       datetime (aware) in JST (for logging)
    Behavior:
      * If user selected "JST", interpret the input as JST and convert to UTC.
      * If user selected "UTC", interpret input as UTC.
    """
    dt_str = f"{data['date']} {data['time']}"
    naive = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")  # naive user input

    if str(data.get("timezone", "")).upper().startswith("JST"):
        local_jst = naive.replace(tzinfo=JST)
        utc_aware = local_jst.astimezone(UTC)
    else:
        utc_aware = naive.replace(tzinfo=UTC)  # treat input as UTC

    target_dt_utc_naive = utc_aware.replace(tzinfo=None)
    target_dt_jst = utc_aware.astimezone(JST)
    return target_dt_utc_naive, target_dt_jst


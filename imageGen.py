
# imageGen.py  (profiles: underwater / overwater) — safe with optional scripts
import base64, json, os, re, requests
from pathlib import Path
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True))
except ImportError:
    pass

BASE_URL = (os.getenv("RUNPOD_URL") or os.getenv("WEBUI_URL") or "").rstrip("/")
AUTH = None  # set ("user","pass") for basic auth

# ----------------- Models (override via env if names differ) -----------------
SDXL_BASE    = os.getenv("SDXL_BASE",    "sd_xl_base_1.0.safetensors [31e35c80fc]")
SDXL_REFINER = os.getenv("SDXL_REFINER", "sd_xl_refiner_1.0.safetensors [7440042bbd]")
SDXL_VAE     = os.getenv("SDXL_VAE",     "sdxl_vae.safetensors")

CNXL_DEPTH   = os.getenv("CNXL_DEPTH",   "controlnetxlCNXL_bdsqlszDepth [c4d5ca3b]")
CNXL_CANNY   = os.getenv("CNXL_CANNY",   "controlnetxlCNXL_bdsqlszCanny [a74daa41]")

# ----------------- Profiles -----------------
PROFILES = {
    "underwater": {
          "seed": 595415233, 
        "steps": 25, "cfg": 6.0, "denoise": 0.63,
        "sampler": "DPM++ 3M SDE", "scheduler": "Karras", "clip_skip": 1,
        "refiner_switch_at": 0.90,
        "target_wh": (1024, 1024),
        "prompt": (
            "underwater shot, underwater surface seen from below, flat flood water surface, refracted sunlight, "
            "soft god rays from above, dancing caustics on the shallow flood water, physics, subtle foam along edges, "
            "photorealistic, high detail, natural flood water colors, aquatic, serene"
        ),
        "negative": (
            "sky, horizon, surface seen from above, shoreline, boat, people, fish, plants, text, logo, watermark, "
            "distortion, cloud, ceiling, whale, shark, human, animal, cell-like pattern, seaweed, jellyfish, mermaid, "
            "coral, swimming, diving, sun, sinking, drowning, divers, rocks, seabed, abstract, land, hectic, baby"
        ),
        "mask_blur": 1, "inpainting_fill": 3, "inpaint_full_res": False, "inpaint_padding": 32, "invert_mask": 0,
        "soft_inpaint": {
    "enabled": True,
    "schedule_bias": 0.8,
    "preserve_strength": 1.2,
    "transition_boost": 2.5,
    "mask_influence": 0.7, 
    "diff_threshold": 1.0,
    "diff_contrast": 8.0,

},
        "controlnet": {
            "processor_res": 512,
            "pixel_perfect": True,
            "units": [
                {
                    "enabled": True,
                    "module": "depth_leres++",
                    "model": CNXL_DEPTH,
                    "weight": 0.30,
                    "guidance_start": 0.0,
                    "guidance_end": 0.8,
                    "threshold_a": 0.0,
                    "threshold_b": 0.0,
                    "control_mode": 0,
                    "resize_mode": 1,
                    "image_from": "init",
                },
                {
                    "enabled": True,
                    "module": "canny",
                    "model": CNXL_CANNY,
                    "weight": 0.45,
                    "guidance_start": 0.0,
                    "guidance_end": 0.9,
                    "threshold_a": 100.0,
                    "threshold_b": 200.0,
                    "control_mode": 0,
                    "resize_mode": 1,
                    "image_from": "canny",
                },
            ]
        },
    },
    "overwater": {
        "steps": 36, "cfg": 7.0, "denoise": 0.55,
        "sampler": "DPM++ 3M SDE Karras", "scheduler": "Karras", "clip_skip": 1,
        "refiner_switch_at": 0.80,
        "target_wh": (1024, 1024),
        "prompt": "calm flood water filling the masked area, subtle foam along edges, high detail, photorealistic",
        "negative": (
            "fence, wall, twirls, railing, poles, buildings, wood, barrier, object, debris, distortion, text, logo, "
            "watermark, people, boats, tree, car, waves, tide, plants, brick, rock, stone, bush"
        ),
        "mask_blur": 1, "inpainting_fill": 0, "inpaint_full_res": False, "inpaint_padding": 32, "invert_mask": 0,
        "soft_inpaint": None,
        "controlnet": None,
    },
}

_ALIASES = {"new": "underwater", "legacy": "overwater"}

DEFAULT_PROFILE = (os.getenv("IMAGEGEN_PROFILE", "underwater").lower().strip() or "underwater")
DEFAULT_PROFILE = _ALIASES.get(DEFAULT_PROFILE, DEFAULT_PROFILE)
if DEFAULT_PROFILE not in PROFILES:
    DEFAULT_PROFILE = "underwater"

# ----------------- helpers -----------------
def _b64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("utf-8")

def _get(endpoint: str):
    if not BASE_URL:
        raise RuntimeError("RUNPOD_URL/WEBUI_URL env is missing")
    url = f"{BASE_URL}/sdapi/v1/{endpoint.lstrip('/')}"
    r = requests.get(url, auth=AUTH, timeout=600)
    r.raise_for_status()
    return r.json()

def _post(endpoint: str, payload: dict):
    if not BASE_URL:
        raise RuntimeError("RUNPOD_URL/WEBUI_URL env is missing")
    url = f"{BASE_URL}/sdapi/v1/{endpoint.lstrip('/')}"
    r = requests.post(url, json=payload, auth=AUTH, timeout=600)
    try:
        r.raise_for_status()
    except Exception:
        print("HTTP", r.status_code, "error:", r.text[:2000])
        raise
    return r.json()

def _set_options(clip_skip: int):
    _post("options", {
        "sd_model_checkpoint": SDXL_BASE,
        "sd_vae": SDXL_VAE,
        "CLIP_stop_at_last_layers": clip_skip,
    })

# ----- script discovery / optional features -----
def _list_scripts():
    # Return dict from /scripts with keys txt2img/img2img (if endpoint exists).
    try:
        s = _get("scripts")
    except Exception:
        return {}
    return s if isinstance(s, dict) else {}

def _norm(s: str) -> str:
    return re.sub(r"[\s_\-]+", "", s.lower())

def _find_script_key(keywords: list) -> str | None:
    # Find an installed script whose name/title contains all keywords (case/space insensitive).
    scripts = _list_scripts()
    pools = []
    for k in ("txt2img", "img2img"):
        v = scripts.get(k) or []
        if isinstance(v, list):
            pools.extend(v)
    needed = [_norm(k) for k in keywords]
    for item in pools:
        if isinstance(item, dict):
            cand = item.get("name") or item.get("title") or ""
        else:
            cand = str(item)
        if cand and all(k in _norm(cand) for k in needed):
            return cand
    return None

# ----------------- optional features -----------------
def _cn_unit_template():
    return {
        "enabled": True,
        "low_vram": False,
        "model": "",
        "module": "",
        "weight": 1.0,
        "image": None,
        "input_image": None,
        "resize_mode": "Crop and Resize",
        "processor_res": 512,
        "threshold_a": 0.0,
        "threshold_b": 0.0,
        "guidance_start": 0.0,
        "guidance_end": 1.0,
        "pixel_perfect": True,
        "control_mode": "Balanced",
    }


CONTROL_MODE_MAP = {
    0: "Balanced",
    1: "My prompt is more important",
    2: "ControlNet is more important",
    "0": "Balanced",
    "1": "My prompt is more important",
    "2": "ControlNet is more important",
    "balanced": "Balanced",
    "prompt": "My prompt is more important",
    "controlnet": "ControlNet is more important",
}
RESIZE_MODE_MAP = {
    0: "Just Resize",
    1: "Crop and Resize",
    2: "Resize and Fill",
    "0": "Just Resize",
    "1": "Crop and Resize",
    "2": "Resize and Fill",
    "just": "Just Resize",
    "crop": "Crop and Resize",
    "fill": "Resize and Fill",
}

def _maybe_soft_inpaint(alwayson_scripts: dict, profile: dict):
    if os.getenv("IMAGEGEN_DISABLE_SOFT_INPAINT", "").strip():
        return
    si = profile.get("soft_inpaint")
    if not si or not si.get("enabled"):
        return

    key = _find_script_key(["soft", "inpaint"])
    if not key:
        return

    # [enabled, schedule_bias, preserve_strength, transition_boost,
    #  mask_influence, diff_threshold, diff_contrast]
    args = [
        True,
        float(si.get("schedule_bias", 1.0)),
        float(si.get("preserve_strength", 1.2)),
        float(si.get("transition_boost", 2.0)),
        float(si.get("mask_influence", 0.55)),   # <- not 0
        float(si.get("diff_threshold", 1.0)),
        float(si.get("diff_contrast", 8.0)),     # <- will be 8, not 2
    ]
    alwayson_scripts[key] = {"args": args}
    print(f"[soft-inpaint] using '{key}' with args={args}")



def _maybe_controlnet(alwayson_scripts: dict, profile: dict, init_b64: str, canny_b64: str):
    if os.getenv("IMAGEGEN_DISABLE_CONTROLNET", "").strip():
        return
    cn = profile.get("controlnet")
    if not cn:
        return
    key = _find_script_key(["control", "net"]) or "controlnet"
    use_field = os.getenv("IMAGEGEN_CN_FIELD", "input_image").strip().lower()  # 'input_image' (default) or 'image'
    units_payload = []
    for u in cn.get("units", []):
        if not u.get("enabled", True):
            continue
        unit = _cn_unit_template()
        unit.update({
                "module": u["module"],
                "model": u["model"],
                "weight": float(u.get("weight", 1.0)),
                "processor_res": int(cn.get("processor_res", 512)),
                "pixel_perfect": bool(cn.get("pixel_perfect", True)),
                "threshold_a": float(u.get("threshold_a", 0.0)),
                "threshold_b": float(u.get("threshold_b", 0.0)),
                "guidance_start": float(u.get("guidance_start", 0.0)),
                "guidance_end": float(u.get("guidance_end", 1.0)),
            })
            # normalize enum fields to strings to satisfy strict validators
        rm = u.get("resize_mode", unit.get("resize_mode", "Crop and Resize"))
        cm = u.get("control_mode", unit.get("control_mode", "Balanced"))
        unit["resize_mode"] = RESIZE_MODE_MAP.get(rm, RESIZE_MODE_MAP.get(str(rm).lower(), "Crop and Resize"))
        unit["control_mode"] = CONTROL_MODE_MAP.get(cm, CONTROL_MODE_MAP.get(str(cm).lower(), "Balanced"))
        src = u.get("image_from", "init")
        b64 = init_b64 if src == "init" else canny_b64
        if use_field == "image":
            unit.pop("input_image", None)
            unit["image"] = {"image": b64}
        else:
            unit.pop("image", None)
            unit["input_image"] = b64
        units_payload.append(unit)
    if units_payload:
        alwayson_scripts[key] = {"args": units_payload}

# ----------------- Public API -----------------
def generate_from_files(street_image: str, mask_image: str, out_path: str,
                        canny_control_image: str | None = None,
                        *, profile: str | None = None,
                        want_info: bool = False) -> str | tuple[str, str | None]:

    prof_key = (profile or DEFAULT_PROFILE).lower()
    prof_key = _ALIASES.get(prof_key, prof_key)
    prof = PROFILES[prof_key]
    _set_options(prof["clip_skip"])

    street_image = str(street_image)
    mask_image   = str(mask_image)
    canny_img    = str(canny_control_image) if canny_control_image else mask_image
    out_path     = str(out_path)
    for pth in (street_image, mask_image, canny_img):
        if not Path(pth).exists():
            raise FileNotFoundError(pth)

    init_b64  = _b64(street_image)
    mask_b64  = _b64(mask_image)
    canny_b64 = _b64(canny_img)

    alwayson = {}
    _maybe_controlnet(alwayson, prof, init_b64, canny_b64)
    _maybe_soft_inpaint(alwayson, prof)

    w, h = prof["target_wh"]
    payload = {
        "prompt": prof["prompt"],
        "negative_prompt": prof["negative"],
        "seed": prof.get("seed", -1),
        "steps": int(prof["steps"]),
        "cfg_scale": float(prof["cfg"]),
        "denoising_strength": float(prof["denoise"]),
        "sampler_name": prof["sampler"].replace(" Karras", ""),
        "scheduler": prof.get("scheduler", "Karras"),
        "width": int(w),
        "height": int(h),
        "init_images": [init_b64],
        "mask": mask_b64,
        "mask_blur": int(prof["mask_blur"]),
        "inpainting_fill": int(prof["inpainting_fill"]),
        "inpaint_full_res": bool(prof["inpaint_full_res"]),
        "inpaint_full_res_padding": int(prof["inpaint_padding"]),
        "inpainting_mask_invert": int(prof["invert_mask"]),
        "refiner_checkpoint": SDXL_REFINER,
        "refiner_switch_at": float(prof["refiner_switch_at"]),
        "resize_mode": 1,
        "alwayson_scripts": alwayson,
    }

    result = _post("img2img", payload)
    infotext = None
    info_raw = result.get("info")
    if isinstance(info_raw, str):
        try:
            j = json.loads(info_raw)            # WebUI sends a JSON string
            if isinstance(j, dict):
                its = j.get("infotexts")
                if isinstance(its, list) and its:
                    infotext = its[0]
                else:
                    infotext = info_raw
        except Exception:
            infotext = info_raw

    b64_img = result["images"][0]
    img_bytes = base64.b64decode(b64_img)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(img_bytes)

    summarize_run(infotext)

    return (out_path, infotext) if want_info else out_path

def summarize_run(info_str: str) -> dict:
    out = {}
    try:
        j = json.loads(info_str)
        egp = j.get("extra_generation_params", {})
        out["seed"] = j.get("seed")
        out["sampler"] = j.get("sampler_name")
        out["denoise"] = j.get("denoising_strength")
        out["refiner_switch_at"] = egp.get("Refiner switch at")
        out["soft_inpaint"] = {k: egp[k] for k in egp if k.lower().startswith("soft inpainting")}
        # ControlNet lines are strings; keep them for display
        out["cn0"] = egp.get("ControlNet 0")
        out["cn1"] = egp.get("ControlNet 1")
    except Exception:
        out["raw"] = info_str
    print(out)
    return out

UUID_RE = re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}")
def _normalize_uuid(u: str) -> str:
    m = UUID_RE.search(u)
    return m.group(0) if m else u.split("_")[0]

def generate_from_uuid(uuid: str, images_dir="images", *,
                       profile: str | None = None,
                       want_info: bool = False) -> str | tuple[str, str | None]:
    d = Path(images_dir)
    base = _normalize_uuid(uuid)

    # normalize profile & requested mask type
    prof_key = (profile or DEFAULT_PROFILE).lower()
    prof_key = _ALIASES.get(prof_key, prof_key)
    if prof_key not in PROFILES:
        prof_key = "underwater"
    want = "underwater" if prof_key == "underwater" else "overwater"

    # street
    street_candidates = sorted(d.glob(f"{base}*streetview.jpg"))
    if not street_candidates:
        raise FileNotFoundError(f"No streetview found for {base}")
    exact = d / f"{base}_streetview.jpg"
    street = exact if exact in street_candidates else street_candidates[0]

    # masks
    all_masks = sorted([p for p in d.glob(f"{base}*_*mask*.png")], key=lambda x: x.name.lower())
    def first(pred):
        for m in all_masks:
            if pred(m): return m
        return None
    mask = first(lambda m: f"_{want}_mask" in m.name and "_naive" not in m.name.lower()) or                first(lambda m: f"_{want}_mask" in m.name and "_naive" in m.name.lower())
    if not mask:
        other = "overwater" if want == "underwater" else "underwater"
        mask = first(lambda m: f"_{other}_mask" in m.name and "_naive" not in m.name.lower()) or                    first(lambda m: f"_{other}_mask" in m.name and "_naive" in m.name.lower())
    if not mask:
        raise FileNotFoundError(
            f"No mask found for {base}. Looked for '*_{want}_mask.png'. "
            f"Found: {[m.name for m in all_masks]}"
        )

    out_path = d / f"{base}_ai.png"
    return generate_from_files(str(street), str(mask), str(out_path),
                               canny_control_image=str(mask),
                               profile=prof_key,
                               want_info=want_info)

if __name__ == "__main__":
    print("imageGen module ready. Default profile:", DEFAULT_PROFILE)

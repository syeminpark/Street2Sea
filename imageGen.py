# imageGen.py
import base64, requests, json, os
from pathlib import Path
import requests
from dotenv import load_dotenv, find_dotenv
import re

try:
    from PIL import Image
except Exception:
    Image = None

# ---- env ----
load_dotenv(find_dotenv(usecwd=True))
BASE_URL = os.getenv("RUNPOD_URL", "").rstrip("/")
AUTH = None  # set to ("user","pass") if your WebUI is auth-protected

# ---- WebUI settings you already use ----
STEPS   = 36
CFG     = 7
DENOISE = 0.55
SEED    = -1
SAMPLER = "DPM++ 3M SDE Karras"

BASE_CKPT    = "sd_xl_base_1.0.safetensors [31e35c80fc]"
REFINER_CKPT = "sd_xl_refiner_1.0.safetensors [7440042bbd]"
SD_VAE       = "sdxl_vae.safetensors"
REFINER_SWITCH_AT = 0.8
TARGET_W = 1024
TARGET_H = 1024

PROMPT = (
    "calm flood water filling the masked area, subtle foam along edges, high detail, photorealistic"
)
NEGATIVE = (
    "fence, wall, twrils, railing, poles, buildings, wood, barrier, object, debris, distortion, text, logo, "
    "watermark, people, boats, tree, car, waves, tide, plants, brick, rock, stone, bush"
)

MASK_BLUR = 1
INPAINTING_FILL = 0
INPAINT_FULL_RES = False
INPAINT_PADDING  = 32
RESIZE_MODE = 0

# ------------- helpers -------------
def _b64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("utf-8")

def _get(endpoint: str):
    url = f"{BASE_URL}/sdapi/v1/{endpoint.lstrip('/')}"
    r = requests.get(url, auth=AUTH, timeout=600)
    r.raise_for_status()
    return r.json()

def _post(endpoint: str, payload: dict):
    url = f"{BASE_URL}/sdapi/v1/{endpoint.lstrip('/')}"
    r = requests.post(url, json=payload, auth=AUTH, timeout=600)
    try:
        r.raise_for_status()
    except Exception:
        # make debugging easier
        print("HTTP", r.status_code, "error:", r.text[:2000])
        raise
    return r.json()

def _set_options():
    _post("options", {
        "sd_model_checkpoint": BASE_CKPT,
        "sd_vae": SD_VAE,
    })

def _img_size(path: str, fallback=(1000, 600)):
    if Image is None:
        return fallback
    try:
        with Image.open(path) as im:
            return im.size
    except Exception:
        return fallback

# ------------- public API -------------
def generate_from_files(street_image: str, mask_image: str, out_path: str) -> str:
    """
    Inpaint 'street_image' using 'mask_image' (white = fill).
    Saves PNG to 'out_path'. Returns the output path.
    """
    if not BASE_URL:
        raise RuntimeError("RUNPOD_URL missing in environment (.env).")

    street_image = str(street_image)
    mask_image   = str(mask_image)
    out_path     = str(out_path)

    if not Path(street_image).exists():
        raise FileNotFoundError(street_image)
    if not Path(mask_image).exists():
        raise FileNotFoundError(mask_image)

    _set_options()

    _orig_w, _orig_h = _img_size(street_image)
    W, H = TARGET_W, TARGET_H
    init_b64 = _b64(street_image)
    mask_b64 = _b64(mask_image)

    payload = {
        "prompt": PROMPT,
        "negative_prompt": NEGATIVE,
        "seed": SEED,
        "steps": STEPS,
        "cfg_scale": CFG,
        "denoising_strength": DENOISE,
        "sampler_name": SAMPLER,
        "width": W,
        "height": H,
        "init_images": [init_b64],
        "mask": mask_b64,
        "mask_blur": MASK_BLUR,
        "inpainting_fill": INPAINTING_FILL,
        "inpaint_full_res": INPAINT_FULL_RES,
        "inpaint_full_res_padding": INPAINT_PADDING,
        "inpainting_mask_invert": 0,  # white edits, black keeps
        "refiner_checkpoint": REFINER_CKPT,
        "refiner_switch_at": REFINER_SWITCH_AT,
          "resize_mode": RESIZE_MODE, 
    }

    result = _post("img2img", payload)
    b64_img = result["images"][0]
    data = base64.b64decode(b64_img)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(data)
    return out_path





UUID_RE = re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}")

def _normalize_uuid(u: str) -> str:
    # Extract bare UUID even if u is "…_naive" or has other suffixes
    m = UUID_RE.search(u)
    return m.group(0) if m else u.split("_")[0]

def generate_from_uuid(uuid: str, images_dir="images") -> str:
    d = Path(images_dir)
    base = _normalize_uuid(uuid)

    # Streetview (no naive variants expected, but handle base uuid mismatch)
    street_candidates = sorted(d.glob(f"{base}*streetview.jpg"))
    if not street_candidates:
        raise FileNotFoundError(f"No streetview found for {base}")
    # Prefer exact "<uuid>_streetview.jpg" if present
    exact = d / f"{base}_streetview.jpg"
    street = exact if exact in street_candidates else street_candidates[0]

    # Mask: ignore *_naive_overwater_mask.png
    mask_candidates = [p for p in d.glob(f"{base}*_overwater_mask.png") if "_naive" not in p.name.lower()]
    if not mask_candidates:
        raise FileNotFoundError(f"No non-naive overwater mask found for {base}")
    mask = sorted(mask_candidates)[0]

    out_path = d / f"{base}_ai.png"
    return generate_from_files(str(street), str(mask), str(out_path))

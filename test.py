#!/usr/bin/env python3
"""
Flood inpainting via Automatic1111 API — matches current WebUI settings from screenshots:
- Base model: sd_xl_base_1.0.safetensors [31e3c580fc]
- Refiner: sd_xl_refiner_1.0.safetensors [7440042bbd], switch at 0.8
- VAE: sdxl_vae.safetensors
- Sampler: DPM++ 2M Karras
- Steps: 36
- CFG: 7.0
- Denoising strength: 0.45
- Size: 1000 x 600
- Masked content: fill
- Inpaint area: Whole picture
- Mask blur: 1
- Seed: 1311410810
"""
import base64, requests, json
from pathlib import Path

# =========================
# CONFIG — EDIT THESE
# =========================
BASE_URL = "https://qswa5r77ba2ky8-3001.proxy.runpod.net/"
AUTH = None                       # ("user","pass") if your WebUI has auth, else None

# Files
STREET_IMAGE = "./images/a33648c3-6fd4-49d2-ba4c-6f9fc3d74ec8_streetview.jpg"
MASK_IMAGE   = "./images/a33648c3-6fd4-49d2-ba4c-6f9fc3d74ec8_mask.png"
OUTDIR       = "outputs_webui_settings"

# Generation params (from WebUI)
WIDTH, HEIGHT = 1000, 600
STEPS  = 36
CFG    = 7
DENOISE = 0.55
SEED    = 1311410810
SAMPLER = "DPM++ 3M SDE Karras"  # schedule baked into the name for A1111 API

# Inpainting (from WebUI)
MASK_BLUR = 1
INPAINTING_FILL = 0           # 0=fill, 1=original, 2=latent noise, 3=latent nothing
INPAINT_FULL_RES = False      # False = Whole picture, True = Only masked
INPAINT_PADDING  = 32         # only used when INPAINT_FULL_RES=True

# Models (from WebUI)
BASE_CKPT   = "sd_xl_base_1.0.safetensors [31e3c580fc]"
REFINER_CKPT= "sd_xl_refiner_1.0.safetensors [7440042bbd]"
SD_VAE      = "sdxl_vae.safetensors"
REFINER_SWITCH_AT = 0.8

# Prompts (from WebUI bars)
PROMPT = (
    "calm flood water filling the masked area, subtle foam along edges, high detail, photorealistic,"
)
NEGATIVE = (
    "fence, wall, railing, poles, buildings, wood, barrier, object, debris, distortion, text, logo, "
    "watermark, people, boats, tree, car, waves, tide, plants, brick, rock, stone, bush,"
)

# Optional: ControlNet (disabled by default to match current WebUI screenshots)
USE_CONTROLNET = False
CN_MODULE = "depth_midas"     # e.g., "depth_midas" or "canny"
CN_MODEL  = ""                # fill with an SDXL ControlNet model name if you enable it
CN_WEIGHT = 0.75
CN_START, CN_END = 0.0, 0.85

# =========================
def b64(path): return base64.b64encode(Path(path).read_bytes()).decode("utf-8")

def get(endpoint):
    url = BASE_URL.rstrip("/") + "/sdapi/v1/" + endpoint.lstrip("/")
    r = requests.get(url, auth=AUTH, timeout=600)
    r.raise_for_status()
    return r.json()

def post(endpoint, payload):
    url = BASE_URL.rstrip("/") + "/sdapi/v1/" + endpoint.lstrip("/")
    r = requests.post(url, json=payload, auth=AUTH, timeout=600)
    try:
        r.raise_for_status()
    except Exception:
        print("HTTP", r.status_code, "error:", r.text[:2000])
        raise
    return r.json()

def set_options():
    # Ensure base checkpoint & VAE match WebUI
    opts = {
        "sd_model_checkpoint": BASE_CKPT,
        "sd_vae": SD_VAE,
        # If you ever need to force Clip Skip: "CLIP_stop_at_last_layers": 1
    }
    post("options", opts)

def controlnet_unit(image_b64):
    return {
        "enabled": True,
        "module": CN_MODULE,
        "model": CN_MODEL,
        "weight": CN_WEIGHT,
        "image": image_b64,
        "processor_res": 640,
        "resize_mode": "Scale to Fit (Inner Fit)",
        "guidance_start": CN_START,
        "guidance_end": CN_END,
        "control_mode": "Balanced",
        "low_vram": False
    }

def inpaint_payload(init_b64, mask_b64, use_cn=False):
    p = {
        "prompt": PROMPT,
        "negative_prompt": NEGATIVE,
        "seed": SEED,
        "steps": STEPS,
        "cfg_scale": CFG,
        "denoising_strength": DENOISE,
        "sampler_name": SAMPLER,
        "width": WIDTH,
        "height": HEIGHT,
        "init_images": [init_b64],
        "mask": mask_b64,
        "mask_blur": MASK_BLUR,
        "inpainting_fill": INPAINTING_FILL,
        "inpaint_full_res": INPAINT_FULL_RES,
        "inpaint_full_res_padding": INPAINT_PADDING,
        "inpainting_mask_invert": 0,     # white edits, black keeps
        # SDXL Refiner (matches the UI toggle + switch at)
        "refiner_checkpoint": REFINER_CKPT,
        "refiner_switch_at": REFINER_SWITCH_AT,
    }
    if use_cn:
        p["alwayson_scripts"] = {
            "ControlNet": {"args": [ controlnet_unit(init_b64) ]}
        }
    return p

def main():
    Path(OUTDIR).mkdir(parents=True, exist_ok=True)
    # Make sure WebUI uses the same base/refiner/vae as the screenshots
    set_options()

    init_b64 = b64(STREET_IMAGE)
    mask_b64 = b64(MASK_IMAGE)

    # Plain inpaint (matches WebUI)
    payload = inpaint_payload(init_b64, mask_b64, use_cn=USE_CONTROLNET)
    result = post("img2img", payload)
    out_path = Path(OUTDIR) / "inpaint_webui_settings.png"
    out_path.write_bytes(base64.b64decode(result["images"][0]))
    print(f"Saved: {out_path.resolve()}")

if __name__ == "__main__":
    main()

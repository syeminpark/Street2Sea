#!/usr/bin/env python3
import base64, requests
from pathlib import Path


# =========================
# CONFIG — EDIT THESE
# =========================
BASE_URL = "https://qswa5r77ba2ky8-3001.proxy.runpod.net/"
AUTH = None                       # ("user","pass") if your WebUI has auth, else None

# list controlnet models
print(requests.get(BASE_URL.rstrip('/') + '/controlnet/model_list').json())
# see / set base model
print(requests.get(BASE_URL.rstrip('/') + '/sdapi/v1/options').json()['sd_model_checkpoint'])# list controlnet models


STREET_IMAGE = "./images/a33648c3-6fd4-49d2-ba4c-6f9fc3d74ec8_streetview.jpg"
MASK_IMAGE   = "./images/a33648c3-6fd4-49d2-ba4c-6f9fc3d74ec8_mask.png"        
OUTDIR       = "outputs_no_ip"

WIDTH, HEIGHT = 1024, 576
STEPS  = 26
CFG = 9.0               # was 7.0
DENOISE = 0.55           # was 0.42
SAMPLER = "DPM++ 2M Karras"

# ControlNet (for structure). Set model string exactly as shown by /controlnet/model_list.
USE_CONTROLNET = True
CN_MODULE = "depth_midas"     # or "canny"
CN_MODEL  = "diffusion_pytorch_model [4d6257d3]"
# Prompts
PROMPT_BASE  = "photorealistic, realistic lighting, cinematic, detailed"
PROMPT_FLOOD = (
  "murky floodwater covering masked ground, wet reflective surface, puddles, "
  "ripples and small waves, foam near edges, debris, realistic refraction"
)

NEGATIVE = (
  "cartoon, CGI, glossy plastic, rainbow colors, psychedelic, fractal patterns, "
  "oil painting, watercolor, text, watermark, oversharpen, artifacts"
)

# =========================
def b64(path): return base64.b64encode(Path(path).read_bytes()).decode("utf-8")

def post(endpoint, payload):
    url = BASE_URL.rstrip("/") + "/sdapi/v1/" + endpoint.lstrip("/")
    r = requests.post(url, json=payload, auth=AUTH, timeout=600)
    try:
        r.raise_for_status()
    except Exception as e:
        print("HTTP", r.status_code, "error:", r.text[:2000])
        raise
    return r.json()

def save_img(img_b64, dest):
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_bytes(base64.b64decode(img_b64))

def make_common(init_b64):
    return dict(
        prompt = f"{PROMPT_BASE}, {PROMPT_FLOOD}",
        negative_prompt = NEGATIVE,
        steps = STEPS,
        cfg_scale = CFG,
        denoising_strength = DENOISE,
        sampler_name = SAMPLER,
        width = WIDTH,
        height = HEIGHT,
        init_images = [init_b64],
    )

def cn_unit(image_b64, weight=1.0, res=640):
    return {
        "enabled": True,
        "module": CN_MODULE,                 # e.g. "depth_midas" or "canny"
        "model": CN_MODEL,                   # exact string from /controlnet/model_list
        "weight": weight,
        "image": image_b64,
        "processor_res": res,
        "resize_mode": "Scale to Fit (Inner Fit)",  # <-- was 1
        "guidance_start": 0.0,
        "guidance_end": 1.0,
        "control_mode": "Balanced",          # <-- was 0
        "low_vram": False
    }
# -------- Variants --------
def run_rp_mask(init_b64, mask_b64):
    payload = make_common(init_b64)
    payload["alwayson_scripts"] = {
        "Regional Prompter": {
            "args": [{
                "regions": [{
                    "mask": mask_b64,
                    "prompt": PROMPT_FLOOD
                }]
            }]
        }
    }
    return post("img2img", payload)

def run_inpaint_mask(init_b64, mask_b64):
    payload = make_common(init_b64)
    payload.update({
        "mask": mask_b64,
        "mask_blur": 3,                 # soft edge, tweak 2–6
        "inpainting_fill": 1,           # 1 = start from ORIGINAL pixels (no crazy noise)
        "inpaint_full_res": True,       # paint at native detail in the masked area
        "inpaint_full_res_padding": 32, # small context border
        "inpainting_mask_invert": 0,    # WHITE = edit, BLACK = keep
        "only_masked": True,            # (A1111 supports this) focus compute inside mask
        "denoising_strength": 0.42,     # gentle; raise to 0.5 if you need more water
    })
    return post("img2img", payload)

def run_rp_mask_cn(init_b64, mask_b64, struct_b64):
    payload = make_common(init_b64)
    payload["alwayson_scripts"] = {
        "Regional Prompter": {
            "args": [{
                "regions": [{
                    "mask": mask_b64,
                    "prompt": PROMPT_FLOOD
                }]
            }]
        },
        "ControlNet": {
            "args": [ cn_unit(struct_b64) ] if USE_CONTROLNET else []
        }
    }
    return post("img2img", payload)


def run_inpaint_mask_cn(init_b64, mask_b64, struct_b64):
    payload = make_common(init_b64)
    payload.update({
        "mask": mask_b64,
        "mask_blur": 3,
        "inpainting_fill": 1,             # ORIGINAL pixels baseline
        "inpaint_full_res": True,
        "inpaint_full_res_padding": 32,
        "inpainting_mask_invert": 0,
        "only_masked": True,
        "denoising_strength": 0.42,
        "alwayson_scripts": {
            "ControlNet": {
                "args": [{
                    "enabled": True,
                    "module": CN_MODULE,                 # e.g. "depth_midas"
                    "model": CN_MODEL,                   # exact string from /controlnet/model_list
                    "weight": 0.8,                       # let depth guide, but not dominate
                    "image": struct_b64,                 # street image as the control
                    "processor_res": 640,
                    "resize_mode": "Scale to Fit (Inner Fit)",
                    "guidance_start": 0.0,
                    "guidance_end": 1.0,
                    "control_mode": "Balanced",
                    "low_vram": False
                }]
            }
        }
    })
    return post("img2img", payload)


def main():
    outdir = Path(OUTDIR); outdir.mkdir(parents=True, exist_ok=True)
    init_b64 = b64(STREET_IMAGE)
    mask_b64 = b64(MASK_IMAGE)

    print("[1/4] Regional Prompting + Mask")
    j1 = run_rp_mask(init_b64, mask_b64)
    save_img(j1["images"][0], outdir / "01_rp_mask.png")

    print("[2/4] Inpainting + Mask")
    j2 = run_inpaint_mask(init_b64, mask_b64)
    save_img(j2["images"][0], outdir / "02_inpaint_mask.png")

    print("[3/4] Regional Prompting + Mask + ControlNet")
    j3 = run_rp_mask_cn(init_b64, mask_b64, init_b64)   # use the street image as structural ref
    save_img(j3["images"][0], outdir / "03_rp_mask_cn.png")

    print("[4/4] Inpainting + Mask + ControlNet")
    j4 = run_inpaint_mask_cn(init_b64, mask_b64, init_b64)
    save_img(j4["images"][0], outdir / "04_inpaint_mask_cn.png")

    print(f"Done. See results in: {outdir.resolve()}")

if __name__ == "__main__":
    main()

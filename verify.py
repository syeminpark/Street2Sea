from PIL import Image

street = Image.open("./images/a33648c3-6fd4-49d2-ba4c-6f9fc3d74ec8_streetview.jpg").convert("RGB")
mask   = Image.open("./images/a33648c3-6fd4-49d2-ba4c-6f9fc3d74ec8_mask.png").convert("L")   # grayscale mask

print("street:", street.size, "mask:", mask.size)

# If different, resize mask to match street (use NEAREST for hard edges)
if mask.size != street.size:
    mask = mask.resize(street.size, Image.NEAREST)
    mask.save("mask_resized.png")

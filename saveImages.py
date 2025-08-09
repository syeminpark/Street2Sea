# saveImages.py
import os
import uuid
from typing import List, Dict

def save_images(images: List[bytes], folder: str = "images", ext: str = "jpg") -> List[Dict[str, str]]:
    """
    Save each image to `folder` as <uuid>_streetview.<ext>.
    Returns a list of dicts: {"uuid": "<uuid>", "filename": "<file>", "path": "<abs/rel path>"}.
    """
    os.makedirs(folder, exist_ok=True)
    saved = []

    for img_bytes in images:
        uid = str(uuid.uuid4())                # string → JSON-safe
        filename = f"{uid}_streetview.{ext}"
        path = os.path.join(folder, filename)

        with open(path, "wb") as f:
            f.write(img_bytes)

        saved.append({"uuid": uid, "filename": filename, "path": path})

    return saved

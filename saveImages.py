import os
import uuid


def save_images(images: list[bytes], folder: str = "images", ext: str = "jpg") -> list[str]:
    """
    Saves a list of raw image bytes into `folder` with UUID filenames.
    Returns list of saved file paths.
    """
    os.makedirs(folder, exist_ok=True)  # ensure folder exists
    saved_paths = []
    UUID=uuid.uuid4()

    for img_bytes in images:
        filename = f"{UUID}_streetview.{ext}"
        file_path = os.path.join(folder, filename)
        with open(file_path, "wb") as f:
            f.write(img_bytes)
        saved_paths.append(file_path)

    return uuid

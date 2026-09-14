"""Conversion between ComfyUI IMAGE tensors and encoded image bytes.

A ComfyUI IMAGE is a torch tensor shaped (B, H, W, C) with float values in 0..1.
Sloyd's image endpoints take multipart file uploads, and its skybox endpoints
return a 2D equirectangular image, so both directions are needed.
"""

from __future__ import annotations

import io

import numpy as np
import torch
from PIL import Image

# Sloyd accepts images up to 20MB. Encoding a 4k+ frame as lossless PNG can exceed
# that, so oversized inputs are downscaled on the long edge before upload.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_UPLOAD_EDGE = 2048


def tensor_to_pil(image: torch.Tensor) -> Image.Image:
    """Convert the first frame of an IMAGE batch to a PIL image."""
    if image is None or image.numel() == 0:
        raise ValueError("Received an empty IMAGE input.")

    frame = image
    if frame.dim() == 4:
        frame = frame[0]
    if frame.dim() != 3:
        raise ValueError(f"Expected an IMAGE shaped (B, H, W, C); got {tuple(image.shape)}.")

    array = frame.detach().cpu().float().clamp(0.0, 1.0).numpy()
    array = (array * 255.0).round().astype(np.uint8)

    channels = array.shape[-1]
    if channels == 1:
        return Image.fromarray(array[:, :, 0], mode="L").convert("RGB")
    if channels == 3:
        return Image.fromarray(array, mode="RGB")
    if channels == 4:
        return Image.fromarray(array, mode="RGBA")
    raise ValueError(f"Unsupported channel count {channels} in IMAGE input.")


def tensor_to_png_bytes(image: torch.Tensor) -> bytes:
    """Encode the first frame of an IMAGE batch as PNG bytes for upload."""
    pil_image = tensor_to_pil(image)

    longest_edge = max(pil_image.size)
    if longest_edge > MAX_UPLOAD_EDGE:
        scale = MAX_UPLOAD_EDGE / longest_edge
        new_size = (
            max(1, round(pil_image.width * scale)),
            max(1, round(pil_image.height * scale)),
        )
        pil_image = pil_image.resize(new_size, Image.LANCZOS)

    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG", optimize=True)
    data = buffer.getvalue()

    if len(data) > MAX_UPLOAD_BYTES:
        # PNG is lossless and can still exceed the cap on noisy images; fall back
        # to high-quality JPEG, which Sloyd also accepts.
        buffer = io.BytesIO()
        pil_image.convert("RGB").save(buffer, format="JPEG", quality=95, optimize=True)
        data = buffer.getvalue()

    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(
            "Encoded image exceeds Sloyd's 20MB upload limit even after downscaling. "
            "Reduce the input resolution."
        )
    return data


def image_bytes_to_tensor(data: bytes) -> torch.Tensor:
    """Decode downloaded image bytes into a single-frame IMAGE tensor."""
    with Image.open(io.BytesIO(data)) as decoded:
        decoded.load()
        pil_image = decoded.convert("RGB")

    array = np.asarray(pil_image).astype(np.float32) / 255.0
    return torch.from_numpy(array).unsqueeze(0)

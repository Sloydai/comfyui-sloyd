"""2D image nodes: Text to Image, Image Edit, and Sketch to Image.

All return a normal ComfyUI IMAGE (result published at jobs/{id}.png), plus a
SLOYD_JOB handle and the saved path. Contracts confirmed against the live API:
  - text-to-image   : JSON { prompt }
  - image-edit      : JSON { jobId, prompt }  (source uploaded via image-upload)
  - sketch-to-image : multipart file upload   (NOT a jobId; a JSON body 500s)
"""

from __future__ import annotations

import torch

from .._compat import logger
from ..images import tensor_to_png_bytes
from .base import (
    CATEGORY_2D,
    SEED_INPUT,
    TIMEOUT_INPUT,
    finish_image_job,
    get_client,
    validate_prompt,
)

RETURN_TYPES = ("IMAGE", "SLOYD_JOB", "STRING", "STRING")
RETURN_NAMES = ("image", "sloyd_job", "image_path", "job_id")


class SloydTextToImage:
    """POST /jobs/text-to-image"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "a cute robot mascot, flat vector art",
                        "tooltip": "What to generate. Up to 4096 characters.",
                    },
                ),
                "seed": SEED_INPUT,
            },
            "optional": {
                "timeout_seconds": TIMEOUT_INPUT,
            },
        }

    RETURN_TYPES = RETURN_TYPES
    RETURN_NAMES = RETURN_NAMES
    FUNCTION = "generate"
    CATEGORY = CATEGORY_2D
    DESCRIPTION = "Generate a 2D image from a text prompt using the Sloyd API."

    def generate(self, prompt: str, seed: int, sloyd_credentials=None, timeout_seconds: int = 900):
        cleaned_prompt = validate_prompt(prompt, required=True)
        with get_client(sloyd_credentials) as client:
            job_id = client.create_job_json("text-to-image", {"prompt": cleaned_prompt})
            logger.info("Sloyd text-to-image job %s started", job_id)
            job = client.wait_for_job(job_id, float(timeout_seconds), "Sloyd text-to-image")
            return finish_image_job(client, job_id, "text-to-image", job, prompt=cleaned_prompt)


class SloydImageEdit:
    """POST /jobs/image-upload -> POST /jobs/image-edit

    The source image is uploaded first; image-edit takes that job id (field 'jobId').
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": (
                    "IMAGE",
                    {"tooltip": "Image to edit. Only the first frame of a batch is used."},
                ),
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "make it snowy",
                        "tooltip": "How to edit the image. Up to 4096 characters.",
                    },
                ),
                "seed": SEED_INPUT,
            },
            "optional": {
                "timeout_seconds": TIMEOUT_INPUT,
            },
        }

    RETURN_TYPES = RETURN_TYPES
    RETURN_NAMES = RETURN_NAMES
    FUNCTION = "generate"
    CATEGORY = CATEGORY_2D
    DESCRIPTION = "Edit an image with a text prompt using the Sloyd API."

    def generate(
        self,
        image: torch.Tensor,
        prompt: str,
        seed: int,
        sloyd_credentials=None,
        timeout_seconds: int = 900,
    ):
        cleaned_prompt = validate_prompt(prompt, required=True)
        image_bytes = tensor_to_png_bytes(image)
        with get_client(sloyd_credentials) as client:
            source_id = client.upload_image(image_bytes, "edit_source.png")
            logger.info("Sloyd: uploaded edit source as image job %s", source_id)
            job_id = client.create_job_json(
                "image-edit", {"jobId": source_id, "prompt": cleaned_prompt}
            )
            logger.info("Sloyd image-edit job %s started", job_id)
            job = client.wait_for_job(job_id, float(timeout_seconds), "Sloyd image-edit")
            return finish_image_job(client, job_id, "image-edit", job, prompt=cleaned_prompt)


class SloydSketchToImage:
    """POST /jobs/sketch-to-image

    Confirmed via live probe: this endpoint takes a multipart file upload, not a
    jobId. A JSON body returns 500.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "sketch": (
                    "IMAGE",
                    {"tooltip": "Sketch or line drawing to turn into an image. First frame only."},
                ),
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "a wooden chair, product photo",
                        "tooltip": "What the sketch should become. Up to 4096 characters.",
                    },
                ),
                "seed": SEED_INPUT,
            },
            "optional": {
                "timeout_seconds": TIMEOUT_INPUT,
            },
        }

    RETURN_TYPES = RETURN_TYPES
    RETURN_NAMES = RETURN_NAMES
    FUNCTION = "generate"
    CATEGORY = CATEGORY_2D
    DESCRIPTION = "Turn a sketch into a finished image using the Sloyd API."

    def generate(
        self,
        sketch: torch.Tensor,
        prompt: str,
        seed: int,
        sloyd_credentials=None,
        timeout_seconds: int = 900,
    ):
        cleaned_prompt = validate_prompt(prompt, required=True)
        sketch_bytes = tensor_to_png_bytes(sketch)
        with get_client(sloyd_credentials) as client:
            job_id = client.create_job_multipart(
                "sketch-to-image",
                files={"file": ("sketch.png", sketch_bytes, "image/png")},
                data={"prompt": cleaned_prompt},
            )
            logger.info("Sloyd sketch-to-image job %s started", job_id)
            job = client.wait_for_job(job_id, float(timeout_seconds), "Sloyd sketch-to-image")
            return finish_image_job(client, job_id, "sketch-to-image", job, prompt=cleaned_prompt)

"""Skybox from Image.

Two Sloyd calls behind one node:

    POST /jobs/image-upload        -> imageJobId (free, 0 credits)
    POST /jobs/skybox-from-image   -> jobId for the 360 environment

The result is a 2D equirectangular image, so it is returned as a normal ComfyUI
IMAGE. That lets it flow into SaveImage, upscalers, and the community 360 preview
nodes without a Sloyd-specific viewer.
"""

from __future__ import annotations

import os

import torch

from .._compat import logger
from ..client import SKYBOX_EXTENSIONS
from ..images import image_bytes_to_tensor, tensor_to_png_bytes
from ..types import KIND_SKYBOX, SloydJob
from .base import (
    CATEGORY_ENV,
    SEED_INPUT,
    TIMEOUT_INPUT,
    get_client,
    optional,
    output_dir,
    to_relative_output_path,
    validate_prompt,
)


class SloydSkyboxFromImage:
    """POST /jobs/skybox-from-image"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": (
                    "IMAGE",
                    {"tooltip": "Source image to expand into a 360 environment. First frame of a batch only."},
                ),
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": (
                            "Optional. Instructions for expanding the source into a full "
                            "360-degree environment. Leave blank to let Sloyd decide."
                        ),
                    },
                ),
                "seed": SEED_INPUT,
            },
            "optional": {
                "gen_style_id": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": (
                            "Optional Sloyd generation style ID. Leave blank for the default. "
                            "Valid IDs are listed under Generation Styles in the Sloyd API docs."
                        ),
                    },
                ),
                "sloyd_credentials": ("SLOYD_CREDENTIALS",),
                "timeout_seconds": TIMEOUT_INPUT,
            },
        }

    RETURN_TYPES = ("IMAGE", "SLOYD_JOB", "STRING", "STRING")
    RETURN_NAMES = ("skybox", "sloyd_job", "skybox_path", "job_id")
    FUNCTION = "generate"
    CATEGORY = CATEGORY_ENV
    DESCRIPTION = (
        "Expand an image into a 360-degree equirectangular skybox using the Sloyd API."
    )

    def generate(
        self,
        image: torch.Tensor,
        prompt: str,
        seed: int,
        gen_style_id: str = "",
        sloyd_credentials=None,
        timeout_seconds: int = 900,
    ):
        cleaned_prompt = validate_prompt(prompt, required=False)
        image_bytes = tensor_to_png_bytes(image)

        with get_client(sloyd_credentials) as client:
            image_job_id = client.upload_image(image_bytes, "skybox_source.png")
            logger.info("Sloyd: uploaded skybox source as image job %s", image_job_id)

            job_id = client.create_job_json(
                "skybox-from-image",
                {
                    "imageJobId": image_job_id,
                    "prompt": optional(cleaned_prompt),
                    "genStyleId": optional(gen_style_id),
                },
            )
            logger.info("Sloyd skybox-from-image job %s started", job_id)
            job = client.wait_for_job(job_id, float(timeout_seconds), "Sloyd skybox")

            content, extension = client.download_asset(job_id, SKYBOX_EXTENSIONS)

            directory = output_dir()
            absolute_path = os.path.join(directory, f"{job_id}{extension}")
            with open(absolute_path, "wb") as handle:
                handle.write(content)
            relative_path = to_relative_output_path(absolute_path)
            logger.info("Sloyd: saved skybox %s", relative_path)

            skybox_tensor = image_bytes_to_tensor(content)

            gen_params = job.get("genParams")
            sloyd_job = SloydJob(
                job_id=job_id,
                kind=KIND_SKYBOX,
                credentials=client.credentials,
                endpoint="skybox-from-image",
                absolute_path=absolute_path,
                relative_path=relative_path,
                prompt=cleaned_prompt,
                gen_params=gen_params if isinstance(gen_params, dict) else {},
            )

        return (skybox_tensor, sloyd_job, relative_path, job_id)

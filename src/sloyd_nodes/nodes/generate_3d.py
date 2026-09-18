"""3D model generation nodes: text, single image, and multi-image to 3D.

Every 3D node emits the same outputs:

    MODEL_3D     (FILE_3D_GLB) plugs straight into Preview 3D (Advanced) / Save 3D
    SLOYD_JOB    typed handle, chains into Retexture / Split to Parts
    STRING       model path relative to ComfyUI/output, for Save Asset / external use
    STRING       raw job id, for logging or an external pipeline
"""

from __future__ import annotations

import torch

from .._compat import logger
from ..images import tensor_to_png_bytes
from .base import (
    CATEGORY_3D,
    MODEL_3D_TYPE,
    SEED_INPUT,
    TEXTURE_RESOLUTIONS,
    TIMEOUT_INPUT,
    TOPOLOGIES,
    clamp_face_count,
    finish_model_job,
    get_client,
    validate_prompt,
)

RETURN_TYPES = (MODEL_3D_TYPE, "SLOYD_JOB", "STRING", "STRING")
RETURN_NAMES = ("model_3d", "sloyd_job", "model_path", "job_id")

# Multi-image jobs take noticeably longer than single-image; the live probe did not
# finish one in 600s, so this family defaults higher.
MULTI_IMAGE_TIMEOUT = {
    "default": 1500,
    "min": 60,
    "max": 3600,
    "step": 30,
    "tooltip": "How long to wait for the job before giving up, in seconds. "
    "Multi-image generation is slower than single-image.",
}

_TARGET_FACE_INPUT = (
    "INT",
    {
        "default": 0,
        "min": 0,
        "max": 500000,
        "step": 1000,
        "tooltip": "0 lets the Sloyd pipeline choose. Maximum 500000.",
    },
)
_TEXTURE_INPUT = (
    TEXTURE_RESOLUTIONS,
    {"default": "auto", "tooltip": "'none' produces a geometry-only model with no texture."},
)
_TOPOLOGY_INPUT = (TOPOLOGIES, {"default": "auto", "tooltip": "Mesh topology of the output."})


class SloydTextTo3D:
    """POST /jobs/text-to-3d"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "a medieval knight helmet",
                        "tooltip": "What to generate. Up to 4096 characters.",
                    },
                ),
                "topology": _TOPOLOGY_INPUT,
                "target_face_count": _TARGET_FACE_INPUT,
                "texture_resolution": _TEXTURE_INPUT,
                "t_pose": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Generate in a neutral T-pose. Useful if you plan to rig or animate.",
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
    CATEGORY = CATEGORY_3D
    DESCRIPTION = "Generate a 3D model (GLB) from a text prompt using the Sloyd API."

    def generate(
        self,
        prompt: str,
        topology: str,
        target_face_count: int,
        texture_resolution: str,
        t_pose: bool,
        seed: int,
        sloyd_credentials=None,
        timeout_seconds: int = 900,
    ):
        cleaned_prompt = validate_prompt(prompt, required=True)
        with get_client(sloyd_credentials) as client:
            job_id = client.create_job_json(
                "text-to-3d",
                {
                    "prompt": cleaned_prompt,
                    "topology": topology,
                    "targetFaceCount": clamp_face_count(target_face_count),
                    "textureResolution": texture_resolution,
                    "tPose": t_pose,
                },
            )
            logger.info("Sloyd text-to-3d job %s started", job_id)
            job = client.wait_for_job(job_id, float(timeout_seconds), "Sloyd text-to-3d")
            return finish_model_job(client, job_id, "text-to-3d", job, prompt=cleaned_prompt)


class SloydImageTo3D:
    """POST /jobs/image-to-3d"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": (
                    "IMAGE",
                    {"tooltip": "Reference image. Only the first frame of a batch is used."},
                ),
                "topology": _TOPOLOGY_INPUT,
                "target_face_count": _TARGET_FACE_INPUT,
                "texture_resolution": _TEXTURE_INPUT,
                "seed": SEED_INPUT,
            },
            "optional": {
                "timeout_seconds": TIMEOUT_INPUT,
            },
        }

    RETURN_TYPES = RETURN_TYPES
    RETURN_NAMES = RETURN_NAMES
    FUNCTION = "generate"
    CATEGORY = CATEGORY_3D
    DESCRIPTION = "Generate a 3D model (GLB) from a single reference image using the Sloyd API."

    def generate(
        self,
        image: torch.Tensor,
        topology: str,
        target_face_count: int,
        texture_resolution: str,
        seed: int,
        sloyd_credentials=None,
        timeout_seconds: int = 900,
    ):
        image_bytes = tensor_to_png_bytes(image)
        with get_client(sloyd_credentials) as client:
            job_id = client.create_job_multipart(
                "image-to-3d",
                files={"file": ("input.png", image_bytes, "image/png")},
                data={
                    "topology": topology,
                    "targetFaceCount": clamp_face_count(target_face_count),
                    "textureResolution": texture_resolution,
                },
            )
            logger.info("Sloyd image-to-3d job %s started", job_id)
            job = client.wait_for_job(job_id, float(timeout_seconds), "Sloyd image-to-3d")
            return finish_model_job(client, job_id, "image-to-3d", job)


class SloydMultiImageTo3D:
    """POST /jobs/multi-image-to-3d

    frontImage is required; at least one of left/back/right is also required.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "front_image": ("IMAGE", {"tooltip": "Front view. Required."}),
            },
            "optional": {
                "left_image": ("IMAGE", {"tooltip": "Left view. At least one of left/back/right is required."}),
                "back_image": ("IMAGE", {"tooltip": "Back view."}),
                "right_image": ("IMAGE", {"tooltip": "Right view."}),
                "generate_type": (
                    ["Normal", "LowPoly", "Geometry", "Sketch"],
                    {"default": "Normal", "tooltip": "Generation mode."},
                ),
                "polygon_type": (
                    ["triangle", "quadrilateral"],
                    {"default": "triangle", "tooltip": "Output polygon type."},
                ),
                "enable_pbr": (
                    "BOOLEAN",
                    {"default": False, "tooltip": "Generate PBR material maps."},
                ),
                "target_face_count": _TARGET_FACE_INPUT,
                "seed": SEED_INPUT,
                "timeout_seconds": ("INT", MULTI_IMAGE_TIMEOUT),
            },
        }

    RETURN_TYPES = RETURN_TYPES
    RETURN_NAMES = RETURN_NAMES
    FUNCTION = "generate"
    CATEGORY = CATEGORY_3D
    DESCRIPTION = (
        "Generate a 3D model (GLB) from up to four views of the same subject using the Sloyd API. "
        "Front view required; connect at least one of left/back/right."
    )

    def generate(
        self,
        front_image: torch.Tensor,
        left_image=None,
        back_image=None,
        right_image=None,
        generate_type: str = "Normal",
        polygon_type: str = "triangle",
        enable_pbr: bool = False,
        target_face_count: int = 0,
        seed: int = 0,
        sloyd_credentials=None,
        timeout_seconds: int = 1500,
    ):
        extra_views = {
            "leftImage": left_image,
            "backImage": back_image,
            "rightImage": right_image,
        }
        if all(v is None for v in extra_views.values()):
            raise ValueError(
                "Multi-Image to 3D needs at least one of left/back/right in addition to the front view."
            )

        files = {"frontImage": ("front.png", tensor_to_png_bytes(front_image), "image/png")}
        for field, tensor in extra_views.items():
            if tensor is not None:
                files[field] = (f"{field}.png", tensor_to_png_bytes(tensor), "image/png")

        data = {
            "GenerateType": generate_type,
            "PolygonType": polygon_type,
            "EnablePBR": "true" if enable_pbr else "false",  # API expects a string
        }
        faces = clamp_face_count(target_face_count)
        if faces:
            data["FaceCount"] = str(faces)

        with get_client(sloyd_credentials) as client:
            job_id = client.create_job_multipart("multi-image-to-3d", files=files, data=data)
            logger.info("Sloyd multi-image-to-3d job %s started", job_id)
            job = client.wait_for_job(job_id, float(timeout_seconds), "Sloyd multi-image-to-3d")
            return finish_model_job(client, job_id, "multi-image-to-3d", job)

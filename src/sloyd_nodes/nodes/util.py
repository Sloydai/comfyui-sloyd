"""Utility nodes: credential selection, saving, and job inspection."""

from __future__ import annotations

import os
import re
import shutil

from .._compat import get_output_directory, logger
from ..credentials import DEFAULT_PROFILE, available_profiles
from ..credentials import resolve as resolve_credentials
from ..types import SloydJob
from .base import CATEGORY_UTIL, to_relative_output_path

_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._/-]+")


class SloydCredentialsNode:
    """Selects a named credential profile.

    Only the profile *name* is a widget value. The client id and secret are read
    server-side from sloyd_config.json, so nothing sensitive is serialised into the
    workflow JSON or into the metadata of generated files.

    Most users never need this node: leave the credentials input on the generation
    nodes unconnected and they resolve the default automatically.
    """

    @classmethod
    def INPUT_TYPES(cls):
        profiles = available_profiles()
        return {
            "required": {
                "profile": (
                    profiles,
                    {
                        "default": DEFAULT_PROFILE,
                        "tooltip": (
                            "Named profile from sloyd_config.json. 'default' falls back to the "
                            "SLOYD_CLIENT_ID / SLOYD_CLIENT_SECRET environment variables."
                        ),
                    },
                ),
            }
        }

    RETURN_TYPES = ("SLOYD_CREDENTIALS",)
    RETURN_NAMES = ("sloyd_credentials",)
    FUNCTION = "load"
    CATEGORY = CATEGORY_UTIL
    DESCRIPTION = (
        "Select a named Sloyd credential profile. Only needed when using more than "
        "one Sloyd account in a single workflow."
    )

    def load(self, profile: str):
        credentials = resolve_credentials(profile)
        logger.info("Sloyd: resolved profile %s (%s)", credentials.profile, credentials.redacted_id)
        return (credentials,)


class SloydSaveAsset:
    """Copies a generated asset to a chosen name under ComfyUI/output."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "sloyd_job": ("SLOYD_JOB",),
                "filename_prefix": (
                    "STRING",
                    {
                        "default": "sloyd/model",
                        "tooltip": (
                            "Output name relative to ComfyUI/output, without an extension. "
                            "A counter is appended when the name already exists."
                        ),
                    },
                ),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("saved_path",)
    FUNCTION = "save"
    CATEGORY = CATEGORY_UTIL
    OUTPUT_NODE = True
    DESCRIPTION = "Save a generated Sloyd asset under a chosen filename in ComfyUI/output."

    def save(self, sloyd_job: SloydJob, filename_prefix: str):
        source = sloyd_job.absolute_path
        if not source or not os.path.isfile(source):
            raise ValueError(
                f"Sloyd job {sloyd_job.job_id} has no downloaded file to save. "
                "Run the generation node again."
            )

        prefix = _UNSAFE_FILENAME.sub("_", (filename_prefix or "sloyd/model").strip("/ "))
        if not prefix:
            prefix = "sloyd/model"

        extension = os.path.splitext(source)[1]
        base_dir = get_output_directory()
        destination = os.path.join(base_dir, f"{prefix}{extension}")
        os.makedirs(os.path.dirname(destination), exist_ok=True)

        counter = 1
        while os.path.exists(destination):
            destination = os.path.join(base_dir, f"{prefix}_{counter:05d}{extension}")
            counter += 1

        shutil.copy2(source, destination)
        relative = to_relative_output_path(destination)
        logger.info("Sloyd: saved asset to %s", relative)
        return (relative,)


class SloydJobInfo:
    """Unpacks a SLOYD_JOB into plain strings for debugging or downstream text nodes."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"sloyd_job": ("SLOYD_JOB",)}}

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("job_id", "kind", "asset_path", "gen_params")
    FUNCTION = "info"
    CATEGORY = CATEGORY_UTIL
    DESCRIPTION = "Read the job id, kind, local path, and applied parameters from a Sloyd job."

    def info(self, sloyd_job: SloydJob):
        import json

        return (
            sloyd_job.job_id,
            sloyd_job.kind,
            sloyd_job.relative_path or "",
            json.dumps(sloyd_job.gen_params, indent=2, sort_keys=True),
        )

"""The SLOYD_JOB link type.

Sloyd's model tools (retexture, split-to-parts, skybox-edit) take the jobId of an
asset the caller already owns. Passing a bare job id string around would make the
user copy identifiers by hand, so generation nodes emit a typed handle instead.
It carries the credentials that created the job, which keeps a chained node on the
same key without re-resolving.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .credentials import SloydCredentials

KIND_MODEL = "model"
KIND_SKYBOX = "skybox"
KIND_IMAGE = "image"


@dataclass
class SloydJob:
    """A completed Sloyd job and the local file it was downloaded to."""

    job_id: str
    kind: str
    credentials: SloydCredentials
    endpoint: str
    absolute_path: str | None = None
    relative_path: str | None = None
    prompt: str = ""
    gen_params: dict[str, Any] = field(default_factory=dict)

    def require_kind(self, expected: str, node_label: str) -> None:
        """Guard chained nodes against being fed the wrong sort of job."""
        if self.kind != expected:
            raise ValueError(
                f"{node_label} expects a Sloyd {expected} job, but received a "
                f"{self.kind} job (id {self.job_id}). Check the wiring."
            )

    def __repr__(self) -> str:
        return (
            f"SloydJob(job_id={self.job_id!r}, kind={self.kind!r}, "
            f"endpoint={self.endpoint!r}, path={self.relative_path!r})"
        )

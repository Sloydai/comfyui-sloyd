"""HTTP client for the Sloyd API.

Every generation endpoint follows the same three-step shape:

    POST /jobs/<endpoint>   ->  { "jobId": "..." }        (returns in under a second)
    GET  /jobs/{jobId}      ->  poll until status success or error
    GET  <public asset URL> ->  download the finished file

See https://api-dashboard.sloyd.ai/documentation/
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, BinaryIO

import requests

from ._compat import ProgressBar, logger, raise_if_cancelled
from .credentials import SloydCredentials
from .errors import (
    SloydError,
    SloydCredentialsError,
    SloydInsufficientCreditsError,
    SloydJobFailedError,
    SloydRateLimitError,
    SloydTimeoutError,
    insufficient_credits_message,
    invalid_credentials_message,
    rate_limit_message,
)

BASE_URL = "https://api.sloyd.ai/api"
ASSET_BASE_URL = "https://storage.googleapis.com/ai-services-quality/jobs"

# Sloyd caps each key at 5 concurrent jobs (pending or running) while the API is
# in test. ComfyUI users batch aggressively, so a 429 is an expected condition
# rather than an error: back off and retry instead of failing the run.
MAX_CONCURRENT_JOBS = 5
RATE_LIMIT_MAX_WAIT = 600.0
RATE_LIMIT_BACKOFF = (5.0, 10.0, 20.0, 30.0, 45.0, 60.0)

REQUEST_TIMEOUT = 60
POLL_INTERVAL = 2.0
DEFAULT_JOB_TIMEOUT = 900.0

TERMINAL_SUCCESS = {"success", "completed"}
TERMINAL_ERROR = {"error", "failed"}

# 3D endpoints publish a GLB at jobs/{jobId}.glb. Skybox jobs publish a 2D
# equirectangular image at the same path, but the documentation does not state
# the extension, so candidates are probed in order.
GLB_EXTENSIONS = (".glb",)
SKYBOX_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def asset_url(job_id: str, extension: str) -> str:
    return f"{ASSET_BASE_URL}/{job_id}{extension}"


class SloydClient:
    """Authenticated Sloyd API client scoped to one credential pair."""

    def __init__(self, credentials: SloydCredentials, timeout: int = REQUEST_TIMEOUT) -> None:
        self._credentials = credentials
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(credentials.headers())

    @property
    def credentials(self) -> SloydCredentials:
        """The credential pair this client authenticates with."""
        return self._credentials

    # --- Low-level request handling ----------------------------------------

    def _raise_for_status(self, response: requests.Response) -> None:
        if response.status_code < 400:
            return

        body: dict[str, Any] = {}
        try:
            parsed = response.json()
            if isinstance(parsed, dict):
                body = parsed
        except (ValueError, json.JSONDecodeError):
            pass

        if response.status_code == 401:
            raise SloydCredentialsError(invalid_credentials_message())

        if response.status_code == 402:
            raise SloydInsufficientCreditsError(
                insufficient_credits_message(
                    body.get("required", "?"), body.get("available", "?")
                )
            )

        if response.status_code == 429:
            raise SloydRateLimitError(rate_limit_message(MAX_CONCURRENT_JOBS))

        message = body.get("message") or response.text.strip() or response.reason
        raise SloydError(f"Sloyd API error {response.status_code}: {message}")

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{BASE_URL}{path}"
        try:
            response = self._session.request(method, url, timeout=self._timeout, **kwargs)
        except requests.Timeout as exc:
            raise SloydError(
                f"Sloyd API request to {path} timed out after {self._timeout}s."
            ) from exc
        except requests.RequestException as exc:
            raise SloydError(f"Could not reach the Sloyd API at {url}: {exc}") from exc

        self._raise_for_status(response)
        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise SloydError(f"Sloyd API returned a non-JSON response for {path}.") from exc
        if not isinstance(payload, dict):
            raise SloydError(f"Sloyd API returned an unexpected response shape for {path}.")
        return payload

    def _request_with_backoff(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Issue a request, absorbing the concurrency cap with bounded backoff."""
        waited = 0.0
        for attempt in range(len(RATE_LIMIT_BACKOFF) + 1):
            try:
                return self._request(method, path, **kwargs)
            except SloydRateLimitError:
                if attempt >= len(RATE_LIMIT_BACKOFF) or waited >= RATE_LIMIT_MAX_WAIT:
                    raise
                delay = RATE_LIMIT_BACKOFF[attempt]
                logger.info(
                    "Sloyd: %d concurrent jobs already running, retrying in %.0fs",
                    MAX_CONCURRENT_JOBS,
                    delay,
                )
                self._sleep_interruptible(delay)
                waited += delay
        raise SloydRateLimitError(rate_limit_message(MAX_CONCURRENT_JOBS))

    @staticmethod
    def _sleep_interruptible(seconds: float) -> None:
        """Sleep in short slices so Cancel stays responsive."""
        deadline = time.monotonic() + seconds
        while True:
            raise_if_cancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(0.5, remaining))

    # --- Job creation -------------------------------------------------------

    def create_job_json(self, endpoint: str, payload: dict[str, Any]) -> str:
        body = {key: value for key, value in payload.items() if value is not None}
        response = self._request_with_backoff("POST", f"/jobs/{endpoint}", json=body)
        return self._extract_job_id(response, endpoint)

    def create_job_multipart(
        self,
        endpoint: str,
        files: dict[str, tuple[str, bytes, str]],
        data: dict[str, Any] | None = None,
    ) -> str:
        form = {key: str(value) for key, value in (data or {}).items() if value is not None}
        response = self._request_with_backoff(
            "POST", f"/jobs/{endpoint}", files=files, data=form
        )
        return self._extract_job_id(response, endpoint)

    @staticmethod
    def _extract_job_id(response: dict[str, Any], endpoint: str) -> str:
        job_id = response.get("jobId") or response.get("id")
        if not job_id:
            raise SloydError(
                f"Sloyd /jobs/{endpoint} did not return a jobId. Response: {response}"
            )
        return str(job_id)

    def upload_image(self, image_bytes: bytes, filename: str = "image.png") -> str:
        """Upload a standalone image and return its job id. Free (0 credits)."""
        return self.create_job_multipart(
            "image-upload", {"file": (filename, image_bytes, "image/png")}
        )

    # --- Polling ------------------------------------------------------------

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/jobs/{job_id}")

    def wait_for_job(
        self,
        job_id: str,
        timeout: float = DEFAULT_JOB_TIMEOUT,
        label: str = "Sloyd job",
    ) -> dict[str, Any]:
        """Poll until the job reaches a terminal status.

        Reports progress and honours Cancel, so a multi-minute generation does not
        leave the ComfyUI queue looking frozen.
        """
        progress = ProgressBar(100)
        started = time.monotonic()
        last_stage: str | None = None

        while True:
            raise_if_cancelled()
            job = self.get_job(job_id)
            status = str(job.get("status", "")).lower()

            stage = _current_stage(job)
            if stage and stage != last_stage:
                logger.info("%s [%s]: %s", label, job_id, stage)
                last_stage = stage

            if status in TERMINAL_SUCCESS:
                progress.set(100)
                return job

            if status in TERMINAL_ERROR:
                reason = job.get("errorMessage") or "no reason given"
                raise SloydJobFailedError(
                    f"Sloyd job {job_id} failed: {reason}. "
                    "Credits for a failed job are refunded automatically."
                )

            elapsed = time.monotonic() - started
            if elapsed > timeout:
                raise SloydTimeoutError(
                    f"Sloyd job {job_id} did not finish within {timeout:.0f}s "
                    f"(last status: {status or 'unknown'}). The job may still complete; "
                    "raise the timeout on the node and run again to pick it up."
                )

            # No total duration is published, so progress is elapsed-based and
            # capped short of 100 to avoid claiming completion before it lands.
            progress.set(min(95, int(elapsed / timeout * 100)))
            self._sleep_interruptible(POLL_INTERVAL)

    # --- Downloading --------------------------------------------------------

    def download_asset(
        self, job_id: str, extensions: tuple[str, ...] = GLB_EXTENSIONS
    ) -> tuple[bytes, str]:
        """Fetch the finished asset, trying each candidate extension in order.

        The asset URL is public and derived from the job id, so no auth is sent.
        """
        attempts: list[str] = []
        for extension in extensions:
            url = asset_url(job_id, extension)
            try:
                response = requests.get(url, timeout=self._timeout)
            except requests.RequestException as exc:
                attempts.append(f"{extension}: {exc}")
                continue
            if response.status_code == 200 and response.content:
                return response.content, extension
            attempts.append(f"{extension}: HTTP {response.status_code}")

        raise SloydError(
            f"Sloyd job {job_id} reported success but no asset could be downloaded. "
            f"Tried: {', '.join(attempts)}."
        )

    def download_asset_to_file(
        self,
        job_id: str,
        destination_dir: str,
        extensions: tuple[str, ...] = GLB_EXTENSIONS,
        basename: str | None = None,
    ) -> str:
        """Download the asset into ``destination_dir`` and return the full path."""
        content, extension = self.download_asset(job_id, extensions)
        os.makedirs(destination_dir, exist_ok=True)
        path = os.path.join(destination_dir, f"{basename or job_id}{extension}")
        tmp_path = f"{path}.part"
        with open(tmp_path, "wb") as handle:  # type: BinaryIO
            handle.write(content)
        os.replace(tmp_path, path)
        return path

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> SloydClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _current_stage(job: dict[str, Any]) -> str | None:
    """Human-readable name of the stage the job is in, if the API reported one."""
    fragments = job.get("fragments")
    if not isinstance(fragments, list) or not fragments:
        return None
    last = fragments[-1]
    if isinstance(last, dict):
        name = last.get("displayName") or last.get("name")
        return str(name) if name else None
    return None

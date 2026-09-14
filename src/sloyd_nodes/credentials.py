"""Sloyd credential resolution.

Sloyd authenticates with two values sent on every request:

    x-client-id: sok_live_...
    x-client-secret: <secret>

ComfyUI serialises every node widget value into the saved workflow JSON *and* into
the metadata of generated files. A secret typed into a widget therefore leaks the
moment a workflow is shared, screenshotted, or handed to a teammate. So the secret
never lives on the graph: nodes resolve it server-side, in this order.

    1. An explicit profile passed in via a Sloyd Credentials node
    2. SLOYD_CLIENT_ID / SLOYD_CLIENT_SECRET environment variables
    3. sloyd_config.json next to this package

Config file shape (all keys optional except the credential pair):

    {
      "client_id": "sok_live_...",
      "client_secret": "...",
      "profiles": {
        "staging": { "client_id": "sok_test_...", "client_secret": "..." }
      }
    }
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from typing import Any

from .errors import SloydCredentialsError, missing_credentials_message

ENV_CLIENT_ID = "SLOYD_CLIENT_ID"
ENV_CLIENT_SECRET = "SLOYD_CLIENT_SECRET"

DEFAULT_PROFILE = "default"

# custom_nodes/comfyui-sloyd/sloyd_config.json
_PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(_PACKAGE_ROOT, "sloyd_config.json")

_lock = threading.Lock()


@dataclass(frozen=True)
class SloydCredentials:
    """A resolved client id / secret pair.

    __repr__ is overridden so the secret cannot land in a log line or traceback.
    """

    client_id: str
    client_secret: str
    profile: str = DEFAULT_PROFILE

    def headers(self) -> dict[str, str]:
        return {
            "x-client-id": self.client_id,
            "x-client-secret": self.client_secret,
        }

    @property
    def redacted_id(self) -> str:
        if len(self.client_id) <= 12:
            return self.client_id
        return f"{self.client_id[:12]}...{self.client_id[-4:]}"

    def __repr__(self) -> str:  # pragma: no cover - defensive
        return f"SloydCredentials(profile={self.profile!r}, client_id={self.redacted_id!r}, client_secret=***)"

    __str__ = __repr__


def _read_config() -> dict[str, Any]:
    with _lock:
        if not os.path.isfile(CONFIG_PATH):
            return {}
        try:
            with open(CONFIG_PATH, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise SloydCredentialsError(
                f"Could not read {CONFIG_PATH}: {exc}. Fix or delete the file and try again."
            ) from exc
    return data if isinstance(data, dict) else {}


def _write_config(data: dict[str, Any]) -> None:
    with _lock:
        tmp_path = f"{CONFIG_PATH}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        os.replace(tmp_path, CONFIG_PATH)
        # Credentials file: owner read/write only. Best effort on platforms
        # where chmod is a no-op (Windows).
        try:
            os.chmod(CONFIG_PATH, 0o600)
        except OSError:
            pass


def _pair_from_mapping(mapping: Any, profile: str) -> SloydCredentials | None:
    if not isinstance(mapping, dict):
        return None
    client_id = str(mapping.get("client_id") or "").strip()
    client_secret = str(mapping.get("client_secret") or "").strip()
    if client_id and client_secret:
        return SloydCredentials(client_id, client_secret, profile)
    return None


def available_profiles() -> list[str]:
    """Profile names offered by the Sloyd Credentials node dropdown."""
    names = [DEFAULT_PROFILE]
    config = _read_config()
    profiles = config.get("profiles")
    if isinstance(profiles, dict):
        names.extend(sorted(str(name) for name in profiles if str(name) != DEFAULT_PROFILE))
    return names


def resolve(profile: str = DEFAULT_PROFILE) -> SloydCredentials:
    """Return the credentials for ``profile``, or raise with setup instructions."""
    profile = (profile or DEFAULT_PROFILE).strip() or DEFAULT_PROFILE
    config = _read_config()

    # A named profile is an explicit request: only look there.
    if profile != DEFAULT_PROFILE:
        profiles = config.get("profiles")
        found = _pair_from_mapping(
            profiles.get(profile) if isinstance(profiles, dict) else None, profile
        )
        if found:
            return found
        raise SloydCredentialsError(
            f"Sloyd profile {profile!r} not found in {CONFIG_PATH}. "
            f"Known profiles: {', '.join(available_profiles())}."
        )

    env_id = os.environ.get(ENV_CLIENT_ID, "").strip()
    env_secret = os.environ.get(ENV_CLIENT_SECRET, "").strip()
    if env_id and env_secret:
        return SloydCredentials(env_id, env_secret, "environment")

    found = _pair_from_mapping(config, DEFAULT_PROFILE)
    if found:
        return found

    raise SloydCredentialsError(missing_credentials_message())


def save_default(client_id: str, client_secret: str) -> None:
    """Persist the default credential pair. Used by the Settings panel."""
    client_id = (client_id or "").strip()
    client_secret = (client_secret or "").strip()
    if not client_id or not client_secret:
        raise SloydCredentialsError("Both a client id and a client secret are required.")

    config = _read_config()
    config["client_id"] = client_id
    config["client_secret"] = client_secret
    _write_config(config)


def status() -> dict[str, Any]:
    """Non-secret summary of what is configured, for the Settings panel."""
    config = _read_config()
    env_configured = bool(
        os.environ.get(ENV_CLIENT_ID, "").strip()
        and os.environ.get(ENV_CLIENT_SECRET, "").strip()
    )
    file_pair = _pair_from_mapping(config, DEFAULT_PROFILE)
    try:
        active: SloydCredentials | None = resolve()
    except SloydCredentialsError:
        active = None
    return {
        "configured": active is not None,
        "source": active.profile if active else None,
        "client_id": active.redacted_id if active else None,
        "env_configured": env_configured,
        "file_configured": file_pair is not None,
        "config_path": CONFIG_PATH,
        "profiles": available_profiles(),
    }

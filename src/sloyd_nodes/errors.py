"""Error types that render as actionable messages in the ComfyUI toast.

ComfyUI surfaces the string of whatever exception a node raises. Sloyd's failure
modes (missing credentials, empty credit balance, the concurrency cap) are all
things a user can fix, so each one gets a message that says how.
"""

from __future__ import annotations

DASHBOARD_URL = "https://api-dashboard.sloyd.ai/"


class SloydError(Exception):
    """Base class for every Sloyd failure surfaced to the user."""


class SloydCredentialsError(SloydError):
    """No usable client id / secret pair was found, or Sloyd rejected it."""


class SloydInsufficientCreditsError(SloydError):
    """HTTP 402. The job was not started and nothing was consumed."""


class SloydRateLimitError(SloydError):
    """HTTP 429. Too many concurrent jobs on this key."""


class SloydJobFailedError(SloydError):
    """The job reached status 'error'. Credits are refunded automatically."""


class SloydTimeoutError(SloydError):
    """The job did not reach a terminal status within the allotted time."""


def missing_credentials_message() -> str:
    return (
        "Sloyd credentials not found. Add them in one of these ways:\n"
        "  1. ComfyUI Settings -> Sloyd -> Client ID / Client Secret\n"
        "  2. Environment variables SLOYD_CLIENT_ID and SLOYD_CLIENT_SECRET\n"
        "  3. sloyd_config.json in the custom_nodes/comfyui-sloyd folder\n"
        f"Generate a key at {DASHBOARD_URL} (API Keys -> Generate Key)."
    )


def invalid_credentials_message() -> str:
    return (
        "Sloyd rejected these credentials (401). The client id and secret must be "
        "from the same key, and the key must still be active.\n"
        f"Check or re-issue it at {DASHBOARD_URL} (API Keys)."
    )


def insufficient_credits_message(required: object, available: object) -> str:
    return (
        f"Not enough Sloyd credits: this job needs {required}, balance is {available}. "
        "The job was not started and nothing was charged.\n"
        f"Top up at {DASHBOARD_URL} (API Keys -> billing), then run again."
    )


def rate_limit_message(max_concurrent: int) -> str:
    return (
        f"Sloyd is running the maximum of {max_concurrent} concurrent jobs for this key. "
        "The node retried with backoff and still could not start.\n"
        "Reduce the batch size, or stagger the queue and run again."
    )

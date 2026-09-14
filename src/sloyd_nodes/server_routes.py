"""Backend routes for the Settings panel credential entry.

The secret is written to sloyd_config.json server-side and is never sent back to the
browser: the status route returns only a redacted client id and which source is
active. That keeps the secret out of the workflow JSON, out of generated-file
metadata, and out of the frontend's persisted settings.

Security note: these routes inherit whatever access control the ComfyUI server has,
which by default is none. On a ComfyUI instance reachable beyond localhost (started
with --listen, or behind a shared tunnel) anyone who can reach the API can write
credentials here. Prefer the SLOYD_CLIENT_ID / SLOYD_CLIENT_SECRET environment
variables for shared or remote deployments.
"""

from __future__ import annotations

from ._compat import logger
from .credentials import save_default, status
from .errors import SloydCredentialsError

_registered = False


def register_routes() -> bool:
    """Attach the Sloyd routes to the running ComfyUI server.

    Returns False when ComfyUI's server is unavailable, so importing the package
    outside ComfyUI stays harmless.
    """
    global _registered
    if _registered:
        return True

    try:
        from aiohttp import web
        from server import PromptServer  # type: ignore
    except ImportError:
        logger.debug("Sloyd: ComfyUI server not available, skipping route registration")
        return False

    instance = getattr(PromptServer, "instance", None)
    if instance is None or not hasattr(instance, "routes"):
        logger.debug("Sloyd: PromptServer has no routes, skipping route registration")
        return False

    routes = instance.routes

    @routes.get("/sloyd/credentials")
    async def get_credentials(_request):
        """Report what is configured. Never returns the secret."""
        try:
            return web.json_response(status())
        except SloydCredentialsError as exc:
            return web.json_response({"configured": False, "error": str(exc)}, status=200)

    @routes.post("/sloyd/credentials")
    async def post_credentials(request):
        """Persist a client id / secret pair to sloyd_config.json."""
        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "Expected a JSON body."}, status=400)

        if not isinstance(payload, dict):
            return web.json_response({"error": "Expected a JSON object."}, status=400)

        client_id = str(payload.get("client_id") or "").strip()
        client_secret = str(payload.get("client_secret") or "").strip()

        try:
            save_default(client_id, client_secret)
        except SloydCredentialsError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except OSError as exc:
            return web.json_response(
                {"error": f"Could not write the Sloyd config file: {exc}"}, status=500
            )

        logger.info("Sloyd: credentials saved to the config file")
        return web.json_response(status())

    _registered = True
    logger.debug("Sloyd: registered credential routes")
    return True

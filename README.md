# Sloyd AI for ComfyUI

Generate 3D models and 360° skyboxes with the [Sloyd API](https://api-dashboard.sloyd.ai/documentation/) inside your ComfyUI workflows.

## Nodes

| Node | Sloyd endpoint | Outputs |
| --- | --- | --- |
| **Sloyd: Text to 3D** | `POST /jobs/text-to-3d` | `SLOYD_JOB`, `model_path`, `job_id` |
| **Sloyd: Image to 3D** | `POST /jobs/image-to-3d` | `SLOYD_JOB`, `model_path`, `job_id` |
| **Sloyd: Skybox from Image** | `POST /jobs/image-upload` → `POST /jobs/skybox-from-image` | `IMAGE`, `SLOYD_JOB`, `skybox_path`, `job_id` |
| **Sloyd: Credentials** | — | `SLOYD_CREDENTIALS` |
| **Sloyd: Save Asset** | — | `saved_path` |
| **Sloyd: Model to 3D File** | — | `model_3d` (for Preview 3D / Save 3D) |
| **Sloyd: Job Info** | — | `job_id`, `kind`, `asset_path`, `gen_params` |

Generated files land in `ComfyUI/output/sloyd/`.

### Wiring

To view a generated model, convert it to a `model_3d` object with **Sloyd: Model to
3D File**, then feed that into **Preview 3D (Advanced)** or a **Save 3D** node:

```
Sloyd: Text to 3D ──model_path──> Sloyd: Model to 3D File ──model_3d──> Preview 3D (Advanced)
```

(Current ComfyUI 3D nodes accept a `model_3d` object, not a path string, so the
bridge node is what makes the connection. On older ComfyUI builds without the File3D
type, the bridge node is hidden; use **Sloyd: Save Asset** with the `model_path`
output instead.)

`skybox` is a normal ComfyUI `IMAGE` (equirectangular), so it flows into
`SaveImage`, upscalers, and community 360° viewers such as
[ComfyUI_preview360panorama](https://github.com/ProGamerGov/ComfyUI_preview360panorama):

```
LoadImage ──image──> Sloyd: Skybox from Image ──skybox──> Preview 360 Panorama
```

`SLOYD_JOB` is a typed handle carrying the job id plus the credentials that created
it. Sloyd's model tools (retexture, split-to-parts, skybox-edit) take the id of an
asset you already own, so this is how those nodes will chain once they ship here —
no copying identifiers by hand.

## Setup

### 1. Get Sloyd credentials

Sloyd authenticates with **two** values, not a single API key:

```
x-client-id: sok_live_...
x-client-secret: <secret>
```

1. Sign in to the [API Dashboard](https://api-dashboard.sloyd.ai/).
2. Open **API Keys** and set up API billing. This requires a prepaid balance
   (minimum $12, converted at 75 credits per $1).
3. Click **Generate Key**. The client secret is shown **once** and cannot be
   retrieved later, so copy it immediately.

### 2. Give them to ComfyUI

Pick one. They resolve in this order:

**Environment variables** — best for Docker, headless, and cloud runners:

```bash
export SLOYD_CLIENT_ID="sok_live_..."
export SLOYD_CLIENT_SECRET="..."
```

**Settings panel** — easiest for a local install. Open
**Settings → Sloyd → Credentials**, paste both values. The secret goes to the
ComfyUI backend, is written to `sloyd_config.json`, and the field then clears.

**Config file** — create `sloyd_config.json` in this folder:

```json
{
  "client_id": "sok_live_...",
  "client_secret": "...",
  "profiles": {
    "staging": { "client_id": "sok_test_...", "client_secret": "..." }
  }
}
```

The file is written `0600` and is listed in both `.gitignore` and `.comfyignore`.

Once configured, leave the `sloyd_credentials` input on the generation nodes
unconnected and it resolves automatically. The **Sloyd: Credentials** node is only
needed to switch between named profiles in a single workflow.

## Why the secret is never a node widget

ComfyUI serialises every widget value into the saved workflow JSON *and* into the
metadata of generated files. A secret typed into a widget leaks the moment you
share a workflow, post a screenshot, or hand the graph to a teammate. So these
nodes resolve credentials server-side and expose only a profile *name* on the graph.

> **Deploying beyond localhost?** The `/sloyd/credentials` route inherits whatever
> access control your ComfyUI server has, which by default is none. On an instance
> started with `--listen` or exposed through a tunnel, anyone who can reach the API
> can write credentials through it. Use the environment variables instead.

## Costs and behaviour

Sloyd is prepaid. Credits are charged when a job **starts**, and refunded
automatically if it fails. Per-endpoint pricing is at
[sloyd.ai/api/pricing](https://sloyd.ai/api/pricing).

- **Each run costs credits.** ComfyUI caches node results, so re-queueing an
  unchanged graph does *not* re-bill. To deliberately re-roll, change the `seed`
  widget. Sloyd has no seed parameter, so this only busts the ComfyUI cache; it
  does not make results reproducible.
- **Running out of credits** raises a message naming the shortfall. The job is not
  started and nothing is charged.
- **Concurrency.** While the Sloyd API is in test, each key is limited to 5
  concurrent jobs. The nodes absorb a `429` with bounded backoff rather than
  failing your run, but large batches will serialise.
- **Cancel works.** Long polls check for interruption, so pressing Cancel stops the
  node instead of blocking the queue.

## Install

Search for **Sloyd** in ComfyUI-Manager, or:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/sloyd-ai/comfyui-sloyd
pip install -r comfyui-sloyd/requirements.txt
```

Restart ComfyUI.

## License

MIT

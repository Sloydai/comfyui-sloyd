# Sloyd AI for ComfyUI

Generate 3D models and 360° skyboxes with the [Sloyd API](https://api-dashboard.sloyd.ai/documentation/) inside your ComfyUI workflows.

## Nodes

Covers every generation endpoint currently live on the Sloyd API.

### 3D models (`Sloyd/3D`)

| Node | Sloyd endpoint | Outputs |
| --- | --- | --- |
| **Sloyd: Text to 3D** | `POST /jobs/text-to-3d` | `model_3d`, `sloyd_job`, `model_path`, `job_id` |
| **Sloyd: Image to 3D** | `POST /jobs/image-to-3d` | `model_3d`, `sloyd_job`, `model_path`, `job_id` |
| **Sloyd: Multi-Image to 3D** | `POST /jobs/multi-image-to-3d` | `model_3d`, `sloyd_job`, `model_path`, `job_id` |
| **Sloyd: Retexture** | `POST /jobs/retexture` | `model_3d`, `sloyd_job`, `model_path`, `job_id` |
| **Sloyd: Split to Parts** | `POST /jobs/split-to-parts` | `model_3d`, `sloyd_job`, `model_path`, `job_id` |

### 360° skyboxes (`Sloyd/Environments`)

| Node | Sloyd endpoint | Outputs |
| --- | --- | --- |
| **Sloyd: Text to Skybox** | `POST /jobs/text-to-worldbox` | `skybox`, `sloyd_job`, `skybox_path`, `job_id` |
| **Sloyd: Skybox from Image** | `image-upload` → `skybox-from-image` | `skybox`, `sloyd_job`, `skybox_path`, `job_id` |
| **Sloyd: Edit Skybox** | `POST /jobs/skybox-edit` | `skybox`, `sloyd_job`, `skybox_path`, `job_id` |

### 2D images (`Sloyd/2D`)

| Node | Sloyd endpoint | Outputs |
| --- | --- | --- |
| **Sloyd: Text to Image** | `POST /jobs/text-to-image` | `image`, `sloyd_job`, `image_path`, `job_id` |
| **Sloyd: Image Edit** | `image-upload` → `image-edit` | `image`, `sloyd_job`, `image_path`, `job_id` |
| **Sloyd: Sketch to Image** | `POST /jobs/sketch-to-image` | `image`, `sloyd_job`, `image_path`, `job_id` |

### Utility (`Sloyd/Utility`)

| Node | Purpose |
| --- | --- |
| **Sloyd: Save Asset** | Copy a generated asset to a filename you choose |

Generated files auto-save to `ComfyUI/output/sloyd/`.

### Wiring

Outputs are ready to use with no adapter node.

**3D** — `model_3d` plugs straight into **Preview 3D (Advanced)** or a **Save 3D** node:

```
Sloyd: Text to 3D ──model_3d──> Preview 3D (Advanced)
```

**Skybox / 2D** — `skybox` and `image` are normal ComfyUI `IMAGE` outputs, so they
flow into `Save Image`, `Preview Image`, upscalers, and community 360° viewers such
as [ComfyUI_preview360panorama](https://github.com/ProGamerGov/ComfyUI_preview360panorama):

```
Load Image ──image──> Sloyd: Skybox from Image ──skybox──> Preview 360 Panorama
```

**Chaining model tools** — `sloyd_job` is a typed handle carrying the job id and the
credentials that made it. Retexture, Split to Parts, and Edit Skybox accept it, so
you wire the upstream node's `sloyd_job` output straight in, no copying identifiers:

```
Sloyd: Text to 3D ──sloyd_job──> Sloyd: Retexture ──model_3d──> Preview 3D (Advanced)
```

(On older ComfyUI builds without the File3D type, `model_3d` falls back to a path
string; use **Sloyd: Save Asset** with the `model_path` output to keep the file.)

Credentials resolve automatically from the environment or config file (see Setup),
so no credential node is needed on the graph.

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

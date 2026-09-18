# Sloyd AI for ComfyUI

Generate production-ready **3D models**, **360° skyboxes**, and **images** from text or
reference images, using the [Sloyd API](https://api-dashboard.sloyd.ai/documentation/)
inside your ComfyUI workflows.

Twelve nodes covering every generation endpoint Sloyd offers: text/image/multi-image to
3D, retexture, split into parts, 360° skyboxes from text or an image plus skybox
editing, and 2D text-to-image, image editing, and sketch-to-image.

Models come back as GLB with clean topology and PBR textures, ready for Blender, Unity,
Unreal, or Godot. Outputs plug straight into ComfyUI's own preview and save nodes, no
adapter nodes needed.

> Sloyd runs in the cloud, so these nodes need no local model weights and no GPU.
> They do need a Sloyd API key with prepaid credits: see [Setup](#setup).

## Quick start

1. Install the pack (see [Install](#install)) and restart ComfyUI.
2. Add your Sloyd key in **Settings → Sloyd → Credentials**
   ([get one here](https://api-dashboard.sloyd.ai/)).
3. Open an example from [`example_workflows/`](example_workflows) and press Run.

## Example workflows

Drag any of these onto the ComfyUI canvas, or use **Workflow → Open**.

| File | What it does |
| --- | --- |
| [`01_text_to_3d.json`](example_workflows/01_text_to_3d.json) | Text prompt → 3D model, shown in Preview 3D |
| [`02_image_to_3d.json`](example_workflows/02_image_to_3d.json) | Load an image → 3D model |
| [`03_text_to_skybox.json`](example_workflows/03_text_to_skybox.json) | Text prompt → 360° equirectangular skybox |
| [`04_retexture_chain.json`](example_workflows/04_retexture_chain.json) | Generate a model, then retexture it via the `sloyd_job` wire |

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

Easiest: the **Settings panel**. Open **Settings → Sloyd**. You get:

- **Setup → Get an API key & buy credits** — a link straight to the dashboard.
- **Setup → Credential status** — shows whether credentials are active and where
  they came from.
- **Credentials → Client ID** and **Client Secret** — paste both. The secret is
  sent to the ComfyUI backend, written to `sloyd_config.json`, and the field is
  then cleared, so it never lives in the browser or in a saved workflow.

Alternatives, resolved in this order (the first that is set wins):

**Environment variables** — best for Docker, headless, and cloud runners:

```bash
export SLOYD_CLIENT_ID="sok_live_..."
export SLOYD_CLIENT_SECRET="..."
```

**Config file** — create `sloyd_config.json` in this folder:

```json
{
  "client_id": "sok_live_...",
  "client_secret": "..."
}
```

The file is written `0600` and is listed in both `.gitignore` and `.comfyignore`.

Once configured, the generation nodes resolve credentials automatically, nothing to
wire on the graph.

## Why the secret is never a node widget

ComfyUI serialises every widget value into the saved workflow JSON *and* into the
metadata of generated files. A secret typed into a widget leaks the moment you
share a workflow, post a screenshot, or hand the graph to a teammate. So these
nodes resolve credentials server-side; nothing sensitive ever touches the graph.

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

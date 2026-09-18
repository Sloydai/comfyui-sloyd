/**
 * Sloyd credential setup in ComfyUI's Settings panel (Settings -> Sloyd).
 *
 * Only setting types documented by ComfyUI are used here: boolean, text, number,
 * slider, combo, color, image, hidden. An unsupported type (e.g. "url") throws
 * during registration and silently drops the ENTIRE extension, which is what kept
 * this panel from appearing in earlier revisions. Do not add a type outside that
 * list. See https://docs.comfy.org/custom-nodes/js/javascript_settings
 *
 * The secret is POSTed to the Python backend, written to sloyd_config.json, and the
 * field is then cleared. It is never kept in frontend-persisted settings, never put
 * on a node, and never returned by the status route, so it cannot leak through a
 * shared workflow or a generated file's metadata.
 */

// Served from /extensions/comfyui-sloyd/js/, so the app scripts are three levels up
// at /scripts/. Using "../../" resolves to /extensions/scripts/ which 404s, silently
// preventing this whole extension from loading.
import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const DASHBOARD_URL = "https://api-dashboard.sloyd.ai/";

const ID_CLIENT_ID = "Sloyd.Credentials.ClientId";
const ID_CLIENT_SECRET = "Sloyd.Credentials.ClientSecret";
const ID_STATUS = "Sloyd.Credentials.Status";

let pendingClientId = "";
// onChange also fires once per page load; only save on genuine user input.
let ready = false;

function toast(severity, summary, detail) {
  try {
    app.extensionManager?.toast?.add({ severity, summary, detail, life: 8000 });
  } catch (err) {
    console.log(`[Sloyd] ${summary}: ${detail ?? ""}`);
  }
}

async function readStatus() {
  try {
    const response = await api.fetchApi("/sloyd/credentials");
    if (!response.ok) return null;
    return await response.json();
  } catch (err) {
    console.warn("[Sloyd] Could not read credential status:", err);
    return null;
  }
}

async function saveCredentials(clientId, clientSecret) {
  const response = await api.fetchApi("/sloyd/credentials", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: clientId, client_secret: clientSecret }),
  });
  let payload = {};
  try {
    payload = await response.json();
  } catch (err) {
    /* non-JSON error body */
  }
  if (!response.ok) {
    throw new Error(payload.error || `Save failed with HTTP ${response.status}`);
  }
  return payload;
}

function setSetting(id, value) {
  try {
    app.ui.settings.setSettingValue(id, value);
  } catch (err) {
    /* settings not ready yet */
  }
}

function getSetting(id) {
  try {
    return (app.ui.settings.getSettingValue(id) || "").trim();
  } catch (err) {
    return "";
  }
}

function describeStatus(status) {
  if (!status) return "Unknown - is the ComfyUI backend running?";
  if (!status.configured) {
    return `Not configured. Get a key at ${DASHBOARD_URL} then paste it below.`;
  }
  const source =
    status.source === "environment"
      ? "environment variables"
      : status.source === "default"
        ? "config file"
        : status.source;
  return `Active: ${status.client_id} (via ${source})`;
}

async function refreshStatus() {
  const status = await readStatus();
  setSetting(ID_STATUS, describeStatus(status));
  return status;
}

/** Persist once both halves are present, then clear the secret field. */
async function trySave() {
  if (!ready) return; // ignore the load-time onChange
  const clientId = (pendingClientId || getSetting(ID_CLIENT_ID) || "").trim();
  const secret = getSetting(ID_CLIENT_SECRET);
  if (!clientId || !secret) return; // Sloyd needs the pair on every request

  try {
    const status = await saveCredentials(clientId, secret);
    setSetting(ID_CLIENT_SECRET, ""); // never keep the secret client-side
    setSetting(ID_STATUS, describeStatus(status));
    toast(
      "success",
      "Sloyd credentials saved",
      `Stored for ${status.client_id || clientId}. The secret stays on the server, not in your workflows.`
    );
  } catch (err) {
    toast("error", "Sloyd credentials not saved", String(err.message || err));
  }
}

app.registerExtension({
  name: "sloyd.credentials",

  settings: [
    {
      id: ID_STATUS,
      category: ["Sloyd", "Credentials", "Status"],
      name: "Status",
      tooltip:
        "Whether Sloyd credentials are active, and where they came from. " +
        `Get a key and buy prepaid credits at ${DASHBOARD_URL} (API Keys -> Generate Key).`,
      type: "text",
      defaultValue: "Checking...",
      attrs: { readonly: true },
    },
    {
      id: ID_CLIENT_ID,
      category: ["Sloyd", "Credentials", "Client ID"],
      name: "Client ID",
      tooltip:
        `The sok_live_... value from ${DASHBOARD_URL} (API Keys). ` +
        "Safe to store; this is not the secret.",
      type: "text",
      defaultValue: "",
      onChange: async (value) => {
        pendingClientId = (value || "").trim();
        await trySave();
      },
    },
    {
      id: ID_CLIENT_SECRET,
      category: ["Sloyd", "Credentials", "Client Secret"],
      name: "Client Secret",
      tooltip:
        "Shown only once when you generate the key. Paste it here: it is sent to the " +
        "ComfyUI backend, written to sloyd_config.json, and this field is then cleared. " +
        "It never enters a workflow.",
      type: "text",
      attrs: { type: "password" },
      defaultValue: "",
      onChange: async () => {
        await trySave();
      },
    },
  ],

  async setup() {
    const status = await refreshStatus();
    ready = true; // from here on, onChange means the user typed something
    if (status?.configured) {
      console.log(`[Sloyd] Credentials active from ${status.source} (${status.client_id}).`);
    } else {
      console.log(
        `[Sloyd] No credentials yet. Get a key at ${DASHBOARD_URL} then set them in ` +
          "Settings -> Sloyd -> Credentials (or via SLOYD_CLIENT_ID / SLOYD_CLIENT_SECRET)."
      );
    }
  },
});

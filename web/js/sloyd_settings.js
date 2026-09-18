/**
 * Sloyd credential setup in ComfyUI's Settings panel (Settings -> Sloyd).
 *
 * Onboarding + storage in one place:
 *   - a link to api-dashboard.sloyd.ai to generate a key and buy credits
 *   - Client ID and Client Secret fields
 *   - a read-only status line showing whether credentials are active
 *
 * The secret is POSTed to the Python backend, written to sloyd_config.json, and the
 * field is then cleared. It is never kept in frontend-persisted settings, never put
 * on a node, and never returned by the status route, so it cannot leak through a
 * shared workflow or a generated file's metadata.
 *
 * Everything is defensive: if a future frontend changes the settings API, the
 * extension logs and gives up rather than blocking node loading. Users can always
 * fall back to the SLOYD_CLIENT_ID / SLOYD_CLIENT_SECRET env vars or editing
 * sloyd_config.json directly.
 */

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const DASHBOARD_URL = "https://api-dashboard.sloyd.ai/";

const ID_HELP = "Sloyd.Setup";
const ID_CLIENT_ID = "Sloyd.ClientId";
const ID_CLIENT_SECRET = "Sloyd.ClientSecret";
const ID_STATUS = "Sloyd.Status";

let pendingClientId = "";

function toast(severity, summary, detail) {
  try {
    app.extensionManager?.toast?.add({ severity, summary, detail, life: 6000 });
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

function refreshStatusLine(status) {
  if (!status) return;
  let line;
  if (status.configured) {
    const src =
      status.source === "environment"
        ? "environment variables"
        : status.source === "default"
          ? "config file"
          : status.source;
    line = `Active (${status.client_id} via ${src})`;
  } else {
    line = "Not configured - paste your Client ID and Secret below.";
  }
  setSetting(ID_STATUS, line);
}

/** Persist once both halves are present, then clear the secret field. */
async function trySave() {
  const clientId = (pendingClientId || getSetting(ID_CLIENT_ID) || "").trim();
  const secret = getSetting(ID_CLIENT_SECRET);
  if (!clientId || !secret) return; // Sloyd needs the pair on every request.

  try {
    const status = await saveCredentials(clientId, secret);
    setSetting(ID_CLIENT_SECRET, ""); // never keep the secret client-side
    refreshStatusLine(status);
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
      id: ID_HELP,
      category: ["Sloyd", "Setup", "Dashboard"],
      name: "Get an API key & buy credits",
      tooltip:
        "Opens the Sloyd API Dashboard. Sign in, open API Keys, set up billing " +
        "(prepaid credits), then Generate Key. Copy the Client Secret - it is shown only once.",
      type: "url",
      defaultValue: DASHBOARD_URL,
    },
    {
      id: ID_STATUS,
      category: ["Sloyd", "Setup", "Status"],
      name: "Credential status",
      tooltip: "Whether Sloyd credentials are currently active, and where they came from.",
      type: "text",
      defaultValue: "Checking...",
      attrs: { readonly: true, disabled: true },
    },
    {
      id: ID_CLIENT_ID,
      category: ["Sloyd", "Credentials", "Client ID"],
      name: "Client ID",
      tooltip:
        "The sok_live_... value from the Sloyd API Dashboard (API Keys). Safe to store; not the secret.",
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
    const status = await readStatus();
    refreshStatusLine(status);
    if (status?.configured) {
      console.log(`[Sloyd] Credentials active from ${status.source} (${status.client_id}).`);
    } else {
      console.log(
        "[Sloyd] No credentials yet. Settings -> Sloyd: open the dashboard link to get a key, " +
          "then paste Client ID + Secret. (Or set SLOYD_CLIENT_ID / SLOYD_CLIENT_SECRET.)"
      );
    }
  },
});

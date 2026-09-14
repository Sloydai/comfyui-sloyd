/**
 * Adds the Sloyd credential fields to ComfyUI's Settings panel.
 *
 * The secret is POSTed to the Python backend, which writes it to sloyd_config.json,
 * and the field is then cleared. It is deliberately never kept in the frontend's
 * persisted settings, never placed on a node widget, and never returned by the
 * status route -- so it cannot ride along in a shared workflow or in the metadata
 * of a generated file.
 *
 * Everything here is wrapped defensively: if a future frontend release changes the
 * settings API, the extension logs and gives up rather than breaking node loading.
 * Credentials can always be supplied via SLOYD_CLIENT_ID / SLOYD_CLIENT_SECRET or
 * by editing sloyd_config.json directly.
 */

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const SETTINGS_CATEGORY = ["Sloyd", "Credentials"];
const ID_CLIENT_ID = "Sloyd.ClientId";
const ID_CLIENT_SECRET = "Sloyd.ClientSecret";

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

/** Clear the secret field so it is not persisted client-side. */
function clearSecretSetting() {
  try {
    app.ui.settings.setSettingValue(ID_CLIENT_SECRET, "");
  } catch (err) {
    console.warn("[Sloyd] Could not clear the secret field:", err);
  }
}

async function trySave() {
  const clientId = (pendingClientId || "").trim();
  let secret = "";
  try {
    secret = (app.ui.settings.getSettingValue(ID_CLIENT_SECRET) || "").trim();
  } catch (err) {
    return;
  }

  // Wait until both halves are present. Sloyd needs the pair on every request.
  if (!clientId || !secret) return;

  try {
    const status = await saveCredentials(clientId, secret);
    clearSecretSetting();
    toast(
      "success",
      "Sloyd credentials saved",
      `Stored for ${status.client_id || clientId}. The secret is kept on the server, not in your workflows.`
    );
  } catch (err) {
    toast("error", "Sloyd credentials not saved", String(err.message || err));
  }
}

app.registerExtension({
  name: "sloyd.credentials",

  settings: [
    {
      id: ID_CLIENT_ID,
      category: [...SETTINGS_CATEGORY, "Client ID"],
      name: "Client ID",
      tooltip:
        "The sok_live_... value from the Sloyd API Dashboard (API Keys). Safe to store; it is not the secret.",
      type: "text",
      defaultValue: "",
      onChange: (value) => {
        pendingClientId = value || "";
        void trySave();
      },
    },
    {
      id: ID_CLIENT_SECRET,
      category: [...SETTINGS_CATEGORY, "Client Secret"],
      name: "Client Secret",
      tooltip:
        "Shown only once when you generate the key. Paste it here; it is sent to the ComfyUI backend, written to sloyd_config.json, and this field is then cleared. It never enters a workflow.",
      type: "text",
      attrs: { type: "password" },
      defaultValue: "",
      onChange: () => {
        void trySave();
      },
    },
  ],

  async setup() {
    const status = await readStatus();
    if (!status) return;

    if (status.configured) {
      console.log(
        `[Sloyd] Credentials active from ${status.source} (${status.client_id}).`
      );
      // Reflect the stored id so the panel is not misleadingly blank, but only
      // when the frontend has nothing of its own.
      try {
        const current = (app.ui.settings.getSettingValue(ID_CLIENT_ID) || "").trim();
        if (!current && status.source !== "environment") {
          pendingClientId = "";
        }
      } catch (err) {
        /* settings not ready */
      }
    } else {
      console.log(
        "[Sloyd] No credentials configured. Settings -> Sloyd -> Credentials, " +
          "or set SLOYD_CLIENT_ID and SLOYD_CLIENT_SECRET."
      );
    }
  },
});

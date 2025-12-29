// Job-Track Extension Popup Script

const API_BASE = "http://localhost:8787";

let profiles = [];
let selectedProfileId = null;

/**
 * Show a status message.
 * @param {string} message - Message to display.
 * @param {'error'|'success'|'info'} type - Message type.
 */
function showStatus(message, type = "info") {
  const container = document.getElementById("status-container");
  container.innerHTML = `<div class="status status-${type}">${message}</div>`;

  if (type !== "error") {
    setTimeout(() => {
      container.innerHTML = "";
    }, 3000);
  }
}

/**
 * Check if the local API server is running.
 * @returns {Promise<boolean>}
 */
async function checkServerConnection() {
  const statusEl = document.getElementById("server-status");
  try {
    const response = await fetch(`${API_BASE}/api/profiles`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
    if (response.ok) {
      statusEl.textContent = "✓ Connected to Job-Track API";
      statusEl.className = "server-status connected";
      return true;
    }
  } catch (e) {
    // Connection failed
  }
  statusEl.textContent = "✗ Cannot connect to Job-Track API (is it running?)";
  statusEl.className = "server-status disconnected";
  return false;
}

/**
 * Fetch profiles from the local API.
 */
async function fetchProfiles() {
  const container = document.getElementById("profiles-container");

  try {
    const response = await fetch(`${API_BASE}/api/profiles`);
    if (!response.ok) {
      throw new Error("Failed to fetch profiles");
    }

    const data = await response.json();
    profiles = data.profiles || [];

    if (profiles.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          No profiles found.<br>
          Add one in the Job-Track TUI.
        </div>
      `;
      return;
    }

    // Load previously selected profile from storage
    const stored = await chrome.storage.local.get("selectedProfileId");
    if (stored.selectedProfileId) {
      selectedProfileId = stored.selectedProfileId;
    }

    renderProfiles();
  } catch (e) {
    container.innerHTML = `
      <div class="empty-state">
        Failed to load profiles.<br>
        Make sure the Job-Track API is running.
      </div>
    `;
  }
}

/**
 * Render the profiles list.
 */
function renderProfiles() {
  const container = document.getElementById("profiles-container");
  const autofillBtn = document.getElementById("autofill-btn");

  container.innerHTML = profiles
    .map((profile) => {
      const isSelected = profile.id === selectedProfileId;
      const resumeVersions = profile.resume_versions || [];
      const latestResume =
        resumeVersions.length > 0
          ? `Resume v${resumeVersions.length}`
          : "No resume uploaded";

      return `
      <div class="profile-card ${isSelected ? "selected" : ""}" data-id="${
        profile.id
      }">
        <div class="profile-title">${escapeHtml(profile.profile_name)}</div>
        <div class="profile-name">${escapeHtml(
          profile.first_name + " " + profile.last_name
        )}</div>
        <div class="profile-email">${escapeHtml(profile.email)}</div>
        <div class="profile-resume">📄 ${latestResume}</div>
      </div>
    `;
    })
    .join("");

  // Add click handlers
  container.querySelectorAll(".profile-card").forEach((card) => {
    card.addEventListener("click", () => selectProfile(card.dataset.id));
  });

  // Enable/disable autofill button
  autofillBtn.disabled = !selectedProfileId;
}

/**
 * Select a profile.
 * @param {string} profileId - Profile ID to select.
 */
async function selectProfile(profileId) {
  selectedProfileId = profileId;
  await chrome.storage.local.set({ selectedProfileId });
  renderProfiles();
}

/**
 * Escape HTML special characters.
 * @param {string} text - Text to escape.
 * @returns {string}
 */
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Send autofill request to content script.
 */
async function autofillForm() {
  if (!selectedProfileId) {
    showStatus("Please select a profile first", "error");
    return;
  }

  const profile = profiles.find((p) => p.id === selectedProfileId);
  if (!profile) {
    showStatus("Profile not found", "error");
    return;
  }

  try {
    // Get the current active tab
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });

    // Send message to content script
    const response = await chrome.tabs.sendMessage(tab.id, {
      action: "autofill",
      profile: profile,
    });

    if (response && response.success) {
      showStatus(`Filled ${response.filledCount} fields!`, "success");
    } else {
      showStatus(response?.error || "No form fields found", "info");
    }
  } catch (e) {
    showStatus("Could not access this page", "error");
  }
}

// Initialize popup
document.addEventListener("DOMContentLoaded", async () => {
  // Check connection and fetch profiles
  await checkServerConnection();
  await fetchProfiles();

  // Set up button handlers
  document
    .getElementById("autofill-btn")
    .addEventListener("click", autofillForm);
  document.getElementById("refresh-btn").addEventListener("click", async () => {
    showStatus("Refreshing...", "info");
    await fetchProfiles();
  });
});

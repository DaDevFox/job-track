const API_BASE = "http://127.0.0.1:8787/api";
let profiles = [];
let selectedProfileId = null;

const profilesContainer = document.querySelector("#profiles");
const statusEl = document.querySelector("#status");
const fillButton = document.querySelector("#fill");
const resumeInput = document.querySelector("#resume");

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.style.color = isError ? "#dc2626" : "#1f2937";
}

function renderProfiles() {
  profilesContainer.innerHTML = "";
  if (!profiles.length) {
    profilesContainer.textContent =
      "No profiles yet. Create one in the TUI or via API.";
    fillButton.disabled = true;
    return;
  }
  profiles.forEach((profile) => {
    const wrapper = document.createElement("label");
    wrapper.className = "profile-option";
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "profile";
    input.value = profile.id;
    if (profile.id === selectedProfileId) {
      input.checked = true;
    }
    input.addEventListener("change", () => {
      selectedProfileId = profile.id;
      chrome.storage.local.set({ selectedProfileId });
      fillButton.disabled = false;
    });
    const content = document.createElement("div");
    content.innerHTML = `<strong>${profile.label}</strong><br/><small>${profile.full_name} · ${profile.email}</small>`;
    wrapper.appendChild(input);
    wrapper.appendChild(content);
    profilesContainer.appendChild(wrapper);
  });
  fillButton.disabled = !selectedProfileId;
}

async function loadProfiles() {
  try {
    const response = await fetch(`${API_BASE}/profiles`);
    profiles = await response.json();
    const stored = await chrome.storage.local.get("selectedProfileId");
    selectedProfileId =
      stored.selectedProfileId || (profiles[0] && profiles[0].id);
    renderProfiles();
  } catch (error) {
    setStatus(`Failed to load profiles: ${error}`);
  }
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function fillForm() {
  if (!selectedProfileId) {
    setStatus("Select a profile first.", true);
    return;
  }
  const profile = profiles.find((p) => p.id === selectedProfileId);
  if (!profile) {
    setStatus("Profile not found.", true);
    return;
  }
  const tab = await getActiveTab();
  await chrome.tabs.sendMessage(tab.id, {
    type: "JOBTRACK_FILL",
    profile,
  });
  await fetch(`${API_BASE}/jobs/profile-selection`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ apply_url: tab.url, profile_id: profile.id }),
  });
  setStatus(`Filled form with ${profile.label}`);
}

async function uploadResume(event) {
  const file = event.target.files?.[0];
  if (!file || !selectedProfileId) {
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  try {
    const response = await fetch(
      `${API_BASE}/profiles/${selectedProfileId}/resume`,
      {
        method: "POST",
        body: formData,
      }
    );
    if (!response.ok) {
      throw new Error(response.statusText);
    }
    setStatus("Resume uploaded.");
  } catch (error) {
    setStatus(`Upload failed: ${error}`, true);
  } finally {
    resumeInput.value = "";
  }
}

fillButton.addEventListener("click", () => fillForm());
resumeInput.addEventListener("change", uploadResume);

loadProfiles();

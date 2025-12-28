const API_BASE = "http://127.0.0.1:8787/api";

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "JOBTRACK_FORM_SUBMITTED") {
    fetch(`${API_BASE}/jobs/profile-selection`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        apply_url: message.url,
        profile_id: message.profileId ?? null,
      }),
    }).catch((error) => console.error("JobTrack log failed", error));
  }
});

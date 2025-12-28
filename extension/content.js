let lastProfileId = null;

const FIELD_KEYS = {
  full_name: ["full-name", "fullname", "name", "applicant-name"],
  email: ["email", "e-mail", "applicant-email"],
  phone: ["phone", "tel", "telephone"],
  location: ["location", "city", "address"],
  website: ["website", "portfolio", "linkedin", "github"],
};

function matches(element, key) {
  if (!key) return false;
  const haystack = [
    element.name,
    element.id,
    element.getAttribute("placeholder"),
    element.getAttribute("aria-label"),
    element.closest("label")?.textContent,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(key);
}

function fillValue(element, value) {
  if (!value) return false;
  element.focus();
  element.value = value;
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

function fillProfile(profile) {
  const inputs = Array.from(document.querySelectorAll("input, textarea"));
  const payload = {
    full_name: profile.full_name,
    email: profile.email,
    phone: profile.phone,
    location: profile.location,
    website: profile.website,
    ...profile.autofill_data,
  };
  for (const [field, value] of Object.entries(payload)) {
    if (!value) continue;
    const keys = FIELD_KEYS[field] || [field];
    for (const input of inputs) {
      if (keys.some((key) => matches(input, key))) {
        if (fillValue(input, value)) break;
      }
    }
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "JOBTRACK_FILL" && message.profile) {
    fillProfile(message.profile);
    lastProfileId = message.profile.id;
    sendResponse({ status: "filled" });
  }
});

document.addEventListener(
  "submit",
  () => {
    if (lastProfileId) {
      chrome.runtime.sendMessage({
        type: "JOBTRACK_FORM_SUBMITTED",
        url: window.location.href,
        profileId: lastProfileId,
      });
    }
  },
  true
);

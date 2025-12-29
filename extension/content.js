// Job-Track Content Script
// Handles autofilling form fields on job application pages

/**
 * Check if we're on a Workday site.
 * @returns {boolean}
 */
function isWorkdaySite() {
  return (
    window.location.hostname.includes("myworkday") ||
    window.location.hostname.includes("workday") ||
    window.location.hostname.includes("wd5") ||
    window.location.hostname.includes("wd3") ||
    window.location.hostname.includes("wd1") ||
    document.querySelector("[data-automation-id]") !== null
  );
}

/**
 * Common field patterns for job applications.
 */
const FIELD_PATTERNS = {
  name: [
    /full.?name/i,
    /^name$/i,
    /your.?name/i,
    /applicant.?name/i,
    /candidate.?name/i,
    /legalName--firstName/i,
  ],
  firstName: [
    /first.?name/i,
    /given.?name/i,
    /^fname$/i,
    /legalName--firstName/i,
    /firstName/i,
  ],
  lastName: [
    /last.?name/i,
    /surname/i,
    /family.?name/i,
    /^lname$/i,
    /legalName--lastName/i,
    /lastName/i,
  ],
  email: [/e?.?mail/i, /email.?address/i, /emailAddress/i],
  phone: [
    /phone/i,
    /mobile/i,
    /telephone/i,
    /cell/i,
    /contact.?number/i,
    /phoneNumber/i,
    /phone-number/i,
    /deviceType-/i,
  ],
  linkedin: [/linkedin/i, /linked.?in/i],
  github: [/github/i, /git.?hub/i],
  portfolio: [/portfolio/i, /website/i, /personal.?site/i, /url/i],
  address: [
    /address.?line.?1/i,
    /street.?address/i,
    /address--addressLine1/i,
    /addressSection_addressLine1/i,
  ],
  city: [/city/i, /address--city/i, /addressSection_city/i],
  state: [
    /state/i,
    /region/i,
    /province/i,
    /address--region/i,
    /addressSection_state/i,
  ],
  postalCode: [
    /zip/i,
    /postal/i,
    /address--postalCode/i,
    /addressSection_postalCode/i,
  ],
};

/**
 * Workday-specific field mappings using data-automation-id attributes.
 * Workday uses different delimiters across versions:
 *   - Older: `Section_` (e.g., legalNameSection_firstName)
 *   - Newer: `--` (e.g., legalName--firstName)
 *   - Some: simple names (e.g., firstName)
 */
const WORKDAY_AUTOMATION_IDS = {
  firstName: [
    // -- delimiter (newer)
    "legalName--firstName",
    "name--firstName",
    // Section_ delimiter (older)
    "legalNameSection_firstName",
    "nameSection_firstName",
    // Simple/other patterns
    "firstName",
    "name-first",
    "first-name",
    "formField-firstName",
  ],
  lastName: [
    // -- delimiter (newer)
    "legalName--lastName",
    "name--lastName",
    // Section_ delimiter (older)
    "legalNameSection_lastName",
    "nameSection_lastName",
    // Simple/other patterns
    "lastName",
    "name-last",
    "last-name",
    "legalName-lastName",
    "formField-lastName",
  ],
  email: [
    "email",
    "emailAddress",
    "email-address",
    "contactInformation--email",
    "emailSection_email",
    "formField-email",
  ],
  phone: [
    // -- delimiter
    "phone--phoneNumber",
    "phone--number",
    "contactInformation--phone",
    // Section_ delimiter
    "phoneSection_phoneNumber",
    // Simple patterns
    "phone-number",
    "phoneNumber",
    "phone",
    "formField-phone",
  ],
  address: [
    // -- delimiter
    "address--addressLine1",
    "addressSection--addressLine1",
    // Section_ delimiter
    "addressSection_addressLine1",
    // Simple patterns
    "address-line-1",
    "addressLine1",
    "streetAddress",
    "formField-address",
  ],
  city: [
    // -- delimiter
    "address--city",
    "addressSection--city",
    // Section_ delimiter
    "addressSection_city",
    // Simple patterns
    "city",
    "formField-city",
  ],
  state: [
    // -- delimiter
    "address--region",
    "address--state",
    "addressSection--state",
    // Section_ delimiter
    "addressSection_region",
    "addressSection_state",
    // Simple patterns
    "state",
    "region",
    "formField-state",
  ],
  postalCode: [
    // -- delimiter
    "address--postalCode",
    "address--zipCode",
    "addressSection--postalCode",
    // Section_ delimiter
    "addressSection_postalCode",
    "addressSection_zipCode",
    // Simple patterns
    "postalCode",
    "zipCode",
    "zip",
    "formField-postalCode",
  ],
  country: [
    // -- delimiter
    "address--countryRegion",
    "address--country",
    "addressSection--country",
    // Section_ delimiter
    "addressSection_countryRegion",
    "addressSection_country",
    // Simple patterns
    "country",
    "countryRegion",
    "formField-country",
  ],
  linkedin: [
    "linkedinQuestion",
    "linkedin",
    "linkedIn",
    "linkedin-url",
    "socialLinks--linkedin",
    "formField-linkedin",
  ],
};

/**
 * Check if an element matches any of the given patterns.
 * @param {HTMLElement} element - Element to check.
 * @param {RegExp[]} patterns - Patterns to match against.
 * @returns {boolean}
 */
function matchesPatterns(element, patterns) {
  const checkText = [
    element.name || "",
    element.id || "",
    element.placeholder || "",
    element.getAttribute("aria-label") || "",
    element.getAttribute("data-testid") || "",
    element.getAttribute("data-automation-id") || "",
    element.getAttribute("data-uxi-widget-type") || "",
    element.getAttribute("autocomplete") || "",
  ].join(" ");

  // Also check associated label
  let labelText = "";
  if (element.id) {
    const label = document.querySelector(`label[for="${element.id}"]`);
    if (label) {
      labelText = label.textContent || "";
    }
  }

  // Check parent elements for Workday's nested structure
  let parentText = "";
  let parent = element.parentElement;
  for (let i = 0; i < 5 && parent; i++) {
    parentText += " " + (parent.getAttribute("data-automation-id") || "");
    parentText += " " + (parent.getAttribute("aria-label") || "");
    parent = parent.parentElement;
  }

  const fullText = checkText + " " + labelText + " " + parentText;
  return patterns.some((pattern) => pattern.test(fullText));
}

/**
 * Find all fillable input fields on the page.
 * @returns {HTMLInputElement[]}
 */
function findInputFields() {
  // Standard inputs
  const standardInputs = Array.from(
    document.querySelectorAll(
      'input[type="text"], input[type="email"], input[type="tel"], input:not([type]), textarea'
    )
  );

  // Workday-specific: find inputs with data-automation-id
  const workdayInputs = Array.from(
    document.querySelectorAll(
      "[data-automation-id] input, [data-automation-id] textarea, input[data-automation-id], textarea[data-automation-id]"
    )
  );

  // Workday also uses contenteditable divs and custom input wrappers
  const workdayCustomInputs = Array.from(
    document.querySelectorAll(
      '[data-automation-id][contenteditable="true"], [role="textbox"], [data-uxi-widget-type="selectinput"] input'
    )
  );

  // Combine and deduplicate
  const allInputs = [
    ...new Set([...standardInputs, ...workdayInputs, ...workdayCustomInputs]),
  ];

  return allInputs.filter((el) => {
    // Filter out hidden or disabled fields
    const style = window.getComputedStyle(el);
    return (
      style.display !== "none" &&
      style.visibility !== "hidden" &&
      !el.disabled &&
      !el.readOnly &&
      el.offsetParent !== null // Check if element is actually visible
    );
  });
}

/**
 * Find Workday fields by their specific automation IDs.
 * @param {string[]} automationIds - List of automation IDs to look for.
 * @returns {HTMLElement|null}
 */
function findWorkdayField(automationIds) {
  for (const id of automationIds) {
    // Direct match on data-automation-id
    let element = document.querySelector(`[data-automation-id="${id}"] input`);
    if (element && isVisible(element)) return element;

    element = document.querySelector(`[data-automation-id="${id}"] textarea`);
    if (element && isVisible(element)) return element;

    element = document.querySelector(`input[data-automation-id="${id}"]`);
    if (element && isVisible(element)) return element;

    // Look for input inside containers with matching automation-id
    element = document.querySelector(`[data-automation-id*="${id}"] input`);
    if (element && isVisible(element)) return element;
  }
  return null;
}

/**
 * Check if an element is visible.
 * @param {HTMLElement} el - Element to check.
 * @returns {boolean}
 */
function isVisible(el) {
  if (!el) return false;
  const style = window.getComputedStyle(el);
  return (
    style.display !== "none" &&
    style.visibility !== "hidden" &&
    !el.disabled &&
    el.offsetParent !== null
  );
}

/**
 * Set a value on an input field, triggering appropriate events.
 * Works with both standard inputs and React/Workday controlled components.
 * @param {HTMLInputElement} element - Element to fill.
 * @param {string} value - Value to set.
 */
function fillField(element, value) {
  if (!value || !element) return false;

  try {
    // Focus the element
    element.focus();

    // For React apps (including Workday), we need to use the native value setter
    // to bypass React's synthetic event system
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value"
    )?.set;
    const nativeTextAreaValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLTextAreaElement.prototype,
      "value"
    )?.set;

    if (element.tagName === "INPUT" && nativeInputValueSetter) {
      nativeInputValueSetter.call(element, value);
    } else if (element.tagName === "TEXTAREA" && nativeTextAreaValueSetter) {
      nativeTextAreaValueSetter.call(element, value);
    } else {
      element.value = value;
    }

    // Trigger a comprehensive set of events to ensure React/Workday picks up the change
    // Input event - primary event for React
    const inputEvent = new Event("input", { bubbles: true, cancelable: true });
    element.dispatchEvent(inputEvent);

    // Change event
    const changeEvent = new Event("change", {
      bubbles: true,
      cancelable: true,
    });
    element.dispatchEvent(changeEvent);

    // Keyboard events for apps that listen to keystrokes
    element.dispatchEvent(
      new KeyboardEvent("keydown", { bubbles: true, key: "a" })
    );
    element.dispatchEvent(
      new KeyboardEvent("keypress", { bubbles: true, key: "a" })
    );
    element.dispatchEvent(
      new KeyboardEvent("keyup", { bubbles: true, key: "a" })
    );

    // Some frameworks need compositionend event
    element.dispatchEvent(
      new CompositionEvent("compositionend", { bubbles: true, data: value })
    );

    // Blur to trigger validation
    element.blur();

    // Focus again briefly for Workday's validation
    setTimeout(() => {
      element.focus();
      element.blur();
    }, 50);

    return true;
  } catch (e) {
    console.error("Job-Track: Error filling field", e);
    return false;
  }
}

/**
 * Split a full name into first and last name.
 * @param {string} fullName - Full name to split.
 * @returns {{firstName: string, lastName: string}}
 */
function splitName(fullName) {
  const parts = (fullName || "").trim().split(/\s+/);
  if (parts.length === 0 || (parts.length === 1 && parts[0] === "")) {
    return { firstName: "", lastName: "" };
  }
  if (parts.length === 1) {
    return { firstName: parts[0], lastName: "" };
  }
  return {
    firstName: parts[0],
    lastName: parts.slice(1).join(" "),
  };
}

/**
 * Autofill Workday-specific form fields using automation IDs.
 * @param {Object} profile - Profile data.
 * @returns {{filledCount: number}}
 */
function autofillWorkday(profile) {
  let filledCount = 0;

  // Profile may have first_name/last_name separately or full_name
  const firstName =
    profile.first_name ||
    splitName(profile.full_name || profile.name).firstName;
  const lastName =
    profile.last_name || splitName(profile.full_name || profile.name).lastName;

  // Map profile fields to Workday automation IDs
  const fieldMappings = [
    { automationIds: WORKDAY_AUTOMATION_IDS.firstName, value: firstName },
    { automationIds: WORKDAY_AUTOMATION_IDS.lastName, value: lastName },
    { automationIds: WORKDAY_AUTOMATION_IDS.email, value: profile.email },
    { automationIds: WORKDAY_AUTOMATION_IDS.phone, value: profile.phone },
    {
      automationIds: WORKDAY_AUTOMATION_IDS.linkedin,
      value: profile.linkedin_url,
    },
    {
      automationIds: WORKDAY_AUTOMATION_IDS.address,
      value: profile.address_street || profile.address,
    },
    {
      automationIds: WORKDAY_AUTOMATION_IDS.city,
      value: profile.address_city || profile.city,
    },
    {
      automationIds: WORKDAY_AUTOMATION_IDS.state,
      value: profile.address_state || profile.state,
    },
    {
      automationIds: WORKDAY_AUTOMATION_IDS.postalCode,
      value: profile.address_zip || profile.postal_code,
    },
  ];

  for (const mapping of fieldMappings) {
    if (mapping.value) {
      const field = findWorkdayField(mapping.automationIds);
      if (field && fillField(field, mapping.value)) {
        filledCount++;
      }
    }
  }

  return { filledCount };
}

/**
 * Autofill form fields with profile data.
 * @param {Object} profile - Profile data.
 * @returns {{success: boolean, filledCount: number, error?: string}}
 */
function autofillForm(profile) {
  let filledCount = 0;

  // If on Workday, try Workday-specific filling first
  if (isWorkdaySite()) {
    console.log(
      "Job-Track: Detected Workday site, using Workday-specific autofill"
    );
    const workdayResult = autofillWorkday(profile);
    filledCount += workdayResult.filledCount;
  }

  // Also try standard field detection for any fields we might have missed
  const fields = findInputFields();

  if (fields.length === 0 && filledCount === 0) {
    return {
      success: false,
      filledCount: 0,
      error: "No form fields found on this page",
    };
  }

  // Profile may have first_name/last_name separately or full_name
  const fullName =
    profile.full_name ||
    profile.name ||
    `${profile.first_name || ""} ${profile.last_name || ""}`.trim();
  const nameParts = {
    firstName: profile.first_name || splitName(fullName).firstName,
    lastName: profile.last_name || splitName(fullName).lastName,
  };

  // Track which fields we've already filled to avoid duplicates
  const filledElements = new Set();

  fields.forEach((field) => {
    if (filledElements.has(field)) return;
    if (field.value && field.value.trim()) return; // Skip already-filled fields

    let filled = false;

    // Check each field type
    if (matchesPatterns(field, FIELD_PATTERNS.name)) {
      filled = fillField(field, fullName);
    } else if (matchesPatterns(field, FIELD_PATTERNS.firstName)) {
      filled = fillField(field, nameParts.firstName);
    } else if (matchesPatterns(field, FIELD_PATTERNS.lastName)) {
      filled = fillField(field, nameParts.lastName);
    } else if (matchesPatterns(field, FIELD_PATTERNS.email)) {
      filled = fillField(field, profile.email);
    } else if (matchesPatterns(field, FIELD_PATTERNS.phone)) {
      filled = fillField(field, profile.phone);
    } else if (matchesPatterns(field, FIELD_PATTERNS.linkedin)) {
      filled = fillField(field, profile.linkedin_url);
    } else if (matchesPatterns(field, FIELD_PATTERNS.github)) {
      filled = fillField(field, profile.github_url);
    } else if (matchesPatterns(field, FIELD_PATTERNS.portfolio)) {
      filled = fillField(field, profile.portfolio_url);
    } else if (matchesPatterns(field, FIELD_PATTERNS.address)) {
      filled = fillField(field, profile.address_street || profile.address);
    } else if (matchesPatterns(field, FIELD_PATTERNS.city)) {
      filled = fillField(field, profile.address_city || profile.city);
    } else if (matchesPatterns(field, FIELD_PATTERNS.state)) {
      filled = fillField(field, profile.address_state || profile.state);
    } else if (matchesPatterns(field, FIELD_PATTERNS.postalCode)) {
      filled = fillField(field, profile.address_zip || profile.postal_code);
    }

    if (filled) {
      filledCount++;
      filledElements.add(field);
    }
  });

  return {
    success: filledCount > 0,
    filledCount,
  };
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "autofill" && message.profile) {
    // For Workday and other dynamic sites, wait a bit and retry if needed
    const attemptAutofill = (attemptsLeft) => {
      const result = autofillForm(message.profile);

      // If we found few fields and are on Workday, retry after a delay
      // (Workday may still be loading form sections)
      if (!result.success && attemptsLeft > 0 && isWorkdaySite()) {
        setTimeout(() => attemptAutofill(attemptsLeft - 1), 500);
      } else {
        sendResponse(result);
      }
    };

    // Start with 3 attempts for Workday sites
    attemptAutofill(isWorkdaySite() ? 3 : 1);
    return true; // Keep the message channel open for async response
  }
  return true;
});

// For Workday: observe DOM changes and prepare for dynamic form loading
if (isWorkdaySite()) {
  console.log(
    "Job-Track: Workday site detected, monitoring for dynamic form changes"
  );
}

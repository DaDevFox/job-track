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
    /^phone$/i,
    /phoneNumber/i,
    /phone-number/i,
    /phone--phoneNumber/i,
    /phone--number/i,
    /mobile/i,
    /telephone/i,
    /cell/i,
    /contact.?number/i,
  ],
  // Patterns to EXCLUDE from phone number filling (phone extension fields)
  phoneExtension: [
    /extension/i,
    /ext\.?$/i,
    /phone.*ext/i,
    /phoneExtension/i,
    /phone--extension/i,
  ],
  phoneDeviceType: [
    /device.?type/i,
    /phone.?type/i,
    /phoneDeviceType/i,
    /phone--deviceType/i,
    /deviceType/i,
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
    "address--countryRegion",
    "addressSection--state",
    "addressSection_countryRegion",
    "addressSection--region",
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
    "address--country",
    "addressSection--country",
    // Section_ delimiter
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
  phoneDeviceType: [
    // -- delimiter
    "phone--deviceType",
    "phone--type",
    "phoneNumber--phoneType",
    // Section_ delimiter
    "phoneSection_deviceType",
    // Simple patterns
    "phoneDeviceType",
    "deviceType",
    "phone-device-type",
  ],
  // Phone extension - we want to find but NOT fill these
  phoneExtension: [
    "phone--extension",
    "phoneSection_extension",
    "phoneExtension",
    "extension",
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
    // Focus the element first
    element.focus();

    // Clear any existing value first
    element.value = "";

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

    // Set the value using native setter
    if (element.tagName === "INPUT" && nativeInputValueSetter) {
      nativeInputValueSetter.call(element, value);
    } else if (element.tagName === "TEXTAREA" && nativeTextAreaValueSetter) {
      nativeTextAreaValueSetter.call(element, value);
    } else {
      element.value = value;
    }

    // Create and dispatch InputEvent - this is what React listens for
    // The key is using InputEvent (not Event) with inputType specified
    const inputEvent = new InputEvent("input", {
      bubbles: true,
      cancelable: true,
      inputType: "insertText",
      data: value,
    });
    element.dispatchEvent(inputEvent);

    // Also dispatch a change event
    const changeEvent = new Event("change", {
      bubbles: true,
      cancelable: true,
    });
    element.dispatchEvent(changeEvent);

    // Dispatch blur event to trigger validation
    element.dispatchEvent(new FocusEvent("blur", { bubbles: true }));

    // For Workday specifically, we need to trigger React's internal handlers
    // by simulating the full focus/input/blur cycle after a small delay
    setTimeout(() => {
      // Re-focus and simulate user interaction
      element.focus();

      // Dispatch focusin event (some React versions use this)
      element.dispatchEvent(new FocusEvent("focusin", { bubbles: true }));

      // Re-dispatch input event to ensure React state updates
      const inputEvent2 = new InputEvent("input", {
        bubbles: true,
        cancelable: true,
        inputType: "insertText",
        data: value,
      });
      element.dispatchEvent(inputEvent2);

      // Trigger blur and focusout for validation
      element.dispatchEvent(new FocusEvent("blur", { bubbles: true }));
      element.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
    }, 100);

    return true;
  } catch (e) {
    console.error("Job-Track: Error filling field", e);
    return false;
  }
}

/**
 * Simulate typing into a field character by character.
 * Use this for fields that don't respond to bulk value setting.
 * @param {HTMLInputElement} element - Element to fill.
 * @param {string} value - Value to type.
 */
function simulateTyping(element, value) {
  if (!value || !element) return false;

  try {
    element.focus();
    element.value = "";

    for (let i = 0; i < value.length; i++) {
      const char = value[i];

      // Dispatch keydown
      element.dispatchEvent(
        new KeyboardEvent("keydown", {
          bubbles: true,
          cancelable: true,
          key: char,
          code: `Key${char.toUpperCase()}`,
        })
      );

      // Append character to value
      element.value += char;

      // Dispatch input event for this character
      element.dispatchEvent(
        new InputEvent("input", {
          bubbles: true,
          cancelable: true,
          inputType: "insertText",
          data: char,
        })
      );

      // Dispatch keyup
      element.dispatchEvent(
        new KeyboardEvent("keyup", {
          bubbles: true,
          cancelable: true,
          key: char,
          code: `Key${char.toUpperCase()}`,
        })
      );
    }

    // Final change and blur events
    element.dispatchEvent(new Event("change", { bubbles: true }));
    element.dispatchEvent(new FocusEvent("blur", { bubbles: true }));
    element.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));

    return true;
  } catch (e) {
    console.error("Job-Track: Error simulating typing", e);
    return false;
  }
}

/**
 * US State abbreviation to full name mapping (two-way).
 */
const US_STATES = {
  AL: "Alabama",
  AK: "Alaska",
  AZ: "Arizona",
  AR: "Arkansas",
  CA: "California",
  CO: "Colorado",
  CT: "Connecticut",
  DE: "Delaware",
  FL: "Florida",
  GA: "Georgia",
  HI: "Hawaii",
  ID: "Idaho",
  IL: "Illinois",
  IN: "Indiana",
  IA: "Iowa",
  KS: "Kansas",
  KY: "Kentucky",
  LA: "Louisiana",
  ME: "Maine",
  MD: "Maryland",
  MA: "Massachusetts",
  MI: "Michigan",
  MN: "Minnesota",
  MS: "Mississippi",
  MO: "Missouri",
  MT: "Montana",
  NE: "Nebraska",
  NV: "Nevada",
  NH: "New Hampshire",
  NJ: "New Jersey",
  NM: "New Mexico",
  NY: "New York",
  NC: "North Carolina",
  ND: "North Dakota",
  OH: "Ohio",
  OK: "Oklahoma",
  OR: "Oregon",
  PA: "Pennsylvania",
  RI: "Rhode Island",
  SC: "South Carolina",
  SD: "South Dakota",
  TN: "Tennessee",
  TX: "Texas",
  UT: "Utah",
  VT: "Vermont",
  VA: "Virginia",
  WA: "Washington",
  WV: "West Virginia",
  WI: "Wisconsin",
  WY: "Wyoming",
  DC: "District of Columbia",
  // Territories
  PR: "Puerto Rico",
  VI: "Virgin Islands",
  GU: "Guam",
  AS: "American Samoa",
  MP: "Northern Mariana Islands",
};

// Create reverse mapping (full name -> abbreviation)
const US_STATES_REVERSE = Object.fromEntries(
  Object.entries(US_STATES).map(([abbr, name]) => [name.toLowerCase(), abbr])
);

/**
 * Get all possible variations of a state name for matching.
 * @param {string} state - State name or abbreviation.
 * @returns {string[]} - Array of possible values to match against.
 */
function getStateVariations(state) {
  if (!state) return [];
  const trimmed = state.trim();
  const upper = trimmed.toUpperCase();
  const lower = trimmed.toLowerCase();

  const variations = [trimmed, upper, lower];

  // If it's an abbreviation, add the full name
  if (US_STATES[upper]) {
    variations.push(US_STATES[upper]);
    variations.push(US_STATES[upper].toLowerCase());
  }

  // If it's a full name, add the abbreviation
  if (US_STATES_REVERSE[lower]) {
    variations.push(US_STATES_REVERSE[lower]);
    variations.push(US_STATES_REVERSE[lower].toLowerCase());
  }

  return [...new Set(variations)];
}

/**
 * Common device type variations for matching.
 */
const DEVICE_TYPE_VARIATIONS = {
  mobile: ["mobile", "cell", "cellular", "mobile phone", "cell phone"],
  home: ["home", "home phone", "landline", "residence"],
  work: ["work", "work phone", "office", "business"],
};

/**
 * Get all possible variations of a device type for matching.
 * @param {string} deviceType - Device type value.
 * @returns {string[]} - Array of possible values to match against.
 */
function getDeviceTypeVariations(deviceType) {
  if (!deviceType) return [];
  const lower = deviceType.toLowerCase().trim();

  // Check if it matches any known type
  for (const [key, variations] of Object.entries(DEVICE_TYPE_VARIATIONS)) {
    if (variations.includes(lower) || key === lower) {
      return variations;
    }
  }

  // Return the original value in different cases
  return [deviceType.trim(), lower, deviceType.trim().toUpperCase()];
}

/**
 * Try to match a value against dropdown options with various strategies.
 * @param {Array} options - Array of option elements or {value, text} objects.
 * @param {string} value - Value to match.
 * @param {string} fieldType - Type of field ('state', 'deviceType', 'country', or 'default').
 * @returns {Object|null} - Matching option or null.
 */
function findDropdownMatch(options, value, fieldType = "default") {
  if (!value || !options.length) return null;

  const valueTrimmed = value.trim();
  const valueLower = valueTrimmed.toLowerCase();

  // Get variations based on field type
  let variations = [valueTrimmed, valueLower];
  if (fieldType === "state") {
    variations = getStateVariations(value);
  } else if (fieldType === "deviceType") {
    variations = getDeviceTypeVariations(value);
  }

  // Strategy 1: Exact match (case-insensitive, trimmed)
  for (const opt of options) {
    const optValue = (opt.value || "").trim().toLowerCase();
    const optText = (opt.text || opt.textContent || "").trim().toLowerCase();

    for (const v of variations) {
      const vLower = v.toLowerCase();
      if (optValue === vLower || optText === vLower) {
        return opt;
      }
    }
  }

  // Strategy 2: Option starts with or contains our value
  for (const opt of options) {
    const optText = (opt.text || opt.textContent || "").trim().toLowerCase();

    for (const v of variations) {
      const vLower = v.toLowerCase();
      if (optText.startsWith(vLower) || optText.includes(vLower)) {
        return opt;
      }
    }
  }

  // Strategy 3: Our value starts with or contains option text
  for (const opt of options) {
    const optText = (opt.text || opt.textContent || "").trim().toLowerCase();
    if (optText.length < 2) continue; // Skip very short options

    for (const v of variations) {
      const vLower = v.toLowerCase();
      if (vLower.startsWith(optText) || vLower.includes(optText)) {
        return opt;
      }
    }
  }

  return null;
}

/**
 * Fill a dropdown/select element by finding and selecting a matching option.
 * Supports both native select elements and Workday's custom dropdowns.
 * @param {HTMLElement} element - The dropdown container or select element.
 * @param {string} value - The value to select (will match against option text or value).
 * @param {string} fieldType - Type of field for smart matching ('state', 'deviceType', 'country', 'default').
 * @returns {boolean} - Whether the fill was successful.
 */
function fillDropdown(element, value, fieldType = "default") {
  if (!value || !element) return false;

  try {
    // Native <select> element
    if (element.tagName === "SELECT") {
      const options = Array.from(element.options);
      const match = findDropdownMatch(options, value, fieldType);

      if (match) {
        element.value = match.value;
        element.dispatchEvent(new Event("change", { bubbles: true }));
        element.dispatchEvent(new Event("input", { bubbles: true }));
        return true;
      }
      return false;
    }

    // Workday custom dropdown - these are button-based with popup lists
    // Find the button trigger
    let dropdownButton = element;
    if (element.tagName !== "BUTTON") {
      dropdownButton = element.querySelector("button") || element;
    }

    console.log("Job-Track: Clicking dropdown button:", dropdownButton);

    // Click to open the dropdown - use full mouse event sequence for React/Workday
    // Based on reference implementation that works with Workday
    dropdownButton.focus();

    // Full event sequence: pointerdown -> mousedown -> focus -> mouseup -> click
    ["pointerdown", "mousedown"].forEach((eventType) => {
      dropdownButton.dispatchEvent(
        new MouseEvent(eventType, {
          bubbles: true,
          cancelable: true,
          view: window,
        })
      );
    });
    dropdownButton.focus();
    ["mouseup", "click"].forEach((eventType) => {
      dropdownButton.dispatchEvent(
        new MouseEvent(eventType, {
          bubbles: true,
          cancelable: true,
          view: window,
        })
      );
    });

    // Need to wait for Workday's popup to render (it's async)
    // Use multiple attempts with increasing delays
    const attemptSelectOption = (attemptNum) => {
      if (attemptNum > 6) {
        console.log(
          "Job-Track: Failed to find dropdown options after 6 attempts"
        );
        document.body.click(); // Close dropdown
        return;
      }

      // Workday renders dropdown popups at the document level
      // Look for the popup listbox that just appeared
      const optionSelectors = [
        '[role="option"]',
        '[data-automation-id="promptOption"]',
        '[data-automation-id*="promptOption"]',
        '[data-automation-id*="option"]',
        '[data-automation-id*="menuItem"]',
        'li[role="option"]',
        'div[role="option"]',
        ".WDJT_option",
        '[aria-selected][role="option"]',
        '[id*="option"][role="option"]',
        '[role="listbox"] [role="option"]',
        '[data-automation-widget="wd-popup"] li',
        'ul[role="listbox"] li',
      ];

      let options = [];
      for (const selector of optionSelectors) {
        options = Array.from(document.querySelectorAll(selector));
        // Filter to only visible options with content
        options = options.filter((opt) => {
          const rect = opt.getBoundingClientRect();
          const hasContent = (opt.textContent || "").trim().length > 0;
          return rect.width > 0 && rect.height > 0 && hasContent;
        });
        if (options.length > 0) {
          console.log(
            `Job-Track: Found ${options.length} options with selector: ${selector}`
          );
          break;
        }
      }

      if (options.length === 0) {
        // Retry after increasing delay
        const delay = 200 + attemptNum * 80;
        console.log(
          `Job-Track: No options found, retrying in ${delay}ms (attempt ${attemptNum})...`
        );
        setTimeout(() => attemptSelectOption(attemptNum + 1), delay);
        return;
      }

      // Find matching option using smart matching
      const match = findDropdownMatch(options, value, fieldType);

      if (match) {
        console.log(
          `Job-Track: Found matching option for "${value}":`,
          match.textContent?.trim()
        );

        // More robust event sequence for React/Workday (from reference implementation)
        ["pointerover", "pointerdown", "mousedown", "mouseup", "click"].forEach(
          (eventType) => {
            match.dispatchEvent(new MouseEvent(eventType, { bubbles: true }));
          }
        );
        match.dispatchEvent(new Event("change", { bubbles: true }));
      } else {
        console.log(
          `Job-Track: No match found for "${value}" in ${options.length} options`
        );
        // Log available options for debugging
        const availableOptions = options
          .slice(0, 10)
          .map((o) => o.textContent?.trim());
        console.log("Job-Track: Available options:", availableOptions);
        document.body.click(); // Close dropdown
      }
    };

    // Start attempting to find options after initial delay (300ms to allow popup to render)
    setTimeout(() => attemptSelectOption(1), 300);

    return true; // Return true optimistically since actual click happens async
  } catch (e) {
    console.error("Job-Track: Error filling dropdown", e);
    return false;
  }
}

/**
 * Find and fill a Workday dropdown by automation ID.
 * @param {string[]} automationIds - List of automation IDs to search for.
 * @param {string} value - Value to select.
 * @param {string} fieldType - Type of field for smart matching ('state', 'deviceType', 'country', 'default').
 * @returns {boolean}
 */
function fillWorkdayDropdown(automationIds, value, fieldType = "default") {
  if (!value) return false;

  console.log(
    `Job-Track: Attempting to fill dropdown for ${fieldType} with value "${value}"`
  );
  console.log(
    `Job-Track: Looking for automation IDs:`,
    automationIds.slice(0, 5)
  );

  for (const id of automationIds) {
    // Look for dropdown container or button with this automation ID
    let element = document.querySelector(`[data-automation-id="${id}"]`);
    if (!element) {
      element = document.querySelector(`[data-automation-id*="${id}"]`);
    }
    if (!element) {
      element = document.querySelector(`[id="${id}"]`);
    }

    if (element) {
      console.log(
        `Job-Track: Found element with automation-id containing "${id}":`,
        element.tagName
      );

      // If the element is a button, it's the dropdown trigger itself
      if (element.tagName === "BUTTON") {
        return fillDropdown(element, value, fieldType);
      }

      // If it's a select, fill it directly
      if (element.tagName === "SELECT") {
        return fillDropdown(element, value, fieldType);
      }

      // Look for select inside the container
      const select = element.querySelector("select");
      if (select) {
        return fillDropdown(select, value, fieldType);
      }

      // Look for a button inside (Workday custom dropdown)
      const button = element.querySelector("button");
      if (button) {
        return fillDropdown(button, value, fieldType);
      }

      // Look for combobox role elements
      const combobox = element.querySelector(
        '[role="combobox"], [aria-haspopup="listbox"]'
      );
      if (combobox) {
        return fillDropdown(combobox, value, fieldType);
      }

      // Container itself might be clickable
      if (
        element.getAttribute("role") === "combobox" ||
        element.getAttribute("aria-haspopup")
      ) {
        return fillDropdown(element, value, fieldType);
      }

      // Last resort: try filling the container itself
      return fillDropdown(element, value, fieldType);
    }
  }

  console.log(`Job-Track: No element found for automation IDs:`, automationIds);
  return false;
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

  // Map profile fields to Workday automation IDs (text inputs)
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
      automationIds: WORKDAY_AUTOMATION_IDS.postalCode,
      value: profile.address_zip || profile.postal_code,
    },
  ];

  for (const mapping of fieldMappings) {
    if (mapping.value) {
      const field = findWorkdayField(mapping.automationIds);
      if (field) {
        // Try the standard fill first
        if (fillField(field, mapping.value)) {
          filledCount++;
          // For Workday, also try simulating typing as a backup after a delay
          // This helps with fields that have strict validation
          setTimeout(() => {
            if (field.value !== mapping.value) {
              simulateTyping(field, mapping.value);
            }
          }, 200);
        }
      }
    }
  }

  // Handle dropdown fields (phone device type, state, country)
  const dropdownMappings = [
    {
      automationIds: WORKDAY_AUTOMATION_IDS.phoneDeviceType,
      value: profile.phone_device_type || "Mobile",
      fieldType: "deviceType",
    },
    {
      automationIds: WORKDAY_AUTOMATION_IDS.state,
      value: profile.address_state || profile.state,
      fieldType: "state",
    },
    {
      automationIds: WORKDAY_AUTOMATION_IDS.country,
      value: profile.address_country || profile.country,
      fieldType: "country",
    },
  ];

  for (const mapping of dropdownMappings) {
    if (mapping.value) {
      if (
        fillWorkdayDropdown(
          mapping.automationIds,
          mapping.value,
          mapping.fieldType
        )
      ) {
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
    } else if (matchesPatterns(field, FIELD_PATTERNS.phoneExtension)) {
      // Skip phone extension fields - do not fill them with phone number
      filled = false;
    } else if (matchesPatterns(field, FIELD_PATTERNS.phoneDeviceType)) {
      // Phone device type - try to fill dropdown or text field
      const deviceType = profile.phone_device_type || "Mobile";
      if (field.tagName === "SELECT") {
        filled = fillDropdown(field, deviceType, "deviceType");
      } else {
        filled = fillField(field, deviceType);
      }
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
      // State might be a dropdown
      const stateValue = profile.address_state || profile.state;
      if (field.tagName === "SELECT") {
        filled = fillDropdown(field, stateValue, "state");
      } else {
        filled = fillField(field, stateValue);
      }
    } else if (matchesPatterns(field, FIELD_PATTERNS.postalCode)) {
      filled = fillField(field, profile.address_zip || profile.postal_code);
    }

    if (filled) {
      filledCount++;
      filledElements.add(field);
    }
  });

  // Also try to fill any dropdown elements for country/state
  const dropdowns = document.querySelectorAll("select");
  dropdowns.forEach((select) => {
    if (filledElements.has(select)) return;
    if (select.value && select.value.trim()) return;

    const selectText = [
      select.name || "",
      select.id || "",
      select.getAttribute("aria-label") || "",
    ]
      .join(" ")
      .toLowerCase();

    let filled = false;
    if (/country/i.test(selectText)) {
      filled = fillDropdown(
        select,
        profile.address_country || profile.country,
        "country"
      );
    } else if (/state|region|province/i.test(selectText)) {
      filled = fillDropdown(
        select,
        profile.address_state || profile.state,
        "state"
      );
    } else if (/device.?type|phone.?type/i.test(selectText)) {
      filled = fillDropdown(
        select,
        profile.phone_device_type || "Mobile",
        "deviceType"
      );
    }

    if (filled) {
      filledCount++;
      filledElements.add(select);
    }
  });

  // After filling all fields, trigger a final validation pass
  // This helps Workday and other React apps recognize the filled state
  if (filledCount > 0) {
    triggerFormValidation();
  }

  return {
    success: filledCount > 0,
    filledCount,
  };
}

/**
 * Trigger form validation by simulating user interaction.
 * This helps React-based forms (like Workday) recognize filled fields.
 */
function triggerFormValidation() {
  setTimeout(() => {
    // Find all filled inputs and re-trigger their validation
    const inputs = document.querySelectorAll("input, textarea");
    inputs.forEach((input) => {
      if (input.value && input.value.trim()) {
        // Dispatch events to trigger React's validation
        input.dispatchEvent(new FocusEvent("focus", { bubbles: true }));
        input.dispatchEvent(
          new InputEvent("input", {
            bubbles: true,
            cancelable: true,
            inputType: "insertText",
            data: input.value,
          })
        );
        input.dispatchEvent(new FocusEvent("blur", { bubbles: true }));
        input.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
      }
    });

    // Click somewhere neutral to trigger any pending validations
    // Workday often validates on clicking outside the form field
    const body = document.body;
    body.click();

    // Also try triggering validation on any visible form
    const forms = document.querySelectorAll("form");
    forms.forEach((form) => {
      // Don't submit, just trigger validation events
      form.dispatchEvent(new Event("input", { bubbles: true }));
      form.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }, 300);
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

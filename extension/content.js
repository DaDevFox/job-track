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
  phoneDeviceType: [
    // -- delimiter
    "phone--deviceType",
    "phone--type",
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
      element.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: char,
        code: `Key${char.toUpperCase()}`,
      }));
      
      // Append character to value
      element.value += char;
      
      // Dispatch input event for this character
      element.dispatchEvent(new InputEvent("input", {
        bubbles: true,
        cancelable: true,
        inputType: "insertText",
        data: char,
      }));
      
      // Dispatch keyup
      element.dispatchEvent(new KeyboardEvent("keyup", {
        bubbles: true,
        cancelable: true,
        key: char,
        code: `Key${char.toUpperCase()}`,
      }));
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
 * Fill a dropdown/select element by finding and selecting a matching option.
 * Supports both native select elements and Workday's custom dropdowns.
 * @param {HTMLElement} element - The dropdown container or select element.
 * @param {string} value - The value to select (will match against option text or value).
 * @returns {boolean} - Whether the fill was successful.
 */
function fillDropdown(element, value) {
  if (!value || !element) return false;
  
  try {
    const valueLower = value.toLowerCase().trim();
    
    // Native <select> element
    if (element.tagName === 'SELECT') {
      const options = Array.from(element.options);
      const match = options.find(opt => 
        opt.value.toLowerCase() === valueLower ||
        opt.text.toLowerCase() === valueLower ||
        opt.text.toLowerCase().includes(valueLower) ||
        valueLower.includes(opt.text.toLowerCase())
      );
      
      if (match) {
        element.value = match.value;
        element.dispatchEvent(new Event('change', { bubbles: true }));
        element.dispatchEvent(new Event('input', { bubbles: true }));
        return true;
      }
      return false;
    }
    
    // Workday custom dropdown - click to open, then find and click option
    // First, find and click the dropdown trigger
    const dropdownTrigger = element.querySelector('button, [role="combobox"], [aria-haspopup]') || element;
    dropdownTrigger.click();
    
    // Wait for dropdown to open and find options
    setTimeout(() => {
      // Look for dropdown options in various places
      const optionSelectors = [
        '[role="option"]',
        '[role="listbox"] [role="option"]',
        '[data-automation-id*="option"]',
        '.option',
        'li',
      ];
      
      let options = [];
      for (const selector of optionSelectors) {
        // Check both within element and in document (Workday often renders dropdowns at body level)
        options = Array.from(document.querySelectorAll(selector));
        if (options.length > 0) break;
      }
      
      // Find matching option
      const match = options.find(opt => {
        const text = (opt.textContent || '').toLowerCase().trim();
        return text === valueLower || 
               text.includes(valueLower) || 
               valueLower.includes(text);
      });
      
      if (match) {
        match.click();
        return true;
      } else {
        // Close dropdown if no match found
        document.body.click();
      }
    }, 100);
    
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
 * @returns {boolean}
 */
function fillWorkdayDropdown(automationIds, value) {
  if (!value) return false;
  
  for (const id of automationIds) {
    // Look for dropdown container with this automation ID
    let container = document.querySelector(`[data-automation-id="${id}"]`);
    if (!container) {
      container = document.querySelector(`[data-automation-id*="${id}"]`);
    }
    
    if (container) {
      // Find the actual dropdown trigger or select within
      const select = container.querySelector('select');
      if (select) {
        return fillDropdown(select, value);
      }
      
      // Workday custom dropdown
      const dropdown = container.querySelector('[role="combobox"], [role="listbox"], button, [aria-haspopup]');
      if (dropdown) {
        return fillDropdown(container, value);
      }
      
      // Container itself might be the dropdown
      if (container.getAttribute('role') === 'combobox' || container.getAttribute('aria-haspopup')) {
        return fillDropdown(container, value);
      }
    }
  }
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
    },
    {
      automationIds: WORKDAY_AUTOMATION_IDS.state,
      value: profile.address_state || profile.state,
    },
    {
      automationIds: WORKDAY_AUTOMATION_IDS.country,
      value: profile.address_country || profile.country,
    },
  ];
  
  for (const mapping of dropdownMappings) {
    if (mapping.value) {
      if (fillWorkdayDropdown(mapping.automationIds, mapping.value)) {
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
      if (field.tagName === 'SELECT') {
        filled = fillDropdown(field, deviceType);
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
      if (field.tagName === 'SELECT') {
        filled = fillDropdown(field, stateValue);
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
  const dropdowns = document.querySelectorAll('select');
  dropdowns.forEach(select => {
    if (filledElements.has(select)) return;
    if (select.value && select.value.trim()) return;
    
    const selectText = [
      select.name || '',
      select.id || '',
      select.getAttribute('aria-label') || '',
    ].join(' ').toLowerCase();
    
    let filled = false;
    if (/country/i.test(selectText)) {
      filled = fillDropdown(select, profile.address_country || profile.country);
    } else if (/state|region|province/i.test(selectText)) {
      filled = fillDropdown(select, profile.address_state || profile.state);
    } else if (/device.?type|phone.?type/i.test(selectText)) {
      filled = fillDropdown(select, profile.phone_device_type || "Mobile");
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
    const inputs = document.querySelectorAll('input, textarea');
    inputs.forEach(input => {
      if (input.value && input.value.trim()) {
        // Dispatch events to trigger React's validation
        input.dispatchEvent(new FocusEvent("focus", { bubbles: true }));
        input.dispatchEvent(new InputEvent("input", {
          bubbles: true,
          cancelable: true,
          inputType: "insertText",
          data: input.value,
        }));
        input.dispatchEvent(new FocusEvent("blur", { bubbles: true }));
        input.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
      }
    });
    
    // Click somewhere neutral to trigger any pending validations
    // Workday often validates on clicking outside the form field
    const body = document.body;
    body.click();
    
    // Also try triggering validation on any visible form
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
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

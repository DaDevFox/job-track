// Job-Track Content Script
// Handles autofilling form fields on job application pages

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
  ],
  firstName: [
    /first.?name/i,
    /given.?name/i,
    /^fname$/i,
  ],
  lastName: [
    /last.?name/i,
    /surname/i,
    /family.?name/i,
    /^lname$/i,
  ],
  email: [
    /e?.?mail/i,
    /email.?address/i,
  ],
  phone: [
    /phone/i,
    /mobile/i,
    /telephone/i,
    /cell/i,
    /contact.?number/i,
  ],
  linkedin: [
    /linkedin/i,
    /linked.?in/i,
  ],
  github: [
    /github/i,
    /git.?hub/i,
  ],
  portfolio: [
    /portfolio/i,
    /website/i,
    /personal.?site/i,
    /url/i,
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
    element.name || '',
    element.id || '',
    element.placeholder || '',
    element.getAttribute('aria-label') || '',
    element.getAttribute('data-testid') || '',
  ].join(' ');
  
  // Also check associated label
  let labelText = '';
  if (element.id) {
    const label = document.querySelector(`label[for="${element.id}"]`);
    if (label) {
      labelText = label.textContent || '';
    }
  }
  
  const fullText = checkText + ' ' + labelText;
  return patterns.some(pattern => pattern.test(fullText));
}

/**
 * Find all fillable input fields on the page.
 * @returns {HTMLInputElement[]}
 */
function findInputFields() {
  return Array.from(document.querySelectorAll(
    'input[type="text"], input[type="email"], input[type="tel"], input:not([type]), textarea'
  )).filter(el => {
    // Filter out hidden or disabled fields
    const style = window.getComputedStyle(el);
    return (
      style.display !== 'none' &&
      style.visibility !== 'hidden' &&
      !el.disabled &&
      !el.readOnly
    );
  });
}

/**
 * Set a value on an input field, triggering appropriate events.
 * @param {HTMLInputElement} element - Element to fill.
 * @param {string} value - Value to set.
 */
function fillField(element, value) {
  if (!value) return false;
  
  // Focus the element
  element.focus();
  
  // Set the value
  element.value = value;
  
  // Trigger input events (important for React/Vue apps)
  element.dispatchEvent(new Event('input', { bubbles: true }));
  element.dispatchEvent(new Event('change', { bubbles: true }));
  element.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
  
  // Blur to trigger validation
  element.blur();
  
  return true;
}

/**
 * Split a full name into first and last name.
 * @param {string} fullName - Full name to split.
 * @returns {{firstName: string, lastName: string}}
 */
function splitName(fullName) {
  const parts = fullName.trim().split(/\s+/);
  if (parts.length === 1) {
    return { firstName: parts[0], lastName: '' };
  }
  return {
    firstName: parts[0],
    lastName: parts.slice(1).join(' '),
  };
}

/**
 * Autofill form fields with profile data.
 * @param {Object} profile - Profile data.
 * @returns {{success: boolean, filledCount: number, error?: string}}
 */
function autofillForm(profile) {
  const fields = findInputFields();
  
  if (fields.length === 0) {
    return { success: false, filledCount: 0, error: 'No form fields found on this page' };
  }
  
  let filledCount = 0;
  const nameParts = splitName(profile.name || '');
  
  fields.forEach(field => {
    let filled = false;
    
    // Check each field type
    if (matchesPatterns(field, FIELD_PATTERNS.name)) {
      filled = fillField(field, profile.name);
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
    }
    
    if (filled) {
      filledCount++;
    }
  });
  
  return {
    success: filledCount > 0,
    filledCount,
  };
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'autofill' && message.profile) {
    const result = autofillForm(message.profile);
    sendResponse(result);
  }
  return true; // Keep the message channel open for async response
});

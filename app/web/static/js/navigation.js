const SAFE_MEETING_ID = "[A-Za-z0-9][A-Za-z0-9._-]{0,127}";
const KNOWN_PATHS = [
  /^\/dashboard$/,
  /^\/meetings$/,
  /^\/plans$/,
  new RegExp(`^/meetings/${SAFE_MEETING_ID}$`),
  new RegExp(`^/meetings/${SAFE_MEETING_ID}/transcript$`),
  new RegExp(`^/meetings/${SAFE_MEETING_ID}/confidential-notes$`),
];

const FOCUS_TARGETS = new Map([
  ["meeting_search", "meeting-search"],
]);

const CONFIRMATION_REQUIRED_PATHS = [
  /^\/plans$/,
  new RegExp(`^/meetings/${SAFE_MEETING_ID}/transcript$`),
];

const ALTERNATIVE_ACTION_PATHS = new Map([
  ["open_membership_plans", () => "/plans"],
  ["open_transcript", (meetingId) => `/meetings/${meetingId}/transcript`],
]);

export function isKnownNavigationPath(path) {
  if (typeof path !== "string" || path.startsWith("//") || path.includes("\\")) {
    return false;
  }
  let url;
  try {
    url = new URL(path, window.location.origin);
  } catch {
    return false;
  }
  if (
    url.origin !== window.location.origin ||
    url.search !== "" ||
    url.hash !== ""
  ) {
    return false;
  }
  return KNOWN_PATHS.some((pattern) => pattern.test(url.pathname));
}

export function followApprovedNavigation(navigation, options = {}) {
  if (
    navigation === null ||
    typeof navigation !== "object" ||
    navigation.method !== "GET" ||
    !isKnownNavigationPath(navigation.path)
  ) {
    return false;
  }
  const confirmationSatisfied = (
    options !== null &&
    typeof options === "object" &&
    options.confirmationSatisfied === true
  );
  if (
    !confirmationSatisfied &&
    !confirmSensitiveNavigation(navigation.path)
  ) {
    return false;
  }
  window.location.assign(navigation.path);
  return true;
}

export function followConfirmedPath(path) {
  if (!isKnownNavigationPath(path) || !confirmSensitiveNavigation(path)) {
    return false;
  }
  window.location.assign(path);
  return true;
}

export function followApprovedAlternativeAction(actionId, meetingId) {
  const resolvePath = ALTERNATIVE_ACTION_PATHS.get(actionId);
  if (resolvePath === undefined) {
    return false;
  }
  const path = resolvePath(meetingId);
  return followConfirmedPath(path);
}

function confirmSensitiveNavigation(path) {
  const requiresConfirmation = CONFIRMATION_REQUIRED_PATHS.some((pattern) =>
    pattern.test(path),
  );
  return !requiresConfirmation || window.confirm("Continue to this page?");
}

export function focusApprovedTarget(target) {
  const elementId = FOCUS_TARGETS.get(target);
  if (elementId === undefined) {
    return false;
  }
  const element = document.getElementById(elementId);
  if (!(element instanceof HTMLElement)) {
    return false;
  }
  element.focus();
  return true;
}

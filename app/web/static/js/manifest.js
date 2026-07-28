const MANIFEST_VERSION = 1;
const MEETING_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const PAGE_IDS = new Set([
  "login",
  "dashboard",
  "meeting_history",
  "meeting_detail",
  "transcript",
  "confidential_notes",
  "membership_plans",
]);

let currentManifest = null;

function readEmbeddedManifest() {
  const element = document.getElementById("page-manifest");
  if (!(element instanceof HTMLScriptElement)) {
    throw new Error("Page manifest is unavailable.");
  }

  let parsed;
  try {
    parsed = JSON.parse(element.textContent || "{}");
  } catch {
    throw new Error("Page manifest is invalid.");
  }

  if (
    parsed.version !== MANIFEST_VERSION ||
    !PAGE_IDS.has(parsed.page_id) ||
    !isMeetingIdOrNull(parsed.active_meeting_id) ||
    !Array.isArray(parsed.visible_meeting_ids)
  ) {
    throw new Error("Page manifest is unsupported.");
  }

  const visibleMeetingIds = sanitizeMeetingIds(parsed.visible_meeting_ids);
  return {
    version: MANIFEST_VERSION,
    page_id: parsed.page_id,
    active_meeting_id: parsed.active_meeting_id,
    visible_meeting_ids: visibleMeetingIds,
  };
}

function isMeetingIdOrNull(value) {
  return value === null || (
    typeof value === "string" && MEETING_ID_PATTERN.test(value)
  );
}

function sanitizeMeetingIds(values) {
  const unique = [];
  for (const value of values) {
    if (
      typeof value === "string" &&
      MEETING_ID_PATTERN.test(value) &&
      !unique.includes(value)
    ) {
      unique.push(value);
    }
    if (unique.length === 50) {
      break;
    }
  }
  return unique;
}

function writeEmbeddedManifest() {
  const element = document.getElementById("page-manifest");
  if (element instanceof HTMLScriptElement && currentManifest !== null) {
    element.textContent = JSON.stringify(currentManifest);
  }
}

export function getPageManifest() {
  if (currentManifest === null) {
    currentManifest = readEmbeddedManifest();
  }
  return {
    ...currentManifest,
    visible_meeting_ids: [...currentManifest.visible_meeting_ids],
  };
}

export function setVisibleMeetingIds(meetingIds) {
  const manifest = getPageManifest();
  currentManifest = {
    ...manifest,
    visible_meeting_ids: sanitizeMeetingIds(meetingIds),
  };
  writeEmbeddedManifest();
}

export function getAssistantPageManifest() {
  const manifest = getPageManifest();
  if (manifest.page_id === "login") {
    throw new Error("The assistant is unavailable on the login page.");
  }
  return {
    page_id: manifest.page_id,
    active_meeting_id: manifest.active_meeting_id,
    visible_meeting_ids: manifest.visible_meeting_ids,
  };
}

export function isSafeMeetingId(value) {
  return typeof value === "string" && MEETING_ID_PATTERN.test(value);
}

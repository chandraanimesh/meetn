import { ApiError, apiFetch } from "./api.js";
import {
  getPageManifest,
  isSafeMeetingId,
  setVisibleMeetingIds,
} from "./manifest.js";
import {
  followApprovedAlternativeAction,
  followConfirmedPath,
} from "./navigation.js";

const MAX_TRANSCRIPT_CHARACTERS = 200000;

function elementById(id) {
  return document.getElementById(id);
}

function showPageAlert(message) {
  const alert = elementById("page-alert");
  if (alert instanceof HTMLElement) {
    alert.textContent = message;
    alert.hidden = false;
  }
}

function handlePageError(error) {
  if (error instanceof ApiError && error.status === 401) {
    return;
  }
  if (error instanceof ApiError && error.status === 403) {
    showPageAlert("You do not have permission to view this page.");
    return;
  }
  if (error instanceof ApiError && error.status === 404) {
    showPageAlert("The requested meeting resource was not found.");
    return;
  }
  showPageAlert("We could not load this page. Please try again.");
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Not available";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function meetingStatusLabel(value) {
  const labels = {
    scheduled: "Planned to meet",
    rescheduled: "Rescheduled",
    in_progress: "In progress",
    completed: "Completed",
    cancelled: "Cancelled",
  };
  return labels[value] || "Meeting";
}

function safeMeetingPath(meetingId, suffix = "") {
  if (!isSafeMeetingId(meetingId)) {
    throw new Error("Meeting identifier is invalid.");
  }
  return `/meetings/${encodeURIComponent(meetingId)}${suffix}`;
}

function emptyState(message) {
  const paragraph = document.createElement("p");
  paragraph.className = "empty-state";
  paragraph.textContent = message;
  return paragraph;
}

function createMeetingCard(meeting) {
  const article = document.createElement("article");
  article.className = "meeting-card";
  article.dataset.meetingId = meeting.id;

  const status = document.createElement("p");
  status.className = "eyebrow";
  status.textContent = meetingStatusLabel(meeting.status);

  const title = document.createElement("h3");
  const link = document.createElement("a");
  link.href = safeMeetingPath(meeting.id);
  link.textContent = meeting.title || "Untitled meeting";
  title.append(link);

  const time = document.createElement("p");
  time.className = "muted";
  time.textContent = meeting.place
    ? `${formatDate(meeting.start_time)} · ${meeting.place}`
    : formatDate(meeting.start_time);

  article.append(status, title, time);
  return article;
}

async function loadMeetings(targetId, limit = null) {
  const response = await apiFetch("/api/me/meetings");
  const meetings = Array.isArray(response?.items) ? response.items : [];
  setVisibleMeetingIds(meetings.map((meeting) => meeting.id));

  const target = elementById(targetId);
  if (!(target instanceof HTMLElement)) {
    return meetings;
  }
  const visibleMeetings = limit === null ? meetings : meetings.slice(0, limit);
  target.replaceChildren(
    ...(visibleMeetings.length > 0
      ? visibleMeetings.map(createMeetingCard)
      : [emptyState("No meetings are available yet.")]),
  );
  return meetings;
}

async function initializeDashboard() {
  await loadMeetings("dashboard-meetings", 3);
}

async function initializeMeetingHistory() {
  const meetings = await loadMeetings("meeting-list");
  initializeMeetingScheduler(meetings);
  const search = elementById("meeting-search");
  const target = elementById("meeting-list");
  if (!(search instanceof HTMLInputElement) || !(target instanceof HTMLElement)) {
    return;
  }
  search.addEventListener("input", () => {
    const query = search.value.trim().toLocaleLowerCase();
    const filtered = meetings.filter((meeting) =>
      String(meeting.title || "").toLocaleLowerCase().includes(query),
    );
    target.replaceChildren(
      ...(filtered.length > 0
        ? filtered.map(createMeetingCard)
        : [emptyState("No meetings match your search.")]),
    );
  });
}

function toDateTimeLocal(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return localDate.toISOString().slice(0, 16);
}

function meetingDurationMinutes(meeting) {
  const start = new Date(meeting.start_time);
  const end = new Date(meeting.end_time);
  const duration = Math.round((end.getTime() - start.getTime()) / 60000);
  return [30, 60, 90, 120].includes(duration) ? duration : 60;
}

function setSchedulerStatus(message, isError = false) {
  const status = elementById("schedule-form-status");
  if (status instanceof HTMLElement) {
    status.textContent = message;
    status.classList.toggle("form-error", isError);
  }
}

function populateSchedulerFromMeeting(meeting) {
  const fields = {
    "schedule-title": meeting?.title || "",
    "schedule-place": meeting?.place || "",
    "schedule-start-time": toDateTimeLocal(meeting?.start_time),
    "schedule-purpose": meeting?.purpose || "",
    "schedule-personal-gift": meeting?.personal_gift || "",
  };
  for (const [id, value] of Object.entries(fields)) {
    const control = elementById(id);
    if (
      control instanceof HTMLInputElement ||
      control instanceof HTMLTextAreaElement
    ) {
      control.value = value;
    }
  }
  const duration = elementById("schedule-duration");
  if (duration instanceof HTMLSelectElement && meeting !== undefined) {
    duration.value = String(meetingDurationMinutes(meeting));
  }
}

function initializeMeetingScheduler(meetings) {
  const toggle = elementById("meeting-form-toggle");
  const panel = elementById("meeting-scheduler");
  const form = elementById("meeting-schedule-form");
  const mode = elementById("schedule-mode");
  const existingRow = elementById("schedule-existing-row");
  const meetingSelect = elementById("schedule-meeting-id");
  if (
    !(toggle instanceof HTMLButtonElement) ||
    !(panel instanceof HTMLElement) ||
    !(form instanceof HTMLFormElement) ||
    !(mode instanceof HTMLSelectElement) ||
    !(existingRow instanceof HTMLElement) ||
    !(meetingSelect instanceof HTMLSelectElement)
  ) {
    return;
  }

  meetingSelect.replaceChildren(
    ...meetings.map((meeting) => {
      const option = document.createElement("option");
      option.value = meeting.id;
      option.textContent = meeting.title || "Untitled meeting";
      return option;
    }),
  );

  const updateMode = () => {
    const rescheduling = mode.value === "reschedule";
    existingRow.hidden = !rescheduling;
    meetingSelect.required = rescheduling;
    if (rescheduling) {
      const selected = meetings.find(
        (meeting) => meeting.id === meetingSelect.value,
      );
      populateSchedulerFromMeeting(selected);
    } else {
      populateSchedulerFromMeeting(undefined);
    }
    setSchedulerStatus("");
  };

  toggle.addEventListener("click", () => {
    panel.hidden = !panel.hidden;
    toggle.setAttribute("aria-expanded", String(!panel.hidden));
    if (!panel.hidden) {
      mode.focus();
    }
  });
  mode.addEventListener("change", updateMode);
  meetingSelect.addEventListener("change", () => {
    const selected = meetings.find(
      (meeting) => meeting.id === meetingSelect.value,
    );
    populateSchedulerFromMeeting(selected);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const title = elementById("schedule-title");
    const place = elementById("schedule-place");
    const start = elementById("schedule-start-time");
    const duration = elementById("schedule-duration");
    const purpose = elementById("schedule-purpose");
    const gift = elementById("schedule-personal-gift");
    const submit = elementById("schedule-submit");
    if (
      !(title instanceof HTMLInputElement) ||
      !(place instanceof HTMLInputElement) ||
      !(start instanceof HTMLInputElement) ||
      !(duration instanceof HTMLSelectElement) ||
      !(purpose instanceof HTMLTextAreaElement) ||
      !(gift instanceof HTMLInputElement) ||
      !(submit instanceof HTMLButtonElement)
    ) {
      return;
    }

    const parsedStart = new Date(start.value);
    if (Number.isNaN(parsedStart.getTime())) {
      setSchedulerStatus("Choose a valid date and time.", true);
      return;
    }
    const requestBody = {
      title: title.value.trim(),
      place: place.value.trim(),
      purpose: purpose.value.trim(),
      personal_gift: gift.value.trim(),
      start_time: parsedStart.toISOString(),
      duration_minutes: Number.parseInt(duration.value, 10),
    };
    const rescheduling = mode.value === "reschedule";
    if (rescheduling && !isSafeMeetingId(meetingSelect.value)) {
      setSchedulerStatus("Choose a valid meeting to reschedule.", true);
      return;
    }

    submit.disabled = true;
    setSchedulerStatus(rescheduling ? "Rescheduling…" : "Planning meeting…");
    try {
      const result = await apiFetch(
        rescheduling
          ? `/api/meetings/${encodeURIComponent(meetingSelect.value)}/schedule`
          : "/api/meetings",
        {
          method: rescheduling ? "PATCH" : "POST",
          body: JSON.stringify(requestBody),
        },
      );
      setSchedulerStatus(
        rescheduling ? "Meeting rescheduled." : "Meeting planned.",
      );
      window.location.assign(safeMeetingPath(result.id));
    } catch (error) {
      setSchedulerStatus(
        error instanceof ApiError
          ? error.message
          : "Could not save the meeting.",
        true,
      );
      submit.disabled = false;
    }
  });
}

function appendMetadata(list, labelText, valueText) {
  const wrapper = document.createElement("div");
  const label = document.createElement("dt");
  const value = document.createElement("dd");
  label.textContent = labelText;
  value.textContent = valueText;
  wrapper.append(label, value);
  list.append(wrapper);
}

function createResourceLink(label, href, confirmationRequired = false) {
  const link = document.createElement("a");
  link.className = "button button-secondary";
  link.href = href;
  link.textContent = label;
  if (confirmationRequired) {
    link.dataset.confirmNavigation = "true";
  }
  return link;
}

function recordingAvailabilityMessage(reason) {
  const messages = {
    available: "The recording is available for your verified membership.",
    not_created: "A recording has not been created for this meeting.",
    processing: "The recording is still processing.",
    plan_restriction: "Your verified membership does not include recording access.",
    unauthorized: "Recording availability cannot be shown for this meeting.",
  };
  return messages[reason] || "Recording availability could not be verified.";
}

function renderRecordingAvailability(result, meetingId) {
  const message = elementById("recording-availability-message");
  const requiredPlan = elementById("recording-required-plan");
  const actions = elementById("recording-alternative-actions");
  if (message instanceof HTMLElement) {
    message.textContent = recordingAvailabilityMessage(result.verified_reason);
  }
  if (requiredPlan instanceof HTMLElement) {
    if (
      result.verified_reason === "plan_restriction" &&
      typeof result.required_plan === "string"
    ) {
      requiredPlan.textContent = `Required plan: ${result.required_plan}`;
      requiredPlan.hidden = false;
    } else {
      requiredPlan.textContent = "";
      requiredPlan.hidden = true;
    }
  }
  if (!(actions instanceof HTMLElement)) {
    return;
  }
  const allowedActions = Array.isArray(result.allowed_alternative_action_ids)
    ? result.allowed_alternative_action_ids
    : [];
  const buttons = allowedActions.flatMap((actionId) => {
    const labels = {
      open_transcript: "Confirm and open transcript",
      open_membership_plans: "Confirm and view membership plans",
    };
    if (!Object.hasOwn(labels, actionId)) {
      return [];
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button button-secondary";
    button.textContent = labels[actionId];
    button.addEventListener("click", () => {
      followApprovedAlternativeAction(actionId, meetingId);
    });
    return [button];
  });
  actions.replaceChildren(...buttons);
}

async function initializeMeetingDetail(meetingId) {
  const meeting = await apiFetch(`/api/meetings/${encodeURIComponent(meetingId)}`);
  const recordingAvailability = await apiFetch(
    `/api/meetings/${encodeURIComponent(meetingId)}/recording-availability`,
  );
  const title = elementById("meeting-title");
  const status = elementById("meeting-status");
  const metadata = elementById("meeting-metadata");
  const participants = elementById("participant-list");
  const resourceLinks = elementById("meeting-resource-links");

  if (title instanceof HTMLElement) {
    title.textContent = meeting.title || "Meeting detail";
  }
  if (status instanceof HTMLElement) {
    status.textContent = meetingStatusLabel(meeting.status);
  }
  if (metadata instanceof HTMLElement) {
    metadata.replaceChildren();
    appendMetadata(metadata, "Starts", formatDate(meeting.start_time));
    appendMetadata(metadata, "Ends", formatDate(meeting.end_time));
    appendMetadata(metadata, "Place", meeting.place || "Not specified");
    appendMetadata(metadata, "Purpose", meeting.purpose || "Not specified");
    appendMetadata(
      metadata,
      "Personal gift",
      meeting.personal_gift || "None planned",
    );
    appendMetadata(metadata, "Organizer ID", meeting.organizer_id || "Not available");
  }
  if (participants instanceof HTMLElement) {
    const items = Array.isArray(meeting.participants) ? meeting.participants : [];
    participants.replaceChildren(
      ...(items.length > 0
        ? items.map((participant) => {
            const item = document.createElement("li");
            item.textContent = `${participant.user_id} · ${participant.role}`;
            return item;
          })
        : [emptyState("No participants are listed.")]),
    );
  }
  if (resourceLinks instanceof HTMLElement) {
    resourceLinks.replaceChildren(
      createResourceLink(
        "Open or add transcript",
        safeMeetingPath(meetingId, "/transcript"),
        true,
      ),
      createResourceLink(
        "Open confidential notes",
        safeMeetingPath(meetingId, "/confidential-notes"),
      ),
    );
  }
  renderRecordingAvailability(recordingAvailability, meetingId);
}

function setTranscriptUploadStatus(message, isError = false) {
  const status = elementById("transcript-upload-status");
  if (status instanceof HTMLElement) {
    status.textContent = message;
    status.classList.toggle("form-error", isError);
  }
}

function initializeTranscriptUpload(meetingId) {
  const form = elementById("transcript-upload-form");
  const textarea = elementById("transcript-input");
  const fileInput = elementById("transcript-file");
  const submit = elementById("transcript-submit");
  const content = elementById("transcript-content");
  if (
    !(form instanceof HTMLFormElement) ||
    !(textarea instanceof HTMLTextAreaElement) ||
    !(fileInput instanceof HTMLInputElement) ||
    !(submit instanceof HTMLButtonElement)
  ) {
    return;
  }

  fileInput.addEventListener("change", async () => {
    const file = fileInput.files?.[0];
    if (!(file instanceof File)) {
      return;
    }
    const plainTextFile = (
      file.type === "text/plain" ||
      (file.type === "" && file.name.toLocaleLowerCase().endsWith(".txt"))
    );
    if (!plainTextFile) {
      fileInput.value = "";
      setTranscriptUploadStatus("Choose a plain-text .txt file.", true);
      return;
    }
    if (file.size > MAX_TRANSCRIPT_CHARACTERS * 4) {
      fileInput.value = "";
      setTranscriptUploadStatus("The selected file is too large.", true);
      return;
    }
    try {
      const fileContent = await file.text();
      if (
        fileContent.length > MAX_TRANSCRIPT_CHARACTERS ||
        fileContent.includes("\u0000")
      ) {
        throw new Error("Unsupported transcript file content");
      }
      textarea.value = fileContent;
      setTranscriptUploadStatus("Text file loaded. Review it before saving.");
    } catch {
      fileInput.value = "";
      setTranscriptUploadStatus("The text file could not be read safely.", true);
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const transcriptText = textarea.value.trim();
    if (
      transcriptText.length === 0 ||
      transcriptText.length > MAX_TRANSCRIPT_CHARACTERS ||
      transcriptText.includes("\u0000")
    ) {
      setTranscriptUploadStatus("Enter valid transcript text before saving.", true);
      return;
    }

    submit.disabled = true;
    setTranscriptUploadStatus("Saving transcript…");
    try {
      const result = await apiFetch(
        `/api/meetings/${encodeURIComponent(meetingId)}/transcript`,
        {
          method: "POST",
          body: JSON.stringify({ content: transcriptText }),
        },
      );
      if (content instanceof HTMLElement) {
        content.textContent = result.content || "The transcript is empty.";
      }
      textarea.value = "";
      fileInput.value = "";
      textarea.disabled = true;
      fileInput.disabled = true;
      setTranscriptUploadStatus("Transcript saved. Participants can now view it.");
    } catch (error) {
      submit.disabled = false;
      setTranscriptUploadStatus(
        error instanceof ApiError
          ? error.message
          : "The transcript could not be saved.",
        true,
      );
    }
  });
}

async function initializeTranscript(meetingId, session) {
  setMeetingBackLink("transcript-back-link", meetingId);
  const content = elementById("transcript-content");
  const uploadPanel = elementById("transcript-upload-panel");
  const meeting = await apiFetch(
    `/api/meetings/${encodeURIComponent(meetingId)}`,
  );
  const organizerHint = (
    typeof session?.user?.id === "string" &&
    meeting.organizer_id === session.user.id
  );

  try {
    const transcript = await apiFetch(
      `/api/meetings/${encodeURIComponent(meetingId)}/transcript`,
    );
    if (content instanceof HTMLElement) {
      content.textContent = transcript.content || "The transcript is empty.";
    }
    if (uploadPanel instanceof HTMLElement) {
      uploadPanel.hidden = true;
    }
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 404) {
      throw error;
    }
    if (content instanceof HTMLElement) {
      content.textContent = "No transcript has been added for this meeting yet.";
    }
    if (uploadPanel instanceof HTMLElement) {
      uploadPanel.hidden = !organizerHint;
    }
    if (organizerHint) {
      initializeTranscriptUpload(meetingId);
    }
  }
}

async function initializeConfidentialNotes(meetingId) {
  const response = await apiFetch(
    `/api/meetings/${encodeURIComponent(meetingId)}/confidential-notes`,
  );
  const target = elementById("confidential-note-list");
  if (target instanceof HTMLElement) {
    const notes = Array.isArray(response?.items) ? response.items : [];
    target.replaceChildren(
      ...(notes.length > 0
        ? notes.map((note) => {
            const article = document.createElement("article");
            article.className = "panel note-card";
            const metadata = document.createElement("p");
            metadata.className = "eyebrow";
            metadata.textContent = `Created ${formatDate(note.created_at)}`;
            const content = document.createElement("p");
            content.className = "protected-note";
            content.textContent = note.content || "Empty note";
            article.append(metadata, content);
            return article;
          })
        : [emptyState("No confidential notes are available to you.")]),
    );
  }
  setMeetingBackLink("notes-back-link", meetingId);
}

function setMeetingBackLink(elementId, meetingId) {
  const link = elementById(elementId);
  if (link instanceof HTMLAnchorElement) {
    link.href = safeMeetingPath(meetingId);
  }
}

async function initializeAuthenticatedPage(manifest) {
  const session = await apiFetch("/api/v1/session");
  const sessionUser = elementById("session-user");
  if (sessionUser instanceof HTMLElement) {
    sessionUser.textContent = session?.user?.display_name || "Signed in";
  }

  const logoutButton = elementById("logout-button");
  if (logoutButton instanceof HTMLButtonElement) {
    logoutButton.addEventListener("click", async () => {
      logoutButton.disabled = true;
      try {
        await apiFetch("/api/v1/auth/logout", { method: "POST" });
        window.location.assign("/login");
      } catch (error) {
        logoutButton.disabled = false;
        handlePageError(error);
      }
    });
  }

  switch (manifest.page_id) {
    case "dashboard":
      await initializeDashboard();
      break;
    case "meeting_history":
      await initializeMeetingHistory();
      break;
    case "meeting_detail":
      await initializeMeetingDetail(manifest.active_meeting_id);
      break;
    case "transcript":
      await initializeTranscript(manifest.active_meeting_id, session);
      break;
    case "confidential_notes":
      await initializeConfidentialNotes(manifest.active_meeting_id);
      break;
    case "membership_plans":
      break;
    default:
      throw new Error("Unsupported page.");
  }
}

function initializeConfirmedLinks() {
  for (const link of document.querySelectorAll("[data-confirm-navigation]")) {
    if (!(link instanceof HTMLAnchorElement)) {
      continue;
    }
    link.addEventListener("click", (event) => {
      event.preventDefault();
      followConfirmedPath(link.pathname);
    });
  }
}

async function initialize() {
  try {
    const manifest = getPageManifest();
    initializeConfirmedLinks();
    if (manifest.page_id === "login") {
      return;
    }
    if (
      ["meeting_detail", "transcript", "confidential_notes"].includes(
        manifest.page_id,
      ) && !isSafeMeetingId(manifest.active_meeting_id)
    ) {
      throw new Error("Meeting identifier is unavailable.");
    }
    await initializeAuthenticatedPage(manifest);
  } catch (error) {
    handlePageError(error);
  }
}

void initialize();

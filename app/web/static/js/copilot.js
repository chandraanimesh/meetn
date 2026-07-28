import { ApiError, apiFetch } from "./api.js";
import { getAssistantPageManifest } from "./manifest.js";
import {
  focusApprovedTarget,
  followApprovedNavigation,
} from "./navigation.js";
import { applyAssistantPresentation } from "./theme.js";

const toggle = document.getElementById("copilot-toggle");
const closeButton = document.getElementById("copilot-close");
const panel = document.getElementById("copilot-panel");
const form = document.getElementById("copilot-form");
const input = document.getElementById("copilot-input");
const messages = document.getElementById("copilot-messages");
const quickOptions = document.getElementById("copilot-options");
const voiceButton = document.getElementById("copilot-voice-button");
const voiceHelp = document.getElementById("copilot-voice-help");
const voiceStatus = document.getElementById("copilot-voice-status");
const SpeechRecognitionConstructor =
  window.SpeechRecognition || window.webkitSpeechRecognition;
const voiceSupported = typeof SpeechRecognitionConstructor === "function";
let welcomeShown = false;
let speechRecognition = null;
let voiceActive = false;
let voiceOutcome = null;

const NAVIGATION_PROMPTS = new Map([
  ["open_dashboard", "Open my dashboard"],
  ["open_meeting_history", "Open my meeting history"],
  ["open_membership_plans", "Open membership plans"],
  ["focus_meeting_search", "Focus meeting search"],
]);

function setVoiceState(active, message) {
  voiceActive = active;
  if (voiceButton instanceof HTMLButtonElement) {
    voiceButton.setAttribute("aria-pressed", String(active));
    voiceButton.textContent = active ? "Stop" : "Speak";
  }
  if (voiceStatus instanceof HTMLElement && typeof message === "string") {
    voiceStatus.textContent = message;
  }
}

function stopVoiceInput({ abort = false, announce = true } = {}) {
  if (speechRecognition === null || !voiceActive) {
    return;
  }
  voiceOutcome = "stopped";
  try {
    if (abort) {
      speechRecognition.abort();
    } else {
      speechRecognition.stop();
    }
    setVoiceState(false, announce ? "Voice input stopped." : "");
  } catch {
    setVoiceState(false, announce ? "Voice input is already stopped." : "");
  }
}

function voiceErrorMessage(errorCode) {
  if (errorCode === "not-allowed" || errorCode === "service-not-allowed") {
    return "Microphone access was denied. You can continue by typing.";
  }
  if (errorCode === "audio-capture") {
    return "No microphone is available. You can continue by typing.";
  }
  if (errorCode === "no-speech") {
    return "No speech was detected. Try again or type your request.";
  }
  return "Voice input could not be completed. You can continue by typing.";
}

function initializeVoiceInput() {
  if (
    !(voiceButton instanceof HTMLButtonElement) ||
    !(input instanceof HTMLInputElement)
  ) {
    return;
  }
  if (!voiceSupported) {
    voiceButton.disabled = true;
    voiceButton.hidden = true;
    if (voiceHelp instanceof HTMLElement) {
      voiceHelp.textContent =
        "Voice input is not supported in this browser. Typing still works.";
    }
    return;
  }

  speechRecognition = new SpeechRecognitionConstructor();
  speechRecognition.continuous = false;
  speechRecognition.interimResults = false;
  speechRecognition.maxAlternatives = 1;
  speechRecognition.lang =
    document.documentElement.lang || window.navigator.language || "en-US";

  speechRecognition.addEventListener("start", () => {
    voiceOutcome = null;
    setVoiceState(true, "Listening. Speak your request now.");
  });
  speechRecognition.addEventListener("result", (event) => {
    voiceOutcome = "result";
    const transcript = String(
      event.results?.[0]?.[0]?.transcript || "",
    ).trim();
    setVoiceState(false, "Speech recognized.");
    if (transcript.length === 0) {
      if (voiceStatus instanceof HTMLElement) {
        voiceStatus.textContent =
          "No speech was detected. Try again or type your request.";
      }
      return;
    }
    if (transcript.length > 2000) {
      if (voiceStatus instanceof HTMLElement) {
        voiceStatus.textContent =
          "The spoken request was too long. Please shorten it or type instead.";
      }
      return;
    }
    void sendMessage(transcript);
  });
  speechRecognition.addEventListener("error", (event) => {
    voiceOutcome = "error";
    setVoiceState(false, voiceErrorMessage(event.error));
  });
  speechRecognition.addEventListener("end", () => {
    if (voiceActive) {
      setVoiceState(
        false,
        voiceOutcome === null
          ? "Voice input ended. Try again or type your request."
          : "Voice input stopped.",
      );
    }
  });

  voiceButton.addEventListener("click", () => {
    if (voiceActive) {
      stopVoiceInput();
      return;
    }
    voiceOutcome = null;
    setVoiceState(true, "Starting voice input.");
    try {
      speechRecognition.start();
    } catch {
      setVoiceState(
        false,
        "Voice input could not start. You can continue by typing.",
      );
    }
  });
}

function setPanelOpen(open) {
  if (!(panel instanceof HTMLElement) || !(toggle instanceof HTMLButtonElement)) {
    return;
  }
  panel.hidden = !open;
  toggle.setAttribute("aria-expanded", String(open));
  if (!open) {
    stopVoiceInput({ abort: true });
  }
  if (open && input instanceof HTMLInputElement) {
    if (!welcomeShown) {
      addMessage(
        "assistant",
        "Where would you like to go? Choose an option or type your request.",
      );
      welcomeShown = true;
    }
    input.focus();
  }
}

function addMessage(sender, text) {
  if (!(messages instanceof HTMLElement)) {
    return null;
  }
  const wrapper = document.createElement("div");
  wrapper.className = `copilot-message copilot-message-${sender}`;
  const label = document.createElement("p");
  label.className = "message-label";
  label.textContent = sender === "user" ? "You" : "Meetn";
  const content = document.createElement("p");
  content.textContent = text;
  wrapper.append(label, content);
  messages.append(wrapper);
  messages.scrollTop = messages.scrollHeight;
  return wrapper;
}

function addActionButton(container, label, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "button button-small button-secondary";
  button.textContent = label;
  button.addEventListener("click", () => {
    button.disabled = true;
    onClick();
  });
  container.append(button);
}

async function executeConfirmedAction(result) {
  try {
    const confirmed = await apiFetch("/api/assistant/actions/confirm", {
      method: "POST",
      body: JSON.stringify({
        action_id: result.action_id,
        parameters: result.parameters || {},
      }),
    });
    renderAssistantResult(confirmed, {
      autoExecute: true,
      confirmationSatisfied: true,
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return;
    }
    addMessage(
      "assistant",
      error instanceof ApiError
        ? error.message
        : "The confirmed action could not be completed.",
    );
  }
}

function renderAssistantResult(result, execution = {}) {
  applyAssistantPresentation(result.presentation);
  const container = addMessage(
    "assistant",
    typeof result.message === "string"
      ? result.message
      : "The assistant could not provide a safe response.",
  );
  if (!(container instanceof HTMLElement)) {
    return;
  }

  if (result.requires_confirmation === true) {
    addActionButton(container, "Confirm", () => {
      void executeConfirmedAction(result);
    });
    return;
  }
  if (result.status !== "success") {
    return;
  }
  if (result.navigation !== null && result.navigation !== undefined) {
    if (
      execution.autoExecute === true &&
      followApprovedNavigation(result.navigation, {
        confirmationSatisfied: execution.confirmationSatisfied === true,
      })
    ) {
      return;
    }
    addActionButton(container, "Open page", () => {
      if (!followApprovedNavigation(result.navigation)) {
        addMessage("assistant", "That navigation instruction was rejected.");
      }
    });
  }
  if (typeof result.focus_target === "string") {
    if (
      execution.autoExecute === true &&
      focusApprovedTarget(result.focus_target)
    ) {
      setPanelOpen(false);
      return;
    }
    addActionButton(container, "Focus control", () => {
      if (!focusApprovedTarget(result.focus_target)) {
        addMessage("assistant", "That focus instruction was rejected.");
      }
    });
  }
}

function setFormBusy(busy) {
  if (!(form instanceof HTMLFormElement)) {
    return;
  }
  for (const control of form.elements) {
    if (control instanceof HTMLInputElement || control instanceof HTMLButtonElement) {
      control.disabled = busy;
    }
  }
  if (voiceButton instanceof HTMLButtonElement) {
    voiceButton.disabled = busy || !voiceSupported;
  }
  if (quickOptions instanceof HTMLElement) {
    for (const button of quickOptions.querySelectorAll("button")) {
      if (button instanceof HTMLButtonElement) {
        button.disabled = busy || button.dataset.contextUnavailable === "true";
      }
    }
  }
}

async function sendMessage(rawMessage) {
  const message = String(rawMessage || "").trim();
  if (message.length === 0 || message.length > 2000) {
    return;
  }
  addMessage("user", message);
  setFormBusy(true);
  try {
    const result = await apiFetch("/api/assistant/messages", {
      method: "POST",
      body: JSON.stringify({
        message,
        page_manifest: getAssistantPageManifest(),
      }),
    });
    renderAssistantResult(result, { autoExecute: true });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return;
    }
    addMessage(
      "assistant",
      error instanceof ApiError && error.status === 403
        ? "You do not have permission to use that resource."
        : "The assistant is unavailable right now. Please try again.",
    );
  } finally {
    setFormBusy(false);
    if (
      input instanceof HTMLInputElement &&
      (!(panel instanceof HTMLElement) || !panel.hidden)
    ) {
      input.focus();
    }
  }
}

if (toggle instanceof HTMLButtonElement) {
  toggle.addEventListener("click", () => {
    setPanelOpen(toggle.getAttribute("aria-expanded") !== "true");
  });
}
if (closeButton instanceof HTMLButtonElement) {
  closeButton.addEventListener("click", () => setPanelOpen(false));
}

document.addEventListener("click", (event) => {
  const copilotElement = document.getElementById("copilot");
  if (
    copilotElement &&
    toggle instanceof HTMLButtonElement &&
    toggle.getAttribute("aria-expanded") === "true" &&
    !copilotElement.contains(event.target)
  ) {
    setPanelOpen(false);
  }
});
if (form instanceof HTMLFormElement && input instanceof HTMLInputElement) {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const message = input.value;
    input.value = "";
    void sendMessage(message);
  });
}

initializeVoiceInput();
window.addEventListener("pagehide", () => {
  stopVoiceInput({ abort: true, announce: false });
});

if (quickOptions instanceof HTMLElement && input instanceof HTMLInputElement) {
  const manifest = getAssistantPageManifest();
  for (const button of quickOptions.querySelectorAll("button")) {
    if (!(button instanceof HTMLButtonElement)) {
      continue;
    }
    const meetingUnavailable = (
      button.dataset.requiresMeeting === "true" &&
      typeof manifest.active_meeting_id !== "string"
    );
    const pageUnavailable = (
      typeof button.dataset.requiredPage === "string" &&
      button.dataset.requiredPage !== manifest.page_id
    );
    if (meetingUnavailable || pageUnavailable) {
      button.dataset.contextUnavailable = "true";
      button.disabled = true;
      button.title = meetingUnavailable
        ? "Open a meeting first to use this option."
        : "This option is available on the meeting history page.";
    }
  }

  quickOptions.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) {
      return;
    }
    const option = target.dataset.assistantOption;
    const navigationPrompt = NAVIGATION_PROMPTS.get(option);
    if (navigationPrompt !== undefined) {
      void sendMessage(navigationPrompt);
      return;
    }
    if (
      [
        "open_meeting_detail",
        "open_transcript",
        "open_transcript_upload",
        "open_confidential_notes",
      ].includes(option)
    ) {
      const meetingId = manifest.active_meeting_id;
      if (typeof meetingId !== "string") {
        return;
      }
      const prompts = {
        open_meeting_detail: `Open meeting details for ${meetingId}`,
        open_transcript: `Open the transcript for meeting ${meetingId}`,
        open_transcript_upload: `Add transcript for meeting ${meetingId}`,
        open_confidential_notes: (
          `Open confidential notes for meeting ${meetingId}`
        ),
      };
      void sendMessage(prompts[option]);
      return;
    }
    if (option === "create_meeting") {
      input.value = (
        "Plan a meeting titled [title] at [place] on " +
        "[YYYY-MM-DDTHH:MM+timezone] for 60 minutes. " +
        "Purpose: [purpose]. Personal gift: none."
      );
    } else if (option === "reschedule_meeting") {
      const meeting = manifest.active_meeting_id || "[meeting ID]";
      input.value = (
        `Reschedule meeting ${meeting} to [YYYY-MM-DDTHH:MM+timezone] ` +
        "for 60 minutes."
      );
    }
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
  });
}

import html
import json
from dataclasses import dataclass


PAGE_MANIFEST_VERSION = 1


@dataclass(frozen=True, slots=True)
class PageDefinition:
    page_id: str
    title: str
    content: str
    authenticated: bool = True


PAGE_DEFINITIONS = {
    "login": PageDefinition(
        page_id="login",
        title="Sign in",
        authenticated=False,
        content="""
<section class="login-card" aria-labelledby="login-title">
  <p class="eyebrow">Meeting Website Copilot</p>
  <h1 id="login-title">Welcome to Meetn</h1>
  <p class="lead">Review meetings and safely navigate protected content.</p>
  <a class="button button-primary button-wide" href="/api/v1/auth/google/start">
    Continue with Google
  </a>
  <p class="muted small">Your session stays in a secure HttpOnly cookie.</p>
</section>
""",
    ),
    "dashboard": PageDefinition(
        page_id="dashboard",
        title="Dashboard",
        content="""
<section class="page-heading">
  <div>
    <p class="eyebrow">Overview</p>
    <h1>Dashboard</h1>
    <p class="lead">Your latest meetings and protected workspace.</p>
  </div>
  <a class="button button-secondary" href="/meetings">View all meetings</a>
</section>
<section aria-labelledby="recent-meetings-title">
  <div class="section-heading">
    <h2 id="recent-meetings-title">Recent meetings</h2>
  </div>
  <div id="dashboard-meetings" class="card-grid" aria-live="polite">
    <p class="loading-state">Loading meetings…</p>
  </div>
</section>
""",
    ),
    "meeting_history": PageDefinition(
        page_id="meeting_history",
        title="Meeting history",
        content="""
<section class="page-heading">
  <div>
    <p class="eyebrow">Archive</p>
    <h1>Meeting history</h1>
    <p class="lead">Meetings you organize or participate in.</p>
  </div>
  <button id="meeting-form-toggle" class="button button-primary" type="button"
          aria-expanded="false" aria-controls="meeting-scheduler">
    Add or reschedule meeting
  </button>
</section>
<section id="meeting-scheduler" class="panel scheduler-panel"
         aria-labelledby="meeting-scheduler-title" hidden>
  <div class="section-heading">
    <div>
      <p class="eyebrow">Schedule</p>
      <h2 id="meeting-scheduler-title">Plan meeting details</h2>
    </div>
  </div>
  <form id="meeting-schedule-form" class="scheduler-form">
    <label>
      Scheduling action
      <select id="schedule-mode" name="mode">
        <option value="plan">Plan a new meeting</option>
        <option value="reschedule">Reschedule an existing meeting</option>
      </select>
    </label>
    <label id="schedule-existing-row" hidden>
      Existing meeting
      <select id="schedule-meeting-id" name="meeting_id"></select>
    </label>
    <label>
      Meeting title
      <input id="schedule-title" name="title" maxlength="160" required />
    </label>
    <label>
      Place
      <input id="schedule-place" name="place" maxlength="255" required />
    </label>
    <label>
      Date and time
      <input id="schedule-start-time" name="start_time"
             type="datetime-local" required />
    </label>
    <label>
      Duration
      <select id="schedule-duration" name="duration_minutes">
        <option value="30">30 minutes</option>
        <option value="60" selected>1 hour</option>
        <option value="90">1 hour 30 minutes</option>
        <option value="120">2 hours</option>
      </select>
    </label>
    <label class="form-wide">
      Purpose
      <textarea id="schedule-purpose" name="purpose" maxlength="1000"
                rows="3" required></textarea>
    </label>
    <label class="form-wide">
      Personal gift (optional)
      <input id="schedule-personal-gift" name="personal_gift"
             maxlength="255" />
    </label>
    <div class="form-wide button-row">
      <button id="schedule-submit" class="button button-primary" type="submit">
        Save meeting
      </button>
      <p id="schedule-form-status" class="muted form-status"
         role="status" aria-live="polite"></p>
    </div>
  </form>
</section>
<section aria-labelledby="meeting-list-title">
  <div class="search-row">
    <label for="meeting-search">Search meetings</label>
    <input id="meeting-search" type="search" autocomplete="off"
           placeholder="Search by title" />
  </div>
  <h2 id="meeting-list-title" class="visually-hidden">Meeting list</h2>
  <div id="meeting-list" class="stack" aria-live="polite">
    <p class="loading-state">Loading meeting history…</p>
  </div>
</section>
""",
    ),
    "meeting_detail": PageDefinition(
        page_id="meeting_detail",
        title="Meeting detail",
        content="""
<section class="page-heading">
  <div>
    <p class="eyebrow">Meeting</p>
    <h1 id="meeting-title">Meeting detail</h1>
    <p id="meeting-status" class="status-pill">Loading</p>
  </div>
  <a class="text-link" href="/meetings">Back to meeting history</a>
</section>
<div id="meeting-detail" class="detail-layout" aria-live="polite">
  <section class="panel" aria-labelledby="meeting-overview-title">
    <h2 id="meeting-overview-title">Overview</h2>
    <dl id="meeting-metadata" class="metadata-list"></dl>
  </section>
  <section class="panel" aria-labelledby="meeting-actions-title">
    <h2 id="meeting-actions-title">Protected resources</h2>
    <div id="meeting-resource-links" class="button-stack"></div>
  </section>
  <section class="panel panel-wide" aria-labelledby="recording-availability-title">
    <p class="eyebrow">Backend verified</p>
    <h2 id="recording-availability-title">Recording availability</h2>
    <p id="recording-availability-message" class="lead">Checking recording state…</p>
    <p id="recording-required-plan" class="muted" hidden></p>
    <div id="recording-alternative-actions" class="button-row"></div>
  </section>
  <section class="panel panel-wide" aria-labelledby="participants-title">
    <h2 id="participants-title">Participants</h2>
    <ul id="participant-list" class="clean-list"></ul>
  </section>
</div>
""",
    ),
    "transcript": PageDefinition(
        page_id="transcript",
        title="Transcript",
        content="""
<section class="page-heading">
  <div>
    <p class="eyebrow">Protected resource</p>
    <h1>Transcript</h1>
    <p class="lead">Available only to authorized meeting members.</p>
  </div>
  <a id="transcript-back-link" class="text-link" href="/meetings">
    Back to meeting
  </a>
</section>
<section class="panel" aria-labelledby="transcript-content-title">
  <h2 id="transcript-content-title">Transcript content</h2>
  <pre id="transcript-content" class="protected-content" aria-live="polite">Loading transcript…</pre>
</section>
<section id="transcript-upload-panel" class="panel transcript-upload-panel"
         aria-labelledby="transcript-upload-title" hidden>
  <p class="eyebrow">Organizer tool</p>
  <h2 id="transcript-upload-title">Add transcript</h2>
  <p class="muted">
    Paste transcript text or choose a UTF-8 plain-text file. Existing
    transcripts are never overwritten.
  </p>
  <form id="transcript-upload-form" class="transcript-form">
    <label for="transcript-input">Transcript text</label>
    <textarea id="transcript-input" name="content" rows="12" maxlength="200000"
              required placeholder="Paste the meeting transcript here"></textarea>
    <label for="transcript-file">Or choose a .txt file</label>
    <input id="transcript-file" name="transcript_file" type="file"
           accept=".txt,text/plain" />
    <p class="muted small">Maximum 200,000 characters. Plain text only.</p>
    <div class="button-row">
      <button id="transcript-submit" class="button button-primary" type="submit">
        Save transcript
      </button>
      <p id="transcript-upload-status" class="form-status" role="status"
         aria-live="polite"></p>
    </div>
  </form>
</section>
""",
    ),
    "confidential_notes": PageDefinition(
        page_id="confidential_notes",
        title="Confidential notes",
        content="""
<section class="page-heading">
  <div>
    <p class="eyebrow">Restricted resource</p>
    <h1>Confidential notes</h1>
    <p class="lead">Access is checked separately for every meeting.</p>
  </div>
  <a id="notes-back-link" class="text-link" href="/meetings">
    Back to meeting
  </a>
</section>
<section aria-labelledby="notes-list-title">
  <h2 id="notes-list-title" class="visually-hidden">Accessible notes</h2>
  <div id="confidential-note-list" class="stack" aria-live="polite">
    <p class="loading-state">Loading confidential notes…</p>
  </div>
</section>
""",
    ),
    "membership_plans": PageDefinition(
        page_id="membership_plans",
        title="Membership plans",
        content="""
<section class="page-heading centered-heading">
  <div>
    <p class="eyebrow">Membership</p>
    <h1>Choose the right plan</h1>
    <p class="lead">Plan information is illustrative in this prototype.</p>
  </div>
</section>
<section class="plan-grid" aria-label="Membership plans">
  <article class="plan-card">
    <p class="eyebrow">Starter</p>
    <h2>Meeting basics</h2>
    <p class="plan-price">Free</p>
    <ul><li>Meeting history</li><li>Meeting details</li></ul>
    <button class="button button-secondary" type="button" disabled>Current prototype</button>
  </article>
  <article class="plan-card featured-plan">
    <p class="eyebrow">Professional</p>
    <h2>Extended access</h2>
    <p class="plan-price">Coming soon</p>
    <ul><li>Transcript access when authorized</li><li>Advanced meeting tools</li></ul>
    <button class="button button-primary" type="button" disabled>Not available yet</button>
  </article>
  <article class="plan-card">
    <p class="eyebrow">Organization</p>
    <h2>Team controls</h2>
    <p class="plan-price">Contact us</p>
    <ul><li>Centralized membership</li><li>Organization policies</li></ul>
    <button class="button button-secondary" type="button" disabled>Not available yet</button>
  </article>
</section>
""",
    ),
}


def render_page(
    page_id: str,
    *,
    active_meeting_id: str | None = None,
) -> str:
    definition = PAGE_DEFINITIONS[page_id]
    manifest = {
        "version": PAGE_MANIFEST_VERSION,
        "page_id": definition.page_id,
        "active_meeting_id": active_meeting_id,
        "visible_meeting_ids": (
            [active_meeting_id] if active_meeting_id is not None else []
        ),
    }
    manifest_json = _safe_script_json(manifest)
    title = html.escape(definition.title)
    shell_class = "login-shell" if not definition.authenticated else "app-shell"
    header = _authenticated_header() if definition.authenticated else _login_header()
    assistant = _assistant_widget() if definition.authenticated else ""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="page-manifest-version" content="{PAGE_MANIFEST_VERSION}" />
  <title>{title} · Meetn</title>
  <link rel="stylesheet" href="/static/css/app.css?v=1" />
</head>
<body data-page-id="{html.escape(definition.page_id, quote=True)}">
  <div class="{shell_class}">
    {header}
    <main id="main-content" class="page-container">
      <div id="page-alert" class="page-alert" role="alert" hidden></div>
      {definition.content}
    </main>
    {assistant}
  </div>
  <script id="page-manifest" type="application/json">{manifest_json}</script>
  <script type="module" src="/static/js/theme.js?v=1"></script>
  <script type="module" src="/static/js/pages.js?v=1"></script>
  <script type="module" src="/static/js/copilot.js?v=1"></script>
</body>
</html>"""


def _safe_script_json(value: object) -> str:
    return (
        json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _login_header() -> str:
    return f"""
<header class="login-header">
  <a class="brand" href="/login" aria-label="Meetn sign in">Meetn</a>
  {_theme_settings()}
</header>
"""


def _authenticated_header() -> str:
    return f"""
<header class="site-header">
  <a class="brand" href="/dashboard" aria-label="Meetn dashboard">Meetn</a>
  <nav class="primary-nav" aria-label="Primary navigation">
    <a href="/dashboard">Dashboard</a>
    <a href="/meetings">Meetings</a>
    <a href="/plans" data-confirm-navigation="membership_plans">Plans</a>
  </nav>
  <div class="account-controls">
    {_theme_settings()}
    <span id="session-user" class="session-user" aria-live="polite"></span>
    <button id="logout-button" class="button button-ghost" type="button">Sign out</button>
  </div>
</header>
"""


def _theme_settings() -> str:
    return """
<details class="settings-menu">
  <summary aria-label="Open appearance settings">Settings</summary>
  <div class="settings-popover">
    <label for="theme-select">Appearance</label>
    <select id="theme-select" name="theme">
      <option value="system">System</option>
      <option value="light">Light</option>
      <option value="dark">Dark</option>
      <option value="soothing">Soothing</option>
      <option value="happy">Happy</option>
    </select>
    <span id="theme-status" class="visually-hidden" aria-live="polite"></span>
  </div>
</details>
"""


def _assistant_widget() -> str:
    return """
<aside id="copilot" class="copilot" aria-label="Website assistant">
  <button id="copilot-toggle" class="copilot-toggle" type="button"
          aria-expanded="false" aria-controls="copilot-panel">
    <span class="default-text">Ask Meetn</span>
    <span class="hover-text">tell me what u want today</span>
  </button>
  <section id="copilot-panel" class="copilot-panel" hidden>
    <header class="copilot-header">
      <div><p class="eyebrow">Assistant</p><h2>Where would you like to go?</h2></div>
      <button id="copilot-close" class="icon-button" type="button" aria-label="Close assistant">×</button>
    </header>
    <div id="copilot-options" class="copilot-options" aria-label="Quick options">
      <p class="copilot-option-label">Navigate</p>
      <button type="button" data-assistant-option="open_dashboard">Dashboard</button>
      <button type="button" data-assistant-option="open_meeting_history">Meetings</button>
      <button type="button" data-assistant-option="open_membership_plans">Plans</button>
      <button type="button" data-assistant-option="open_meeting_detail"
              data-requires-meeting="true">Meeting detail</button>
      <button type="button" data-assistant-option="open_transcript"
              data-requires-meeting="true">Transcript</button>
      <button type="button" data-assistant-option="open_transcript_upload"
              data-requires-meeting="true">Add transcript</button>
      <button type="button" data-assistant-option="open_confidential_notes"
              data-requires-meeting="true">Confidential notes</button>
      <button type="button" data-assistant-option="focus_meeting_search"
              data-required-page="meeting_history">Search meetings</button>
      <p class="copilot-option-label">Meeting actions</p>
      <button type="button" data-assistant-option="create_meeting">Plan meeting</button>
      <button type="button" data-assistant-option="reschedule_meeting">Reschedule</button>
    </div>
    <div id="copilot-messages" class="copilot-messages" aria-live="polite"></div>
    <form id="copilot-form" class="copilot-form">
      <label class="visually-hidden" for="copilot-input">Ask the website assistant</label>
      <input id="copilot-input" name="message" maxlength="2000" required
             autocomplete="off" placeholder="Open my meeting history" />
      <button id="copilot-voice-button" class="button button-secondary copilot-voice-button"
              type="button" aria-label="Speak your assistant request"
              aria-pressed="false" aria-controls="copilot-input"
              aria-describedby="copilot-voice-help copilot-voice-status">Speak</button>
      <button class="button button-primary" type="submit">Send</button>
      <p id="copilot-voice-help" class="copilot-voice-help">
        Voice is optional and may use your browser's speech service. Typing always works.
      </p>
      <span id="copilot-voice-status" class="visually-hidden" aria-live="polite"></span>
    </form>
  </section>
</aside>
"""

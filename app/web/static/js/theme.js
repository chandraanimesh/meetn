const THEME_STORAGE_KEY = "meetn.presentation-theme.v1";
const ALLOWED_THEMES = new Set([
  "system",
  "light",
  "dark",
  "soothing",
  "happy",
]);
const colorScheme = window.matchMedia("(prefers-color-scheme: dark)");
let selectedTheme = "system";

function readStoredTheme() {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return ALLOWED_THEMES.has(stored) ? stored : "system";
  } catch {
    return "system";
  }
}

function resolvedTheme(theme) {
  if (theme === "system") {
    return colorScheme.matches ? "dark" : "light";
  }
  return theme;
}

function announceTheme(theme) {
  const status = document.getElementById("theme-status");
  if (status instanceof HTMLElement) {
    status.textContent = `${theme[0].toUpperCase()}${theme.slice(1)} theme active.`;
  }
}

export function setPresentationTheme(
  theme,
  { persist = true, announce = true } = {},
) {
  if (!ALLOWED_THEMES.has(theme)) {
    return false;
  }
  selectedTheme = theme;
  document.documentElement.dataset.theme = resolvedTheme(theme);
  document.documentElement.dataset.themePreference = theme;

  const select = document.getElementById("theme-select");
  if (select instanceof HTMLSelectElement) {
    select.value = theme;
  }
  if (persist) {
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // The visual preference still applies when storage is unavailable.
    }
  }
  if (announce) {
    announceTheme(theme);
  }
  return true;
}

export function applyAssistantPresentation(presentation) {
  if (
    presentation === null ||
    typeof presentation !== "object" ||
    !ALLOWED_THEMES.has(presentation.theme)
  ) {
    return false;
  }
  return setPresentationTheme(presentation.theme, {
    persist: true,
    announce: true,
  });
}

selectedTheme = readStoredTheme();
setPresentationTheme(selectedTheme, { persist: false, announce: false });

const select = document.getElementById("theme-select");
if (select instanceof HTMLSelectElement) {
  select.value = selectedTheme;
  select.addEventListener("change", () => {
    setPresentationTheme(select.value);
  });
}

colorScheme.addEventListener("change", () => {
  if (selectedTheme === "system") {
    setPresentationTheme("system", { persist: false, announce: false });
  }
});

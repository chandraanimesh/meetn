export class ApiError extends Error {
  constructor(status, message, code = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

let csrfToken = null;

function requireSameOriginApiPath(path) {
  if (
    typeof path !== "string" ||
    path.startsWith("//") ||
    path.includes("\\") ||
    !(path.startsWith("/api/") || path.startsWith("/api/v1/"))
  ) {
    throw new TypeError("Only same-origin API paths are allowed.");
  }
  return path;
}

function redirectToLogin() {
  if (window.location.pathname === "/login") {
    return;
  }
  const currentPath = `${window.location.pathname}${window.location.search}`;
  window.location.assign(`/login?next=${encodeURIComponent(currentPath)}`);
}

async function readResponseBody(response) {
  if (response.status === 204) {
    return null;
  }
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export async function apiFetch(path, options = {}) {
  const apiPath = requireSameOriginApiPath(path);
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");
  if (options.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const method = String(options.method || "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    if (typeof csrfToken !== "string" || csrfToken.length === 0) {
      throw new ApiError(
        403,
        "The secure browser session is not ready. Reload and try again.",
        "CSRF_TOKEN_UNAVAILABLE",
      );
    }
    headers.set("X-CSRF-Token", csrfToken);
  }

  const response = await fetch(apiPath, {
    ...options,
    headers,
    credentials: "include",
  });
  const body = await readResponseBody(response);

  if (
    apiPath === "/api/v1/session" &&
    typeof body?.csrf_token === "string" &&
    body.csrf_token.length > 0
  ) {
    csrfToken = body.csrf_token;
  }

  if (response.status === 401) {
    redirectToLogin();
    throw new ApiError(401, "Please sign in to continue.", "AUTHENTICATION_REQUIRED");
  }
  if (response.status === 403) {
    throw new ApiError(
      403,
      "You do not have permission to view this resource.",
      body?.error?.code || "ACCESS_DENIED",
    );
  }
  if (!response.ok) {
    throw new ApiError(
      response.status,
      body?.error?.message || "The request could not be completed.",
      body?.error?.code || null,
    );
  }
  return body;
}

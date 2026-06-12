const stripTrailingSlash = (value = "") => value.replace(/\/+$/, "");

const configuredBackendUrl = stripTrailingSlash(process.env.REACT_APP_BACKEND_URL || "");
const browserOrigin = typeof window !== "undefined" ? stripTrailingSlash(window.location.origin) : "";

export const BACKEND_BASE_URL = configuredBackendUrl || browserOrigin;
export const API = `${BACKEND_BASE_URL}/api`;
export const WS_BASE_URL = BACKEND_BASE_URL.replace(/^http/i, (match) =>
  match.toLowerCase() === "https" ? "wss" : "ws"
);

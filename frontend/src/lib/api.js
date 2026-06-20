const stripTrailingSlash = (value = "") => value.replace(/\/+$/, "");

const browserOrigin = typeof window !== "undefined" ? stripTrailingSlash(window.location.origin) : "";
const isLocalBrowser = /localhost|127\.0\.0\.1/i.test(browserOrigin);
const fallbackBackendUrl = isLocalBrowser ? browserOrigin : "https://readyup-arena-api.onrender.com";
const configuredBackendUrl = stripTrailingSlash(process.env.REACT_APP_BACKEND_URL || fallbackBackendUrl);

export const BACKEND_BASE_URL = configuredBackendUrl || fallbackBackendUrl;
export const API = `${BACKEND_BASE_URL}/api`;
export const WS_BASE_URL = BACKEND_BASE_URL.replace(/^http/i, (match) =>
  match.toLowerCase() === "https" ? "wss" : "ws"
);

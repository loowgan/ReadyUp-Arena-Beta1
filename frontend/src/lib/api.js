const stripTrailingSlash = (value = "") => value.replace(/\/+$/, "");

const browserOrigin = typeof window !== "undefined" ? stripTrailingSlash(window.location.origin) : "";
const isLocalBrowser = /localhost|127\.0\.0\.1/i.test(browserOrigin);
const productionBackendUrl = "https://readyup-arena-api.onrender.com";
const fallbackBackendUrl = isLocalBrowser ? browserOrigin : productionBackendUrl;
const configuredBackendUrl = stripTrailingSlash(process.env.REACT_APP_BACKEND_URL || fallbackBackendUrl);
const frontendProxyBase = isLocalBrowser ? configuredBackendUrl : "/backend";

export const BACKEND_BASE_URL = configuredBackendUrl || fallbackBackendUrl;
export const API = `${frontendProxyBase}/api`;
export const HEALTH_API = `${frontendProxyBase}/health/ready`;
export const WS_BASE_URL = BACKEND_BASE_URL.replace(/^http/i, (match) =>
  match.toLowerCase() === "https" ? "wss" : "ws"
);

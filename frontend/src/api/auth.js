import client from "./client";

function getStorageWithToken() {
  if (sessionStorage.getItem("access")) return sessionStorage;
  if (localStorage.getItem("access")) return localStorage;
  return null;
}

export function getAccessToken() {
  const store = getStorageWithToken();
  return store ? store.getItem("access") : null;
}

export function clearTokens() {
  localStorage.removeItem("access");
  localStorage.removeItem("refresh");
  sessionStorage.removeItem("access");
  sessionStorage.removeItem("refresh");
}

function extractErr(error) {
  const d = error?.response?.data;
  if (!d) return "Network error, try again.";
  if (typeof d === "string") return d;
  if (d.detail) return d.detail;
  const k = Object.keys(d)[0];
  if (k) {
    const v = d[k];
    const msg = Array.isArray(v) ? v[0] : String(v);
    // Clarify if it's a short field message
    if (msg.includes("at least") && msg.includes("characters")) {
      return `${k.charAt(0).toUpperCase() + k.slice(1)} must be at least 8 characters long.`;
    }
    return msg;
  }
  return "Something went wrong. Please try again.";
}

export async function login(username, password, rememberMe = false) {
  try {
    const { data } = await client.post("/token/", { username, password });

    const store = rememberMe ? localStorage : sessionStorage;

    // Clear both first, then set in the chosen one
    clearTokens();
    store.setItem("access", data.access);
    store.setItem("refresh", data.refresh);

    // Optional: remember flag (not strictly required but nice to have)
    store.setItem("remember_me", rememberMe ? "1" : "0");

    return data;
  } catch (e) {
    throw new Error(extractErr(e)); // 🔴 important
  }
}

export async function register(payload) {
  try {
    const { data } = await client.post("/register/", payload);
    return data;
  } catch (e) {
    throw new Error(extractErr(e));   // 🔴 important
  }
}

export function logout() {
  clearTokens();
}
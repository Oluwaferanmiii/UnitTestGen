import client from "./client";

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

export async function login(username, password) {
  try {
    const { data } = await client.post("/token/", { username, password });
    localStorage.setItem("access", data.access);
    localStorage.setItem("refresh", data.refresh);
    return data;
  } catch (e) {
    throw new Error(extractErr(e));   // 🔴 important
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
  localStorage.removeItem("access");
  localStorage.removeItem("refresh");
}
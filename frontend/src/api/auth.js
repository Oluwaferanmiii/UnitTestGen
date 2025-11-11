import client from "./client";

export async function login(username, password) {
  const { data } = await client.post("/token/", { username, password });
  localStorage.setItem("access", data.access);
  localStorage.setItem("refresh", data.refresh);
  return data;
}

export async function register(payload) {
  // expects your Django /api/register/ (you said it's available)
  const { data } = await client.post("/register/", payload);
  return data;
}

export function logout() {
  localStorage.removeItem("access");
  localStorage.removeItem("refresh");
}
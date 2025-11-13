// src/api/sessions.js
import client from "./client";

export async function listSessions() {
  const { data } = await client.get("/sessions/");
  return data; // array of sessions (each with items[])
}

export async function createSession() {
  const { data } = await client.post("/sessions/", {}); // empty session
  return data; // new session
}

export async function getSession(id) {
  const { data } = await client.get(`/sessions/${id}/`);
  return data; // session with items[]
}

export async function updateSession(id, payload) {
  const { data } = await client.patch(`/sessions/${id}/`, payload);
  return data;
}

export async function deleteSession(id) {
  const { data } = await client.delete(`/sessions/${id}/`);
  return data;
}
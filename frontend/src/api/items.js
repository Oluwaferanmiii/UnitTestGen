// src/api/items.js
import client from "./client";

export async function addItem(sessionId, { pasted_code, file, modelMode = "base" }) {
  if (file) {
    const form = new FormData();
    form.append("uploaded_code", file);
    form.append("mode", modelMode); // ✅ send mode with multipart

    const { data } = await client.post(`/sessions/${sessionId}/items/`, form);
    return data;
  }

  const { data } = await client.post(`/sessions/${sessionId}/items/`, {
    pasted_code,
    mode: modelMode, // ✅ send mode with JSON
  });

  return data;
}

export async function regenerate(sessionId, itemId, modelMode = "base") {
  const params = new URLSearchParams();
  if (itemId) params.set("item_id", itemId);
  params.set("mode", modelMode); // ✅ backend reads query_params too

  const qs = params.toString() ? `?${params.toString()}` : "";
  const { data } = await client.post(`/regenerate/${sessionId}/${qs}`);
  return data;
}
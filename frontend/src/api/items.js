// src/api/items.js
import client from "./client";

export async function addItem(sessionId, { pasted_code, file }) {
  if (file) {
    const form = new FormData();
    form.append("uploaded_code", file);
    const { data } = await client.post(
      `/sessions/${sessionId}/items/`,
      form,
      { headers: { "Content-Type": "multipart/form-data" } }
    );
    return data;
  }
  const { data } = await client.post(`/sessions/${sessionId}/items/`, {
    pasted_code,
  });
  return data;
}

export async function regenerate(sessionId, itemId) {
  const query = itemId ? `?item_id=${itemId}` : "";
  const { data } = await client.post(`/regenerate/${sessionId}/${query}`);
  return data;
}
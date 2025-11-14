// src/api/client.js
import axios from "axios";
import { getAccessToken, clearTokens } from "./auth";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE,
});

// --------- helpers for refresh token storage ---------
function getRefreshToken() {
  // Prefer sessionStorage if present, otherwise localStorage
  return (
    sessionStorage.getItem("refresh") ||
    localStorage.getItem("refresh") ||
    null
  );
}

function setAccessToken(access) {
  // Put the new access token in the same place as the refresh token
  if (sessionStorage.getItem("refresh")) {
    sessionStorage.setItem("access", access);
  } else if (localStorage.getItem("refresh")) {
    localStorage.setItem("access", access);
  } else {
    // Fallback (should rarely happen)
    localStorage.setItem("access", access);
  }
}

// --------- attach access token on every request ---------
client.interceptors.request.use((config) => {
  const token = getAccessToken(); // now checks both storages
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshing = false;
let queue = [];

// --------- handle 401 + token refresh ---------
client.interceptors.response.use(
  (r) => r,
  async (error) => {
    const status = error?.response?.status;
    const original = error.config;

    if (status === 401 && !original._retry) {
      const refresh = getRefreshToken();

      // If we don't have a refresh token, just log out
      if (!refresh) {
        clearTokens();
        window.location.replace("/login");
        throw error;
      }

      if (refreshing) {
        // queue requests while a refresh is in flight
        return new Promise((res, rej) => queue.push({ res, rej }));
      }

      original._retry = true;
      refreshing = true;

      try {
        const { data } = await axios.post(
          `${import.meta.env.VITE_API_BASE}/token/refresh/`,
          { refresh }
        );

        // Save new access token in the correct storage
        setAccessToken(data.access);

        // Update the header for the original request
        original.headers.Authorization = `Bearer ${data.access}`;

        // Resolve queued requests
        queue.forEach(({ res }) => res(client(original)));
        queue = [];

        return client(original);
      } catch (e) {
        // Fail all queued requests
        queue.forEach(({ rej }) => rej(e));
        queue = [];

        clearTokens();
        window.location.replace("/login");
        throw e;
      } finally {
        refreshing = false;
      }
    }

    throw error;
  }
);

export default client;
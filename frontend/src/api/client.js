// src/api/client.js
import axios from "axios";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE,
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("access");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing = false;
let queue = [];

client.interceptors.response.use(
  (r) => r,
  async (error) => {
    const status = error?.response?.status;
    const original = error.config;
    if (status === 401 && !original._retry) {
      if (refreshing) {
        // queue requests while a refresh is in flight
        return new Promise((res, rej) => queue.push({ res, rej }));
      }
      original._retry = true;
      refreshing = true;
      try {
        const refresh = localStorage.getItem("refresh");
        const { data } = await axios.post(
          `${import.meta.env.VITE_API_BASE}/token/refresh/`,
          { refresh }
        );
        localStorage.setItem("access", data.access);
        original.headers.Authorization = `Bearer ${data.access}`;
        queue.forEach(({ res }) => res(client(original)));
        queue = [];
        return client(original);
      } catch (e) {
        queue.forEach(({ rej }) => rej(e));
        queue = [];
        localStorage.removeItem("access");
        localStorage.removeItem("refresh");
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
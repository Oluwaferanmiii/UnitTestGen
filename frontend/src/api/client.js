import axios from "axios";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE, // e.g. http://127.0.0.1:8000/api
});

// attach access token if present
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("access");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default client;
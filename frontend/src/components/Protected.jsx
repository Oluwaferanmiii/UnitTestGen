// src/components/Protected.jsx (updated)
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getAccessToken } from "../api/auth";

export default function Protected({ children }) {
  const nav = useNavigate();
  const [token] = useState(() => getAccessToken());

  useEffect(() => {
    if (!token) {
      nav("/login", { replace: true });
    }
  }, [token, nav]);

  return token ? children : null;
}
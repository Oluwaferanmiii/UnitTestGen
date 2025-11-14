// src/components/SessionWatcher.jsx
import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { clearTokens, getAccessToken } from "../api/auth";

const INACTIVITY_MS = 30 * 60 * 1000; // 30 minutes

export default function SessionWatcher({ children }) {
  const nav = useNavigate();
  const location = useLocation();
  const timerRef = useRef(null);

  useEffect(() => {
    function resetTimer() {
      const token = getAccessToken();
      if (!token) return; // no active session → nothing to track

      if (timerRef.current) clearTimeout(timerRef.current);

      timerRef.current = setTimeout(() => {
        // Inactive for too long → log out
        clearTokens();
        sessionStorage.setItem("sessionExpired", "1");
        nav("/login", { replace: true });
      }, INACTIVITY_MS);
    }

    const events = ["click", "keydown", "mousemove", "scroll"];
    events.forEach((ev) => window.addEventListener(ev, resetTimer));

    // start timer on mount / route change
    resetTimer();

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      events.forEach((ev) => window.removeEventListener(ev, resetTimer));
    };
  }, [nav, location]);

  // 🔴 THIS IS CRITICAL – without this you get a blank screen
  return children;
}
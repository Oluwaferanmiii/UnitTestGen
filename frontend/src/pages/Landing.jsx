import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Logo from "../components/Logo";
import Btn from "../components/Btn";

export default function Landing() {
  const nav = useNavigate();
  const ASSET_BASE = import.meta.env.BASE_URL;

  // ✅ Theme
  const [themeMode, setThemeMode] = useState(
    () => localStorage.getItem("unittestlab:theme") || "dark"
  );

  useEffect(() => {
    localStorage.setItem("unittestlab:theme", themeMode);

    // optional but nice: helps if you later want CSS to react to theme
    document.documentElement.setAttribute("data-theme", themeMode);
  }, [themeMode]);

  const isLight = themeMode === "light";

  // ✅ Landing-only theme tokens
  const theme = {
    pageBg: isLight
      ? "linear-gradient(135deg,#f4f6fb 0%, #eef2ff 55%, #dbeafe 100%)"
      : "linear-gradient(120deg,#0b0b0c 55%, #1a1040 100%)",
    pageText: isLight ? "#0f172a" : "#fff",

    toggleBg: isLight ? "rgba(255,255,255,0)" : "rgba(0,0,0,0.35)",
    toggleBorder: isLight
      ? "1px solid rgba(15,23,42,0.12)"
      : "1px solid rgba(255,255,255,0.16)",

    // Button base styles (Landing only)
    btnBg: isLight ? "rgba(255,255,255,0.35)" : "rgba(0,0,0,0.20)",
    btnBorder: isLight
      ? "1px solid rgba(15,23,42,0.22)"
      : "1px solid rgba(255,255,255,0.22)",
    btnText: isLight ? "#0f172a" : "#fff",

    // Hover styles (Landing only)
    btnHoverBg: isLight ? "rgba(37,99,235,0.10)" : "rgba(255,255,255,0.08)",
    btnHoverBorder: isLight
      ? "1px solid rgba(37,99,235,0.35)"
      : "1px solid rgba(255,255,255,0.35)",
  };

  // Simple hover handlers (no extra state needed)
  const onBtnEnter = (e) => {
    e.currentTarget.style.background = theme.btnHoverBg;
    e.currentTarget.style.border = theme.btnHoverBorder;
  };

  const onBtnLeave = (e) => {
    e.currentTarget.style.background = theme.btnBg;
    e.currentTarget.style.border = theme.btnBorder;
  };

  const landingBtnStyle = {
    background: theme.btnBg,
    border: theme.btnBorder,
    color: theme.btnText,
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        alignItems: "center",
        justifyItems: "center",
        color: theme.pageText,
        background: theme.pageBg,
        padding: 24,
      }}
    >
      {/* ✅ Theme toggle */}
      <button
        type="button"
        title={isLight ? "Switch to dark mode" : "Switch to light mode"}
        onClick={() => setThemeMode((m) => (m === "light" ? "dark" : "light"))}
        style={{
          position: "fixed",
          top: 18,
          right: 18,
          padding: "8px 12px",
          borderRadius: 999,
          background: theme.toggleBg,
          border: theme.toggleBorder,
          cursor: "pointer",
          backdropFilter: "blur(10px)",
          zIndex: 9999,
        }}
      >
        <img
          src={`${ASSET_BASE}${isLight ? "light_mode.svg" : "dark_mode.svg"}`}
          alt={isLight ? "Light mode" : "Dark mode"}
          style={{ width: 18, height: 18 }}
        />
      </button>

      {/* Logo top-left (large variant for landing) */}
      <div style={{ position: "absolute", top: 24 }}>
        <Logo size="large" />
      </div>

      {/* Buttons (large) */}
      <div style={{ display: "grid", gap: 24, width: "fit-content" }}>
        <Btn
          size="medium"
          variant="outline"
          onClick={() => nav("/login")}
          styleOverride={landingBtnStyle}
          onMouseEnter={onBtnEnter}
          onMouseLeave={onBtnLeave}
        >
          Sign in
        </Btn>

        <Btn
          size="medium"
          variant="outline"
          onClick={() => nav("/register")}
          styleOverride={landingBtnStyle}
          onMouseEnter={onBtnEnter}
          onMouseLeave={onBtnLeave}
        >
          Sign up
        </Btn>
      </div>
    </div>
  );
}
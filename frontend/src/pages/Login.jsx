import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { login } from "../api/auth";
import Logo from "../components/Logo";
import Btn from "../components/Btn";

export default function Login() {
  const nav = useNavigate();
  const [form, setForm] = useState({ username: "", password: "" });
  const [remember, setRemember] = useState(true);
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);
  const ASSET_BASE = import.meta.env.BASE_URL;

  // ✅ Theme 
  const [themeMode, setThemeMode] = useState(
    () => localStorage.getItem("unittestlab:theme") || "dark"
  );

  useEffect(() => {
    localStorage.setItem("unittestlab:theme", themeMode);
  }, [themeMode]);

  const isLight = themeMode === "light";

  // ✅ Theme tokens
  const theme = {
    pageBg: isLight
      ? "linear-gradient(135deg,#f4f6fb 0%, #e7efff 55%, #dbeafe 100%)"
      : "linear-gradient(120deg,#0b0b0c 55%, #1F044F 100%)",
    pageText: isLight ? "#0f172a" : "#fff",

    usernameInputBg: isLight ? "#ffffff" : "#d4d4d4",
    usernameInputText: isLight ? "#0f172a" : "#111",
    usernameInputBorder: isLight ? "1px solid rgba(15,23,42,0.12)" : "none",

    passwordInputBg: isLight ? "#ffffff" : "#0b0b0c",
    passwordInputText: isLight ? "#0f172a" : "#fff",
    passwordInputBorder: isLight
      ? "1px solid rgba(15,23,42,0.18)"
      : "1px solid rgba(255,255,255,0.6)",

    infoText: isLight ? "rgba(15,23,42,0.75)" : "#e5e7eb",
    linkGreen: isLight ? "#2563eb" : "#22c55e",

    // keep purple button in dark; use blue in light
    btnBg: isLight ? "#2563eb" : "#5B32A4",

    toggleBg: isLight ? "rgba(255, 255, 255, 0)" : "rgba(0,0,0,0.35)",
    toggleText: isLight ? "#0f172a" : "#fff",
    toggleBorder: isLight
      ? "1px solid rgba(15,23,42,0.12)"
      : "1px solid rgba(255,255,255,0.16)",
  };

  useEffect(() => {
    if (sessionStorage.getItem("sessionExpired") === "1") {
      setInfo("Session expired, please log in again.");
      sessionStorage.removeItem("sessionExpired");
    }
  }, []);

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await login(form.username, form.password, remember);
      nav("/dashboard", { replace: true });
    } catch (e) {
      console.error("login error:", e);
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: theme.pageBg, // ✅ theme-aware
        color: theme.pageText, // ✅ theme-aware
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        alignItems: "center",
        padding: 32,
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
          color: theme.toggleText,
          border: theme.toggleBorder,
          cursor: "pointer",
          backdropFilter: "blur(10px)",
        }}
      >
        <img
          src={`${ASSET_BASE}${isLight ? "light_mode.svg" : "dark_mode.svg"}`}
          alt={isLight ? "Light mode" : "Dark mode"}
          style={{ width: 18, height: 18 }}
        />
      </button>

      {/* LEFT SIDE: FORM */}
      <div
        style={{
          maxWidth: 500,
          justifySelf: "center",
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <h1 style={{ marginBottom: 24, fontSize: "2.5rem", fontWeight: 700 }}>
          Sign in
        </h1>

        <form onSubmit={onSubmit} style={{ display: "grid", gap: 18 }}>
          <input
            placeholder="Username"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            style={{
              width: 428,
              padding: "16px 20px",
              borderRadius: 12,
              border: theme.usernameInputBorder, // ✅ theme-aware
              background: theme.usernameInputBg, // ✅ theme-aware
              color: theme.usernameInputText, // ✅ theme-aware
              fontSize: "16px",
            }}
          />
          <input
            type="password"
            placeholder="Password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            style={{
              width: 428,
              padding: "16px 20px",
              borderRadius: 12,
              border: theme.passwordInputBorder, // ✅ theme-aware
              background: theme.passwordInputBg, // ✅ theme-aware
              color: theme.passwordInputText, // ✅ theme-aware
              fontSize: "16px",
            }}
          />
          {/* Remember me */}
          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 14,
              opacity: 0.9,
            }}
          >
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
            />
            <span>Remember me on this device</span>
          </label>

          {err && (
            <div style={{ color: "#f87171", fontSize: 14 }}>{err}</div>
          )}

          {/* Legacy/Unused Code */}
          {/* Forgot Password */}
          {/* <div style={{ textAlign: "right", fontSize: 14 }}>
            <Link
              to="/forgot-password"
              style={{ color: "rgba(255,255,255,0.75)", textDecoration: "none" }}
            >
              Forgot Password?
            </Link>
          </div> */}
          {info && (
            <div style={{ color: theme.infoText, fontSize: 14 }}>{info}</div>
          )}

          {/* Purple button */}
          <Btn
            type="submit"
            size="medium"
            variant="solid"
            disabled={loading}
            styleOverride={{
              background: theme.btnBg, // theme-aware (purple in dark, blue in light)
              color: "#fff",
              border: "none",
            }}
          >
            {loading ? "Logging in..." : "Login"}
          </Btn>

          <div style={{ marginTop: 4 }}>
            Don’t have an account?{" "}
            <Link to="/register" style={{ color: theme.linkGreen }}>
              Sign up
            </Link>
          </div>
        </form>
      </div>

      {/* RIGHT SIDE: LOGO */}
      <div style={{ justifySelf: "center" }}>
        <Logo size="medium" />
      </div>
    </div>
  );
}
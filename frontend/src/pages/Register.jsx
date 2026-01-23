import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { register } from "../api/auth";
import Logo from "../components/Logo";
import Btn from "../components/Btn";

export default function Register() {
  const nav = useNavigate();
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
    confirm: "",
  });
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
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

    darkInputBg: isLight ? "#ffffff" : "#0b0b0c",
    darkInputText: isLight ? "#0f172a" : "#fff",
    darkInputBorder: isLight
      ? "1px solid rgba(15,23,42,0.18)"
      : "1px solid rgba(255,255,255,0.6)",

    linkGreen: isLight ? "#2563eb" : "#22c55e",

    // keep purple button in dark; use blue in light
    btnBg: isLight ? "#2563eb" : "#5B32A4",

    toggleBg: isLight ? "rgba(255, 255, 255, 0.03)" : "rgba(0,0,0,0.35)",
    toggleText: isLight ? "#0f172a" : "#fff",
    toggleBorder: isLight
      ? "1px solid rgba(15,23,42,0.12)"
      : "1px solid rgba(255,255,255,0.16)",
  };

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    setOk("");

    if (form.password !== form.confirm) {
      setErr("Passwords do not match.");
      return;
    }

    try {
      await register({
        username: form.username,
        email: form.email,
        password: form.password,
      });
      setOk("Registration successful. Please sign in.");
      setTimeout(() => nav("/login"), 800);
    } catch (e) {
      setErr(e.message);
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

      {/* LEFT: form */}
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
          Sign up
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
              fontSize: 16,
            }}
          />

          <input
            placeholder="Email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            style={{
              width: 428,
              padding: "16px 20px",
              borderRadius: 12,
              border: theme.darkInputBorder, // ✅ theme-aware
              background: theme.darkInputBg, // ✅ theme-aware
              color: theme.darkInputText, // ✅ theme-aware
              fontSize: 16,
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
              border: theme.darkInputBorder, // ✅ theme-aware
              background: theme.darkInputBg, // ✅ theme-aware
              color: theme.darkInputText, // ✅ theme-aware
              fontSize: 16,
            }}
          />

          <input
            type="password"
            placeholder="Retype Password"
            value={form.confirm}
            onChange={(e) => setForm({ ...form, confirm: e.target.value })}
            style={{
              width: 428,
              padding: "16px 20px",
              borderRadius: 12,
              border: theme.darkInputBorder, // ✅ theme-aware
              background: theme.darkInputBg, // ✅ theme-aware
              color: theme.darkInputText, // ✅ theme-aware
              fontSize: 16,
            }}
          />

          {err && <div style={{ color: "#f87171" }}>{err}</div>}
          {ok && <div style={{ color: "#22c55e" }}>{ok}</div>}

          {/* Purple CTA, same feel as login */}
          <Btn
            type="submit"
            size="medium"
            variant="solid"
            disabled={false}
            styleOverride={{
              background: theme.btnBg, // ✅ theme-aware
              color: "#fff",
              border: "none",
            }}
          >
            Register
          </Btn>

          <div style={{ marginTop: 4 }}>
            Already have an account?{" "}
            <Link to="/login" style={{ color: theme.linkGreen }}>
              Login
            </Link>
          </div>
        </form>
      </div>

      <div style={{ justifySelf: "center" }}>
        <Logo size="medium" />
      </div>
    </div>
  );
}
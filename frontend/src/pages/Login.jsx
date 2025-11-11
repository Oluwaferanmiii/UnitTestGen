import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { login } from "../api/auth";
import Logo from "../components/Logo";
import Btn from "../components/Btn";

export default function Login() {
  const nav = useNavigate();
  const [form, setForm] = useState({ username: "", password: "" });
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await login(form.username, form.password);
      nav("/dashboard", { replace: true });
    } catch {
      setErr("Invalid credentials or server error.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(120deg,#0b0b0c 55%, #1F044F 100%)",
        color: "#fff",
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        alignItems: "center",
        padding: 32,
      }}
    >
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
              border: "none",
              background: "#d4d4d4",
              color: "#111",
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
              border: "1px solid rgba(255,255,255,0.6)",
              background: "#0b0b0c",
              color: "#fff",
              fontSize: "16px",
            }}
          />

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

          {err && <div style={{ color: "#f87171" }}>{err}</div>}

          {/* Purple button (matches Figma) */}
          <Btn
            type="submit"
            size="medium"
            variant="solid"
            disabled={loading}
            styleOverride={{
              background: "#5B32A4",
              color: "#fff",
              border: "none",
            }}
          >
            {loading ? "Logging in..." : "Login"}
          </Btn>

          <div style={{ marginTop: 4 }}>
            Don’t have an account?{" "}
            <Link to="/register" style={{ color: "#22c55e" }}>
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
import { useState } from "react";
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

  async function onSubmit(e) {
    e.preventDefault();
    setErr(""); setOk("");

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
    } catch {
      setErr("Could not register. Try a different username/email.");
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
              border: "none",
              background: "#d4d4d4",
              color: "#111",
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
              border: "1px solid rgba(255,255,255,0.6)",
              background: "#0b0b0c",
              color: "#fff",
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
              border: "1px solid rgba(255,255,255,0.6)",
              background: "#0b0b0c",
              color: "#fff",
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
              border: "1px solid rgba(255,255,255,0.6)",
              background: "#0b0b0c",
              color: "#fff",
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
              background: "#5B32A4",
              color: "#fff",
              border: "none",
            }}
          >
            Register
          </Btn>

          <div style={{ marginTop: 4 }}>
            Already have an account?{" "}
            <Link to="/login" style={{ color: "#22c55e" }}>
              Login
            </Link>
          </div>
        </form>
      </div>

      {/* RIGHT: big logo to match Figma */}
      <div style={{ justifySelf: "center" }}>
        <Logo size="medium" />
      </div>
    </div>
  );
}
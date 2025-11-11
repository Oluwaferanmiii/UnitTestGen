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
    setErr(""); setLoading(true);
    try {
      await login(form.username, form.password);
      nav("/dashboard", { replace: true });
    } catch (e) {
      setErr("Invalid credentials or server error.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(120deg,#0b0b0c 55%, #1F044F 100%)",
      color: "#fff",
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      alignItems: "center",
      padding: 32,
      gap: 24,
    }}>
      <div style={{ maxWidth: 520, marginLeft: "10vw" }}>
        <h1 style={{ marginBottom: 24 }}>Sign in</h1>
        <form onSubmit={onSubmit} style={{ display: "grid", gap: 16 }}>
          <input
            placeholder="Username"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            style={{ padding: 16, borderRadius: 12, border: "1px solid #555", background:"#d4d4d4" }}
          />
          <input
            type="password"
            placeholder="Password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            style={{ padding: 16, borderRadius: 12, border: "1px solid #555", background:"#0b0b0c", color:"#fff" }}
          />
          {err && <div style={{ color: "#f87171" }}>{err}</div>}
          <Btn type="submit" variant="solid" disabled={loading}>
            {loading ? "Logging in..." : "Login"}
          </Btn>
          <div style={{ marginTop: 4 }}>
            Don’t have an account? <Link to="/register" style={{ color: "#22c55e" }}>Sign up</Link>
          </div>
        </form>
      </div>

      <div style={{ justifySelf: "center" }}>
        <Logo size={40} />
      </div>
    </div>
  );
}
import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { register } from "../api/auth";
import Logo from "../components/Logo";
import Btn from "../components/Btn";

export default function Register() {
  const nav = useNavigate();
  const [form, setForm] = useState({ username:"", email:"", password:"", confirm:"" });
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
      await register({ username: form.username, email: form.email, password: form.password });
      setOk("Registration successful. Please sign in.");
      setTimeout(() => nav("/login"), 800);
    } catch (e) {
      setErr("Could not register. Try a different username/email.");
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
        <h1 style={{ marginBottom: 24 }}>Sign up</h1>
        <form onSubmit={onSubmit} style={{ display: "grid", gap: 16 }}>
          <input placeholder="Username"
            value={form.username}
            onChange={(e)=>setForm({...form, username:e.target.value})}
            style={{ padding:16, borderRadius:12, border:"1px solid #555", background:"#d4d4d4" }}
          />
          <input placeholder="Email"
            value={form.email}
            onChange={(e)=>setForm({...form, email:e.target.value})}
            style={{ padding:16, borderRadius:12, border:"1px solid #555", background:"#0b0b0c", color:"#fff" }}
          />
          <input type="password" placeholder="Password"
            value={form.password}
            onChange={(e)=>setForm({...form, password:e.target.value})}
            style={{ padding:16, borderRadius:12, border:"1px solid #555", background:"#0b0b0c", color:"#fff" }}
          />
          <input type="password" placeholder="Retype Password"
            value={form.confirm}
            onChange={(e)=>setForm({...form, confirm:e.target.value})}
            style={{ padding:16, borderRadius:12, border:"1px solid #555", background:"#0b0b0c", color:"#fff" }}
          />
          {err && <div style={{ color: "#f87171" }}>{err}</div>}
          {ok && <div style={{ color: "#22c55e" }}>{ok}</div>}
          <Btn type="submit" variant="solid">Register</Btn>
          <div style={{ marginTop: 4 }}>
            Already have an account? <Link to="/login" style={{ color: "#22c55e" }}>Login</Link>
          </div>
        </form>
      </div>

      <div style={{ justifySelf: "center" }}>
        <Logo size={40} />
      </div>
    </div>
  );
}
import { useNavigate } from "react-router-dom";
import Logo from "../components/Logo";
import Btn from "../components/Btn";

export default function Landing() {
  const nav = useNavigate();
  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(120deg,#0b0b0c 55%, #1F044F 100%)",
      display: "grid",
      gridTemplateColumns: "1fr",
      alignItems: "center",
      justifyItems: "center",
      color: "#fff",
      padding: 24,
    }}>
      <div style={{ position: "absolute", top: 24, left: 24 }}>
        <Logo />
      </div>

      <div style={{ display: "grid", gap: 24, width: 420, maxWidth: "90%" }}>
        <Btn variant="solid" onClick={() => nav("/login")}>Sign in</Btn>
        <Btn variant="outline" onClick={() => nav("/register")}>Sign up</Btn>
      </div>
    </div>
  );
}
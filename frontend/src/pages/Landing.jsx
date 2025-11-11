import { useNavigate } from "react-router-dom";
import Logo from "../components/Logo";
import Btn from "../components/Btn";

export default function Landing() {
  const nav = useNavigate();

  return (
    <div
      className="app-gradient"
      style={{
        minHeight: "100vh",
        display: "grid",
        alignItems: "center",
        justifyItems: "center",
        color: "#fff",
        padding: 24,
      }}
    >
      {/* Logo top-left (large variant for landing) */}
      <div style={{ position: "absolute", top: 24, left: 24 }}>
        <Logo size="large" />
      </div>

      {/* Buttons (large) */}
      <div style={{ display: "grid", gap: 24, width: "fit-content" }}>
        <Btn size="large" variant="outline" onClick={() => nav("/login")}>
          Sign in
        </Btn>
        <Btn size="large" variant="outline" onClick={() => nav("/register")}>
          Sign up
        </Btn>
      </div>
    </div>
  );
}
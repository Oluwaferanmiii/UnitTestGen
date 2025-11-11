import { useNavigate } from "react-router-dom";
import { logout } from "../api/auth";

export default function Dashboard() {
  const nav = useNavigate();

  return (
    <div style={{
      minHeight: "100vh",
      display: "grid",
      gridTemplateColumns: "320px 1fr",
      background: "linear-gradient(120deg,#0b0b0c 55%, #1a1040 100%)",
      color: "#fff",
    }}>
      {/* Sidebar */}
      <aside style={{ borderRight: "1px solid #2c2c2c", padding: 16 }}>
        <div style={{ fontWeight: 800, marginBottom: 12 }}>UNITTESTLAB</div>
        <button style={{ width: "100%", padding: 12, borderRadius: 10, marginBottom: 16 }}>
          New Session
        </button>
        <div style={{ opacity: 0.8, marginBottom: 8 }}>History</div>
        <div style={{ display: "grid", gap: 8 }}>
          {/* session items will go here */}
          <div style={{ height: 36, background: "#262626", borderRadius: 10 }} />
          <div style={{ height: 36, background: "#262626", borderRadius: 10 }} />
          <div style={{ height: 36, background: "#262626", borderRadius: 10 }} />
        </div>
      </aside>

      {/* Main */}
      <main style={{ padding: 20 }}>
        <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h2 style={{ margin: 0 }}>Session Title</h2>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={() => { logout(); nav("/login"); }} style={{ padding: 10, borderRadius: 10 }}>
              Logout
            </button>
          </div>
        </header>

        {/* Empty state for now */}
        <div style={{ display: "grid", placeItems: "center", height: "70vh" }}>
          <h1>Start New Session</h1>
        </div>
      </main>
    </div>
  );
}
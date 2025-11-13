import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { logout } from "../api/auth";
import Logo from "../components/Logo";

export default function Dashboard() {
  const nav = useNavigate();

  // Placeholder sessions until we wire the API
  const [sessions] = useState([
    { id: 1, title: "Test History palindrome" },
    { id: 2, title: "…Test History 2…" },
    { id: 3, title: "…Add Test…" },
  ]);
  const [selectedId, setSelectedId] = useState(null);
  const [hoveredId, setHoveredId] = useState(null);

  // Styles
  const sidebarBg =
    "linear-gradient(180deg, rgba(10,10,10,0.98) 0%, rgba(12,8,24,0.98) 100%)";
  const appBg = "linear-gradient(120deg,#0b0b0c 55%, #1a1040 100%)";

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        gridTemplateColumns: "320px 1fr",
        background: appBg,
        color: "#fff",
      }}
    >
      {/* Sidebar */}
      <aside
        style={{
          borderRight: "1px solid #2c2c2c",
          padding: 16,
          background: sidebarBg, // darker than main
        }}
      >
        {/* Logo (no duplicate text) */}
        <div style={{ marginBottom: 1 }}>
          <Logo width={200} height={50} /> {/* adjust number if you want it bigger */}
        </div>

        {/* New Session */}
        <button
          style={{
            width: "75%",
            padding: 12,
            borderRadius: 12,
            marginBottom: 16,
            marginTop: 12,
            background: "#d4d4d4",
            color: "#111",
            border: "1px solid rgba(255,255,255,0.15)",
            cursor: "pointer",
          }}
        >
          New Session
        </button>

        {/* History */}
        <div style={{ opacity: 0.9, marginBottom: 8, fontWeight: 600 }}>
          Test History
        </div>
        <div style={{ display: "grid", gap: 10 }}>
          {sessions.map((s) => {
            const isSelected = selectedId === s.id;
            const isHovered = hoveredId === s.id;
            const active = isSelected || isHovered;

            return (
              <div
                key={s.id}
                onClick={() => setSelectedId(s.id)}
                onMouseEnter={() => setHoveredId(s.id)}
                onMouseLeave={() => setHoveredId(null)}
                style={{
                  padding: "10px 12px",
                  borderRadius: 12,
                  cursor: "pointer",
                  transition: "background 160ms ease, border-color 160ms ease",
                  background: active ? "#3a3a3a" : "transparent",
                  border: active
                    ? "1px solid rgba(255,255,255,0.25)"
                    : "1px solid rgba(255,255,255,0.12)",
                }}
              >
                <div
                  style={{
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    fontSize: 14,
                  }}
                  title={s.title}
                >
                  {s.title}
                </div>
              </div>
            );
          })}
        </div>
      </aside>

      {/* Main */}
      <main style={{ padding: 20 }}>
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 16,
            borderBottom: "1px solid rgba(255,255,255,0.08)",
            paddingBottom: 8,
          }}
        >
          <h2 style={{ margin: 0 }}>Session Title</h2>

          <button
            onClick={() => {
              logout();
              nav("/login");
            }}
            style={{
              padding: "10px 14px",
              borderRadius: 12,
              background: "#e5e7eb",
              color: "#111",
              border: "1px solid rgba(255,255,255,0.15)",
              cursor: "pointer",
              marginRight: 20,
              marginBottom: 5,
            }}
          >
            Logout
          </button>
        </header>

        {/* Empty state for now */}
        <div style={{ display: "grid", placeItems: "center", height: "70vh" }}>
          <h1>Start New Session</h1>
        </div>
      </main>
    </div>
  );
}
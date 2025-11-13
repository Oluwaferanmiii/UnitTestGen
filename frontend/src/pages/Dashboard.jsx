// src/pages/Dashboard.jsx
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { logout } from "../api/auth";
import {
  listSessions,
  createSession,
  getSession,
  deleteSession,          // ✅ import deleteSession
} from "../api/sessions";
import { addItem } from "../api/items";
import Logo from "../components/Logo";
import CodeEditor from "../components/CodeEditor";

export default function Dashboard() {
  const nav = useNavigate();
  const qc = useQueryClient();

  // ---------------- UI state ----------------
  const [activeId, setActiveId] = useState(null);
  const [mode, setMode] = useState("paste"); // "paste" | "upload"
  const [file, setFile] = useState(null);
  const [fileErr, setFileErr] = useState("");
  const [toast, setToast] = useState("");
  const fileRef = useRef(null);
  const [code, setCode] = useState("");
  const [menuOpenId, setMenuOpenId] = useState(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteId, setDeleteId] = useState(null);

  // ---------------- Data fetch ----------------
  const sessionsQ = useQuery({
    queryKey: ["sessions"],
    queryFn: listSessions,
  });

  // 1️⃣ Auto-select most recent session
  useEffect(() => {
    if (!sessionsQ.data || sessionsQ.data.length === 0) return;
    if (activeId == null) {
      setActiveId(sessionsQ.data[0].id);
    }
  }, [sessionsQ.data, activeId]);

  // 2️⃣ Handle outside-click to close menu
  useEffect(() => {
    function handleClickOutside(e) {
      // If no menu open, ignore
      if (menuOpenId === null) return;

      // If click happened inside any dropdown/menu/button → do NOT close
      const menu = document.getElementById(`menu-${menuOpenId}`);
      const btn = document.getElementById(`btn-${menuOpenId}`);

      if (menu?.contains(e.target) || btn?.contains(e.target)) {
        return;
      }

      // Otherwise → close it
      setMenuOpenId(null);
    }

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [menuOpenId]);

  const activeSessionQ = useQuery({
    queryKey: ["session", activeId],
    queryFn: () => getSession(activeId),
    enabled: !!activeId,
  });


  // ---------------- Mutations ----------------
  const newSessionMut = useMutation({
    mutationFn: createSession,
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: ["sessions"] });
      setActiveId(created.id);
      setToast("New session created.");
      setTimeout(() => setToast(""), 1200);
    },
    onError: () => setToast("Failed to create session."),
  });

  const addItemMut = useMutation({
    mutationFn: async (payload) => {
      if (!activeId) throw new Error("No active session.");
      return addItem(activeId, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["session", activeId] });
      qc.invalidateQueries({ queryKey: ["sessions"] });
      setToast("Generated tests.");
      setTimeout(() => setToast(""), 1200);
      setFile(null);
      setFileErr("");
      if (fileRef.current) {
        fileRef.current.value = ""; // ✅ clear file input visually
      }
    },
    onError: (e) => {
      setToast(
        typeof e?.message === "string" ? e.message : "Generation failed."
      );
      setTimeout(() => setToast(""), 1800);
    },
  });

  const deleteMut = useMutation({
    mutationFn: deleteSession,
    onSuccess: (_data, deletedId) => {
      qc.invalidateQueries({ queryKey: ["sessions"] });

      // If deleting active session → clear active
      if (deletedId === activeId) {
        setActiveId(null);
      }

      setToast("Session deleted.");
      setTimeout(() => setToast(""), 1200);
    },
    onError: () => {
      setToast("Failed to delete session.");
      setTimeout(() => setToast(""), 1500);
    },
  });

  // ---------------- Handlers ----------------
  function handleFileChange(e) {
    setFileErr("");
    const f = e.target.files?.[0];
    if (!f) {
      setFile(null);
      return;
    }
    if (!f.name.endsWith(".py")) {
      setFileErr("Only .py files are allowed.");
      setFile(null);
      return;
    }
    if (f.size > 512 * 1024) {
      setFileErr("File is too large (max 512 KB).");
      setFile(null);
      return;
    }
    setFile(f);
  }

  // History row style helper
  function rowStyle(id) {
    const selected = id === activeId;
    return {
      padding: "10px 14px",
      borderRadius: 12,
      border: "1px solid rgba(255,255,255,.14)",
      background: selected ? "rgba(255,255,255,0.06)" : "transparent",
      color: "#fff",
      cursor: "pointer",
    };
  }

  const sessions = useMemo(() => sessionsQ.data ?? [], [sessionsQ.data]);

  const activeItems = [...(activeSessionQ.data?.items ?? [])].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at)
  );

  // ---------------- Render ----------------
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        gridTemplateColumns: "320px 1fr",
        background: "linear-gradient(120deg,#0b0b0c 55%, #1a1040 100%)",
        color: "#fff",
      }}
    >
      {/* Sidebar */}
      <aside
        style={{
          borderRight: "1px solid rgba(255,255,255,.15)",
          padding: 16,
          background:
            "linear-gradient(rgba(10,10,11,.98) 0%, rgba(12,8,24,.98) 100%)",
        }}
      >
        <div style={{ marginBottom: 12 }}>
          <Logo width={200} height={75} />
        </div>

        <button
          onClick={() => newSessionMut.mutate()}
          disabled={newSessionMut.isLoading}
          style={{
            width: "75%",
            padding: 12,
            borderRadius: 15,
            marginBottom: 16,
            background: "#d4d4d4",
            color: "#111",
            border: "none",
            cursor: "pointer",
            fontWeight: 600,
          }}
        >
          {newSessionMut.isLoading ? "Creating…" : "New Session"}
        </button>

        <div style={{ opacity: 0.9, marginBottom: 10, fontWeight: 600 }}>
          Test History
        </div>

        <div style={{ display: "grid", gap: 10 }}>
          {sessions.map((s) => (
            <div key={s.id} style={{ position: "relative" }}>
              <div
                onClick={(e) => {
                  e.stopPropagation();     // <--- prevent closing menu when selecting session
                  setActiveId(s.id);
                  setMenuOpenId(null);     // close menu when switching sessions
                }}
                style={rowStyle(s.id)}
                onMouseEnter={(e) => {
                  if (s.id !== activeId)
                    e.currentTarget.style.background =
                      "rgba(255,255,255,0.04)";
                }}
                onMouseLeave={(e) => {
                  if (s.id !== activeId)
                    e.currentTarget.style.background = "transparent";
                }}
              >
                {s.title ? s.title : `Session #${s.id}`}
              </div>

              {/* 3-dot menu button */}
              <button
                id={`btn-${s.id}`}
                onClick={(e) => {
                  e.stopPropagation();
                  setMenuOpenId(s.id);
                  setDeleteId(s.id);
                }}
                style={{
                  position: "absolute",
                  right: 10,
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "transparent",
                  border: "none",
                  color: "#fff",
                  fontSize: 18,
                  cursor: "pointer",
                  padding: 0,
                }}
              >
                ⋮
              </button>

              {/* Dropdown menu */}
              {menuOpenId === s.id && (
                <div
                  id={`menu-${s.id}`}
                  onClick={(e) => e.stopPropagation()} 
                  style={{
                    position: "absolute",
                    right: 0,
                    top: 36,
                    background: "rgba(20,20,25,.95)",
                    border: "1px solid rgba(255,255,255,.15)",
                    padding: "6px 10px",
                    borderRadius: 8,
                    zIndex: 50,
                    width: 120,
                  }}
                >
                  <div
                    onClick={() => {
                      setMenuOpenId(null);
                      setShowDeleteModal(true);
                    }}
                    style={{
                      padding: "6px 6px",
                      cursor: "pointer",
                      color: "#f87171",
                    }}
                  >
                    Delete
                  </div>
                </div>
              )}
            </div>
          ))}

          {sessions.length === 0 && (
            <div style={{ opacity: 0.7, fontSize: 14 }}>
              No sessions yet — create one above.
            </div>
          )}
        </div>
      </aside>

      {/* Main */}
      <main style={{ padding: 20 }}>
        {/* Header */}
        <header style={{ marginBottom: 16 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <h2 style={{ margin: 0 }}>Session Title</h2>
            <button
              onClick={() => {
                logout();
                qc.clear();
                nav("/login");
              }}
              style={{
                padding: "10px 14px",
                borderRadius: 12,
                background: "#eaeaea",
                color: "#111",
                border: "none",
                cursor: "pointer",
              }}
            >
              Logout
            </button>
          </div>
          <div
            style={{
              height: 1,
              background:
                "linear-gradient(to right, rgba(255,255,255,.14), rgba(255,255,255,.06))",
              marginTop: 12,
              marginLeft: -20,
              marginRight: -20,
            }}
          />
        </header>

        {/* Composer */}
        <div style={{ marginTop: 12 }}>
          <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
            <button
              type="button"
              onClick={() => {
                setMode("paste");
                setFile(null);
                setFileErr("");
              }}
              style={{
                padding: "8px 12px",
                borderRadius: 10,
                background: mode === "paste" ? "#2b2b35" : "transparent",
                color: "#fff",
                border: "1px solid rgba(255,255,255,.18)",
                cursor: "pointer",
              }}
            >
              Paste code
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("upload");
                setFileErr("");
              }}
              style={{
                padding: "8px 12px",
                borderRadius: 10,
                background: mode === "upload" ? "#2b2b35" : "transparent",
                color: "#fff",
                border: "1px solid rgba(255,255,255,.18)",
                cursor: "pointer",
              }}
            >
              Upload .py
            </button>
          </div>

          {/* Paste mode */}
          {mode === "paste" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const trimmed = code.trim();
                if (!trimmed || !activeId) return;
                addItemMut.mutate({ pasted_code: trimmed });
                setCode("");
              }}
              style={{ display: "flex", gap: 12, alignItems: "stretch" }}
            >
              <CodeEditor value={code} onChange={setCode} />
              <button
                type="submit"
                style={{
                  padding: "12px 18px",
                  borderRadius: 12,
                  background: "#5B32A4",
                  color: "#fff",
                  border: "none",
                  cursor: "pointer",
                  alignSelf: "flex-start",
                }}
                disabled={addItemMut.isLoading || !activeId}
              >
                {addItemMut.isLoading ? "Generating…" : "Generate"}
              </button>
            </form>
          )}

          {/* Upload mode */}
          {mode === "upload" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!file) {
                  setFileErr("Choose a .py file first.");
                  return;
                }
                if (!activeId) return;
                addItemMut.mutate({ file });
              }}
              style={{
                display: "flex",
                gap: 12,
                alignItems: "center",
                background: "#0b0b0c",
                border: "1px solid rgba(255,255,255,.2)",
                borderRadius: 12,
                padding: 12,
              }}
            >
              <input
                ref={fileRef}
                type="file"
                accept=".py"
                onChange={handleFileChange}
                style={{ color: "#fff" }}
              />
              <button
                type="submit"
                style={{
                  padding: "10px 16px",
                  borderRadius: 12,
                  background: "#5B32A4",
                  color: "#fff",
                  border: "none",
                  cursor: "pointer",
                }}
                disabled={addItemMut.isLoading || !activeId}
              >
                {addItemMut.isLoading ? "Uploading…" : "Generate"}
              </button>
            </form>
          )}

          {fileErr && (
            <div style={{ color: "#f87171", marginTop: 8 }}>{fileErr}</div>
          )}
        </div>

        {/* Results */}
        {activeItems.length > 0 && (
          <div style={{ marginTop: 20, display: "grid", gap: 16 }}>
            {activeItems.map((it) => (
              <div
                key={it.id}
                style={{
                  background: "rgba(255,255,255,0.03)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  borderRadius: 12,
                  padding: 16,
                }}
              >
                {it.pasted_code && (
                  <>
                    <div style={{ opacity: 0.8, marginBottom: 6 }}>
                      User code:
                    </div>
                    <pre
                      style={{
                        margin: 0,
                        whiteSpace: "pre-wrap",
                        fontFamily:
                          "ui-monospace, SFMono-Regular, Menlo, monospace",
                        fontSize: 13,
                      }}
                    >
                      {it.pasted_code}
                    </pre>
                    <div
                      style={{
                        margin: "10px 0",
                        height: 1,
                        background: "rgba(255,255,255,0.12)",
                      }}
                    />
                  </>
                )}
                <div style={{ opacity: 0.8, marginBottom: 6 }}>
                  Generated tests:
                </div>
                <pre
                  style={{
                    margin: 0,
                    whiteSpace: "pre-wrap",
                    fontFamily:
                      "ui-monospace, SFMono-Regular, Menlo, monospace",
                    fontSize: 13,
                  }}
                >
                  {it.generated_tests || "# (empty)"}
                </pre>
              </div>
            ))}
          </div>
        )}

        {/* Empty state */}
        {!activeSessionQ.isLoading && activeItems.length === 0 && (
          <div
            style={{
              display: "grid",
              placeItems: "center",
              height: "50vh",
              opacity: 0.8,
            }}
          >
            <h1>Start New Session</h1>
          </div>
        )}

        {/* Toast */}
        {toast && (
          <div
            style={{
              position: "fixed",
              bottom: 18,
              left: "50%",
              transform: "translateX(-50%)",
              background: "rgba(40,40,48,.92)",
              border: "1px solid rgba(255,255,255,.15)",
              padding: "10px 14px",
              borderRadius: 10,
              fontSize: 14,
            }}
          >
            {toast}
          </div>
        )}
      </main>

      {/* Delete modal */}
      {showDeleteModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.55)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 200,
          }}
          onClick={() => setShowDeleteModal(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "rgba(20,20,25,1)",
              padding: 24,
              borderRadius: 12,
              width: 360,
              border: "1px solid rgba(255,255,255,.12)",
            }}
          >
            <h3 style={{ marginTop: 0, marginBottom: 12 }}>
              Delete this session?
            </h3>
            <p style={{ opacity: 0.8, fontSize: 14, marginBottom: 20 }}>
              This action cannot be undone.
            </p>

            <div
              style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}
            >
              <button
                style={{
                  padding: "8px 14px",
                  borderRadius: 8,
                  border: "1px solid rgba(255,255,255,.25)",
                  background: "transparent",
                  color: "#fff",
                  cursor: "pointer",
                }}
                onClick={() => setShowDeleteModal(false)}
              >
                Cancel
              </button>

              <button
                style={{
                  padding: "8px 14px",
                  borderRadius: 8,
                  background: "#e11d48",
                  color: "#fff",
                  border: "none",
                  cursor: "pointer",
                }}
                onClick={() => {
                  if (deleteId != null) {
                    deleteMut.mutate(deleteId); 
                  }
                  setShowDeleteModal(false);
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
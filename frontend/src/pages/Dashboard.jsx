// src/pages/Dashboard.jsx
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { logout } from "../api/auth";
import {
  listSessions,
  createSession,
  getSession,
  deleteSession, 
  updateSession,
} from "../api/sessions";
import { addItem, regenerate } from "../api/items";
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
  const [isDragging, setIsDragging] = useState(false);
  const [copiedId, setCopiedId] = useState(null);
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [renameId, setRenameId] = useState(null);
  const [renameValue, setRenameValue] = useState("");
  const [showSearchModal, setShowSearchModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [modelMode, setModelMode] = useState(() => {
  return localStorage.getItem("unittestlab:modelMode") || "base";
  });

  useEffect(() => {
    localStorage.setItem("unittestlab:modelMode", modelMode);
  }, [modelMode]);

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
    onMutate: () => {
    setToast("Generation started…");
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
      const data = e?.response?.data;
      let msg =
        (data && (data.error || data.detail)) ||
        e?.message ||
        "Generation failed.";

      setToast(msg);
      setTimeout(() => setToast(""), 1800);
    },
  });

  const isGenerating = addItemMut.isPending; 

  const deleteMut = useMutation({
    mutationFn: deleteSession,
    onSuccess: (_data, deletedId) => {
      // Get current sessions from cache (before invalidation)
      const current = qc.getQueryData(["sessions"]) || [];
      const remaining = current.filter((s) => s.id !== deletedId);

      // Immediately update the cache so the sidebar stays in sync
      qc.setQueryData(["sessions"], remaining);
      qc.invalidateQueries({ queryKey: ["sessions"] });

      // If we just deleted the active session, move to next one (if any)
      if (deletedId === activeId) {
        const next = remaining.length ? remaining[0].id : null;
        setActiveId(next);
      }

      setToast("Session deleted.");
      setTimeout(() => setToast(""), 1200);
    },
    onError: () => {
      setToast("Failed to delete session.");
      setTimeout(() => setToast(""), 1500);
    },
  });

  const renameMut = useMutation({
    mutationFn: ({ id, title }) => updateSession(id, { title }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["sessions"] });
      qc.invalidateQueries({ queryKey: ["session", vars.id] });

      setToast("Session renamed.");
      setTimeout(() => setToast(""), 1200);
    },
    onError: () => {
      setToast("Failed to rename session.");
      setTimeout(() => setToast(""), 1500);
    },
  });

const regenMut = useMutation({
  mutationFn: ({ sessionId, itemId, modelMode }) => regenerate(sessionId, itemId, modelMode),

  onMutate: () => {
    setToast("Regeneration started…");
  },

  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ["session", activeId] });
    setToast("Regenerated tests.");
    setTimeout(() => setToast(""), 1200);
  },

  onError: () => {
    setToast("Regeneration failed.");
    setTimeout(() => setToast(""), 1500);
  },
});

  const isRegenerating = regenMut.isPending;
  const isBusy = isGenerating || isRegenerating;

  // ---------------- Handlers ----------------
  async function handleCopyTests(text, itemId) {
    if (!text) return;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        // Fallback
        const ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setCopiedId(itemId);
      setTimeout(() => setCopiedId(null), 1000); // show "Copied" for 1s
    } catch (err) {
      console.error("Copy failed", err);
      setToast("Failed to copy tests.");
      setTimeout(() => setToast(""), 1500);
    }
  }

  function handleDownloadTests(text, itemId) {
    if (!text) return;

    // Attempt to extract test function name
    let filename = `tests_item_${itemId}.py`;  // fallback

    const match = text.match(/def\s+(test_[a-zA-Z0-9_]+)\s*\(/);
    if (match && match[1]) {
      filename = `${match[1]}.py`;
    }

    const blob = new Blob([text], { type: "text/x-python;charset=utf-8" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function validateAndSetFile(f) {
    setFileErr("");

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

  function handleFileChange(e) {
    const f = e.target.files?.[0];
    validateAndSetFile(f);
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

  // 🔍 Filtered search results (by title OR item code/tests)
  const searchResults = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return [];

    return sessions.filter((s) => {
      const title = (s.title || `Session #${s.id}`).toLowerCase();
      const inTitle = title.includes(q);

      const inItems = (s.items || []).some((it) => {
        const pasted = (it.pasted_code || "").toLowerCase();
        const tests = (it.generated_tests || "").toLowerCase();
        return pasted.includes(q) || tests.includes(q);
      });

      return inTitle || inItems;
    });
  }, [searchQuery, sessions]);

  const activeItems = activeId
    ? [...(activeSessionQ.data?.items ?? [])].sort(
        (a, b) => new Date(b.created_at) - new Date(a.created_at)
      )
    : [];

  const activeTitle =
  activeSessionQ.data?.title ||
  (activeId ? `Session #${activeId}` : "Session Title");

  // ---------------- Render ----------------
  return (
    <div
      style={{
        height: "100vh",
        display: "grid",
        gridTemplateColumns: "320px 1fr",
        background: "linear-gradient(120deg,#0b0b0c 55%, #1a1040 100%)",
        color: "#fff",
        overflow: "hidden",
      }}
    >
      {/* Sidebar */}
      <aside
        style={{
          borderRight: "1px solid rgba(255,255,255,.15)",
          padding: 16,
          background:
            "linear-gradient(rgba(10,10,11,.98) 0%, rgba(12,8,24,.98) 100%)",
          height: "100vh", 
          overflowY: "auto", 
        }}
      >
        <div style={{ marginBottom: 12 }}>
          <Logo width={200} height={75} />
        </div>

        {/* New Session button */}
        <button
          onClick={() => newSessionMut.mutate()}
          disabled={newSessionMut.isLoading}
          style={{
            width: "100%",
            padding: 12,
            borderRadius: 15,
            marginBottom: 5,
            background: "transparent",
            color: "#fff",
            border: "none",
            cursor: "pointer",
            fontWeight: 600,
            transition: "0.15s ease",
            opacity: newSessionMut.isLoading ? 0.7 : 1,
            display: "flex",
            alignItems: "center",
            gap: 10,           
            justifyContent: "flex-start",
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.background = "rgba(255,255,255,0.1)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.background = "transparent")
          }
        >
          <img
            src="New_session.svg" 
            alt=""
            style={{ width: 18, height: 18, opacity: 0.9 }}
          />
          {newSessionMut.isLoading ? "Creating…" : "New session"}
        </button>
        
        {/* search button */}
        <button
          onClick={() => setShowSearchModal(true)}
          style={{
            width: "100%",
            padding: 12,
            borderRadius: 15,
            marginBottom: 16,
            background: "transparent",
            color: "#fff",
            border: "none",
            cursor: "pointer",
            fontWeight: 600,
            transition: "0.15s ease",
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-start",
            gap: 10,
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.background = "rgba(255,255,255,0.1)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.background = "transparent")
          }
        >
          <img
            src="/search.svg"
            alt=""
            style={{ width: 18, height: 18, opacity: 0.9 }}
          />
          Search sessions
        </button>

        <div
          style={{
            opacity: 0.9,
            marginBottom: 10,
            fontWeight: 600,
          }}
        >
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
                    width: 140,
                  }}
                >
                  <div
                    onClick={() => {
                      setMenuOpenId(null);
                      setRenameId(s.id);
                      setRenameValue(s.title || "New Session");
                      setShowRenameModal(true);
                    }}
                    style={{
                      padding: "6px 6px",
                      cursor: "pointer",
                      color: "#e5e7eb",
                      borderBottom: "1px solid rgba(255,255,255,.12)",
                      marginBottom: 4,
                    }}
                  >
                    Rename
                  </div>

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
      <main style={{ 
        padding: 20,
        height: "100vh",
        overflowY: "auto",
        boxSizing: "border-box",
        }}>
        {/* Header */}
        <header style={{ marginBottom: 16 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <h2 style={{ margin: 0 }}>{activeTitle}</h2>
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
            {/* ✅ Model dropdown pill */}
            <div style={{ marginLeft: 8, display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ opacity: 0.75, fontSize: 13 }}>Model</span>
              <select
                value={modelMode}
                onChange={(e) => setModelMode(e.target.value)}
                style={{
                  padding: "7px 10px",
                  borderRadius: 10,
                  background: "rgba(255,255,255,0.06)",
                  color: "#fff",
                  border: "1px solid rgba(255,255,255,.18)",
                  cursor: "pointer",
                  outline: "none",
                }}
              >
                <option value="base" style={{ color: "#111" }}>
                  Base (Standard)
                </option>
                <option value="edge" style={{ color: "#111" }}>
                  Edge (Edge-case)
                </option>
              </select>
            </div>
          </div>

          {/* Paste mode */}
          {mode === "paste" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const trimmed = code.trim();
                if (!trimmed || !activeId) return;
                addItemMut.mutate({ pasted_code: trimmed, modelMode });
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
                  background: isGenerating ? "#4a278a" : "#5B32A4",
                  color: "#fff",
                  border: "none",
                  cursor: isGenerating ? "wait" : "pointer",
                  opacity: isGenerating ? 0.85 : 1,
                  alignSelf: "flex-start",
                }}
                disabled={isBusy  || !activeId}
              >
                {isGenerating ? "Generating…" : "Generate"}
              </button>
            </form>
          )}

          {mode === "upload" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!file) {
                  setFileErr("Choose a .py file first.");
                  return;
                }
                if (!activeId) return;
                addItemMut.mutate({ file, modelMode });
              }}
              style={{
                display: "flex",
                gap: 12,
                alignItems: "center",
              }}
            >
              {/* Dropzone / clickable area */}
              <div
                onClick={() => {
                  if (fileRef.current) fileRef.current.click();
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setIsDragging(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setIsDragging(false);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setIsDragging(false);

                  let f =
                    (e.dataTransfer.files && e.dataTransfer.files[0]) ||
                    (e.dataTransfer.items &&
                      e.dataTransfer.items[0]?.kind === "file" &&
                      e.dataTransfer.items[0].getAsFile());

                  if (f) {
                    validateAndSetFile(f);
                  }
                }}
                style={{
                  flex: 1,
                  padding: 12,
                  borderRadius: 12,
                  background: isDragging ? "#111827" : "#0b0b0c",
                  border: isDragging
                    ? "1px dashed rgba(255,255,255,.6)"
                    : "1px solid rgba(255,255,255,.2)",
                  transition: "background 120ms ease, border 120ms ease",
                  cursor: "pointer",
                  fontSize: 14,
                  color: "#e5e5e5",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <span>
                  {file ? `Selected file: ${file.name}` : "Drop .py file here or click to choose"}
                </span>
              </div>

              {/* Hidden native input, still used for click-to-select */}
              <input
                ref={fileRef}
                type="file"
                accept=".py"
                onChange={handleFileChange}
                style={{ display: "none" }}
              />

              <button
                type="submit"
                style={{
                  padding: "10px 16px",
                  borderRadius: 12,
                  background: isGenerating ? "#4a278a" : "#5B32A4",
                  color: "#fff",
                  border: "none",
                  cursor: isGenerating ? "wait" : "pointer",
                  opacity: isGenerating ? 0.85 : 1,
                  whiteSpace: "nowrap",
                }}
                disabled={isBusy || !activeId}
              >
                {isGenerating ? "Generating…" : "Generate"}
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
                  {/* Header row for Generated tests + actions */}
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: 6,
                    }}
                  >
                    <div style={{ opacity: 0.8 }}>Generated tests:</div>

                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      {/* Copy button */}
                      <button
                        type="button"
                        onClick={() => handleCopyTests(it.generated_tests, it.id)}
                        style={{
                          border: "none",
                          background: "transparent",
                          cursor: "pointer",
                          padding: 4,
                          display: "flex",
                          alignItems: "center",
                          gap: 4,
                        }}
                        title="Copy tests to clipboard"
                      >
                        {copiedId === it.id ? (
                          <span style={{ fontSize: 12, color: "#a7f3d0" }}>Copied</span>
                        ) : (
                          <img
                            src="/copy.svg"
                            alt="Copy"
                            style={{ width: 16, height: 16 }}
                          />
                        )}
                      </button>

                      {/* Regenerate button */}
                      <button
                        type="button"
                        disabled={isBusy}
                        onClick={() =>
                          regenMut.mutate({ sessionId: activeId, itemId: it.id, modelMode })
                        }
                        style={{
                          border: "none",
                          background: "transparent",
                          cursor: "pointer",
                          padding: 4,
                        }}
                        title="Regenerate tests for this code"
                      >
                        <img
                          src="/Reload.svg"       // make sure reload.svg is in /public
                          alt="Regenerate"
                          style={{ width: 16, height: 16 }}
                        />
                      </button>

                      {/* Download button */}
                      <button
                        type="button"
                        onClick={() => handleDownloadTests(it.generated_tests, it.id)}
                        style={{
                          border: "none",
                          background: "transparent",
                          cursor: "pointer",
                          padding: 4,
                        }}
                        title="Download tests as .py"
                      >
                        <img
                          src="/download.svg" 
                          alt="Download"
                          style={{ width: 16, height: 16 }}
                        />
                      </button>
                    </div>
                  </div>

                  {/* Actual test code */}
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
              top: 75,
              right: 30,
              background: "rgba(40,40,48,.92)",
              border: "1px solid rgba(255,255,255,.15)",
              padding: "10px 14px",
              borderRadius: 10,
              fontSize: 14,
              zIndex: 999, 
            }}
          >
            {toast}
          </div>
        )}
      </main>
      
      {/* Search modal */}
      {showSearchModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.55)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 205,
          }}
          onClick={() => setShowSearchModal(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "rgba(20,20,25,1)",
              padding: 24,
              borderRadius: 12,
              width: 500,
              border: "1px solid rgba(255,255,255,.12)",
              maxHeight: "70vh",
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}
          >
            <h3 style={{ margin: 0 }}>Search test history</h3>
            <p style={{ margin: 0, opacity: 0.8, fontSize: 13 }}>
              Search by session title or code/tests within that session.
            </p>

            <input
              type="text"
              autoFocus
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Type to search…"
              style={{
                marginTop: 6,
                width: "100%",
                padding: "8px 10px",
                borderRadius: 8,
                border: "1px solid rgba(255,255,255,.25)",
                background: "rgba(15,15,20,1)",
                color: "#fff",
                fontSize: 14,
              }}
            />

            <div
              style={{
                marginTop: 8,
                overflowY: "auto",
                flex: 1,
                borderRadius: 8,
                border: "1px solid rgba(255,255,255,.12)",
                padding: 6,
                background: "rgba(10,10,15,1)",
              }}
            >
              {searchQuery.trim() === "" && (
                <div style={{ opacity: 0.7, fontSize: 13, padding: 6 }}>
                  Start typing to search your sessions…
                </div>
              )}

              {searchQuery.trim() !== "" && searchResults.length === 0 && (
                <div style={{ opacity: 0.7, fontSize: 13, padding: 6 }}>
                  No matches found.
                </div>
              )}

              {searchResults.map((s) => (
                <div
                  key={s.id}
                  onClick={() => {
                    setActiveId(s.id);
                    setShowSearchModal(false);
                    setSearchQuery("");
                  }}
                  style={{
                    padding: "8px 10px",
                    borderRadius: 8,
                    marginBottom: 4,
                    cursor: "pointer",
                    background: "rgba(255,255,255,0.03)",
                    border: "1px solid rgba(255,255,255,0.12)",
                  }}
                >
                  <div style={{ fontSize: 14, fontWeight: 500 }}>
                    {s.title || `Session #${s.id}`}
                  </div>
                  <div style={{ fontSize: 12, opacity: 0.7, marginTop: 2 }}>
                    {s.items?.length
                      ? `${s.items.length} item${s.items.length > 1 ? "s" : ""}`
                      : "No items yet"}
                  </div>
                </div>
              ))}
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                marginTop: 8,
              }}
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
                onClick={() => {
                  setShowSearchModal(false);
                  setSearchQuery("");
                }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rename modal */}
      {showRenameModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.55)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 210,
          }}
          onClick={() => setShowRenameModal(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "rgba(20,20,25,1)",
              padding: 24,
              borderRadius: 12,
              width: 380,
              border: "1px solid rgba(255,255,255,.12)",
            }}
          >
            <h3 style={{ marginTop: 0, marginBottom: 12 }}>
              Rename session
            </h3>

            <label style={{ fontSize: 14, opacity: 0.9 }}>
              New title
            </label>
            <input
              type="text"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              style={{
                marginTop: 6,
                width: "100%",
                padding: "8px 10px",
                borderRadius: 8,
                border: "1px solid rgba(255,255,255,.25)",
                background: "rgba(15,15,20,1)",
                color: "#fff",
                fontSize: 14,
              }}
              maxLength={120}
            />

            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: 10,
                marginTop: 18,
              }}
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
                onClick={() => setShowRenameModal(false)}
              >
                Cancel
              </button>

              <button
                style={{
                  padding: "8px 14px",
                  borderRadius: 8,
                  background: "#6366f1",
                  color: "#fff",
                  border: "none",
                  cursor: "pointer",
                  opacity: renameMut.isLoading ? 0.7 : 1,
                }}
                disabled={renameMut.isLoading}
                onClick={() => {
                  const trimmed = renameValue.trim() || "New Session";
                  if (!renameId) return;

                  renameMut.mutate({ id: renameId, title: trimmed });
                  setShowRenameModal(false);
                }}
              >
                {renameMut.isLoading ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        </div>
      )}

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
              This will delete {sessions.find(s => s.id === deleteId)?.title || `Session #${deleteId}`}
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
                  background: "#880808",
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
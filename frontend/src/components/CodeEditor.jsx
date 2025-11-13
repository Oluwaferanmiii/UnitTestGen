// src/components/CodeEditor.jsx
import Editor from "react-simple-code-editor";
import Prism from "prismjs";
import "prismjs/components/prism-python";
import "prismjs/themes/prism-tomorrow.css";

export default function CodeEditor({ value, onChange, style = {} }) {
  const wrapperStyle = {
    position: "relative", // needed for placeholder overlay
    background: "#0b0b0c",
    border: "1px solid rgba(255,255,255,.2)",
    borderRadius: 12,
    padding: 0,
    fontFamily: "monospace",
    fontSize: 14,
    flex: 1,
    minHeight: 160,
    ...style,
  };

  function focusEditor() {
    const el = document.getElementById("codeArea");
    if (el) el.focus();
  }

  return (
    <div style={wrapperStyle} onClick={focusEditor}>
      {/* Placeholder overlay */}
      {!value && (
        <div
          style={{
            position: "absolute",
            top: 12,
            left: 12,
            color: "rgba(255,255,255,0.45)",
            fontFamily: "monospace",
            fontSize: 14,
            pointerEvents: "none", // clicks pass through to wrapper -> focusEditor
          }}
        >
          Write / Paste Code
        </div>
      )}

      <Editor
        value={value}
        onValueChange={onChange}
        highlight={(code) =>
          Prism.highlight(code, Prism.languages.python, "python")
        }
        padding={12}
        textareaId="codeArea"
        style={{
          outline: 0,
          minHeight: 160,
          whiteSpace: "pre",
        }}
      />
    </div>
  );
}
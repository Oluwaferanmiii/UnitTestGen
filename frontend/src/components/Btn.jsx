// src/components/Btn.jsx
export default function Btn({
  children,
  variant = "outline",   // "outline" | "solid"
  size = "medium",       // "small" | "medium" | "large"
  onClick,
  type = "button",
  disabled = false,
  styleOverride = {},
  ...rest
}) {
  // Define dimensions for each size
  const sizeMap = {
    small: { width: 180, height: 48, fontSize: 14 },
    medium: { width: 240, height: 60, fontSize: 16 },
    large: { width: 428, height: 97, fontSize: 20 },
  };

  const { width, height, fontSize } = sizeMap[size] || sizeMap.medium;

  // Theme (read once)
  const themeMode = localStorage.getItem("unittestlab:theme") || "dark";
  const isLight = themeMode === "light";

  // Determine class variant
  const className = variant === "solid" ? "button-pill solid" : "button-pill";

  // ✅ Theme-aware defaults (only for OUTLINE)
  const outlineDefaults = variant === "outline"
    ? {
        color: isLight ? "#0f172a" : "#fff",
        border: isLight
          ? "1px solid rgba(15,23,42,0.22)"
          : "1px solid rgba(255,255,255,0.35)",
        background: "transparent",
      }
    : {};

  // ✅ Hover backgrounds differ by theme (only for OUTLINE)
  function handleEnter(e) {
    if (disabled) return;
    if (variant !== "outline") return;

    e.currentTarget.style.background = isLight
      ? "rgba(37,99,235,0.08)"   // light hover
      : "rgba(255,255,255,0.12)"; // dark hover
  }

  function handleLeave(e) {
    if (disabled) return;
    if (variant !== "outline") return;

    e.currentTarget.style.background = "transparent";
  }

  return (
    <button
      {...rest}
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={className}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      style={{
        width,
        height,
        fontSize,

        // ✅ Only affects outline by default (landing)
        ...outlineDefaults,

        // ✅ Page-level overrides still win (login/register stay perfect)
        ...styleOverride,
      }}
    >
      {children}
    </button>
  );
}
export default function Btn({ children, variant="solid", onClick, type="button", disabled }) {
  const base = {
    padding: "14px 22px",
    borderRadius: 14,
    fontWeight: 700,
    cursor: "pointer",
    border: "1px solid #999",
    background: "transparent",
    color: "#fff",
  };
  const styles = variant === "solid"
    ? { ...base, background: "#d4d4d4", color: "#111", border: "none" }
    : base;
  return (
    <button type={type} onClick={onClick} disabled={disabled} style={styles}>
      {children}
    </button>
  );
}
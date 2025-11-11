export default function Logo({ size = 28 }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <img
        src="/logo.svg"
        alt="UnitTestLab Logo"
        width={size}
        height={size}
        style={{ objectFit: "contain" }}
      />
      <span style={{ fontWeight: 800, letterSpacing: 2, color: "#ddd" }}>
        UNITTESTLAB
      </span>
    </div>
  );
}
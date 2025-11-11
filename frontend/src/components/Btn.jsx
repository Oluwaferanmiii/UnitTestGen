export default function Btn({
  children,
  variant = "outline",   // "outline" | "solid"
  size = "medium",       // "small" | "medium" | "large"
  onClick,
  type = "button",
  disabled = false,
  styleOverride = {},
}) {
  // Define dimensions for each size
  const sizeMap = {
    small: { width: 180, height: 48, fontSize: 14 },
    medium: { width: 240, height: 60, fontSize: 16 },
    large: { width: 428, height: 97, fontSize: 20 },
  };

  const { width, height, fontSize } = sizeMap[size] || sizeMap.medium;

  // Determine class variant
  const className = variant === "solid" ? "button-pill solid" : "button-pill";

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={className}
      style={{
        width,
        height,
        fontSize,
        ...styleOverride, // <-- this lets us override background color etc.
      }}
    >
      {children}
    </button>
  );
}
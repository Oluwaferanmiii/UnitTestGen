export default function Logo({ size = "medium" }) {
  // Map string sizes → pixel dimensions
  const sizeMap = {
    small: 32,
    medium: 656,
    large: 500,
  };

  // If numeric size passed, use that directly
  const finalSize = typeof size === "number" ? size : sizeMap[size] || sizeMap.medium;

  return (
    <img
      src="/Logo.svg"  // Make sure it's lowercase and inside public/
      alt="UnitTestLab Logo"
      width={finalSize}
      height={finalSize}
      style={{
        display: "block",
        objectFit: "contain",
      }}
    />
  );
}
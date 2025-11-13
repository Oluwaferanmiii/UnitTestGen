// src/components/Logo.jsx
export default function Logo({
  size = "medium",
  width,          // optional explicit width (px)
  height,         // optional explicit height (px)
  src = "/Logo2.svg",
  alt = "UnitTestLab Logo",
  style = {},
}) {
  // Size presets can be non-square now
  const presets = {
    small:  { w: 36,   h: 36 },
    medium: { w: 656,  h: 656 },
    large:  { w: 500,  h: 200 },
  };

  // Start from preset or numeric square
  let w, h;
  if (typeof size === "number") {
    w = h = size;
  } else if (presets[size]) {
    ({ w, h } = presets[size]);
  } else {
    ({ w, h } = presets.medium);
  }

  // Explicit props override anything
  if (typeof width === "number")  w = width;
  if (typeof height === "number") h = height;

  return (
    <img
      src={src}
      alt={alt}
      width={w}
      height={h}
      style={{ display: "block", objectFit: "contain", ...style }}
    />
  );
}
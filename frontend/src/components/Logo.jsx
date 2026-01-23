// src/components/Logo.jsx
const ASSET_BASE = import.meta.env.BASE_URL;

export default function Logo({
  size = "medium",
  width,
  height,
  src, // optional override
  alt = "UnitTestLab Logo",
  style = {},
}) {
  const presets = {
    small: { w: 36, h: 36 },
    medium: { w: 656, h: 656 },
    large: { w: 500, h: 200 },
  };

  let w, h;
  if (typeof size === "number") {
    w = h = size;
  } else if (presets[size]) {
    ({ w, h } = presets[size]);
  } else {
    ({ w, h } = presets.medium);
  }

  if (typeof width === "number") w = width;
  if (typeof height === "number") h = height;

  // ✅ Default logo path that works in Docker (Vite base="/static/")
  const resolvedSrc = src ?? `${ASSET_BASE}Logo2.svg`;

  return (
    <img
      src={resolvedSrc}
      alt={alt}
      width={w}
      height={h}
      style={{ display: "block", objectFit: "contain", ...style }}
    />
  );
}
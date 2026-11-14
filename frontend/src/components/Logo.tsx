export function Logo({ size = 36 }: { size?: number }) {
  return (
    <img
      src="/logo.jpg"
      alt=""
      width={size}
      height={size}
      className="brand-logo"
      style={{ width: size, height: size }}
    />
  )
}

/** Decorative animated mesh for the hero — CSS-only, no assets. */

export function AnimatedBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div className="mesh-bg absolute inset-0" />
      <div
        className="glow-orb"
        style={{
          width: "min(55vw, 420px)",
          height: "min(55vw, 420px)",
          top: "8%",
          right: "5%",
          background: "rgba(20, 184, 160, 0.35)",
        }}
      />
      <div
        className="glow-orb"
        style={{
          width: "min(40vw, 300px)",
          height: "min(40vw, 300px)",
          bottom: "12%",
          left: "8%",
          background: "rgba(47, 111, 173, 0.28)",
          animationDelay: "2.5s",
        }}
      />
      <div
        className="absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(155, 176, 182, 0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(155, 176, 182, 0.06) 1px, transparent 1px)",
          backgroundSize: "56px 56px",
          maskImage:
            "radial-gradient(ellipse 70% 60% at 60% 40%, black, transparent)",
        }}
      />
      <div
        className="absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.45'/%3E%3C/svg%3E\")",
          mixBlendMode: "soft-light",
        }}
      />
    </div>
  );
}

import type { ReactNode } from "react";

/**
 * Dark navy background with glowing vertical blue "light column" beams rising from
 * the bottom edge, each column an overlapping radial-gradient ellipse -- this is what
 * produces the scalloped divots between beams and the soft rounded tops, matching the
 * reference: deep near-black base, saturated blue glow concentrated at the bottom,
 * fading to near-black toward the top.
 */
const HERO_GRADIENT_STYLE: React.CSSProperties = {
  backgroundColor: "#050810",
  backgroundImage: [
    "radial-gradient(ellipse 32% 105% at 4% 100%, rgba(59,130,246,0.95), transparent 68%)",
    "radial-gradient(ellipse 32% 100% at 24% 100%, rgba(30,64,175,0.85), transparent 66%)",
    "radial-gradient(ellipse 34% 108% at 45% 100%, rgba(37,99,235,0.95), transparent 68%)",
    "radial-gradient(ellipse 32% 100% at 66% 100%, rgba(30,64,175,0.85), transparent 66%)",
    "radial-gradient(ellipse 34% 108% at 87% 100%, rgba(59,130,246,0.95), transparent 68%)",
    "radial-gradient(ellipse 40% 90% at 106% 100%, rgba(37,99,235,0.85), transparent 64%)",
    "linear-gradient(to bottom, #050810 0%, #050810 38%, #071228 68%, #0a1a3a 100%)",
  ].join(", "),
  backgroundRepeat: "no-repeat",
};

export default function GradientHero({
  children, className = "", overlayFade = true,
}: {
  children: ReactNode;
  className?: string;
  /** Slightly darkens the top so light-colored content stays readable over the glow. */
  overlayFade?: boolean;
}) {
  return (
    <div className={`relative overflow-hidden hero-glow-pulse ${className}`} style={HERO_GRADIENT_STYLE}>
      {overlayFade && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: "linear-gradient(to bottom, rgba(5,8,16,0.5) 0%, rgba(5,8,16,0) 22%)" }}
        />
      )}
      <div className="relative">{children}</div>
    </div>
  );
}

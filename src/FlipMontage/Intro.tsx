import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export const Intro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scale = spring({
    frame,
    fps,
    config: { damping: 200, stiffness: 120 },
  });

  const opacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#05070d",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          transform: `scale(${0.85 + scale * 0.15})`,
          opacity,
          textAlign: "center",
          padding: "0 80px",
        }}
      >
        <div
          style={{
            fontFamily:
              "Helvetica, Arial, sans-serif",
            fontWeight: 800,
            fontSize: 78,
            lineHeight: 1.15,
            color: "#ffffff",
            letterSpacing: -1,
          }}
        >
          Akrobaatiline
          <br />
          sünnipäevatervitus
        </div>
      </div>
    </AbsoluteFill>
  );
};

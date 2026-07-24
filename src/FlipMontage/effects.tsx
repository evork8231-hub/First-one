import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

export const FlashPulse: React.FC<{ triggerFrame: number }> = ({
  triggerFrame,
}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(
    frame - triggerFrame,
    [0, 3, 10],
    [0, 0.85, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  return (
    <AbsoluteFill
      style={{ backgroundColor: "white", opacity, pointerEvents: "none" }}
    />
  );
};

export const zoomPunchScale = (frame: number, triggerFrame: number) =>
  interpolate(frame - triggerFrame, [0, 6, 22], [1, 1.16, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

export const ZoomPunch: React.FC<{
  triggerFrame: number;
  children: React.ReactNode;
}> = ({ triggerFrame, children }) => {
  const frame = useCurrentFrame();
  const scale = zoomPunchScale(frame, triggerFrame);
  return (
    <AbsoluteFill style={{ transform: `scale(${scale})` }}>
      {children}
    </AbsoluteFill>
  );
};

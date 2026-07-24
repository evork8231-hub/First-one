import React from "react";
import { Audio, OffthreadVideo, Sequence, staticFile } from "remotion";
import type { MultiFlipClip as MultiFlipClipType } from "./clips";
import { FPS } from "./clips";
import { FlashPulse, ZoomPunch } from "./effects";

const secToFrames = (s: number) => Math.round(s * FPS);

const videoStyle: React.CSSProperties = {
  width: "100%",
  height: "100%",
  objectFit: "cover",
};

export const MultiFlipClip: React.FC<{ clip: MultiFlipClipType }> = ({
  clip,
}) => {
  const accentFrame = secToFrames(clip.accentAt - clip.trimIn);
  const impactFrame = secToFrames(clip.impactAt - clip.trimIn);

  return (
    <>
      <ZoomPunch triggerFrame={accentFrame}>
        <OffthreadVideo
          src={staticFile(clip.src)}
          trimBefore={secToFrames(clip.trimIn)}
          style={videoStyle}
        />
      </ZoomPunch>
      <FlashPulse triggerFrame={accentFrame} />
      <Sequence from={Math.max(accentFrame - 5, 0)} durationInFrames={secToFrames(1)}>
        <Audio src={staticFile("audio/whoosh.mp3")} volume={0.9} />
      </Sequence>
      <Sequence from={Math.max(impactFrame - 2, 0)} durationInFrames={secToFrames(1)}>
        <Audio src={staticFile("audio/impact.mp3")} volume={0.9} />
      </Sequence>
    </>
  );
};

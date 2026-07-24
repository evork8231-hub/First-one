import React from "react";
import type { MultiFlipClip as MultiFlipClipType } from "./clips";
import { FPS } from "./clips";
import { FitVideo } from "./FitVideo";
import { FlashPulse, ZoomPunch } from "./effects";

const secToFrames = (s: number) => Math.round(s * FPS);

export const MultiFlipClip: React.FC<{ clip: MultiFlipClipType }> = ({
  clip,
}) => {
  const accentFrame = secToFrames(clip.accentAt - clip.trimIn);

  return (
    <>
      <ZoomPunch triggerFrame={accentFrame}>
        <FitVideo
          src={clip.src}
          trimBefore={secToFrames(clip.trimIn)}
          fit={clip.fit ?? "cover"}
        />
      </ZoomPunch>
      <FlashPulse triggerFrame={accentFrame} />
    </>
  );
};

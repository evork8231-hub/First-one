import React from "react";
import { Sequence } from "remotion";
import type { SingleFlipClip as SingleFlipClipType } from "./clips";
import { FPS } from "./clips";
import { FitVideo } from "./FitVideo";
import { FlashPulse, ZoomPunch } from "./effects";

const secToFrames = (s: number) => Math.round(s * FPS);
const PREMOUNT_FRAMES = 15;

export const SingleFlipClip: React.FC<{ clip: SingleFlipClipType }> = ({
  clip,
}) => {
  const fit = clip.fit ?? "cover";
  const leadInFrames = secToFrames(clip.flipStart - clip.trimIn);
  const flipOutFrames = secToFrames(
    (clip.flipEnd - clip.flipStart) / clip.slowMoFactor,
  );
  const landingFrames = secToFrames(clip.trimOut - clip.flipEnd);
  const flipOutFrom = leadInFrames;
  const landingFrom = leadInFrames + flipOutFrames;

  return (
    <>
      <Sequence
        durationInFrames={leadInFrames}
        premountFor={PREMOUNT_FRAMES}
      >
        <FitVideo
          src={clip.src}
          trimBefore={secToFrames(clip.trimIn)}
          fit={fit}
        />
      </Sequence>
      <Sequence
        from={flipOutFrom}
        durationInFrames={flipOutFrames}
        premountFor={PREMOUNT_FRAMES}
      >
        <ZoomPunch triggerFrame={0}>
          <FitVideo
            src={clip.src}
            trimBefore={secToFrames(clip.flipStart)}
            playbackRate={clip.slowMoFactor}
            fit={fit}
          />
        </ZoomPunch>
        <FlashPulse triggerFrame={0} />
      </Sequence>
      <Sequence
        from={landingFrom}
        durationInFrames={landingFrames}
        premountFor={PREMOUNT_FRAMES}
      >
        <FitVideo
          src={clip.src}
          trimBefore={secToFrames(clip.flipEnd)}
          fit={fit}
        />
      </Sequence>
    </>
  );
};

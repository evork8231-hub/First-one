import React from "react";
import { Audio, OffthreadVideo, Sequence, staticFile } from "remotion";
import type { SingleFlipClip as SingleFlipClipType } from "./clips";
import { FPS } from "./clips";
import { FlashPulse, ZoomPunch } from "./effects";

const secToFrames = (s: number) => Math.round(s * FPS);
const PREMOUNT_FRAMES = 15;

const videoStyle: React.CSSProperties = {
  width: "100%",
  height: "100%",
  objectFit: "cover",
};

export const SingleFlipClip: React.FC<{ clip: SingleFlipClipType }> = ({
  clip,
}) => {
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
        <OffthreadVideo
          src={staticFile(clip.src)}
          trimBefore={secToFrames(clip.trimIn)}
          style={videoStyle}
        />
      </Sequence>
      <Sequence
        from={flipOutFrom}
        durationInFrames={flipOutFrames}
        premountFor={PREMOUNT_FRAMES}
      >
        <ZoomPunch triggerFrame={0}>
          <OffthreadVideo
            src={staticFile(clip.src)}
            trimBefore={secToFrames(clip.flipStart)}
            playbackRate={clip.slowMoFactor}
            style={videoStyle}
          />
        </ZoomPunch>
        <FlashPulse triggerFrame={0} />
      </Sequence>
      <Sequence
        from={landingFrom}
        durationInFrames={landingFrames}
        premountFor={PREMOUNT_FRAMES}
      >
        <OffthreadVideo
          src={staticFile(clip.src)}
          trimBefore={secToFrames(clip.flipEnd)}
          style={videoStyle}
        />
      </Sequence>
      <Sequence
        from={Math.max(flipOutFrom - 5, 0)}
        durationInFrames={secToFrames(1)}
      >
        <Audio src={staticFile("audio/whoosh.mp3")} volume={0.9} />
      </Sequence>
      <Sequence
        from={Math.max(landingFrom - 3, 0)}
        durationInFrames={secToFrames(1)}
      >
        <Audio src={staticFile("audio/impact.mp3")} volume={0.9} />
      </Sequence>
    </>
  );
};

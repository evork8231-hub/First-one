import React from "react";
import { Audio, staticFile } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import {
  INTRO_DURATION_IN_FRAMES,
  REPEAT_COUNT,
  TRANSITION_FRAMES,
  clipDurationInFrames,
  clips,
  totalDurationInFrames,
} from "./clips";
import { Intro } from "./Intro";
import { SingleFlipClip } from "./SingleFlipClip";
import { MultiFlipClip } from "./MultiFlipClip";

export { totalDurationInFrames };

const transition = (
  <TransitionSeries.Transition
    presentation={fade()}
    timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
  />
);

export const FlipMontage: React.FC = () => {
  const plays = Array.from({ length: REPEAT_COUNT }, (_, playIndex) =>
    clips.map((clip, i) => {
      const isVeryLastClip =
        playIndex === REPEAT_COUNT - 1 && i === clips.length - 1;
      return (
        <React.Fragment key={`play${playIndex}-${clip.src}`}>
          <TransitionSeries.Sequence
            durationInFrames={clipDurationInFrames(clip)}
          >
            {clip.type === "single" ? (
              <SingleFlipClip clip={clip} />
            ) : (
              <MultiFlipClip clip={clip} />
            )}
          </TransitionSeries.Sequence>
          {!isVeryLastClip && transition}
        </React.Fragment>
      );
    }),
  ).flat();

  return (
    <>
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={INTRO_DURATION_IN_FRAMES}>
          <Intro />
        </TransitionSeries.Sequence>
        {transition}
        {plays}
      </TransitionSeries>
      <Audio src={staticFile("audio/song.mp3")} volume={0.8} />
    </>
  );
};

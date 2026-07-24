import React from "react";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import {
  INTRO_DURATION_IN_FRAMES,
  TRANSITION_FRAMES,
  clipDurationInFrames,
  clips,
  totalDurationInFrames,
} from "./clips";
import { Intro } from "./Intro";
import { SingleFlipClip } from "./SingleFlipClip";
import { MultiFlipClip } from "./MultiFlipClip";

export { totalDurationInFrames };

export const FlipMontage: React.FC = () => {
  return (
    <TransitionSeries>
      <TransitionSeries.Sequence durationInFrames={INTRO_DURATION_IN_FRAMES}>
        <Intro />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition
        presentation={fade()}
        timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
      />
      {clips.map((clip, i) => (
        <React.Fragment key={clip.src}>
          <TransitionSeries.Sequence
            durationInFrames={clipDurationInFrames(clip)}
          >
            {clip.type === "single" ? (
              <SingleFlipClip clip={clip} />
            ) : (
              <MultiFlipClip clip={clip} />
            )}
          </TransitionSeries.Sequence>
          {i < clips.length - 1 && (
            <TransitionSeries.Transition
              presentation={fade()}
              timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
            />
          )}
        </React.Fragment>
      ))}
    </TransitionSeries>
  );
};

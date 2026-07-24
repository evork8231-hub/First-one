import React from "react";
import { Audio, staticFile } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import {
  TRANSITION_FRAMES,
  clipDurationInFrames,
  clips,
  totalDurationInFrames,
} from "./clips";
import { SingleFlipClip } from "./SingleFlipClip";
import { MultiFlipClip } from "./MultiFlipClip";

export { totalDurationInFrames };

export const FlipMontage: React.FC = () => {
  return (
    <>
      <TransitionSeries>
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
      <Audio src={staticFile("audio/song.mp3")} volume={0.8} />
    </>
  );
};

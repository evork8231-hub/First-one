export const FPS = 30;

export type SingleFlipClip = {
  type: "single";
  src: string;
  /** seconds into the source file */
  trimIn: number;
  flipStart: number;
  flipEnd: number;
  trimOut: number;
  slowMoFactor: number;
  fit?: "cover" | "contain";
};

export type MultiFlipClip = {
  type: "multi";
  src: string;
  trimIn: number;
  /** moment the first takeoff happens, for the whoosh/flash accent */
  accentAt: number;
  /** moment of the final landing, for the impact accent */
  impactAt: number;
  trimOut: number;
  fit?: "cover" | "contain";
};

export type ClipDef = SingleFlipClip | MultiFlipClip;

export const clips: ClipDef[] = [
  {
    type: "single",
    src: "videos/clip-01.mp4",
    trimIn: 0.4,
    flipStart: 0.75,
    flipEnd: 1.65,
    trimOut: 2.2,
    slowMoFactor: 0.5,
  },
  {
    type: "single",
    src: "videos/clip-02.mp4",
    trimIn: 1.0,
    flipStart: 2.3,
    flipEnd: 2.85,
    trimOut: 3.5,
    slowMoFactor: 0.5,
  },
  {
    type: "single",
    src: "videos/clip-03.mp4",
    trimIn: 3.0,
    flipStart: 4.75,
    flipEnd: 5.5,
    trimOut: 6.0,
    slowMoFactor: 0.5,
  },
  {
    type: "single",
    src: "videos/clip-04.mp4",
    trimIn: 1.2,
    flipStart: 3.8,
    flipEnd: 4.6,
    trimOut: 5.0,
    slowMoFactor: 0.5,
  },
  {
    type: "multi",
    src: "videos/clip-05.mp4",
    trimIn: 4.0,
    accentAt: 4.5,
    impactAt: 9.0,
    trimOut: 9.5,
  },
  {
    type: "multi",
    src: "videos/clip-06.mp4",
    trimIn: 3.3,
    accentAt: 3.85,
    impactAt: 6.85,
    trimOut: 7.5,
    fit: "contain",
  },
];

const secToFrames = (s: number) => Math.round(s * FPS);

export const clipDurationInFrames = (clip: ClipDef): number => {
  if (clip.type === "multi") {
    return secToFrames(clip.trimOut - clip.trimIn);
  }
  const leadIn = clip.flipStart - clip.trimIn;
  const flipOut = (clip.flipEnd - clip.flipStart) / clip.slowMoFactor;
  const landing = clip.trimOut - clip.flipEnd;
  return secToFrames(leadIn + flipOut + landing);
};

export const TRANSITION_FRAMES = 8;
export const INTRO_DURATION_IN_FRAMES = secToFrames(3);
export const REPEAT_COUNT = 2;

const perPlayDurations = clips.map(clipDurationInFrames);

const segmentDurations = [
  INTRO_DURATION_IN_FRAMES,
  ...Array(REPEAT_COUNT).fill(perPlayDurations).flat(),
];

export const totalDurationInFrames =
  segmentDurations.reduce((sum, d) => sum + d, 0) -
  TRANSITION_FRAMES * (segmentDurations.length - 1);

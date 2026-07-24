import React from "react";
import { AbsoluteFill, OffthreadVideo, staticFile } from "remotion";

type FitVideoProps = {
  src: string;
  trimBefore: number;
  playbackRate?: number;
  fit: "cover" | "contain";
};

/**
 * "contain" avoids cropping wide-shot footage where the action drifts
 * outside a center-cropped vertical frame; a blurred cover copy fills
 * the letterboxed space behind it.
 */
export const FitVideo: React.FC<FitVideoProps> = ({
  src,
  trimBefore,
  playbackRate,
  fit,
}) => {
  if (fit === "cover") {
    return (
      <OffthreadVideo
        src={staticFile(src)}
        trimBefore={trimBefore}
        playbackRate={playbackRate}
        muted
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
    );
  }

  return (
    <AbsoluteFill>
      <OffthreadVideo
        src={staticFile(src)}
        trimBefore={trimBefore}
        playbackRate={playbackRate}
        muted
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          filter: "blur(50px) brightness(0.45)",
          transform: "scale(1.2)",
        }}
      />
      <AbsoluteFill style={{ justifyContent: "center" }}>
        <OffthreadVideo
          src={staticFile(src)}
          trimBefore={trimBefore}
          playbackRate={playbackRate}
          muted
          style={{ width: "100%", height: "auto", objectFit: "contain" }}
        />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

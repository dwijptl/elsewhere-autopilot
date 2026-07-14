import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Sequence,
  interpolate,
  random,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {TransitionSeries, linearTiming} from '@remotion/transitions';
import {fade} from '@remotion/transitions/fade';
import {slide} from '@remotion/transitions/slide';
import {wipe} from '@remotion/transitions/wipe';
import type {Manifest} from './Root';
import {MapZoom} from './Map';
import {getStyle, StylePack} from './styles';
import {
  CaptionsLayer,
  CinematicOverlay,
  LightLeak,
  Outro,
  ProgressBar,
  SceneVisual,
  SfxLayer,
  Watermark,
} from './elements';
import {
  AnimatedLowerThird,
  AnimatedStatCard,
  CtaLayer,
  EditorialCard,
  KineticTitle,
  SceneFrame,
} from './motion-library';
import type {MotionSpec} from './motion-library';
import {GlassCard} from './glass';
import {LoopDiagram, Schematic, TwoChoices, Verdict} from './dossier';
import {MetricReadout, TelemetryHUD} from './hud';
import type {Milestone} from './hud';
import {blurWhip, zoomPunch} from './transitions';

// Deterministic transition choice, biased by the video's style pack.
// Remotion's transition presentations are invariant generic types; this helper
// intentionally mixes slide, fade, wipe, whip and punch presentations at runtime.
const pickTransition = (i: number, style: StylePack): any => {
  const r = random(`tr-${style.name}-${i}`);
  switch (style.transitionBias) {
    case 'slides':
      if (r < 0.3) return blurWhip('from-right');
      if (r < 0.5) return blurWhip('from-left');
      if (r < 0.7) return slide({direction: 'from-right'});
      if (r < 0.85) return zoomPunch();
      return fade();
    case 'fades':
      if (r < 0.65) return fade();
      if (r < 0.85) return zoomPunch();
      return slide({direction: 'from-right'});
    case 'wipes':
      if (r < 0.4) return wipe({direction: 'from-left'});
      if (r < 0.6) return wipe({direction: 'from-top-left'});
      if (r < 0.8) return zoomPunch();
      return fade();
    default:
      if (r < 0.35) return fade();
      if (r < 0.5) return zoomPunch();
      if (r < 0.65) return slide({direction: 'from-right'});
      if (r < 0.78) return slide({direction: 'from-left'});
      if (r < 0.9) return wipe({direction: 'from-left'});
      return blurWhip('from-right');
  }
};

const MusicTrack: React.FC<{m: Manifest}> = ({m}) => {
  const frame = useCurrentFrame();
  const {durationInFrames, fps} = useVideoConfig();
  if (!m.musicPath || m.musicVolume <= 0) return null;
  const fadeF = Math.round(1.5 * fps);
  const seconds = frame / fps;
  const automation = m.musicAutomation ?? [];
  let active = -1;
  for (let i = 0; i < automation.length; i++) {
    if (seconds >= automation[i].start) active = i;
  }
  let narrativeFactor = active >= 0 ? automation[active].factor : 1;
  if (active > 0) {
    const local = seconds - automation[active].start;
    narrativeFactor = interpolate(local, [0, m.musicTransitionSeconds ?? 0.45],
      [automation[active - 1].factor, automation[active].factor],
      {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  }
  const vol =
    m.musicVolume *
    narrativeFactor *
    interpolate(
      frame,
      [0, fadeF, Math.max(durationInFrames - fadeF, fadeF + 1), durationInFrames],
      [0, 1, 1, 0],
      {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
    );
  return <Audio loop src={staticFile(m.musicPath)} volume={vol} />;
};

// ── Impact-graphic windowing ────────────────────────────────────────────
// Overlay graphics (kinetic/stat/card/glass) are impact moments, not
// wallpaper: they hold for ~overlaySeconds, fade out, and hand the frame
// back to the footage for the rest of the scene's narration.

const FadeShell: React.FC<{frames: number; fps: number;
  children: React.ReactNode}> = ({frames, fps, children}) => {
  const frame = useCurrentFrame();
  const fadeF = Math.max(Math.round(0.4 * fps), 6);
  const opacity = interpolate(frame,
    [Math.max(frames - fadeF, 1), Math.max(frames - 1, 2)], [1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <AbsoluteFill style={{opacity}}>{children}</AbsoluteFill>;
};

export const OverlayWindow: React.FC<{frames: number; fps: number; from?: number;
  children: React.ReactNode}> = ({frames, fps, from, children}) => (
  <Sequence from={from ?? 0} durationInFrames={Math.max(frames, 1)}>
    <FadeShell frames={frames} fps={fps}>{children}</FadeShell>
  </Sequence>
);

const DimFill: React.FC<{frames: number; fps: number}> = ({frames, fps}) => {
  const frame = useCurrentFrame();
  const fadeF = Math.max(Math.round(0.4 * fps), 6);
  const opacity = interpolate(frame,
    [0, 8, Math.max(frames - fadeF, 9), Math.max(frames - 1, 10)],
    [0, 0.55, 0.55, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <AbsoluteFill style={{background: 'rgb(6,10,20)', opacity,
    pointerEvents: 'none'}} />;
};

export const TimedDim: React.FC<{frames: number; fps: number; from?: number}> =
  ({frames, fps, from}) => (
  <Sequence from={from ?? 0} durationInFrames={Math.max(frames, 1)}>
    <DimFill frames={frames} fps={fps} />
  </Sequence>
);

// ── Delivery-driven camera: the narrator's tone moves the lens ─────────
// "reveal": half-second hold, then an accelerating push-in toward the
// subject. "urgent": a 2-3px deterministic handheld jitter at ~15Hz.
const CameraRig: React.FC<{
  delivery?: string;
  fps: number;
  frames: number;
  sceneN: number;
  children: React.ReactNode;
}> = ({delivery, fps, frames, sceneN, children}) => {
  const frame = useCurrentFrame();
  let transform: string | undefined;
  if (delivery === 'reveal') {
    const hold = Math.round(0.5 * fps);
    const p = interpolate(frame, [hold, Math.max(frames, hold + 1)], [0, 1],
      {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
    transform = `scale(${(1 + 0.055 * p * p).toFixed(4)})`;
  } else if (delivery === 'urgent') {
    const step = Math.floor(frame / 2); // ~15Hz jitter
    const sx = (random(`shx-${sceneN}-${step}`) - 0.5) * 5;
    const sy = (random(`shy-${sceneN}-${step}`) - 0.5) * 4;
    transform = `translate(${sx.toFixed(2)}px, ${sy.toFixed(2)}px) scale(1.02)`;
  }
  if (!transform) return <>{children}</>;
  return <AbsoluteFill style={{transform}}>{children}</AbsoluteFill>;
};

const TruthChip: React.FC<{text: string; accent: string}> = ({text, accent}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const s = width / 1920;
  const inO = interpolate(frame, [0, Math.round(0.5 * fps)], [0, 1],
    {extrapolateRight: 'clamp'});
  const outO = interpolate(frame, [Math.round(6 * fps), Math.round(7 * fps)],
    [1, 0], {extrapolateLeft: 'clamp'});
  return (
    <div style={{
      position: 'absolute', top: 26 * s, right: 30 * s,
      maxWidth: 560 * s, opacity: Math.min(inO, outO),
      background: 'rgba(28,24,20,0.78)', borderLeft: `${3 * s}px solid ${accent}`,
      padding: `${8 * s}px ${14 * s}px`, borderRadius: 4 * s,
      color: '#EFE4D2', fontSize: 21 * s, lineHeight: 1.35,
      fontFamily: 'Inter, sans-serif', letterSpacing: 0.3, textAlign: 'left',
    }}>{text}</div>
  );
};

export const Main: React.FC<{manifest: Manifest}> = ({manifest: m}) => {
  const fps = m.fps;
  const {durationInFrames} = useVideoConfig();
  const style = getStyle(m.style);
  const chapterMarks = m.scenes.slice(1).map(
    (sc) => ((sc.start ?? 0) * fps) / Math.max(durationInFrames, 1));
  const metricLabel = String((m as any).variableLabel ?? '');
  const metricUnit = String((m as any).variableUnit ?? '');
  const milestones: Milestone[] = m.scenes.map((sc) => ({
    start: sc.start ?? 0,
    value: (sc as any).milestone?.value as number | undefined,
    label: (sc as any).milestone?.label as string | undefined,
    unit: (sc as any).milestone?.unit as string | undefined,
  }));
  const hasMetric = milestones.some(
    (p) => typeof p.value === 'number' && isFinite(p.value));
  const maxShotSeconds = m.maxShotSeconds ?? 5;
  const overlaySeconds = Math.min(
    Math.max(Number((m as any).overlaySeconds ?? 5), 2.5), 12);
  const overlayRanges = m.scenes
    .filter((scene) => ['kinetic', 'stat', 'card', 'glass'].includes(scene.visualMode ?? ''))
    .map((scene) => {
      const impact = Number((scene as any).impactStart ?? 0);
      return {start: (scene.start ?? 0) + impact,
        end: (scene.start ?? 0) + Math.min(scene.audioDuration, impact + overlaySeconds)};
    });
  const outroFrames = Math.max(Math.round((m.outroSeconds ?? 4) * fps), fps);

  const items: React.ReactNode[] = [];
  m.scenes.forEach((scene, i) => {
    const sceneFrames = Math.round(scene.audioDuration * fps);
    const mode = scene.visualMode ?? 'broll';
    const overlayScene = mode === 'kinetic' || mode === 'stat' || mode === 'card' || mode === 'glass';
    // word-synced impact: the graphic enters on the spoken keyword
    const impactF = Math.max(0, Math.min(
      Math.round(Number((scene as any).impactStart ?? 0) * fps),
      Math.max(sceneFrames - fps, 0)));
    // Dossier schematic and verdict scenes ARE their overlay — the diagram
    // is the content, not a garnish, so it holds for the whole scene.
    // (Pilot #2: a 34-second diagram scene showed 5s of card and 29s of
    // empty gradient. The overlay cap is for punctuation, not chapters.)
    const overlayIsScene = style.name === 'dossier' &&
      (Boolean(scene.verdictCard) || mode === 'glass' || mode === 'stat'
        || ((scene.card as any)?.options?.length ?? 0) >= 2);
    const overlayFrames = overlayIsScene
      ? Math.max(1, sceneFrames - impactF)
      : Math.max(1, Math.min(sceneFrames - impactF,
          Math.round(overlaySeconds * fps)));
    const isMap = mode === 'map' && scene.map && scene.map.world;
    const motion: MotionSpec = scene.motion ?? {};
    items.push(
      <TransitionSeries.Sequence key={`s-${scene.n}`} durationInFrames={sceneFrames}>
        <CameraRig delivery={(scene as any).delivery} fps={fps}
          frames={sceneFrames} sceneN={scene.n}>
          {isMap ? (
            <MapZoom map={scene.map} sceneFrames={sceneFrames} style={style} />
          ) : (
            <SceneVisual
              assets={scene.assets}
              visualBeats={scene.visualBeats ?? []}
              sceneFrames={sceneFrames}
              fps={fps}
              maxShotSeconds={maxShotSeconds}
              sceneN={scene.n}
              style={style}
            />
          )}
        </CameraRig>
        {overlayScene ? (
          <TimedDim frames={overlayFrames} fps={fps} from={impactF} />
        ) : null}
        {scene.audioPath ? <Audio src={staticFile(scene.audioPath)} /> : null}
        {mode === 'kinetic' && scene.kineticText ? (
          <OverlayWindow frames={overlayFrames} fps={fps} from={impactF}>
            <KineticTitle text={scene.kineticText} style={style}
              variant={motion.kineticVariant} />
          </OverlayWindow>
        ) : null}
        {mode === 'stat' && scene.stat && scene.stat.label ? (
          <OverlayWindow frames={overlayFrames} fps={fps} from={impactF}>
            <AnimatedStatCard stat={scene.stat} style={style}
              variant={motion.statVariant} />
          </OverlayWindow>
        ) : null}
        {mode === 'card' && scene.verdictCard ? (
          <OverlayWindow frames={overlayFrames} fps={fps} from={impactF}>
            <Verdict
              data={{
                verdict: m.verdict ?? 'FAILED',
                settlement: m.settlement?.name,
                reason: m.verdictReason,
                outcome: (m as any).verdictOutcome,
              }}
              durationInFrames={overlayFrames}
            />
          </OverlayWindow>
        ) : null}
        {mode === 'card' && !scene.verdictCard
          && ((scene.card as any)?.options?.length ?? 0) >= 2 ? (
          // "Two moves left" spoken over nothing was a pilot-review failure —
          // a choice the audience can't see is a choice they can't feel.
          <OverlayWindow frames={overlayFrames} fps={fps} from={impactF}>
            <TwoChoices options={(scene.card as any).options}
              kicker={scene.card?.kicker} durationInFrames={overlayFrames} />
          </OverlayWindow>
        ) : null}
        {mode === 'card' && !scene.verdictCard
          && !((scene.card as any)?.options?.length >= 2)
          && scene.card && scene.card.headline ? (
          <OverlayWindow frames={overlayFrames} fps={fps} from={impactF}>
            <EditorialCard card={scene.card} style={style} variant={motion.cardVariant} />
          </OverlayWindow>
        ) : null}
        {mode === 'glass' && scene.glass && (scene.glass.headline || scene.glass.label || scene.glass.location || scene.glass.chapter || scene.glass.value != null) ? (
          <OverlayWindow frames={overlayFrames} fps={fps} from={impactF}>
            {style.name === 'dossier' && ((scene.glass as any)?.loop?.length ?? 0) >= 3 ? (
              <LoopDiagram stages={(scene.glass as any).loop}
                headline={scene.glass.headline} kicker={scene.glass.kicker}
                durationInFrames={overlayFrames} />
            ) : style.name === 'dossier' ? (
              <Schematic
                data={{...scene.glass, nodes: m.systems?.map((sy) => ({
                  name: sy.name,
                  runs_at: sy.runs_at,
                  depends_on: sy.depends_on,
                }))}}
                durationInFrames={overlayFrames}
              />
            ) : (
              <GlassCard data={scene.glass} style={style} variant={motion.glassVariant} />
            )}
          </OverlayWindow>
        ) : null}
        {!overlayScene && !isMap && scene.title ? (
          <AnimatedLowerThird title={scene.title} style={style}
            variant={motion.lowerThirdVariant} index={scene.n} />
        ) : null}
        <SceneFrame variant={motion.frameVariant} style={style} sceneN={scene.n} />
        {i > 0 ? <LightLeak seed={`scene-${scene.n}`} /> : null}
      </TransitionSeries.Sequence>
    );
    items.push(
      <TransitionSeries.Transition
        key={`t-${scene.n}`}
        presentation={pickTransition(i, style)}
        timing={linearTiming({durationInFrames: m.xfadeFrames})}
      />
    );
  });
  // branded outro end card
  items.push(
    <TransitionSeries.Sequence key="outro" durationInFrames={outroFrames}>
      <Outro
        brandName={m.brandName || 'TERRA INCOGNITA'}
        tagline={m.brandTagline || "Mapping the world's hidden places"}
        style={style}
        watermarkPath={m.watermarkPath}
      />
    </TransitionSeries.Sequence>
  );

  return (
    <AbsoluteFill style={{backgroundColor: style.bg}}>
      <TransitionSeries>{items}</TransitionSeries>
      <CaptionsLayer captions={m.captions} style={style}
        compactRanges={overlayRanges} compactYFrac={0.84} sizeBoost={1.15} />
      {(m as any).truthLabel ? (
        // The disclosure is SEEN, not just spoken — top-right, first ~7s,
        // small enough to be honest without being an apology.
        <Sequence from={Math.round(0.6 * fps)}
          durationInFrames={Math.round(7 * fps)}>
          <TruthChip text={String((m as any).truthLabel)} accent={style.accent} />
        </Sequence>
      ) : null}
      <CinematicOverlay />
      {style.hud ? (
        <TelemetryHUD starts={m.scenes.map((sc) => sc.start ?? 0)}
          accent={style.accent} accent2={style.accent2}
          milestones={milestones} metricLabel={metricLabel}
          metricUnit={metricUnit} />
      ) : hasMetric ? (
        // clamped to the story — the counter must not haunt the end card
        <Sequence from={0} durationInFrames={Math.max(
          Math.round(((m.scenes[m.scenes.length - 1]?.start ?? 0)
            + (m.scenes[m.scenes.length - 1]?.audioDuration ?? 0)) * fps), 1)}>
          <MetricReadout milestones={milestones} label={metricLabel}
            unit={metricUnit} accent={style.accent} />
        </Sequence>
      ) : null}
      <CtaLayer event={m.cta} style={style} fps={fps} />
      {m.watermarkPath ? (
        <Watermark src={m.watermarkPath} opacity={m.watermarkOpacity ?? 0.08} />
      ) : null}
      {m.progressBar ? (
        <ProgressBar accent={style.accent} marks={chapterMarks} />
      ) : null}
      <SfxLayer events={m.sfx ?? []} fps={fps} />
      <MusicTrack m={m} />
    </AbsoluteFill>
  );
};

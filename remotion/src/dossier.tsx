/** The dossier — ELSEWHERE's two signature graphics.
 *
 * Channel 1's glass.tsx renders a liquid-glass HUD panel. This file renders the
 * opposite: ink on paper, filed by an engineer, photographed later. Same data
 * contract (so the pipeline is shared), no visual DNA in common (so the
 * channels never cannibalise each other).
 *
 * Two components, and they carry the whole format:
 *
 *   <Schematic>  the system diagram. THE HIDDEN DEPENDENCY IS DRAWN HERE, in
 *                plain sight, and never pointed at. The pleasure of this format
 *                is a viewer noticing the shared node half a second before the
 *                narrator does.
 *
 *   <Verdict>    SURVIVED / ADAPTED / FAILED. It stamps down, it does not
 *                animate in. No music swell (see canon/art_bible.md). The
 *                colour is the spoiler and the audience learns to read it.
 */
import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {DOSSIER, VERDICT_COLORS} from './styles';

const MONO = 'ui-monospace, "SF Mono", Menlo, monospace';
const SANS = 'Inter, system-ui, sans-serif';

/** Paper grain + a faint graticule. Everything in this world was printed. */
const Paper: React.FC<{children: React.ReactNode}> = ({children}) => (
  <div
    style={{
      position: 'absolute',
      inset: 0,
      background: `
        repeating-linear-gradient(0deg, rgba(140,106,74,0.05) 0 1px, transparent 1px 44px),
        repeating-linear-gradient(90deg, rgba(140,106,74,0.05) 0 1px, transparent 1px 44px),
        radial-gradient(ellipse at 50% 40%, ${DOSSIER.ink} 0%, ${DOSSIER.basalt} 100%)
      `,
    }}
  >
    {children}
  </div>
);

export type SchematicData = {
  kicker?: string;
  headline?: string;
  body?: string;
  value?: number | null;
  suffix?: string;
  label?: string;
  delta?: number | null;
  delta_direction?: 'up' | 'down' | 'flat';
  location?: string;
  chapter?: string;
  /** The systems drawn as nodes. When two of them name the same dependency,
   *  the diagram quietly draws ONE node and lets both lines run into it. */
  nodes?: {name: string; runs_at?: string; depends_on?: string}[];
};

export const Schematic: React.FC<{data: SchematicData; durationInFrames: number}> = ({
  data,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();

  // ink bleeding into paper — no easing curve that feels digital
  const draw = spring({frame, fps, config: {damping: 200, mass: 0.9}});
  const out = interpolate(
    frame,
    [durationInFrames - 12, durationInFrames],
    [1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
  );

  const nodes = (data.nodes ?? []).slice(0, 5);
  const cx = width / 2;
  const cy = height / 2 + 40;
  const radius = Math.min(width, height) * 0.26;

  // the shared node: if two systems declare the same dependency, it is drawn
  // once, at the centre, in the channel's own amber. It is never labelled as
  // "the problem". It does not have to be.
  const deps = nodes.map((n) => (n.depends_on ?? '').trim()).filter(Boolean);
  const shared = deps.find((d, i) => deps.indexOf(d) !== i) ?? null;

  return (
    <Paper>
      <div style={{position: 'absolute', inset: 0, opacity: out}}>
        {data.kicker ? (
          <div
            style={{
              position: 'absolute',
              top: 72,
              left: 96,
              fontFamily: MONO,
              fontSize: 26,
              letterSpacing: 6,
              color: DOSSIER.copper,
              textTransform: 'uppercase',
            }}
          >
            {data.kicker}
          </div>
        ) : null}

        {data.headline ? (
          <div
            style={{
              position: 'absolute',
              top: 116,
              left: 96,
              right: 96,
              fontFamily: SANS,
              fontSize: 58,
              fontWeight: 600,
              color: DOSSIER.paper,
              lineHeight: 1.15,
            }}
          >
            {data.headline}
          </div>
        ) : null}

        <svg width={width} height={height} style={{position: 'absolute', inset: 0}}>
          {/* every system draws a line to the thing it depends on */}
          {nodes.map((n, i) => {
            const th = (2 * Math.PI * i) / Math.max(nodes.length, 1) - Math.PI / 2;
            const x = cx + radius * Math.cos(th);
            const y = cy + radius * Math.sin(th) * 0.78;
            const len = draw;
            const isShared = shared && n.depends_on === shared;
            return (
              <g key={n.name}>
                <line
                  x1={cx}
                  y1={cy}
                  x2={cx + (x - cx) * len}
                  y2={cy + (y - cy) * len}
                  stroke={isShared ? DOSSIER.amber : DOSSIER.copper}
                  strokeWidth={isShared ? 4 : 2}
                  strokeDasharray={isShared ? undefined : '10 8'}
                  opacity={0.9}
                />
                <circle
                  cx={x}
                  cy={y}
                  r={9}
                  fill={DOSSIER.basalt}
                  stroke={DOSSIER.amber}
                  strokeWidth={3}
                  opacity={len}
                />
                <text
                  x={x}
                  y={y - 26}
                  textAnchor="middle"
                  fill={DOSSIER.paper}
                  fontFamily={MONO}
                  fontSize={28}
                  letterSpacing={3}
                  opacity={len}
                >
                  {n.name.toUpperCase()}
                </text>
                {n.runs_at ? (
                  <text
                    x={x}
                    y={y + 42}
                    textAnchor="middle"
                    fill={DOSSIER.copper}
                    fontFamily={MONO}
                    fontSize={22}
                    opacity={len * 0.9}
                  >
                    {n.runs_at}
                  </text>
                ) : null}
              </g>
            );
          })}

          {/* the shared dependency. One node. Two lines. No annotation. */}
          {shared ? (
            <>
              <circle
                cx={cx}
                cy={cy}
                r={20 + 6 * Math.sin(frame / 14)}
                fill="none"
                stroke={DOSSIER.amber}
                strokeWidth={3}
                opacity={draw * 0.7}
              />
              <circle cx={cx} cy={cy} r={11} fill={DOSSIER.amber} opacity={draw} />
              <text
                x={cx}
                y={cy + 58}
                textAnchor="middle"
                fill={DOSSIER.amber}
                fontFamily={MONO}
                fontSize={26}
                letterSpacing={4}
                opacity={draw}
              >
                {shared.toUpperCase()}
              </text>
            </>
          ) : null}
        </svg>

        {data.value !== null && data.value !== undefined ? (
          <div
            style={{
              position: 'absolute',
              right: 96,
              bottom: 120,
              textAlign: 'right',
              fontFamily: MONO,
            }}
          >
            <div style={{fontSize: 96, color: DOSSIER.paper, fontWeight: 600}}>
              {data.value}
              <span style={{fontSize: 48, color: DOSSIER.copper}}>{data.suffix}</span>
            </div>
            {data.label ? (
              <div style={{fontSize: 24, letterSpacing: 4, color: DOSSIER.copper}}>
                {data.label.toUpperCase()}
              </div>
            ) : null}
          </div>
        ) : null}

        {data.body ? (
          <div
            style={{
              position: 'absolute',
              left: 96,
              bottom: 120,
              maxWidth: '46%',
              fontFamily: SANS,
              fontSize: 30,
              lineHeight: 1.45,
              color: DOSSIER.text,
              opacity: 0.85,
            }}
          >
            {data.body}
          </div>
        ) : null}
      </div>
    </Paper>
  );
};

export type VerdictData = {
  verdict: 'SURVIVED' | 'ADAPTED' | 'FAILED' | string;
  settlement?: string;
  reason?: string;
};

export const Verdict: React.FC<{data: VerdictData; durationInFrames: number}> = ({
  data,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const key = String(data.verdict || '').toUpperCase();
  const color = VERDICT_COLORS[key] ?? DOSSIER.amber;

  // A stamp, not a reveal. It arrives fast, overshoots a touch, and stops.
  // Anything smoother reads as a title card; this has to read as a decision.
  const stamp = spring({frame, fps, config: {damping: 12, stiffness: 220, mass: 0.6}});
  const scale = interpolate(stamp, [0, 1], [1.35, 1]);
  const opacity = interpolate(frame, [0, 6], [0, 1], {extrapolateRight: 'clamp'});
  const rule = interpolate(stamp, [0, 1], [0, width * 0.42]);

  return (
    <Paper>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 28,
        }}
      >
        {data.settlement ? (
          <div
            style={{
              fontFamily: MONO,
              fontSize: 28,
              letterSpacing: 8,
              color: DOSSIER.copper,
              textTransform: 'uppercase',
              opacity,
            }}
          >
            {data.settlement}
          </div>
        ) : null}

        <div style={{height: 2, width: rule, background: DOSSIER.copper, opacity: 0.5}} />

        <div
          style={{
            fontFamily: SANS,
            fontSize: 168,
            fontWeight: 800,
            letterSpacing: 14,
            color,
            transform: `scale(${scale})`,
            opacity,
            // ink pressed into paper, not a glow
            textShadow: `0 2px 0 rgba(0,0,0,0.35)`,
          }}
        >
          {key}
        </div>

        <div style={{height: 2, width: rule, background: DOSSIER.copper, opacity: 0.5}} />

        {data.reason ? (
          <div
            style={{
              marginTop: 18,
              maxWidth: '62%',
              textAlign: 'center',
              fontFamily: SANS,
              fontSize: 32,
              lineHeight: 1.5,
              color: DOSSIER.text,
              opacity: interpolate(frame, [10, 30], [0, 0.85], {
                extrapolateRight: 'clamp',
              }),
            }}
          >
            {data.reason}
          </div>
        ) : null}
      </div>
    </Paper>
  );
};

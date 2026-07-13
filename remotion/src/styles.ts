/** Terra Incognita brand tokens + rotating visual style packs.
 * Brand stays constant (amber, navy, Inter, watermark, outro);
 * style packs rotate per video so the channel never looks templated. */

export const BRAND = {
  navy: '#0A1428',
  panel: '#132441',
  amber: '#FFB020',
  amberSoft: '#FFC85C',
  sky: '#4DA3FF',
  text: '#F4F7FB',
};

/** ELSEWHERE's palette. Deliberately shares NOTHING with BRAND above —
 * different channel, different world, no colour in common. */
export const DOSSIER = {
  basalt: '#1C1814',    // the black of volcanic rock, not the black of space
  paper: '#E8DCC8',     // filed-report off-white. Never pure #FFF.
  amber: '#D98A3B',     // anything engineered: pipes, lights, system flows
  copper: '#8C6A4A',    // oxidised metal, secondary structure
  stress: '#C43B2E',    // THE RED. The failure path. Nothing else, ever.
  ink: '#2A241E',       // panel fill
  text: '#EFE4D2',
};

export type StylePack = {
  name: string;
  accent: string;
  accent2: string;
  bg: string;
  captionVariant: 'pop' | 'boxed' | 'minimal' | 'chip';
  lowerThirdVariant: 'bar' | 'chip' | 'underline';
  gradeOverlay: string; // CSS background layered over footage
  visualFilter: string; // CSS filter applied to footage
  transitionBias: 'mixed' | 'slides' | 'fades' | 'wipes';
  hud?: boolean; // telemetry pack: persistent sci-doc HUD overlay
};

export const STYLE_PACKS: Record<string, StylePack> = {
  documentary: {
    name: 'documentary',
    accent: BRAND.amber,
    accent2: BRAND.sky,
    bg: BRAND.navy,
    captionVariant: 'pop',
    lowerThirdVariant: 'bar',
    gradeOverlay:
      'linear-gradient(180deg, rgba(255,176,32,0.05) 0%, rgba(10,20,40,0.14) 100%)',
    visualFilter: 'saturate(1.06) contrast(1.04)',
    transitionBias: 'mixed',
  },
  kinetic: {
    name: 'kinetic',
    accent: BRAND.amber,
    accent2: '#FFFFFF',
    bg: '#080D1A',
    captionVariant: 'boxed',
    lowerThirdVariant: 'chip',
    gradeOverlay:
      'radial-gradient(ellipse at center, rgba(0,0,0,0) 45%, rgba(4,8,16,0.42) 100%)',
    visualFilter: 'saturate(1.16) contrast(1.12)',
    transitionBias: 'slides',
  },
  editorial: {
    name: 'editorial',
    accent: BRAND.amberSoft,
    accent2: BRAND.sky,
    bg: BRAND.navy,
    captionVariant: 'minimal',
    lowerThirdVariant: 'underline',
    gradeOverlay:
      'linear-gradient(180deg, rgba(77,163,255,0.05) 0%, rgba(10,20,40,0.10) 100%)',
    visualFilter: 'saturate(0.92) contrast(1.02)',
    transitionBias: 'fades',
  },
  noir: {
    name: 'noir',
    accent: BRAND.amber,
    accent2: '#E8ECF4',
    bg: '#06090F',
    captionVariant: 'chip',
    lowerThirdVariant: 'bar',
    gradeOverlay:
      'linear-gradient(180deg, rgba(10,20,40,0.22) 0%, rgba(6,9,15,0.38) 100%)',
    visualFilter: 'grayscale(0.85) contrast(1.18) brightness(0.96)',
    transitionBias: 'wipes',
  },
  telemetry: {
    name: 'telemetry',
    accent: BRAND.amber,
    accent2: '#6FE3D4',
    bg: '#060B14',
    captionVariant: 'minimal',
    lowerThirdVariant: 'underline',
    gradeOverlay:
      'linear-gradient(180deg, rgba(111,227,212,0.04) 0%, rgba(6,11,20,0.30) 100%)',
    visualFilter: 'saturate(0.88) contrast(1.10) brightness(0.97)',
    transitionBias: 'fades',
    hud: true,
  },

  /** ELSEWHERE — the only pack this channel uses.
   *
   * Channel 1 rotates four packs so it never looks templated. Channel 2 does
   * the opposite on purpose: ONE look, forever, because the look is the world.
   * A viewer should recognise this planet from a thumbnail at 160px with the
   * title cropped off.
   *
   * Grammar: a matte archival engineering dossier. Warm paper, basalt black,
   * amber system-flow lines, and one red — reserved exclusively for the
   * failure path, so the red itself becomes a spoiler the audience learns to
   * read. No glass. No HUD. Those are channel 1's language and using them here
   * would cannibalise the brand we are deliberately keeping separate.
   */
  dossier: {
    name: 'dossier',
    accent: DOSSIER.amber,
    accent2: DOSSIER.copper,
    bg: DOSSIER.basalt,
    captionVariant: 'minimal',
    lowerThirdVariant: 'underline',
    gradeOverlay:
      'linear-gradient(180deg, rgba(217,138,59,0.06) 0%, rgba(28,24,20,0.30) 100%)',
    // warm, slightly faded, slightly lifted blacks — a photograph that has
    // been in a filing cabinet, not a render that came out of a GPU
    visualFilter: 'saturate(0.86) contrast(0.96) sepia(0.12) brightness(1.02)',
    transitionBias: 'fades',
  },
};

export const getStyle = (name?: string): StylePack =>
  STYLE_PACKS[name ?? ''] ?? STYLE_PACKS.documentary;

/** The three endings. The colour IS the verdict — after six episodes a viewer
 * knows what has happened before the narrator says a word. */
export const VERDICT_COLORS: Record<string, string> = {
  SURVIVED: '#6E8F52',   // lichen green — earned, never triumphant
  ADAPTED: DOSSIER.amber, // the channel's own colour: the city became something else
  FAILED: DOSSIER.stress, // the red. Used nowhere else in the frame, ever.
};

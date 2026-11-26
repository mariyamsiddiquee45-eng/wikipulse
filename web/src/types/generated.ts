/* Generated from schemas/ by scripts/generate-types.mjs. Do not edit. */

export interface WikiPulseArticle {
  schema_version: 1;
  article: string;
  title: string;
  slug: string;
  url: string;
  description: string | null;
  extract: string | null;
  first_day: string;
  last_day: string;
  history: {
    d: string;
    v: number;
    s: boolean;
  }[];
  spikes: {
    day: string;
    type: "Flash" | "Slow burn" | "Recurring" | "Always-on";
    z_score: number | null;
    score: number;
  }[];
}

export interface WikiPulseDay {
  schema_version: 1;
  day: string;
  events: {
    id: string;
    label: string;
    score: number;
    type: "Flash" | "Slow burn" | "Recurring" | "Always-on";
    /**
     * @minItems 1
     */
    members: [
      {
        article: string;
        title: string;
        slug: string;
        views: number;
        baseline: number | null;
        z_score: number | null;
        class_probability: number | null;
        type: "Flash" | "Slow burn" | "Recurring" | "Always-on";
        score: number;
      },
      ...{
        article: string;
        title: string;
        slug: string;
        views: number;
        baseline: number | null;
        z_score: number | null;
        class_probability: number | null;
        type: "Flash" | "Slow burn" | "Recurring" | "Always-on";
        score: number;
      }[]
    ];
    extract: {
      text: string | null;
      url: string;
      license: "CC BY-SA 4.0";
    };
  }[];
}

export interface WikiPulseManifest {
  schema_version: 1;
  generated_at: string;
  data_through: string | null;
  first_day: string | null;
  last_day: string | null;
  days: string[];
  counts: {
    [k: string]: number;
  };
  files: {
    path: string;
    sha256: string;
    bytes: number;
    gzip_bytes: number;
  }[];
}

export interface WikiPulseMethods {
  schema_version: 1;
  generated_at: string;
  labels: number;
  classes: string[];
  detector: {
    z_threshold: number;
    minimum_views: number;
  };
  classifier: {
    model: string;
    event_f1: number;
    macro_f1: number;
    brier: number;
    labels: number;
    generated_at: string;
    baselines?: {};
  } | null;
  limitations: string[];
}

export interface WikiPulseSearchShard {
  schema_version: 1;
  prefix: string;
  articles: {
    slug: string;
    title: string;
    description: string | null;
    url: string;
    last_day: string;
  }[];
}

export interface WikiPulseStatus {
  schema_version: 1;
  last_run: string | null;
  ok: boolean;
  warnings: string[];
  data_through: string | null;
}

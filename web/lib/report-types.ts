/** TypeScript types mirroring backend AnalysisReport + ChartDataResponse.
 *
 * Loose typing — the backend schemas are the source of truth (Pydantic v2),
 * and we trust them within this repo rather than re-validating with Zod.
 */

import type { Timeframe } from "@/lib/timeframes";


export type Pivot = {
  idx: number;
  datetime: string;
  price: number;
  type: "H" | "L";
  label: "HH" | "HL" | "LH" | "LL" | "?";
  swing_pct: number;
  swing_bars: number;
  fib_retrace_of_prior: number | null;
  confirmed: boolean;
};

export type ChannelLine = { slope: number; intercept: number };
export type ChannelLines = {
  upper: ChannelLine;
  lower: ChannelLine;
  slope_angle_deg: number;
  fit_pivot_indices: number[];
};

export type FibLevel = { ratio: number; price: number };
export type FibZones = {
  last_impulse_retracements: FibLevel[];
  last_impulse_extensions: FibLevel[];
  last_correction_retracements: FibLevel[];
};

export type StructureSummary = {
  instrument: string;
  timeframe: Timeframe;
  date_range: [string, string];
  bar_count: number;
  pivots: Pivot[];
  recent_pivots: Pivot[];
  current_price: number;
  price_position_pct: number;
  channel_lines: ChannelLines;
  atr_14: number;
  realized_vol_20_pct: number;
  structural_phase_hints: string[];
  fibonacci_zones: FibZones;
};

export type WaveSegment = {
  label: string;
  start_pivot_idx: number;
  end_pivot_idx: number;
};

export type ElliottCount = {
  pattern: string;
  degree: string;
  waves: WaveSegment[];
  current_wave: string;
  rationale: string;
};

export type NeowaveCount = {
  pattern: string;
  mono_waves: WaveSegment[];
  current_position: string;
  rationale: string;
};

export type RuleResult = {
  rule_id: string;
  name: string;
  severity: "hard" | "soft";
  passed: boolean;
  message: string;
};

export type RuleCompliance = { rule_results: RuleResult[] };

export type InvalidationLevel = {
  price: number;
  direction: "above" | "below";
  reason: string;
};

export type ValidatedElliottCount = {
  count: ElliottCount;
  compliance: RuleCompliance;
  invalidation: InvalidationLevel | null;
};

export type ValidatedNeowaveCount = {
  count: NeowaveCount;
  compliance: RuleCompliance;
  invalidation: InvalidationLevel | null;
};

export type ValidationOutcome = {
  timeframe: string;
  elliott_surviving: ValidatedElliottCount[];
  elliott_rejected: ValidatedElliottCount[];
  neowave_surviving: ValidatedNeowaveCount[];
  neowave_rejected: ValidatedNeowaveCount[];
};

export type TimeframeReport = {
  timeframe: Timeframe;
  structure: StructureSummary;
  validation: ValidationOutcome;
};

export type CountRef = {
  timeframe: string;
  framework: "elliott" | "neowave";
  count_idx: number;
};

export type SynthesisScenario = {
  rank: 1 | 2 | 3;
  label: "Primary" | "Alternate" | "Counter";
  summary: string;
  cross_timeframe_alignment: string;
  cross_framework_agreement: string;
  supporting: CountRef[];
  invalidation_levels: InvalidationLevel[];
};

export type SynthesisReport = {
  scenarios: SynthesisScenario[];
  methodology_note: string;
};

export type CostBreakdownEntry = {
  agent_name: string;
  model: string;
  is_test: boolean;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  cache_hit: boolean;
  timeframe: string | null;
};

export type AnalysisReport = {
  disclaimer: string;
  run_id: string;
  instrument_name: string;
  status:
    | "pending"
    | "running"
    | "completed"
    | "failed"
    | "rejected_cost_cap";
  started_at: string;
  completed_at: string | null;
  timeframes: TimeframeReport[];
  synthesis: SynthesisReport | null;
  cost_breakdown: CostBreakdownEntry[];
  total_cost_usd: number;
  error: string | null;
};

export type ChartBar = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type ChartDataResponse = {
  disclaimer: string;
  run_id: string;
  timeframe: Timeframe;
  instrument_name: string;
  bars: ChartBar[];
  pivots: Pivot[];
  elliott_counts: ValidatedElliottCount[];
  neowave_counts: ValidatedNeowaveCount[];
  invalidation_levels: InvalidationLevel[];
  fibonacci_zones: FibZones | null;
  channel_lines: ChannelLines;
};

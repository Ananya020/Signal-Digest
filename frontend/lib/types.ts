export type Severity = "notable" | "significant" | "extreme";

export type Freshness = "LIVE" | "RECENT" | "DELAYED" | "STALE" | "UNAVAILABLE";

export interface Flag {
  id: number;
  ticker: string;
  trading_day: string;
  signal_type: "price_zscore" | "volatility_regime";
  z_score: number | null;
  severity: Severity;
  severity_rank: 1 | 2 | 3;
  volume_ratio: number | null;
  sector_relative: "sector_wide" | "stock_specific" | null;
  computed_at: string;
  provider_state_at_computation: string;
  /** Step A ("since you last checked"): the flag's severity_rank/z_score at
   * the moment it was last acked, if this flag has prior ack history for
   * this watchlist and the snapshot differs from its current values.
   * `null` for a flag with no such history — never fabricated. */
  since_last_ack: { severity_rank_at_ack: 1 | 2 | 3 | null; z_score_at_ack: number | null; acked_at: string } | null;
}

export interface DigestResponse {
  freshness: Freshness;
  detail: string;
  flags: Flag[];
  /** Deterministic template synthesis over `flags` — no LLM, computed
   * server-side. `null` when there are zero active signals; render the
   * existing calm empty-state copy in that case, not this field. */
  brief: string | null;
}

export interface ProviderStatus {
  state: Freshness;
  last_successful_fetch: string;
  age_seconds: number;
  detail: string;
  demo_mode: boolean;
}

export interface EvidencePoint {
  date: string;
  return: number;
  price: number;
}

export interface EvidenceResponse {
  ticker: string;
  window_start: string;
  window_end: string;
  mean_return: number;
  stdev_return: number | null;
  points: EvidencePoint[];
  flagged_point: { date: string; return: number; z_score: number | null };
}

export interface Watchlist {
  id: string;
  name: string;
  created_at: string;
}

export interface TickerInfo {
  ticker: string;
  name: string;
  sector: string;
}

export type FaultMode = "outage" | "stale" | "recover";

/** One row of a ticker's historical audit trail (`GET /tickers/{ticker}/flags`)
 * — deliberately a narrower shape than `Flag`: only the fields the History
 * panel actually shows, not the full flags-table row. */
export interface HistoricalFlag {
  trading_day: string;
  signal_type: "price_zscore" | "volatility_regime";
  z_score: number | null;
  severity: Severity;
}

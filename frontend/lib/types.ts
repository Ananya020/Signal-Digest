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
}

export interface DigestResponse {
  freshness: Freshness;
  detail: string;
  flags: Flag[];
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

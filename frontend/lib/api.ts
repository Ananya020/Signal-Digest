import type {
  DigestResponse,
  EvidenceResponse,
  FaultMode,
  HistoricalFlag,
  ProviderStatus,
  TickerInfo,
  Watchlist,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export async function listWatchlists(): Promise<Watchlist[]> {
  const res = await fetch(`${BASE_URL}/watchlists`);
  return json(res);
}

export async function createWatchlist(name: string): Promise<{ id: string; user_id: string; name: string }> {
  const res = await fetch(`${BASE_URL}/watchlists`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  return json(res);
}

export async function addWatchlistItem(watchlistId: string, ticker: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/watchlists/${watchlistId}/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker }),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
}

/** Result of a digest poll: either the server said nothing changed (304,
 * caller should keep its current state) or fresh data + a new ETag. */
export type DigestPollResult =
  | { notModified: true }
  | { notModified: false; data: DigestResponse; etag: string | null };

export async function fetchDigest(watchlistId: string, previousEtag: string | null): Promise<DigestPollResult> {
  const headers: Record<string, string> = {};
  if (previousEtag) headers["If-None-Match"] = previousEtag;

  const res = await fetch(`${BASE_URL}/watchlists/${watchlistId}/digest`, { headers });

  if (res.status === 304) {
    return { notModified: true };
  }
  const data = await json<DigestResponse>(res);
  return { notModified: false, data, etag: res.headers.get("ETag") };
}

export async function ackFlags(
  watchlistId: string,
  flagIds: number[]
): Promise<{ acked: number[]; ignored: { id: number; reason: string }[]; hash: string }> {
  const res = await fetch(`${BASE_URL}/watchlists/${watchlistId}/ack`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ flag_ids: flagIds }),
  });
  return json(res);
}

export async function listWatchlistItems(watchlistId: string): Promise<TickerInfo[]> {
  const res = await fetch(`${BASE_URL}/watchlists/${watchlistId}/items`);
  return json(res);
}

export async function removeWatchlistItem(watchlistId: string, ticker: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/watchlists/${watchlistId}/items/${ticker}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
}

export async function fetchProviderStatus(): Promise<ProviderStatus> {
  const res = await fetch(`${BASE_URL}/provider/status`);
  return json(res);
}

export async function setFaultMode(mode: FaultMode): Promise<{ mode: string; frozen_at: string | null }> {
  const res = await fetch(`${BASE_URL}/admin/fault`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  return json(res);
}

export async function fetchEvidence(ticker: string, flagId: number): Promise<EvidenceResponse> {
  const res = await fetch(`${BASE_URL}/tickers/${ticker}/evidence?flag_id=${flagId}`);
  return json(res);
}

export async function listTickers(): Promise<TickerInfo[]> {
  const res = await fetch(`${BASE_URL}/tickers`);
  return json(res);
}

/** The ticker's full historical audit trail — every recorded flag, reverse
 * chronological, independent of watchlist membership or ack state. Distinct
 * from the digest (current, unacked, watchlist-scoped). */
export async function fetchTickerFlags(ticker: string): Promise<HistoricalFlag[]> {
  const res = await fetch(`${BASE_URL}/tickers/${ticker}/flags`);
  return json(res);
}

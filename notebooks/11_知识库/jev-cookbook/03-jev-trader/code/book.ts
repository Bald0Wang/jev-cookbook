/**
 * Minimum-round-trip Kuru order book reader.
 *
 * One raw JSON-RPC `eth_call` to `getL2Book()` (selector 0x46fdfbb1), decoded here. The SDK's
 * `getFormattedL2OrderBook` makes two sequential eth_calls (getL2Book, then getVaultParams pinned
 * to the returned block). On MON-USDC the Kuru AMM vault has vaultBidOrderSize == 0, so the SDK
 * merges zero vault levels and the second call is pure latency. If the vault ever goes live
 * (`vaultActive(await readVaultParams(...))`), pass `{ vault: true }`: both calls go in ONE
 * JSON-RPC batch (one HTTP round trip) and the AMM ladder is merged exactly as the SDK does it.
 *
 * Number formatting replicates the SDK bit-for-bit (parseFloat of the decimal string, floor bids /
 * ceil asks to tick, group by price in the same order) so bid/ask/mid/imbalance match exactly.
 */
import type { ethers } from "ethers";
import type { Book } from "./market";

export type Level = [price: number, size: number];

/** Subset of Kuru.MarketParams we need (BigNumber or anything with toString()). */
export interface BookParams {
  pricePrecision: { toString(): string };
  sizePrecision: { toString(): string };
  tickSize: { toString(): string };
}

export interface ReadBookOptions {
  /** Also fetch getVaultParams in the same HTTP batch and merge AMM levels. Default false. */
  vault?: boolean;
  /** eth_call block tag. Default "latest". */
  blockTag?: string;
  timeoutMs?: number;
}

export interface VaultParams {
  kuruAmmVault: string;
  vaultBestBid: bigint;
  bidPartiallyFilledSize: bigint;
  vaultBestAsk: bigint;
  askPartiallyFilledSize: bigint;
  vaultBidOrderSize: bigint;
  vaultAskOrderSize: bigint;
  spread: bigint;
}

export interface L2Book {
  block: number;
  bids: Level[]; // raw (unrounded) floats, on-chain order
  asks: Level[];
}

export const SEL_GET_L2_BOOK = "0x46fdfbb1"; // getL2Book()
export const SEL_GET_VAULT_PARAMS = "0x88bb4f60"; // getVaultParams()
const ADDRESS_ZERO = "0x0000000000000000000000000000000000000000";
const MAX_UINT256 = (1n << 256n) - 1n;

type RpcProvider = ethers.providers.JsonRpcProvider | string;
const urlOf = (p: RpcProvider) => (typeof p === "string" ? p : p.connection.url);

async function rpcPost(url: string, body: unknown, timeoutMs?: number): Promise<any> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal: timeoutMs ? AbortSignal.timeout(timeoutMs) : undefined,
  });
  if (!res.ok) throw new Error(`rpc http ${res.status}`);
  return res.json();
}

const ethCall = (id: number, to: string, data: string, tag: string) => ({ jsonrpc: "2.0", id, method: "eth_call", params: [{ to, data }, tag] });

/** Read the book. One eth_call by default; one batched HTTP request with `vault: true`. */
export async function readBook(provider: RpcProvider, market: string, params: BookParams, opts: ReadBookOptions = {}): Promise<Book> {
  const url = urlOf(provider);
  const tag = opts.blockTag ?? "latest";
  const l2Call = ethCall(1, market, SEL_GET_L2_BOOK, tag);
  const json = await rpcPost(url, opts.vault ? [l2Call, ethCall(2, market, SEL_GET_VAULT_PARAMS, tag)] : l2Call, opts.timeoutMs);
  const responses: any[] = Array.isArray(json) ? json : [json];
  const byId = new Map(responses.map((r) => [r.id, r]));
  const l2 = byId.get(1);
  if (!l2?.result) throw new Error(`getL2Book: ${l2?.error?.message ?? "no result"}`);
  let vault: VaultParams | undefined;
  if (opts.vault) {
    const v = byId.get(2);
    if (!v?.result) throw new Error(`getVaultParams: ${v?.error?.message ?? "no result"}`);
    vault = decodeVaultParams(v.result);
  }
  return buildBook(l2.result, params, vault);
}

/** One eth_call. Use every N blocks to decide whether `vault: true` is needed. */
export async function readVaultParams(provider: RpcProvider, market: string, blockTag = "latest"): Promise<VaultParams> {
  const json = await rpcPost(urlOf(provider), ethCall(1, market, SEL_GET_VAULT_PARAMS, blockTag));
  if (!json?.result) throw new Error(`getVaultParams: ${json?.error?.message ?? "no result"}`);
  return decodeVaultParams(json.result);
}

export const vaultActive = (v: VaultParams) => v.vaultBidOrderSize !== 0n && v.kuruAmmVault.toLowerCase() !== ADDRESS_ZERO;

// ---------------------------------------------------------------------------------------------
// Decoding

/** Unwrap ABI-encoded `bytes` return data (offset word, length word, payload) to "0x" + payload. */
export function abiBytesPayload(abiHex: string): string {
  const hex = abiHex.startsWith("0x") ? abiHex.slice(2) : abiHex;
  const offset = Number(BigInt("0x" + hex.slice(0, 64))) * 2;
  const length = Number(BigInt("0x" + hex.slice(offset, offset + 64))) * 2;
  return "0x" + hex.slice(offset + 64, offset + 64 + length);
}

/** Decode the getL2Book() return value (ABI-encoded bytes) into block number and raw levels. */
export function decodeL2Book(abiHex: string, priceDec: number, sizeDec: number): L2Book {
  const data = abiBytesPayload(abiHex);
  const block = Number(BigInt("0x" + data.slice(2, 66)));
  let offset = 66;
  const readSide = (): Level[] => {
    const out: Level[] = [];
    while (offset < data.length) {
      const price = BigInt("0x" + data.slice(offset, offset + 64));
      offset += 64;
      if (price === 0n) break;
      const size = BigInt("0x" + data.slice(offset, offset + 64));
      offset += 64;
      out.push([toFloat(price, priceDec), toFloat(size, sizeDec)]);
    }
    return out;
  };
  const bids = readSide();
  const asks = readSide();
  return { block, bids, asks };
}

export function decodeVaultParams(abiHex: string): VaultParams {
  const hex = abiHex.startsWith("0x") ? abiHex.slice(2) : abiHex;
  const word = (i: number) => BigInt("0x" + hex.slice(i * 64, i * 64 + 64));
  return {
    kuruAmmVault: "0x" + hex.slice(24, 64),
    vaultBestBid: word(1),
    bidPartiallyFilledSize: word(2),
    vaultBestAsk: word(3),
    askPartiallyFilledSize: word(4),
    vaultBidOrderSize: word(5),
    vaultAskOrderSize: word(6),
    spread: word(7),
  };
}

/** Same result as parseFloat(ethers.utils.formatUnits(x, decimals)). */
export function toFloat(x: bigint, decimals: number): number {
  const neg = x < 0n;
  let s = (neg ? -x : x).toString();
  if (decimals === 0) return neg ? -Number(s) : Number(s);
  if (s.length <= decimals) s = "0".repeat(decimals - s.length + 1) + s;
  const n = Number(s.slice(0, s.length - decimals) + "." + s.slice(s.length - decimals));
  return neg ? -n : n;
}

/** SDK log10BigNumber: digit count minus one (precisions are powers of ten). */
export const log10 = (x: { toString(): string }) => x.toString().length - 1;

const mulDivRound = (v: bigint, m: bigint, d: bigint) => (v * m + d / 2n) / d;

/** Port of the SDK's getAmmPricesFromVaultParams (vault prices are 1e18-scaled). */
export function ammLevels(v: VaultParams, sizeDec: number): { bids: Level[]; asks: Level[] } {
  const bids: Level[] = [], asks: Level[] = [];
  if (!vaultActive(v)) return { bids, asks };
  const sc = v.spread / 10n;
  const firstBid = v.vaultBidOrderSize - v.bidPartiallyFilledSize;
  const firstAsk = v.vaultAskOrderSize - v.askPartiallyFilledSize;
  let bp = v.vaultBestBid, bs = v.vaultBidOrderSize, ap = v.vaultBestAsk, as = v.vaultAskOrderSize;
  for (let i = 0; i < 300; i++) {
    if (bp === 0n) break;
    bids.push([toFloat(bp, 18), toFloat(i === 0 ? firstBid : bs, sizeDec)]);
    bp = mulDivRound(bp, 1000n, 1000n + sc);
    bs = mulDivRound(bs, 2000n + sc, 2000n);
  }
  for (let i = 0; i < 300; i++) {
    if (ap >= MAX_UINT256) break;
    asks.push([toFloat(ap, 18), toFloat(i === 0 ? firstAsk : as, sizeDec)]);
    ap = mulDivRound(ap, 1000n + sc, 1000n);
    as = mulDivRound(as, 2000n, 2000n + sc);
  }
  return { bids, asks };
}

/** Sum sizes per price, preserving first-seen order (SDK combinePrices / groupOrders). */
function group(levels: Level[], key: (p: number) => number = (p) => p): Level[] {
  const m = new Map<number, number>();
  for (const [p, s] of levels) { const k = key(p); m.set(k, (m.get(k) ?? 0) + s); }
  return Array.from(m.entries());
}
const desc = (a: Level, b: Level) => b[0] - a[0];

/** Formatted levels exactly as Kuru.OrderBook.getFormattedL2OrderBook produces them (both sorted descending). */
export function formatLevels(l2: L2Book, params: BookParams, vault?: VaultParams): { bids: Level[]; asks: Level[] } {
  const decimals = log10(params.pricePrecision) - log10(params.tickSize);
  const mult = 10 ** decimals;
  const floorTick = (p: number) => Math.floor(p * mult) / mult;
  const ceilTick = (p: number) => Math.ceil(p * mult) / mult;
  const amm = vault ? ammLevels(vault, log10(params.sizePrecision)) : { bids: [], asks: [] };
  const bids = group([...l2.bids, ...amm.bids]).sort(desc);
  const asks = group([...l2.asks, ...amm.asks]).sort(desc);
  return { bids: group(bids, floorTick).sort(desc), asks: group(asks, ceilTick).sort(desc) };
}

/** Build the trader's Book from raw getL2Book return data (+ optional decoded vault params). */
export function buildBook(l2Hex: string, params: BookParams, vault?: VaultParams): Book {
  const l2 = decodeL2Book(l2Hex, log10(params.pricePrecision), log10(params.sizePrecision));
  const { bids, asks } = formatLevels(l2, params, vault);
  if (!bids.length || !asks.length) throw new Error(`empty book side at block ${l2.block} (bids=${bids.length} asks=${asks.length})`);
  const bid = bids[0]![0], ask = asks[asks.length - 1]![0];
  const mid = (bid + ask) / 2;
  const near = (levels: Level[]) => levels.filter((l) => Math.abs(l[0] - mid) / mid < 0.01).reduce((s, l) => s + l[1], 0);
  const bidDepth = near(bids), askDepth = near(asks);
  const within = (levels: Level[], bps: number) => levels.filter((l) => (Math.abs(l[0] - mid) / mid) * 10_000 <= bps).reduce((s, l) => s + l[1], 0);
  const depthBps: Book["depthBps"] = {};
  for (const b of [10, 25, 50]) depthBps[String(b)] = { bid: within(bids, b), ask: within(asks, b) };
  return {
    block: l2.block, bid, ask, mid,
    spreadBps: ((ask - bid) / mid) * 10_000,
    imbalance: bidDepth + askDepth ? (bidDepth - askDepth) / (bidDepth + askDepth) : 0,
    levels: { bids: bids.slice(0, 5), asks: asks.slice(-5).reverse() },
    depthBps,
  };
}

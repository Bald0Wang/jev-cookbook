# Jev Trader — Product Spec

## One line
A live public dashboard showing an AI make a real trade decision on Monad every 300 ms block.

## What it is
A single-page web app. A TypeSafe "Jev" model (a System One model: no text output, returns typed decisions with probabilities in ~100 ms) watches the MON-USDC order book on Kuru, Monad's on-chain exchange. Every block (300 ms) it answers one question: buy or sell. Every block is a real order from a real wallet, confirmed in the same block. The page shows this happening live.

## Who it is for
1. Crypto Twitter, via a 20-second screen-recorded clip and a link. They have three seconds to get it.
2. People who click through and watch for five minutes. They should be able to verify everything: wallet, transactions, cost.

## The message
Primary: "This AI makes a real trade decision every 300 ms on Monad."
Secondary punchline: "The AI costs less than the gas." (Jev inference for an hour ≈ $0.20; gas for the same hour ≈ $2–5.)
Nothing on screen may compete with these two lines.

## Design principles
- One screen. No navigation, no settings, no login.
- Motion is the content. Something visibly changes every 300 ms, and the viewer should feel the rhythm of the chain.
- Everything shown is real and verifiable. Wallet address, tx hashes, block heights link to the explorer.
- Legible in a compressed 1080p clip and at phone width. Big numbers, high contrast, no thin type.
- Restraint. Dark trading-desk aesthetic. Green = buy, red = sell, neutral grey = hold. One accent color (Monad purple is acceptable). No gradients, no decorative charts.
- Honest. Every block trades, so spread and gas bleed are visible. Losses are shown as plainly as gains. A "stand-in model" badge appears when real Jev is not connected.

## Layout (desktop 16:9 primary; mobile stacks vertically in the same order)

1. Header strip
   - Title (working name: Jev Trader), live indicator dot, "block 105,416,201" ticking every 300 ms.
   - Wallet address, truncated, with copy and explorer link.
   - Model badge: "jev-latest" (or "stand-in" in amber).
   - Uptime.

2. Hero: price chart
   - MON/USDC mid price, rolling window (default last 5 minutes ≈ 1,000 blocks; toggle 1m / 5m / 15m).
   - A marker on every fill: green up-triangle for buy, red down-triangle for sell. Nearly every block has one.
   - Current price in large type at the right edge of the line. Position size and side shown as a small pill (e.g. "long 12 MON").

3. Decision panel (the flicker; this is the signature element)
   - Updates every block. Shows the decision for the current block.
   - Two-way probability bar: buy vs sell with percentages. The chosen side is highlighted. (This is also the "will price go up" number: buy probability = up probability.)
   - Decision latency in ms for this block (e.g. "94 ms").
   - A tiny per-block tick strip along the bottom: the last 60 blocks as small squares, green/red for buy/sell, amber for "late" (model missed the block, no trade). Scrolls left as blocks arrive.

4. Counters row (six tiles, tabular numerals, all live)
   - Blocks seen
   - Decisions made
   - Trades executed
   - Jev spend (USD, four decimals)
   - Gas spend (MON and USD)
   - P&L (MON and %). Red or green. No smoothing, no hiding.
   Jev spend and gas spend sit adjacent so the "AI costs less than gas" comparison is visual without a caption.

5. Trade tape
   - Last 12 fills: block, side, size, price, decision latency, tx hash (link).
   - New rows slide in from the top.

6. Footer
   - One-line disclaimer: experimental demo, tiny bankroll, not financial advice, the model is not trying to be profitable.
   - Credits and links: TypeSafe (Jev), Monad, Kuru, source repo. Credit, not co-branding.

## States
- Live: everything above.
- Model late: block ticks amber, decision panel shows "late — held", counter for late blocks increments.
- RPC disconnected: header dot turns red, chart freezes with a "reconnecting" overlay, counters stop.
- Out of funds / paused: banner across the hero, decisions continue in dry-run (shown greyed) but no fills.
- Replay: plays back a recorded session at real speed, clearly labelled "replay", for recording clips or when markets are dead.
- Stand-in model: amber badge in header, otherwise identical.

## Interactions (deliberately few)
- Hover a chart marker: tooltip with block, side, size, price, probabilities at that block.
- Click tx hash or block: opens explorer.
- Click wallet: copies address.
- Chart window toggle.
- Nothing else. No trading controls for viewers.

## Live data shape (delivered over a server stream, one event per block)
- block, timestamp
- mid, bestBid, bestAsk, spread
- decision: action (buy | sell; hold only when late), probabilities {buy, sell, hold}, upIn10 (= buy probability), latencyMs, late (bool)
- fill (optional): side, size, price, txHash, gasMon
- position: side, size, entryPrice, unrealizedMon
- totals: blocks, decisions, trades, jevUsd, gasMon, gasUsd, pnlMon, pnlPct, lateBlocks

## Non-goals
- No comparison with other models. One model, one market.
- No memecoins, no launchpad feed.
- No user wallets, no user trading, no accounts.
- No historical analytics, no backtests, no strategy explanation.
- No chat, no text output from the model anywhere.

## Technical constraints the design must respect
- 3.3 updates per second, indefinitely. Animations must be cheap: transforms and opacity only, no layout thrash.
- Constantly changing numbers need tabular (fixed-width) numerals so tiles do not jitter.
- Must stay legible with a fill on nearly every block: markers must not smear into a solid band at 3 per second (thin markers, or aggregate when zoomed out).
- Screen-recordable: no elements that only make sense with hover.
- Works at 390 px wide.

## Success criterion
A viewer with no context, watching a 20-second clip on a phone with the sound off, understands within three seconds that an AI is trading on a blockchain every fraction of a second, and can see what it costs. Then they share it.

# Swing Trading App — Product Spec

**Source:** Working session between Carlos (strategy author) and Juan (engineering owner). Transcript: `transcript_timestamped.txt` (~92 min). Citations below reference timestamp ranges from that transcript.

**Status:** Draft v1, based on a single walkthrough. Strategy already exists and backtests in TradingView; this spec covers what needs to be built around it to make it executable.

---

## 1. Meeting Summary

Carlos walked Juan through a swing-trading strategy he has built and validated in TradingView using PineScript. The system combines several classical technical indicators (ADX, MACD, MACD histogram, linear-regression channels, RSI/Stochastic divergence) across multiple chart types (candles, Heikin Ashi, Renko, Kagi) and timeframes (10m → daily). Each chart produces a numeric score via a custom rule set Carlos designed, scores are aggregated into a single oscillator, and the oscillator's zero-line crossings produce buy/sell signals. A parallel "regime" scorer applied to four broad-market ETFs (SPY, RSP, QQQ, IWM) classifies overall market conditions (choppy → strongest) and modulates how signals should be acted on.

Carlos demonstrated backtests across GLW, FXY, BTC, NVDA, and SPY going back to 2015 (and 2007–2009 for SPY). The strategy consistently outperforms buy-and-hold on individual tickers, especially when short selling is enabled, and correctly side-stepped the 2008 crash and the COVID drawdown. The session ended with agreement on a phased plan: first attempt a low-code path (TradingView → Alpaca via TradingView's broker integration), and if that proves insufficient, build a custom trade bot that consumes the strategy's signals and routes orders to Alpaca directly. Carlos will share his TradingView Pro credentials with Juan for the feasibility investigation.

---

## 2. Goals & Non-Goals

**Goals**
- Take the existing PineScript strategy and execute its buy/sell signals automatically against a brokerage account.
- Start in paper-trading mode to validate live behavior matches backtests.
- Preserve the strategy's core mechanic: one signal → close any existing position → open opposite full position, with compounding.
- Reach a "go-live" state where Carlos has confidence to switch from paper to real capital.

**Non-Goals (per Carlos, [54:14 — 1:32:00])**
- Re-deriving or re-implementing the strategy itself; that work is owned by Carlos in PineScript.
- Partial position sizing, complex risk overlays, or stop-loss orchestration in v1 (signals already control exits).
- Multi-account / multi-user features. Single user (Carlos), single broker account.

---

## 3. Glossary

| Term | Meaning (as Carlos defined it) |
|---|---|
| **Trigger chart** | The fastest timeframe whose zero-cross produces signals. 10-min for day trading, **4-hour for swing trading** (the focus of this app). |
| **Score** | Net integer score for one chart, computed by the indicator system. |
| **Regime** | Score of the overall market, computed across SPY / RSP / QQQ / IWM on 30m / 1h / 4h / daily. Determines whether to trend-follow or look for reversals. |
| **Oscillator** | Carlos's custom indicator that combines all per-chart scores into a single line; zero-line crossings produce signals. |
| **Pyramiding** | Layering into a position over time. Carlos is *still validating* whether this helps for day trading [35:42 — 36:30]. Not in scope for swing v1. |
| **Renko / Kagi** | Chart types that plot bars only when price moves a magnitude threshold (time-independent). Used to filter noise. |

---

## 4. System Overview

```
TradingView (Carlos's PineScript)             [exists today]
  ├─ Per-ticker scorer  ─┐
  ├─ Regime scorer       ├──► Combined oscillator ──► Buy/sell signal
  └─ MACD histogram      ┘                                │
                                                          ▼
                                              ┌──────────────────────┐
                                              │  Signal-to-order     │
                                              │  bridge (TO BUILD)   │
                                              └──────────────────────┘
                                                          │
                                                          ▼
                                                   Alpaca (broker)
                                                  paper → live account
```

Two integration paths, in priority order:

**Path A — TradingView's native broker integration (preferred, [1:33:00 — 1:36:00])**
Use TradingView's built-in Alpaca connector. If TradingView can fire orders directly to Alpaca on strategy-script signals, no custom backend is required.

**Path B — Custom trade bot (fallback, [1:35:30 — 1:36:30])**
TradingView publishes webhook alerts on strategy signals → small service receives webhook → calls Alpaca REST API → records execution. Requires a separately scoped session with Carlos to formally document the point system so logic can be reimplemented if needed (transcript closes on this commitment, [1:36:00]).

---

## 5. Strategy Inputs — Charts & Indicators

Carlos walked through the 8-chart layout used for the **day-trading** version. The swing version reuses the same scoring rules but rescales the timeframes [1:13 — 1:24]. **Capture this here only because the developer building the bridge needs to know what the PineScript is producing — the developer does not need to reimplement these.**

### 5.1 Per-ticker chart panel (day-trading layout shown)

| Position | Chart | Indicators applied |
|---|---|---|
| Bottom-left (trigger) | **10-min candle** | ADX, MACD, MACD histogram |
| Bottom-mid | **1-hour candle** | ADX, MACD, linear regression channels (20/50/100 period), RSI/Stochastic divergence |
| Bottom-mid | **30-min candle** | Same as 1-hour |
| Bottom-right | **1-hour Heikin Ashi** | Same indicator set |
| Top row | **Renko (default magnitude)**, **30-min Renko**, **1-hour Renko**, **Kagi** | Score-only; meant to reinforce signal by stripping time noise |

For **swing trading**, the trigger chart shifts to **4-hour** [54:53 — 55:30]. PineScript's inability to query Renko data forced Carlos to substitute a mix of Heikin Ashi + candle charts for the swing version [45:48 — 46:48]. **Open question:** does the developer need to know the exact swing chart set, or does the PineScript abstract this away?

### 5.2 Per-chart score: ADX

| Condition | Score |
|---|---|
| ADX < 20 | 0 (no trend, ignore) |
| 20 ≤ ADX < 25 | +1 (in direction of slope) |
| 25 ≤ ADX < 35 | +2 |
| 35 ≤ ADX < 50 | +3 |
| ADX ≥ 50 | +4 |

Modifiers (apply to any nonzero score):
- Slope of ADX up + area maintaining or expanding → score as above.
- Slope down → subtract 1 from the bucket score (so +4 → +3, +3 → +2, etc.).
- Below 35 and sloping down, floor at +1 (still trending) [22:11 — 22:23].

### 5.3 Per-chart score: MACD

| MACD position | Slope | Score |
|---|---|---|
| Above 0 | Up | +2 |
| Above 0 | Down | −1 (earliest sell warning) |
| Below 0 | Down | −2 |
| Below 0 | Up | +1 |

MACD is the **fastest** indicator to flip, used as the earliest warning signal [22:34 — 23:46].

### 5.4 Per-chart score: MACD Histogram

Added later as an experimental control parameter; back-testing showed it improved swing profitability [39:33 — 41:00].

| Condition | Score |
|---|---|
| Histogram increasing above 0 | +1 |
| Histogram decreasing below 0 | −1 |
| Otherwise | 0 |

The histogram measures the distance between the MACD line and its signal line (acceleration of the move).

### 5.5 Linear regression channels (20 / 50 / 100 period)

Drawn on the 1-hour and 30-min candle charts only [13:54 — 14:18].
- Channels at ±2 standard deviations (outer bounds) and half-standard-deviation guides between.
- Slope of each channel indicates trend over its lookback period.
- **Alignment** of all three (20 + 50 + 100 sloping the same way) signals the strongest moves [13:00 — 13:33]. Carlos awards extra score when aligned (exact point value not stated — **open question**).
- Used for **price positioning** vs the channel (top of band = overextended; bottom of band = room to run) [1:21:30 — 1:22:50].

### 5.6 Divergence indicator (RSI-based, 1-hour chart only)

Engine: takes RSI measurements; flags when price makes higher highs but RSI makes lower lows (or inverse) [25:32 — 27:51].
- **Rarely used in the additive score.** Used **only as a counter-trend brake** when the price has already had a big run and is at ±2 to ±3 standard deviations in the linear regression channel.
- Each divergence triggered → −1 point.
- Purpose: discourage entries at overextended levels and encourage profit-taking.

### 5.7 Net per-chart score & threshold filtering

Each chart's indicators sum to a net integer ("the 5", "+3", etc., visible on Carlos's chart). The combined oscillator (see §6) only reacts when scores cross a threshold; below threshold it ignores everything as "choppy" [17:30 — 18:00].

---

## 6. The Combined Oscillator

The oscillator is the single output line the strategy script trades against [38:00 — 39:30].

- **Inputs:** all per-chart scores + regime score + MACD histogram weights + divergence brakes.
- **Output:** a numeric value with sign and color.
- **Signal rules:**
  - Line crosses **above 0** = **buy** signal.
  - Line crosses **below 0** = **sell** signal.
- **Visual encoding:**
  - Color = strength. Red = strong (acceleration), yellow/orange = weak (wait for confirmation), green = bullish strength.
  - Slope = direction (which side of zero it's heading toward).
- **On-chart markers:**
  - Green triangle/diamond on the chart = buy signal fired.
  - Red triangle/diamond = sell signal fired.
  - Orange circle = zero-cross occurred but strength is weak; **wait for color to confirm** (red or green) before treating as a real signal [50:09 — 50:54].

**Position bias** (above/below 0) is described as a probabilistic lean, not a guarantee [51:38 — 52:08].

---

## 7. Regime System

Applied to **four ETFs simultaneously**, across **four timeframes** [29:55 — 31:30]:

| ETF | Purpose |
|---|---|
| SPY | Cap-weighted S&P 500 — what the megacaps are doing |
| RSP | **Equal-weighted** S&P 500 — breadth (is the move broad or driven by 10 stocks?) |
| QQQ | Tech/NASDAQ proxy |
| IWM | Russell 2000 — small caps |

Timeframes: 30-minute, 1-hour, 4-hour, daily — all **candle charts only**, no Renko/Kagi in the regime calculation [31:25 — 31:33].

### Regime zones (visualized as background color on the oscillator pane)

| Zone | Color | Behavior |
|---|---|---|
| Choppy (regime 0) | Gray | Most signals will whipsaw. **Look for reversal trades**, not trend-following. Carlos: "score under ~35 points = choppy" [37:14 — 37:46]. |
| Mild trending | Teal / light blue | Next regime up |
| Strong | Purple-blue | Near top |
| Strongest | Purple | Strongest market trend, trust signals fully |

Numeric threshold values for each zone are configurable; **35 is the choppy ceiling Carlos cited** but he flagged he's still tuning [37:46 — 38:24].

### Regime check cadence

| Carlos's manual practice | Target for bot |
|---|---|
| Regime chart: every 30 min | Every 10 min |
| Per-ticker charts: every 10 min | Every 10 min for day; every 4h for swing |

---

## 8. Backtest / Strategy Script Behavior

The PineScript strategy already exists and runs in TradingView's Strategy Tester [48:09 — onward].

**Parameters surfaced in the UI** [54:43 — 55:30]:
- Timeframe selector (day-trading bundle vs swing 4-hour). **Swing 4-hour is the production setting.**
- Initial capital (default 10,000; user can set 100,000 etc.).
- Compounding toggle (**on by default**).
- Allow long trades (toggle).
- Allow short trades (toggle).

**Position sizing logic** [55:08 — 55:26]:
- All capital goes into each trade. On exit, all proceeds (gain or loss) roll into the next trade — natural compounding.

**Outputs of the strategy tester:**
- Equity curve (green) vs buy-and-hold curve (blue).
- Total return % vs buy-and-hold %.
- Per-trade log with entry/exit timestamps and P&L (used for manual auditing).

**Validated backtest results Carlos showed (for sanity-checking the bridge later):**

| Ticker | Window | Strategy | Buy-and-hold |
|---|---|---|---|
| GLW (Corning) | 2015–2026, long+short | ~1,000% | 517% |
| GLW | 2015–2026, long-only | 858% | ~500% |
| FXY (Yen) | 2015–2026, long-only | +10% | Loss |
| FXY | 2015–2026, long+short | +62% | Loss |
| BTC | 2015–2026 | 7,000,000% (Carlos suspects this is implausible — **flag for validation**) | Billions% |
| NVDA | last several years | Outperformed QQQ; got out at $626 on Feb 13, 2026 |
| SPY | 2007–2009 | Sidestepped 2008 crash; caught reversal lows |
| SPY | 2020 | Sidestepped COVID drawdown |

Carlos repeatedly audits trade-by-trade to confirm executions match what the indicator showed [1:01:30 — 1:02:30].

---

## 9. Integration Requirements (the actual work)

### 9.1 Functional requirements for the executor

| ID | Requirement | Notes |
|---|---|---|
| F1 | Receive buy/sell signal from the strategy on every zero-cross. | Source: TradingView strategy script. |
| F2 | On buy signal: close any open short, then open a long with **100% of available capital**. | Compounding behavior must match Strategy Tester. |
| F3 | On sell signal: close any open long, then open a short with 100% capital. | Short trades are toggled on per backtest demo. |
| F4 | Use **market orders** for entries and exits. | Carlos: "based on signal given, execute" [1:30:48 — 1:31:00]. |
| F5 | All trading begins on **Alpaca paper account**; switch to live account is a config flag. | Carlos's stated v1 acceptance criterion [1:18:00 — 1:18:20]. |
| F6 | Log every executed trade with timestamp, signal trigger, ticker, side, qty, fill price. | Needed to replay against TradingView's trade log for parity. |
| F7 | Alert Carlos (push, SMS, email — TBD) when a trade fires. | Implicit; not explicitly scoped in transcript. **Open question.** |

### 9.2 Path A specifics — TradingView ↔ Alpaca direct integration

- Carlos has TradingView **Pro** ($700/yr, [1:33:00 — 1:33:10]).
- Alpaca claims a TradingView broker integration ("Add Alpaca on TradingView") [1:32:00 — 1:32:20].
- Juan to test whether the integration can:
  - Take signals from a strategy script (not just manual orders), and
  - Submit them to Alpaca automatically.
- Documented Alpaca/TradingView feature surface noted in the call [1:25:48 — 1:29:00]:
  - **Supports:** market orders, limit orders, stop orders, stop-limit orders, full position close.
  - **Does NOT support:** partial position close (irrelevant — strategy is 100% in/out), reverse position in one click (need close + open as two orders), demo account on TradingView itself (Alpaca paper trading covers this).
- Some user reviews of the Alpaca integration are mixed (fee transparency, hidden costs) [1:21:00 — 1:22:00] — **flag for investigation, not blocker.**

### 9.3 Path B specifics — Custom trade bot (fallback)

If Path A can't ingest strategy signals automatically, build:

- A **webhook receiver** that TradingView's alert system can POST to on each strategy signal.
- A **dispatcher** that translates the webhook payload into Alpaca REST API calls (close + open, in sequence).
- A **trade journal** persisting every order and fill (DB or even append-only file is fine for v1).
- A **mode switch** (paper vs live) — single config flag, default paper.
- A **heartbeat / liveness check** so Carlos knows the bot is running.

This path requires a follow-up session with Carlos to formally write down each rule of the scoring system **only if** signals can't be exported from TradingView and the strategy must be reimplemented server-side [1:36:00 — 1:36:30]. If TradingView can emit webhook alerts on its signals, no reimplementation is needed.

### 9.4 Non-functional

- **Reliability:** missing a signal is worse than executing late. Backtest assumes every signal is taken.
- **Latency:** swing trading is 4-hour cadence — minutes of delay are acceptable.
- **Cost:** Carlos willing to pay ~$100/mo for the integration tier if needed [1:23:30 — 1:23:50].
- **Security:** Carlos will share TradingView credentials via WhatsApp; Alpaca account will be created/linked separately. Credentials must not be checked into source.

---

## 10. Milestones / Phased Plan

| Phase | Outcome | Exit criteria |
|---|---|---|
| **0. Setup** | Juan has TradingView Pro access; Alpaca paper account created and linked. | Juan can view Carlos's strategy script in TradingView Pro. |
| **1. Path-A feasibility** | Determine if TradingView + Alpaca integration can fire strategy-driven trades automatically. | Documented yes/no + screenshots of the order surfacing in Alpaca paper account. |
| **2a. Live paper trading (Path A)** | Strategy runs end-to-end into Alpaca paper for ≥1 week. | Trade journal matches TradingView Strategy Tester executions over the same window. |
| **2b. Custom bot (Path B, if A fails)** | Webhook receiver + Alpaca dispatcher live in paper mode. | Same as 2a — log parity with backtest. |
| **3. Validation** | Compare paper-trade returns against Strategy Tester for the same window, same ticker, same timeframe. | <5% drift attributable to slippage/fills; no missed signals. |
| **4. Go-live** | Flip mode to real Alpaca brokerage account, smaller capital allocation initially. | Carlos's go/no-go after Phase 3. |

---

## 11. Open Questions

These come directly from gaps in the transcript that should be answered before or during implementation.

### Strategy questions for Carlos

1. **Exact swing-version chart set.** The transcript states Renko had to be removed for the swing version and replaced with "a mixture of Heikin Ashi and candle charts" [45:48 — 46:48]. Does the developer need this list, or does the PineScript encapsulate it?
2. **Linear-regression alignment scoring.** Carlos awards points when 20/50/100 channels align, but the exact point values weren't stated. Confirm.
3. **Regime score thresholds.** "Below 35 = choppy" was cited, but the full zone boundaries (mild / strong / strongest) weren't given. Need numeric values, or confirmation that they're configurable inputs in the PineScript.
4. **Choppy-regime behavior.** Carlos said "look for reversal trades" in choppy regimes [37:32 — 38:00] — does the current PineScript actually invert signals in regime 0, or is that a future enhancement?
5. **Pyramiding for day trading.** Carlos still validating [35:42 — 36:30]. Is pyramiding in scope for swing v1, or strictly out?
6. **Bitcoin 7,000,000% return.** Carlos flagged this as suspicious. Needs independent validation before any real-money exposure to BTC [56:46 — 57:00].
7. **False-signal filtering.** Carlos identified this as the next research area [1:17:40 — 1:18:20]. Should v1 ship with the current behavior and iterate, or wait?

### Engineering questions

8. **Notifications.** Should Carlos be alerted on every signal, or only on errors / mismatches? Channel (WhatsApp, email, SMS)?
9. **Multiple tickers simultaneously.** Carlos demoed signals on GLW, FXY, BTC, NVDA, SPY individually. Is v1 single-ticker, or does the bot need to run the strategy on a watchlist concurrently? Capital allocation between them?
10. **Reconciliation.** How does the bot handle a discrepancy where the broker fill price differs materially from what the backtest assumed? Log only, halt, or alert?
11. **Restart behavior.** If the bot is down when a signal fires, does it skip the signal on restart, attempt a late entry, or wait for the next signal?
12. **TradingView alert rate limits.** Path B depends on webhook alerts; investigate TradingView Pro's webhook alert allowance.

---

## 12. References (transcript)

All bracketed timestamps in this document are seconds-to-minutes references against `transcript_timestamped.txt`. The companion clean transcript is `transcript.txt`.

- Strategy walkthrough: 0:00 — 38:00
- Regime system: 27:00 — 32:00
- Oscillator and signal markers: 38:00 — 52:00
- Backtest demos (GLW, FXY, BTC, NVDA, SPY): 52:00 — 1:18:00
- Integration discussion (TradingView + Alpaca): 1:18:00 — 1:36:00
- Path B agreement (custom bot fallback): 1:35:30 — 1:36:30

[View timestamped transcript](computer:///Users/drelajara/Documents/Claude/Projects/Swing%20Trading%20App%20(1)/transcript_timestamped.txt)  
[View clean transcript](computer:///Users/drelajara/Documents/Claude/Projects/Swing%20Trading%20App%20(1)/transcript.txt)

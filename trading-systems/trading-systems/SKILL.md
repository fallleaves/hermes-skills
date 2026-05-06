---
name: trading-systems
description: Build, analyze, and debug quantitative trading systems — options backtesting, data collection pipelines, broker APIs (ThetaData, Yahoo Finance), and strategy simulation. Covers project structure patterns, dual-database architecture, API quirks, and common bugs in options trading codebases.
---

# Trading Systems Skill

## What This Skill Covers

- **Options trading backtesting systems** — strategy simulation, strike selection, P&L tracking, portfolio management
- **Data collection pipelines** — bulk backfilling of stock/options data from broker APIs
- **Broker API integration** — ThetaData (primary), Yahoo Finance (secondary stock data)
- **Dual-database architecture** — separating raw data collection (backfill) from strategy execution (backtest)
- **Common bugs and pitfalls** in options trading codebases

## Project Structure Pattern

Typical options trading system layout:

```
src/
  data/           # API clients (theta_client, stock_client)
  strategy/       # Core logic (volatility model, risk manager, strike selection)
  backtest/       # Simulation engine, portfolio, optimizer
  utils/          # Metrics
config/           # Ticker lists, parameters
backfill_v2/      # Data collection pipeline (separate from backtest engine)
```

## Dual-Database Architecture

Many projects conflate two distinct systems:

- **backfill_v2.db (BackfillStorage)** — raw data collection, job tracking, progress tracking. Tables: `stocks`, `options`, `jobs`, `job_progress`
- **option_data.db (OptionDatabase)** — strategy-optimized cache. Tables: `option_data`, `stocks`, `expirations`, `strikes`, `earnings_dates`, `backfill_jobs`

The backfill system populates its own DB; the backtest engine can use either as a cache for `ThetaClient`. They have different schemas.

## Key References

- `references/theta-data-quirks.md` — ThetaData API errors, rate limits, entitlement tiers, and the multi-day range fetch pattern

## Common Bugs

### Unsorted Expirations in Backtest Engine

In `src/backtest/engine.py`, the backtest selects the nearest expiration with:

```python
future_exps = [e for e in expirations if e >= target_date_str]
if future_exps:
    best_exp = future_exps[0]  # BUG: list is not sorted!
```

ThetaData returns expirations in an arbitrary order. Always sort before taking the first element:

```python
future_exps = sorted([e for e in expirations if e >= target_date_str])
if future_exps:
    best_exp = future_exps[0]
```

### Greeks Not Fetched

The `options` table schema includes `iv`, `delta`, `gamma`, `theta`, `vega`, `rho` columns, and `ThetaClient` has `get_bulk_greeks()` — but it's never called. All Greeks are stored as `NULL`. If Greeks are needed, add `bulk_greeks` calls in the fetch loop.

### 471 Entitlement Error Crashes Entire Job

In `theta.py`, any non-471 API exception is re-raised, killing the entire job:

```python
except Exception as api_err:
    if "471" in str(api_err):
        logger.error(f"Entitlement Error ... Stopping this expiration.")
        break   # ← breaks inner strike loop only
    else:
        raise   # ← CRASH: network timeout, 500, etc. kills the whole job
```

Should catch all API errors, log warning, and continue — only 471 is entitlements-scope (old data range). Non-471 errors should retry or skip without crashing.

### job_progress Is Coarse-Grained

`_run_option_backfill` records progress per ticker at the start date only:

```python
self.job_manager.record_progress(job["id"], ticker, job["start_date"], "completed")
```

The `job_progress` table PK is `(job_id, ticker, date)` — so for a multi-day backfill, you get at most 1 progress row per ticker. No per-day tracking means no intelligent resume. If a job fails at ticker 15 of 30, you can't see which days succeeded.

### Zero Logging State — Backfill Runs Completely Silent

After removing all logging calls, the entire backfill system runs with zero log output. This was done intentionally so the team can rebuild logging from scratch based on actual needs.

**Current state:** No visibility into:
- When API calls are made
- When data is written to DB
- Errors or entitlement warnings
- Job start/end/completion

**What needs to be decided (per job run):**
1. **API error visibility** — non-471 errors are silently skipped (contract excluded). 471 entitlement errors break the expiration loop silently. Should these be visible?
2. **DB write confirmation** — `upsert_option_data()` runs per contract with no confirmation. DB is source of truth, but a count at job end may be useful.
3. **Job-level summary** — CLI prints `SUCCESS/FAILURE` only. Useful to know: total rows fetched, contracts attempted, errors encountered, expirations that hit 471.
4. **Per-day progress** — `job_progress` table exists but only records at `start_date` granularity per ticker. No per-day visibility during a multi-day run.

**Exception handling (current state):**
```python
# theta.py — non-471 exceptions now silently skip the contract
try:
    df = self.client.get_hist_eod(...)
except Exception as api_err:
    if "471" in str(api_err):
        break  # entitlement — stop this expiration, continue to next
    continue  # skip this contract, continue to next
```
Non-471 no longer crashes the job. 471 breaks the expiration loop (correct — old data outside tier).

### Rate Limiter Free Tier Is 0.5 calls/sec

In `backfill_v2/rate_limiter.py`:

```python
"free": 0.5,   # 1 call every 2 seconds
```

At 0.5 calls/sec, backfilling 1,000 contracts takes ~33 minutes minimum. This is extremely conservative. The ThetaData free tier allows burst patterns — a 1.0-2.0 calls/sec average is safer and much faster.

## Trigger Conditions

Load this skill when the user asks to:
- Analyze, build, or modify an options trading system
- Work with ThetaData API
- Backfill options data
- Run a backtest on a trading strategy
- Debug issues in a quantitative finance codebase

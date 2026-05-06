# ThetaData API — Common Quirks & Pitfalls

## Entitlement Tiers (Error 471)

ThetaData Free Tier only supports **last 30 days** of historical data. Requesting older data returns:

```
ThetaData Error [471]: NOT_ENTITLED
This usually means your subscription does not cover this historical data range.
The Free Tier only supports the last 30 days.
```

| Tier | Rate Limit | Historical Range |
|---|---|---|
| Free | 0.5 calls/sec | Last 30 days |
| Basic | 4.0 calls/sec | ~2 years |
| Pro | 10.0 calls/sec | Full range |

Rate limiter configuration in `backfill_v2/rate_limiter.py`:

```python
RateLimiter.for_tier("free")   # 0.5 calls/sec (very conservative)
RateLimiter.for_tier("basic")  # 4.0 calls/sec
RateLimiter.for_tier("pro")    # 10.0 calls/sec
```

### Two-Level Cache Architecture

The dedup works in two layers that are often confused:

**Layer 1 — `processed_contracts` (in-memory, per run):**
```python
# theta.py:105-109
contract_key = (ticker, exp, int(s), right)
if contract_key in processed_contracts:
    continue  # skip entirely — no API call, no DB check
processed_contracts.add(contract_key)
```
This is global per run: once `(TSLA, 20250402, 300000, C)` is added, it's never touched again for any future trading day. **One API call per unique contract, total.**

**Layer 2 — `get_existing_dates_for_contract` (DB query, per contract):**
```python
# theta.py:111-115, storage.py:169-177
existing_dates = storage.get_existing_dates_for_contract(root, exp, strike, right, start_date, end_date)
```
Returns all dates already in DB for this specific contract. The multi-day API response is then filtered per-row:
```python
# theta.py:153-156
if not force_update and d_display in existing_dates:
    continue  # this specific date already cached
```

**Why this matters:** `get_hist_eod` always uses the FULL backfill range as start/end (`20250101` → `20260501`) — not the current trading day. So even on day 300 of the run, the API call returns all ~336 rows again, and Python filters out the already-cached ones. This is a deliberate time-for-space tradeoff: redundant data transfer to keep API calls minimal.

### Concrete Cache Check Walkthrough

For `(TSLA, 20250402, 300000, C)` on trade date `2025-01-02`:
1. `processed_contracts` check → not present → add and proceed
2. DB query `get_existing_dates_for_contract` → returns `{}` (no data yet)
3. API call `get_hist_eod(TSLA, 20250402, 300000, C, 20250101, 20260501)` → returns all ~336 days
4. Per-row filter → all rows inserted
5. Contract marked done in `processed_contracts`

On trade date `2025-03-15`: contract key already in `processed_contracts` → skipped entirely, zero API call, zero DB query.

**Only one API call per (root, exp, strike, right) combo, total, regardless of how many trading days fall within that contract's window.**

## Error 472 — No Data

Error 472 from ThetaData means "no data for this request" — not an error condition, just empty result. The client returns `None` for this.

## Greeks Are Not Fetched

The `get_bulk_greeks()` method exists in `ThetaClient` but is never called in the fetch pipeline. Greeks columns (iv, delta, gamma, theta, vega, rho) are always `NULL` in the database.

## Stock EOD Endpoint

`get_stock_eod()` uses the same `/hist/stock/eod` endpoint and also respects the 30-day free tier limit. If backfilling old stock data, this will also fail with 471.

## Entitlements Check

```python
if response.status_code == 471:
    raise Exception("ThetaData Error [471]: NOT_ENTITLED... Free Tier only supports last 30 days.")
```

Always catch this specifically — it means the historical range requested is outside your tier.

## Date Format Gotcha

ThetaData uses `YYYYMMDD` (integer/string without dashes) for date parameters in EOD endpoints, but `YYYY-MM-DD` (ISO) elsewhere. When connecting to `get_hist_eod`, dates must be `YYYYMMDD` format:

```python
date_str = dt.strftime("%Y%m%d")  # "20250102" not "2025-01-02"
```

### Non-471 API Errors: Silent Skip

In `theta.py._fetch_contract_by_contract()`:
```python
try:
    df = self.client.get_hist_eod(ticker, exp, s, right, start_date_str, end_date_str)
except Exception as exc:
    stats["contracts_errored"] += 1
    if "471" in str(exc):
        stats["entitlement_skips"] += 1
        logger.warning(f"[{ticker}] {exp} {s} {right} — entitlement error (471), skipping remaining strikes for this expiry")
        break  # stop this expiration — all remaining strikes will 471 too
    else:
        logger.warning(f"[{ticker}] {exp} {s} {right} — API error: {exc}")
    continue  # skip this contract, move to next
```

| Error | Behavior |
|-------|----------|
| 471 NOT_ENTITLED | WARNING log, break expiration loop, continue to next expiration |
| Other API errors (500, network timeout, etc.) | WARNING log, skip contract, continue to next |
| Empty result (no trading data) | Recorded as NULL sentinel row for that trade date only |

### Backfill Time Scales Superlinearly with `exp_days`

`exp_days` doesn't just change the window size — it multiplies API calls per trading day by changing how many expirations are "active."

For TSLA with 30% strike width (~90 strikes × 2 rights):

| exp_days | Approx active expirations per day | Contracts/day | Free tier time per trading day |
|----------|----------------------------------|---------------|-------------------------------|
| 30 | ~5 | ~900 | ~30 min |
| 90 | ~6–7 | ~1,080–1,260 | ~37–42 min |

A 16-month backfill at `exp_days=90` takes ~67 hours of pure rate-limiting. The `exp_days=30` Q1 run completed in ~90 minutes.

**Overlap effect:** `exp_days=90` on a date within Q1 fetches March/April expirations that were NOT in the `exp_days=30` run — so the cached Q1 data doesn't fully cover the new run even for overlapping dates. Only truly identical contracts (same exp + same strike + same right) are skipped.

**Rule of thumb:** Estimate `hours ≈ (trading_days × active_expirations × strikes × 2 × 2) / 3600` at 0.5 calls/sec. Use `exp_days=30` for test runs, scale up only when needed.

The `RateLimiter.for_tier("free")` in `backfill_v2/rate_limiter.py` is set to `0.5` calls/sec (1 call every 2 seconds). At this rate, 1,000 contracts takes ~33 minutes minimum.

The backtest engine uses `RateLimiter.for_tier("basic")` (4.0 calls/sec) — the difference is not documented anywhere.

**Key insight:** Free tier does NOT mean you can only make 0.5 calls/sec sustained. ThetaData free tier supports burst patterns. A well-tuned free tier fetcher should average 1.0–2.0 calls/sec for bulk backfills.

## Job Progress Is Not Per-Day

`job_manager.record_progress(job_id, ticker, start_date, status)` is called once per ticker at the start date. The `job_progress` table PK is `(job_id, ticker, date)`, but `date` is always `start_date` — not the actual day being processed.

This means:
- Multi-day backfills show no granular progress
- Failed jobs can't be intelligently resumed
- No visibility into "how far did we get"

**Consequence:** If a job fails mid-way, you can't see which tickers/days completed. You either re-run from scratch or manually inspect the database.

# Data Simulator

`src/simulator/` generates NovaMart's source files — there's no real
upstream system. It exists so the pipeline has something realistically
messy, cross-channel, and large (1M+ records over a 2-year history) to
ingest, profile, validate, and quarantine. `scripts/simulate_new_data.py`
and `scripts/run_pipeline.py --mode backfill` are the entry points; both
call into `src.simulator.simulator_main.generate_range`.

## Shared universe (`universe.py`)

One `Universe` instance (seeded, default `seed=42`) is built once per
simulation run and passed to every source generator, so cross-channel data
is internally consistent rather than independently random:

- **200 products** (`NUM_PRODUCTS`), each with a *single* cost/price/weight
  but **three different SKUs** — `shopify_sku`, `amazon_asin`,
  `pos_internal_sku` — so the pipeline's `SKUMapper` has something real to
  resolve. ~5% are `is_active=False` (discontinued).
- **5,000 customers** (`NUM_CUSTOMERS`), of which ~28%
  (`CROSS_CHANNEL_OVERLAP_PCT`) appear in 2-3 channels. Cross-channel
  customers get a slightly different identity per channel via
  `_name_variant` (e.g. "Robert" → "R." or "Rob", a random middle
  initial ~10% of the time) — this is what makes fuzzy customer
  resolution (`src/dedup/customer_resolver.py`) meaningful rather than a
  trivial exact-match join.
- Channel-specific field availability is randomized once per customer:
  POS emails are present ~60% of the time, Amazon phone numbers ~30%,
  POS loyalty IDs ~60%. Nothing here is deliberately corrupted — that's
  layered on separately (see below).
- Amazon referral-fee % (8-15%, by category) and FBA fee tiers, Shopify/POS
  card-processing fee constants, and per-channel return rates
  (amazon 6% / shopify 4% / pos 2%) all live here, feeding
  `revenue_calculator.py`'s downstream economics.

## Per-source generators, on their natural cadence

`simulator_main.generate_range(start_date, end_date, output_dir, ...)`
walks hour-by-hour across the requested date range and fires each
generator at its own cadence (`BASE_RANGES` in `simulator_main.py`):

| Source | Cadence | Volume (pre-seasonal) | Generator |
|---|---|---|---|
| POS | hourly | 20-35 transactions | `pos_simulator.generate_pos_batch` |
| Shopify | every 6 hours | 100-200 orders | `shopify_simulator.generate_shopify_batch` |
| Amazon | daily (midnight) | 400-600 orders | `amazon_simulator.generate_amazon_batch` |
| Shipping (fedex/ups/usps) | daily (midnight) | 250 total, split 40/35/25 | `shipping_simulator.generate_shipping_batch` |
| Customers | weekly (Sunday) | 200-400 new + 50 updated | `customer_simulator.generate_customer_sync` |
| Products | monthly (1st) | full 200-product catalog snapshot | `product_simulator.generate_product_catalog` |

These per-batch ranges (not the smaller daily figures in
`seasonal_patterns.py`) are what the 1M+ record historical target is built
from — a 2-year backfill produces roughly 17.5k hours of POS batches,
~2.9k Shopify batches, ~730 Amazon/shipping days, etc.

## Seasonality (`seasonal_patterns.py`)

Every count above is scaled by `volume_multiplier(date, start_date, channel)`,
which multiplies three independent factors:

- **Day-of-week**: Saturday 1.3x, Sunday 1.1x, weekdays 1.0x.
- **Month-over-month growth**: 3% compounding per elapsed month
  (`MONTHLY_GROWTH_RATE`) — later months in the 2-year history have
  meaningfully higher baseline volume than month 1.
- **Named seasonal events**: Black Friday-Cyber Monday weekend (computed
  from Thanksgiving's actual date) is a 4x spike; Amazon-only Prime Day
  (2nd Tue-Wed of July) is 2x; all of Nov/Dec is 2.5x; January is a 0.8x
  clearance dip; Aug/Sep back-to-school is 1.5x; Jun/Jul summer lull is
  0.85x. `product_category_multiplier` additionally spikes winter
  products (heaters, blankets) 2x in Nov-Feb, summer products (fans) 2x
  in May-Aug, and December gift categories (Audio/Gaming/Wearables/
  Accessories) 1.4x. Returns spike 1.8x in January (`return_rate_multiplier`)
  independent of order volume.

## Progressive quality degradation (`timeline.py` + `quality_degrader.py`)

Rather than uniformly-random messiness, data quality degrades on a
scripted 24-month timeline (`month_index` = whole months since
`HISTORICAL_START = 2024-01-01`), so the pipeline's profiling/drift/quality
trend charts show a believable story arc instead of flat noise:

| Month(s) | Stage | What changes |
|---|---|---|
| 0-5 | `baseline` | Normal rates throughout |
| 6 | `shopify_schema_drift` | Shopify export adds a `discount_type` column |
| 7-8 | `gradual_quality_decline` | Optional-field null rates (`phone`, `notes`, `shipping_address_line_2`) ramp linearly from baseline toward degraded levels |
| 9 | `amazon_breaking_schema` | Amazon renames `referral_fee` → `referral_fee_amount` |
| 10-11 | `duplicate_file_uploads` | File duplicate-upload rate jumps 0% → 2% |
| 12(-13) | `pos_system_upgrade` | POS switches v3 → v4 JSON structure; months 12-13 can emit either format (transition window) |
| 13-18 | `increasing_chaos` | Corrupted-file rate 1% → 2%, empty-file rate 0.5% → 1%, and a 1.5x Q4 return-rate multiplier if in Nov/Dec |
| 19-24 | `stabilization` | Elevated rates hold, no further escalation |

`quality_degrader.py` only computes *rates* for a given date
(`optional_field_null_rate`, `corrupted_file_rate`, `empty_file_rate`,
`duplicate_file_rate`, `q4_return_rate_multiplier`); `chaos_injector.py`
is what actually mutates rows/files, keeping "how much" and "how" cleanly
separated. `stage_summary(date)` returns a full snapshot of all active
parameters for a given date, useful for debugging which stage produced a
given file.

## Chaos injection categories (`chaos_injector.py`)

Row-level functions take `list[dict]` and return a new list (pure,
non-mutating); file-level functions operate on already-written files.
Grouped by the project's five issue categories:

- **Data quality**: duplicate rows (`inject_duplicate_rows`), trailing
  whitespace, mixed-case strings, nulled required fields, negative
  amounts on fields that should be positive, future-dated orders, and
  obviously-fake test data (`John Doe` / `test@test.com`) leaking into
  a small % of rows.
- **Format issues**: currency-prefixed amount strings (`"$19.99"` instead
  of `19.99`), and dates reformatted from ISO to `MM/DD/YYYY` for a
  subset of rows within the same file (inconsistent formatting *within*
  one export, not just across exports).
- **Semantic conflicts**: sign-convention flips (`flip_sign_convention`)
  — e.g. a refund recorded as positive when it should be negative.
- **Encoding problems**: HTML-entity-escaped strings, invisible/zero-width
  characters inserted mid-string, BOM prefixing (`add_bom`), a full
  UTF-8 → Windows-1252 re-encode that mangles/drops non-mappable
  characters (`reencode_windows1252`), and alternate Unicode
  normalization forms (NFC vs NFD) for names.
- **Schema drift** (structural): add an unexpected column, drop an
  expected one, or shuffle column order — used to implement the
  scripted `timeline.py` events above.
- **File-level chaos**: `duplicate_file` (copies under a new name,
  simulating a re-upload), `truncate_file` (simulates a corrupted/partial
  write), `empty_file`. Every batch file written by `simulator_main.py`
  rolls against `_apply_file_chaos`, which picks at most one of
  empty/corrupt/duplicate per file based on that date's rates (checked in
  that priority order, so they're mutually exclusive per file).

A `level` multiplier (default 1.0, every `_rate()` call is
`min(base_rate * level, 1.0)`) scales every injection rate uniformly —
this is what `--chaos-level` on `run_pipeline.py`/`simulate_new_data.py`
controls for ad-hoc "extreme testing" without touching the scripted
timeline.

Note: row-level chaos hooks are wired into each `_generate_*` function in
`simulator_main.py` selectively (a representative subset per source), not
exhaustively for every function `chaos_injector.py` defines — extending
coverage means calling more of its functions from the relevant
`generate_*` function.

## Running it

```bash
python scripts/simulate_new_data.py --date yesterday   # incremental, one day
python scripts/run_pipeline.py --mode backfill          # full 2-year history
```

See `docs/runbook.md` for the full set of run modes and their flags
(`--chaos-level`, `--seed`, date ranges).

# Reproducible public-data validation

MetricPilot's real-public-data track uses **UCI Online Retail**, an observed
transaction dataset from a UK-based non-store retailer. This historical data is
not evidence of present-day retail conditions, causal explanations, or model
quality. AI-assisted implementation and deterministic validation remain distinct
from a live model benchmark.

## Source, attribution, and license

- Source: [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail)
- Download: [official workbook ZIP](https://archive.ics.uci.edu/static/public/352/online+retail.zip)
- Citation: Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning
  Repository. [DOI: 10.24432/C5BW33](https://doi.org/10.24432/C5BW33)
- License: [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)
- Adaptation: source transaction lines are filtered and aggregated into
  month-country counts and positive gross-sales values. The bundled artifact
  contains no customer identifiers, product descriptions, or invoice identifiers.
- Original ZIP SHA-256:
  `f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b`
- Workbook SHA-256:
  `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`

## Rebuild offline

Download and extract the official ZIP separately. Keep its raw workbook in
ignored local storage; it is not a runtime dependency or bundled customer file.

```sh
python -m pip install -r requirements-data.txt
python -m backend.import_retail 'artifacts/local/uci/Online Retail.xlsx'
```

The optional importer dependency is pinned in `requirements-data.txt`. The
importer does not make network calls. It requires the pinned workbook checksum,
one `Online Retail` sheet, the original eight headers in their original order,
and exactly 541,909 source records. It parses the entire sheet, not a sample.
The default output is `data/retail_monthly.json`; `--output PATH` can change it.
The application uses the bundled JSON and does not need openpyxl or raw records.

## Metric contract and audit

A line contributes only when:

1. Its invoice does not begin with `C` (case-insensitive cancellation marker)
2. Quantity is a finite positive integer and unit price is finite and positive
3. Invoice number, a valid workbook date, and a nonempty country are present

Gross sales equal the exact decimal sum of quantity times unit price, in GBP.
Prices are converted from their workbook scalar decimal representation using
`Decimal(str(value))`; money is not prematurely rounded to pennies. The result
is **positive gross sales**, not net revenue, profit, or recognized revenue.
Cancellations, returns/nonpositive quantities, and nonpositive-price lines are
excluded rather than netted against sales. Country is the source's country
label, not proof of nationality or geographic causation.

Exact duplicate source rows are **retained**. The source cannot establish whether
a repeated line is a duplicated record or a genuine repeated sale. The audit
counts each repetition after the first against all eight original source
columns, before filtering. Removing them silently would introduce a different
metric. Missing customer IDs and descriptions are counted but do not disqualify
otherwise valid non-customer-level sales analysis.

All audit counts refer to the full source. Cancellation, nonpositive quantity,
nonpositive price, and invalid-record reason counts can overlap. They must not be
summed to infer excluded lines; `excluded_lines` counts each rejected row once,
and `included_lines + excluded_lines = total_rows`. Missingness and duplicates
are descriptive audit counts, not additional exclusion rules. `invalid_lines`
means an invalid/missing required date, country, invoice number, or nonfinite or
malformed numeric value (including a nonintegral quantity). `country_count`
counts distinct countries among included lines. Source date minimum/maximum cover
all valid source dates, including excluded records, with no invented timezone.

Monthly orders are distinct invoice numbers within each month and country.
Lines are accepted source lines including duplicates. Units are summed accepted
quantities. Monthly records are sorted by month and country.

## Comparison and independent references

The fixed comparison is **October 2011 versus November 2011**, two complete months
inside the source's 1 December 2010 to 9 December 2011 coverage. December 2011 is
partial and must not be selected as a full-month comparison. The source spans
13 calendar-month labels, not 13 full months. Other seasonal, calendar-length,
and coverage differences still limit interpretations.

`reference.before` and `reference.after` contain hand-written Python/Decimal
source-row totals for these fixed months, including distinct invoice counts,
line counts, units, and gross sales. `reference.country_totals` contains the same
per-country totals and signed after-minus-before deltas, including zero for an
absent side. These accumulators read accepted rows directly and never query
DuckDB or sum the bundled monthly results. They provide a separate numerical
reference for runtime SQL verification. Because they share the documented row
filter, fixtures independently test that filter with manually calculated money,
missing values, cancellations, overlaps, and retained duplicates. This is not a
wholly independent extraction of the source workbook.

## Artifact schema and deterministic hash

Top-level fields:

- `source`: name, source URL, download URL, DOI, citation, license, license URL,
  original ZIP `source_sha256`, `workbook_sha256`, and `source_rows`
- `audit`: `total_rows`, `cancellation_lines`, `nonpositive_quantity_lines`,
  `nonpositive_price_lines`, `missing_customer_id_lines`,
  `missing_description_lines`, `exact_duplicate_rows`, `invalid_lines`,
  `included_lines`, `excluded_lines`, `country_count`, `source_date_min`, and
  `source_date_max`
- `monthly`: sorted rows with `month` (`YYYY-MM`), `country`, integer `lines`,
  `orders`, `units`, and decimal-string `gross_sales_gbp`
- `reference`: `before_month`, `after_month`, `before`, `after`, `delta_gbp`,
  and `country_totals`. Each side has decimal-string `gross_sales_gbp` and
  integer `orders`, `lines`, and `units`. Country rows add `country` and
  decimal-string `delta_gbp`
- `hash`: SHA-256 of all other fields, using UTF-8 encoded
  `json.dumps(payload_without_hash, sort_keys=True, separators=(',', ':'))`
  with Python's default `ensure_ascii=True`

The output contains no generation timestamp, so the same pinned source and
importer yield the same payload hash. The hash validates artifact consistency;
it is not a signature or proof that every transformation is correct.

## Verified pinned-source results

The checked-in import contains 302 month-country rows (38,243 bytes), covering
38 included countries. Its canonical payload hash is
`cbf7b1111cb3798d29646147a4ecfd7c8b228c5c5e03c8f396a62e67445e17bd`.

- Source lines: 541,909; included: 530,104; excluded: 11,805
- Cancellation lines: 9,288; nonpositive-quantity lines: 10,624;
  nonpositive-price lines: 2,517; invalid lines: 0
- Missing customer IDs: 135,080; missing descriptions: 1,454
- Exact duplicate repetitions: 5,268, all retained
- Source timestamp bounds: `2010-12-01T08:26:00` through `2011-12-09T12:50:00`
- All included source gross sales: **GBP 10,666,684.544**. Preserve fractional
  pennies in numerical storage; round only for presentation
- October 2011: GBP 1,154,979.30; 2,040 orders; 59,304 lines; 623,401 units
- November 2011: GBP 1,509,496.33; 2,769 orders; 83,369 lines; 754,507 units
- November minus October gross sales: **GBP 354,517.03**
- The comparison-month country union contains 29 countries

These values describe the specified gross-sales filter and duplicate-retention
policy. A different filter, particularly dropping anonymous transactions or
netting returns, gives different totals and must carry a different metric label.

## Execute the case study

Use the normal local startup commands, then open `/retail`. The separate
`POST /api/retail/analyze` endpoint accepts a question and optional `mode`
(`deterministic` by default, or explicitly enabled `live`). Both use the fixed
LangGraph sequence: local MiniLM contract retrieval, sales-comparison SQL and
country-contribution SQL. Deterministic mode uses checked templates without API
calls; live mode adds cited model interpretation and server-rendered verified
facts under the persistent budget. Neither mode accepts configurable SQL.

A successful actual-model retail development example is recorded separately.
The final paired retail supplement was execution-blocked before any response
was recorded; it has no published model-quality score. Do not substitute the
development example for that missing evaluation.

```sh
python -m evals.retail
```

The evaluator verifies eight monthly measures, all 29 country deltas and two
reconciled total deltas against the source-row references. Its result is in
`evals/results/retail.json`. This is a fixed-data engineering regression,
not a held-out accuracy score. The new page is locally built; public deployment
and browser interactions remain unverified.

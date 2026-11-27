# USDT Amount Cleaning Plan — Step 0 to Step 8

## 1. Objective and principles

- Clean only the USDT `amount` column.
- Never delete raw rows.
- Add `amount_flag` and filter on it later.
- Every removal must be reversible and countable.
- Keep the raw amount representation for precision checks.

Notebook: `Lab/EDA.ipynb`  
Source data: `Lab/combined_snapshot_2026-11-10_full/transactions.csv.gz`  
USDT rows: **2,717,550**

The snapshot contains all tables exported inside one PostgreSQL `REPEATABLE READ READ ONLY` transaction.

## 2. Threshold and source

TRON USDT total supply:

```text
94,248,192,941.363764 USDT
```

Source: Tronscan USDT token page  
`https://tronscan.org/token20/TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t/transfers`  
Retrieved: 2026-11-10.

Cross-check: DefiLlama reported about `$92.30B` on TRON around 2026-11-08.

Decision: the removal threshold is the TRON USDT total supply.  
`1e9` is a large-review boundary, not the removal threshold.

Supporting evidence: only two values occur between `1e10` and `1e16` (`11,579,208,925` each). Both are below the supply threshold and are classified as `large_review`.

## 3. Step 0 — Protect raw data and create flags

Status: implemented in `Lab/EDA.ipynb`.

Flag priority:

```text
sentinel -> above_supply -> zero -> dust -> large_review -> ok
```

| Flag | Rule | Rows | Share |
|---|---|---:|---:|
| `ok` | normal range | 2,666,239 | 98.112% |
| `large_review` | `1e6 < amount <= supply` | 12,507 | 0.460% |
| `dust` | `0 < amount < 0.01` | 8,055 | 0.296% |
| `zero` | `amount == 0` | 27,932 | 1.028% |
| `above_supply` | above supply, excluding sentinel | 137 | 0.005% |
| `sentinel` | exact uint256 placeholder | 2,680 | 0.099% |

Implemented outputs:

- `amount_flag` column.
- Main flag bar chart with action-based analogous colors.
- Separate removal chart below the main chart.
- Interpretation markdown.
- Sentinel explanation markdown.

Minimal removal total:

```text
sentinel + above_supply = 2,817 rows (0.104%)
```

No raw rows are deleted.

## 4. Step 1 — Scope

- Keep only `token_symbol == "USDT"`.
- Record `2,717,550` rows.
- Record the column list and raw dtype.

## 5. Step 2 — Structural checks

Check and record:

- null or NaN amounts,
- non-numeric parsing failures,
- negative amounts,
- zero amounts,
- raw amount dtype,
- numeric amount dtype.

Precision note:

- Preserve `amount_raw` as a string.
- Use numeric `amount` for thresholds.
- Use the raw string for exact sentinel detection because `float64` cannot preserve every digit near `1e71`.
- After structural checks pass, the working `amount` column is cast to standard `float64`.

Expected result: no nulls, no non-numeric values, and no negative amounts.

## 6. Step 3 — Impossible values

Remove by flag only:

```text
sentinel       2,680
above_supply     137
total          2,817
```

Sentinel value:

```text
2^256 / 1,000,000 = 1.157920892373162e71
```

The sentinel appears **2,680 times** and is larger than the entire USDT supply. It is an overflow or placeholder value, not a real transfer.

Case counts elsewhere in the large-value range:

```text
1e10 < amount < supply       2
1e9 < amount < 1e10          4
exact 1e10                   1
exact 1e9                   14
1e6 < amount < 1e9      12,486
exact 1e6                 3,300
```

Action: flag `sentinel` and `above_supply`; do not physically delete rows.

## 7. Step 4 — Zeros

Facts:

```text
zero rows             27,932
distinct senders      11,711
distinct receivers     9,574
```

Top zero senders:

```text
TAFYx2Y9oLCFr36kQfZt8tU2qcT5yUBDbK    180
TWJ4hoqJSYSZQEKjoV9CopkikTaXCKPotH    115
TKwNfJYb2iyouByKpNdxQ6tryXK8KhTPT9    108
```

Top zero receivers:

```text
TPwezUWpEGmFBENNWJHwXHRG1D2NCEEt5s   1,136
TTJxU3P8rHycAyFY4kVtGNfmnMH4ezcuM9     746
TTRr81XJt6zESpJw2zHgJNAsxcsyT5MVYv     403
```

Largest zero months:

```text
2022-12   2,186
2026-10   2,093
2023-01   1,424
```

Hop-edge dependency, computed from the same full snapshot:

```text
Zero transaction hashes : 27,932
Hop edges on zero tx    : 4,241
Share of hop rows       : 0.177%
```

Action: keep zero rows in the raw table; exclude them from flow-feature calculations.

## 8. Step 5 — Large but possible

Facts:

```text
1e9 < amount < 1e10        4
1e6 < amount < 1e9    12,486
exact 1e6              3,300
```

`large_review` rule:

```text
1e6 < amount <= TRON_USDT_SUPPLY
```

Count: `12,507`.

Inspect samples for:

- exchange, contract, or mint address,
- blacklist membership,
- other amounts sent or received by the same wallets.

Action: keep and flag unless evidence shows otherwise.

Boundary note: exact `1e6` rows are currently excluded from `large_review`. Including them would increase the count to `15,807`.

## 9. Step 6 — Dust

Facts:

```text
dust rows              8,055
distinct senders       3,714
distinct receivers     1,970
```

Action: flag as `dust`; keep raw rows; test whether excluding dust changes flow features.

## 10. Step 7 — Sensitivity check

Compare:

```text
minimal cleaning: remove only sentinel + above_supply = 2,817
strict cleaning : remove every non-ok flag = 51,311
```

Strict total uses `large_review = 12,507`.

Compute:

- total USDT volume per wallet,
- median total volume,
- aggregate volume,
- Spearman rank correlation (rho) on a fixed random sample of wallets.

Use `pandas.DataFrame.corr(method="spearman")`; no `scipy` is required.

Report whether the cleaning choice materially changes wallet rankings or total volume.

## 11. Step 8 — Cleaning log

| Rule | Reason | Rows | Action |
|---|---|---:|---|
| sentinel | max uint256 placeholder | 2,680 | removed |
| above_supply | physically impossible | 137 | removed |
| zero | no value moved | 27,932 | flagged |
| dust | below 0.01 USDT | 8,055 | flagged |
| large_review | possible large transfer | 12,507 | flagged |
| ok | normal range | 2,666,239 | kept |

Totals:

```text
minimal removed: 2,817
strict removed : 51,311
```

## 12. Open decisions

- Confirm the supply threshold replaces the old `1e9` removal rule.
- Confirm `large_review` excludes exact `1e6`.
- Decide whether the strict-cleaning sensitivity test should remove `large_review` rows or only flag them.

## 13. Verification checklist

- All flag counts sum to `2,717,550`.
- Raw rows are not deleted.
- Charts render inline.
- Cleaning-log counts match notebook output.
- No PNG files are created.
- The removal chart total equals `2,817`.

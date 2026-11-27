# Color Theory & Visual Encoding for EDA Profile Plots
<!-- Last updated: 2026-11-27 | Edit count: 1 -->

Authoritative color-harmony and visual-encoding specification for
`src/scripts/eda/profile/`. Code constants live in
[`style.py`](../../../../src/scripts/eda/profile/style.py); this document owns
the perceptual rationale so code comments stay one line.

## Scenario: why naive palettes fail here

Consider overlaid full-frame histograms across the four canonical cohorts:
`illicit` (0.17% of the universe, 17,046 wallets), `suspicious` (40.2%), `licit`
(52.6%), and `unlabeled` (7.0%).

1. **Traffic-light failure (red vs. green):** Under deuteranopia/protanopia (~8%
   of male readers), saturated red (`#FF0000`) and green (`#00AA00`) collapse
   into nearly identical muddy olive-brown. The primary inferential contrast
   (`illicit vs licit`) becomes unreadable.
2. **Default categorical cycle failure (Matplotlib `tab10`):** Assigning four
   equally saturated arbitrary hues gives `unlabeled` the same chromatic weight
   as `illicit` and `licit`, visually implying `unlabeled` is a confirmed class
   rather than a provisional residual.
3. **Rainbow/jet heatmap failure:** Non-monotonic luminance creates false visual
   boundaries on eligibility and missingness matrices, making a 60%→65% step
   look sharper than a 20%→40% step.

## 1. Core Harmony: Split-Complementary + Anchored Neutral

All cohort plots use a **Split-Complementary Triad plus an Achromatic Neutral**
calibrated in perceptual lightness (`L*`) and hue angle (`H°`, OkLCH):

| Role / Cohort | Hex | Approx. `L*` | Hue zone (`H°`) | Harmony & semantic function |
| --- | --- | --- | --- | --- |
| `illicit` | `#C83E2B` | ~46 | ~28° (warm vermilion) | High-salience threat anchor; ensures the 0.17% cohort leads visual hierarchy |
| `suspicious` | `#D9822B` | ~63 | ~68° (warm amber-ochre) | Warm-analogous partner (+40° from `illicit`, `ΔL* ≈ +17`); signals graph proximity without colliding under CVD or grayscale |
| `licit` | `#1F6F8B` | ~44 | ~228° (cool deep cerulean) | Direct cool complement (~180° opposite warm pole); maximizes figure–ground separation for the independent `illicit vs licit` contrast |
| `unlabeled` | `#7A8694` | ~55 | Achromatic cool slate (`C ≈ 0.02`) | Deliberately desaturated background arm; suppresses chromatic pull so readers never equate `unlabeled` with `licit` |

**Why this geometry works:**
- **Warm-vs-cool polarity** maps directly onto domain semantics: risk-side arms
  (`illicit`, `suspicious`) occupy the warm half-plane, the independent control
  arm (`licit`) occupies the cool pole, and the provisional residual
  (`unlabeled`) sits at zero chroma.
- **Luminance separation inside the warm pair** (`L* 46` vs `L* 63`) ensures
  `illicit` and `suspicious` remain separable in monochrome print and under
  red-green color-vision deficiency.
- **No pure black or neon saturation:** Primary ink is dark charcoal `#1F2933`
  (>14:1 WCAG AAA contrast on `#FFFFFF`), metadata ink is `#52606D` (>6.4:1
  WCAG AA), and structural gridlines drop to `#E5E9EF` so ink belongs to data,
  not chart chrome.

## 2. Orthogonal Secondary Palettes

Secondary encodings never reuse `suspicious` amber or `unlabeled` slate for
unrelated axes, preventing cross-plot semantic drift:

- **Schema polarity (`illicit` vs `licit` vs `both`):** Reuses `#C83E2B`
  (`illicit`) and `#1F6F8B` (`licit`) plus muted **indigo-plum `#5B4B8A`** for
  cross-schema (`both`) union metrics.
- **Token pair (`TRX` vs `USDT`):** Orthogonal cool-violet **plum `#5B4B8A`**
  (`TRX`) vs **sage teal `#2A9D8F`** (`USDT`), separated by ~110° and distinct
  from vermilion/amber risk encodings.
- **Status / severity:** `error` `#C83E2B`, `warn`/`partial` `#D9822B`,
  `ok`/`complete` `#2E7D6F` (pine-teal, kept quieter than `licit` cerulean),
  `dropped` `#9B2226`, `retained` `#1F6F8B`.
- **Sequential ramps (monotonic luminance):**
  - `ELIGIBILITY_CMAP` (`#F4F7FA → #A9D0DE → #4E95AE → #164E63`): single-hue
    cerulean progression; darker ink = higher valid retention. Text polarity
    flips from `#1F2933` to `#FFFFFF` at `58%` to preserve WCAG legibility.
  - `RISK_CMAP` (`#FAF6F2 → #E9B98A → #D97B48 → #9B2226`): warm sand-to-crimson
    progression; darker/warmer = worse missingness or failure mass.
- **Diverging ramp (`DELTA_CMAP`):** `#1F6F8B` (cerulean) ↔ `#F1F5F9` (paper
  zero) ↔ `#C83E2B` (vermilion), symmetric around `0.0` so unchanged cells
  recede into the canvas while shifts pop symmetrically.

## 3. Redundant Non-Color Encoding Contract

Color is never the sole channel carrying a statistical distinction:

1. **Line / marker redundancy:** Cohort overlays pair color with distinct
   linestyles (`illicit: "-"`, `suspicious: "--"`, `licit: "-."`,
   `unlabeled: ":"`) and markers (`o`, `s`, `D`, `^`).
2. **Direct numeric annotation:** Counts, percentages, and exact denominators
   sit directly beside bars and inside heatmap cells.
3. **Scale honesty:** Heavy-tailed counts (`10¹` to `10⁷`) use explicit `log10`
   or `symlog` axes with clear axis-unit labels; bounded shares (`0–100%`) stay
   strictly linear.

## 4. Per-Plot Visual Encoding Matrix (Plots 01–12)

| # | Figure | Primary encoding | Scale / layout guard | Color-theory role |
| --- | --- | --- | --- | --- |
| `01` | Table volume & coverage | Grouped bars by schema (`#C83E2B` vs `#1F6F8B`) + amber badge for non-complete status | `log10` x-axis so `17K` blacklist & `721` seeds remain legible beside `15M` tx | Establishes schema warm/cool identity on Plot 01 |
| `02` | Column missingness & dtypes | Lollipop stems along `RISK_CMAP`; exact `0%` anchored in pine-teal `#2E7D6F` | Faceted by schema; linear `0–100%` | Separates clean keys (0%) from structural nulls (~96% `accounts` timestamps) |
| `03` | Quality checks & L1 anomalies | Left: severity (`error` vermilion / `warn` amber). Right: schema + `both` plum | `log10` x-axis + direct `n (%)` labels | Keeps severity semantics distinct from schema source across adjacent panels |
| `04` | Annual tx volume | Grouped bars by token (`TRX` plum vs `USDT` sage) + warm translucent pre-mainnet band | `log10` y-axis + dashed mainnet cutoff | Orthogonal token pair avoids confusion with illicit/licit schema titles |
| `05` | Cohort composition & n-flow | Left: Split-Complementary 4-cohort bars. Right: muted slate `n_in` vs cohort-colored `n_out` | Left `log10` (0.17% vs 52.6%); right linear for additive subtraction clarity | Neutral `n_in` bar recedes so retained `n_out` carries the focus |
| `06` | Cross-schema overlap | Left: paired illicit/licit % bars. Right: plum shared `tx_hash` vs amber discordance | Left linear `%`; right `log10` rows | Highlights that overlap is symmetric in count (`3,387`) but asymmetric in share (`19.9%` vs `0.05%`) |
| `07` | Hop nesting & seed clusters | Left: `suspicious` amber vs `licit` cerulean share bars. Right: IQR bar + p50 dot + mean diamond | Left linear `%`; right `log10` fan-out | Contrasts crawl depth shapes and exposes extreme seed-cluster skew (`max=1.91M`) |
| `08` | H1–H6 eligibility matrix | Single-hue monotonic `ELIGIBILITY_CMAP` + white hypothesis dividers | Fixed `[0%, 100%]` bounds; adaptive text contrast flip at 58% | Low-eligibility cells read immediately as pale gaps against dark full-eligibility blocks |
| `09` | Zero-mass, tail ratio, skew | 4-cohort split-complementary markers (`o/s/D/^`) jittered vertically | Linear `%` / `log10` ratio / `symlog` skew + amber threshold rules (`10x`, `±2`) | Multi-panel alignment links zero-inflation directly to extreme skewness |
| `10` | Quantile ranges | Cohort-colored `p10–p90` whiskers, thick IQR bar, hollow `p50` circle, dark `mean` diamond | Auto `log10` when dynamic range > 20× and max > 25 | Hollow median vs dark diamond makes mean–median right-skew divergence instant |
| `11` | Pre-binned histograms | Overlaid cohort lines (hue + linestyle + marker) + subtle 8% vermilion fill under `illicit` | Bucket-aware x-ticks; linear cohort share `%` | Light fill anchors the 0.17% primary target without occluding the other 3 curves |
| `12` | Raw vs transformed shift | Panel A: symmetric `DELTA_CMAP` (pp). Panel B: cohort dots around 0%. Panel C: vermilion raw vs cerulean transformed | Symmetric `[-vmax, +vmax]` zero-centered colormap | Zero change vanishes into neutral `#F1F5F9`; real transform shifts stand out immediately |

## Rejected alternatives

- **Seaborn `deep` / `bright` defaults:** Equal-chroma hues fail the `unlabeled`
  subordination rule and weaken `illicit vs licit` contrast.
- **Viridis for categorical cohorts:** Sequential colormaps imply an ordinal
  numeric progression; `wallet_class` is nominal with nested/provisional roles,
  not an interval scale.
- **Dual y-axes on count + share plots:** Distort perceived ratios; replaced by
  single-scale bars with direct `count (share%)` text annotations.

## Verification

- Visual inspection of all 11 rendered PNGs under `outputs/eda/profile/raw/` and
  synthetic Plot 12 under `compare` tests.
- Unit assertion in
  [`test_eda_profile.py`](../../../../src/scripts/eda/profile/tests/test_eda_profile.py)
  confirming palette keys match canonical `COHORT_ORDER`.

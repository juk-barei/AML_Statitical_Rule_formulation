# Provenance: nested sampling and incomplete AML label sets

- **Date:** 2026-11-21
- **Rounds:** 3 parallel research lanes (sampling design, network sampling, blockchain AML labels) + 1 direct cross-check; 1 citation/URL pass; 1 review pass; 1 revision.
- **Sources consulted:** 95 research-note entries across four notes (26 sampling, 25 network, 32 AML, 12 direct), with overlap. Additional project artifacts: `outputs/profiling/cohort_counts.csv`, `db_overview.csv`, `group_overlap.csv`, `local_cohort_check.csv`, and the Step 1/2 context docs.
- **Sources accepted:** 56 entries in the final report: 46 literature/official sources (numbered 10–55) and 10 project artifacts (numbered 1–9a).
- **Sources rejected / unavailable:** Goodman 1961 full text (Project Euclid blocked; attribution via Heckathorn only); Hook & Regal 1995 (metadata only, no abstract); several paywalled full texts read at abstract level; commercial blockchain-analytics marketing pages (undated, not used); arXiv:2609.03036 (unrefereed preprint with proprietary-scale claims, listed but not relied on). Three `web_search` queries were rate-limited by Exa (HTTP 429); one OpenAlex query returned 429.
- **Verification:** PASS WITH NOTES
- **Plan:** `outputs/.plans/nested-sampling-aml-wallets.md`
- **Research files:**
  - `outputs/.drafts/nested-sampling-aml-wallets-research-sampling.md`
  - `outputs/.drafts/nested-sampling-aml-wallets-research-network.md`
  - `outputs/.drafts/nested-sampling-aml-wallets-research-aml.md`
  - `outputs/.drafts/nested-sampling-aml-wallets-research-direct.md`
  - `outputs/.drafts/nested-sampling-aml-wallets-draft.md`
  - `outputs/.drafts/nested-sampling-aml-wallets-cited.md`
  - `outputs/.drafts/nested-sampling-aml-wallets-revised.md`
  - `outputs/.drafts/nested-sampling-aml-wallets-verification.md`

## Verification notes

- 32/32 DOIs in the cited draft resolved against Crossref with matching title, year, and first author. The Hanley & Lippman-Hand DOI was corrected to `10.1001/jama.1983.03330370053031`.
- The OFAC quotation was verified verbatim against the downloaded PDF. The Lumley `twophase` description was verified against the `survey` manual, p. 152.
- Some publisher pages returned HTTP 403 to automated fetch (Wiley, OUP, Taylor & Francis, SAGE, ACM, Lippincott); the DOI resolver reached the correct article landing page in each case, so these are access blocks, not dead links.
- The FATF PDF returned 403; the HTML landing page is the alternative. The Hidiroglou PDF returned 403; only the indexed abstract was read.
- Local counts were obtained read-only via `src.scripts.ETL.get_local_engine()` over PostgreSQL TCP `localhost:5432` at 2026-11-21T08:58Z and recorded in `outputs/profiling/local_cohort_check.csv`. `pg_isready` without `-h` checks the Unix socket and returned no response; the TCP endpoint was reachable, and the licit ETL was running.
- The local licit count (3,149,914) is a moving partial, not a final `N`. The local licit run was mid-ingestion: 6 completed, 5 running, 3 pending shards at the snapshot.
- Remaining notes: the 49.7% suspicious–licit overlap comes from a 5,000-row sample whose draw method is not recorded (Wilson 95% CI about 48.3–51.1%); the test plan's ≈6,300 illicit figure is close to the local 6,324, so its provenance is unresolved; the 15,165 lower bound has no artifact (the CSV shows 15,185); the multi-seed cluster-assignment rule is unresolved (216,776 wallets reachable from more than one seed).

# Statistical information — online profile

Snapshot: overview **2026-11-20T10:57Z**; overlap **11:12Z**. The DBs are live and drift, so freeze an extract before analysis.

**Illicit:** 4,540,183 accounts; 13,480,384 transactions; 6,096,327 hop rows; blacklist **15,165–15,185** across runs; hop-0 478; suspicious **3,598,120** (hop 1–5, non-blacklist).

**Licit:** 6,614,681 accounts; 11,326,298 transactions; 80,756 hop rows; 721 seed wallets; 0 blacklisted.

**Overlap:** 2,977 licit accounts are in the illicit blacklist (0.045% of licit; 19.6% of blacklist); 6/721 licit seed wallets are blacklisted; **49.7%** of a 5,000 suspicious sample (hop 1–5, blacklist excluded) appears in licit accounts. Licit is not a clean control.

**Verdict:** three groups only after priority cleaning. Use all eligible illicit (≈6,300), then 50,000 per comparison arm, seed-cluster sampled. Do not use 500,000 per arm.

Scripts: `scripts/profile_databases.py` (table/column profile), `scripts/profile_overlap.py` (overlap and cohort counts). Outputs: `outputs/profiling/`.

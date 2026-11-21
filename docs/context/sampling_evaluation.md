# Sampling evaluation

The two online DBs are live and not a fixed snapshot: counts moved during profiling. The local mirror (2,125,343 accounts) is older than the online illicit DB (4.5M accounts).

The licit DB is not a clean sampling frame. It has 6.6M accounts, 0 blacklisted rows, and 721 seed wallets; yet 2,977 licit accounts are in the illicit blacklist, 6/721 licit seeds are blacklisted, and 49.7% of a 5,000 suspicious sample is present in licit accounts.

**Implication:** freeze a timestamp, clean licit by priority, and report the licit sampling frame before pooling. For phase 1, use all eligible illicit wallets (≈6,300), then 50,000 per comparison arm, seed-cluster sampled. Treat any uncleaned licit result as `unlabeled`, not a control.

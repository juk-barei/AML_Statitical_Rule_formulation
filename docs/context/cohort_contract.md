# Cohort contract

Unit: one wallet. Priority: **illicit > suspicious > licit > unlabeled**.

| Group | Rule | Current count |
| --- | --- | ---: |
| `illicit` | TronScan blacklist, `label = 1`; hop-0 adds no new wallets | 15,165–15,185 |
| `suspicious` | `min(hop_level) ∈ 1..5` **and** not blacklisted | 3,598,120 |
| `licit` | Licit DB accounts **minus** illicit and suspicious | 6,614,681 raw |
| `unlabeled` | Remaining accounts | not computed |

Any blacklist record at hop 1–5 is illicit, not suspicious. If a wallet is in both licit and suspicious, **suspicious wins**; if in licit and illicit, **illicit wins**. Only the leftover is licit; never relabel an overlap as unlabeled.

The licit DB is not clean: 2,977 licit accounts are blacklisted, 6/721 licit seed wallets are blacklisted, and 49.7% of a 5,000 suspicious sample appears in licit accounts. Clean the overlaps before calling any wallet licit; otherwise it stays `unlabeled`.

Hop depth is nested inside `suspicious`, not crossed with class. Wallet is the unit; seed is the clustering unit. Exact licit–suspicious overlap and the licit sampling frame remain open.

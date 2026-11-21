# Feature-definition audit

- **H2 burst:** implemented on USDT only; `docs/hypothesis.md` says volume in+out. Decide the token scope before testing.
- **H6 direction:** `docs/hypothesis.md` needs IN/OUT direction; the notebook builds events from `from_address`/`to_address` without carrying direction.
- **H4 coverage:** Jaccard is defined only when both sets are non-empty; illicit passes are rare.
- **Activity floor:** H2 pass rates reverse when the ≥5-USDT-event floor is applied; report both.
- **Hygiene:** drop `hex_address` from analysis views unless the hex form is required.

Do not silently change a feature after seeing results. Record the fix in the task file and re-run the profile.

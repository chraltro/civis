# Changelog

All notable changes to the Civis Index methodology and data are recorded
here. Pure code refactors are noted in commit messages, not here.

## [Unreleased]

## [0.1.0] - 2026-05

Initial release. Migrated the prototype dashboard into a versioned repo with
a real Python pipeline, validation suite, CI, and weekly refresh.

### Methodology

- **24 indicators across 9 equally-weighted domains.** Domains: Material,
  Health, Knowledge, Safety, Equality, Freedom, Work, Environment,
  Wellbeing.
- **Hierarchical aggregation.** Indicator z-score → mean within domain →
  weighted mean across domains, weights normalize to sum to 1.
- **Panel-wide z-scoring.** Across all 29 countries × 1990–2023, not
  per-year.
- **Winsorization at ±2.5σ.** Bounds outlier influence so the mean is a
  defensible aggregator.
- **Sign convention.** Indicators have a `direction` of `up` or `down`.
  `down` indicators are sign-flipped after z-scoring.
- **Sporadic-data interpolation.** Linear within observed range; held
  constant before first / after last observation.

### Corrections from the prototype

- **LIS Gini scale.** Prototype handled the LIS (0..1) vs World Bank (0..100)
  scale gap with a hard-coded multiplication. Replaced with a per-source
  `scale` field in the manifest and an automated scale-mismatch validator.
  Tests now catch this bug class automatically.
- **RSF press freedom direction.** Prototype correctly handled the pre-2022
  RSF series as `down` (lower=freer). Direction is now asserted by the
  `directions` validator against a small panel of known-correct rankings,
  so a future migration to the post-2022 RSF score (which would flip the
  direction) cannot pass CI silently.

### Open questions tracked as issues

- GDI direction symmetry (`1 − |1 − GDI|`)
- Equality domain has only 2 indicators
- Internet users saturation in late period
- Adolescent fertility placement (Wellbeing vs Health vs Equality)
- No social trust / political participation indicator in Freedom

See [METHOD.md](METHOD.md) for full methodological detail.

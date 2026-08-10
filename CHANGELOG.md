# Changelog

All notable changes to the Civis Index methodology and data are recorded
here. Pure code refactors are noted in commit messages, not here.

## [Unreleased]

### Methodology

- **Dropped `safe_walking` ("Feel safe walking alone at night").** OWID
  deleted the Gallup World Poll dataset and all three candidate slugs now
  return 404. The only live replacement is a different survey (UN SDG
  16.1.4) covering 17 of the 29 countries, missing NOR, DNK, NLD and SGP
  among others. Adopting it would have counted an extra Safety strength for
  the countries it covers and silently not for the rest, so the indicator is
  removed instead. Safety retains four full-coverage indicators: homicides,
  suicide, road deaths, political stability. Indicator count is now 31.
- **`political_stability` re-sourced.** The World Bank moved the Worldwide
  Governance Indicators out of the default WDI database and prefixed the
  codes, so the old `PV.EST` answered "deleted or archived". Now fetched as
  `GOV_WGI_PV.EST` from source database 3. Same -2.5..+2.5 estimate, so
  scores are comparable; coverage is 29/29 countries, 1996-2024.

### Fixed

- **Weekly refresh no longer fails on World Bank throttling.** The API sheds
  load by answering 400 Bad Request, and the retry layer treated every 4xx
  except 429 as permanent. A varying random subset of indicators failed each
  week (22 of 31 on 2026-08-03, 4 on 2026-08-10). WB requests now retry on
  400 with a longer backoff ladder.
- **Inter-request pacing was skipped on success.** The `time.sleep(sleep_s)`
  in `fetch_all` sat after the `break` that ends a successful fetch, so a
  healthy run hit the World Bank API back to back with no delay. Pacing now
  applies to every request, and the default gap is 1.5s.
- **Clearer error for a retired indicator code.** The World Bank returns
  HTTP 200 with a message body when a code is archived. That surfaced as
  `unexpected WB response for <code>: [{...}]`; it now reports the code, the
  source database, and the API's own message.

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

# Civis Index — methodology

## What we are measuring

The Civis Index attempts to summarize "where do people live well" across 29
advanced economies, with explicit positions on what living well means:

- It includes material conditions but does not let them dominate.
- It treats freedom, equality, and environmental sustainability as parts of
  living well, not as nice-to-haves layered on top of GDP.
- It exposes the value judgment by letting users reweight the domains.

The headline composite score is a single number per country per year, but the
artifact is meant to be the **shape**, visible on the radar chart, of how a
country distributes wellbeing across its nine domains. A country can score
high overall by being unbalanced (Singapore is strong on Material and Safety,
weak on Freedom) or by being broadly even (the Nordics).

## Why the BCW Index is broken

The reference work is a "Best Country in the World" infographic that takes 12
indicators, computes z-scores, and reports the median. Concretely:

1. **Six of the 12 indicators measure being a rich country**: GDP per capita,
   household consumption, broadband access, internet access, infant mortality,
   maternal mortality. These all correlate strongly with national income. A
   median-of-12 design effectively counts "rich" six times.
2. **Zero indicators measure inequality, freedom, or sustainability**. That
   produces results like Hong Kong ranked second despite the rapid 2020–2022
   collapse of its liberal democratic and press freedom institutions, and
   Singapore in the top three despite indicators of work-life imbalance, the
   absence of inequality measures, and constrained civil liberties.
3. **The median is the wrong aggregator** for 12 z-scores once you fix (1)
   and (2). With more indicators per "concept" you over-weight common
   variation; the median paradoxically ends up reading the median of the
   over-represented concept.

Civis's response is structural, not cosmetic. We rebuild the index with
hierarchical aggregation, a balanced domain set, and the mean — with
winsorization to make the mean defensible.

## Construction

### Indicator selection

31 indicators across 9 domains. Each domain has 2 to 4 indicators. Each
indicator is selected to (a) measure something distinct from its sibling
indicators within the domain and (b) have continuous coverage on at least 27
of 29 panel countries from 1990–present, with a primary source under a
permissive license.

Indicators are listed in [`pipeline/indicators.py`](pipeline/indicators.py),
which is the source of truth. The README has a tabular summary.

### Source manifest

Each indicator declares one or more sources. The first source is primary; the
fetcher discovers OWID column names from a small list of candidates because
OWID periodically renames its short column names. Cross-source merges go
through a sanity check: if median values differ by more than 5x between
sources, the merge raises rather than producing a hybrid series with a
silent scale change. (This is the LIS-vs-WB Gini bug class; LIS reports Gini
0..1 and World Bank reports it 0..100. A merge without rescaling produces a
nonsense series. The validator catches this automatically.)

### Interpolation

For each country and indicator, observations are interpolated linearly inside
the observed range and held constant before the first observation and after
the last. Held-constant pre/post is the same convention the BCW used; it
preserves rankings during periods of missing data without manufacturing
trend.

A held-constant series spanning all 34 years (1990–2023) is suspicious — it
means a single observation got carried across the whole period. The
`coverage` validator flags any (country, indicator) where this happens.

### Z-scores

Each indicator is z-scored across the **entire panel** (29 countries × 34
years), not per-year. This is a methodologically loaded choice:

- **Per-year z-scoring** answers "how does Country X compare to its peers in
  year T?" but produces non-comparable trajectories: a constant z-score over
  time means "kept pace with peers", not "stayed in the same place".
- **Panel-wide z-scoring** answers "how does Country X in year T compare to
  the entire 29-country, 34-year sample?" A flat trajectory means "absolute
  position unchanged"; a rising trajectory means absolute improvement; a
  rising rank but flat z-score means everyone is rising together.

Civis uses the second because the time dimension is part of what we want
the index to communicate. Adolescent fertility falling globally is an
absolute improvement, not just a relative one.

### Winsorization

After z-scoring, values are clipped to ±2.5σ. This is the move that makes
"mean of z-scores" defensible. The mean is sensitive to outliers — a country
at z = +6 dominates the domain mean — but the median throws away signal
across a 29-country panel. Winsorization at ±2.5σ keeps signal while
preventing extreme outliers from running away with a domain.

±2.5σ catches roughly the top and bottom 0.6% of a normal distribution. In
practice the only series that hit this cap are gross outliers: Singapore on
GDP per capita in the 2010s, Lithuania on adolescent fertility in 1990,
Estonia on infant mortality in the early 1990s. None of those should
dominate a domain that has only two or three indicators.

### Sign convention

Each indicator has a `direction` of `up` (higher is better) or `down` (lower
is better). After z-scoring, `down` indicators are sign-flipped so that
positive z always means "better". Then the domain mean is well-defined.

### Aggregation

```
indicator_z[i, c, t]  =  winsorized z-score of indicator i for country c in year t,
                          sign-flipped for 'down' indicators

domain_z[d, c, t]     =  unweighted mean over indicators i in domain d
                          (skipping NaN: a missing indicator doesn't penalize)

composite[c, t]       =  weighted mean over domains d
                          (weights default to 1/9 each; user-adjustable on dashboard)
```

The composite is computed **client-side** in the dashboard from the per-
domain z-scores in `civis.json`. The Python pipeline emits an unweighted
composite as a default convenience, but the dashboard recomputes whenever
weights change.

## Comparison with BCW

The BCW Index would write the same data flow as:

```
BCW_score[c, t]       =  median over indicators i, sign-flipped for 'down',
                         z-scored per-year (not panel-wide).
```

Three substantive differences in the formula, plus the indicator set:

1. **median → mean** (with winsorization to bound outlier influence).
2. **flat indicator list → hierarchical** (indicator → domain → composite).
3. **per-year → panel-wide** z-scores.

Each of these moves the result. Combined with the expanded indicator set,
Hong Kong drops from rank 2 in BCW to outside the top 15 in Civis, primarily
because Freedom and Equality go from being absent to having equal weight to
Material.

## Validation

The pipeline does not deploy data that fails validation. Five families of
checks, run by `civis validate`:

1. **Coverage.** Every (indicator, country) has ≥1 real observation in
   1990–YEAR_MAX. A series that's exactly constant for the entire panel
   period is flagged.
2. **Directions.** For each indicator, the top-3 by 5-year tail mean must
   include at least one country from a known-good panel (e.g. press freedom:
   Norway, Finland, Sweden, Denmark). This catches sign flips and rescale
   bugs without anyone reading numbers.
3. **Scale.** When merging primary + fallback sources, their median values
   must agree to within 5x. This catches the LIS-vs-WB Gini bug class
   automatically.
4. **Aggregation invariants.** Domain z must equal the unweighted mean of
   its constituent indicator z-scores (NaN-skipping). Composite must equal
   the unweighted mean of domain z. Both are recomputed and asserted.
5. **Ranking snapshot.** The latest-year ranking is compared against a
   committed fixture (`tests/fixtures/ranking_snapshot.json`). Any change
   forces an explicit `--update-snapshot` step. This makes data refreshes
   visible in PR review.

The weekly refresh workflow runs `validate`. On failure it opens a GitHub
issue with the validator output and does not commit new data.

## Open methodological questions

These are the live discussions about Civis methodology. Each is tracked as a
GitHub issue; methodology changes go through PR with a before/after
ranking diff.

- **GDI direction.** GDI close to 1.0 = most equal. Both >1.0 and <1.0
  indicate gender inequality. We currently treat it as `up`, which is
  approximately correct in our 29-country panel because most values are
  ≤ 1.0. A symmetric formulation would be `1 − |1 − GDI|`. This change
  would meaningfully shift Equality scores for countries above 1.0
  (currently Lithuania, Estonia, Israel).
- **Equality has only 2 indicators.** Adding wealth-Gini or top-10%
  income share (WID.world) would reduce single-indicator noise.
- **Internet penetration saturation.** After ~2015 internet users
  saturates near 100% in advanced economies. The z-score still rewards
  late catch-up but the indicator stops discriminating. Consider PISA
  scores for the late period as a non-saturating Knowledge measure.
- **Adolescent fertility placement.** Currently in Wellbeing as an
  autonomy proxy. Could move to Health (it's a health outcome) or
  Equality (it correlates with women's economic agency).
- **No social trust or political participation indicator** despite
  Freedom being a domain. V-Dem has these as sub-indices.
- **Press freedom methodology change.** RSF migrated to a 0..100
  higher-is-better score in 2022. Migrating to the new series requires
  flipping the direction in the manifest and re-validating direction
  panels.

## What Civis is not

- Not a global ranking. The 29-country panel is "advanced economies" and
  exists to compare like-with-like. Comparing Mexico to Norway requires
  different sources and a different weighting.
- Not a definitive answer. The dashboard exists because there is no
  definitive answer; users are expected to disagree with the default
  weights and the slider exists to make that disagreement productive.
- Not a freedom index, an inequality index, or any of its constituent
  domains alone. The index sums multiple positions on what living well
  means; reading any single column instead of the composite is fine but
  is no longer "Civis".

## Differences from prototype

The original prototype had two known bugs that are baked into the test suite:

- **LIS Gini scale**: the prototype handled the LIS-vs-WB scale gap with a
  hard-coded `*100`. The pipeline now uses a per-source `scale` field plus
  an automatic scale-mismatch test.
- **RSF direction**: prototype correctly used `down` for the pre-2022
  series. Direction is asserted by the `directions` validator against a
  known-good panel.

Both bugs would have been caught by the validator if it had existed in the
prototype. They are now part of the test suite.

# Civis Index

**Where do people actually live the best lives?**

Civis is a hierarchical index of wellbeing across 29 advanced economies, 1990 to
the present. 31 indicators across 9 equally-weighted domains: material conditions,
health, knowledge, safety, equality, freedom, work, environment, subjective
wellbeing. Indicator z-scores are aggregated to domain z-scores, then to a
country composite. Domain weights are user-adjustable on the dashboard, so the
value judgment is visible rather than hidden.

This repository contains the data pipeline, the dashboard, and the methodology.
The dashboard refreshes weekly from public sources.

## The argument

A widely-circulated "Best Country in the World" infographic (BCW Index) ranked
Hong Kong second. It does this by taking 12 indicators, z-scoring each, and
reporting the median per country. Six of those 12 are close proxies for "rich
and developed" (GDP, household consumption, broadband, internet, infant
mortality, maternal mortality). It has no measure of inequality, no measure of
political freedom, no measure of work-life balance, and no measure of
environmental sustainability. The result is a wealth ranking dressed up as a
wellbeing index. That ranking laundered an authoritarian government's material
achievements into a wellbeing claim.

Civis takes the same starting question and rebuilds the index. Three structural
changes:

1. **Hierarchical aggregation**, not a flat median. Indicator z-scores → mean
   within domain → mean across domains. Correlated indicators (GDP + household
   consumption) don't double-count a single underlying factor (income), because
   they share a domain. A whole missing domain costs you 1/9 of the score, not
   1/12 of a variable list.
2. **Nine equally-weighted domains**, deliberately balanced between
   outcome-quantity (Material, Health, Knowledge) and outcome-quality
   (Equality, Freedom, Work, Environment, Wellbeing). Equal weights are a
   defensible starting point, not a claim of objectivity. The dashboard
   exposes a weight slider for each domain so you can disagree without leaving
   the page.
3. **Winsorized z-scores at ±2.5σ**, which lets us use the mean (not the
   median) as the aggregation operator without single-country outliers
   dominating. Median throws away too much signal across a 29-country panel.

The headline finding under equal weights: **Norway, Switzerland, Iceland,
Denmark, Sweden** in the top five. Hong Kong drops from 2nd (BCW) into the
back half once Freedom, Equality, and Environment carry equal weight.
Singapore drops similarly. The United States lands in the middle of the pack
despite very high GDP, because its inequality, suicide rate, environmental
footprint, and incarceration-driven safety score offset its material lead.

## What this repository contains

- **`pipeline/`** — the Python data pipeline. `civis fetch` pulls the 31
  indicators from World Bank WDI and Our World in Data; `civis process`
  produces a single canonical `data/processed/civis.json`; `civis validate`
  runs five families of correctness checks against the data.
- **`web/`** — the static dashboard. Vite + TypeScript + D3, no framework,
  no server. Reads `data/processed/civis.json` at load time.
- **`data/`** — the latest processed JSON and CSV, plus dated snapshots from
  every weekly refresh in `data/snapshots/`.
- **`tests/`** — pytest suite covering aggregation invariants, direction
  panels, scale-mismatch detection, and ranking snapshot drift.
- **`.github/workflows/`** — CI on every PR; weekly cron that refreshes the
  data and opens an issue if validation fails; auto-deploy to GitHub Pages.

For the methodology in detail (winsorization rationale, sign conventions,
interpolation rules, panel boundaries), see [METHOD.md](METHOD.md).

## Reproduce from scratch

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), and Node 22+.

```bash
git clone https://github.com/chraltro/civis
cd civis

# Python pipeline
uv venv --python 3.11
uv pip install -e ".[dev]"
source .venv/bin/activate

civis fetch              # pulls all 31 indicators to data/raw/
civis process            # writes data/processed/civis.json + civis.csv
civis validate           # runs the validation suite
pytest                   # 26 unit tests

# Web dashboard
cd web
npm install
npm run dev              # http://localhost:5173

# Or build for static deploy
npm run build            # output in web/dist/
```

`civis refresh` does fetch + process + validate in one shot, and writes a
dated snapshot to `data/snapshots/`. That's what the weekly cron runs.

## Coverage

29 economies, all of which had high-income status by 1990:

> Australia · Austria · Belgium · Canada · Czechia · Denmark · Estonia ·
> Finland · France · Germany · Hong Kong · Iceland · Israel · Italy · Japan ·
> Korea · Lithuania · Netherlands · New Zealand · Norway · Poland · Portugal ·
> Singapore · Slovenia · Spain · Sweden · Switzerland · United Kingdom ·
> United States.

The country list is intentional: it's a comparison frame for "developed
countries", not a global ranking. Adding emerging economies would change what
the index *measures*, not just its size.

## The 9 domains and 31 indicators

| Domain | Indicators |
|---|---|
| **Material** | GDP per capita (PPP), Household consumption per capita, Fixed broadband subs (per 100) |
| **Health** | Life expectancy at birth, Infant mortality (per 1,000), Maternal mortality (per 100k), Under-5 mortality (per 1k) |
| **Knowledge** | Mean years of schooling, Tertiary attainment, 25+, Internet users, R&D spending |
| **Safety** | Homicide rate, Suicide rate, Road traffic deaths, Political stability (WGI) |
| **Equality** | Income Gini (post-tax), Gender Development Index, Top 10% income share |
| **Freedom** | Liberal democracy (V-Dem), Press freedom (RSF, lower=freer, pre-2022 methodology), Anti-corruption (CPI), Human rights (V-Dem) |
| **Work** | Annual working hours per worker, Unemployment rate, Employment-to-population ratio (15+) |
| **Environment** | PM2.5 air pollution, CO₂ emissions per capita, Renewable energy share, Terrestrial protected areas |
| **Wellbeing** | Life evaluation (Cantril ladder), Adolescent fertility rate (per 1k) |

## Limitations and open questions

- **Equality has only two indicators.** When one is missing the domain
  becomes noisy. Adding a top-10% income share or wealth-Gini would help.
- **GDI is treated as monotonic.** Values close to 1.0 are most equal; both
  >1.0 and <1.0 indicate gender inequality. Civis treats it as `up`, which is
  approximately correct for our 29-country panel but not strictly correct.
  Open issue: fold as `1 − |1 − GDI|`.
- **Knowledge has internet penetration**, which saturated in advanced
  economies after ~2015. The z-score still rewards late catch-up; the domain
  may want a non-saturating measure (e.g. PISA scores) for the late period.
- **Adolescent fertility sits in Wellbeing** as a proxy for life-trajectory
  autonomy. Defensible but contested. Could move to Health or Equality.
- **No social trust or political participation indicator** despite Freedom
  being a domain. V-Dem has these as sub-indices and could be added.
- **Z-scoring is panel-wide**, not per-year. A country at z=0 in 2023 is
  "average across the entire 1990–2023 sample." Trajectory is comparable to
  the long-run baseline. This is deliberate; it means rankings shift slowly
  but are temporally meaningful.
- **Press freedom (RSF) changed methodology in 2022** to a 0–100 higher-is-
  better score. Civis currently uses the pre-2022 series (lower=better,
  direction `down`). Migrating to the post-2022 series will require flipping
  the direction in the manifest and re-validating direction panels.

These are tracked as issues. Methodology changes go through PR review with a
before/after ranking diff.

## Sources and licenses

| Source | What | License |
|---|---|---|
| World Bank WDI | most economic & demographic indicators | [CC-BY 4.0](https://datacatalog.worldbank.org/public-licenses) |
| Our World in Data | schooling, GDI, V-Dem, RSF, CPI, work hours, CO₂, renewables, Cantril | [CC-BY 4.0](https://ourworldindata.org/faqs#how-is-your-work-copyrighted) |
| World Happiness Report (Cantril ladder) | subjective wellbeing | [CC-BY 4.0](https://worldhappiness.report/) |
| V-Dem Institute | liberal democracy index | [CC-BY 4.0](https://v-dem.net) |
| Reporters Without Borders | press freedom | [CC-BY 4.0](https://rsf.org/en/index) |
| Transparency International | CPI | [CC-BY-ND 4.0](https://www.transparency.org/en/cpi) |
| UNDP Human Development Reports | mean schooling, GDI | [CC-BY 3.0 IGO](https://hdr.undp.org/copyright-and-terms-use) |

Civis is licensed under the MIT license; data is redistributed under the
license of each upstream source.

## How to cite

```
Altrock, C. (2026). Civis Index: a hierarchical wellbeing index across
29 advanced economies. https://github.com/chraltro/civis
```

## Contributing

Methodology changes (new indicators, removed indicators, domain reweighting,
direction flips) go through an issue first. Code structure changes are PRs.
See [CONTRIBUTING.md](CONTRIBUTING.md).

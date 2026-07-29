# jma-data

The data behind the charts in [Japan Macro Advisors](https://takujiokubo.substack.com)
articles, published as interactive pages.

**Browse it here → https://takujiokubo.github.io/jma-data/**

Each article gets a folder holding the tidy CSV for every chart in it, plus an
interactive page that redraws those charts so a reader can hover to read values,
zoom into a period, and download any series. The charts are the ones published in
the article, from the same data — not a separate cut.

Model output (term premia, the natural-rate anchor, yield forecasts) is JMA's own
estimate. You are welcome to use it; please attribute it. Nothing here is
investment advice.

## Layout

Two kinds of page live here: **article panels**, one per published piece, and
**standing datasets** such as the yield-curve model output, which are refreshed
per model vintage rather than per article.

```
2026-07-20-long-climb/          an article panel
  index.html       the interactive panel  (generated — do not hand-edit)
  panel.json       the manifest: what each exhibit is and how it is drawn
  data/*.csv       one tidy file per exhibit, as the chart script emitted it
jgb-yield-curve-model/          a standing dataset (refreshed per model vintage)
builder/
  build_panel.py   panel.json + data/*.csv  ->  index.html
  build_index.py   every panel.json         ->  the landing page
  qa_panel.py      gates the built page against its sources
```

## Building a panel

```bash
python builder/build_panel.py 2026-07-20-long-climb
python builder/qa_panel.py    2026-07-20-long-climb
python builder/build_index.py
```

`build_panel.py` reads the interactive house palette from the chart library at
`G:\My Drive\charts\jma_plotly_style.py` when it is present, so a theme change
there reaches these panels on the next build. Without it, the builder falls back
to a vendored copy of the same values and says so.

## Adding a new article

1. Make `<slug>/data/` and copy in each chart's `*_data.csv` from the chart
   library, named `chart-<n>-<what-it-is>.csv` in article order.
2. Write `<slug>/panel.json`. Take `title`, `source` and `ylabel` verbatim from
   each chart script's `TITLE` / `SOURCE` / `YLABEL` constants.
3. Read the chart script's plotting code for the things the CSV cannot carry —
   the view window, the chart form, which columns are series and which are flags,
   what the legend should call them. Getting this wrong produces a plausible
   chart that is not the published one.
4. Build, QA, then extend `qa_panel.py` with gates for the new article's
   published figures. The gates exist to catch a panel that disagrees with the
   article, which is the only failure that actually matters here.

### Manifest kinds

| kind | for | key fields |
|------|-----|-----------|
| `line` | time series | `x`, `start`/`end`, `series[]`, `hlines[]`, `yrange`, `decimals` |
| `decomp` | components stacked to a total | `components[]`, `total`, `split_col` |
| `curve` | a cross-section: maturity on the x-axis | `tenors[]`, `value_prefix`, `lines[]`, `xscale` |
| `bar_line` | grouped bars with an overlay line | `resample`, `bars[]`, `line`, `flag_col` |
| `table` | a table, not a series | `columns[]`, `rule_after_col`/`rule_after_value` |

Any time-series kind accepts `split_col` / `solid_value`: set them and every
series is drawn twice — solid over the rows matching `solid_value`, dotted over
the rest, with a marked boundary — so a projection can never be mistaken for an
observation.

`decomp` stacks with `barmode: "relative"` rather than filling an area, because
a component can be negative (the 10Y term premium is, in 92 months of the
sample) and a negative component has to hang below the zero line while the
positive one still rises from it.

`curve` spaces maturities evenly by default. On a true linear axis 2Y and 5Y sit
inside the leftmost 7% of a 40-year span, which crushes the part of the curve the
policy rate actually moves. Pass `"xscale": "linear"` for year spacing.

## Why a manifest

The data CSV carries numbers and nothing else. It cannot tell you that the
30-year comparison chart windows from end-2017 though its file starts in 2000,
that the natural-rate chart is year-end-sampled bars rather than a monthly line,
that `provisional` is a flag column and not a series, or that `tp_10y_bp` should
read "JMA model" in a legend. Those facts live in the chart scripts, which are
matplotlib and prose and not safely importable. The manifest states them once per
article so the panel matches what was published.

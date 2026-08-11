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
   each chart script's `TITLE` / `SOURCE` / `YLABEL` constants. **Set `tier`** —
   see below; the builder prints a note if you forget.
3. Read the chart script's plotting code for the things the CSV cannot carry —
   the view window, the chart form, which columns are series and which are flags,
   what the legend should call them. Getting this wrong produces a plausible
   chart that is not the published one.
4. Build, QA, then extend `qa_panel.py` with gates for the new article's
   published figures. The gates exist to catch a panel that disagrees with the
   article, which is the only failure that actually matters here.

### What a page offers, and who it is for

**Three keys, and they are independent.** They were one until 2026-08-12, which
is how `paid` came to be read as a description of a page's subject matter.

| key | values | what it does |
|-----|--------|--------------|
| `downloads` | `true` / `false` / absent | **Does the page offer its data?** `true` gives every card a "Download CSV" link, renders the workbook button if a `workbook` is declared, and prints the closing line that says so. `false` gives none of them, and makes declaring a `workbook` a hard error. **Absent defaults to `tier != "free"`** — the behaviour from before the key existed, so every page already built rebuilds byte-identical. |
| `tier` | `free` / `paid` / absent | **What the page says about subscribing.** A `free` page carries the perk block naming what a subscription buys, above the Subscribe button. Required on every page built from 2026-08-05; absent means pre-rule, and the builder prints a note. Kept under its old name because renaming it would move bytes on every live page. |
| `audience` | `free` / `paid` | **Who the page is for.** Inert — the builder never reads it. It exists so the set of paid pages is queryable, which matters while paid pages are still hosted in this public repo. |

**The perk block is suppressed whenever `downloads` is true**, whatever the tier:
a page that hands out its data cannot also advertise that data as the thing a
subscription buys. That is what makes a free page *with* downloads — permitted by
exception, Takuji 2026-08-11 — expressible without omitting `tier` and thereby
recording a new page as pre-rule.

Which value is right for a given page is **policy, not schema**: Takuji's
decision, recorded in
`G:\My Drive\Takuji-home\40.Projects\Substack\_publication-protocol.md`. Nothing
about a page's subject matter follows from any of these keys — pages here carry
report exhibits, model output, standing statistics and pipeline panels, in both
tiers.

> **None of this restricts access.** `unlisted: true` keeps a page off the
> landing index and authenticates nobody, and this repo is public, so any page in
> it is readable by anyone holding the URL. Access control is the separate gated
> site, `jma-data-paid`, behind Cloudflare Access.

The tidy CSVs still live in `<slug>/data/` on a free page — they are the
builder's input and the workbook's provenance. The page just doesn't offer them.
The chart values are inline in `index.html` as figure JSON either way, so this
governs what is *offered*, not what is reachable.

`qa_panel.py` gates all of this in both directions, resolving the keys from the
manifest itself rather than importing the rule from the builder, so a page cannot
drift into a state its manifest does not declare. Pages built before the rule
carry no `tier` key and are unchanged by it — the decision was forward-only, and
they rebuild byte-identical. Do not retrofit.

### Manifest kinds

| kind | for | key fields |
|------|-----|-----------|
| `line` | time series | `x`, `start`/`end`, `series[]`, `hlines[]`, `yrange`, `decimals` |
| `decomp` | components stacked to a total | `components[]`, `total`, `split_col` |
| `curve` | a cross-section: maturity on the x-axis | `tenors[]`, `value_prefix`, `lines[]`, `xscale` |
| `bar_line` | grouped bars with an overlay line | `resample`, `bars[]`, `line`, `flag_col` |
| `signed_bar_line` | bars where the sign carries meaning, plus a line on a second axis | `value{col,pos_label,neg_label}`, `line`, `flag_col`, `yrange`/`ytick`, `y2range`/`y2tick`, `hlines2[]` |
| `ranked_bars` | a league table: two panels of horizontal bars over the same rows in the same order | `label_col`, `year_col`, `top_n`, `panels[]` |
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

`signed_bar_line` splits the series into two traces by sign, so each direction
gets its own colour and its own legend entry — that is where the published PNG's
direction arrows go on a page a reader can zoom. Its two y-ranges are stated
rather than autoscaled: the intervention chart deliberately offsets them so the
bars occupy the lower half of the frame and the exchange rate the upper half,
which is what lets a reader read up from a bar to the rate that prevailed.

`ranked_bars` sorts once, by the first panel's column, and the second panel
inherits the order — the re-ordering between the panels is the point of the
chart. Rows are filtered to the latest year present first: the reserve CSV
carries every candidate economy stamped with its own last observation, and one
bar chart must not mix vintages. At phone width the panels stack rather than
shrink; side by side, each would get about 100px once the label column is paid
for.

## Why a manifest

The data CSV carries numbers and nothing else. It cannot tell you that the
30-year comparison chart windows from end-2017 though its file starts in 2000,
that the natural-rate chart is year-end-sampled bars rather than a monthly line,
that `provisional` is a flag column and not a series, or that `tp_10y_bp` should
read "JMA model" in a legend. Those facts live in the chart scripts, which are
matplotlib and prose and not safely importable. The manifest states them once per
article so the panel matches what was published.

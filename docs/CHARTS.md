# Every chart, diagram and blueprint: 78 kinds

Each image is drawn by the engine from sample data. **Record** says whether the kind writes a full per-item machine-readable record today (42 of 78). **Colour vision** is the result of the engine's colour-vision check.

[Document figures](#document-figures) (26) · [Charts (chart engine)](#charts-chart-engine) (33) · [Mermaid diagrams](#mermaid-diagrams) (6) · [Project census figures](#project-census-figures) (12) · [Module explorer](#module-explorer) (1)

## Document figures

### bar

**Answers:** Is the library's code mass spread across its modules, or concentrated in one?

Family: comparison · Record: no · Colour vision: n/a

![bar](images/docgen-bar.png)

### c4

**Answers:** What runs inside the shop and who talks to whom?

Family: workflow / sequence / state / architecture · Record: yes · Colour vision: n/a

![c4](images/docgen-c4.png)

### centrality

**Answers:** Which services are the hubs whose failure would reach furthest?

Family: network · Record: yes · Colour vision: pass

![centrality](images/docgen-centrality.png)

### choropleth

**Answers:** Is boundary complexity concentrated in a few countries, or spread evenly across the world?

Family: geography · Record: no · Colour vision: pass

![choropleth](images/docgen-choropleth.png)

### code pair

**Answers:** What changes in the function, and when does the change apply?

Family: narrative / explanation · Record: yes · Colour vision: pass

![code_pair](images/docgen-code_pair.png)

### dataflow

**Answers:** What happens to an order between the customer and the warehouse?

Family: workflow / sequence / state / architecture · Record: yes · Colour vision: n/a

![dataflow](images/docgen-dataflow.png)

### decision tree

**Answers:** Where should the on-call engineer look first when checkout latency alarms?

Family: workflow / sequence / state / architecture · Record: yes · Colour vision: pass

![decision_tree](images/docgen-decision_tree.png)

### dependency graph

**Answers:** Which of this package's engines depend on which others, and can any of them be removed independently?

Family: workflow / sequence / state / architecture · Record: no · Colour vision: n/a

![dependency_graph](images/docgen-dependency_graph.png)

### deployment

**Answers:** What runs where, and which connections cross a trust boundary?

Family: workflow / sequence / state / architecture · Record: yes · Colour vision: n/a

![deployment](images/docgen-deployment.png)

### echarts

**Answers:** 

Family: bridge to the chart engine · Record: yes · Colour vision: n/a

![echarts](images/docgen-echarts.png)

### error map

**Answers:** Which component raised this code, and how worried should I be?

Family: reference / lookup · Record: yes · Colour vision: pass

![error_map](images/docgen-error_map.png)

### flowchart

**Answers:** At which points in a docgen build can a document be refused, and what refuses it?

Family: workflow / sequence / state / architecture · Record: no · Colour vision: n/a

![flowchart](images/docgen-flowchart.png)

### geo map

**Answers:** Which countries cost this engine's bundled boundary dataset the most geometry to draw?

Family: geography · Record: no · Colour vision: pass

![geo_map](images/docgen-geo_map.png)

### heatmap

**Answers:** Do any directories mix code and documentation, or is each one single-purpose?

Family: matrix / heat · Record: no · Colour vision: pass

![heatmap](images/docgen-heatmap.png)

### isometric3d

**Answers:** How lopsided is the file distribution across the five busiest directories?

Family: 2.5D / 3D · Record: no · Colour vision: n/a

![isometric3d](images/docgen-isometric3d.png)

### layered workflow

**Answers:** How deeply nested is the project: is it flat, or does it bury its content?

Family: workflow / sequence / state / architecture · Record: no · Colour vision: n/a

![layered_workflow](images/docgen-layered_workflow.png)

### mermaid

**Answers:** What does graphify actually produce when you point it at a tree, and what consumes each output?

Family: bridge to the Mermaid engine · Record: no · Colour vision: n/a

![mermaid](images/docgen-mermaid.png)

### pie

**Answers:** What kind of file is this tree mostly made of?

Family: part to whole · Record: no · Colour vision: pass

![pie](images/docgen-pie.png)

### radar

**Answers:** Does the tree have a lopsided shape across its main directories, or a balanced one?

Family: comparison · Record: no · Colour vision: n/a

![radar](images/docgen-radar.png)

### sankey

**Answers:** Why do two figures count 210 files and 170 files?

Family: flow · Record: no · Colour vision: pass

![sankey](images/docgen-sankey.png)

### sequence

**Answers:** In what order does a build consult the registry, render figures, and run the export gates?

Family: workflow / sequence / state / architecture · Record: no · Colour vision: n/a

![sequence](images/docgen-sequence.png)

### severity incident

**Answers:** How serious were this quarter's incidents, which areas had them, and did they cluster?

Family: time · Record: yes · Colour vision: pass

![severity_incident](images/docgen-severity_incident.png)

### state

**Answers:** Once a build starts, what states can a document actually end in?

Family: workflow / sequence / state / architecture · Record: no · Colour vision: n/a

![state](images/docgen-state.png)

### story strip

**Answers:** In what order does a payout that is recorded too late turn into a loss, and what stops it?

Family: narrative / explanation · Record: yes · Colour vision: pass

![story_strip](images/docgen-story_strip.png)

### system map

**Answers:** How is the project's file population distributed across its directories?

Family: workflow / sequence / state / architecture · Record: no · Colour vision: n/a

![system_map](images/docgen-system_map.png)

### timeline

**Answers:** Was this project built steadily, or in bursts?

Family: time · Record: no · Colour vision: n/a

![timeline](images/docgen-timeline.png)

## Charts (chart engine)

### area

**Answers:** How many active users did the product have each month?

Family: time-series · Record: yes · Colour vision: n/a

![area](images/visual-engine-area.png)

### area stacked

**Answers:** How is traffic split between web, mobile and API clients over time?

Family: time-series · Record: yes · Colour vision: pass

![area_stacked](images/visual-engine-area_stacked.png)

### bar

**Answers:** Which month shipped the most releases?

Family: comparison · Record: yes · Colour vision: n/a

![bar](images/visual-engine-bar.png)

### bar grouped

**Answers:** How does each team's median review time compare between the two quarters?

Family: comparison · Record: yes · Colour vision: pass

![bar_grouped](images/visual-engine-bar_grouped.png)

### bar horizontal

**Answers:** Which services receive the most incident pages?

Family: comparison · Record: yes · Colour vision: n/a

![bar_horizontal](images/visual-engine-bar_horizontal.png)

### bar stacked

**Answers:** What share of each week's builds passed, failed or were cancelled?

Family: comparison · Record: yes · Colour vision: pass

![bar_stacked](images/visual-engine-bar_stacked.png)

### boxplot

**Answers:** How widely does build duration vary between pipelines?

Family: distribution · Record: yes · Colour vision: n/a

![boxplot](images/visual-engine-boxplot.png)

### breakeven

**Answers:** How many units must be sold before the product covers its costs?

Family: capacity-economics · Record: yes · Colour vision: pass

![breakeven](images/visual-engine-breakeven.png)

### bubble

**Answers:** Which services combine high error rates with heavy traffic?

Family: relationship · Record: yes · Colour vision: n/a

![bubble](images/visual-engine-bubble.png)

### donut

**Answers:** What fraction of the test suite is unit, integration or end-to-end?

Family: part-to-whole · Record: yes · Colour vision: pass

![donut](images/visual-engine-donut.png)

### fan

**Answers:** By when will the documents be stamped, and how uncertain is that date?

Family: uncertainty · Record: yes · Colour vision: pass

![fan](images/visual-engine-fan.png)

### funnel

**Answers:** Where do visitors drop out between landing and paying?

Family: flow · Record: yes · Colour vision: pass

![funnel](images/visual-engine-funnel.png)

### gantt

**Answers:** Which documentation tasks run in parallel, and what holds up the launch?

Family: schedule · Record: yes · Colour vision: pass

![gantt](images/visual-engine-gantt.png)

### graph

**Answers:** Which services depend on which?

Family: network · Record: yes · Colour vision: n/a

![graph](images/visual-engine-graph.png)

### heatmap

**Answers:** Which days and hours see the most support tickets?

Family: matrix-heat · Record: yes · Colour vision: pass

![heatmap](images/visual-engine-heatmap.png)

### learning curve

**Answers:** Would more training data still improve the validation score, or has the model stopped learning?

Family: uncertainty · Record: yes · Colour vision: pass

![learning_curve](images/visual-engine-learning_curve.png)

### line

**Answers:** How did p95 API latency move over the last six months?

Family: time-series · Record: yes · Colour vision: n/a

![line](images/visual-engine-line.png)

### line step

**Answers:** At which dates did the on-call roster change size?

Family: time-series · Record: yes · Colour vision: n/a

![line_step](images/visual-engine-line_step.png)

### matrix

**Answers:** Which services are covered by which kind of test?

Family: matrix-heat · Record: yes · Colour vision: pass

![matrix](images/visual-engine-matrix.png)

### none

**Answers:** Is a chart warranted for a single number that never changes?

Family: NO_CHART · Record: no · Colour vision: n/a

### pareto

**Answers:** Which few root causes account for most of the open documentation defects?

Family: comparison · Record: yes · Colour vision: pass

![pareto](images/visual-engine-pareto.png)

### pie

**Answers:** Where does the support queue's volume come from?

Family: part-to-whole · Record: yes · Colour vision: pass

![pie](images/visual-engine-pie.png)

### radar

**Answers:** How do the two release trains compare across quality dimensions?

Family: comparison · Record: yes · Colour vision: pass

![radar](images/visual-engine-radar.png)

### sankey

**Answers:** Where do incoming support tickets end up?

Family: flow · Record: yes · Colour vision: pass

![sankey](images/visual-engine-sankey.png)

### saturation

**Answers:** At what offered load does extra traffic stop producing extra throughput?

Family: capacity-economics · Record: yes · Colour vision: pass

![saturation](images/visual-engine-saturation.png)

### scatter

**Answers:** Do larger pull requests take longer to review?

Family: relationship · Record: yes · Colour vision: n/a

![scatter](images/visual-engine-scatter.png)

### scorecard

**Answers:** How many release checks are proven, how many failed, and how many could not be verified?

Family: status · Record: yes · Colour vision: pass

![scorecard](images/visual-engine-scorecard.png)

### sunburst

**Answers:** How is the documentation corpus split by area and type?

Family: hierarchy · Record: yes · Colour vision: pass

![sunburst](images/visual-engine-sunburst.png)

### timeline

**Answers:** When did the major milestones of the migration happen?

Family: time-series · Record: yes · Colour vision: n/a

![timeline](images/visual-engine-timeline.png)

### tornado

**Answers:** Which input moves the effort forecast the most?

Family: variance-sensitivity · Record: yes · Colour vision: pass

![tornado](images/visual-engine-tornado.png)

### tree

**Answers:** How is the platform organised into teams and squads?

Family: hierarchy · Record: yes · Colour vision: n/a

![tree](images/visual-engine-tree.png)

### treemap

**Answers:** Which services hold the most lines of code?

Family: hierarchy · Record: yes · Colour vision: pass

![treemap](images/visual-engine-treemap.png)

### waterfall

**Answers:** How does the effort estimate move from the baseline to the forecast, and which changes drive it?

Family: variance-sensitivity · Record: yes · Colour vision: pass

![waterfall](images/visual-engine-waterfall.png)

## Mermaid diagrams

### classDiagram

**Answers:** How are reports, findings and contracts related?

Family: workflow / sequence / state / architecture · Record: no · Colour vision: n/a

![classDiagram](images/mermaid-engine-classDiagram.png)

### erDiagram

**Answers:** Which entities does an order involve and how are they related?

Family: workflow / sequence / state / architecture · Record: no · Colour vision: n/a

![erDiagram](images/mermaid-engine-erDiagram.png)

### flowchart

**Answers:** How does a change move from an opened pull request to a release?

Family: workflow / sequence / state / architecture · Record: no · Colour vision: n/a

![flowchart](images/mermaid-engine-flowchart.png)

### sequenceDiagram

**Answers:** In what order do the services talk when a user logs in?

Family: workflow / sequence / state / architecture · Record: no · Colour vision: n/a

![sequenceDiagram](images/mermaid-engine-sequenceDiagram.png)

### stateDiagram-v2

**Answers:** Which states can a document pass through between draft and archive?

Family: workflow / sequence / state / architecture · Record: no · Colour vision: n/a

![stateDiagram-v2](images/mermaid-engine-stateDiagram-v2.png)

### xychart-beta

**Answers:** How fast is the number of open defects falling from sprint to sprint?

Family: comparison / time series · Record: no · Colour vision: pass

![xychart-beta](images/mermaid-engine-xychart-beta.png)

## Project census figures

### census-activity

**Answers:** In which months was the documentation last worked on?

Family: time · Record: no · Colour vision: n/a

![census-activity](images/census-census-activity.png)

### census-age-heat

**Answers:** How old are the live documents of each area?

Family: matrix / heat · Record: no · Colour vision: pass

![census-age-heat](images/census-census-age-heat.png)

### census-areas

**Answers:** 

Family: comparison · Record: no · Colour vision: pass

![census-areas](images/census-census-areas.png)

### census-code-explorer

**Answers:** What is inside each package, what does it import, and is it written down anywhere?

Family: hierarchy · Record: no · Colour vision: fail

![census-code-explorer](images/census-census-code-explorer.png)

### census-completeness

**Answers:** Where are the gaps in the documentation system, dimension by dimension?

Family: comparison · Record: no · Colour vision: n/a

![census-completeness](images/census-census-completeness.png)

### census-crossed

**Answers:** How many documents have been taken out of the live project, and how?

Family: comparison · Record: no · Colour vision: n/a

![census-crossed](images/census-census-crossed.png)

### census-docs-explorer

**Answers:** Which parts of the documentation are alive, which have gone quiet, and which are archives?

Family: hierarchy · Record: no · Colour vision: fail

![census-docs-explorer](images/census-census-docs-explorer.png)

### census-flow

**Answers:** Of everything ever written, how much is still alive, how much is archived, how much is gone?

Family: flow · Record: no · Colour vision: pass

![census-flow](images/census-census-flow.png)

### census-growth

**Answers:** Is the documentation growing, and is anything being removed?

Family: workflow / sequence / state / architecture · Record: no · Colour vision: pass

![census-growth](images/census-census-growth.png)

### census-layers

**Answers:** How is the documentation layered, and which layers cite which?

Family: workflow / sequence / state / architecture · Record: no · Colour vision: n/a

![census-layers](images/census-census-layers.png)

### census-model

**Answers:** What does the census treat as a document, a stamp, a link and a mark, and how do they relate?

Family: workflow / sequence / state / architecture · Record: no · Colour vision: n/a

![census-model](images/census-census-model.png)

### census-stamps

**Answers:** Of the documents stamped as a source of truth, how many stamps still hold?

Family: part to whole · Record: no · Colour vision: pass

![census-stamps](images/census-census-stamps.png)

## Module explorer

### explorer

**Answers:** What are the parts of the platform, how large is each, and what does each one call?

Family: hierarchy · Record: no · Colour vision: fail

![explorer](images/explorer-explorer.png)

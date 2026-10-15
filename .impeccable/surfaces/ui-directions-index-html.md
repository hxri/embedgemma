---
version: 1
slug: "ui-directions-index-html"
primary_target: "ui/directions/index.html"
related_targets: []
---

# Surface brief: /directions/ (sentence arithmetic) and its "How it works" view

Scope: the directions page (`ui/directions/`), an Operate surface (type, toggle, read the verdict) that gains a
switchable Read view explaining the pipeline. Extension of an established surface: inherits the light paper
system shared by `/finder/`, `/words/` and `/directions/` (Atkinson, white paper, blue accent, ink outlines,
green verdict), not the Rythmo band world of `/`.

Audience and job: Hari narrating to a room, screen projected; a viewer reading alone afterwards. The job of
the new view: understand where EmbeddingGemma 2 sits in the pipeline (six places), what DiffusionGemma does
(proposes tokens inside the reading only), what NLLB does (writes the expected foreign form), and why the
landing test is the proof while the decoded sentence is a reading.

Confirmed answers: stepper with Play (eight steps, click-through, autoplay); chart labels use the live
sentence, directions, expected form and rank from the Try view, falling back to the roof example; the
decoder's inner loop is shown (DiffusionGemma step, EmbeddingGemma judge, gradient nudge, 24-step counter,
pick of six).

Constraints: vanilla HTML/CSS/JS served by the FastAPI server; Safari is the demo browser; reduced motion
must keep every step readable; no new fonts; the switch must not lose the Try view's state.

## Direction contract

THESIS: one flow chart that is the page, lit one node at a time while a dot carries the point through it;
it refuses the category default of a numbered card grid of "steps" beside a static diagram image.

OWN-WORLD: the paper system already on the page. EmbeddingGemma nodes are the only blue fills, DiffusionGemma
is the one ink-black box, the translator is grey, points are blue dots, the verdict is green. Edges are 2px
ink rules with small arrowheads; inactive nodes fade to 40%, the active node gets a 3px blue ring. Labels are
Atkinson inside the nodes via foreignObject, so live text wraps.

STORY: the viewer sees the sentence become a dot, sees the dot move when directions are added, sees it
compared against the bank and land on the expected form, then sees the separate reading loop where
DiffusionGemma proposes and EmbeddingGemma judges 24 times. They leave knowing EmbeddingGemma appears six
times and is the only model that ever makes or judges a vector.

FIRST VIEWPORT: a two-button switch under the title (Try it / How it works). In the How view: left third is
the step panel (step n of 8, a short title, two to three sentences, Back / Next / Play, legend); right two
thirds is the chart at 960x620 units, top row sentence -> EmbeddingGemma -> point e -> directions, the moved
point v below, the proof column at left (expected form, embed, bank, nearest, verdict) and the reading column
at right (hints, DiffusionGemma + EmbeddingGemma judge loop with a step counter, pick, decoded sentence). The
primary action is Next. Signature interaction: the travelling dot along the active edge and the cycling
judge loop on step 7; one orchestrated intro where edges draw in and nodes fade up on first entry.

FORM: extension of an existing surface; no concept roll (seed: none, local addition per new-work section 3).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict,
DESIGN.md, and every shipping raster carrying its provenance.

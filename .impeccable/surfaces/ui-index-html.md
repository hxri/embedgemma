---
version: 1
slug: "ui-index-html"
primary_target: "ui/index.html"
related_targets: []
---

# Surface brief: ui/index.html (the demo stage)

Scope: the single-page demo stage. Visitor mode: Experience (the take and its sound lead; the interface recedes).

Audience and job: a room watching a projected laptop; a volunteer performs about 10 s in front of the camera; everyone waits for the sound. Action: press the mic. Proof: the sound that plays is the model's real nearest neighbour; the detection sheet shows the scores and both retrieval paths.

Constraints: Safari on the demo Mac (Chrome must work too); model server through a tunnel at localhost:8787; about 1 s per match; ESC-50 clips are 5 s and loop over the take; cosine scores are compressed, so rank and z-score carry the truth. Near-silent takes drop their audio and must say so.

Memorable moment: the hand-written cue crossing the sync bar as the sound starts.

Unresolved: product name (working title "Rythmo", not confirmed by the user).

## Direction contract

THESIS: The matched sound arrives hand-written on a dubbing band that scrolls under the picture and fires the instant its first letter crosses a fixed sync bar. The page refuses the AI-demo arrangement: no record button over a preview, no list of score cards.

OWN-WORLD: A darkened dubbing auditorium. Warm near-black ground; the picture is a projected rectangle with a soft, offset light spill. Beneath it, the band: a paler charcoal strip with sprocket perforations and faint grain, carrying marker-lettered cues (Caveat, self-hosted) stretched horizontally to their real duration. One red-orange sync bar, fixed at the centre, full band height. Five family inks that never change meaning (animals red, nature green, human yellow, home blue, city violet); pure white ink belongs to the playing cue alone, runners-up sit at half strength. UI text in Atkinson Hyperlegible, tabular numerals. Controls are stage objects: a drawn stage mic with a red lamp, a loop counter and timecode, a sheet tab. The detection sheet is ruled paper sliding in from the right. Earlier takes stay on the strip to the left.

STORY: The room sees the live picture and an empty band. Someone steps up and presses the mic; the countdown lands at the bar; ten seconds of action while a pen trace of the mic draws across the band. The band whips back, the model detects, the winner is written across the top line in white and the sound hits as its first letter crosses the bar. Runners-up appear below; tapping one swaps it up and the sound changes at the bar. The sheet shows the numbers when asked.

FIRST VIEWPORT: Full-viewport auditorium. The picture (live camera, then the take) fills the top ~60% of the height as a centred 16:9 rectangle with a thin edge. Beneath, the band spans the full width at ~28% of the height: one large top line, three smaller lines, the sync bar at horizontal centre. The bottom ~12% is the deck: loop number and timecode with play/pause at left, the mic (primary action) centred directly under the bar, the sheet tab at right. Nothing else on screen.

FORM: The rythmo band of dubbing stages, candidate 6 of 7 on the resonance-ordered list; seed key e79f028f. Signature interaction: the sync bar is the only place a sound starts or changes. Motion grammar: the band moves only with the video clock (plus one scripted rewind-and-write before the reveal); everything else is still. Raised lines: takes stay on the strip (earth tower); one active edge (cloud quarry); white ink reserved for the playing cue (CRT arcade); inks never change meaning (football kit).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

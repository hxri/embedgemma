---
name: Rythmo (working title, unconfirmed)
description: A dubbing band scrolling under a projected picture; the matched sound is hand-written on the band and fires at a fixed red sync bar.
colors:
  ground: "#121110"
  ground-deep: "#0a0908"
  strip: "#1d1c19"
  strip-hole: "#0b0b0a"
  strip-edge: "#2b2a26"
  picture-edge: "#2a2a2e"
  hardware-edge: "#2f2f33"
  hardware-edge-hover: "#55545b"
  text: "#f4efe6"
  text-dim: "#a69f92"
  white: "#ffffff"
  bar: "#ff5a36"
  paper: "#efe8d8"
  paper-rule: "rgba(29, 26, 22, 0.14)"
  paper-pressed: "#e3dac6"
  ink-paper: "#1d1a16"
  ink-paper-dim: "#6b6258"
  ink-animals: "#e8503f"
  ink-nature: "#52c472"
  ink-human: "#f4c743"
  ink-home: "#4b97f5"
  ink-city: "#ba8cf3"
typography:
  display:
    fontFamily: "Caveat, Bradley Hand, cursive"
    fontSize: "33cqh"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.02em"
  headline:
    fontFamily: "Caveat, Bradley Hand, cursive"
    fontSize: "11.5cqh"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.02em"
  hand-note:
    fontFamily: "Caveat, Bradley Hand, cursive"
    fontSize: "clamp(22px, 3.2vw, 40px)"
    fontWeight: 400
    lineHeight: 1.4
  title:
    fontFamily: "Atkinson, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.4
  timecode:
    fontFamily: "Atkinson, system-ui, sans-serif"
    fontSize: "clamp(18px, 2vw, 28px)"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "0.02em"
    fontFeature: "tabular-nums"
  body:
    fontFamily: "Atkinson, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.4
  body-sheet:
    fontFamily: "Atkinson, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: "28px"
    fontFeature: "tabular-nums"
  label:
    fontFamily: "Atkinson, system-ui, sans-serif"
    fontSize: "clamp(13px, 1.2vw, 16px)"
    fontWeight: 400
    lineHeight: 1.4
    fontFeature: "tabular-nums"
rounded:
  edge: "3px"
  sm: "6px"
  md: "8px"
  lg: "14px"
  round: "50%"
spacing:
  xs: "4px"
  sm: "8px"
  md: "14px"
  lg: "18px"
  xl: "24px"
  rule: "28px"
  band-h: "clamp(170px, 27vh, 300px)"
  deck-h: "clamp(84px, 12vh, 120px)"
components:
  transport:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    rounded: "{rounded.round}"
    size: "44px"
  mic:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: "6px 18px 4px"
  mic-hover:
    backgroundColor: "rgba(244, 239, 230, 0.06)"
  sheet-tab:
    backgroundColor: "transparent"
    textColor: "{colors.text-dim}"
    rounded: "{rounded.md}"
    padding: "10px 14px"
  sheet-tab-hover:
    textColor: "{colors.text}"
  sheet-button:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink-paper}"
    rounded: "{rounded.sm}"
    padding: "6px 12px"
  sheet-button-hover:
    backgroundColor: "{colors.paper-pressed}"
  sheet:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink-paper}"
    padding: "20px 24px 24px 56px"
    width: "min(440px, 100vw)"
  picture-note:
    backgroundColor: "rgba(10, 10, 11, 0.7)"
    textColor: "{colors.text}"
    rounded: "{rounded.edge}"
    padding: "20px 28px"
    typography: "{typography.body}"
---

# Design System: Rythmo (working title)

The product name "Rythmo" is a builder's placeholder, not confirmed by the user. Everything else in this file is read from the shipped `ui/` artifact (`style.css`, `index.html`, `app.js`) after the finish review's ship verdict.

## Overview

**Creative North Star: "The Dubbing Band"**

A darkened dubbing auditorium. The screen is three stacked stage objects: a projected picture floating in a warm near-black room with a soft amber light spill behind it, a charcoal rythmo band with sprocket holes scrolling underneath it, and a hardware deck along the bottom. Nothing on screen is a web control dressed up; the mic is a drawn stage mic with a red lamp, the counter is a timecode readout, the inspector is a sheet of ruled paper that slides in from the right.

The band is the whole idea. Time runs horizontally at a fixed pixel rate; the matched sound arrives as marker lettering in Caveat, stretched to its real five-second duration, and the sound starts the instant the first letter crosses the one red-orange sync bar fixed at the band's centre. Density is low by design: the room watches from several metres, so there is one large line, three smaller lines, a bar, and a deck, and nothing else.

Motion belongs to the video clock. The band moves only when the take plays (plus one scripted rewind-and-write before each reveal); every other element is still, and state is shown by ink, lamp, and bar flash rather than by things moving around.

**Key Characteristics:**
- Warm near-black ground, paler charcoal strip, cream paper sheet: three materials, no greys for their own sake.
- One accent (red-orange bar) that only ever means "sync": the bar itself, the recording lamp, focus rings, form accent colour, the sheet's margin line.
- Five family inks with fixed meanings; white reserved for the playing cue.
- Two faces: Caveat for anything written on the band, Atkinson Hyperlegible with tabular numerals for everything the deck and sheet say.
- Container-relative band type (`cqh`) so the lettering scales with the band, not the viewport.
- Flat surfaces; depth comes from the picture's projector shadow, the sheet's edge shadow, and the band's cut sprocket holes.

## Colors

A warm, low-key auditorium palette: near-blacks tinted toward brown, bone-coloured text, one hot sync accent, and a cream paper for the sheet.

### Primary
- **Sync Bar** (`bar`): the fixed sync bar, its end arrows and flash halo, the recording lamp when lit, keyboard focus rings on the dark stage, text selection, `accent-color` of the sheet's radios, checkbox and slider, and the error state of the band note. It is the one hot colour on the stage and it only ever signals "the sound starts or changes here" or "recording".

### Secondary (family inks)
Five inks, assigned by sound family through `data-family` and the `--ink` custom property, used identically on the band's runner-up lines and the sheet's class dots. They never change meaning.
- **Animals** (`ink-animals`): a slightly warmer, duller red than the bar so the two do not read as the same signal.
- **Nature** (`ink-nature`): leaf green.
- **Human** (`ink-human`): marker yellow.
- **Home** (`ink-home`): sky blue.
- **City** (`ink-city`): violet.
- **White** (`white`): not a family; the playing cue (`.line.l0`) overrides its family ink with pure white. Runners-up keep their family ink at 72% opacity.

### Neutral (stage)
- **Ground** (`ground`): body background and the centre of the stage's radial gradient; a warm near-black.
- **Ground Deep** (`ground-deep`): the gradient's outer edge, the deck background, and the dark half of selection.
- **Strip** (`strip`): the band surface, under a tiled fractal-noise grain at 5.5% alpha.
- **Strip Hole** (`strip-hole`): the sprocket perforations, drawn as a repeating radial gradient.
- **Strip Edge** (`strip-edge`): the band's 1px top and bottom borders.
- **Picture Edge** (`picture-edge`): the 1px border around the projected picture and the picture note (`#2a2a2e`, a literal in the stylesheet, not a variable).
- **Hardware Edge / Hardware Edge Hover** (`hardware-edge`, `hardware-edge-hover`): the 1px rings on the transport button and sheet tab, and the tab's hover/expanded ring (literals in the stylesheet). The drawn mic's body uses a related cool-grey trio (`#35343a` fill, `#6b6a72` stroke, `#9a98a2` grille and arc).
- **Text** (`text`): bone-white UI text on the stage.
- **Text Dim** (`text-dim`): loop labels, mic label, take marks, countdown numerals, band notes, idle sheet tab.

### Neutral (paper)
- **Paper** (`paper`): the detection sheet's surface, with a 28px repeating horizontal rule in `paper-rule` and a vertical red margin line at 44px (the animals ink at 55% alpha).
- **Paper Pressed** (`paper-pressed`): hover fill of the sheet's outlined buttons.
- **Ink Paper / Ink Paper Dim** (`ink-paper`, `ink-paper-dim`): sheet text, and the sheet's secondary text (query line, timings, loop number, slider output). Focus rings and selection on the sheet switch to `ink-paper`.

### Named Rules
**The One Bar Rule.** Red-orange means sync or recording and nothing else. Do not use `bar` for emphasis, links, headings or decoration; on the sheet it appears only as the form `accent-color` and the margin line.

**The Fixed Ink Rule.** A family ink is bound to its family in every surface (band lines, sheet dots) and never reassigned for hierarchy, mood or state.

**The White Cue Rule.** Pure white is the playing cue's ink alone. Nothing else on the stage is `#ffffff`.

## Typography

**Display Font:** Caveat (self-hosted variable 400-700, with Bradley Hand, cursive fallback)
**Body Font:** Atkinson Hyperlegible (self-hosted 400, 700, 400 italic, with system-ui, sans-serif fallback)

**Character:** Everything written on the band is marker handwriting; everything the hardware and the sheet say is a plain, highly legible sans with tabular numerals. The two never mix on one element: Caveat is reserved for band content (cues, take marks, countdown numerals, band notes) and never appears on the deck or the sheet.

### Hierarchy
- **Display** (Caveat 600, `33cqh` of the band, line-height 1, 0.02em tracking): the playing cue on the band's top line, in white. Its text is stretched horizontally with `scaleX` from 1x up to 2.4x to fill the cue's real duration, with up to 0.12em additional tracking before the stretch limit; the remainder of the cue is held as a 1px rule in the cue's ink at 35% opacity, closed by a 1px end tick.
- **Headline** (Caveat 600, `11.5cqh`, line-height 1): the three runner-up lines, in family ink at 72% opacity; 100% on hover and focus.
- **Hand note** (Caveat 400, `clamp(22px, 3.2vw, 40px)`): status notes on the band ("detecting", "silent take, matched on frames only"), sitting left of the bar while idle and shrinking to `clamp(16px, 1.6vw, 22px)` at the bottom-left while a take plays. Take marks use `clamp(14px, 1.3vw, 20px)`; the countdown numerals use Caveat 700 at `34cqh` and 45% opacity.
- **Title** (Atkinson 700, 22px): the sheet heading.
- **Timecode** (Atkinson 700, `clamp(18px, 2vw, 28px)`, tabular, 0.02em): the deck's `mm:ss.d` readout.
- **Body** (Atkinson 400, 16px, line-height 1.4): base UI text; the picture note uses `clamp(16px, 2vw, 22px)`, max 34ch, centred.
- **Body, sheet** (Atkinson 400, 16px, line-height 28px, tabular): all sheet text sits on a 28px baseline so it lands on the paper's ruled lines; the query line is the italic cut. Bold 700 carries legends, column heads, the playing row's name and the top rows' z-scores.
- **Label** (Atkinson 400, `clamp(13px, 1.2vw, 16px)`, tabular): the mic label and the loop label (`clamp(14px, 1.3vw, 18px)`).

### Named Rules
**The Band Is Caveat Rule.** Caveat is for things written on the band. The deck, the picture note and the sheet are Atkinson only.

**The Ruled Baseline Rule.** On the sheet, every line of text is 28px tall so it sits on the paper's rules; do not introduce line-heights that break the rule pitch.

**The Band Scales With Itself Rule.** Band lettering is sized in `cqh` against the band container, never in `px`, `rem` or viewport units.

## Layout

Full-viewport stage, `overflow: hidden`, with no scrolling: a CSS grid of three rows, `1fr` picture / `--band-h` (`clamp(170px, 27vh, 300px)`) band / `--deck-h` (`clamp(84px, 12vh, 120px)`) deck. The picture row is a size container; the 16:9 picture is `min(100%, 168cqh)` wide, centred, with padding `clamp(12px, 2.4vh, 28px)` top and `clamp(12px, 3vw, 40px)` sides. The band is also a size container so its type and the sprocket rows resolve against its own height.

The band's strip is positioned at the band's horizontal centre and translated left by `bandT * PPS`, where `PPS` is `max(90, bandWidth / 8.5)` pixels per second: the band always shows about 8.5 s of strip, and the bar at 50% marks "now". Takes are laid out left to right on the strip at their origin time, 10 s long with a 2.6 s gap; countdown numerals sit at -3, -2, -1 s before each take; cues repeat every 5 s (the clip length) with an 18px gap. Earlier takes remain on the strip at 38% opacity. Four lines stack inside a take: the top line from 9% to 53% of band height, the three runners at 55%, 68% and 81%, each 12-13% tall.

The deck is a three-column grid `1fr auto 1fr` so the mic sits exactly under the bar; transport and counter at left with a 14px gap, the sheet tab at right, side padding `clamp(14px, 3vw, 40px)`. The sheet is a fixed right panel `min(440px, 100vw)` wide, padded `20px 24px 24px 56px` so text clears the margin line.

Spacing uses small fixed steps: 4px (sheet option gaps), 6-8px (control gaps, sheet rows), 10-14px (deck and sheet-tab padding, button gaps), 16-18px (form blocks, note offsets), 20-28px (picture-note and sheet padding). The 28px rule pitch is the sheet's vertical unit.

At `max-width: 720px` the stage stops filling the viewport: the picture row becomes `(100vw - 20px) * 9 / 16 + 18px`, the band fixes at 200px and the deck at 92px, the grid aligns to the top, the picture goes full width with 10px padding, the deck becomes `auto 1fr auto` with 12px padding, the loop label hides, the mic padding tightens to `4px 10px 2px`, the sheet's left padding drops to 48px and the slider to 110px.

## Elevation & Depth

Flat surfaces with three structural exceptions, all of them physical. The picture is a projected rectangle: a soft two-layer drop shadow lifts it off the ground, and a blurred amber ellipse behind it (`.picture::before`, 48px blur, 16% alpha) is the projector's light spill. The sheet is a sheet of paper over the stage: a long, soft left-edge shadow. The band is cut, not lifted: its sprocket holes are drawn into the strip with the hole colour, and its grain is a tiled SVG noise, so it reads as material rather than as a layer. Everything on the deck is flush with the deck; buttons are outlined rings or borderless, never raised.

### Shadow Vocabulary
- **Projector lift** (`box-shadow: 0 24px 70px -20px rgba(0, 0, 0, 0.85), 0 6px 18px -8px rgba(0, 0, 0, 0.7)`): the picture at rest.
- **Recording ring** (`box-shadow: 0 0 0 3px var(--bar), 0 24px 70px -20px rgba(0, 0, 0, 0.85)`): the live picture while recording; the ring replaces the near shadow.
- **Sheet edge** (`box-shadow: -18px 0 50px -16px rgba(0, 0, 0, 0.8)`): the open sheet over the stage.
- **Bar flash** (`0 0 0 2px var(--bar), 0 0 28px 8px rgba(255, 90, 54, 0.75)` decaying to none over 0.5s ease-out): fired every time a sound starts or changes at the bar.
- **Lamp glow** (`0 0 10px 2px rgba(255, 90, 54, 0.8)`): the mic lamp when lit; at rest it is a dark red disc with an inset 1px ring.

### Named Rules
**The Physical Shadow Rule.** A shadow exists only where a stage object would cast one: the projected picture, the paper sheet, the lit lamp, the flashing bar. No hover shadows, no card shadows, no ambient glows on controls.

**The Flash At The Bar Rule.** The bar flash is the feedback for a sound starting or changing. Do not add a second confirmation anywhere else.

## Shapes

Hardware is round; paper is square-ish; the picture and band are hard-edged. Circles: the 44px transport button, the 10px lamp, the 10px family dots on the sheet. The mic's hover pad has a 14px radius; the sheet tab 8px; sheet buttons and the sheet close 6px; the picture and picture note a bare 3px edge; the band, bar and sheet have no radius at all. Borders are 1px hairlines in the hardware or picture edge colour, or 1px solid `ink-paper` on sheet buttons. The band is clipped (`overflow: hidden`) and the cue lettering is revealed with `clip-path: inset()` sweeping left to right. The bar is a 3px vertical rule with 7px-wide, 9px-tall solid triangles at both ends. The mic trace is a symmetric polygon about the band's mid-line, amplitude 16% of band height, filled at 6% and stroked at 16% bone-white.

## Components

### Band (signature)
A charcoal strip with grain, 16px sprocket rows top and bottom (11x8px holes on a 24px pitch), 1px edge borders, and a fixed 3px sync bar at centre. Content lives on a `.strip` that translates with the video clock. Cues (`.cue`) are Caveat 600 at line-height 1, white-space nowrap, stretched with `scaleX` to their duration, revealed by `clip-path` over 0.7s `--ease-out` with a per-cue delay of `line * 90ms + repeat * 140ms`. Lines (`.line`) are buttons; promoting a runner-up swaps its class to `.l0`, and `top`, `height` and `font-size` tween over 0.45s `--ease-out` so the lettering visibly moves up into white. Past takes sit at 38% opacity; take marks are a 1px dashed bone-white rule at 35% with a small Caveat label. The band note is Caveat in `text-dim`, red-orange when it reports an error.

### Sync bar
3px `bar` rule, full band height, arrow caps at both ends, `z-index` above the strip. `.flash` plays `barflash` 0.5s ease-out. The bar never moves.

### Transport (play/pause)
- **Shape:** circle (44px, `rounded.round`), 1px `hardware-edge` ring, transparent fill.
- **Icon:** inline 20px SVG filled with `currentColor`; play and pause swap by `data-playing`.
- **Disabled:** 35% opacity, default cursor. No hover treatment.

### Mic (primary action)
- **Shape:** borderless pad, 14px radius, padding `6px 18px 4px`; a 10px lamp sits centred at the top edge.
- **Glyph:** inline drawn SVG, `clamp(44px, 7vh, 62px)` tall, cool-grey body and grille.
- **Label:** Atkinson label size in `text-dim`, tabular ("Record 10 s", "Record again").
- **Hover / Active:** 6% bone-white fill and `translateY(-1px)` over 0.2s `--ease-out`; active `translateY(1px)`.
- **States:** `countdown` blinks the lamp (1s, `steps(2, start)`); `recording` holds the lamp lit with its glow and rings the live picture in `bar`. Disabled: 60% opacity.

### Sheet tab
- **Shape:** 8px radius, 1px `hardware-edge` ring, padding `10px 14px`, 8px gap between an 18px stroked SVG and the word "Sheet".
- **States:** `text-dim` at rest; `text` with `hardware-edge-hover` ring on hover and while `aria-expanded="true"`, over 0.2s.

### Detection sheet
- **Surface:** fixed right panel on `paper` with a 28px horizontal rule in `paper-rule` and a 1px red margin line at 44px; text in `ink-paper`; thin `#b8ad98` scrollbar.
- **Motion:** slides from `translateX(104%)` to 0 over 0.38s `--ease-out`.
- **Head:** 22px bold title, `ink-paper-dim` loop number, 32px close button (6px radius, 8% ink hover fill).
- **Form:** legends bold; radios, checkbox and slider use `accent-color: bar`; 16px native controls; 140px slider with tabular output in `ink-paper-dim`.
- **Buttons:** `paper` fill, 1px `ink-paper` border, 6px radius, padding `6px 12px`; hover `paper-pressed`; disabled 40%.
- **Class table:** collapsed borders, 28px rows, tabular numerals, numeric columns right-aligned at 52px, the sound name truncating with an ellipsis; 10px family dot before the name; the playing row's name bold, the top rows' z bold; row hover 6% ink fill; rows are clickable and pull that class onto the band.
- **Selection / focus:** on the sheet, selection inverts to `ink-paper` on `paper` and focus rings switch to `ink-paper`.

### Picture note
A centred message box over the picture (no camera, permission denied): 70% `ground-deep` fill, 1px `picture-edge`, 3px radius, padding `20px 28px`, max 34ch, `clamp(16px, 2vw, 22px)` Atkinson.

### Focus
`:focus-visible` is a 3px `bar` outline offset 3px on the stage (inset 4px on the picture toggle), `ink-paper` on the sheet.

### Motion grammar
One easing, `--ease-out: cubic-bezier(0.16, 1, 0.3, 1)`, for every spatial transition (cue reveal 0.7s, line swap 0.45s, sheet slide 0.38s, mic hover 0.2s); plain `ease` for opacity and colour (picture crossfade 0.35s, band note 0.25s, lamp 0.2s, sheet button fill 0.15s). The strip itself is never CSS-transitioned: it is positioned each frame from the take's `currentTime`. The one scripted move is the reveal: a 750ms expo-eased rewind to 1.2 s before the take (with a 3px motion blur on the strip), a 650ms pause while the cues are written, then a linear 1.2 s pre-roll into the bar at which the sound starts. Under `prefers-reduced-motion: reduce` the rewind, pre-roll, whip blur, cue reveal, line tween, sheet slide, picture crossfade, mic lift, bar flash animation and lamp blink are all removed; the band still jumps to position, the cues appear, and the sound still starts at the bar. `body.shot` (screenshot mode) disables the sheet, picture and line transitions only.

## Do's and Don'ts

### Do:
- **Do** write anything that goes on the band in Caveat 600, sized in `cqh`, stretched to its duration with `scaleX` (max 2.4x) and finished with a rule to the cue's end.
- **Do** keep the sync bar fixed at the band's horizontal centre and start or change sounds only there, with the bar flash as the confirmation.
- **Do** bind colour to family through `data-family` and `--ink`, and render the playing cue in white.
- **Do** set sheet text on the 28px rule pitch and use tabular numerals for every number on the deck and the sheet.
- **Do** build controls as stage objects: outlined circles and rings on the deck, outlined paper buttons on the sheet, inline SVG drawn with `currentColor` or the mic's grey trio.
- **Do** respect `prefers-reduced-motion` by removing travel and reveal animation while keeping the reveal itself (band in place, cues present, sound at the bar).

### Don't:
- **Don't** use `bar` for anything but sync, recording, focus and the sheet's form accent.
- **Don't** reassign a family ink, use white for a runner-up, or tint the top line by family.
- **Don't** move the strip with CSS transitions or on any clock other than the take's `currentTime` (plus the scripted rewind and pre-roll).
- **Don't** put Caveat on the deck or the sheet, or Atkinson on the band.
- **Don't** add shadows to controls, hover glows, or lifted cards; the only shadows are the picture's, the sheet's, the lamp's and the bar flash.
- **Don't** size band type in `px`, `rem` or viewport units, or let the band row grow beyond its clamp.

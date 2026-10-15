# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Static HTML, CSS and JS with no build step (user's choice). Served by the FastAPI model server on
big-machine (`server.py`, port 8787) and reached from the MacBook through an SSH tunnel at
`http://localhost:8787`. The browser on the demo machine is Safari (the only browser installed), so
recording uses Safari's MediaRecorder (`video/mp4`). Chrome must also work (webm uploads are transcoded).

## Users

Hari, demoing to a room: the laptop is projected or screen-shared, 5 to 30 people watching from a
distance. A volunteer (often Hari) performs a short action in front of the MacBook camera. The
audience sees the screen, not the laptop. Secondary: Hari alone, exploring what the model does.

## Product Purpose

A fun live demo of EmbeddingGemma 2's single multimodal embedding space. Record ~10 s of someone doing
something, embed the clip, find the closest sound effect in a library, play it over the video.
Success: the reveal lands in the room (a laugh, a "whoa"), and people leave understanding that one
small model placed video, audio and text in the same space and picked the sound by nearness.
Not production; no accounts, no persistence beyond the session.

## Positioning

One 740M-parameter embedding model does the whole job: the clip (frames + its audio), 2000 library
sounds (audio) and 50 class captions (text) are all embedded by the same model into one 768-d space,
and the nearest sound wins. No captioner, no separate audio model, no LLM. Everything shown is a real
model output; nothing is staged.

## Operating Context

- Capture: MacBook Air camera and microphone, in the browser, 10 s, with a countdown.
- Inference: big-machine GPU 0, model kept loaded; a match returns in about 1 s (transcode 0.3 s,
  embed 0.5 s). Network: Tailscale over the box's WiFi, which occasionally drops.
- Library: ESC-50, 2000 clips of 5 s, 50 classes in 5 families (animals, nature, human, home, city).
  Clips loop to cover the 10 s video. License CC BY-NC (fine for a demo).
- Vocabulary: "sound" (a library clip), "class" (one of 50 named sounds), "family" (one of 5 groups),
  "match" (the retrieval result), "paths" (visual path = frames vs captions; audio path = clip audio
  vs library audio).

## Capabilities and Constraints

- Query modes: frames + audio interleaved (default), frames only, audio only. A near-silent clip
  (mean level below -42 dBFS) automatically drops its audio and uses frames only; the UI should say so.
- Scoring modes: against library audio embeddings, against class-caption text embeddings, or a weighted
  blend (alpha). Results: top-k clips and all 50 classes with score, z-score, and both path scores.
- Cosine scores are compressed (roughly 0.6 to 0.75). Rankings and z-scores are meaningful; raw values
  are not impressive and must not be dressed up as percentages or confidences.
- A muxed mp4 (video + chosen sound, optionally mixed with the original audio) can be produced on
  request for download.
- API: `GET /api/health`, `GET /api/classes`, `POST /api/match` (multipart video + form fields),
  `POST /api/mux`. Media at `/media/<id>.mp4`, sounds at `/sfx/<clip>.wav`.
- Undecided: product name. Working title "Rythmo" (after the rythmo band of dubbing stages, the
  chosen visual world) is an assumption by the builder, not confirmed by the user.

## Evidence on Hand

Real: the model, the index, the ESC-50 clips and their class names, per-match timings and scores.
Absent and must not be fabricated: benchmark claims beyond Google's published numbers, user quotes,
accuracy percentages for this demo.

## Product Principles

- The reveal is the product. Everything before it builds one beat of tension; everything after it
  gets out of the way of the video and the sound.
- The model is the star. The interface explains the mechanism (one space, nearest sound) without
  claiming more than it does.
- Truth on demand. The numbers and both retrieval paths are one gesture away, never in the way.
- Built for the back of the room. Type, motion and state changes must read from several metres.
- Honest failure. A silent clip, a lost tunnel, or a denied camera says what happened and what to do.

## Accessibility & Inclusion

Keyboard operable (record, choose sound, play, open inspector). Reduced-motion preference respected
(the reveal still happens, without the large motion). Projected contrast: text and controls hold up
on a washed-out projector.

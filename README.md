# embedgemma: video -> sound effect, with EmbeddingGemma 2

Record a ~10 s clip of someone doing something, embed it with EmbeddingGemma 2
(`google/embeddinggemma-2`, natively multimodal, one 768-d space for text / image /
video / audio), retrieve the closest sound effect from ESC-50, mux it onto the video, play it.
Everything model-side runs on big-machine GPU 0; the Mac records and plays.

## Run the demo UI (Rythmo)

```bash
./ui.sh            # Tailscale up, SSH tunnel to localhost:8787, model server on GPU 0, opens Safari
./ui.sh stop       # drop the tunnel (the server keeps running in tmux "eg-server" on the box)
./ui.sh restart    # restart the server after editing server.py / engine.py
```

Then in Safari: allow the camera and microphone once. Press the mic (or Space / R), do something
for ten seconds, and watch the band. Keys: 1 to 4 swap a line onto the top (plays it), S opens the
detection sheet, Space pauses. Clicking the picture also pauses. Rows in the sheet pull any of the
50 sounds onto the band; "Download the dub" renders an mp4 with the chosen sound.

The UI is `ui/` (index.html, style.css, app.js, core.js, self-hosted fonts). Edit locally, then
`./bscp -q -r ui bm:research/embedgemma/` to push; the server serves it statically. `./shot.sh`
renders it in headless Chrome on the box into `.impeccable/review/` (desktop, mobile, and the
MacBook viewport); `?shot=result` shows a stored real result without a camera.

## The other two pages

- `/say/`: speak a full sentence in any language, get the matching clip out of 1000 (MSR-VTT test set),
  no speech recognition; typed queries too. Index built by `build_vindex.py` into `vindex/` on the box.
  Measured: typed caption R@1 52% over 1000 clips; spoken English (synthetic voice) R@1 47%, Hindi 21%,
  Tamil 3%. Short one-word queries do not work; say a sentence.
- `/steer/`: pick a clip, a sentence or a 6 s camera take, slide along five directions in the embedding
  space, see the nearest real clip, sound and captions follow, then let DiffusionGemma write the sentence
  that lives at that point (`guided.py`: gradient classifier guidance through EmbeddingGemma's input
  embeddings, no training). Directions are chosen empirically by `pick_dirs.py` (writes
  `vindex/directions.json` and the attribute-augmented caption bank `vindex/bank_aug.npz`). The decode
  service is `steer_server.py` on port 8788; `ui.sh` starts it.

- `/finder/`: the zero-shot SFX finder. Drop a frame (image or video file) or click a gallery photo; the
  three closest sound effects come back and the first plays. 130 curated Wikimedia Commons photos
  (`build_gallery.py`, up to 3 per ESC-50 class, kept only if the model recognises the class) so the
  demo stays in distribution; route is frame to class caption to sound (96.9% top-1 on the curated set;
  frame straight to audio only 23.8%).
- `/words/`: the words codec. Pick a photo, a sound, a sentence, any mix, or drop a file; the fused point
  is written back as up to eight vocabulary words chosen so the model reads them to the same point
  (`words.py`: codebook of all 262,144 single-token embeddings in `mp/codebook.npy`, greedy forward
  selection then backward elimination, 0.1 to 0.5 s, no training). Proof panel: what the point finds vs
  what the words find over the 1000 clips and 2000 sounds; a box to type the words back. English mode
  restricts to common dictionary words (`mp/english.txt`); "any" mode allows every token in every script.
  Three clickable examples at the top. Background: `mp/e1..e7` experiments showed EmbeddingGemma cannot
  read its own vectors zero-shot (R@1 51.6 -> 3.3); a 2.5 min adapter makes single-vector round trips
  lossless and 6 min of LoRA brings multi-vector fusion to parity with averaging, never above it.
- `/directions/`: sentence arithmetic. Type a sentence, toggle directions (not, past tense, question,
  man>woman, woman>man, at night, in slow motion, or a language), slide the push; the server adds the
  fitted directions to the sentence's embedding (`directions.py`, directions from `mp/directions_text.npy`)
  and proves the landing: among the 26,939-sentence bank (`build_variant_bank.py`: captions, their
  rule-written variants from `variants.py`, translated captions) plus the typed sentence's own rule-written
  or NLLB-translated form, is the changed form now rank 1? "Write the sentence" sends the point to the
  decode service with the five nearest bank sentences as hints. API: `GET /api/dir/ops`,
  `POST /api/dir/move`, `POST /api/dir/decode` (JSON: text, ops, lang, strength). A "How it works"
  switch (`?view=how` or `#how`) shows an eight-step animated flow chart of the pipeline, labelled with
  the live sentence, directions, expected form and rank; EmbeddingGemma nodes are the blue ones.

## Command-line loop

```bash
./demo.sh                                  # record 10 s (camera + mic) -> match -> play
./demo.sh clips/some_clip.mp4              # re-run on an existing clip
./demo.sh clips/some_clip.mp4 --query video --mode text   # pass-through to match.py
```

`match.py` options (run on the box, `python match.py in/clip.mp4 ...`):

| flag | values | meaning |
|---|---|---|
| `--query` | `both` (default), `video`, `audio` | what to embed from the clip: frames + its audio track interleaved, frames only, audio only. In `both`, audio is dropped only when it is quiet on average (below -42 dB) and has no sharp peak (above -20 dB) |
| `--mode` | `both` (default), `audio`, `text` | score against library clips' audio embeddings, their class-caption text embeddings, or `alpha`-weighted both |
| `--alpha` | 0..1 | weight on the audio score in `--mode both` |
| `--mix` | | keep the clip's original audio under the sound effect |
| `--fps`, `--max-frames` | | video sampling (default 3 fps, up to 32 frames) |

Scoring is two-path late fusion. The take's frames (3 fps, pooled by the model into one vector) are
scored against the 50 class captions (the visual path); the take's audio, reduced to the loud moments
only (event gating, so ten seconds of room tone around three claps embeds as claps, not hiss), is
scored against all 2000 library clips (the audio path). Each path is z-scored over the library and the
two are blended with `alpha`. Interleaving frames and audio into one embedding was tried first and
dropped: ~4000 frame tokens swamp ~250 audio tokens in the mean pool, so the sound of the take barely
counted. Cosine scores from this model are compressed (~0.6-0.75); rankings and z matter, not raw values.
ESC-50 has no finger-snap class; a snap lands near mouse click, clapping or drinking.

## Files

- `record.sh` ffmpeg avfoundation capture (device 0 camera, device 0 mic), 1280x720 h264 + aac
- `demo.sh` record -> `bscp` upload -> `match.py` on GPU 0 -> download -> `ffplay`
- `bscp` scp over the Tailscale SOCKS proxy; host alias `bm:` (use paths relative to remote home, not `~`)
- `build_index.py` builds `index/` on the box: ESC-50 (2000 x 5 s, 50 classes) as 16 kHz mono wav,
  audio embeddings for every clip, text embedding per class from `captions.py`. `--relabel` recomputes text only.
- `captions.py` caption-style phrasing per class ("a person clapping their hands"), which matches
  the model's video<->caption training far better than "the sound of clapping" did.
- `server.py` FastAPI model server (keeps EmbeddingGemma 2 loaded): `GET /api/health`, `GET /api/classes`,
  `POST /api/match` (multipart video + query/mode/alpha/k), `POST /api/mux`; serves `ui/`, `/sfx/`, `/media/`
- `engine.py` the retrieval core shared by `server.py` and `match.py`
- `words.py` the vector-to-words codec behind `/api/words`, `/api/words/read`, `/api/words/picks`
- `mp/` multi-pass embedding experiments (`build_codebook.py`, `e1_selfpass.py` .. `e7_fidelity.py`,
  `fusion_model.py`, checkpoints `adapter.pt`, `fusion_lora0.pt`, `fusion_lora8.pt`, logs) and the
  text-direction experiments (`e8_directions.py` builds `mp/directions_text.npy` from minimal pairs:
  negation, past tense, question, gender, "at night", "in slow motion", 13 languages; `e10_compose.py`
  composition / transfer / pairs-needed; `e9_decode.py`, `e11_decode2.py` read perturbed points back
  through the decode service, which now accepts caller-supplied `hint_texts`)
- `ui.sh`, `shot.sh` Mac-side launcher and screenshot helper
- `setup_box.sh` one-time conda env `embedgemma` (py3.12, torch 2.14 cu130, transformers 5.19,
  sentence-transformers 6.1, torchcodec 0.17)

## On the box

```
~/research/embedgemma/{build_index.py,match.py,captions.py,index/,in/}
conda activate embedgemma; CUDA_VISIBLE_DEVICES=0
```

ESC-50 is CC BY-NC (fine for a demo). Model is Apache 2.0.

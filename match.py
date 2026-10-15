#!/usr/bin/env python
"""CLI: embed a clip with EmbeddingGemma 2, retrieve the best sound effect, mux it onto the video.
See engine.py for the logic; the web server (server.py) uses the same Engine."""
import argparse
import time

from engine import Engine, mux


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--index", default="index")
    ap.add_argument("--query", choices=["video", "audio", "both"], default="both",
                    help="frames only, the clip's audio only, or both interleaved (default; falls back to video)")
    ap.add_argument("--mode", choices=["audio", "text", "both"], default="both",
                    help="score against clip audio embeddings, class-caption text embeddings, or alpha-weighted both")
    ap.add_argument("--alpha", type=float, default=0.5)
    ap.add_argument("--audio-gate-db", type=float, default=-42.0, help="drop the clip's audio below this mean level...")
    ap.add_argument("--audio-peak-db", type=float, default=-28.0, help="...unless it peaks above this (a snap, a knock)")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--fps", type=float, default=3.0)
    ap.add_argument("--max-frames", type=int, default=32)
    ap.add_argument("--mix", action="store_true", help="keep the clip's original audio under the sound effect")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-mux", action="store_true")
    args = ap.parse_args()

    t = time.time()
    e = Engine(args.index)
    r = e.match(args.video, query=args.query, mode=args.mode, alpha=args.alpha, k=args.k, fps=args.fps,
                max_frames=args.max_frames, gate_db=args.audio_gate_db, peak_db=args.audio_peak_db)
    q = r["query"]
    if q["requested"] != q["used"]:
        why = "no audio track" if not q["has_audio"] else f"audio mean {q['mean_db']:.1f} dB, peak {q['peak_db']:.1f} dB is room tone"
        print(f"!! {why} -> using --query {q['used']}")
    print(f"\nmodel load {e.load_s:.1f}s | embed {q['embed_s']:.1f}s | query={q['used']} | mode={args.mode}")
    print("\ntext-only  top classes :", ", ".join(f"{d['class']} ({d['score']:.3f})" for d in r["paths"]["text"]))
    print("audio-only top classes :", ", ".join(f"{d['class']} ({d['score']:.3f})" for d in r["paths"]["audio"]))
    print(f"\n{'rank':<5}{'score':<8}{'z':<7}{'audio':<8}{'text':<8}{'class':<20}clip")
    for d in r["results"]:
        print(f"{d['rank']:<5}{d['score']:<8.3f}{d['z']:<7.2f}{d['audio']:<8.3f}{d['text']:<8.3f}{d['class']:<20}{d['clip']}")
    if args.no_mux:
        return
    best = r["results"][0]
    out = args.out or args.video.rsplit(".", 1)[0] + "_sfx.mp4"
    mux(args.video, e.clip_path(best["clip"]), out, args.mix)
    print(f"\n>>> {best['class']}  ->  {out}   ({time.time() - t:.1f}s total)")


if __name__ == "__main__":
    main()

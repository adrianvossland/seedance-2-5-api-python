"""Command line: python -m seedance "prompt" [options]

Local files given to --first-frame, --last-frame, --image, --video, --audio or
--edit are uploaded first. --estimate prints the cost and sends nothing.
"""
from __future__ import annotations

import argparse
import sys

from .client import Seedance
from .errors import SeedanceError
from .limits import FIXED_RATIOS, RESOLUTIONS
from .pricing import CHECKED, estimate


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m seedance", description="Generate one Seedance 2.5 video.")
    parser.add_argument("prompt")
    parser.add_argument("-o", "--output", default="seedance.mp4")
    parser.add_argument("-d", "--duration", type=int, default=5, help="4-30 seconds (default 5)")
    parser.add_argument("-r", "--resolution", choices=RESOLUTIONS, default="720p")
    parser.add_argument("-a", "--aspect-ratio", choices=FIXED_RATIOS, default="16:9",
                        help="text and reference jobs; frame jobs always follow the first frame")
    parser.add_argument("--first-frame", help="URL or local image")
    parser.add_argument("--last-frame", help="URL or local image (needs --first-frame)")
    parser.add_argument("--image", action="append", default=[], help="reference image, repeatable")
    parser.add_argument("--video", action="append", default=[], help="reference video, repeatable")
    parser.add_argument("--audio", action="append", default=[], help="reference audio, repeatable")
    parser.add_argument("--edit", help="URL or local video to edit (4-30 s)")
    parser.add_argument("--silent", action="store_true", help="no generated soundtrack")
    parser.add_argument("--estimate", action="store_true", help="print the cost and exit")
    parser.add_argument("--edit-seconds", type=float, help="length of the --edit video, for --estimate")
    parser.add_argument("--video-seconds", type=float, action="append", default=[],
                        help="length of each --video, for --estimate")
    args = parser.parse_args(argv)

    if args.estimate:
        quote = estimate(args.duration, args.resolution, args.video_seconds,
                         edit_source_seconds=args.edit_seconds if args.edit else None)
        print(f"{quote.billed_seconds} s x ${quote.rate}/s = ${quote.usd:.4f} at {quote.resolution} "
              f"(official list price ${quote.official_usd:.4f}; rates checked {CHECKED})")
        return 0

    try:
        client = Seedance()
        audio = not args.silent
        if args.edit:
            job = client.edit_video(args.prompt, args.edit, resolution=args.resolution, generate_audio=audio)
        elif args.first_frame:
            job = client.image_to_video(args.prompt, args.first_frame, last_frame=args.last_frame,
                                        duration=args.duration, resolution=args.resolution, generate_audio=audio)
        elif args.image or args.video or args.audio:
            job = client.reference_to_video(args.prompt, images=args.image, videos=args.video, audios=args.audio,
                                            duration=args.duration, resolution=args.resolution,
                                            aspect_ratio=args.aspect_ratio, generate_audio=audio)
        else:
            job = client.text_to_video(args.prompt, duration=args.duration, resolution=args.resolution,
                                       aspect_ratio=args.aspect_ratio, generate_audio=audio)
        print(f"submitted {job.request_id}", file=sys.stderr)
        done = client.run(job, args.output,
                          on_progress=lambda j: print(f"  {j.progress or 0}% ({j.eta_seconds or '?'} s left)",
                                                      file=sys.stderr))
    except SeedanceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    usage = done.usage
    print(f"saved {args.output}; billed {usage.billed_seconds if usage else '?'} s at {args.resolution}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

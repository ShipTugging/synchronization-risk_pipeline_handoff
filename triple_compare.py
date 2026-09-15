"""Build a 3-way comparison per sample frame:
  1) raw original frame (from input.mp4)
  2) teammate's YOLO-Seg overlay (from vision_overlay.mp4)
  3) our own overlay (from visualize_frame.py's build_comparison, re-derived here)

Does not modify visualize_frame.py or risk_pipeline.py. Purely a visual
diagnostic aid, same spirit as the earlier vflip/grid probe scripts.

Usage:
    python3 triple_compare.py --index 0 120 240 360 479
"""

import argparse
import os

import cv2
import numpy as np
from PIL import Image

from jsonl_utils import load_synchronized_jsonl
from visualize_frame import JSONL_PATH, VIDEO_PATH, OUT_DIR, decode_mask, extract_video_frame, build_comparison

OVERLAY_VIDEO_PATH = os.path.join(os.path.dirname(VIDEO_PATH), "vision_overlay.mp4")


def extract_overlay_frame(video_path: str, frame_index: int) -> np.ndarray:
    """Same verified extraction approach as extract_video_frame: seek by
    frame index, cross-checked earlier against POS_MSEC and sequential read
    (all three agreed exactly, see session log)."""
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    assert 0 <= frame_index < total_frames
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame_bgr = cap.read()
    cap.release()
    assert ok, f"failed to read frame {frame_index} from {video_path}"
    return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)


def label(img: np.ndarray, text: str) -> np.ndarray:
    pil = Image.fromarray(img).convert("RGB")
    from PIL import ImageDraw
    draw = ImageDraw.Draw(pil)
    draw.rectangle([0, 0, 8 + 9 * len(text), 26], fill=(0, 0, 0))
    draw.text((4, 4), text, fill=(255, 255, 0))
    return np.array(pil)


def build_triple(records, index: int) -> tuple[np.ndarray, dict]:
    record = records[index]
    ts = record["timestamp_ms"]

    original_rgb = extract_video_frame(VIDEO_PATH, ts, index)
    teammate_overlay_rgb = extract_overlay_frame(OVERLAY_VIDEO_PATH, index)

    mask = decode_mask(record)
    _, our_overlay_rgb = build_comparison(original_rgb, mask)

    panels = [
        label(original_rgb, "input.mp4 (raw)"),
        label(teammate_overlay_rgb, "vision_overlay.mp4 (teammate)"),
        label(our_overlay_rgb, "our overlay (mask_base64)"),
    ]
    combined = np.concatenate(panels, axis=1)

    info = {
        "timestamp_ms": ts,
        "roll_deg": record["imu"]["roll_deg"],
        "confidence": record["vision"]["confidence"],
    }
    return combined, info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, nargs="+", required=True)
    args = parser.parse_args()

    records = load_synchronized_jsonl(JSONL_PATH)
    os.makedirs(OUT_DIR, exist_ok=True)

    for idx in args.index:
        combined, info = build_triple(records, idx)
        out_path = os.path.join(OUT_DIR, f"frame_{idx}_triple_compare.png")
        Image.fromarray(combined).save(out_path)
        print(f"[frame {idx}] t={info['timestamp_ms']:.0f}ms roll={info['roll_deg']:.2f}deg "
              f"conf={info['confidence']:.3f}")
        print(f"  saved: {out_path}")


if __name__ == "__main__":
    main()

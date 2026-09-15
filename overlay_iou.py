"""Attempt to extract an approximate binary mask from vision_overlay.mp4's
rendered highlight (a translucent green line) and compare it against our
own decoded mask_base64 mask via IoU, for the same 5 sample frames.

Caveats (deliberately not hidden -- see printed output too):
 - We don't know vision_overlay.mp4's exact overlay compositing (color,
   alpha, line thickness algorithm). The extraction here is a plain color
   threshold (green channel dominance), verified against sampled pixels
   from the actual line region and background (water/sky) to pick a
   threshold that clearly separates them for frame 0 -- not something
   guaranteed correct for all 5 frames without a visual sanity check.
 - The teammate's overlay looks like a thin rendered line (skeleton/
   centerline-like), while our decode_mask is the full-width YOLO-Seg
   mask blob. Even a perfectly *centered* line will not reach IoU close
   to 1 against a much fatter mask -- IoU here is only meaningful as a
   directional signal (near 0 = clearly disjoint, clearly >0 with strong
   spatial overlap = same location), not as an exact agreement score.

Usage:
    python3 overlay_iou.py --index 0 120 240 360 479
"""

import argparse
import os

import cv2
import numpy as np
from PIL import Image

from jsonl_utils import load_synchronized_jsonl
from visualize_frame import JSONL_PATH, VIDEO_PATH, OUT_DIR, decode_mask

OVERLAY_VIDEO_PATH = os.path.join(os.path.dirname(VIDEO_PATH), "vision_overlay.mp4")

# HUD text box measured on frame 0 (greenness>150 pixels spanned y:20-101,
# x:10-155); padded for safety margin, assumed fixed across frames since
# it's an on-screen HUD overlay, not scene content.
HUD_EXCLUDE_BOX = (0, 0, 180, 115)  # x0, y0, x1, y1

GREENNESS_THRESHOLD = 20  # water/sky measured at -9..1, line pixels at 40..190 on frame 0


def extract_overlay_frame(video_path: str, frame_index: int) -> np.ndarray:
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    assert 0 <= frame_index < total_frames
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame_bgr = cap.read()
    cap.release()
    assert ok
    return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)


def extract_overlay_mask(frame_rgb: np.ndarray) -> np.ndarray:
    r = frame_rgb[..., 0].astype(int)
    g = frame_rgb[..., 1].astype(int)
    b = frame_rgb[..., 2].astype(int)
    greenness = g - np.maximum(r, b)
    mask = greenness > GREENNESS_THRESHOLD

    x0, y0, x1, y1 = HUD_EXCLUDE_BOX
    mask[y0:y1, x0:x1] = False
    return mask


def iou(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    inter = np.logical_and(mask_a, mask_b).sum()
    union = np.logical_or(mask_a, mask_b).sum()
    if union == 0:
        return float("nan")
    return inter / union


def centroid(mask: np.ndarray):
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return None
    return float(xs.mean()), float(ys.mean())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, nargs="+", required=True)
    args = parser.parse_args()

    records = load_synchronized_jsonl(JSONL_PATH)
    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"extraction method: greenness (G - max(R,B)) > {GREENNESS_THRESHOLD}, "
          f"HUD text box {HUD_EXCLUDE_BOX} excluded")
    print("(sanity-checked against frame 0: water/sky greenness in [-9, 1], "
          "line-region greenness in [40, 190])\n")

    for idx in args.index:
        record = records[idx]
        our_mask = decode_mask(record) > 0

        teammate_frame = extract_overlay_frame(OVERLAY_VIDEO_PATH, idx)
        teammate_mask = extract_overlay_mask(teammate_frame)

        teammate_px = int(teammate_mask.sum())
        our_px = int(our_mask.sum())

        if teammate_px == 0:
            print(f"[frame {idx}] extraction FAILED: 0 pixels passed the green threshold "
                  f"-- cannot compute IoU for this frame, skipping numeric comparison.")
            continue

        score = iou(our_mask, teammate_mask)
        c_ours = centroid(our_mask)
        c_team = centroid(teammate_mask)
        centroid_dist = None
        if c_ours and c_team:
            centroid_dist = float(np.hypot(c_ours[0] - c_team[0], c_ours[1] - c_team[1]))

        print(f"[frame {idx}] our_mask_px={our_px} teammate_overlay_px={teammate_px} "
              f"IoU={score:.4f} centroid_dist_px={centroid_dist:.1f}"
              if centroid_dist is not None else
              f"[frame {idx}] our_mask_px={our_px} teammate_overlay_px={teammate_px} IoU={score:.4f}")

        # visualization: our mask in red, teammate overlay in green, overlap in yellow
        vis = np.zeros((*our_mask.shape, 3), dtype=np.uint8)
        vis[our_mask] = [255, 0, 0]
        vis[teammate_mask] = [0, 255, 0]
        both = our_mask & teammate_mask
        vis[both] = [255, 255, 0]
        out_path = os.path.join(OUT_DIR, f"frame_{idx}_iou_overlap.png")
        Image.fromarray(vis).save(out_path)
        print(f"  saved: {out_path}  (red=ours, green=teammate, yellow=overlap)")


if __name__ == "__main__":
    main()

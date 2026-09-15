"""Visualize a single synchronized.jsonl record: decode its vision mask,
pull the matching frame out of input.mp4, and render a side-by-side +
overlay comparison image.

This is an exploration/validation tool only. It does NOT compute
towline_angle_deg or sag_ratio -- those are left to be designed separately.

Usage:
    python3 visualize_frame.py --index 240
    python3 visualize_frame.py --index 0 120 240 360 479
"""

import argparse
import base64
import io
import os

import cv2
import numpy as np
from PIL import Image

from jsonl_utils import load_synchronized_jsonl

HERE = os.path.dirname(os.path.abspath(__file__))
JSONL_PATH = os.path.join(HERE, "synchronized.jsonl")
VIDEO_PATH = os.path.join(HERE, "input.mp4")
OUT_DIR = os.path.join(HERE, "mask_visualization")


def decode_mask(record: dict) -> np.ndarray:
    """Decode vision.mask_base64 into a numpy image array, validating
    that the decoded size matches mask_width/mask_height."""
    vision = record["vision"]
    raw = base64.b64decode(vision["mask_base64"])
    img = Image.open(io.BytesIO(raw))
    img.load()

    assert img.width == vision["mask_width"], (
        f"decoded mask width {img.width} != mask_width {vision['mask_width']}"
    )
    assert img.height == vision["mask_height"], (
        f"decoded mask height {img.height} != mask_height {vision['mask_height']}"
    )

    return np.array(img)


def extract_video_frame(video_path: str, timestamp_ms: float, frame_index: int) -> np.ndarray:
    """Extract the frame from video_path matching timestamp_ms.

    frame_index is used as the primary seek (exact, since input.mp4 is a
    fixed 24fps/480-frame recording produced 1:1 with synchronized.jsonl);
    timestamp_ms is only used to sanity-check that seek.
    """
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    assert 0 <= frame_index < total_frames, (
        f"frame_index {frame_index} out of range [0, {total_frames})"
    )

    expected_index = round(timestamp_ms / 1000.0 * fps)
    if expected_index != frame_index:
        print(
            f"  [warn] timestamp_ms={timestamp_ms} implies frame {expected_index} "
            f"via fps={fps}, but using record order index {frame_index}"
        )

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame_bgr = cap.read()
    cap.release()

    assert ok, f"failed to read frame {frame_index} from {video_path}"

    return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)


def build_comparison(original_rgb: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (side_by_side, overlay) RGB images.

    mask is treated as non-zero == towline pixel, regardless of whether it's
    single-channel or RGB(A) -- no assumption made about its exact encoding.
    """
    if mask.ndim == 3:
        mask_bool = np.any(mask[..., :3] > 0, axis=-1)
    else:
        mask_bool = mask > 0

    h, w = original_rgb.shape[:2]
    if mask_bool.shape != (h, w):
        mask_bool = np.array(
            Image.fromarray(mask_bool.astype(np.uint8) * 255).resize((w, h), Image.NEAREST)
        ) > 0

    mask_rgb = np.zeros_like(original_rgb)
    mask_rgb[mask_bool] = [255, 255, 255]

    side_by_side = np.concatenate([original_rgb, mask_rgb], axis=1)

    overlay = original_rgb.copy().astype(np.float32)
    red = np.array([255, 40, 40], dtype=np.float32)
    alpha = 0.5
    overlay[mask_bool] = overlay[mask_bool] * (1 - alpha) + red * alpha
    overlay = overlay.astype(np.uint8)

    return side_by_side, overlay


def visualize_index(records: list[dict], index: int) -> None:
    record = records[index]
    vision = record["vision"]
    timestamp_ms = record["timestamp_ms"]

    print(f"[frame {index}] timestamp_ms={timestamp_ms} "
          f"towline_detected={vision['towline_detected']} "
          f"confidence={vision['confidence']:.4f}")

    mask = decode_mask(record)
    mask_bool = np.any(mask[..., :3] > 0, axis=-1) if mask.ndim == 3 else mask > 0
    nonzero_ratio = float(np.count_nonzero(mask_bool)) / mask_bool.size
    print(f"  mask nonzero pixel ratio: {nonzero_ratio:.4%}")

    os.makedirs(OUT_DIR, exist_ok=True)

    mask_path = os.path.join(OUT_DIR, f"frame_{index}_mask.png")
    Image.fromarray(mask).save(mask_path)

    original_rgb = extract_video_frame(VIDEO_PATH, timestamp_ms, index)
    original_path = os.path.join(OUT_DIR, f"frame_{index}_original.png")
    Image.fromarray(original_rgb).save(original_path)

    side_by_side, overlay = build_comparison(original_rgb, mask)
    compare_path = os.path.join(OUT_DIR, f"frame_{index}_compare.png")

    # side-by-side (original | mask) on top, full-width overlay below
    top = side_by_side
    bottom = np.zeros_like(top)
    bottom[:, : overlay.shape[1]] = overlay
    combined = np.concatenate([top, bottom], axis=0)
    Image.fromarray(combined).save(compare_path)

    print(f"  saved: {mask_path}")
    print(f"  saved: {original_path}")
    print(f"  saved: {compare_path}")

    if nonzero_ratio == 0.0:
        print(f"  [!] frame {index}: mask is EMPTY despite towline_detected="
              f"{vision['towline_detected']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, nargs="+", required=True,
                         help="one or more record indices (0-based, matches frame order)")
    args = parser.parse_args()

    records = load_synchronized_jsonl(JSONL_PATH)

    for idx in args.index:
        visualize_index(records, idx)


if __name__ == "__main__":
    main()

"""
PNG Upscaler Script for Windows 10
====================================
Upscales PNG images using high-quality Lanczos resampling (via Pillow).

Requirements:
    pip install Pillow

Usage:
    python upscale_png.py <input.png> [options]

Examples:
    python upscale_png.py photo.png                        # 2x upscale (default)
    python upscale_png.py photo.png --scale 4              # 4x upscale
    python upscale_png.py photo.png --width 1920           # Resize to specific width
    python upscale_png.py photo.png --width 1920 --height 1080  # Resize to exact dimensions
    python upscale_png.py photo.png --output upscaled.png  # Custom output filename
"""

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow is not installed.")
    print("Run: pip install Pillow")
    sys.exit(1)


def upscale_image(
    input_path: str,
    output_path: str = None,
    scale: float = 2.0,
    target_width: int = None,
    target_height: int = None,
    resample=Image.LANCZOS,
):
    input_path = Path(input_path)

    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    if input_path.suffix.lower() != ".png":
        print(f"WARNING: File does not have a .png extension: {input_path}")

    # Build output path
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_upscaled.png"
    else:
        output_path = Path(output_path)

    print(f"Opening: {input_path}")
    img = Image.open(input_path)
    orig_width, orig_height = img.size
    print(f"Original size: {orig_width} x {orig_height} px  |  Mode: {img.mode}")

    # Determine target dimensions
    if target_width and target_height:
        new_width = target_width
        new_height = target_height
    elif target_width:
        ratio = target_width / orig_width
        new_width = target_width
        new_height = int(orig_height * ratio)
    elif target_height:
        ratio = target_height / orig_height
        new_width = int(orig_width * ratio)
        new_height = target_height
    else:
        new_width = int(orig_width * scale)
        new_height = int(orig_height * scale)

    print(f"Target size:   {new_width} x {new_height} px  (scale factor: {new_width/orig_width:.2f}x)")

    if new_width <= orig_width and new_height <= orig_height:
        print("WARNING: Target is smaller than or equal to the original. Continuing anyway...")

    # Perform upscale
    print("Upscaling... ", end="", flush=True)
    upscaled = img.resize((new_width, new_height), resample)
    print("Done.")

    # Save
    upscaled.save(output_path, format="PNG", optimize=False)
    print(f"Saved to: {output_path}")

    # File size info
    in_size = input_path.stat().st_size / 1024
    out_size = output_path.stat().st_size / 1024
    print(f"File size: {in_size:.1f} KB  →  {out_size:.1f} KB")


def main():
    parser = argparse.ArgumentParser(
        description="Upscale a PNG image using high-quality Lanczos resampling.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input", help="Path to the input PNG file")
    parser.add_argument(
        "--scale", type=float, default=2.0,
        help="Scale multiplier (default: 2.0 = double the resolution)"
    )
    parser.add_argument(
        "--width", type=int, default=None,
        help="Target width in pixels (preserves aspect ratio unless --height also set)"
    )
    parser.add_argument(
        "--height", type=int, default=None,
        help="Target height in pixels (preserves aspect ratio unless --width also set)"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Output file path (default: <input>_upscaled.png)"
    )
    parser.add_argument(
        "--filter", type=str, default="lanczos",
        choices=["lanczos", "bicubic", "bilinear", "nearest"],
        help="Resampling filter (default: lanczos — best quality)"
    )

    args = parser.parse_args()

    filter_map = {
        "lanczos": Image.LANCZOS,
        "bicubic": Image.BICUBIC,
        "bilinear": Image.BILINEAR,
        "nearest": Image.NEAREST,
    }

    upscale_image(
        input_path=args.input,
        output_path=args.output,
        scale=args.scale,
        target_width=args.width,
        target_height=args.height,
        resample=filter_map[args.filter],
    )


if __name__ == "__main__":
    main()

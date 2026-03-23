"""PNG upscaler using Pillow with strict validation and robust error handling."""

from __future__ import annotations

import argparse
import logging
import math
from pathlib import Path
from typing import Optional

from PIL import Image, UnidentifiedImageError
from PIL.Image import Resampling

LOGGER = logging.getLogger(__name__)

FILTER_MAP: dict[str, Resampling] = {
    "lanczos": Resampling.LANCZOS,
    "bicubic": Resampling.BICUBIC,
    "bilinear": Resampling.BILINEAR,
    "nearest": Resampling.NEAREST,
}


class UpscaleError(Exception):
    """Base exception for image upscaling failures."""


class ValidationError(UpscaleError):
    """Raised when input arguments, dimensions, or paths are invalid."""


def _is_within_directory(base_dir: Path, target_path: Path) -> bool:
    try:
        target_path.relative_to(base_dir)
        return True
    except ValueError:
        return False


def _resolve_output_path(input_path: Path, output_path: Optional[str | Path]) -> Path:
    """Resolve output path and block directory traversal outside input directory."""
    base_dir = input_path.parent.resolve()
    if output_path is None:
        return base_dir / f"{input_path.stem}_upscaled.png"

    requested = Path(output_path)
    if any(part == ".." for part in requested.parts):
        raise ValidationError("Output path must not contain '..' traversal segments.")

    if requested.is_absolute():
        resolved = requested.resolve()
    else:
        resolved = (base_dir / requested).resolve()

    if not _is_within_directory(base_dir, resolved):
        raise ValidationError("Output path must remain within the input file directory.")

    if resolved.suffix.lower() != ".png":
        raise ValidationError("Output filename must have a .png extension.")

    return resolved


def _safe_size_kib(path: Path) -> Optional[float]:
    try:
        return path.stat().st_size / 1024
    except OSError as exc:
        LOGGER.warning("Unable to read file size for %s: %s", path, exc)
        return None


def _load_png(input_path: Path) -> Image.Image:
    """Load an image, verify PNG format, and fully decode to catch corruption."""
    try:
        with Image.open(input_path) as image:
            image.load()
            if image.format != "PNG":
                raise ValidationError(f"Input file is not a PNG image: {input_path}")
            if image.width <= 0 or image.height <= 0:
                raise ValidationError(
                    f"Input image has invalid dimensions: {image.width}x{image.height}"
                )
            return image.copy()
    except FileNotFoundError as exc:
        raise ValidationError(f"Input file not found: {input_path}") from exc
    except PermissionError as exc:
        raise UpscaleError(f"Permission denied reading input file: {input_path}") from exc
    except UnidentifiedImageError as exc:
        raise ValidationError(f"Input file is not a valid image: {input_path}") from exc
    except ValidationError:
        raise
    except (OSError, ValueError) as exc:
        raise UpscaleError(f"Failed to decode input file '{input_path}': {exc}") from exc


def _calculate_target_dimensions(
    orig_width: int,
    orig_height: int,
    scale: float,
    target_width: Optional[int],
    target_height: Optional[int],
) -> tuple[int, int]:
    if orig_width <= 0 or orig_height <= 0:
        raise ValidationError(f"Source dimensions must be positive, got {orig_width}x{orig_height}")

    if target_width is not None and target_width <= 0:
        raise ValidationError(f"--width must be > 0, got {target_width}")
    if target_height is not None and target_height <= 0:
        raise ValidationError(f"--height must be > 0, got {target_height}")

    if target_width is not None and target_height is not None:
        new_width = target_width
        new_height = target_height
    elif target_width is not None:
        ratio = target_width / orig_width
        new_width = target_width
        new_height = max(1, int(round(orig_height * ratio)))
    elif target_height is not None:
        ratio = target_height / orig_height
        new_width = max(1, int(round(orig_width * ratio)))
        new_height = target_height
    else:
        if not math.isfinite(scale) or scale <= 0:
            raise ValidationError(f"--scale must be a finite number > 0, got {scale}")
        new_width = max(1, int(round(orig_width * scale)))
        new_height = max(1, int(round(orig_height * scale)))

    if new_width <= 0 or new_height <= 0:
        raise ValidationError(f"Computed invalid target dimensions: {new_width}x{new_height}")
    return new_width, new_height


def upscale_image(
    input_path: str | Path,
    output_path: Optional[str | Path] = None,
    scale: float = 2.0,
    target_width: Optional[int] = None,
    target_height: Optional[int] = None,
    resample: Optional[Resampling] = None,
    optimize: bool = True,
    compress_level: int = 6,
) -> Path:
    """Upscale a PNG image and return output path."""
    source_path = Path(input_path).expanduser()
    if compress_level < 0 or compress_level > 9:
        raise ValidationError(f"--compress-level must be between 0 and 9, got {compress_level}")

    destination_path = _resolve_output_path(source_path, output_path)
    try:
        if destination_path.resolve() == source_path.resolve():
            raise ValidationError("Output path must be different from input path.")
    except OSError as exc:
        raise UpscaleError(f"Unable to resolve input/output paths: {exc}") from exc

    selected_resample = resample if resample is not None else Resampling.LANCZOS
    image = _load_png(source_path)
    try:
        orig_width, orig_height = image.size
        new_width, new_height = _calculate_target_dimensions(
            orig_width=orig_width,
            orig_height=orig_height,
            scale=scale,
            target_width=target_width,
            target_height=target_height,
        )

        LOGGER.info("Opening: %s", source_path)
        LOGGER.info("Original size: %d x %d px | Mode: %s", orig_width, orig_height, image.mode)
        LOGGER.info(
            "Target size: %d x %d px (scale factor: %.2fx)",
            new_width,
            new_height,
            new_width / orig_width,
        )
        if new_width <= orig_width and new_height <= orig_height:
            LOGGER.warning("Target dimensions are not larger than source dimensions.")

        upscaled = image.resize((new_width, new_height), selected_resample)
        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            upscaled.save(
                destination_path,
                format="PNG",
                optimize=optimize,
                compress_level=compress_level,
            )
        except (OSError, ValueError) as exc:
            raise UpscaleError(f"Failed to save output file '{destination_path}': {exc}") from exc
        finally:
            upscaled.close()
    finally:
        image.close()

    LOGGER.info("Saved to: %s", destination_path)
    in_size = _safe_size_kib(source_path)
    out_size = _safe_size_kib(destination_path)
    if in_size is not None and out_size is not None:
        LOGGER.info("File size: %.1f KiB -> %.1f KiB", in_size, out_size)

    return destination_path


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upscale a PNG image using high-quality Lanczos resampling.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python upscale_png.py photo.png\n"
            "  python upscale_png.py photo.png --scale 4\n"
            "  python upscale_png.py photo.png --width 1920\n"
            "  python upscale_png.py photo.png --width 1920 --height 1080\n"
            "  python upscale_png.py photo.png --no-optimize --compress-level 9\n"
            "  python upscale_png.py photo.png --output output/upscaled.png"
        ),
    )
    parser.add_argument("input", help="Path to the input PNG file")
    parser.add_argument(
        "--scale",
        type=float,
        default=2.0,
        help="Scale multiplier (> 0, default: 2.0)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help="Target width in pixels (> 0). Preserves aspect ratio unless --height is set.",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=None,
        help="Target height in pixels (> 0). Preserves aspect ratio unless --width is set.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output path relative to input directory (default: <input>_upscaled.png).",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default="lanczos",
        choices=sorted(FILTER_MAP.keys()),
        help="Resampling filter (default: lanczos)",
    )
    parser.add_argument(
        "--no-optimize",
        dest="optimize",
        action="store_false",
        help="Disable PNG optimization during save.",
    )
    parser.set_defaults(optimize=True)
    parser.add_argument(
        "--compress-level",
        type=int,
        default=6,
        help="PNG compression level from 0 (fastest) to 9 (smallest). Default: 6.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    try:
        upscale_image(
            input_path=args.input,
            output_path=args.output,
            scale=args.scale,
            target_width=args.width,
            target_height=args.height,
            resample=FILTER_MAP[args.filter],
            optimize=args.optimize,
            compress_level=args.compress_level,
        )
    except UpscaleError as exc:
        LOGGER.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

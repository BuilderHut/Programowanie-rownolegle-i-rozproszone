"""Tworzy przykladowy obraz z wyraznymi krawedziami do demonstracji."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def generate_sample(output: Path, width: int = 900, height: int = 600) -> None:
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    for x in range(width):
        shade = int(230 * x / max(1, width - 1))
        draw.line((x, 0, x, height), fill=(shade, 110, 230 - shade))

    margin = min(width, height) // 10
    draw.rectangle(
        (margin, margin, width // 2, height // 2),
        fill=(245, 220, 35),
        outline=(20, 20, 20),
        width=8,
    )
    draw.ellipse(
        (width // 2, margin, width - margin, height - margin),
        fill=(40, 190, 110),
        outline=(255, 255, 255),
        width=10,
    )
    draw.line(
        (margin, height - margin, width - margin, height // 2),
        fill=(255, 255, 255),
        width=14,
    )
    draw.text((margin, height - margin - 45), "Sobel - test krawedzi", fill=(0, 0, 0))

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generuje obraz demonstracyjny.")
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("sample_input.png"), help="Plik PNG."
    )
    args = parser.parse_args()
    generate_sample(args.output)
    print(f"Utworzono: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


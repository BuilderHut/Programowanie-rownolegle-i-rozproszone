"""Zadanie 1: rownolegle przetwarzanie obrazu w wielu procesach."""

from __future__ import annotations

import argparse
import multiprocessing
import os
from pathlib import Path
from time import perf_counter

import numpy as np
from PIL import Image

from image_processing import (
    image_to_grayscale_array,
    process_image_parallel,
    save_grayscale_image,
    sobel_filter,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Zadanie 1 - rownolegle wykrywanie krawedzi filtrem Sobela."
    )
    parser.add_argument("input", type=Path, help="Sciezka do obrazu wejsciowego.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("processed_parallel.png"),
        help="Plik wynikowy (domyslnie: processed_parallel.png).",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=max(1, os.cpu_count() or 1),
        help="Liczba procesow roboczych (domyslnie: liczba logicznych CPU).",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Porownaj wynik i czas z wykonaniem sekwencyjnym.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.workers < 1:
        raise SystemExit("Liczba procesow musi byc dodatnia.")
    if not args.input.is_file():
        raise SystemExit(f"Nie znaleziono obrazu: {args.input}")

    with Image.open(args.input) as source_image:
        pixels = image_to_grayscale_array(source_image)

    worker_count = min(args.workers, pixels.shape[0])
    started = perf_counter()
    result = process_image_parallel(pixels, worker_count)
    parallel_time = perf_counter() - started

    args.output.parent.mkdir(parents=True, exist_ok=True)
    save_grayscale_image(result, str(args.output))

    print(f"Rozmiar obrazu: {pixels.shape[1]}x{pixels.shape[0]} px")
    print(f"Procesy robocze: {worker_count}")
    print(f"Czas rownolegly: {parallel_time:.4f} s")
    print(f"Zapisano wynik: {args.output.resolve()}")

    if args.benchmark:
        started = perf_counter()
        sequential_result = sobel_filter(pixels)
        sequential_time = perf_counter() - started
        identical = np.array_equal(result, sequential_result)
        speedup = sequential_time / parallel_time if parallel_time else float("inf")
        print(f"Czas sekwencyjny: {sequential_time:.4f} s")
        print(f"Przyspieszenie: {speedup:.2f}x")
        print(f"Wyniki identyczne: {'TAK' if identical else 'NIE'}")
        if not identical:
            return 2

    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())


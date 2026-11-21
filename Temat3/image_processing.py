"""Wspolne funkcje przetwarzania obrazu dla zadan 1 i 2.

Filtr Sobela jest zaimplementowany bez bibliotek przetwarzania obrazu -
wykorzystuje jedynie operacje na tablicach NumPy.
"""

from __future__ import annotations

from dataclasses import dataclass
from multiprocessing import Pool
from typing import Sequence

import numpy as np
from numpy.typing import NDArray
from PIL import Image


GrayArray = NDArray[np.uint8]


@dataclass(frozen=True)
class ImageFragment:
    """Fragment obrazu wraz z informacja o marginesach do odciecia."""

    index: int
    pixels: GrayArray
    trim_top: int = 0
    trim_bottom: int = 0


@dataclass(frozen=True)
class ProcessedFragment:
    """Gotowy fragment bez nadmiarowych pikseli marginesu."""

    index: int
    pixels: GrayArray


def image_to_grayscale_array(image: Image.Image) -> GrayArray:
    """Konwertuje dowolny obraz Pillow do dwuwymiarowej tablicy uint8."""

    return np.asarray(image.convert("L"), dtype=np.uint8)


def sobel_filter(pixels: NDArray[np.generic]) -> GrayArray:
    """Wykrywa krawedzie filtrem Sobela zaimplementowanym w NumPy.

    Macierze 3x3 nie sa nakladane w petli piksel po pikselu. Zamiast tego
    tworzymy przesuniete widoki obrazu, a nastepnie obliczamy skladowe Gx i
    Gy zgodnie z maskami Sobela. Wynik jest obcinany do zakresu 0..255.
    """

    source = np.asarray(pixels)
    if source.ndim != 2:
        raise ValueError("Filtr Sobela wymaga dwuwymiarowego obrazu w skali szarosci.")
    if source.shape[0] == 0 or source.shape[1] == 0:
        raise ValueError("Nie mozna przetworzyc pustego obrazu.")

    image = source.astype(np.float32, copy=False)
    padded = np.pad(image, ((1, 1), (1, 1)), mode="edge")

    top_left = padded[:-2, :-2]
    top = padded[:-2, 1:-1]
    top_right = padded[:-2, 2:]
    middle_left = padded[1:-1, :-2]
    middle_right = padded[1:-1, 2:]
    bottom_left = padded[2:, :-2]
    bottom = padded[2:, 1:-1]
    bottom_right = padded[2:, 2:]

    gradient_x = (
        -top_left
        + top_right
        - 2.0 * middle_left
        + 2.0 * middle_right
        - bottom_left
        + bottom_right
    )
    gradient_y = (
        -top_left
        - 2.0 * top
        - top_right
        + bottom_left
        + 2.0 * bottom
        + bottom_right
    )

    magnitude = np.hypot(gradient_x, gradient_y)
    return np.clip(magnitude, 0, 255).astype(np.uint8)


def split_image(pixels: NDArray[np.generic], parts: int, halo: int = 1) -> list[ImageFragment]:
    """Dzieli obraz na poziome pasy z marginesem potrzebnym filtrowi.

    Dla maski 3x3 kazdy wewnetrzny fragment dostaje dodatkowy wiersz nad i
    pod swoim zakresem. Po przetworzeniu te wiersze sa odcinane. Zapobiega to
    powstawaniu sztucznych krawedzi w miejscach laczenia fragmentow.
    """

    image = np.asarray(pixels)
    if image.ndim != 2:
        raise ValueError("Podzial wymaga dwuwymiarowego obrazu.")
    if image.shape[0] == 0 or image.shape[1] == 0:
        raise ValueError("Nie mozna podzielic pustego obrazu.")
    if parts < 1:
        raise ValueError("Liczba fragmentow musi byc dodatnia.")
    if halo < 0:
        raise ValueError("Margines nie moze byc ujemny.")

    height = image.shape[0]
    actual_parts = min(parts, height)
    boundaries = np.linspace(0, height, actual_parts + 1, dtype=int)
    fragments: list[ImageFragment] = []

    for index in range(actual_parts):
        core_start = int(boundaries[index])
        core_end = int(boundaries[index + 1])
        extended_start = max(0, core_start - halo)
        extended_end = min(height, core_end + halo)

        fragments.append(
            ImageFragment(
                index=index,
                pixels=np.ascontiguousarray(image[extended_start:extended_end], dtype=np.uint8),
                trim_top=core_start - extended_start,
                trim_bottom=extended_end - core_end,
            )
        )

    return fragments


def process_fragment(fragment: ImageFragment) -> ProcessedFragment:
    """Przetwarza jeden fragment i usuwa dodany wczesniej margines."""

    filtered = sobel_filter(fragment.pixels)
    end = filtered.shape[0] - fragment.trim_bottom if fragment.trim_bottom else filtered.shape[0]
    core = filtered[fragment.trim_top:end]
    return ProcessedFragment(fragment.index, np.ascontiguousarray(core))


def merge_image(fragments: Sequence[ProcessedFragment]) -> GrayArray:
    """Scala przetworzone fragmenty w kolejnosci ich indeksow."""

    if not fragments:
        raise ValueError("Brak fragmentow do scalenia.")

    ordered = sorted(fragments, key=lambda item: item.index)
    expected_indices = list(range(len(ordered)))
    indices = [item.index for item in ordered]
    if indices != expected_indices:
        raise ValueError(f"Nieprawidlowa numeracja fragmentow: {indices}.")

    widths = {item.pixels.shape[1] for item in ordered if item.pixels.ndim == 2}
    if len(widths) != 1 or any(item.pixels.ndim != 2 for item in ordered):
        raise ValueError("Fragmenty maja niezgodne wymiary.")

    return np.ascontiguousarray(np.concatenate([item.pixels for item in ordered], axis=0))


def process_image_parallel(pixels: NDArray[np.generic], workers: int) -> GrayArray:
    """Dzieli obraz i przetwarza fragmenty w osobnych procesach."""

    fragments = split_image(pixels, workers, halo=1)
    process_count = len(fragments)
    with Pool(processes=process_count) as pool:
        processed = pool.map(process_fragment, fragments)
    return merge_image(processed)


def save_grayscale_image(pixels: NDArray[np.generic], output_path: str) -> None:
    """Zapisuje dwuwymiarowa tablice jako obraz PNG lub inny format Pillow."""

    image = np.asarray(pixels, dtype=np.uint8)
    if image.ndim != 2:
        raise ValueError("Do zapisu oczekiwany jest obraz w skali szarosci.")
    Image.fromarray(image).save(output_path)


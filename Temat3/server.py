"""Zadanie 2: serwer rozdzielajacy fragmenty obrazu do klientow."""

from __future__ import annotations

import argparse
import socket
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter
from typing import Callable

import numpy as np
from PIL import Image

from image_processing import (
    ImageFragment,
    ProcessedFragment,
    image_to_grayscale_array,
    merge_image,
    save_grayscale_image,
    split_image,
)
from network_protocol import PROTOCOL_VERSION, receive_all, send_all


def _validate_response(response: object, expected: ImageFragment) -> ProcessedFragment:
    if not isinstance(response, dict):
        raise ValueError("Klient zwrocil dane w nieprawidlowym formacie.")
    if response.get("status") != "ok":
        message = response.get("message", "nieznany blad klienta")
        raise RuntimeError(f"Klient zglosil blad: {message}")
    if response.get("version") != PROTOCOL_VERSION:
        raise ValueError("Klient uzywa niezgodnej wersji protokolu.")
    if response.get("index") != expected.index:
        raise ValueError("Klient zwrocil fragment o nieprawidlowym indeksie.")

    pixels = np.asarray(response.get("pixels"))
    expected_height = (
        expected.pixels.shape[0] - expected.trim_top - expected.trim_bottom
    )
    expected_shape = (expected_height, expected.pixels.shape[1])
    if pixels.ndim != 2 or pixels.shape != expected_shape:
        raise ValueError(
            f"Klient zwrocil rozmiar {pixels.shape}, oczekiwano {expected_shape}."
        )

    return ProcessedFragment(expected.index, np.ascontiguousarray(pixels, dtype=np.uint8))


def _serve_client(
    client_socket: socket.socket,
    address: tuple[str, int],
    fragment: ImageFragment,
    timeout: float,
) -> ProcessedFragment:
    with client_socket:
        client_socket.settimeout(timeout)
        print(f"Klient {address[0]}:{address[1]} otrzymuje fragment {fragment.index}.")
        send_all(
            client_socket,
            {
                "type": "process_fragment",
                "version": PROTOCOL_VERSION,
                "index": fragment.index,
                "pixels": fragment.pixels,
                "trim_top": fragment.trim_top,
                "trim_bottom": fragment.trim_bottom,
            },
        )
        response = receive_all(client_socket)
        result = _validate_response(response, fragment)
        print(f"Odebrano gotowy fragment {fragment.index} od {address[0]}:{address[1]}.")
        return result


def run_server(
    input_path: Path,
    output_path: Path,
    host: str,
    port: int,
    clients: int,
    timeout: float = 120.0,
    ready_callback: Callable[[int], None] | None = None,
) -> float:
    """Uruchamia serwer, zapisuje wynik i zwraca czas pracy w sekundach."""

    if clients < 1:
        raise ValueError("Liczba klientow musi byc dodatnia.")
    if not input_path.is_file():
        raise FileNotFoundError(f"Nie znaleziono obrazu: {input_path}")

    with Image.open(input_path) as image:
        pixels = image_to_grayscale_array(image)
    fragments = split_image(pixels, clients, halo=1)
    actual_clients = len(fragments)
    if actual_clients != clients:
        print(
            f"Obraz ma tylko {pixels.shape[0]} wierszy; liczba klientow zostala "
            f"zmniejszona do {actual_clients}."
        )

    started = perf_counter()
    results: list[ProcessedFragment] = []

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((host, port))
        server_socket.listen(actual_clients)
        server_socket.settimeout(timeout)
        bound_port = int(server_socket.getsockname()[1])
        print(f"Serwer nasluchuje na {host}:{bound_port}.")
        print(f"Oczekiwana liczba klientow: {actual_clients}.")
        if ready_callback is not None:
            ready_callback(bound_port)

        futures: list[Future[ProcessedFragment]] = []
        with ThreadPoolExecutor(max_workers=actual_clients) as executor:
            for fragment in fragments:
                client_socket, address = server_socket.accept()
                futures.append(
                    executor.submit(
                        _serve_client,
                        client_socket,
                        (str(address[0]), int(address[1])),
                        fragment,
                        timeout,
                    )
                )

            for future in as_completed(futures):
                results.append(future.result())

    merged = merge_image(results)
    if merged.shape != pixels.shape:
        raise RuntimeError(f"Wynik ma rozmiar {merged.shape}, oczekiwano {pixels.shape}.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_grayscale_image(merged, str(output_path))
    elapsed = perf_counter() - started
    print(f"Scalono {len(results)} fragmentow w obraz {merged.shape[1]}x{merged.shape[0]} px.")
    print(f"Zapisano wynik: {output_path.resolve()}")
    print(f"Calkowity czas: {elapsed:.4f} s")
    return elapsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Zadanie 2 - serwer rozproszonego przetwarzania obrazu."
    )
    parser.add_argument("input", type=Path, help="Obraz wejsciowy.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("processed_distributed.png"),
        help="Plik wynikowy (domyslnie: processed_distributed.png).",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Adres nasluchiwania (domyslnie: 0.0.0.0).",
    )
    parser.add_argument("--port", type=int, default=2040, help="Port TCP (domyslnie: 2040).")
    parser.add_argument(
        "--clients", type=int, default=2, help="Liczba klientow/fragmentow (domyslnie: 2)."
    )
    parser.add_argument(
        "--timeout", type=float, default=120.0, help="Limit oczekiwania w sekundach."
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    run_server(
        input_path=args.input,
        output_path=args.output,
        host=args.host,
        port=args.port,
        clients=args.clients,
        timeout=args.timeout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


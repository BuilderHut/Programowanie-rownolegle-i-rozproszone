"""Zadanie 2: klient odbierajacy i przetwarzajacy fragment obrazu."""

from __future__ import annotations

import argparse
import socket
import time
from time import perf_counter

import numpy as np

from image_processing import ImageFragment, process_fragment
from network_protocol import PROTOCOL_VERSION, receive_all, send_all


def _connect_with_retry(
    host: str,
    port: int,
    timeout: float,
    retries: int,
    retry_delay: float,
) -> socket.socket:
    last_error: OSError | None = None
    for attempt in range(1, retries + 1):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(timeout)
        try:
            client_socket.connect((host, port))
            return client_socket
        except OSError as error:
            client_socket.close()
            last_error = error
            if attempt < retries:
                print(f"Serwer niedostepny (proba {attempt}/{retries}); ponawiam...")
                time.sleep(retry_delay)
    raise ConnectionError(f"Nie mozna polaczyc sie z {host}:{port}: {last_error}")


def _parse_task(message: object) -> ImageFragment:
    if not isinstance(message, dict) or message.get("type") != "process_fragment":
        raise ValueError("Serwer wyslal nieznany typ zadania.")
    if message.get("version") != PROTOCOL_VERSION:
        raise ValueError("Serwer uzywa niezgodnej wersji protokolu.")

    pixels = np.asarray(message.get("pixels"))
    if pixels.ndim != 2 or pixels.size == 0:
        raise ValueError("Odebrany fragment obrazu jest nieprawidlowy.")
    return ImageFragment(
        index=int(message["index"]),
        pixels=np.ascontiguousarray(pixels, dtype=np.uint8),
        trim_top=int(message.get("trim_top", 0)),
        trim_bottom=int(message.get("trim_bottom", 0)),
    )


def run_client(
    host: str,
    port: int,
    timeout: float = 120.0,
    retries: int = 30,
    retry_delay: float = 1.0,
) -> tuple[int, float]:
    """Laczy sie z serwerem, wykonuje jedno zadanie i zwraca indeks oraz czas."""

    started = perf_counter()
    with _connect_with_retry(host, port, timeout, retries, retry_delay) as client_socket:
        print(f"Polaczono z serwerem {host}:{port}.")
        try:
            fragment = _parse_task(receive_all(client_socket))
            print(
                f"Przetwarzanie fragmentu {fragment.index} "
                f"({fragment.pixels.shape[1]}x{fragment.pixels.shape[0]} px)."
            )
            result = process_fragment(fragment)
            send_all(
                client_socket,
                {
                    "status": "ok",
                    "version": PROTOCOL_VERSION,
                    "index": result.index,
                    "pixels": result.pixels,
                },
            )
        except Exception as error:
            try:
                send_all(
                    client_socket,
                    {
                        "status": "error",
                        "version": PROTOCOL_VERSION,
                        "message": str(error),
                    },
                )
            except OSError:
                pass
            raise

    elapsed = perf_counter() - started
    print(f"Fragment {result.index} odeslany w {elapsed:.4f} s.")
    return result.index, elapsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Zadanie 2 - klient rozproszonego przetwarzania obrazu."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Adres IP serwera.")
    parser.add_argument("--port", type=int, default=2040, help="Port TCP serwera.")
    parser.add_argument(
        "--timeout", type=float, default=120.0, help="Limit operacji sieciowych w sekundach."
    )
    parser.add_argument("--retries", type=int, default=30, help="Liczba prob polaczenia.")
    parser.add_argument(
        "--retry-delay", type=float, default=1.0, help="Odstep miedzy probami w sekundach."
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.retries < 1:
        raise SystemExit("Liczba prob musi byc dodatnia.")
    run_client(
        host=args.host,
        port=args.port,
        timeout=args.timeout,
        retries=args.retries,
        retry_delay=args.retry_delay,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


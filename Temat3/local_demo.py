"""Automatyczny pokaz zadania 2 na jednym komputerze."""

from __future__ import annotations

import argparse
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from client import run_client
from server import run_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Uruchom serwer i kilku klientow lokalnie w jednym poleceniu."
    )
    parser.add_argument("input", type=Path, help="Obraz wejsciowy.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("processed_distributed.png"),
        help="Plik wynikowy.",
    )
    parser.add_argument("--clients", type=int, default=2, help="Liczba lokalnych klientow.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.clients < 1:
        raise SystemExit("Liczba klientow musi byc dodatnia.")

    ready: queue.Queue[int] = queue.Queue(maxsize=1)
    server_result: queue.Queue[BaseException | None] = queue.Queue(maxsize=1)

    def server_target() -> None:
        try:
            run_server(
                input_path=args.input,
                output_path=args.output,
                host="127.0.0.1",
                port=0,
                clients=args.clients,
                timeout=30.0,
                ready_callback=ready.put,
            )
            server_result.put(None)
        except BaseException as error:
            server_result.put(error)

    server_thread = threading.Thread(target=server_target, name="server", daemon=True)
    server_thread.start()
    try:
        port = ready.get(timeout=10.0)
    except queue.Empty as error:
        raise RuntimeError("Serwer nie uruchomil sie w wyznaczonym czasie.") from error

    with ThreadPoolExecutor(max_workers=args.clients) as executor:
        futures = [
            executor.submit(run_client, "127.0.0.1", port, 30.0, 5, 0.1)
            for _ in range(args.clients)
        ]
        for future in futures:
            future.result()

    server_thread.join(timeout=35.0)
    if server_thread.is_alive():
        raise RuntimeError("Serwer nie zakonczyl pracy.")
    server_error = server_result.get_nowait()
    if server_error is not None:
        raise server_error

    print("Demonstracja lokalna zakonczona pomyslnie.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


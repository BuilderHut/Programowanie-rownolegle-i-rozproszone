from __future__ import annotations

import queue
import socket
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

from client import run_client
from image_processing import sobel_filter
from network_protocol import receive_all, send_all
from server import run_server


class ProtocolTests(unittest.TestCase):
    def test_framed_message_round_trip(self) -> None:
        left, right = socket.socketpair()
        message = {"name": "fragment", "pixels": np.arange(24).reshape(4, 6)}

        with left, right:
            sender = threading.Thread(target=send_all, args=(left, message))
            sender.start()
            received = receive_all(right)
            sender.join(timeout=2.0)

        self.assertEqual(received["name"], message["name"])
        np.testing.assert_array_equal(received["pixels"], message["pixels"])


class DistributedIntegrationTests(unittest.TestCase):
    def test_two_clients_produce_expected_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            input_path = temp_dir / "input.png"
            output_path = temp_dir / "output.png"
            rng = np.random.default_rng(42)
            source = rng.integers(0, 256, size=(64, 80), dtype=np.uint8)
            Image.fromarray(source).save(input_path)

            ready: queue.Queue[int] = queue.Queue(maxsize=1)
            outcome: queue.Queue[BaseException | None] = queue.Queue(maxsize=1)

            def server_target() -> None:
                try:
                    run_server(
                        input_path=input_path,
                        output_path=output_path,
                        host="127.0.0.1",
                        port=0,
                        clients=2,
                        timeout=10.0,
                        ready_callback=ready.put,
                    )
                    outcome.put(None)
                except BaseException as error:
                    outcome.put(error)

            server_thread = threading.Thread(target=server_target, daemon=True)
            server_thread.start()
            port = ready.get(timeout=5.0)

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(run_client, "127.0.0.1", port, 10.0, 3, 0.05)
                    for _ in range(2)
                ]
                for future in futures:
                    future.result(timeout=15.0)

            server_thread.join(timeout=15.0)
            self.assertFalse(server_thread.is_alive())
            server_error = outcome.get_nowait()
            if server_error is not None:
                raise server_error

            result = np.asarray(Image.open(output_path).convert("L"))
            np.testing.assert_array_equal(result, sobel_filter(source))


if __name__ == "__main__":
    unittest.main()


"""Prosty protokol ramek TCP uzywany przez serwer i klienta.

Format jest zgodny z idea z instrukcji: czterobajtowy rozmiar w kolejnosci
big-endian, a po nim kompletna wiadomosc serializowana przez pickle.

Pickle nalezy stosowac tylko w zaufanej sieci laboratoryjnej, poniewaz odbior
danych z nieznanego zrodla moze wykonac zlosliwy kod podczas deserializacji.
"""

from __future__ import annotations

import pickle
import socket
import struct
from typing import Any


HEADER_SIZE = 4
MAX_MESSAGE_SIZE = 512 * 1024 * 1024
PROTOCOL_VERSION = 1


class ProtocolError(RuntimeError):
    """Blad formatu lub rozmiaru komunikatu."""


def receive_exact(sock: socket.socket, size: int) -> bytes:
    """Odbiera dokladnie `size` bajtow albo zglasza zerwanie polaczenia."""

    if size < 0:
        raise ValueError("Rozmiar danych nie moze byc ujemny.")

    chunks: list[bytes] = []
    received = 0
    while received < size:
        packet = sock.recv(min(65536, size - received))
        if not packet:
            raise ConnectionError(
                f"Polaczenie zamknieto po odebraniu {received} z {size} bajtow."
            )
        chunks.append(packet)
        received += len(packet)
    return b"".join(chunks)


def send_all(sock: socket.socket, data: Any) -> None:
    """Wysyla pelny obiekt poprzedzony jego czterobajtowym rozmiarem."""

    payload = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
    size = len(payload)
    if size > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"Komunikat jest za duzy: {size} bajtow.")
    sock.sendall(struct.pack("!I", size))
    sock.sendall(payload)


def receive_all(sock: socket.socket) -> Any:
    """Odbiera kompletna ramke i zwraca zdeserializowany obiekt."""

    header = receive_exact(sock, HEADER_SIZE)
    (size,) = struct.unpack("!I", header)
    if size > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"Odrzucono komunikat o rozmiarze {size} bajtow.")
    payload = receive_exact(sock, size)
    return pickle.loads(payload)


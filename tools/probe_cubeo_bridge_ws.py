#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import os
import socket
import struct
import time


GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
HOST = "127.0.0.1"


def redact(value):
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            lk = str(key).lower()
            if any(token in lk for token in ["token", "secret", "auth", "cookie", "session", "ticket"]):
                clean[key] = "<redacted>"
            else:
                clean[key] = redact(item)
        return clean
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def make_key():
    return base64.b64encode(os.urandom(16)).decode()


def encode_frame(text):
    payload = text.encode("utf-8")
    header = bytearray([0x81])
    n = len(payload)
    mask_bit = 0x80
    if n < 126:
        header.append(mask_bit | n)
    elif n < 65536:
        header.append(mask_bit | 126)
        header += struct.pack("!H", n)
    else:
        header.append(mask_bit | 127)
        header += struct.pack("!Q", n)
    mask = os.urandom(4)
    masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
    return bytes(header) + mask + masked


def recv_exact(sock, n):
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise EOFError
        data += chunk
    return bytes(data)


def recv_frame(sock):
    first = recv_exact(sock, 2)
    opcode = first[0] & 0x0F
    masked = first[1] & 0x80
    n = first[1] & 0x7F
    if n == 126:
        n = struct.unpack("!H", recv_exact(sock, 2))[0]
    elif n == 127:
        n = struct.unpack("!Q", recv_exact(sock, 8))[0]
    mask = recv_exact(sock, 4) if masked else b""
    payload = recv_exact(sock, n) if n else b""
    if masked:
        payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
    return opcode, payload.decode("utf-8", "replace")


def connect(port):
    key = make_key()
    sock = socket.create_connection((HOST, port), timeout=3)
    request = (
        f"GET / HTTP/1.1\r\n"
        f"Host: {HOST}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.sendall(request.encode())
    response = sock.recv(4096).decode("latin1", "replace")
    expected = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
    if "101" not in response or expected not in response:
        raise RuntimeError(f"WebSocket handshake failed: {response[:200]!r}")
    return sock


def send(sock, channel, data=None):
    msg = {"channel": channel, "data": data or {}}
    sock.sendall(encode_frame(json.dumps(msg, ensure_ascii=False)))
    print("SEND", redact(msg))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=23456)
    parser.add_argument("--listen-seconds", type=float, default=6.0)
    args = parser.parse_args()

    sock = connect(args.port)
    sock.settimeout(1)
    try:
        send(sock, "window-ready", {"reconnect": False})
        send(sock, "request-client-info", {})
        send(sock, "request-export-task-list", {})
        deadline = time.time() + args.listen_seconds
        while time.time() < deadline:
            try:
                opcode, text = recv_frame(sock)
            except socket.timeout:
                continue
            if opcode == 8:
                break
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                print("RECV_RAW", text[:500])
                continue
            print("RECV", json.dumps(redact(data), ensure_ascii=False)[:4000])
    finally:
        sock.close()


if __name__ == "__main__":
    main()

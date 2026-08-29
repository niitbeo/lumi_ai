#!/usr/bin/env python3
import base64
import hashlib
import os
import socket
import sqlite3
import struct
import subprocess
import sys
import threading
import time


APP = "/Applications/Kumoo.app/Contents/MacOS/export_helper"
HOST = "127.0.0.1"
PROJECT_ID = "b1687b6e1f9e4268a3c92529d1c4e3b2"
PROJECT_ITEM_ID = "82754b7e1448486d8dcc5ca54f13ce29"
EXPORT_DB = "/Users/nguyenletruong/Library/Caches/com.meitu.kumoo/ColorByte/.mt_cb/db/export.db"
SOURCE = "/Users/nguyenletruong/Desktop/Leien_Photo_AI/1783773107487-943323661_Leien.jpg"
PROJECT_DIR = (
    "/Users/nguyenletruong/Library/Caches/com.meitu.kumoo/ColorByte/.mt_cb/"
    "1280908080/.project/b1687b6e1f9e4268a3c92529d1c4e3b2"
)
ITEM_DIR = f"{PROJECT_DIR}/.items/{PROJECT_ITEM_ID}"
MATERIAL_DIR = f"{PROJECT_DIR}/.materials/5c1f841ef7fd4e75b6fba67480a1df77"
EFFECT_PARAM = "/private/tmp/cubeo_export_helper_effect_param.pb"
OUT = "/private/tmp/cubeo_export_helper_probe.png"
THUMB = "/private/tmp/cubeo_export_helper_probe_thumb.png"


def load_latest_export_item():
    with sqlite3.connect(EXPORT_DB) as con:
        con.text_factory = bytes
        con.row_factory = sqlite3.Row
        row = con.execute(
            """
            select export_item_id, export_id, project_id, project_item_id,
                   cast(src_uri as text) as src_uri, param
            from t_export_item
            where project_id = ? and project_item_id = ? and deleted = 0
            order by id desc limit 1
            """,
            (PROJECT_ID, PROJECT_ITEM_ID),
        ).fetchone()
    if row is None:
        raise RuntimeError("No export item found in Cubeo export.db")
    param = row["param"]
    if isinstance(param, str):
        param = param.encode("latin1")
    if not param:
        raise RuntimeError("Cubeo export item has empty effect param")
    with open(EFFECT_PARAM, "wb") as fh:
        fh.write(param)
    return {
        "export_item_id": row["export_item_id"].decode(),
        "export_id": row["export_id"].decode(),
        "project_id": row["project_id"].decode(),
        "project_item_id": row["project_item_id"].decode(),
        "src_uri": row["src_uri"].decode(),
    }


def varint(n):
    out = bytearray()
    while n > 0x7F:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)


def field_varint(num, value):
    return varint(num << 3) + varint(value)


def field_bytes(num, payload):
    if isinstance(payload, str):
        payload = payload.encode()
    return varint((num << 3) | 2) + varint(len(payload)) + payload


def export_task(task_type, client_id, export_item, material_work_dir=MATERIAL_DIR):
    msg = bytearray()
    msg += field_varint(1, task_type)
    msg += field_bytes(2, client_id)
    msg += field_bytes(3, export_item["project_id"])
    msg += field_bytes(4, export_item["project_item_id"])
    msg += field_bytes(5, export_item["export_id"])
    msg += field_bytes(6, export_item["export_item_id"])
    msg += field_bytes(7, export_item["src_uri"] or SOURCE)
    msg += field_bytes(8, OUT)
    msg += field_bytes(9, THUMB)
    msg += field_bytes(10, EFFECT_PARAM)
    msg += field_bytes(11, material_work_dir)
    msg += field_bytes(12, f"codex-{int(time.time() * 1000)}")
    msg += field_bytes(13, export_item["project_item_id"])
    msg += field_bytes(14, "")
    return bytes(msg)


def universal(index, payload):
    return field_varint(1, index) + field_bytes(2, payload)


def read_varint(buf, pos):
    shift = 0
    value = 0
    while pos < len(buf):
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, pos
        shift += 7
    return value, pos


def parse_proto(buf):
    pos = 0
    fields = []
    while pos < len(buf):
        key, pos = read_varint(buf, pos)
        num, wire = key >> 3, key & 7
        if wire == 0:
            val, pos = read_varint(buf, pos)
            fields.append((num, "varint", val))
        elif wire == 2:
            size, pos = read_varint(buf, pos)
            data = buf[pos : pos + size]
            pos += size
            try:
                text = data.decode("utf-8")
                if not all((ord(ch) >= 32 and ord(ch) < 127) for ch in text):
                    text = None
            except UnicodeDecodeError:
                text = None
            fields.append((num, "bytes", text if text is not None else data.hex()))
        else:
            fields.append((num, f"wire{wire}", None))
            break
    return fields


def frame(payload, opcode=2):
    header = bytearray([0x80 | opcode])
    n = len(payload)
    if n < 126:
        header.append(n)
    elif n < 65536:
        header.append(126)
        header += struct.pack("!H", n)
    else:
        header.append(127)
        header += struct.pack("!Q", n)
    return bytes(header) + payload


def recv_frame(conn):
    first = conn.recv(2)
    if not first:
        return None, b""
    opcode = first[0] & 0x0F
    masked = first[1] & 0x80
    n = first[1] & 0x7F
    if n == 126:
        n = struct.unpack("!H", conn.recv(2))[0]
    elif n == 127:
        n = struct.unpack("!Q", conn.recv(8))[0]
    mask = conn.recv(4) if masked else b""
    data = bytearray()
    while len(data) < n:
        chunk = conn.recv(n - len(data))
        if not chunk:
            break
        data += chunk
    if masked:
        data = bytearray(b ^ mask[i % 4] for i, b in enumerate(data))
    return opcode, bytes(data)


def serve_once(port, task_type, export_item, material_work_dir):
    client_id = str(int(time.time() * 1000))
    accepted = threading.Event()
    received = []

    def server():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((HOST, port))
            srv.listen(1)
            conn, _ = srv.accept()
            with conn:
                req = conn.recv(4096).decode("latin1", "replace")
                key = None
                for line in req.splitlines():
                    if line.lower().startswith("sec-websocket-key:"):
                        key = line.split(":", 1)[1].strip()
                if not key:
                    return
                accept = base64.b64encode(
                    hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
                ).decode()
                conn.sendall(
                    (
                        "HTTP/1.1 101 Switching Protocols\r\n"
                        "Upgrade: websocket\r\n"
                        "Connection: Upgrade\r\n"
                        f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
                    ).encode()
                )
                accepted.set()
                conn.sendall(frame(universal(0, export_task(task_type, client_id, export_item, material_work_dir))))
                conn.settimeout(20)
                end = time.time() + 20
                while time.time() < end:
                    try:
                        op, data = recv_frame(conn)
                    except socket.timeout:
                        break
                    if op is None:
                        break
                    parsed = parse_proto(data)
                    payload_fields = []
                    for num, typ, value in parsed:
                        if num == 2 and typ == "bytes" and isinstance(value, str):
                            try:
                                payload_fields = parse_proto(bytes.fromhex(value))
                            except ValueError:
                                payload_fields = []
                    received.append((op, data, parsed, payload_fields))
                    if op == 8:
                        break

    t = threading.Thread(target=server, daemon=True)
    t.start()
    proc = subprocess.Popen(
        [
            APP,
            "--mode",
            "export",
            "--server_ip",
            HOST,
            "--server_port",
            str(port),
            "--client_id",
            client_id,
            "--main_pid",
            str(os.getpid()),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(APP),
    )
    try:
        accepted.wait(5)
        try:
            stdout, stderr = proc.communicate(timeout=25)
        except subprocess.TimeoutExpired:
            proc.terminate()
            stdout, stderr = proc.communicate(timeout=5)
    finally:
        t.join(timeout=1)
    return {
        "task_type": task_type,
        "returncode": proc.returncode,
        "stdout": stdout.decode("utf-8", "replace"),
        "stderr": stderr.decode("utf-8", "replace"),
        "frames": [
            {
                "opcode": op,
                "len": len(data),
                "hex": data.hex(),
                "universal": parsed,
                "payload": payload_fields,
            }
            for op, data, parsed, payload_fields in received
        ],
        "out_exists": os.path.exists(OUT),
        "out_size": os.path.getsize(OUT) if os.path.exists(OUT) else 0,
    }


def main():
    export_item = load_latest_export_item()
    print({"using_export_item": export_item, "effect_param": EFFECT_PARAM, "effect_param_size": os.path.getsize(EFFECT_PARAM)})
    for path in (OUT, THUMB):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
    material_dirs = [MATERIAL_DIR, PROJECT_DIR, ITEM_DIR]
    for task_type in [0, 1, 2, 3, 4, 10, 100]:
        for material_work_dir in material_dirs:
            port = 55000 + task_type
            result = serve_once(port, task_type, export_item, material_work_dir)
            result["material_work_dir"] = material_work_dir
            print(result)
            if result["out_exists"] and result["out_size"] > 0:
                return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

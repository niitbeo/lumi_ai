#!/usr/bin/env python3
import argparse
import base64
import hashlib
import os
import socket
import sqlite3
import struct
import subprocess
import threading
import time
from pathlib import Path


APP = Path("/Applications/Kumoo.app/Contents/MacOS/export_helper")
HOST = "127.0.0.1"
PROJECT_ID = "b1687b6e1f9e4268a3c92529d1c4e3b2"
PROJECT_ITEM_ID = "82754b7e1448486d8dcc5ca54f13ce29"
EXPORT_DB = Path("/Users/nguyenletruong/Library/Caches/com.meitu.kumoo/ColorByte/.mt_cb/db/export.db")
PROJECT_DB = Path("/Users/nguyenletruong/Library/Caches/com.meitu.kumoo/ColorByte/.mt_cb/db/project.db")
SOURCE = "/Users/nguyenletruong/Desktop/Leien_Photo_AI/1783773107487-943323661_Leien.jpg"
PROJECT_DIR = (
    "/Users/nguyenletruong/Library/Caches/com.meitu.kumoo/ColorByte/.mt_cb/"
    "1280908080/.project/b1687b6e1f9e4268a3c92529d1c4e3b2"
)
MATERIAL_DIR = f"{PROJECT_DIR}/.materials/5c1f841ef7fd4e75b6fba67480a1df77"
OUT_DIR = Path("/private/tmp/cubeo_editor_probe")
OUT_DIR.mkdir(parents=True, exist_ok=True)


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
    fields = []
    pos = 0
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
            text = None
            try:
                decoded = data.decode("utf-8")
                if all(32 <= ord(ch) < 127 for ch in decoded):
                    text = decoded
            except UnicodeDecodeError:
                pass
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


def universal_index(parsed):
    for num, typ, value in parsed:
        if num == 1 and typ == "varint":
            return value
    return None


def universal(index, payload=b""):
    return field_varint(1, index) + field_bytes(2, payload)


def extract_payload(parsed):
    for num, typ, value in parsed:
        if num == 2 and typ == "bytes" and isinstance(value, str):
            try:
                return bytes.fromhex(value)
            except ValueError:
                return value.encode()
    return b""


def load_export_param():
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
        raise RuntimeError("No export item found")
    return row_to_item(row), bytes(row["param"])


def load_project_param():
    with sqlite3.connect(PROJECT_DB) as con:
        con.text_factory = bytes
        con.row_factory = sqlite3.Row
        row = con.execute(
            """
            select item_id as export_item_id, project_id, item_id as project_item_id,
                   cast(item_uri as text) as src_uri, effect_param
            from t_project_item
            where project_id = ? and item_id = ? and is_deleted = 0
            limit 1
            """,
            (PROJECT_ID, PROJECT_ITEM_ID),
        ).fetchone()
    if row is None:
        raise RuntimeError("No project item found")
    item = row_to_item(row)
    item["export_id"] = "codex-current-project"
    return item, bytes(row["effect_param"])


def row_to_item(row):
    item = {}
    for key in row.keys():
        val = row[key]
        if isinstance(val, bytes):
            val = val.decode("utf-8", "ignore")
        item[key] = val
    return item


def export_task(task_type, client_id, export_item, effect_param_path, output_path, thumb_path):
    msg = bytearray()
    msg += field_varint(1, task_type)
    msg += field_bytes(2, client_id)
    msg += field_bytes(3, export_item["project_id"])
    msg += field_bytes(4, export_item["project_item_id"])
    msg += field_bytes(5, export_item["export_id"])
    msg += field_bytes(6, export_item["export_item_id"])
    msg += field_bytes(7, export_item.get("src_uri") or SOURCE)
    msg += field_bytes(8, str(output_path))
    msg += field_bytes(9, str(thumb_path))
    msg += field_bytes(10, str(effect_param_path))
    msg += field_bytes(11, MATERIAL_DIR)
    msg += field_bytes(12, f"codex-{int(time.time() * 1000)}")
    msg += field_bytes(13, export_item["project_item_id"])
    msg += field_bytes(14, "")
    return bytes(msg)


def run_once(param_source, task_type, ack_mode, port, dyld_insert=None, app_path=APP):
    export_item, param = load_project_param() if param_source == "project" else load_export_param()
    effect_param_path = OUT_DIR / f"{param_source}_effect_param.pb"
    effect_param_path.write_bytes(param)
    output_path = OUT_DIR / f"{param_source}_task{task_type}_{ack_mode}.png"
    thumb_path = OUT_DIR / f"{param_source}_task{task_type}_{ack_mode}_thumb.png"
    for path in (output_path, thumb_path):
        path.unlink(missing_ok=True)

    client_id = str(int(time.time() * 1000))
    received = []
    accepted = threading.Event()

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
                conn.sendall(frame(universal(0, export_task(task_type, client_id, export_item, effect_param_path, output_path, thumb_path))))
                conn.settimeout(22)
                deadline = time.time() + 22
                while time.time() < deadline:
                    try:
                        op, data = recv_frame(conn)
                    except socket.timeout:
                        break
                    if op is None:
                        break
                    parsed = parse_proto(data)
                    payload = extract_payload(parsed)
                    payload_fields = parse_proto(payload) if payload else []
                    idx = universal_index(parsed)
                    received.append((op, idx, len(data), parsed, payload_fields))
                    if ack_mode == "echo" and idx == 3:
                        conn.sendall(frame(data))
                    elif ack_mode == "ack-empty" and idx == 3:
                        conn.sendall(frame(universal(3, b"")))
                    elif ack_mode == "ack4-payload" and idx == 3:
                        conn.sendall(frame(universal(4, payload)))
                    if op == 8:
                        break

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    child_env = os.environ.copy()
    if dyld_insert:
        child_env["DYLD_INSERT_LIBRARIES"] = dyld_insert
    proc = subprocess.Popen(
        [
            str(app_path),
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
        cwd=str(app_path.parent),
        env=child_env,
    )
    accepted.wait(5)
    try:
        stdout, stderr = proc.communicate(timeout=28)
    except subprocess.TimeoutExpired:
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=5)
    thread.join(timeout=1)

    print(
        {
            "param_source": param_source,
            "param_size": len(param),
            "task_type": task_type,
            "ack_mode": ack_mode,
            "returncode": proc.returncode,
            "out_exists": output_path.exists(),
            "out_size": output_path.stat().st_size if output_path.exists() else 0,
            "thumb_exists": thumb_path.exists(),
            "frames": [
                {
                    "opcode": op,
                    "index": idx,
                    "len": size,
                    "universal": parsed,
                    "payload": payload_fields,
                }
                for op, idx, size, parsed, payload_fields in received
            ],
            "stdout_tail": stdout.decode("utf-8", "replace")[-1200:],
            "stderr_tail": stderr.decode("utf-8", "replace")[-1200:],
        }
    )
    return output_path.exists() and output_path.stat().st_size > 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--param-source", choices=["export", "project"], default="project")
    parser.add_argument("--task-type", type=int, default=1)
    parser.add_argument("--ack-mode", choices=["none", "echo", "ack-empty", "ack4-payload"], default="none")
    parser.add_argument("--port", type=int, default=55111)
    parser.add_argument("--dyld-insert")
    parser.add_argument("--app-path", type=Path, default=APP)
    args = parser.parse_args()
    return 0 if run_once(args.param_source, args.task_type, args.ack_mode, args.port, args.dyld_insert, args.app_path) else 1


if __name__ == "__main__":
    raise SystemExit(main())

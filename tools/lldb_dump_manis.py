import hashlib
import os
import re
import time

import lldb


DUMP_DIR = os.environ.get("CUBEO_MODEL_DUMP_DIR", "/private/tmp/cubeo_model_dump")
MAX_DUMP = 1024 * 1024 * 1024
_seen = set()


def _log(message):
    os.makedirs(DUMP_DIR, exist_ok=True)
    with open(os.path.join(DUMP_DIR, "lldb_trace.log"), "a", encoding="utf-8") as f:
        f.write(message + "\n")


def _safe_name(value):
    value = value or "unknown"
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value[:180]


def _read_reg(frame, name):
    reg = frame.FindRegister(name)
    if not reg.IsValid():
        return 0
    return reg.GetValueAsUnsigned()


def dump_arg0_size_arg1(frame, bp_loc, internal_dict):
    process = frame.GetThread().GetProcess()
    symbol = frame.GetDisplayFunctionName() or frame.GetFunctionName() or "manis"
    ptr = _read_reg(frame, "x0")
    size = _read_reg(frame, "x1")
    if not ptr or not size or size > MAX_DUMP:
        _log(f"skip {symbol} ptr=0x{ptr:x} size={size}")
        return False

    error = lldb.SBError()
    data = process.ReadMemory(ptr, size, error)
    if not error.Success() or not data:
        _log(f"read-fail {symbol} ptr=0x{ptr:x} size={size} err={error.GetCString()}")
        return False

    digest = hashlib.sha256(data).hexdigest()[:20]
    key = f"{symbol}:{size}:{digest}"
    if key in _seen:
        return False
    _seen.add(key)

    os.makedirs(DUMP_DIR, exist_ok=True)
    out = os.path.join(
        DUMP_DIR,
        f"lldb_{_safe_name(symbol)}_{size}_{digest}_{int(time.time() * 1000)}.bin",
    )
    with open(out, "wb") as f:
        f.write(data)
    _log(
        f"dump {symbol} ptr=0x{ptr:x} size={size} sha256={digest} "
        f"first16={data[:16].hex()} out={out}"
    )
    return False


def __lldb_init_module(debugger, internal_dict):
    _log("lldb_dump_manis loaded")

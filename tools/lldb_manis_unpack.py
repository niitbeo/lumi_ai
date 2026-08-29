import hashlib
import os
import struct
from pathlib import Path

import lldb


DUMP_DIR = os.environ.get(
    "CUBEO_MANIS_UNPACK_DIR", "/private/tmp/cubeo_manis_unpack"
)
MAX_POINTER_DUMP = 16 * 1024 * 1024
MINIMAL = os.environ.get("CUBEO_MANIS_MINIMAL", "0") == "1"
_installed = False
_dumped = set()
_decoder_outputs = None
_current_model = "unknown"
_model_hashes = None


def _log(message):
    os.makedirs(DUMP_DIR, exist_ok=True)
    with open(os.path.join(DUMP_DIR, "trace.log"), "a", encoding="utf-8") as out:
        out.write(message + "\n")


def _safe_name(value):
    return "".join(
        ch if ch.isalnum() or ch in ".-_" else "_" for ch in value
    )[:220]


def _load_model_hashes():
    global _model_hashes
    if _model_hashes is not None:
        return
    root = Path(
        os.environ.get(
            "CUBEO_MANIS_ROOT",
            "/Users/nguyenletruong/cubeo-ai/megatron_extracted/megatron",
        )
    )
    _model_hashes = {}
    for path in root.rglob("*"):
        if path.suffix.lower() not in {".manis", ".manisa"} or not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        _model_hashes[digest] = str(path.relative_to(root))
    _log(f"indexed_models count={len(_model_hashes)} root={root}")


def _reg(frame, name):
    value = frame.FindRegister(name)
    return value.GetValueAsUnsigned() if value.IsValid() else 0


def _read(process, address, size):
    if not address or not size:
        return b""
    error = lldb.SBError()
    data = process.ReadMemory(address, size, error)
    if not error.Success():
        return b""
    return data


def _dump(process, label, address, size):
    data = _read(process, address, size)
    if not data:
        _log(f"read_failed label={label} address=0x{address:x} size={size}")
        return
    digest = hashlib.sha256(data).hexdigest()
    key = (address, len(data), digest)
    if key in _dumped:
        return
    _dumped.add(key)
    path = os.path.join(
        DUMP_DIR, f"{label}_{address:x}_{len(data)}_{digest[:16]}.bin"
    )
    with open(path, "wb") as out:
        out.write(data)
    _log(
        f"dump label={label} address=0x{address:x} size={len(data)} "
        f"sha256={digest} first32={data[:32].hex()} path={path}"
    )


def _dump_decoded_model(process, address, size, model_name):
    data = _read(process, address, size)
    if not data:
        _log(
            f"decoded_model_read_failed model={model_name} "
            f"address=0x{address:x} size={size}"
        )
        return

    relative = Path(model_name)
    if relative.is_absolute() or ".." in relative.parts:
        relative = Path(_safe_name(model_name))
    
    digest = hashlib.sha256(data).hexdigest()
    if model_name.startswith("unknown_"):
        relative = Path(f"unknown_{len(data)}_{digest[:16]}")
        
    output = Path(DUMP_DIR) / relative
    output = output.with_suffix(output.suffix + ".decoded")
    output.parent.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256(data).hexdigest()
    if output.exists() and output.read_bytes() == data:
        state = "unchanged"
    else:
        output.write_bytes(data)
        state = "written"
    _log(
        f"decoded_model state={state} model={model_name} "
        f"address=0x{address:x} size={len(data)} sha256={digest} "
        f"first32={data[:32].hex()} path={output}"
    )


def _module_base(target):
    for module in target.modules:
        if module.file.basename == "Manis":
            return module.GetObjectFileHeaderAddress().GetLoadAddress(target)
    return lldb.LLDB_INVALID_ADDRESS


def _dump_pointer_targets(process, owner_label, owner_address, owner_size):
    owner = _read(process, owner_address, owner_size)
    if not owner:
        return
    for offset in range(0, len(owner) - 7, 8):
        pointer = struct.unpack_from("<Q", owner, offset)[0]
        if pointer < 0x10000:
            continue
        region = lldb.SBMemoryRegionInfo()
        error = process.GetMemoryRegionInfo(pointer, region)
        if not error.Success() or not region.IsReadable() or region.IsExecutable():
            continue
        available = region.GetRegionEnd() - pointer
        if available <= 0:
            continue
        size = min(available, MAX_POINTER_DUMP)
        _dump(process, f"{owner_label}_off_{offset:03x}", pointer, size)


def _dump_libcxx_string(process, label, address):
    raw = _read(process, address, 24)
    if len(raw) != 24:
        _log(f"string_read_failed label={label} object=0x{address:x}")
        return
    short_size = raw[23]
    if short_size < 0x80:
        size = short_size
        pointer = address
        kind = "short"
    else:
        pointer, size = struct.unpack_from("<QQ", raw, 0)
        kind = "long"
    _log(
        f"string label={label} kind={kind} object=0x{address:x} "
        f"pointer=0x{pointer:x} size={size} raw={raw.hex()}"
    )
    if 0 < size <= 1024 * 1024 * 1024:
        _dump(process, label, pointer, size)


def before_parser_call(frame, bp_loc, internal_dict):
    process = frame.GetThread().GetProcess()
    parser = _reg(frame, "x21")
    method = _reg(frame, "x8")
    model = _reg(frame, "x20")
    size = _reg(frame, "x19")
    _log(
        f"before_parser parser=0x{parser:x} method=0x{method:x} "
        f"model=0x{model:x} size={size}"
    )
    return False


def after_parser_call(frame, bp_loc, internal_dict):
    process = frame.GetThread().GetProcess()
    parser = _reg(frame, "x21")
    stack = _reg(frame, "sp")
    result = _reg(frame, "x0")
    _log(f"after_parser result={result} parser=0x{parser:x} sp=0x{stack:x}")

    if MINIMAL:
        return False

    _dump(process, "parser_object", parser, 0x200)
    _dump(process, "cache_stack", stack, 0x130)
    _dump_pointer_targets(process, "parser_ptr", parser, 0x100)

    output_pair = _read(process, stack + 0x58, 16)
    if len(output_pair) == 16:
        object_pointer, control_pointer = struct.unpack("<QQ", output_pair)
        _log(
            f"parser_output object=0x{object_pointer:x} "
            f"control=0x{control_pointer:x}"
        )
        _dump(process, "parser_output_object", object_pointer, 0x400)
        _dump_pointer_targets(process, "output_ptr", object_pointer, 0x200)
    return False


def before_unpack_call(frame, bp_loc, internal_dict):
    parser_impl = _reg(frame, "x0")
    method = _reg(frame, "x8")
    model = _reg(frame, "x22")
    size = _reg(frame, "x20")
    _log(
        f"before_unpack impl=0x{parser_impl:x} method=0x{method:x} "
        f"model=0x{model:x} size={size}"
    )
    return False


def after_unpack_call(frame, bp_loc, internal_dict):
    process = frame.GetThread().GetProcess()
    outer_parser = _reg(frame, "x19")
    result = _reg(frame, "x0")
    raw = _read(process, outer_parser + 0x38, 8)
    parser_impl = struct.unpack("<Q", raw)[0] if len(raw) == 8 else 0
    _log(
        f"after_unpack result={result} outer=0x{outer_parser:x} "
        f"impl=0x{parser_impl:x}"
    )
    if MINIMAL:
        return False
    _dump(process, "unpack_impl", parser_impl, 0x400)
    _dump_pointer_targets(process, "unpack_ptr", parser_impl, 0x300)
    return False


def before_decoder_call(frame, bp_loc, internal_dict):
    global _decoder_outputs
    method = _reg(frame, "x8")
    payload = _reg(frame, "x1")
    size = _reg(frame, "x2")
    output_a = _reg(frame, "x3")
    output_b = _reg(frame, "x4")
    _decoder_outputs = (output_a, output_b)
    _log(
        f"before_decoder method=0x{method:x} payload=0x{payload:x} "
        f"size={size} output_a=0x{output_a:x} output_b=0x{output_b:x}"
    )
    process = frame.GetThread().GetProcess()
    _dump_decoded_model(process, payload, size, _current_model)
    return False


def after_decoder_call(frame, bp_loc, internal_dict):
    process = frame.GetThread().GetProcess()
    result = _reg(frame, "x0")
    _log(f"after_decoder result={result}")
    if MINIMAL:
        return False
    if _decoder_outputs:
        output_a, output_b = _decoder_outputs
        _dump_libcxx_string(process, "decoded_a", output_a)
        _dump_libcxx_string(process, "decoded_b", output_b)
    return False


def install_breakpoints(frame, bp_loc, internal_dict):
    global _installed, _current_model
    process = frame.GetThread().GetProcess()
    model_pointer = _reg(frame, "x0")
    model_size = _reg(frame, "x1")
    model_data = _read(process, model_pointer, model_size)
    _load_model_hashes()
    model_digest = hashlib.sha256(model_data).hexdigest() if model_data else ""
    _current_model = _model_hashes.get(model_digest, f"unknown_{model_digest[:16]}")
    _log(
        f"cache_entry model={_current_model} pointer=0x{model_pointer:x} "
        f"size={model_size} sha256={model_digest}"
    )
    if _installed:
        return False
    target = frame.GetThread().GetProcess().GetTarget()
    base = _module_base(target)
    if base == lldb.LLDB_INVALID_ADDRESS:
        _log("Manis module base unavailable")
        return False

    before = target.BreakpointCreateByAddress(base + 0x5A1220)
    before.SetScriptCallbackFunction(
        "lldb_manis_unpack.before_parser_call"
    )
    after = target.BreakpointCreateByAddress(base + 0x5A1224)
    after.SetScriptCallbackFunction(
        "lldb_manis_unpack.after_parser_call"
    )
    unpack_before = target.BreakpointCreateByAddress(base + 0x5A47B0)
    unpack_before.SetScriptCallbackFunction(
        "lldb_manis_unpack.before_unpack_call"
    )
    unpack_after = target.BreakpointCreateByAddress(base + 0x5A47B4)
    unpack_after.SetScriptCallbackFunction(
        "lldb_manis_unpack.after_unpack_call"
    )
    decoder_before = target.BreakpointCreateByAddress(base + 0x1D2914)
    decoder_before.SetScriptCallbackFunction(
        "lldb_manis_unpack.before_decoder_call"
    )
    decoder_after = target.BreakpointCreateByAddress(base + 0x1D2918)
    decoder_after.SetScriptCallbackFunction(
        "lldb_manis_unpack.after_decoder_call"
    )
    _installed = True
    _log(
        f"installed base=0x{base:x} before_id={before.GetID()} "
        f"after_id={after.GetID()} unpack_before_id={unpack_before.GetID()} "
        f"unpack_after_id={unpack_after.GetID()} "
        f"decoder_before_id={decoder_before.GetID()} "
        f"decoder_after_id={decoder_after.GetID()}"
    )
    return False


def __lldb_init_module(debugger, internal_dict):
    target = debugger.GetSelectedTarget()
    breakpoint = target.BreakpointCreateByName("manis::CacheModel")
    breakpoint.SetScriptCallbackFunction("lldb_manis_unpack.install_breakpoints")
    
    breakpoint2 = target.BreakpointCreateByName("manis::Net::CreateNet")
    breakpoint2.SetScriptCallbackFunction("lldb_manis_unpack.install_breakpoints")
    
    _log(f"entry_breakpoint_id={breakpoint.GetID()} entry2={breakpoint2.GetID()}")

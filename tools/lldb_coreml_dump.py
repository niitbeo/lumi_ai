import hashlib
import os
from pathlib import Path

import lldb


DUMP_DIR = Path(os.environ.get(
    "CUBEO_COREML_DUMP_DIR", "/private/tmp/cubeo_coreml_dump"
))
ROOT = Path(os.environ.get(
    "CUBEO_MANIS_ROOT",
    "/Users/nguyenletruong/cubeo-ai/megatron_extracted/megatron",
))
_installed = False
_model_hashes = None
_current_model = "unknown.manisa"


def _log(message):
    DUMP_DIR.mkdir(parents=True, exist_ok=True)
    with (DUMP_DIR / "trace.log").open("a", encoding="utf-8") as output:
        output.write(message + "\n")


def _reg(frame, name):
    value = frame.FindRegister(name)
    return value.GetValueAsUnsigned() if value.IsValid() else 0


def _read(process, address, size):
    error = lldb.SBError()
    data = process.ReadMemory(address, size, error)
    return data if error.Success() else b""


def _module_base(target):
    for module in target.modules:
        if module.file.basename == "Manis":
            return module.GetObjectFileHeaderAddress().GetLoadAddress(target)
    return lldb.LLDB_INVALID_ADDRESS


def capture_model_path(frame, bp_loc, internal_dict):
    global _current_model
    process = frame.GetThread().GetProcess()
    pointer = _reg(frame, "x1")
    error = lldb.SBError()
    path_value = process.ReadCStringFromMemory(pointer, 4096, error)
    if error.Success() and path_value:
        path = Path(path_value)
        try:
            _current_model = str(path.relative_to(ROOT))
        except ValueError:
            _current_model = path.name
    _log(f"model_path model={_current_model} address=0x{pointer:x}")
    return False


def _load_hashes():
    global _model_hashes
    if _model_hashes is not None:
        return
    _model_hashes = {}
    for path in ROOT.rglob("*.manisa"):
        data = path.read_bytes()
        relative = path.relative_to(ROOT)
        for offset in (0, 24, 42, 44, 62):
            if offset < len(data):
                digest = hashlib.sha256(data[offset:]).hexdigest()
                _model_hashes[digest] = relative
    _log(f"indexed_models count={len(_model_hashes)} root={ROOT}")


def capture_coreml_input(frame, bp_loc, internal_dict):
    process = frame.GetThread().GetProcess()
    object_pointer = _reg(frame, "x2")
    declared_size = _reg(frame, "x3") & 0xFFFFFFFF
    options = lldb.SBExpressionOptions()
    options.SetLanguage(lldb.eLanguageTypeObjC_plus_plus)
    value = frame.EvaluateExpression(
        f"(void*)[(id){object_pointer:#x} bytes]", options
    )
    pointer = value.GetValueAsUnsigned() if value.IsValid() else 0
    size = declared_size
    data = _read(process, pointer, size)
    digest = hashlib.sha256(data).hexdigest() if data else ""
    _load_hashes()
    model = _model_hashes.get(digest)
    name = _current_model if _current_model != "unknown.manisa" else (
        str(model) if model else f"unknown_{digest[:16]}.manisa"
    )
    output = DUMP_DIR / name
    output = output.with_suffix(output.suffix + ".mlmodel")
    output.parent.mkdir(parents=True, exist_ok=True)
    if data:
        output.write_bytes(data)
    _log(
        f"coreml_input model={name} object=0x{object_pointer:x} "
        f"address=0x{pointer:x} declared_size={declared_size} size={len(data)} "
        f"sha256={digest} first32={data[:32].hex()} path={output}"
    )
    return False


def install(frame, bp_loc, internal_dict):
    global _installed
    if _installed:
        return False
    target = frame.GetThread().GetProcess().GetTarget()
    base = _module_base(target)
    if base == lldb.LLDB_INVALID_ADDRESS:
        _log("Manis module base unavailable")
        return False
    breakpoint = target.BreakpointCreateByAddress(base + 0x217674)
    breakpoint.SetScriptCallbackFunction(
        "lldb_coreml_dump.capture_coreml_input"
    )
    model_path_breakpoint = target.BreakpointCreateByAddress(base + 0x5A7978)
    model_path_breakpoint.SetScriptCallbackFunction(
        "lldb_coreml_dump.capture_model_path"
    )
    _installed = True
    _log(
        f"installed base=0x{base:x} coreml_input_id={breakpoint.GetID()} "
        f"model_path_id={model_path_breakpoint.GetID()}"
    )
    return False


def __lldb_init_module(debugger, internal_dict):
    target = debugger.GetSelectedTarget()
    breakpoint = target.BreakpointCreateByName(
        "_ZN5manis3Net9CreateNetEPNS_13ExtendOptionsE"
    )
    breakpoint.SetScriptCallbackFunction("lldb_coreml_dump.install")
    _log(f"entry_breakpoint_id={breakpoint.GetID()}")

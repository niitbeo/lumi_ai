import lldb

def free_hook(frame, bp_loc, dict):
    target = frame.GetThread().GetProcess().GetTarget()
    process = frame.GetThread().GetProcess()
    arg1 = frame.FindRegister("x0").GetValueAsUnsigned()
    
    # Evaluate malloc_size
    expr = f"(size_t)malloc_size({arg1})"
    res = target.EvaluateExpression(expr)
    if res.GetError().Success():
        size = res.GetValueAsUnsigned()
        if size > 7000000 and size < 8000000:
            print(f"FOUND 7MB BUFFER AT 0x{arg1:x} size {size}!")
            # Dump it
            error = lldb.SBError()
            data = process.ReadMemory(arg1, size, error)
            if error.Success():
                with open(f"/tmp/seamer_dump/dump_{size}.bin", "wb") as f:
                    f.write(data)
                print("DUMPED!")
    return False

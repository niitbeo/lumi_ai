-- @author: tbx
ui = {}

paramTable = {}
paramTable["default"] = {
    p_clearDpeth = {
        ui_type = "slider", ui_name = "clearDepth", value = 0.5, min = 0.0, max = 1.0, precision = 2, targetNodeID = 1, nodeParam = "bp_setClearDepth"
    },
    p_enableClearColor = {
        ui_type = "switch", ui_name = "clearColor", value = false, targetNodeID = 1, nodeParam = "bp_setClearColorEnable"
    }
}

return { ui = ui, paramTable = paramTable}
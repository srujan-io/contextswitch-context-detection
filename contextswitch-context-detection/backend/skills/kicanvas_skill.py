from .base import WebsiteSkill, Action, Parameter

class KiCanvasSkill(WebsiteSkill):
    website_id = "kicanvas"
    name = "KiCanvas"
    actions = {
        "zoom_in": Action("Zoom into the schematic.", ["schematic_viewer"], ["schematic_canvas"], gestures=["hand","voice"]),
        "zoom_out": Action("Zoom out of the schematic.", ["schematic_viewer"], ["schematic_canvas"], gestures=["hand","voice"]),
        "pan": Action("Move around the schematic canvas.", ["schematic_viewer"], ["schematic_canvas"], [Parameter("direction","string",choices=["up","down","left","right"])], ["hand","head"]),
        "search_component": Action("Find a component in the schematic.", ["schematic_viewer"], ["component_search"], [Parameter("query","string")], ["voice"], True),
        "view_component_details": Action("Show details for a component.", ["schematic_viewer"], ["component"], [Parameter("reference","string")], ["voice","hand"])
    }

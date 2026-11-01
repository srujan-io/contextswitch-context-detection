from .base import WebsiteSkill, Action, Parameter

class GenericBrowserSkill(WebsiteSkill):
    website_id = "generic"
    name = "Generic Browser"
    actions = {
        "scroll_page": Action("Scroll a webpage.", ["*"], ["page"], [Parameter("direction","string",choices=["up","down"])], ["head","hand"]),
        "zoom_page": Action("Change page zoom.", ["*"], ["page"], [Parameter("direction","string",choices=["in","out","reset"])], ["hand","voice"]),
        "find_text": Action("Find text on the current page.", ["*"], ["page"], [Parameter("query","string")], ["voice"], True),
        "navigate_back": Action("Navigate to previous browser history entry.", ["*"], ["browser"], gestures=["voice","hand"], confirmation=True)
    }

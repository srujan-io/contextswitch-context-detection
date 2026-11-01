from .kicanvas_skill import KiCanvasSkill
from .youtube_skill import YouTubeSkill
from .generic_skill import GenericBrowserSkill

class WebsiteSkillRouter:
    def __init__(self):
        self.registry = {
            "kicanvas": KiCanvasSkill(),
            "youtube": YouTubeSkill(),
            "generic": GenericBrowserSkill()
        }

    def get_skill(self, website_id):
        return self.registry.get(website_id, self.registry["generic"])

    def route(self, context):
        skill = self.get_skill(context.get("website_id", "unknown"))
        return {
            "website_id": context.get("website_id", "unknown"),
            "skill_id": skill.website_id,
            "skill_name": skill.name,
            "page_type": context.get("page_type", "unknown"),
            "skill_pack": skill.describe()
        }

    def validate_action(self, context, action, parameters=None, target=None):
        skill = self.get_skill(context.get("website_id", "unknown"))
        return skill.validate(action, parameters or {}, target, context.get("page_type", "unknown"))

from dataclasses import dataclass, field

@dataclass
class Parameter:
    name: str
    kind: str
    required: bool = True
    minimum: float | None = None
    maximum: float | None = None
    choices: list[str] = field(default_factory=list)

@dataclass
class Action:
    description: str
    pages: list[str]
    targets: list[str]
    parameters: list[Parameter] = field(default_factory=list)
    gestures: list[str] = field(default_factory=list)
    confirmation: bool = False

class WebsiteSkill:
    website_id = "generic"
    name = "Generic Browser"
    actions = {}

    def describe(self):
        return {
            "website_id": self.website_id,
            "website_name": self.name,
            "actions": {
                key: {
                    "description": a.description,
                    "page_types": a.pages,
                    "valid_targets": a.targets,
                    "parameters": [p.__dict__ for p in a.parameters],
                    "gesture_mappings": a.gestures,
                    "requires_confirmation": a.confirmation
                } for key, a in self.actions.items()
            }
        }

    def validate(self, action_name, params, target, page_type):
        a = self.actions.get(action_name)
        if not a:
            return {"valid": False, "reason": "Action is not supported by this website skill."}
        if "*" not in a.pages and page_type not in a.pages:
            return {"valid": False, "reason": "Action is not supported on this page type."}
        if a.targets and target not in a.targets:
            return {"valid": False, "reason": "Invalid action target."}
        allowed = {p.name for p in a.parameters}
        if set(params) - allowed:
            return {"valid": False, "reason": "Unexpected parameters supplied."}
        for p in a.parameters:
            v = params.get(p.name)
            if v is None:
                if p.required:
                    return {"valid": False, "reason": f"Missing parameter: {p.name}"}
                continue
            if p.kind == "integer" and (not isinstance(v, int) or isinstance(v, bool)):
                return {"valid": False, "reason": f"{p.name} must be an integer."}
            if p.kind == "number" and (not isinstance(v, (int,float)) or isinstance(v,bool)):
                return {"valid": False, "reason": f"{p.name} must be numeric."}
            if p.kind == "string" and not isinstance(v, str):
                return {"valid": False, "reason": f"{p.name} must be text."}
            if p.minimum is not None and v < p.minimum:
                return {"valid": False, "reason": f"{p.name} is below its allowed minimum."}
            if p.maximum is not None and v > p.maximum:
                return {"valid": False, "reason": f"{p.name} exceeds its allowed maximum."}
            if p.choices and v not in p.choices:
                return {"valid": False, "reason": f"{p.name} has an unsupported value."}
        return {"valid": True, "action": action_name, "target": target,
                "parameters": params, "requires_confirmation": a.confirmation}

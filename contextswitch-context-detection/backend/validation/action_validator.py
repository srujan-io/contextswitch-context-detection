
from typing import Any

from pydantic import BaseModel, Field

from skills.router import WebsiteSkillRouter


MAX_PLAN_STEPS = 5


class ValidationRequest(BaseModel):
    """
    Receives the action plan produced by Module C.
    user_approved should only be True after explicit user approval.
    """

    plan: dict[str, Any]
    context: dict[str, Any]
    user_approved: bool = False


class ActionValidator:

    def __init__(
        self,
        skill_router: WebsiteSkillRouter,
        max_steps: int = MAX_PLAN_STEPS
    ):
        self.skill_router = skill_router
        self.max_steps = max_steps

    def validate_plan(
        self,
        plan: dict,
        context: dict,
        user_approved: bool = False
    ) -> dict:

        website_id = context.get("website_id")
        page_type = context.get("page_type")

        # 1. Check that website context exists.
        if not website_id:
            raise ValueError("Missing website_id in context.")

        if not page_type:
            raise ValueError("Missing page_type in context.")

        # 2. Check that the website has a registered skill.
        if website_id not in self.skill_router.registry:
            raise ValueError(
                f"No website skill registered for: {website_id}"
            )

        skill = self.skill_router.get_skill(website_id)

        # 3. Check that the plan belongs to the active website.
        if plan.get("website") != skill.website_id:
            raise ValueError(
                "The plan website does not match the active website."
            )

        # 4. Check the steps.
        steps = plan.get("steps")

        if not isinstance(steps, list) or not steps:
            raise ValueError("The plan must contain at least one step.")

        # 5. Restrict the number of steps.
        if len(steps) > self.max_steps:
            raise ValueError(
                f"Too many steps. Maximum allowed is {self.max_steps}."
            )

        validated_steps = []
        confirmation_steps = []

        # 6. Validate every action in the plan.
        for index, step in enumerate(steps):

            if not isinstance(step, dict):
                raise ValueError(
                    f"Step {index + 1} must be an object."
                )

            action_name = step.get("action")
            parameters = step.get("parameters", {})
            target = step.get("target")

            # Check action name.
            if not isinstance(action_name, str) or not action_name:
                raise ValueError(
                    f"Step {index + 1} has an invalid action name."
                )

            # Check parameters.
            if not isinstance(parameters, dict):
                raise ValueError(
                    f"Parameters for step {index + 1} must be an object."
                )

            # 7. Verify that the action exists in the website skill.
            action_definition = skill.actions.get(action_name)

            if action_definition is None:
                raise ValueError(
                    f"Unsupported action '{action_name}' "
                    f"for website '{website_id}'."
                )

            # 8. Verify that the current page supports the action.
            allowed_pages = action_definition.pages

            if "*" not in allowed_pages and page_type not in allowed_pages:
                raise ValueError(
                    f"Action '{action_name}' is not supported "
                    f"on page type '{page_type}'."
                )

            # 9. Validate the target identifier.
            allowed_targets = action_definition.targets

            if not allowed_targets:
                if target is not None:
                    raise ValueError(
                        f"Action '{action_name}' does not accept a target."
                    )
            else:
                if target is None and len(allowed_targets) == 1:
                    target = allowed_targets[0]

                if target not in allowed_targets:
                    raise ValueError(
                        f"Invalid target '{target}' for action "
                        f"'{action_name}'. Allowed targets: {allowed_targets}"
                    )

            # 10. Reuse Module B's parameter validation.
            result = skill.validate(
                action_name=action_name,
                params=parameters,
                target=target,
                page_type=page_type
            )

            if not result.get("valid"):
                raise ValueError(
                    f"Step {index + 1} failed validation: "
                    f"{result.get('reason', 'Unknown validation error')}"
                )

            # 11. Get confirmation requirement from Module B.
            requires_confirmation = result.get(
                "requires_confirmation",
                action_definition.confirmation
            )

            validated_step = {
                "action": action_name,
                "parameters": result.get("parameters", parameters),
                "target": target,
                "requires_confirmation": requires_confirmation
            }

            validated_steps.append(validated_step)

            if requires_confirmation:
                confirmation_steps.append(index + 1)

        # 12. Do not allow execution until confirmation is provided.
        approval_required = len(confirmation_steps) > 0

        execution_ready = (
            not approval_required or user_approved
        )

        return {
            "website": skill.website_id,
            "intent": plan.get("intent", ""),
            "status": (
                "ready_for_execution"
                if execution_ready
                else "awaiting_confirmation"
            ),
            "valid": True,
            "total_steps": len(validated_steps),
            "max_steps": self.max_steps,
            "approval_required": approval_required,
            "user_approved": user_approved,
            "confirmation_steps": confirmation_steps,
            "execution_ready": execution_ready,
            "validated_steps": validated_steps
        }

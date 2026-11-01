
import os
import json
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .schemas import (
    ActionPlan,
    PlannerOutput
)

load_dotenv()


class IntentPlanner:

    def __init__(self, skill_router):

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is missing. "
                "Check your backend .env file."
            )

        self.client = genai.Client(api_key=api_key)

        self.model = os.getenv(
            "GEMINI_MODEL",
            "gemini-2.5-flash"
        )

        self.skill_router = skill_router

    # --------------------------------------------------
    # HELPER: EXTRACT COMPONENT REFERENCES
    # --------------------------------------------------

    @staticmethod
    def extract_component_reference(text):

        if not isinstance(text, str):
            return None

        match = re.search(
            r"\b[A-Za-z]{1,3}\s*\d+[A-Za-z]?\b",
            text
        )

        if match:
            return match.group(0).replace(" ", "")

        return None

    # --------------------------------------------------
    # HELPER: GET CURRENTLY SELECTED COMPONENT
    # --------------------------------------------------

    @staticmethod
    def get_selected_component(page_metadata, session_state):

        candidates = [
            page_metadata.get("selected_component"),
            session_state.get("selected_component"),
            session_state.get("current_component")
        ]

        for candidate in candidates:

            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

            if isinstance(candidate, dict):

                reference = (
                    candidate.get("reference")
                    or candidate.get("ref")
                    or candidate.get("designator")
                )

                if reference:
                    return str(reference)

        return None

    # --------------------------------------------------
    # MODULE C: CREATE ACTION PLAN
    # --------------------------------------------------

    def create_plan(
        self,
        command,
        context,
        page_metadata=None,
        session_state=None
    ):

        page_metadata = page_metadata or {}
        session_state = session_state or {}

        # 1. Identify active website through Module B

        website_id = context.get("website_id", "unknown")

        skill = self.skill_router.get_skill(website_id)

        # 2. Retrieve available website actions

        skill_description = skill.describe()

        # 3. Prepare complete planner input

        planner_input = {
            "user_command": command,
            "website_context": context,
            "available_skill": skill_description,
            "page_metadata": page_metadata,
            "session_state": session_state
        }

        # 4. Gemini instructions

        prompt = """
You are the Intent and Planning Agent for Beyond Touch.

YOUR RESPONSIBILITY:

Understand the user's natural-language command and
convert it into an ordered action plan.

You do not execute browser actions.

INPUT INFORMATION:

You receive:
1. User command.
2. Active website context.
3. Available actions from Module B.
4. Page metadata.
5. Current session state.

STRICT RULES:

1. Use only exact action names provided in available_skill.

2. Never invent or rename actions.

3. Use only parameters defined for the selected action.

4. Extract component references correctly.

5. Use page metadata and session state to understand
   references such as:
   "it", "that component", "the selected component"
   and "show its details".

6. If the user requests multiple tasks, create multiple
   ordered steps.

7. Preserve the order of requested operations.

8. For example:

   User: "Find C101 and show its details."

   Step 1:
   action = search_component
   query = C101

   Step 2:
   action = view_component_details
   reference = C101

9. Do not generate duplicate actions.

10. Do not generate targets. Python obtains targets
    directly from Module B.

11. Do not generate JavaScript, Python, shell commands
    or arbitrary browser code.

12. Never claim that an action has been executed.

13. If a required detail is missing and cannot be
    obtained from context, set needs_clarification=true
    and provide a clarification_question.

14. If the requested operation is unsupported by the
    available skill, do not invent an alternative.

15. Return a structured response matching PlannerOutput.

CONTEXT AWARENESS EXAMPLES:

Example A:
User: "Find C101"
Expected: search_component with query C101.

Example B:
User: "Find C101 and show its details"
Expected:
1. search_component with query C101.
2. view_component_details with reference C101.

Example C:
Selected component: R1
User: "Show its details"
Expected: view_component_details with reference R1.

Example D:
No selected component.
User: "Show its details"
Expected: needs_clarification=true.

Remember:
You are a planner, not an executor.
"""

        # 5. Include actual request data in the prompt

        complete_prompt = (
            prompt
            + "\n\nACTUAL INPUT DATA:\n"
            + json.dumps(
                planner_input,
                indent=2,
                default=str
            )
        )

        # 6. Request structured Gemini output

        response = self.client.models.generate_content(
            model=self.model,
            contents=complete_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PlannerOutput
            )
        )

        if not response.text:
            raise ValueError(
                "Gemini returned an empty response."
            )

        # 7. Parse Gemini response

        output = PlannerOutput.model_validate_json(
            response.text
        )

        print("\nGEMINI GENERATED PLAN:")
        print(output.model_dump_json(indent=2))

        # 8. Python determines the trusted website identity

        plan = ActionPlan(
            website=skill.website_id,
            intent=output.intent,
            needs_clarification=output.needs_clarification,
            clarification_question=output.clarification_question,
            steps=output.steps
        )

        return plan

    # --------------------------------------------------
    # MODULE C + MODULE B: VALIDATE ACTION PLAN
    # --------------------------------------------------

    def validate_plan(
        self,
        plan,
        context,
        command,
        page_metadata=None,
        session_state=None
    ):

        page_metadata = page_metadata or {}
        session_state = session_state or {}

        skill = self.skill_router.get_skill(
            context.get("website_id", "unknown")
        )

        # 1. Handle clarification before validation

        if plan.needs_clarification:

            return {
                "website": plan.website,
                "intent": plan.intent,
                "status": "clarification_required",
                "clarification_question": (
                    plan.clarification_question
                ),
                "steps": []
            }

        if not plan.steps:
            raise ValueError(
                "Planner returned an empty action plan."
            )

        # 2. Get component reference from current context

        last_component_reference = (
            self.get_selected_component(
                page_metadata,
                session_state
            )
        )

        validated_steps = []

        # 3. Validate every action in order

        for index, step in enumerate(plan.steps):

            action_definition = skill.actions.get(
                step.action
            )

            if not action_definition:
                raise ValueError(
                    f"Step {index + 1} rejected: "
                    "Unsupported action."
                )

            params = step.parameters.model_dump(
                exclude_none=True
            )

            # Recover component reference for search

            if step.action == "search_component":

                if not params.get("query"):

                    reference = (
                        self.extract_component_reference(command)
                    )

                    if reference:
                        params["query"] = reference

                if params.get("query"):
                    last_component_reference = params["query"]

            # Resolve references for component details

            if step.action == "view_component_details":

                if not params.get("reference"):

                    reference = (
                        self.extract_component_reference(command)
                        or last_component_reference
                    )

                    if reference:
                        params["reference"] = reference

                if params.get("reference"):
                    last_component_reference = params["reference"]

            # Get target from Module B

            if len(action_definition.targets) != 1:

                raise ValueError(
                    f"Step {index + 1} rejected: "
                    "Action requires target selection."
                )

            target = action_definition.targets[0]

            # Validate action, parameters and page type

            result = self.skill_router.validate_action(
                context=context,
                action=step.action,
                parameters=params,
                target=target
            )

            if not result["valid"]:

                raise ValueError(
                    f"Step {index + 1} rejected: "
                    f"{result['reason']}"
                )

            validated_steps.append({
                "action": result["action"],
                "parameters": result["parameters"],
                "target": result["target"],
                "requires_confirmation": (
                    result["requires_confirmation"]
                )
            })

        # 4. Return complete validated plan

        return {
            "website": plan.website,
            "intent": plan.intent,
            "status": "validated",
            "steps": validated_steps
        }

import json
from pathlib import Path
import unittest

from actions import ACTION_RULES, Action, ActionRouter, MockExecutor, classify, parse_intent
from voice_input import process_transcript
from resolver import GroundTruthResolver, canonical_component_ref, parameters_for_action
from matcher import EmbeddingMatcher
from interpreter import GeminiInterpreter, Interpretation
from pipeline import IntentPipeline, PipelineDecision
from matcher import MatchResult
from session_logger import SessionLogger
from smoke_gemini import _safe_exception_summary
from settings import GEMINI_TIMEOUT_MS


class PhraseFixtureTests(unittest.TestCase):
    def test_phrase_fixtures(self):
        fixtures = json.loads((Path(__file__).with_name("phrase_fixtures.json")).read_text())
        for fixture in fixtures:
            with self.subTest(text=fixture["text"]):
                self.assertEqual(list(classify(fixture["text"])), fixture["expected"])


class ResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resolver = GroundTruthResolver.from_default_file()

    def test_component_reference_spacing_and_homophones(self):
        for phrase in ("J108", "J 108", "j-108", "jay one oh eight"):
            with self.subTest(phrase=phrase):
                self.assertEqual(self.resolver.resolve(phrase, "component").canonical, "J108")
        self.assertEqual(canonical_component_ref("see 101"), "C101")

    def test_unknown_component_is_not_repaired(self):
        self.assertEqual(self.resolver.resolve("locate J999", "component").status, "UNKNOWN_TARGET")

    def test_contradictory_component_descriptor_is_ambiguous(self):
        result = self.resolver.resolve("J108 the USB connector", "component")
        self.assertEqual(result.status, "AMBIGUOUS")
        self.assertEqual(set(result.candidates), {"J108", "J106"})

    def test_unknown_sheet_phrase_does_not_resolve(self):
        self.assertEqual(self.resolver.resolve("go to sleep", "sheet").status, "NO_MATCH")

    def test_action_parameters_are_resolved_to_known_targets(self):
        params, error = parameters_for_action("OPEN_SHEET", "open the 3.3-volt regulator", self.resolver)
        self.assertIsNone(error)
        self.assertEqual(params, {"sheet_id": "2_5Vto3.3VRegulator"})

    def test_catalog_and_ground_truth_data_are_consistent(self):
        import json
        from pathlib import Path
        root = Path(__file__).parent / "data"
        catalog = json.loads((root / "catalogs" / "kicad.json").read_text())
        truth = json.loads((root / "kicad_ground_truth.json").read_text())
        labeled = json.loads((root / "labeled_phrases.json").read_text())["phrases"]
        self.assertEqual(catalog["site_type"], truth["site_type"])
        for entry in catalog["actions"]:
            self.assertIn(entry["action"], ACTION_RULES)
            self.assertGreaterEqual(len(entry["examples"]), 8)
            self.assertLessEqual(len(entry["examples"]), 15)
        self.assertEqual(len({item["id"] for item in truth["components"]}), len(truth["components"]))
        for entry in catalog["actions"]:
            self.assertGreaterEqual(sum(row["expected_action"] == entry["action"] for row in labeled), 10)


class EmbeddingMatcherTests(unittest.TestCase):
    class TinyEncoder:
        vectors = {
            "find <component>": [1.0, 0.0],
            "open <sheet>": [0.0, 1.0],
            "where is <component>": [0.9, 0.1],
        }

        def encode(self, texts):
            return [self.vectors.get(text, [1.0, 0.0]) for text in texts]

    def setUp(self):
        self.catalog = {"actions": [
            {"action": "LOCATE_COMPONENT", "examples": ["find <component>", "where is <component>"]},
            {"action": "OPEN_SHEET", "examples": ["open <sheet>"]},
        ]}

    def test_uncalibrated_embeddings_never_auto_accept(self):
        result = EmbeddingMatcher(self.catalog, self.TinyEncoder()).match("where is <component>")
        self.assertFalse(result.accepted)
        self.assertEqual(result.trigger, "UNCALIBRATED")
        self.assertEqual(result.top_action, "LOCATE_COMPONENT")

    def test_thresholds_are_ignored_until_config_marks_calibrated(self):
        matcher = EmbeddingMatcher(self.catalog, self.TinyEncoder(), threshold=0.1, margin=0.0, calibrated=False)
        self.assertEqual(matcher.match("where is <component>").trigger, "UNCALIBRATED")

    def test_embedding_acceptance_requires_score_and_margin(self):
        matcher = EmbeddingMatcher(self.catalog, self.TinyEncoder(), threshold=0.8, margin=0.2)
        result = matcher.match("where is <component>")
        self.assertTrue(result.accepted)
        self.assertIsNone(result.trigger)

    def test_unresolved_or_clipped_input_escalates(self):
        matcher = EmbeddingMatcher(self.catalog, self.TinyEncoder(), threshold=0.5, margin=0.1)
        self.assertEqual(matcher.match("find <component>", unresolved_entity=True).trigger, "UNRESOLVED_ENTITY")
        self.assertEqual(matcher.match("conne").trigger, "POSSIBLY_CLIPPED")


class IntentPipelineTests(unittest.TestCase):
    class AcceptedMatcher:
        def __init__(self, action="LOCATE_COMPONENT"):
            self.action = action
            self.calls = 0
        def match(self, text, unresolved_entity=False):
            self.calls += 1
            return MatchResult(True, self.action, 0.95, "EXPLAIN_COMPONENT", 0.4, None)

    class EscalationMatcher:
        def match(self, text, unresolved_entity=False):
            return MatchResult(False, "LOCATE_COMPONENT", 0.55, "EXPLAIN_COMPONENT", 0.53, "THIN_MARGIN")

    class ProposalInterpreter:
        def interpret(self, transcript, site_type, profile, trigger):
            return Interpretation("CANDIDATES", ({
                "action": "LOCATE_COMPONENT", "params": {"component_ref": "J108"}, "evidence": "J108"
            },))

    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        cls.resolver = GroundTruthResolver.from_default_file()
        cls.catalog = json.loads((Path(__file__).parent / "data/catalogs/kicad.json").read_text())

    def test_clean_match_returns_resolved_parameters(self):
        pipeline = IntentPipeline(self.resolver, self.AcceptedMatcher(), self.ProposalInterpreter())
        result = pipeline.decide("where is J 108", "PCB_WEB", "KICAD_SCHEMATIC")
        self.assertEqual(result.status, "ACCEPTED")
        self.assertEqual(result.parameters, {"component_ref": "J108"})

    def test_unknown_and_contradictory_targets_stop_before_embedding(self):
        matcher = self.AcceptedMatcher()
        pipeline = IntentPipeline(self.resolver, matcher, self.ProposalInterpreter())
        self.assertEqual(pipeline.decide("locate J999", "PCB_WEB", "KICAD_SCHEMATIC").status, "UNKNOWN_TARGET")
        self.assertEqual(pipeline.decide("J108 the USB connector", "PCB_WEB", "KICAD_SCHEMATIC").status, "AMBIGUOUS")
        self.assertEqual(matcher.calls, 0)

    def test_embedding_failure_escalation_returns_confirmation_candidate(self):
        pipeline = IntentPipeline(self.resolver, self.EscalationMatcher(), self.ProposalInterpreter())
        result = pipeline.decide("could you take me to J108", "PCB_WEB", "KICAD_SCHEMATIC")
        self.assertEqual(result.status, "CONFIRM")
        self.assertEqual(result.action, "LOCATE_COMPONENT")
        self.assertEqual(result.parameters, {"component_ref": "J108"})


class GeminiInterpreterTests(unittest.TestCase):
    class FakeResponse:
        def __init__(self, payload):
            self.text = json.dumps(payload)

    class FakeModels:
        def __init__(self, responses):
            self.responses = list(responses)
            self.calls = 0

        def generate_content(self, **kwargs):
            self.calls += 1
            response = self.responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

    class FakeClient:
        def __init__(self, responses):
            self.models = GeminiInterpreterTests.FakeModels(responses)

    @classmethod
    def setUpClass(cls):
        import json
        from pathlib import Path
        cls.json = json
        root = Path(__file__).parent / "data"
        cls.catalog = json.loads((root / "catalogs" / "kicad.json").read_text())
        cls.resolver = GroundTruthResolver.from_default_file()

    def interpreter(self, payloads):
        return GeminiInterpreter(self.FakeClient(payloads), "test-model", self.catalog, self.resolver)

    def test_valid_candidate_is_resolver_grounded(self):
        interpreter = self.interpreter([self.FakeResponse({"ambiguous": False, "candidates": [
            {"action": "LOCATE_COMPONENT", "params": {"component_ref": "J 108"}, "evidence": "J108"}
        ]})])
        result = interpreter.interpret("Could you take me to J108?", "KICAD_SCHEMATIC", "PCB_WEB", "LOW_SCORE")
        self.assertEqual(result.status, "CANDIDATES")
        self.assertEqual(result.candidates[0]["params"], {"component_ref": "J108"})

    def test_hallucinated_target_and_unknown_action_are_rejected(self):
        payload = {"ambiguous": False, "candidates": [
            {"action": "LOCATE_COMPONENT", "params": {"component_ref": "J106"}, "evidence": "J108"},
            {"action": "RUN_ARBITRARY_CODE", "params": {}, "evidence": "J108"},
        ]}
        result = self.interpreter([self.FakeResponse(payload)]).interpret("find J108", "KICAD_SCHEMATIC", "PCB_WEB", "LOW_SCORE")
        self.assertEqual(result.status, "UNRECOGNIZED")

    def test_ambiguous_and_contradictory_inputs_are_not_repaired(self):
        model = self.interpreter([self.FakeResponse({"ambiguous": True, "candidates": []})])
        self.assertEqual(model.interpret("show C101", "KICAD_SCHEMATIC", "PCB_WEB", "THIN_MARGIN").status, "AMBIGUOUS")
        contradiction = self.interpreter([])
        self.assertEqual(contradiction.interpret("J108 the USB connector", "KICAD_SCHEMATIC", "PCB_WEB", "LOW_SCORE").status, "AMBIGUOUS")
        self.assertEqual(contradiction.client.models.calls, 0)

    def test_api_failure_returns_normal_failure_without_leaking_exception(self):
        interpreter = self.interpreter([RuntimeError("offline")])
        result = interpreter.interpret("take me to J108", "KICAD_SCHEMATIC", "PCB_WEB", "LOW_SCORE")
        self.assertEqual(result.status, "UNAVAILABLE")
        self.assertEqual(interpreter.client.models.calls, 1)

    def test_smoke_error_details_include_status_but_redact_key_and_url(self):
        class ApiError(Exception):
            code = 400
            status = "INVALID_ARGUMENT"
            message = "bad request https://example.test/path?key=secret-key"
        summary = _safe_exception_summary(ApiError(), "secret-key")
        self.assertIn("HTTP 400", summary)
        self.assertIn("INVALID_ARGUMENT", summary)
        self.assertNotIn("secret-key", summary)
        self.assertIn("URL REDACTED", summary)

    def test_gemini_timeout_meets_api_minimum(self):
        self.assertGreaterEqual(GEMINI_TIMEOUT_MS, 10_000)


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.executor = MockExecutor()
        self.router = ActionRouter(self.executor)

    def test_typed_command_mock_loop(self):
        result = self.router.handle_text("scroll down", "DOCUMENTATION", "PDF", "scroll-1")
        self.assertTrue(result["success"])
        self.assertEqual(self.executor.executed[0].action, "SCROLL_DOWN")
        self.assertEqual(result["request_id"], "scroll-1")

    def test_complex_command_is_forwarded(self):
        result = self.router.handle_text("Show Motor 2's temperature", "MAINTENANCE", "INDUSTRIAL_DASHBOARD", "task-1")
        self.assertEqual(result["status"], "FORWARDED_TO_PLANNER")
        self.assertEqual(self.executor.executed, [])

    def test_dashboard_action_rejected_on_docs(self):
        action = Action("ACTION", "VOICE", "NEXT_PANEL", "MAINTENANCE", {}, "wrong-site")
        result = self.router.dispatch(action, "DOCUMENTATION")
        self.assertEqual(result["reason"], "UNSUPPORTED_PAGE")

    def test_unknown_action_and_bad_arguments_rejected(self):
        unknown = Action("ACTION", "VOICE", "EXECUTE_JS", "DOCUMENTATION", {}, "unknown")
        malformed = Action("ACTION", "AGENT", "SHOW_MACHINE", "MAINTENANCE", {"machine_id": 2}, "bad-arg")
        self.assertEqual(self.router.dispatch(unknown, "INDUSTRIAL_DASHBOARD")["reason"], "INVALID_ACTION")
        self.assertEqual(self.router.dispatch(malformed, "INDUSTRIAL_DASHBOARD")["reason"], "INVALID_ARGS")

    def test_pause_blocks_and_resume_restores_without_queueing(self):
        self.router.handle_text("pause", "DOCUMENTATION", "PDF", "pause-1")
        blocked = self.router.handle_text("scroll down", "DOCUMENTATION", "PDF", "blocked-1")
        self.assertEqual(blocked["reason"], "PAUSED")
        self.router.handle_text("resume", "DOCUMENTATION", "PDF", "resume-1")
        self.assertEqual(self.executor.executed, [])
        success = self.router.handle_text("scroll down", "DOCUMENTATION", "PDF", "scroll-2")
        self.assertTrue(success["success"])
        self.assertEqual(len(self.executor.executed), 1)

    def test_duplicate_request_is_not_executed_twice(self):
        first = self.router.handle_text("scroll down", "DOCUMENTATION", "PDF", "same-id")
        replay = self.router.handle_text("scroll down", "DOCUMENTATION", "PDF", "same-id")
        self.assertEqual(first, replay)
        self.assertEqual(len(self.executor.executed), 1)

    def test_agent_submission_requires_approval(self):
        action = Action("ACTION", "AGENT", "SUBMIT_FAULT_RECORD", "MAINTENANCE",
                        {"record_id": "draft-1", "approved": False}, "submit-1")
        result = self.router.dispatch(action, "INDUSTRIAL_DASHBOARD")
        self.assertEqual(result["reason"], "APPROVAL_REQUIRED")
        self.assertEqual(self.executor.executed, [])

    def test_kicad_voice_commands_produce_typed_actions(self):
        cases = [
            ("Locate J106, the USB connector", "LOCATE_COMPONENT", {"component_ref": "J106"}),
            ("Where is J108", "LOCATE_COMPONENT", {"component_ref": "J108"}),
            ("Find J 108", "LOCATE_COMPONENT", {"component_ref": "J108"}),
            ("Show me the J-108 connector", "LOCATE_COMPONENT", {"component_ref": "J108"}),
            ("Take me to J_108", "LOCATE_COMPONENT", {"component_ref": "J108"}),
            ("Where do USB D+ and D− go", "TRACE_SIGNAL", {"signal_name": "USB_P, USB_N"}),
            ("What's the purpose of R101", "EXPLAIN_COMPONENT", {"component_ref": "R101"}),
            ("Tell me about C 101", "EXPLAIN_COMPONENT", {"component_ref": "C101"}),
            ("Follow the I2C connections", "TRACE_SIGNAL", {"signal_name": "I2C"}),
            ("Open the 3.3-volt regulator", "OPEN_SHEET", {"sheet_id": "2_5Vto3.3VRegulator"}),
            ("Go to the SAMD21", "OPEN_SHEET", {"sheet_id": "3_uC_SAMD21"}),
            ("Switch to the SAMD21 sheet", "OPEN_SHEET", {"sheet_id": "3_uC_SAMD21"}),
            ("I'm assembling the USB section", "SHOW_ASSEMBLY_CHECKLIST", {"section_id": "USB"}),
            ("Show assembly checklist for USB section", "SHOW_ASSEMBLY_CHECKLIST", {"section_id": "USB"}),
            ("Check off C101", "MARK_COMPONENT_COMPLETE", {"component_ref": "C101"}),
            ("My board won't communicate over USB", "GUIDE_TROUBLESHOOTING", {"issue": "COMMUNICATE OVER USB"}),
            ("Display the USB area", "SHOW_SCHEMATIC_SECTION", {"section_id": "USB"}),
        ]
        for phrase, expected_action, expected_parameters in cases:
            with self.subTest(phrase=phrase):
                kind, action_name, parameters = parse_intent(phrase)
                self.assertEqual((kind, action_name, parameters), ("simple", expected_action, expected_parameters))

    def test_kicad_action_requires_kicad_profile_and_site(self):
        result = self.router.handle_text("Locate J106", "DOCUMENTATION", "PDF", "kicad-wrong-context")
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "UNSUPPORTED_PAGE")

    def test_kicad_voice_command_uses_router_result_path(self):
        result = self.router.handle_text("Locate J106", "PCB_WEB", "KICAD_SCHEMATIC", "locate-j106")
        self.assertTrue(result["success"])
        self.assertEqual(self.executor.executed[-1].parameters, {"component_ref": "J106"})

    def test_transcribed_voice_event_routes_and_has_timestamp(self):
        result = process_transcript(self.router, "Locate J106", "PCB_WEB", "KICAD_SCHEMATIC", "voice-1")
        self.assertEqual(result["voice_event"]["type"], "VOICE_EVENT")
        self.assertEqual(result["voice_event"]["status"], "TRANSCRIBED")
        self.assertIsInstance(result["voice_event"]["timestamp"], int)
        self.assertTrue(result["result"]["success"])
        self.assertEqual(self.executor.executed[-1].parameters, {"component_ref": "J106"})

    def test_fast_control_skips_embeddings_and_gemini_pipeline(self):
        class NeverPipeline:
            resolver = GroundTruthResolver.from_default_file()
            def decide(self, *args):
                raise AssertionError("Fast path should not call the AI pipeline")
        router = ActionRouter(self.executor, intent_pipeline=NeverPipeline())
        result = router.handle_text("scroll down", "PCB_WEB", "KICAD_SCHEMATIC", "fast-scroll")
        self.assertTrue(result["success"])
        self.assertEqual(self.executor.executed[-1].action, "SCROLL_DOWN")

    def test_gemini_proposal_requires_confirmation_before_dispatch(self):
        class ProposalPipeline:
            resolver = GroundTruthResolver.from_default_file()
            def decide(self, *args):
                return PipelineDecision("CONFIRM", "LOCATE_COMPONENT", {"component_ref": "J108"},
                                        "LOW_SCORE", ({"action": "LOCATE_COMPONENT", "params": {"component_ref": "J108"}},))
        router = ActionRouter(self.executor, intent_pipeline=ProposalPipeline())
        proposal = router.handle_text("take me to the serial connector", "PCB_WEB", "KICAD_SCHEMATIC", "proposal-1")
        self.assertEqual(proposal["reason"], "CONFIRMATION_REQUIRED")
        self.assertEqual(self.executor.executed, [])
        confirmed = router.handle_text("yes", "PCB_WEB", "KICAD_SCHEMATIC")
        self.assertTrue(confirmed["success"])
        self.assertEqual(self.executor.executed[-1].parameters, {"component_ref": "J108"})

    def test_pause_cancels_pending_confirmation(self):
        class ProposalPipeline:
            resolver = GroundTruthResolver.from_default_file()
            def decide(self, *args):
                return PipelineDecision("CONFIRM", "LOCATE_COMPONENT", {"component_ref": "J108"}, "LOW_SCORE")
        router = ActionRouter(self.executor, intent_pipeline=ProposalPipeline())
        router.handle_text("something paraphrased", "PCB_WEB", "KICAD_SCHEMATIC", "proposal-2")
        result = router.handle_text("pause", "PCB_WEB", "KICAD_SCHEMATIC", "pause-2")
        self.assertTrue(result["success"])
        self.assertIsNone(router.pending_confirmation)
        self.assertEqual(router.handle_text("yes", "PCB_WEB", "KICAD_SCHEMATIC")["reason"], "UNRECOGNIZED")

    def test_utterance_log_contains_decision_and_final_result(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            logger = SessionLogger(Path(directory) / "utterances.jsonl")
            router = ActionRouter(self.executor, session_logger=logger)
            router.handle_text("scroll down", "DOCUMENTATION", "PDF", "logged-1")
            entry = json.loads((Path(directory) / "utterances.jsonl").read_text())
            self.assertEqual(entry["transcript"], "scroll down")
            self.assertTrue(entry["final_result"]["success"])
            self.assertNotIn("GEMINI_API_KEY", json.dumps(entry))

    def test_dispatch_rechecks_resolved_kicad_targets(self):
        router = ActionRouter(self.executor, resolver=GroundTruthResolver.from_default_file())
        unknown = Action("ACTION", "AGENT", "LOCATE_COMPONENT", "PCB_WEB", {"component_ref": "J999"}, "unknown-ref")
        invalid_sheet = Action("ACTION", "AGENT", "OPEN_SHEET", "PCB_WEB", {"sheet_id": "sleep"}, "fake-sheet")
        self.assertEqual(router.dispatch(unknown, "KICAD_SCHEMATIC")["reason"], "UNKNOWN_TARGET")
        self.assertEqual(router.dispatch(invalid_sheet, "KICAD_SCHEMATIC")["reason"], "UNKNOWN_TARGET")


if __name__ == "__main__":
    unittest.main()

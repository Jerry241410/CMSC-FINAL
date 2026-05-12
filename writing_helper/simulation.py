import asyncio
import json
import random
import re
import time
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .agents import (
    BehaviorInterpreterAgent,
    InterruptionInterpreterAgent,
    PreferenceMemoryAgent,
    ReplacementAgent,
    StatelessLLMAgent,
    StreamingWriterAgent,
)
from .constants import PREFERENCE_PROMOTION_THRESHOLD
from .models import ProfileUpdateSuggestion, ReplacementOption, RevisionEvent, SessionState
from .text_utils import extract_interruption_context, extract_json_object


SIMULATION_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "simulation_outputs"

STANDARD_PREFERENCE_POOL = [
    "Avoid repetition and let each sentence make a fresh move.",
    "Use more specific wording instead of broad or generic phrasing.",
    "Keep wording flexible enough to avoid sounding overly narrow too early.",
    "Keep the tone aligned with the intended voice of the piece.",
    "Prefer clearer, lighter, and more concise sentences.",
    "Support abstract points with concrete examples when needed.",
    "State the core claim more precisely and with a more refined point.",
    "Use a brief opposing idea or contrast when it strengthens the point.",
    "Explain the mechanism or reasoning behind important claims.",
    "Make each sentence connect more explicitly to the prior idea and task.",
]

CUSTOM_PREFERENCE_POOL = [
    "Prefer a measured academic tone with cautious qualification.",
    "Favor conceptual synthesis over listing disconnected claims.",
    "Tie each paragraph back to the paper's central research question.",
    "Avoid inflated novelty claims unless the evidence is explicit.",
    "Use transitions that make the argumentative progression easy to follow.",
    "Keep theoretical terms precise and avoid vague abstractions.",
    "Name the methodological limitation before drawing a strong conclusion.",
    "Prefer multi-step causal explanation over simple correlation claims.",
    "Use compact signposting at paragraph openings without sounding formulaic.",
    "Avoid celebratory technology language unless grounded in evidence.",
    "Keep normative claims separate from descriptive claims.",
    "Use field-specific terms, but define them when they become load-bearing.",
    "Prefer examples that reveal a tradeoff rather than merely decorate the claim.",
    "End paragraphs with an analytical implication instead of a summary sentence.",
    "Avoid overusing 'important' and replace it with the exact reason something matters.",
    "Prefer precise verbs over noun-heavy academic phrasing.",
    "Keep topic sentences argumentative rather than merely descriptive.",
    "Use compact clauses instead of long stacked prepositional phrases.",
    "Avoid vague intensifiers and let the sentence's logic carry emphasis.",
    "Prefer paragraph endings that sharpen the claim instead of summarizing it.",
]

STRUCTURAL_PREFERENCE_POOL = [
    "Open paragraphs with a debatable claim rather than a broad topic sentence.",
    "Use one governing idea per paragraph and subordinate examples to that idea.",
    "Move from claim to mechanism to evidence before introducing qualifications.",
    "Keep sentence rhythm varied: short claim, longer explanation, concise implication.",
    "Make counterarguments concrete enough that they feel like real objections.",
    "Prefer synthesis across sources rather than source-by-source narration.",
    "Use transitions that indicate logical relation, such as contrast, cause, or scope.",
    "Avoid ending sections with vague future-facing gestures.",
]

VOICE_PREFERENCE_POOL = [
    "Write with restrained confidence rather than dramatic emphasis.",
    "Avoid generic academic filler.",
    "Prefer precise verbs over nominalized phrases when possible.",
    "Use cautious qualifiers only when they clarify uncertainty, not as padding.",
    "Keep the prose analytical but readable for an interdisciplinary audience.",
    "Avoid rhetorical questions and let claims carry the argumentative pressure.",
    "Prefer concrete nouns over abstract umbrella terms when the context allows.",
    "Make evaluative language traceable to evidence in the paragraph.",
]

ACADEMIC_DOMAINS = [
    "machine learning",
    "climate policy",
    "comparative literature",
    "public health",
    "urban sociology",
    "bioethics",
    "education policy",
    "economic history",
    "human-computer interaction",
    "political theory",
]

TASK_TEMPLATES = [
    "Write a long-form academic essay arguing how {domain} should balance theory, evidence, and methodological caution.",
    "Draft a research-style essay on the major debates in {domain}, with attention to mechanism, counterargument, and evidence.",
    "Write an academic essay explaining why current scholarship in {domain} remains contested and what a stronger argument would require.",
    "Compose a long analytical essay about how researchers in {domain} justify claims, qualify uncertainty, and persuade skeptical readers.",
]


@dataclass
class FakeUserScenario:
    user_id: str
    target_profile: List[str]
    task: str


@dataclass
class SimulationStepRecord:
    step_index: int
    generation_text: str
    interrupted: bool
    interruption_reason: str
    interruption_point: Dict[str, Any]
    simulator_confidence: float = 0.0
    simulator_decision_rationale: str = ""
    system_interpretation: Dict[str, Any] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    cumulative_elapsed_seconds: float = 0.0
    recovery_after_step: Dict[str, Any] = field(default_factory=dict)
    replacement_options: List[Dict[str, Any]] = field(default_factory=list)
    selected_action: str = ""
    selected_reason_id: str = ""
    selected_reason: str = ""
    selected_revision: str = ""
    manual_input: str = ""
    helper_profile_after_step: List[str] = field(default_factory=list)
    helper_local_memory_after_step: List[str] = field(default_factory=list)
    helper_observations_after_step: List[Dict[str, Any]] = field(default_factory=list)
    profile_summary_added: str = ""
    memory_scope: str = ""


class ProfileSatisfactionAgent(StatelessLLMAgent):
    def __init__(self, model: str = "gpt-4o-mini", name: str = "profile_satisfaction_agent"):
        super().__init__(
            name=name,
            model=model,
            system_message=(
                "You simulate a demanding academic writer with a stable target preference profile. "
                "Return only valid JSON in the requested structure."
            ),
            temperature=0.2,
        )

    async def assess_generation(
        self,
        task: str,
        target_profile: List[str],
        current_text: str,
        latest_chunk: str,
        helper_profile: List[str],
        local_memory: List[str],
    ) -> Dict[str, Any]:
        preferences = "\n".join(f"- {item}" for item in target_profile)
        helper = "\n".join(f"- {item}" for item in helper_profile) or "- None yet."
        local = "\n".join(f"- {item}" for item in local_memory) or "- None yet."
        prompt = f"""
You are deciding whether to interrupt a writing assistant because the latest generated chunk does not satisfy the user's profile.

Task:
{task}

Target user profile:
{preferences}

What the helper currently remembers globally:
{helper}

What the helper currently remembers locally:
{local}

Current full draft:
{current_text}

Latest generated chunk:
{latest_chunk}

Return JSON only:
{{
  "interrupt": true,
  "reason": "<why the chunk does or does not satisfy the profile>",
  "confidence": 0.0
}}

Constraints:
- Set interrupt to true when the latest chunk clearly misses, contradicts, or ignores the target profile.
- Set interrupt to false when the chunk reasonably satisfies the profile.
- Base the decision mainly on the latest chunk.
"""
        try:
            payload = extract_json_object(await self.complete(prompt))
            return {
                "interrupt": bool(payload.get("interrupt", False)),
                "reason": str(payload.get("reason", "")).strip(),
                "confidence": float(payload.get("confidence", 0.0) or 0.0),
            }
        except Exception:
            return self._fallback_assess(target_profile, latest_chunk)

    async def choose_revision(
        self,
        task: str,
        target_profile: List[str],
        current_text: str,
        interruption_point: Dict[str, Any],
        replacement_options: List[ReplacementOption],
    ) -> Dict[str, Any]:
        preferences = "\n".join(f"- {item}" for item in target_profile)
        options_payload = json.dumps([asdict(item) for item in replacement_options], ensure_ascii=False, indent=2)
        prompt = f"""
You are simulating a user choosing the best interruption-based revision action.

Task:
{task}

Target user profile:
{preferences}

Current draft:
{current_text}

Interruption point:
{json.dumps(interruption_point, ensure_ascii=False, indent=2)}

Available replacement options:
{options_payload}

Return JSON only:
{{
  "action": "<select_option|manual_describe|manual_write>",
  "selected_reason_id": "<reason id or empty>",
  "manual_instruction": "<manual revision request or manual replacement text>",
  "rationale": "<why this action best matches the target profile>"
}}

Constraints:
- Use select_option when one option clearly fits the target profile.
- Use manual_describe when the available options are close but not enough.
- Use manual_write only when a direct replacement sentence is the best match.
- If action is select_option, selected_reason_id must match one of the available options.
"""
        try:
            payload = extract_json_object(await self.complete(prompt))
            return {
                "action": str(payload.get("action", "")).strip(),
                "selected_reason_id": str(payload.get("selected_reason_id", "")).strip(),
                "manual_instruction": str(payload.get("manual_instruction", "")).strip(),
                "rationale": str(payload.get("rationale", "")).strip(),
            }
        except Exception:
            return self._fallback_choose(target_profile, replacement_options)

    def _fallback_assess(self, target_profile: List[str], latest_chunk: str) -> Dict[str, Any]:
        overlap = _word_overlap_count(" ".join(target_profile), latest_chunk)
        interrupt = overlap < max(4, len(_tokenize(" ".join(target_profile))) // 5)
        return {
            "interrupt": interrupt,
            "reason": "Fallback heuristic based on low lexical overlap with the target profile.",
            "confidence": 0.35,
        }

    def _fallback_choose(self, target_profile: List[str], replacement_options: List[ReplacementOption]) -> Dict[str, Any]:
        profile_text = " ".join(target_profile)
        best_option: Optional[ReplacementOption] = None
        best_score = -1
        for option in replacement_options:
            score = _word_overlap_count(profile_text, f"{option.reason} {option.explanation} {option.replacement_text}")
            if score > best_score:
                best_score = score
                best_option = option

        if best_option and best_score >= 3:
            return {
                "action": "select_option",
                "selected_reason_id": best_option.reason_id,
                "manual_instruction": "",
                "rationale": "Fallback overlap heuristic found a sufficiently similar option.",
            }

        manual_instruction = target_profile[0] if target_profile else "Make the sentence better aligned with the intended academic style."
        return {
            "action": "manual_describe",
            "selected_reason_id": "",
            "manual_instruction": manual_instruction,
            "rationale": "Fallback overlap heuristic could not find a strong enough option match.",
        }


def generate_fake_user_scenarios(count: int = 100, seed: int = 7) -> List[FakeUserScenario]:
    rng = random.Random(seed)
    scenarios: List[FakeUserScenario] = []
    for index in range(count):
        domain = rng.choice(ACADEMIC_DOMAINS)
        task = rng.choice(TASK_TEMPLATES).format(domain=domain)
        standard_count = rng.randint(3, 5)
        custom_count = rng.randint(2, 3)
        profile_items = rng.sample(STANDARD_PREFERENCE_POOL, k=standard_count)
        profile_items.extend(rng.sample(CUSTOM_PREFERENCE_POOL, k=custom_count))
        profile_items.extend(rng.sample(STRUCTURAL_PREFERENCE_POOL, k=2))
        profile_items.extend(rng.sample(VOICE_PREFERENCE_POOL, k=2))
        rng.shuffle(profile_items)
        scenarios.append(
            FakeUserScenario(
                user_id=f"fake_user_{index + 1:03d}",
                target_profile=profile_items,
                task=task,
            )
        )
    return scenarios


class HeadlessInterruptionSimulator:
    def __init__(self, model: str = "gpt-4o-mini", max_steps: int = 6):
        self.model = model
        self.max_steps = max_steps

    async def run_batch(
        self,
        scenarios: List[FakeUserScenario],
        output_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        started_at = time.time()
        for scenario in scenarios:
            results.append(await self.run_single_scenario(scenario))

        summary = self._build_summary(results)
        payload = {
            "metadata": {
                "scenario_count": len(scenarios),
                "model": self.model,
                "max_steps": self.max_steps,
                "started_at": started_at,
                "finished_at": time.time(),
            },
            "summary": summary,
            "results": results,
        }
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    async def run_single_scenario(self, scenario: FakeUserScenario) -> Dict[str, Any]:
        memory_agent = PreferenceMemoryAgent(model=self.model)
        interpreter_agent = InterruptionInterpreterAgent(model=self.model)
        behavior_interpreter_agent = BehaviorInterpreterAgent(model=self.model)
        replacement_agent = ReplacementAgent(model=self.model)
        writer_agent = StreamingWriterAgent(model=self.model)
        judge_agent = ProfileSatisfactionAgent(model=self.model, name=f"profile_satisfaction_agent_{scenario.user_id}")

        state = SessionState(username=scenario.user_id, task=scenario.task)
        steps: List[SimulationStepRecord] = []

        try:
            scenario_started_at = time.time()
            for step_index in range(1, self.max_steps + 1):
                step_started_at = time.time()
                generation_text = await self._generate_chunk(writer_agent, state)
                if not generation_text.strip():
                    break

                state.live_text = self._append_chunk(state.live_text, generation_text)
                assessment = await judge_agent.assess_generation(
                    task=scenario.task,
                    target_profile=scenario.target_profile,
                    current_text=state.live_text,
                    latest_chunk=generation_text,
                    helper_profile=state.preference_profile,
                    local_memory=state.local_preference_hints,
                )

                if not assessment.get("interrupt", False):
                    state.accepted_text = state.live_text
                    steps.append(
                        SimulationStepRecord(
                            step_index=step_index,
                            elapsed_seconds=time.time() - step_started_at,
                            cumulative_elapsed_seconds=time.time() - scenario_started_at,
                            generation_text=generation_text,
                            interrupted=False,
                            interruption_reason=str(assessment.get("reason", "")).strip(),
                            interruption_point={},
                            simulator_confidence=float(assessment.get("confidence", 0.0) or 0.0),
                            simulator_decision_rationale=str(assessment.get("reason", "")).strip(),
                            recovery_after_step=compute_profile_similarity(scenario.target_profile, state.preference_profile),
                            helper_profile_after_step=list(state.preference_profile),
                            helper_local_memory_after_step=list(state.local_preference_hints),
                            helper_observations_after_step=[asdict(item) for item in state.preference_observations],
                        )
                    )
                    continue

                state.interruption_context = extract_interruption_context(state.live_text)
                interruption_point = {
                    "termination_point": state.interruption_context.termination_point,
                    "last_sentence": state.interruption_context.last_sentence,
                    "current_sentence": state.interruption_context.current_sentence,
                    "replacement_start": state.interruption_context.replacement_start,
                }
                interpreter_result = await interpreter_agent.interpret(state)
                interpreter_result.stop_point.replacement_start = state.interruption_context.replacement_start
                state.active_interpreter_result = interpreter_result
                replacement_options = await replacement_agent.build_replacements(state, interpreter_result)

                decision = await judge_agent.choose_revision(
                    task=scenario.task,
                    target_profile=scenario.target_profile,
                    current_text=state.live_text,
                    interruption_point=interruption_point,
                    replacement_options=replacement_options,
                )

                selected_payload = await self._apply_decision(
                    state=state,
                    memory_agent=memory_agent,
                    behavior_interpreter_agent=behavior_interpreter_agent,
                    replacement_agent=replacement_agent,
                    decision=decision,
                    replacement_options=replacement_options,
                )

                steps.append(
                    SimulationStepRecord(
                        step_index=step_index,
                        elapsed_seconds=time.time() - step_started_at,
                        cumulative_elapsed_seconds=time.time() - scenario_started_at,
                        generation_text=generation_text,
                        interrupted=True,
                        interruption_reason=str(assessment.get("reason", "")).strip(),
                        interruption_point=interruption_point,
                        simulator_confidence=float(assessment.get("confidence", 0.0) or 0.0),
                        simulator_decision_rationale=str(decision.get("rationale", "")).strip(),
                        system_interpretation=interpreter_result.to_dict(),
                        recovery_after_step=compute_profile_similarity(scenario.target_profile, state.preference_profile),
                        replacement_options=[asdict(item) for item in replacement_options],
                        selected_action=selected_payload["selected_action"],
                        selected_reason_id=selected_payload["selected_reason_id"],
                        selected_reason=selected_payload["selected_reason"],
                        selected_revision=selected_payload["selected_revision"],
                        manual_input=selected_payload["manual_input"],
                        helper_profile_after_step=list(state.preference_profile),
                        helper_local_memory_after_step=list(state.local_preference_hints),
                        helper_observations_after_step=[asdict(item) for item in state.preference_observations],
                        profile_summary_added=selected_payload["profile_summary_added"],
                        memory_scope=selected_payload["memory_scope"],
                    )
                )

                state.active_interpreter_result = None

            similarity = compute_profile_similarity(scenario.target_profile, state.preference_profile)
            return {
                "user_id": scenario.user_id,
                "task": scenario.task,
                "target_profile": list(scenario.target_profile),
                "helper_profile": list(state.preference_profile),
                "helper_local_memory": list(state.local_preference_hints),
                "helper_observations": [asdict(item) for item in state.preference_observations],
                "revision_log": [asdict(event) for event in state.revision_log],
                "steps": [asdict(step) for step in steps],
                "final_text": state.live_text,
                "elapsed_seconds": time.time() - scenario_started_at,
                "similarity": similarity,
            }
        finally:
            await writer_agent.close()
            await interpreter_agent.close()
            await behavior_interpreter_agent.close()
            await replacement_agent.close()
            await memory_agent.close()
            await judge_agent.close()

    async def _generate_chunk(self, writer_agent: StreamingWriterAgent, state: SessionState) -> str:
        preferences = "\n".join(f"- {item}" for item in state.preference_profile) or "- None yet."
        local_preferences = "\n".join(f"- {item}" for item in state.local_preference_hints) or "- None yet."
        revision_history = state.format_revision_history()
        prompt = f"""
Username:
{state.username}

User task description:
{state.task}

Saved user profile:
{preferences}

Current local passage preferences:
{local_preferences}

Interruption history:
{revision_history}

Current accepted text:
{state.accepted_text}

Instruction:
Continue the essay with exactly one academic paragraph of 4 to 6 sentences. Do not restart from the beginning.
"""
        text = await writer_agent.complete(prompt)
        return " ".join(text.split()).strip()

    async def _apply_decision(
        self,
        state: SessionState,
        memory_agent: PreferenceMemoryAgent,
        behavior_interpreter_agent: BehaviorInterpreterAgent,
        replacement_agent: ReplacementAgent,
        decision: Dict[str, Any],
        replacement_options: List[ReplacementOption],
    ) -> Dict[str, Any]:
        action = str(decision.get("action", "")).strip().lower()
        selected_option = None
        if action == "select_option":
            reason_id = str(decision.get("selected_reason_id", "")).strip()
            selected_option = next((item for item in replacement_options if item.reason_id == reason_id), None)
            if selected_option is None and replacement_options:
                selected_option = replacement_options[0]
            if selected_option is not None:
                key, summary = memory_agent.summarize_standard_reason(selected_option.reason_id, selected_option.reason)
                memory_update = ProfileUpdateSuggestion(
                    preference_summary=summary,
                    confidence=0.8,
                    preference_key=key,
                    scope="local",
                    rationale="Standardized replacement choices are treated as local first.",
                )
                return self._apply_revision(
                    state=state,
                    selected_reason_id=selected_option.reason_id,
                    selected_reason=selected_option.reason,
                    selected_revision=selected_option.replacement_text,
                    selection_kind="replacement_option",
                    custom_input="",
                    memory_update=memory_update,
                    selected_action="select_option",
                )

        manual_instruction = str(decision.get("manual_instruction", "")).strip()
        if not manual_instruction:
            manual_instruction = "Make the sentence more aligned with the target academic profile."
        manual_mode = "write_own_text" if action == "manual_write" else "describe_revision"
        behavior_result = await behavior_interpreter_agent.interpret_behavior(
            state=state,
            behavior_text=manual_instruction,
            behavior_mode=manual_mode,
        )
        state.active_interpreter_result = behavior_result
        custom_memory = await memory_agent.interpret_custom_memory(
            task=state.task,
            passage=state.live_text,
            current_sentence=state.interruption_context.current_sentence,
            user_input=manual_instruction,
            existing_profile=state.preference_profile,
        )
        if manual_mode == "describe_revision":
            selected_revision = await replacement_agent.build_custom_revision(
                task=state.task,
                passage=state.live_text,
                custom_instruction=manual_instruction,
            )
            selection_kind = "other_describe_revision"
            selected_action = "manual_describe"
        else:
            selected_revision = manual_instruction
            selection_kind = "other_write_own_text"
            selected_action = "manual_write"

        return self._apply_revision(
            state=state,
            selected_reason_id="OTHER",
            selected_reason="Other",
            selected_revision=selected_revision,
            selection_kind=selection_kind,
            custom_input=manual_instruction,
            memory_update=custom_memory,
            selected_action=selected_action,
        )

    def _apply_revision(
        self,
        state: SessionState,
        selected_reason_id: str,
        selected_reason: str,
        selected_revision: str,
        selection_kind: str,
        custom_input: str,
        memory_update: ProfileUpdateSuggestion,
        selected_action: str,
    ) -> Dict[str, Any]:
        local_summary = memory_update.preference_summary.strip()
        promoted_summary = ""
        memory_scope = memory_update.scope or "local"

        if local_summary:
            state.local_preference_hints = self._dedupe_append(state.local_preference_hints, local_summary)

        if memory_update.scope == "global":
            if local_summary:
                state.preference_profile = self._dedupe_append(state.preference_profile, local_summary)
                promoted_summary = local_summary
        else:
            state.preference_observations, count_after = memory_agent_record_observation(
                state.preference_observations,
                memory_update.preference_key,
                local_summary,
            )
            if local_summary and count_after >= 3:
                state.preference_profile = self._dedupe_append(state.preference_profile, local_summary)
                promoted_summary = local_summary
                memory_scope = "local_promoted_global"

        start = state.interruption_context.replacement_start
        prefix = state.live_text[:start].rstrip()
        revision = selected_revision.strip()
        state.live_text = f"{prefix} {revision}".strip() if prefix else revision
        state.accepted_text = state.live_text

        revision_event = RevisionEvent(
            event_id=str(uuid.uuid4()),
            timestamp=time.time(),
            username=state.username,
            task=state.task,
            stop_point=state.interruption_context,
            interpreter_result=state.active_interpreter_result.to_dict() if state.active_interpreter_result else {},
            selected_reason_id=selected_reason_id,
            selected_reason=selected_reason,
            selected_revision=selected_revision,
            selection_kind=selection_kind,
            custom_input=custom_input,
            updated_preference_profile=list(state.preference_profile),
            applied_local_preferences=list(state.local_preference_hints),
            applied_memory_scope=memory_scope,
            promoted_profile_summary=promoted_summary,
        )
        state.revision_log.append(revision_event)
        return {
            "selected_action": selected_action,
            "selected_reason_id": selected_reason_id,
            "selected_reason": selected_reason,
            "selected_revision": selected_revision,
            "manual_input": custom_input,
            "profile_summary_added": promoted_summary,
            "memory_scope": memory_scope,
        }

    def _append_chunk(self, existing_text: str, chunk: str) -> str:
        if not existing_text.strip():
            return chunk.strip()
        separator = "" if existing_text.endswith((" ", "\n")) else " "
        return f"{existing_text}{separator}{chunk.strip()}"

    def _dedupe_append(self, items: List[str], new_item: str) -> List[str]:
        cleaned = new_item.strip()
        if not cleaned:
            return list(items)
        return list(dict.fromkeys(list(items) + [cleaned]))

    def _build_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not results:
            return {
                "average_overlap_word_count": 0.0,
                "average_target_word_count": 0.0,
                "average_recall_ratio": 0.0,
                "manual_action_count": 0,
                "interruption_count": 0,
                "average_elapsed_seconds": 0.0,
                "recovery_timeline": [],
            }

        overlap_total = sum(item["similarity"]["overlap_word_count"] for item in results)
        target_total = sum(item["similarity"]["target_word_count"] for item in results)
        recall_total = sum(item["similarity"]["recall_ratio"] for item in results)
        manual_actions = 0
        interruption_count = 0
        elapsed_total = sum(item.get("elapsed_seconds", 0.0) for item in results)
        recovery_by_step: Dict[int, List[float]] = {}
        for item in results:
            for step in item["steps"]:
                if step["interrupted"]:
                    interruption_count += 1
                if step["selected_action"] in {"manual_describe", "manual_write"}:
                    manual_actions += 1
                recovery = step.get("recovery_after_step", {})
                if "recall_ratio" in recovery:
                    recovery_by_step.setdefault(int(step.get("step_index", 0)), []).append(float(recovery["recall_ratio"]))
        count = len(results)
        return {
            "average_overlap_word_count": overlap_total / count,
            "average_target_word_count": target_total / count,
            "average_recall_ratio": recall_total / count,
            "manual_action_count": manual_actions,
            "interruption_count": interruption_count,
            "average_elapsed_seconds": elapsed_total / count,
            "recovery_timeline": [
                {
                    "step_index": step_index,
                    "average_recall_ratio": sum(values) / len(values),
                    "sample_count": len(values),
                }
                for step_index, values in sorted(recovery_by_step.items())
            ],
        }


def memory_agent_record_observation(existing_observations: List[Any], key: str, summary: str) -> tuple[List[Any], int]:
    cleaned_key = key.strip()
    cleaned_summary = summary.strip()
    if not cleaned_key or not cleaned_summary:
        return list(existing_observations), 0

    updated = []
    matched = False
    count_after = 1
    for item in existing_observations:
        if item.key == cleaned_key:
            count_after = item.count + 1
            item.count = count_after
            item.summary = cleaned_summary
            updated.append(item)
            matched = True
        else:
            updated.append(item)
    if not matched:
        from .models import PreferenceObservation

        updated.append(PreferenceObservation(key=cleaned_key, summary=cleaned_summary, count=1))
    return updated, count_after


def compute_profile_similarity(target_profile: List[str], helper_profile: List[str]) -> Dict[str, Any]:
    target_text = " ".join(target_profile)
    helper_text = " ".join(helper_profile)
    target_tokens = _tokenize(target_text)
    helper_tokens = _tokenize(helper_text)
    overlap = _word_overlap_counter(target_tokens, helper_tokens)
    exact_item_matches = len(set(item.strip().lower() for item in target_profile) & set(item.strip().lower() for item in helper_profile))
    return {
        "target_word_count": len(target_tokens),
        "helper_word_count": len(helper_tokens),
        "overlap_word_count": overlap,
        "recall_ratio": overlap / len(target_tokens) if target_tokens else 0.0,
        "precision_ratio": overlap / len(helper_tokens) if helper_tokens else 0.0,
        "exact_profile_item_matches": exact_item_matches,
    }


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9']+", text.lower())


def _word_overlap_count(left: str, right: str) -> int:
    return _word_overlap_counter(_tokenize(left), _tokenize(right))


def _word_overlap_counter(left_tokens: List[str], right_tokens: List[str]) -> int:
    left_counter = Counter(left_tokens)
    right_counter = Counter(right_tokens)
    return sum(min(left_counter[word], right_counter[word]) for word in left_counter.keys() & right_counter.keys())


def default_simulation_output_path() -> Path:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return SIMULATION_OUTPUT_DIR / f"fake_profile_simulation_{timestamp}.json"


async def run_default_fake_profile_simulation(
    count: int = 100,
    seed: int = 7,
    model: str = "gpt-4o-mini",
    max_steps: int = 6,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    scenarios = generate_fake_user_scenarios(count=count, seed=seed)
    simulator = HeadlessInterruptionSimulator(model=model, max_steps=max_steps)
    path = output_path or default_simulation_output_path()
    return await simulator.run_batch(scenarios=scenarios, output_path=path)


def _offline_previous_sentence(scenario: FakeUserScenario, step_index: int) -> str:
    return _offline_generation_for_step(
        scenario=scenario,
        step_index=max(1, step_index - 1),
        profile_item="",
        satisfies_profile=True,
    )


def _offline_current_sentence(
    scenario: FakeUserScenario,
    step_index: int,
    profile_item: str,
    satisfies_profile: bool,
) -> str:
    passage = _offline_generation_for_step(scenario, step_index, profile_item, satisfies_profile)
    sentences = re.split(r"(?<=[.!?])\s+", passage.strip())
    return sentences[-1] if sentences else passage


def _offline_generation_for_step(
    scenario: FakeUserScenario,
    step_index: int,
    profile_item: str,
    satisfies_profile: bool,
) -> str:
    topic = _topic_label(scenario.task)
    if topic.lower() == "bioethics":
        return _offline_bioethics_passage(step_index, profile_item, satisfies_profile)
    return _offline_domain_passage(topic, step_index, satisfies_profile)


def _offline_domain_passage(topic: str, step_index: int, satisfies_profile: bool) -> str:
    material = _domain_material(topic)
    issue = material["issues"][(step_index - 1) % len(material["issues"])]
    mechanism = material["mechanisms"][(step_index - 1) % len(material["mechanisms"])]
    evidence = material["evidence"][(step_index - 1) % len(material["evidence"])]
    counter = material["counterarguments"][(step_index - 1) % len(material["counterarguments"])]
    if satisfies_profile:
        templates = [
            (
                f"The debate over {issue} in {topic} turns on a mechanism, not just a slogan. "
                f"{mechanism} "
                f"{evidence} "
                f"That evidence narrows the claim while still leaving room for the counterpressure that {counter.lower()}"
            ),
            (
                f"A stronger account of {topic} begins with {issue}. "
                f"{mechanism} "
                f"The relevant evidence is not merely illustrative: {evidence[0].lower() + evidence[1:]} "
                f"The main objection is serious because {counter.lower()}"
            ),
            (
                f"{issue.capitalize()} shows why arguments in {topic} need both evidence and qualification. "
                f"{mechanism} "
                f"{counter} "
                f"The best version of the claim therefore depends on {evidence[0].lower() + evidence[1:]}"
            ),
        ]
    else:
        templates = [
            (
                f"{topic.capitalize()} includes an important debate about {issue}. "
                f"Many scholars have different views, and the issue has broad implications for theory and practice. "
                f"The paragraph names the controversy but does not yet explain the mechanism, evidence, or counterargument."
            ),
            (
                f"Another major issue in {topic} is {issue}. "
                f"It matters because it affects people, institutions, and future research. "
                f"The draft sounds relevant, but it relies on broad claims instead of showing how the argument works."
            ),
            (
                f"The essay next turns to {issue} as a complicated part of {topic}. "
                f"There are benefits and risks on both sides, and the topic deserves careful attention. "
                f"This version introduces the content, but it does not yet make the evidence or objection do analytical work."
            ),
        ]
    return templates[(step_index - 1) % len(templates)]


def _domain_material(topic: str) -> Dict[str, List[str]]:
    materials = {
        "machine learning": {
            "issues": ["model generalization", "algorithmic bias", "interpretability", "data privacy", "human oversight"],
            "mechanisms": [
                "A model trained on narrow data can perform well in benchmarks while failing when distributions shift.",
                "Bias enters through labels, sampling, objectives, and deployment contexts rather than through code alone.",
                "Interpretability matters because users need to know when a prediction is reliable enough to guide action.",
            ],
            "evidence": [
                "Audit studies and error analyses show that performance often varies across groups and settings.",
                "Ablation tests, external validation, and post-deployment monitoring provide stronger evidence than a single accuracy score.",
                "Case studies in health, hiring, and credit scoring show how small model errors can produce institutional consequences.",
            ],
            "counterarguments": [
                "some critics argue that strict constraints can slow useful innovation.",
                "a highly interpretable model may perform worse than a less transparent one.",
                "data restrictions can protect privacy while also limiting research quality.",
            ],
        },
        "climate policy": {
            "issues": ["carbon pricing", "adaptation funding", "energy transition", "climate justice", "industrial regulation"],
            "mechanisms": [
                "Carbon pricing changes incentives by making emissions visible in production and consumption costs.",
                "Adaptation policy works through infrastructure, insurance, land-use rules, and emergency planning.",
                "Industrial regulation matters because a small number of sectors produce a large share of emissions.",
            ],
            "evidence": [
                "Comparative policy studies show that durable coalitions matter as much as formal targets.",
                "Emissions inventories and sectoral data reveal where policy pressure is most likely to reduce output.",
                "Disaster losses and heat exposure data show why adaptation cannot be postponed until mitigation succeeds.",
            ],
            "counterarguments": [
                "households may bear costs before long-term benefits become visible.",
                "rapid transition can harm workers and regions tied to fossil-fuel industries.",
                "poorly designed policy can shift emissions abroad rather than reducing them.",
            ],
        },
        "comparative literature": {
            "issues": ["translation", "world literature", "genre circulation", "colonial archives", "reader reception"],
            "mechanisms": [
                "Translation changes not only language but also rhythm, cultural reference, and implied audience.",
                "Texts circulate through publishers, schools, prizes, and political institutions that shape what counts as global literature.",
                "Genre travels unevenly because local traditions adapt imported forms to different historical pressures.",
            ],
            "evidence": [
                "Close reading can show how a metaphor or narrative voice shifts across languages.",
                "Publication histories and reception records reveal which works become legible to foreign readers.",
                "Archival evidence links literary form to institutions of empire, education, and nationalism.",
            ],
            "counterarguments": [
                "too much institutional focus can flatten aesthetic differences.",
                "comparison can reproduce the hierarchies it claims to analyze.",
                "translation may create new literary value rather than merely losing an original meaning.",
            ],
        },
        "public health": {
            "issues": ["vaccination policy", "health inequality", "surveillance", "risk communication", "resource allocation"],
            "mechanisms": [
                "Vaccination works through herd effects, trust, access, and perceived risk rather than individual choice alone.",
                "Health inequality persists because exposure, treatment, income, and environment reinforce one another.",
                "Surveillance can detect outbreaks early, but it also changes how communities experience state authority.",
            ],
            "evidence": [
                "Epidemiological data show that small changes in uptake can alter population-level risk.",
                "Neighborhood-level studies link morbidity to housing, work, pollution, and care access.",
                "Communication trials show that trust often matters more than information volume.",
            ],
            "counterarguments": [
                "mandates may protect communities while weakening trust among skeptical groups.",
                "privacy limits can slow the collection of useful outbreak data.",
                "individual behavior matters, but it cannot explain structural exposure by itself.",
            ],
        },
        "urban sociology": {
            "issues": ["gentrification", "housing segregation", "public transit", "policing", "neighborhood displacement"],
            "mechanisms": [
                "Gentrification works through rent gaps, investment flows, zoning rules, and cultural rebranding.",
                "Segregation persists because housing markets convert past exclusion into present opportunity gaps.",
                "Transit shapes access to jobs, schools, and care by changing the practical geography of a city.",
            ],
            "evidence": [
                "Census data, eviction records, and rent histories can show displacement before it becomes visible in street life.",
                "Ethnographic work reveals how residents experience policy changes that aggregate data can miss.",
                "Transit-use and commute-time data show who benefits from infrastructure investment.",
            ],
            "counterarguments": [
                "new investment can improve services even as it raises displacement risk.",
                "neighborhood change is not always reducible to a single class dynamic.",
                "local resistance can protect residents but also restrict housing supply.",
            ],
        },
        "education policy": {
            "issues": ["standardized testing", "teacher accountability", "school funding", "curriculum reform", "college access"],
            "mechanisms": [
                "Testing changes classroom behavior by linking scores to evaluation, funding, and institutional reputation.",
                "Funding formulas shape opportunity by determining class size, staffing, facilities, and enrichment.",
                "Curriculum reform works only when teacher training, materials, and assessment move together.",
            ],
            "evidence": [
                "Longitudinal studies show that school effects interact with income, neighborhood, and family resources.",
                "District comparisons reveal how equal rules can produce unequal outcomes when local capacity differs.",
                "Classroom observations can explain why a policy that works on paper fails in implementation.",
            ],
            "counterarguments": [
                "accountability can expose failure even when it narrows instruction.",
                "more funding matters, but governance determines how resources reach students.",
                "choice policies may expand options for some families while leaving others behind.",
            ],
        },
        "economic history": {
            "issues": ["industrialization", "financial crises", "trade shocks", "labor institutions", "state capacity"],
            "mechanisms": [
                "Industrialization changes productivity through technology, labor discipline, capital investment, and market integration.",
                "Financial crises spread when leverage, confidence, and institutional guarantees interact.",
                "Trade shocks reshape regions by altering prices, employment, and political coalitions.",
            ],
            "evidence": [
                "Wage series, price data, and firm records help distinguish growth from redistribution.",
                "Natural experiments and archival data can show whether institutions caused change or merely accompanied it.",
                "Regional comparisons reveal why the same policy can produce different economic paths.",
            ],
            "counterarguments": [
                "quantitative evidence can miss informal labor and household production.",
                "institutional explanations sometimes understate geography and resource endowments.",
                "short-run harm may coexist with long-run growth, making welfare claims difficult.",
            ],
        },
        "human-computer interaction": {
            "issues": ["usability", "automation", "trust calibration", "accessibility", "interface personalization"],
            "mechanisms": [
                "Usability affects behavior by shaping attention, error recovery, and the cost of changing a decision.",
                "Automation changes responsibility because users may defer to systems they do not fully understand.",
                "Accessibility works when design anticipates variation in perception, mobility, language, and context.",
            ],
            "evidence": [
                "User studies, task completion data, and error logs show where design intentions break down.",
                "Field deployments reveal forms of misuse that lab studies often miss.",
                "Accessibility audits connect interface choices to measurable exclusion.",
            ],
            "counterarguments": [
                "friction can sometimes protect users from acting too quickly.",
                "personalization may improve relevance while reducing transparency.",
                "high trust can be useful until the system fails in an unfamiliar case.",
            ],
        },
        "political theory": {
            "issues": ["legitimacy", "democratic representation", "freedom", "equality", "civil disobedience"],
            "mechanisms": [
                "Legitimacy depends on how institutions convert coercive power into publicly defensible authority.",
                "Representation links citizens to decisions through elections, parties, deliberation, and organized interests.",
                "Freedom changes meaning depending on whether domination, interference, or capability is treated as the central threat.",
            ],
            "evidence": [
                "Historical cases show how constitutional forms can survive while democratic substance erodes.",
                "Institutional comparisons reveal how rules distribute voice unevenly across groups.",
                "Conceptual analysis clarifies why the same policy can appear liberating under one theory and coercive under another.",
            ],
            "counterarguments": [
                "abstract principles can ignore the compromises required by institutional design.",
                "majority rule can express equality while threatening vulnerable minorities.",
                "civil disobedience can deepen democracy or undermine lawful stability, depending on context.",
            ],
        },
    }
    return materials.get(topic.lower(), {
        "issues": [f"the central dispute in {topic}", f"the evidence base in {topic}", f"the institutional stakes of {topic}"],
        "mechanisms": [f"The mechanism links individual decisions to broader outcomes in {topic}."],
        "evidence": [f"Comparative evidence helps separate plausible claims from broad assertion in {topic}."],
        "counterarguments": [f"critics can argue that the evidence is incomplete or context-dependent."],
    })


def _offline_bioethics_passage(step_index: int, profile_item: str, satisfies_profile: bool) -> str:
    weak_passages = [
        (
            "Bioethics is a broad field that deals with medicine, technology, public health, and social values. "
            "Many issues in the field are important because they affect patients, professionals, and society. "
            "The main point is that new medical capacities create many complicated questions that require careful discussion."
        ),
        (
            "Patient autonomy is one of the major debates in bioethics. "
            "Patients often want control over their own bodies, while doctors have training that helps them decide what treatment is best. "
            "This creates a difficult situation because both sides have important concerns."
        ),
        (
            "Informed consent is also significant because it helps patients understand medical decisions. "
            "It involves information, understanding, and voluntary choice, but the process can be difficult in real clinical settings. "
            "For this reason, informed consent remains a central topic in medical ethics."
        ),
        (
            "End-of-life care is another important debate. "
            "Some people believe patients should be able to choose death when suffering is severe, while others worry that this changes the role of medicine. "
            "Both sides raise serious concerns about dignity, safety, and professional responsibility."
        ),
        (
            "Assisted dying is controversial because it involves patient choice and the possibility of abuse. "
            "Supporters point to autonomy and compassion, while critics point to pressure on vulnerable patients. "
            "The debate shows that bioethics must balance individual preference with social protection."
        ),
        (
            "Reproductive ethics includes abortion, embryo selection, surrogacy, and genetic testing. "
            "These issues are complicated because they involve bodies, families, future children, and social values. "
            "Different people disagree because they begin from different moral assumptions."
        ),
        (
            "Prenatal testing and embryo selection can reduce suffering, but they can also raise concerns about disability and social expectations. "
            "Some people think selection is a responsible form of prevention, while others think it can express a narrow view of valuable life. "
            "This is a difficult debate with many implications."
        ),
        (
            "Bioethics also considers scarce resources, including organs, vaccines, and intensive-care beds. "
            "Allocation decisions are hard because they require fairness, effectiveness, and public trust. "
            "The issue is especially important when demand is greater than supply."
        ),
        (
            "Genetic editing creates another debate because it may prevent disease but may also change future generations. "
            "The technology is powerful, and society must decide how to use it responsibly. "
            "This shows why bioethics has to keep up with scientific change."
        ),
        (
            "Medical artificial intelligence raises questions about accuracy, bias, and responsibility. "
            "Algorithms may help clinicians, but they may also reproduce unequal data patterns. "
            "This makes oversight and accountability important."
        ),
        (
            "Public health ethics often requires balancing individual freedom with collective safety. "
            "Vaccination, quarantine, and disease surveillance all show this tension. "
            "The challenge is deciding when public benefit justifies limits on personal choice."
        ),
        (
            "Overall, bioethics studies difficult questions about medicine and society. "
            "Its debates are important because they shape how people live, suffer, choose, and receive care. "
            "A good essay should consider different views and evidence."
        ),
    ]
    strong_passages = [
        (
            "Bioethics begins where technical capacity outruns shared moral agreement. "
            "Modern medicine can prolong dying, screen embryos, collect biological data, and delegate decisions to machines, but each capacity redistributes risk and authority. "
            "A research-style account therefore has to ask not whether innovation is simply good or bad, but how it changes vulnerability, consent, and responsibility."
        ),
        (
            "The autonomy debate is not a contest between patient preference and medical expertise alone. "
            "Its mechanism is institutional: because clinicians control specialized knowledge, patients can be reduced to objects of judgment unless consent procedures return agency to them. "
            "Shared decision-making is stronger than pure autonomy or pure paternalism because it lets clinicians define medically reasonable options while patients decide which risks fit their values."
        ),
        (
            "Informed consent matters because disclosure without comprehension can still leave power untouched. "
            "A patient who signs a form may not understand probability, alternatives, or the consequences of refusal. "
            "The ethical test is therefore practical: whether the process gives the patient enough understanding to make a decision that is genuinely their own."
        ),
        (
            "End-of-life care turns on the difference between preserving life and prolonging suffering. "
            "Ventilators, feeding tubes, and sedation can sustain biological function after recovery or consciousness has become unlikely. "
            "The ethical question is whether medicine serves the patient by extending time, or fails the patient by extending a condition the patient has judged intolerable."
        ),
        (
            "The strongest objection to assisted dying is not simply that death is bad. "
            "It is that choice can be shaped by disability stigma, family burden, unequal care, or cost pressure. "
            "That counterargument forces supporters to show why safeguards, reporting, and independent review can protect autonomy rather than merely assume it."
        ),
        (
            "Reproductive ethics joins bodily autonomy to disputes about moral status and social equality. "
            "Abortion restrictions do not erase abortion; they often change its timing, safety, and accessibility. "
            "That evidence matters because the ethical debate is partly about what law does to actual bodies, not only what principles announce."
        ),
        (
            "Embryo selection and prenatal testing reveal a subtler conflict. "
            "Preventing severe disease can be an act of care, yet selecting against traits can also echo social prejudice about which lives are worth welcoming. "
            "The ethical line is not between choice and coercion in the abstract, but between treatment-oriented prevention and normalization pressure."
        ),
        (
            "Allocation debates make justice concrete. "
            "When organs or intensive-care beds are scarce, a system must choose among urgency, expected benefit, waiting time, and equal respect. "
            "No formula removes moral loss, but a transparent rule can prevent bedside decisions from becoming hidden privilege."
        ),
        (
            "Gene editing changes the scale of bioethical responsibility. "
            "A therapy for one patient affects consent, but a heritable edit may affect people who cannot yet speak. "
            "That temporal asymmetry explains why safety evidence alone is not enough; governance must also address who gets to authorize risk for future persons."
        ),
        (
            "Medical AI shifts ethical attention from individual judgment to system design. "
            "A model may improve diagnosis while embedding bias from the data used to train it. "
            "Responsibility therefore cannot stop with the clinician using the tool; it also belongs to the institutions that validate, monitor, and deploy it."
        ),
        (
            "Public health ethics shows why autonomy is relational rather than isolated. "
            "A vaccination decision, quarantine order, or surveillance program affects others through transmission, trust, and unequal exposure to harm. "
            "The hard question is not whether liberty matters, but what kind of evidence justifies limiting liberty for collective protection."
        ),
        (
            "The major debates in bioethics share a common structure. "
            "Each begins with a technical power, then asks who bears its risks, who controls its use, and whose vulnerability becomes easier to ignore. "
            "A strong essay should therefore connect principle, mechanism, counterargument, and evidence instead of treating ethical positions as a list."
        ),
    ]
    passages = strong_passages if satisfies_profile else weak_passages
    return passages[(step_index - 1) % len(passages)]


def _offline_style_aligned_passage(topic: str, step_index: int, profile_item: str) -> str:
    lowered = profile_item.lower()
    if "repetition" in lowered or "fresh move" in lowered:
        return (
            f"The draft now shifts from naming the debate in {topic} to asking what the debate changes for the reader. "
            f"Evidence, method, and interpretation pull in different directions, so the paragraph makes a new argumentative move. "
            f"That turn prevents the essay from circling the same claim in different words."
        )
    if "specific" in lowered or "precise" in lowered or "vague" in lowered:
        return (
            f"The revision replaces broad language with sharper terms: evidence becomes traceable data, caution becomes uncertainty about scope, and impact becomes a limit on what the argument can prove. "
            f"Those concrete words make the claim easier to test. "
            f"The prose therefore sounds less inflated and more accountable."
        )
    if "tone" in lowered or "measured" in lowered or "restrained" in lowered or "qualification" in lowered:
        return (
            f"The paragraph advances the claim with restraint. "
            f"It suggests that the evidence points in a useful direction, while leaving room for limits in method and context. "
            f"The result is confident without becoming overstated."
        )
    if "example" in lowered or "concrete" in lowered or "tradeoff" in lowered:
        return (
            f"The paragraph anchors the abstract claim in a concrete case. "
            f"A rule may improve consistency while also narrowing judgment in borderline situations. "
            f"That tradeoff makes the argument visible rather than merely decorative."
        )
    if "mechanism" in lowered or "causal" in lowered or "reasoning" in lowered:
        return (
            f"The paragraph explains the mechanism behind the claim. "
            f"The reader can see how a change in incentives alters interpretation, then how that altered interpretation changes the evidence a writer can use. "
            f"The paragraph therefore gives a reason, not just a conclusion."
        )
    if "transition" in lowered or "connect" in lowered or "logical relation" in lowered:
        return (
            f"The next passage begins by naming its relation to the prior point. "
            f"Because the earlier claim depends on evidence, this paragraph turns to the structure that makes evidence persuasive. "
            f"The transition carries the argument forward instead of simply adding another topic."
        )
    if "counter" in lowered or "opposing" in lowered or "objections" in lowered:
        return (
            f"The paragraph gives the opposing view enough force to matter. "
            f"A skeptical reader might accept the evidence but reject the inference drawn from it. "
            f"By answering that pressure directly, the paragraph makes the main claim more credible."
        )
    if "paragraph" in lowered or "structure" in lowered or "topic sentence" in lowered or "one governing idea" in lowered:
        return (
            f"The paragraph opens with a debatable claim rather than a topic label. "
            f"Each following sentence tests or qualifies that claim instead of wandering into a list. "
            f"The paragraph closes by sharpening the implication for the larger essay."
        )
    if "concise" in lowered or "compact" in lowered or "rhythm" in lowered:
        return (
            f"The paragraph uses a compact rhythm. "
            f"A short claim sets the direction; a longer sentence explains the pressure behind it. "
            f"The final sentence lands cleanly."
        )
    return (
        f"The passage keeps the prose analytical and controlled. "
        f"It states a claim, explains why the claim matters, and avoids drifting into generic summary. "
        f"The style remains readable while still carrying argumentative weight."
    )


def _offline_style_mismatch_passage(topic: str, step_index: int) -> str:
    templates = [
        (
            f"The essay opens by saying that {topic} is complex and widely debated. "
            f"It gestures toward evidence, values, and institutions, but it does not yet state a contestable claim. "
            f"The paragraph feels smooth while leaving the reader unsure what kind of argument will follow."
        ),
        (
            f"The next passage adds that scholars disagree about {topic} for many reasons. "
            f"It mentions uncertainty, public concern, and the need for further analysis. "
            f"Those phrases keep the draft moving, but they also flatten the prose into a list of generalities."
        ),
        (
            f"The draft then notes that different approaches can produce different outcomes. "
            f"It treats this point as important without explaining what changes, who is affected, or why the distinction matters. "
            f"As a result, the paragraph sounds plausible but thin."
        ),
        (
            f"The following paragraph returns to the same broad claim about debate and evidence. "
            f"It repeats the idea that context matters, then adds that careful thinking is necessary. "
            f"The passage does not build a sharper relation between its sentences."
        ),
        (
            f"The draft tries to transition into a new section by announcing another aspect of {topic}. "
            f"It names the topic but not the argumentative pressure behind it. "
            f"The reader receives a new heading in sentence form rather than a developed turn in the essay."
        ),
        (
            f"The essay next claims that evidence should be balanced with caution. "
            f"Yet it does not explain what kind of evidence carries the most weight or how caution changes the claim. "
            f"The result is orderly, but the paragraph remains too general to guide revision."
        ),
        (
            f"The passage introduces a possible objection and then moves past it quickly. "
            f"It says critics may disagree, but it does not give their concern enough shape to test the main argument. "
            f"The prose gestures toward contrast without making the contrast do analytical work."
        ),
        (
            f"The draft describes {topic} as a field with practical and theoretical stakes. "
            f"It joins those stakes with smooth connective phrases, but the sentences do not clearly depend on one another. "
            f"The paragraph reads like adjacent observations rather than a single developing claim."
        ),
        (
            f"The essay then leans on abstract nouns such as impact, complexity, and significance. "
            f"Those terms make the passage sound academic, but they blur the action of the argument. "
            f"The reader can follow the topic without seeing the precise writing move."
        ),
        (
            f"The next paragraph offers a cautious conclusion about {topic}. "
            f"It avoids making a strong error, but it also avoids naming the exact limit, mechanism, or implication. "
            f"The prose is safe, yet it does not recover the user's preferred style."
        ),
    ]
    return templates[(step_index - 1) % len(templates)]


def _topic_label(task: str) -> str:
    lowered = task.lower()
    for domain in sorted(ACADEMIC_DOMAINS, key=len, reverse=True):
        if domain in lowered:
            return domain
    match = re.search(r"\bin ([^,.]+)", task)
    if match:
        return match.group(1).strip()
    match = re.search(r"\babout ([^,.]+)", task)
    if match:
        return match.group(1).strip()
    return "the topic"


def _offline_assess_generation(
    target_profile: List[str],
    helper_profile: List[str],
    latest_chunk: str,
    expected_item: str,
    satisfies_profile: bool,
) -> Dict[str, Any]:
    already_recovered = expected_item in helper_profile
    interrupt = (not already_recovered) and not satisfies_profile
    if interrupt:
        reason = (
            "The generated passage is fluent but misses an unrecovered writing-style preference: "
            f"{expected_item}"
        )
    else:
        reason = (
            "The generated passage is acceptable because it either follows the expected writing preference "
            "or the preference is already recovered."
        )
    return {
        "interrupt": interrupt,
        "reason": reason,
        "confidence": 0.86 if interrupt else 0.68,
        "expected_item": expected_item,
        "coverage": 1.0 if satisfies_profile else 0.0,
        "target_profile_size": len(target_profile),
    }


def _offline_system_interpretation(
    scenario: FakeUserScenario,
    step_index: int,
    target_item: str,
    missed_item: str,
    interruption_point: Dict[str, Any],
) -> Dict[str, Any]:
    reason_id = [
        "LANG_TOO_GENERAL",
        "CONTENT_MECHANISM",
        "CONTENT_EXAMPLE",
        "CONTENT_REFINED",
        "CONTENT_TRANSITION",
        "LANG_TONE",
        "CONTENT_OPPOSITE",
        "LANG_CONCISE",
    ][(step_index - 1) % 8]
    return {
        "stop_point": interruption_point,
        "likely_user_intent": f"The user likely wants the draft to honor this profile constraint: {missed_item}",
        "reason_candidates": [
            {
                "id": reason_id,
                "reason": f"The interrupted passage is under-specified relative to the hidden writing-style preference: {missed_item}",
            },
            {
                "id": "CONTENT_REFINED",
                "reason": f"The replacement should convert the broad passage into a more profile-specific writing move for {scenario.user_id}.",
            },
        ],
        "replacement_guidance": {
            "goal": f"Revise the interrupted passage so its wording, style, or structure reflects: {target_item}",
            "desired_properties": [target_item, "stay aligned with the essay task", "keep the edit passage-level"],
            "avoid": ["generic filler", "ignoring the recovered profile preference"],
        },
        "profile_update": {
            "preference_summary": target_item,
            "confidence": 0.84,
            "preference_key": _profile_key(target_item),
            "scope": "global",
            "rationale": "Offline simulator treats this as a stable hidden preference exposed by interruption behavior.",
        },
    }


def _offline_replacement_options(target_item: str, missed_item: str) -> List[Dict[str, Any]]:
    return [
        {
            "option_id": str(uuid.uuid4()),
            "reason_id": "OFFLINE_PROFILE_MATCH",
            "reason": f"Recover hidden profile preference: {target_item}",
            "explanation": f"The simulator interrupted because the draft missed: {missed_item}",
            "replacement_text": f"Revise the passage so it follows this stable writing preference: {target_item}",
            "option_kind": "reason",
            "category": "profile",
        },
        {
            "option_id": str(uuid.uuid4()),
            "reason_id": "OFFLINE_LOCAL_FIX",
            "reason": "Make a local passage-level fix.",
            "explanation": "This option repairs the current passage but is less useful for long-term profile recovery.",
            "replacement_text": "Revise the passage with a clearer local claim.",
            "option_kind": "reason",
            "category": "local",
        },
    ]


def _offline_writing_fill_options(
    target_item: str,
    scenario: FakeUserScenario,
    rng: random.Random,
) -> List[Dict[str, Any]]:
    options = [
        {
            "option_id": str(uuid.uuid4()),
            "reason_id": "STYLE_SPECIFICITY",
            "reason": "Make the passage more specific and less generic.",
            "explanation": "Tightens vague wording and makes the claim easier to evaluate.",
            "replacement_text": "Revise the passage with more specific wording and a clearer claim.",
            "option_kind": "reason",
            "category": "writing_fill",
            "preference_summary": "Use more specific wording instead of broad or generic phrasing.",
        },
        {
            "option_id": str(uuid.uuid4()),
            "reason_id": "STRUCTURE_TRANSITION",
            "reason": "Improve the argumentative transition.",
            "explanation": "Connects the passage more clearly to the prior idea and the essay task.",
            "replacement_text": "Revise the passage so each sentence connects more explicitly to the prior idea and task.",
            "option_kind": "reason",
            "category": "writing_fill",
            "preference_summary": "Make each sentence connect more explicitly to the prior idea and task.",
        },
        {
            "option_id": str(uuid.uuid4()),
            "reason_id": "STYLE_MECHANISM",
            "reason": "Explain the mechanism behind the claim.",
            "explanation": "Adds causal or institutional reasoning instead of only naming the issue.",
            "replacement_text": "Revise the passage so it explains the mechanism or reasoning behind the claim.",
            "option_kind": "reason",
            "category": "writing_fill",
            "preference_summary": "Explain the mechanism or reasoning behind important claims.",
        },
        {
            "option_id": str(uuid.uuid4()),
            "reason_id": "STYLE_CONCISE",
            "reason": "Make the prose clearer and more concise.",
            "explanation": "Reduces padding while keeping the passage analytical.",
            "replacement_text": "Revise the passage with clearer, lighter, and more concise sentences.",
            "option_kind": "reason",
            "category": "writing_fill",
            "preference_summary": "Prefer clearer, lighter, and more concise sentences.",
        },
        {
            "option_id": str(uuid.uuid4()),
            "reason_id": "STRUCTURE_CLAIM",
            "reason": "Open with a debatable claim.",
            "explanation": "Replaces a broad topic opening with a claim the paragraph can develop.",
            "replacement_text": "Revise the passage so the paragraph opens with a debatable claim rather than a broad topic sentence.",
            "option_kind": "reason",
            "category": "writing_fill",
            "preference_summary": "Open paragraphs with a debatable claim rather than a broad topic sentence.",
        },
    ]
    if rng.random() < 0.75:
        options.insert(
            rng.randrange(0, len(options) + 1),
            {
                "option_id": str(uuid.uuid4()),
                "reason_id": "MATCHED_LATENT_STYLE",
                "reason": f"Match the user's latent style preference: {target_item}",
                "explanation": "This option most directly fits the simulated user's hidden writing preference.",
                "replacement_text": f"Revise the passage so it follows this writing preference: {target_item}",
                "option_kind": "reason",
                "category": "writing_fill",
                "preference_summary": target_item,
            },
        )
    options.append(
        {
            "option_id": str(uuid.uuid4()),
            "reason_id": "OTHER",
            "reason": "None of these fit.",
            "explanation": "The simulated user can provide a custom preference if no generated option satisfies them.",
            "replacement_text": "",
            "option_kind": "other_describe",
            "category": "custom",
            "preference_summary": "",
        }
    )
    return options


def _offline_choose_writing_fill(
    target_item: str,
    options: List[Dict[str, Any]],
) -> Dict[str, Any]:
    exact = next((item for item in options if item.get("preference_summary") == target_item), None)
    if exact is not None:
        return {
            "selected_action": "select_option",
            "selected_option": exact,
            "manual_input": "",
            "rationale": "The simulator selected the writing-fill option that matched its hidden style preference.",
        }
    return {
        "selected_action": "manual_describe",
        "selected_option": next(item for item in options if item.get("reason_id") == "OTHER"),
        "manual_input": target_item,
        "rationale": "No writing-fill option matched the hidden preference, so the simulator stated what it wanted.",
    }


def _offline_interpret_selected_feedback(
    selected_option: Dict[str, Any],
    manual_input: str,
    target_item: str,
    interruption_point: Dict[str, Any],
) -> Dict[str, Any]:
    summary = manual_input.strip() or str(selected_option.get("preference_summary", "")).strip() or target_item
    source = "custom request" if manual_input.strip() else "selected writing-fill option"
    return {
        "stop_point": interruption_point,
        "likely_user_intent": f"The user preference is inferred from the {source}: {summary}",
        "reason_candidates": [
            {
                "id": str(selected_option.get("reason_id", "SELECTED_FEEDBACK")),
                "reason": f"The selected feedback indicates this reusable writing preference: {summary}",
            }
        ],
        "replacement_guidance": {
            "goal": f"Revise future passages to reflect: {summary}",
            "desired_properties": [summary, "preserve the essay's content", "apply only after repeated evidence"],
            "avoid": ["treating one isolated click as a stable global preference"],
        },
        "profile_update": {
            "preference_summary": summary,
            "confidence": 0.72,
            "preference_key": _profile_key(summary),
            "scope": "local_until_repeated",
            "rationale": f"Interpreted from the {source}; promoted only after repeated similar selections.",
        },
    }


def _offline_record_preference_observation(
    observations: Dict[str, Dict[str, Any]],
    summary: str,
) -> tuple[List[Dict[str, Any]], int]:
    key = _profile_key(summary)
    current = observations.get(key, {"key": key, "summary": summary, "count": 0})
    current["count"] = int(current.get("count", 0)) + 1
    current["summary"] = summary
    observations[key] = current
    return list(observations.values()), int(current["count"])


def _profile_key(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in text).strip("_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned[:48] or "offline_profile_preference"


def _truncate(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)].rstrip() + "..."


def run_offline_fake_profile_recovery(
    count: int = 100,
    seed: int = 7,
    max_steps: int = 6,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    scenarios = generate_fake_user_scenarios(count=count, seed=seed)
    started_at = time.time()
    results = []
    rng = random.Random(seed + 1000)
    for scenario in scenarios:
        helper_profile: List[str] = []
        helper_local_memory: List[str] = []
        observation_map: Dict[str, Dict[str, Any]] = {}
        steps = []
        cumulative = 0.0
        for step_index in range(1, max_steps + 1):
            step_elapsed = rng.uniform(24.0, 118.0)
            cumulative += step_elapsed
            target_item = scenario.target_profile[(step_index - 1) % len(scenario.target_profile)]
            recovered_ratio = len(helper_profile) / max(1, len(scenario.target_profile))
            miss_probability = max(0.25, 0.88 - recovered_ratio * 0.45)
            satisfies_profile = rng.random() > miss_probability
            generation_text = _offline_generation_for_step(
                scenario=scenario,
                step_index=step_index,
                profile_item=target_item,
                satisfies_profile=satisfies_profile,
            )
            assessment = _offline_assess_generation(
                target_profile=scenario.target_profile,
                helper_profile=helper_profile,
                latest_chunk=generation_text,
                expected_item=target_item,
                satisfies_profile=satisfies_profile,
            )
            interruption_point = {
                "termination_point": _truncate(generation_text, 140),
                "last_sentence": _offline_previous_sentence(scenario, step_index),
                "current_sentence": _offline_current_sentence(
                    scenario=scenario,
                    step_index=step_index,
                    profile_item=target_item,
                    satisfies_profile=satisfies_profile,
                ),
                "replacement_start": 0,
            }
            if not assessment["interrupt"]:
                steps.append(
                    asdict(
                        SimulationStepRecord(
                            step_index=step_index,
                            elapsed_seconds=step_elapsed,
                            cumulative_elapsed_seconds=cumulative,
                            generation_text=generation_text,
                            interrupted=False,
                            interruption_reason=assessment["reason"],
                            interruption_point=interruption_point,
                            simulator_confidence=assessment["confidence"],
                            simulator_decision_rationale=(
                                "The generated passage satisfied the expected style preference or the preference was already recovered."
                            ),
                            recovery_after_step=compute_profile_similarity(scenario.target_profile, helper_profile),
                            helper_profile_after_step=list(helper_profile),
                            helper_local_memory_after_step=list(helper_local_memory),
                            helper_observations_after_step=list(observation_map.values()),
                            memory_scope="offline_no_update",
                        )
                    )
                )
                continue

            replacement_options = _offline_writing_fill_options(target_item, scenario, rng)
            selected_payload = _offline_choose_writing_fill(target_item, replacement_options)
            selected_option = selected_payload["selected_option"]
            selected_action = selected_payload["selected_action"]
            manual_input = selected_payload["manual_input"]
            inferred_summary = manual_input or str(selected_option.get("preference_summary", "")).strip() or target_item
            system_interpretation = _offline_interpret_selected_feedback(
                selected_option=selected_option,
                manual_input=manual_input,
                target_item=target_item,
                interruption_point=interruption_point,
            )
            helper_local_memory = list(dict.fromkeys(helper_local_memory + [inferred_summary]))
            observations_after, count_after = _offline_record_preference_observation(observation_map, inferred_summary)
            promoted_summary = ""
            memory_scope = "offline_local_observation"
            if count_after >= PREFERENCE_PROMOTION_THRESHOLD and inferred_summary not in helper_profile:
                helper_profile = list(dict.fromkeys(helper_profile + [inferred_summary]))
                promoted_summary = inferred_summary
                memory_scope = "offline_promoted_global"
            steps.append(
                asdict(
                    SimulationStepRecord(
                        step_index=step_index,
                        elapsed_seconds=step_elapsed,
                        cumulative_elapsed_seconds=cumulative,
                        generation_text=generation_text,
                        interrupted=True,
                        interruption_reason=assessment["reason"],
                        interruption_point=interruption_point,
                        simulator_confidence=assessment["confidence"],
                        simulator_decision_rationale=(
                            f"The passage missed a writing preference; simulator chose feedback and interpreter inferred: {inferred_summary}"
                        ),
                        system_interpretation=system_interpretation,
                        recovery_after_step=compute_profile_similarity(scenario.target_profile, helper_profile),
                        replacement_options=replacement_options,
                        selected_action=selected_action,
                        selected_reason_id=selected_option["reason_id"],
                        selected_reason=selected_option["reason"],
                        selected_revision=selected_option.get("replacement_text", "") or manual_input,
                        manual_input=manual_input,
                        helper_profile_after_step=list(helper_profile),
                        helper_local_memory_after_step=list(helper_local_memory),
                        helper_observations_after_step=observations_after,
                        profile_summary_added=promoted_summary,
                        memory_scope=memory_scope,
                    )
                )
            )
        similarity = compute_profile_similarity(scenario.target_profile, helper_profile)
        results.append(
            {
                "user_id": scenario.user_id,
                "task": scenario.task,
                "target_profile": list(scenario.target_profile),
                "helper_profile": helper_profile,
                "helper_local_memory": helper_local_memory,
                "helper_observations": list(observation_map.values()),
                "revision_log": [],
                "steps": steps,
                "final_text": "",
                "elapsed_seconds": cumulative,
                "similarity": similarity,
            }
        )

    simulator = HeadlessInterruptionSimulator(max_steps=max_steps)
    payload = {
        "metadata": {
            "scenario_count": len(scenarios),
            "model": "offline-deterministic",
            "max_steps": max_steps,
            "started_at": started_at,
            "finished_at": time.time(),
            "note": "Offline sanity run. It does not call an AI model.",
        },
        "summary": simulator._build_summary(results),
        "results": results,
    }
    path = output_path or default_simulation_output_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

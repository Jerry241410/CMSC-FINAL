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
        standard_count = rng.randint(2, 4)
        custom_count = rng.randint(1, 2)
        profile_items = rng.sample(STANDARD_PREFERENCE_POOL, k=standard_count)
        profile_items.extend(rng.sample(CUSTOM_PREFERENCE_POOL, k=custom_count))
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
            for step_index in range(1, self.max_steps + 1):
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
                            generation_text=generation_text,
                            interrupted=False,
                            interruption_reason=str(assessment.get("reason", "")).strip(),
                            interruption_point={},
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
                        generation_text=generation_text,
                        interrupted=True,
                        interruption_reason=str(assessment.get("reason", "")).strip(),
                        interruption_point=interruption_point,
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
            }

        overlap_total = sum(item["similarity"]["overlap_word_count"] for item in results)
        target_total = sum(item["similarity"]["target_word_count"] for item in results)
        recall_total = sum(item["similarity"]["recall_ratio"] for item in results)
        manual_actions = 0
        interruption_count = 0
        for item in results:
            for step in item["steps"]:
                if step["interrupted"]:
                    interruption_count += 1
                if step["selected_action"] in {"manual_describe", "manual_write"}:
                    manual_actions += 1
        count = len(results)
        return {
            "average_overlap_word_count": overlap_total / count,
            "average_target_word_count": target_total / count,
            "average_recall_ratio": recall_total / count,
            "manual_action_count": manual_actions,
            "interruption_count": interruption_count,
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

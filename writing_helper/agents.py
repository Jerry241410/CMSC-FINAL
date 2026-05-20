import asyncio
import json
import uuid
from typing import Callable, List

from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

from .constants import (
    MAX_REPLACEMENT_WORDS,
    MAX_REASON_OPTIONS,
    PREFERENCE_PROMOTION_THRESHOLD,
    PROFILE_MEMORY_TEMPERATURE,
    REPLACEMENT_TEMPERATURE,
    STREAM_TOKEN_DELAY_SECONDS,
    STREAMING_TEMPERATURE,
    TARGET_REASON_OPTIONS,
)
from .models import (
    InterpreterReasonCandidate,
    InterpreterResult,
    PreferenceObservation,
    ProfileUpdateSuggestion,
    ReplacementGuidance,
    ReplacementOption,
    SessionState,
)
from .text_utils import extract_json_object


class BaseLocalAgent:
    def __init__(self, name: str):
        self.name = name


class StatelessLLMAgent(BaseLocalAgent):
    def __init__(self, name: str, model: str, system_message: str, temperature: float | None = None):
        super().__init__(name)
        client_kwargs = {"model": model}
        if temperature is not None:
            client_kwargs["temperature"] = temperature
        self.model_client = OpenAIChatCompletionClient(**client_kwargs)
        self.agent = AssistantAgent(
            name=name,
            model_client=self.model_client,
            model_client_stream=True,
            system_message=system_message,
        )

    async def complete(self, task: str) -> str:
        parts: List[str] = []
        async for item in self.agent.run_stream(task=task):
            text = getattr(item, "content", None)
            if isinstance(text, str) and text:
                parts.append(text)
        return "".join(parts).strip()

    async def close(self) -> None:
        await self.model_client.close()


class PreferenceMemoryAgent(StatelessLLMAgent):
    def __init__(self, model: str = "gpt-4o-mini", name: str = "preference_memory_agent"):
        super().__init__(
            name=name,
            model=model,
            temperature=PROFILE_MEMORY_TEMPERATURE,
            system_message=(
                "You analyze user writing preferences from revision behavior. "
                "Return plain text or JSON exactly as requested."
            ),
        )

    def update_profile(self, existing_profile: List[str], summary: str) -> List[str]:
        cleaned = summary.strip()
        if not cleaned:
            return list(existing_profile)
        return list(dict.fromkeys(existing_profile + [cleaned]))

    def update_local_hints(self, existing_hints: List[str], summary: str) -> List[str]:
        cleaned = summary.strip()
        if not cleaned:
            return list(existing_hints)
        return list(dict.fromkeys(existing_hints + [cleaned]))

    def record_observation(
        self,
        existing_observations: List[PreferenceObservation],
        key: str,
        summary: str,
    ) -> tuple[List[PreferenceObservation], int]:
        cleaned_key = key.strip()
        cleaned_summary = summary.strip()
        if not cleaned_key or not cleaned_summary:
            return list(existing_observations), 0

        updated: List[PreferenceObservation] = []
        matched = False
        count_after = 1
        for item in existing_observations:
            if item.key == cleaned_key:
                count_after = item.count + 1
                updated.append(PreferenceObservation(key=cleaned_key, summary=cleaned_summary, count=count_after))
                matched = True
            else:
                updated.append(item)
        if not matched:
            updated.append(PreferenceObservation(key=cleaned_key, summary=cleaned_summary, count=1))
        return updated, count_after

    def should_promote(self, count: int) -> bool:
        return count >= PREFERENCE_PROMOTION_THRESHOLD

    def summarize_standard_reason(self, reason_id: str, reason_text: str) -> tuple[str, str]:
        mapping = {
            "LANG_REPETITION": (
                "language_avoid_repetition",
                "Avoid repetition and let each sentence make a fresh move.",
            ),
            "LANG_TOO_GENERAL": (
                "language_more_specific_wording",
                "Use more specific wording instead of broad or generic phrasing.",
            ),
            "LANG_TOO_SPECIFIC": (
                "language_keep_flexible_wording",
                "Keep wording flexible enough to avoid sounding overly narrow too early.",
            ),
            "LANG_TONE": (
                "language_tone_alignment",
                "Keep the tone aligned with the intended voice of the piece.",
            ),
            "LANG_CONCISE": (
                "language_concise_clarity",
                "Prefer clearer, lighter, and more concise sentences.",
            ),
            "CONTENT_EXAMPLE": (
                "content_need_example",
                "Support abstract points with concrete examples when needed.",
            ),
            "CONTENT_REFINED": (
                "content_refine_claim",
                "State the core claim more precisely and with a more refined point.",
            ),
            "CONTENT_OPPOSITE": (
                "content_include_counterpoint",
                "Use a brief opposing idea or contrast when it strengthens the point.",
            ),
            "CONTENT_MECHANISM": (
                "content_explain_mechanism",
                "Explain the mechanism or reasoning behind important claims.",
            ),
            "CONTENT_TRANSITION": (
                "content_stronger_transition",
                "Make each sentence connect more explicitly to the prior idea and task.",
            ),
        }
        return mapping.get(reason_id, (reason_id.lower() or "local_preference", self._fallback_summary(reason_text)))

    async def summarize_choice(
        self,
        task: str,
        current_sentence: str,
        selected_reason: str,
        selected_revision: str,
        existing_profile: List[str],
    ) -> str:
        preferences = "\n".join(f"- {item}" for item in existing_profile) or "- None yet."
        prompt = f"""
Write one concise reusable user preference based on the chosen revision.

Task:
{task}

Current interrupted sentence:
{current_sentence}

Selected reason:
{selected_reason}

Selected revision:
{selected_revision}

Existing user profile:
{preferences}

Constraints:
- Return exactly one sentence.
- Describe a durable writing preference, not a one-off edit.
- Keep it under 18 words.
- Do not mention JSON, tasks, or specific quoted text unless necessary.
- Return plain text only.
"""
        try:
            summary = " ".join((await self.complete(prompt)).split()).strip()
            return summary.strip("\"' ")
        except Exception:
            return self._fallback_summary(selected_reason)

    async def interpret_custom_memory(
        self,
        task: str,
        passage: str,
        current_sentence: str,
        user_input: str,
        existing_profile: List[str],
    ) -> ProfileUpdateSuggestion:
        preferences = "\n".join(f"- {item}" for item in existing_profile) or "- None yet."
        prompt = f"""
Interpret whether this user-provided revision instruction should be treated as a local one-time fix or a durable profile preference.

Task:
{task}

Current passage:
{passage}

Current interrupted sentence:
{current_sentence}

User instruction:
{user_input}

Existing user profile:
{preferences}

Return JSON only with this structure:
{{
  "preference_summary": "<concise preference summary>",
  "confidence": 0.0,
  "preference_key": "<short snake_case key>",
  "scope": "<local|global>",
  "rationale": "<brief reason for the scope choice>"
}}

Constraints:
- Use "global" only when the instruction clearly sounds reusable across passages.
- Use "local" for one-time content fixes tied to this passage.
- Keep preference_summary under 18 words.
- Keep preference_key short and reusable.
"""
        try:
            payload = extract_json_object(await self.complete(prompt))
            return ProfileUpdateSuggestion(
                preference_summary=str(payload.get("preference_summary", "")).strip(),
                confidence=float(payload.get("confidence", 0.0) or 0.0),
                preference_key=str(payload.get("preference_key", "")).strip() or self._to_preference_key(user_input),
                scope=str(payload.get("scope", "local")).strip().lower() or "local",
                rationale=str(payload.get("rationale", "")).strip(),
            )
        except Exception:
            summary = self._fallback_summary(user_input)
            return ProfileUpdateSuggestion(
                preference_summary=summary,
                confidence=0.45,
                preference_key=self._to_preference_key(summary),
                scope="global" if self._looks_global(user_input) else "local",
                rationale="Fallback heuristic based on whether the custom instruction sounds reusable.",
            )

    def _fallback_summary(self, selected_reason: str) -> str:
        lowered = selected_reason.lower()
        if any(word in lowered for word in ["generic", "general", "specific wording"]):
            return "Use more specific wording instead of generic phrasing."
        if any(word in lowered for word in ["specific", "narrow", "overcommit"]):
            return "Keep wording flexible before narrowing the point."
        if any(word in lowered for word in ["example", "illustrat", "evidence", "support"]):
            return "Support claims with examples or concrete illustration."
        if any(word in lowered for word in ["repeat", "redund", "duplicate"]):
            return "Avoid repetition and redundant phrasing."
        if any(word in lowered for word in ["tone", "voice", "formal", "stiff"]):
            return "Keep the tone aligned with the intended voice."
        if any(word in lowered for word in ["long", "dense", "unclear", "concise"]):
            return "Prefer clearer and more concise sentences."
        if any(word in lowered for word in ["opposite", "counter", "contrast"]):
            return "Use a contrast or counterpoint when it sharpens the argument."
        if any(word in lowered for word in ["mechanism", "intuition", "why", "reasoning"]):
            return "Explain why the claim holds, not just what it says."
        if any(word in lowered for word in ["transition", "align", "task"]):
            return "Make transitions tighter and more task-aligned."
        if any(word in lowered for word in ["refined", "precise", "claim"]):
            return "State the core claim more precisely."
        return selected_reason.strip()

    def _looks_global(self, user_input: str) -> bool:
        lowered = user_input.lower()
        global_markers = ["prefer", "always", "usually", "tone", "voice", "style", "concise", "specific", "example"]
        return any(marker in lowered for marker in global_markers)

    def _to_preference_key(self, text: str) -> str:
        cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in text).strip("_")
        while "__" in cleaned:
            cleaned = cleaned.replace("__", "_")
        return cleaned[:48] or "custom_preference"


class InterruptionInterpreterAgent(StatelessLLMAgent):
    def __init__(self, model: str = "gpt-4o-mini", name: str = "interruption_interpreter_agent"):
        super().__init__(
            name=name,
            model=model,
            system_message=(
                "You interpret why a user interrupted generated writing. "
                "Return only valid JSON in the requested structure."
            ),
        )

    async def interpret(self, state: SessionState) -> InterpreterResult:
        context = state.interruption_context
        preferences = "\n".join(f"- {item}" for item in state.preference_profile) or "- None yet."
        local_preferences = "\n".join(f"- {item}" for item in state.local_preference_hints) or "- None yet."
        prompt = f"""
Interpret this writing interruption and return exactly the requested JSON structure with no extra keys.

User task description:
{state.task}

Existing user profile:
{preferences}

Current local passage preferences:
{local_preferences}

Stop point information:
{{
  "termination_point": "{context.termination_point}",
  "last_sentence": "{context.last_sentence}",
  "current_sentence": "{context.current_sentence}"
}}

Return exactly this structure:
{{
  "stop_point": {{
    "termination_point": "<exact point where user interrupted>",
    "last_sentence": "<last completed sentence>",
    "current_sentence": "<sentence active at interruption>"
  }},
  "likely_user_intent": "<general description of what the user probably wants>",
  "reason_candidates": [
    {{
      "id": "LANG_REPETITION",
      "reason": "<language reason>"
    }}
  ],
  "replacement_guidance": {{
    "goal": "<what the replacement-generation agent should generate>",
    "desired_properties": ["<p1>", "<p2>"],
    "avoid": ["<a1>", "<a2>"]
  }},
  "profile_update": {{
    "preference_summary": "<possible user preference inferred from this interruption>",
    "confidence": 0.0,
    "preference_key": "<short snake_case key>",
    "scope": "<local|global>",
    "rationale": "<brief reason>"
  }}
}}

Constraints:
- Use the interrupted sentence, the previous sentence, the task, the saved user profile, and current local preferences as evidence.
- Return exactly {TARGET_REASON_OPTIONS} reason candidates.
- Standardize the reasons into exactly these 10 choices in this order:
  1. LANG_REPETITION
  2. LANG_TOO_GENERAL
  3. LANG_TOO_SPECIFIC
  4. LANG_TONE
  5. LANG_CONCISE
  6. CONTENT_EXAMPLE
  7. CONTENT_REFINED
  8. CONTENT_OPPOSITE
  9. CONTENT_MECHANISM
  10. CONTENT_TRANSITION
- Keep the first five language-level and the last five content-level.
- Make each reason specific to this stop point instead of generic writing advice.
- Do not include any keys beyond the required structure.
- Return JSON only.
"""
        try:
            return self._parse_result(extract_json_object(await self.complete(prompt)), state)
        except Exception:
            return self._fallback_interpretation(state)

    def _parse_result(self, payload: dict, state: SessionState) -> InterpreterResult:
        stop_point = payload.get("stop_point", {})
        reasons = payload.get("reason_candidates", [])[:MAX_REASON_OPTIONS]
        parsed_reasons = [
            InterpreterReasonCandidate(
                id=str(item.get("id", "")).strip(),
                reason=str(item.get("reason", "")).strip(),
            )
            for item in reasons
            if str(item.get("id", "")).strip() and str(item.get("reason", "")).strip()
        ]
        parsed_reasons = self._ensure_target_reason_candidates(parsed_reasons, state)
        guidance = payload.get("replacement_guidance", {})
        profile_update = payload.get("profile_update", {})
        return InterpreterResult(
            stop_point=stateful_stop_point(
                termination_point=str(stop_point.get("termination_point", "")).strip(),
                last_sentence=str(stop_point.get("last_sentence", "")).strip(),
                current_sentence=str(stop_point.get("current_sentence", "")).strip(),
            ),
            likely_user_intent=str(payload.get("likely_user_intent", "")).strip(),
            reason_candidates=parsed_reasons,
            replacement_guidance=ReplacementGuidance(
                goal=str(guidance.get("goal", "")).strip(),
                desired_properties=[str(item).strip() for item in guidance.get("desired_properties", []) if str(item).strip()],
                avoid=[str(item).strip() for item in guidance.get("avoid", []) if str(item).strip()],
            ),
            profile_update=ProfileUpdateSuggestion(
                preference_summary=str(profile_update.get("preference_summary", "")).strip(),
                confidence=float(profile_update.get("confidence", 0.0) or 0.0),
                preference_key=str(profile_update.get("preference_key", "")).strip(),
                scope=str(profile_update.get("scope", "local")).strip().lower() or "local",
                rationale=str(profile_update.get("rationale", "")).strip(),
            ),
        )

    def _ensure_target_reason_candidates(
        self,
        parsed_reasons: List[InterpreterReasonCandidate],
        state: SessionState,
    ) -> List[InterpreterReasonCandidate]:
        templates = self._reason_templates(state)
        reasons: List[InterpreterReasonCandidate] = []

        for template in templates:
            matched_reason = next(
                (
                    candidate.reason.strip()
                    for candidate in parsed_reasons
                    if candidate.id == template["id"] and candidate.reason.strip()
                ),
                "",
            )
            reasons.append(InterpreterReasonCandidate(id=template["id"], reason=matched_reason or template["text"]))
            if len(reasons) >= TARGET_REASON_OPTIONS:
                break

        return reasons[:TARGET_REASON_OPTIONS]

    def _fallback_interpretation(self, state: SessionState) -> InterpreterResult:
        reasons = [
            InterpreterReasonCandidate(id=template["id"], reason=template["text"])
            for template in self._reason_templates(state)
        ]

        return InterpreterResult(
            stop_point=state.interruption_context,
            likely_user_intent=state.task.strip() or "The user wants writing that better matches the stated task.",
            reason_candidates=reasons,
            replacement_guidance=ReplacementGuidance(
                goal="Rewrite the interrupted sentence so it better matches the user's likely intent.",
                desired_properties=[
                    "sentence-level replacement",
                    "closer alignment with the task",
                    "more natural fit for the user profile",
                ],
                avoid=[
                    "generic filler",
                    "drifting off task",
                ],
            ),
            profile_update=ProfileUpdateSuggestion(
                preference_summary="Prefer sentence rewrites that stay tightly aligned with the task and feel more intentional.",
                confidence=0.45,
                preference_key="task_aligned_sentence_rewrites",
                scope="local",
                rationale="Fallback interpretation keeps the preference local until repeated.",
            ),
        )

    def _reason_templates(self, state: SessionState) -> List[dict]:
        current_sentence = state.interruption_context.current_sentence.strip() or "the interrupted sentence"
        last_sentence = state.interruption_context.last_sentence.strip() or "the previous sentence"
        task = state.task.strip() or "the user's task"
        profile = ", ".join(state.preference_profile[-3:]) if state.preference_profile else "the saved user profile"

        return [
            {
                "id": "LANG_REPETITION",
                "text": (
                    f"Language: '{current_sentence}' may repeat what '{last_sentence}' already established, "
                    f"so the next sentence should make a fresher move."
                ),
            },
            {
                "id": "LANG_TOO_GENERAL",
                "text": (
                    f"Language: the wording in '{current_sentence}' may be too general for {task}, so it may need "
                    f"sharper diction or more specific phrasing."
                ),
            },
            {
                "id": "LANG_TOO_SPECIFIC",
                "text": (
                    f"Language: the sentence may sound too specific or overcommitted too early, which could make the "
                    f"draft less flexible as it develops for {task}."
                ),
            },
            {
                "id": "LANG_TONE",
                "text": (
                    f"Language: the tone or voice in '{current_sentence}' may not match the user's preferred style "
                    f"suggested by {profile}."
                ),
            },
            {
                "id": "LANG_CONCISE",
                "text": (
                    f"Language: the sentence may be too long, dense, or clunky at this stop point, so it may need "
                    f"cleaner and more concise wording."
                ),
            },
            {
                "id": "CONTENT_EXAMPLE",
                "text": (
                    f"Content: the idea at this stop point may need an example or concrete illustration to make the "
                    f"point land for {task}."
                ),
            },
            {
                "id": "CONTENT_REFINED",
                "text": (
                    f"Content: the claim in '{current_sentence}' may need a more refined, tighter, or more precise "
                    f"statement of the actual point."
                ),
            },
            {
                "id": "CONTENT_OPPOSITE",
                "text": (
                    f"Content: the draft may benefit from briefly showing an opposite idea, counterpressure, or contrast "
                    f"to better defend the point being made."
                ),
            },
            {
                "id": "CONTENT_MECHANISM",
                "text": (
                    f"Content: the sentence may point toward a claim without making the mechanism, intuition, or reasoning "
                    f"clear enough for the reader."
                ),
            },
            {
                "id": "CONTENT_TRANSITION",
                "text": (
                    f"Content: the sentence may transition weakly from '{last_sentence}' or may not align tightly enough "
                    f"with the immediate purpose of {task}."
                ),
            },
        ]


def stateful_stop_point(termination_point: str, last_sentence: str, current_sentence: str):
    from .models import InterruptionContext

    return InterruptionContext(
        termination_point=termination_point,
        last_sentence=last_sentence,
        current_sentence=current_sentence,
        replacement_start=0,
    )


class BehaviorInterpreterAgent(InterruptionInterpreterAgent):
    async def interpret_behavior(
        self,
        state: SessionState,
        behavior_text: str,
        behavior_mode: str,
    ) -> InterpreterResult:
        context = state.interruption_context
        preferences = "\n".join(f"- {item}" for item in state.preference_profile) or "- None yet."
        local_preferences = "\n".join(f"- {item}" for item in state.local_preference_hints) or "- None yet."
        prompt = f"""
Interpret this user behavior and return exactly the requested JSON structure with no extra keys.

Behavior mode:
{behavior_mode}

User task description:
{state.task}

Existing user profile:
{preferences}

Current local passage preferences:
{local_preferences}

Stop point information:
{{
  "termination_point": "{context.termination_point}",
  "last_sentence": "{context.last_sentence}",
  "current_sentence": "{context.current_sentence}"
}}

User behavior text:
{behavior_text}

Return exactly this structure:
{{
  "stop_point": {{
    "termination_point": "<exact point where user interrupted>",
    "last_sentence": "<last completed sentence>",
    "current_sentence": "<sentence active at interruption>"
  }},
  "likely_user_intent": "<general description of what the user probably wants>",
  "reason_candidates": [
    {{
      "id": "R1",
      "reason": "<detailed possible reason>"
    }}
  ],
  "replacement_guidance": {{
    "goal": "<what the replacement-generation agent should generate>",
    "desired_properties": ["<p1>", "<p2>"],
    "avoid": ["<a1>", "<a2>"]
  }},
  "profile_update": {{
    "preference_summary": "<possible user preference inferred from this interruption>",
    "confidence": 0.0,
    "preference_key": "<short snake_case key>",
    "scope": "<local|global>",
    "rationale": "<brief reason>"
  }}
}}

Return JSON only.
"""
        try:
            return self._parse_result(extract_json_object(await self.complete(prompt)), state)
        except Exception:
            return InterpreterResult(
                stop_point=state.interruption_context,
                likely_user_intent=state.task,
                reason_candidates=[
                    InterpreterReasonCandidate(id="R1", reason="The user wants a more specific local revision than the offered options."),
                    InterpreterReasonCandidate(id="R2", reason="The user is showing a direct writing preference through manual feedback."),
                ],
                replacement_guidance=ReplacementGuidance(
                    goal="Produce a sentence-level revision that follows the user's direct behavior.",
                    desired_properties=["follow the user's explicit revision preference", "stay aligned with the task"],
                    avoid=["ignoring the user's explicit intent"],
                ),
                profile_update=ProfileUpdateSuggestion(
                    preference_summary=f"User often prefers: {behavior_text.strip()}",
                    confidence=0.6,
                    preference_key="custom_behavior_preference",
                    scope="global" if "prefer" in behavior_text.lower() else "local",
                    rationale="Fallback behavior uses a simple reusable-language heuristic.",
                ),
            )


class ReplacementAgent(StatelessLLMAgent):
    def __init__(self, model: str = "gpt-4o-mini", name: str = "replacement_agent"):
        super().__init__(
            name=name,
            model=model,
            temperature=REPLACEMENT_TEMPERATURE,
            system_message=(
                "You generate replacement options for an interrupted sentence. "
                "Return only valid JSON."
            ),
        )

    async def build_replacements(
        self,
        state: SessionState,
        interpreter_result: InterpreterResult,
    ) -> List[ReplacementOption]:
        local_preferences = "\n".join(f"- {item}" for item in state.local_preference_hints) or "- None yet."
        prompt = f"""
Generate one replacement option for each reason candidate.

User task:
{state.task}

Sentence to revise:
{state.interruption_context.current_sentence}

Current local passage preferences:
{local_preferences}

Interpreter result:
{json.dumps(interpreter_result.to_dict(), ensure_ascii=False, indent=2)}

Return JSON with this structure:
{{
  "options": [
    {{
      "reason_id": "LANG_REPETITION",
      "reason": "<copy of the reason>",
      "explanation": "<why this option fits>",
      "replacement_text": "<replacement sentence>"
    }}
  ]
}}

Constraints:
- Return exactly one option for each reason candidate provided in the interpreter result.
- Make the options noticeably different from each other.
- Use the reason diagnoses as distinct revision directions instead of repeating the same diagnosis.
- Rewrite only the interrupted sentence or immediate local span.
- replacement_text must be paste-ready prose that can directly replace the interrupted text.
- replacement_text must stay inside the subject matter of the user's draft.
- Do not use replacement_text to explain the revision, interpret the user's intent, or describe a writing move.
- In replacement_text, do not mention "the essay", "the draft", "the passage", "the paragraph", "the sentence", "the revision", "the writer", "the user", or "the reader".
- Do not copy the full task description, bullet lists, or prompt text into the replacement.
- Each replacement_text must be short: at most two sentences and preferably under {MAX_REPLACEMENT_WORDS} words.
- Respect the current local passage preferences when they help.

Return JSON only.
"""
        try:
            payload = extract_json_object(await self.complete(prompt))
            options: List[ReplacementOption] = []
            reason_map = {item.id: item.reason for item in interpreter_result.reason_candidates}
            for item in payload.get("options", []):
                reason_id = str(item.get("reason_id", "")).strip()
                replacement_text = str(item.get("replacement_text", "")).strip()
                if reason_id and replacement_text and reason_id in reason_map:
                    replacement_text = self._sanitize_replacement_text(
                        replacement_text=replacement_text,
                        state=state,
                        reason_id=reason_id,
                    )
                    options.append(
                        ReplacementOption(
                            option_id=str(uuid.uuid4()),
                            reason_id=reason_id,
                            reason=reason_map[reason_id],
                            explanation=str(item.get("explanation", "")).strip() or reason_map[reason_id],
                            replacement_text=replacement_text,
                            category="language" if reason_id.startswith("LANG_") else "content",
                        )
                    )
            if options:
                return self._ensure_target_replacements(options, state, interpreter_result)
        except Exception:
            pass
        return self._fallback_replacements(state, interpreter_result)

    async def build_custom_revision(
        self,
        task: str,
        passage: str,
        custom_instruction: str,
    ) -> str:
        prompt = f"""
Rewrite the interrupted sentence based on the user's custom revision request.

Task:
{task}

Current passage:
{passage}

User revision request:
{custom_instruction}

Return only paste-ready replacement prose for the interrupted sentence or short local span.
Do not explain the revision or mention the essay, draft, passage, paragraph, sentence, writer, user, or reader.
"""
        try:
            text = await self.complete(prompt)
            if text:
                return text.strip()
        except Exception:
            pass
        return custom_instruction.strip()

    def _fallback_replacements(self, state: SessionState, interpreter_result: InterpreterResult) -> List[ReplacementOption]:
        options: List[ReplacementOption] = []
        for reason in interpreter_result.reason_candidates:
            options.append(
                ReplacementOption(
                    option_id=str(uuid.uuid4()),
                    reason_id=reason.id,
                    reason=reason.reason,
                    explanation=reason.reason,
                    replacement_text=self._fallback_rewrite_for_reason(state, reason.id),
                    category="language" if reason.id.startswith("LANG_") else "content",
                )
            )
        return self._ensure_target_replacements(options, state, interpreter_result)

    def _ensure_target_replacements(
        self,
        options: List[ReplacementOption],
        state: SessionState,
        interpreter_result: InterpreterResult,
    ) -> List[ReplacementOption]:
        completed = list(options)
        covered_reason_ids = {item.reason_id for item in completed}

        for reason in interpreter_result.reason_candidates:
            if reason.id in covered_reason_ids:
                continue
            completed.append(
                ReplacementOption(
                    option_id=str(uuid.uuid4()),
                    reason_id=reason.id,
                    reason=reason.reason,
                    explanation=reason.reason,
                    replacement_text=self._fallback_rewrite_for_reason(state, reason.id),
                    category="language" if reason.id.startswith("LANG_") else "content",
                )
            )
            covered_reason_ids.add(reason.id)
            if len(completed) >= TARGET_REASON_OPTIONS:
                break

        return completed[:MAX_REASON_OPTIONS]

    def _fallback_rewrite_for_reason(self, state: SessionState, reason_id: str) -> str:
        sentence = (state.interruption_context.current_sentence or "").strip()
        task = state.task.strip() or "the task"
        previous_sentence = state.interruption_context.last_sentence.strip()
        compact = " ".join(sentence.split()).rstrip(".!?")

        if not compact:
            return "The issue becomes clearer when its practical stakes are named directly."

        if reason_id == "LANG_REPETITION":
            return f"{compact}, while the next consequence changes who carries responsibility."
        if reason_id == "LANG_TOO_GENERAL":
            return f"{compact}, especially where institutional rules shape what choices are available in practice."
        if reason_id == "LANG_TOO_SPECIFIC":
            return f"{compact}, though the same pressure appears across several related cases."
        if reason_id == "LANG_TONE":
            return f"{compact}, with real consequences for people who must act under uncertainty."
        if reason_id == "LANG_CONCISE":
            first_clause = compact.split(",")[0].strip()
            return f"{first_clause}."
        if reason_id == "CONTENT_EXAMPLE":
            return f"{compact}, as shown when formal safeguards exist but access to advocacy remains uneven."
        if reason_id == "CONTENT_REFINED":
            return f"{compact}, because the central problem is not capacity alone but the authority created around it."
        if reason_id == "CONTENT_OPPOSITE":
            return f"{compact}, although that safeguard can also narrow judgment in borderline cases."
        if reason_id == "CONTENT_MECHANISM":
            return f"{compact}, because rules, incentives, and expertise determine how the choice reaches the patient."
        if reason_id == "CONTENT_TRANSITION":
            prefix = "Building on that point, " if previous_sentence else "From there, "
            return f"{prefix}{compact[:1].lower() + compact[1:] if len(compact) > 1 else compact.lower()}."
        return f"{compact}, where the practical consequence matters more than the general topic."

    def _sanitize_replacement_text(self, replacement_text: str, state: SessionState, reason_id: str) -> str:
        normalized = " ".join(replacement_text.split()).strip()
        if not normalized:
            return self._fallback_rewrite_for_reason(state, reason_id)

        lowered = normalized.lower()
        forbidden_markers = [
            "please produce:",
            "instruction:",
            "saved user profile:",
            "current live text:",
            "current accepted text:",
            "user task:",
            "interpreter result:",
            "the essay",
            "the draft",
            "the passage",
            "the paragraph",
            "the sentence",
            "the revision",
            "the writer",
            "the user",
            "the reader",
            "this option",
            "this revision",
            "writing move",
        ]
        if any(marker in lowered for marker in forbidden_markers):
            return self._fallback_rewrite_for_reason(state, reason_id)

        if len(normalized.split()) > MAX_REPLACEMENT_WORDS:
            return self._fallback_rewrite_for_reason(state, reason_id)

        return normalized


class StreamingWriterAgent(StatelessLLMAgent):
    def __init__(self, model: str = "gpt-4o-mini", name: str = "streaming_writer_agent"):
        super().__init__(
            name=name,
            model=model,
            temperature=STREAMING_TEMPERATURE,
            system_message=(
                "You are the main writing generator in an interruption-aware writing system. "
                "Generate streaming prose that follows the user's task, profile, and current local passage preferences. "
                "Do not explain your process."
            ),
        )

    async def stream_generate(
        self,
        state: SessionState,
        on_token: Callable[[str], None],
        should_stop: Callable[[], bool],
    ) -> str:
        prompt = self._build_prompt(state)
        accumulated = ""
        async for item in self.agent.run_stream(task=prompt):
            if should_stop():
                break
            text = getattr(item, "content", None)
            if isinstance(text, str) and text:
                accumulated += text
                on_token(text)
                if STREAM_TOKEN_DELAY_SECONDS > 0:
                    await asyncio.sleep(STREAM_TOKEN_DELAY_SECONDS)
        return accumulated

    def _build_prompt(self, state: SessionState) -> str:
        preferences = "\n".join(f"- {item}" for item in state.preference_profile) or "- None yet."
        local_preferences = "\n".join(f"- {item}" for item in state.local_preference_hints) or "- None yet."
        revision_history = state.format_revision_history()
        return f"""
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

Current live text:
{state.live_text}

Instruction:
Continue the writing with one focused paragraph of 3 to 5 sentences. Start exactly where the current text leaves off, follow the saved profile and local passage preferences, and do not explain your process.
"""

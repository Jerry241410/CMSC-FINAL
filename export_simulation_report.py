import argparse
import html
import json
import statistics
from pathlib import Path
from typing import Any, Dict, List


def main() -> None:
    parser = argparse.ArgumentParser(description="Export compact audit files from a simulation JSON.")
    parser.add_argument("input", type=Path, help="Path to the raw simulation JSON.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Directory for exported audit files.")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    output_dir = args.output_dir or args.input.with_suffix("")
    output_dir.mkdir(parents=True, exist_ok=True)

    step_rows = build_step_rows(payload)
    (output_dir / "interruption_audit.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in step_rows),
        encoding="utf-8",
    )
    (output_dir / "simulation_summary.json").write_text(
        json.dumps(payload.get("summary", {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "simulation_report.md").write_text(build_markdown_report(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "files": ["interruption_audit.jsonl", "simulation_summary.json", "simulation_report.md"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def build_step_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for result in payload.get("results", []):
        for step in result.get("steps", []):
            interpretation = step.get("system_interpretation", {})
            reasons = interpretation.get("reason_candidates", [])
            top_reason = reasons[0].get("reason", "") if reasons else ""
            rows.append(
                {
                    "user_id": result.get("user_id", ""),
                    "profile_group": result.get("profile_group", "common"),
                    "step_index": step.get("step_index", 0),
                    "interrupted": step.get("interrupted", False),
                    "exact_stopping_time_seconds": step.get("cumulative_elapsed_seconds", 0.0)
                    if step.get("interrupted", False)
                    else None,
                    "cumulative_elapsed_seconds": step.get("cumulative_elapsed_seconds", 0.0),
                    "interruption_reason": step.get("interruption_reason", ""),
                    "system_interpretation": top_reason,
                    "repair_or_simulator_decision": top_reason or step.get("simulator_decision_rationale", ""),
                    "selected_action": step.get("selected_action", ""),
                    "selected_revision": step.get("selected_revision", ""),
                    "sample_text_with_replacement_highlight": build_highlighted_sample(step),
                    "recovery_recall": step.get("recovery_after_step", {}).get("recall_ratio", 0.0),
                }
            )
    return rows


def build_markdown_report(payload: Dict[str, Any]) -> str:
    metadata = payload.get("metadata", {})
    results = payload.get("results", [])
    summary = payload.get("summary", {})
    lines = [
        "# Writing Helper Simulation Report",
        "",
        "This report keeps the original recovery audit and adds the common, rare personal, and mixed-profile comparison.",
        "",
        "## Run Setup",
        "",
        f"- Model: `{metadata.get('model', '')}`",
        f"- Steps per profile: `{metadata.get('max_steps', '')}`",
        f"- Total profiles: `{metadata.get('scenario_count', len(results))}`",
        f"- Count per group: `{metadata.get('count_per_group', 'n/a')}`",
        "",
        "## Group Recovery Comparison",
        "",
        "| Group | Profiles | Avg recall | Interruptions | Manual actions | Avg elapsed seconds |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    group_summaries = summary.get("group_summaries", {})
    for group in ["common", "rare", "mix"]:
        group_results = [item for item in results if item.get("profile_group", "common") == group]
        group_summary = group_summaries.get(group, {})
        lines.append(
            "| {group} | `{profiles}` | `{recall:.3f}` | `{interruptions}` | `{manual}` | `{elapsed:.2f}` |".format(
                group=group,
                profiles=len(group_results),
                recall=float(group_summary.get("average_recall_ratio", 0.0) or 0.0),
                interruptions=int(group_summary.get("interruption_count", 0) or 0),
                manual=int(group_summary.get("manual_action_count", 0) or 0),
                elapsed=float(group_summary.get("average_elapsed_seconds", 0.0) or 0.0),
            )
        )

    lines.extend(
        [
            "",
            "## Overall Recovery",
            "",
            f"- Average recall: `{float(summary.get('average_recall_ratio', 0.0) or 0.0):.3f}`",
            f"- Total interruptions: `{int(summary.get('interruption_count', 0) or 0)}`",
            f"- Manual/custom actions: `{int(summary.get('manual_action_count', 0) or 0)}`",
            "",
            "## Profile Size Check",
            "",
            "| Group | Mean profile items | Median | Min | Max |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for group in ["common", "rare", "mix"]:
        sizes = [len(item.get("target_profile", [])) for item in results if item.get("profile_group", "common") == group]
        if sizes:
            lines.append(
                f"| {group} | `{statistics.mean(sizes):.2f}` | `{statistics.median(sizes):.2f}` | `{min(sizes)}` | `{max(sizes)}` |"
            )

    lines.extend(["", "## Highlighted Samples", ""])
    for group in ["common", "rare", "mix"]:
        sample = first_interrupted_step(results, group)
        if not sample:
            continue
        result, step = sample
        interpretation = top_interpretation_reason(step) or step.get("simulator_decision_rationale", "")
        lines.extend(
            [
                f"### {group.title()} Profile Sample",
                "",
                f"- User: `{result.get('user_id', '')}`",
                f"- Step: `{step.get('step_index', 0)}`",
                f"- Exact stopping time: `{float(step.get('cumulative_elapsed_seconds', 0.0) or 0.0):.2f}` seconds",
                f"- Repair or simulator decision: {interpretation}",
                "",
                build_highlighted_sample(step),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def first_interrupted_step(results: List[Dict[str, Any]], group: str) -> Any:
    for result in results:
        if result.get("profile_group", "common") != group:
            continue
        for step in result.get("steps", []):
            if step.get("interrupted", False):
                return result, step
    return None


def top_interpretation_reason(step: Dict[str, Any]) -> str:
    interpretation = step.get("system_interpretation", {})
    reasons = interpretation.get("reason_candidates", []) if isinstance(interpretation, dict) else []
    return str(reasons[0].get("reason", "")).strip() if reasons else ""


def build_highlighted_sample(step: Dict[str, Any]) -> str:
    generation = str(step.get("generation_text", "")).strip()
    revision = str(step.get("selected_revision", "")).strip()
    if not revision:
        return html.escape(generation)
    return f"{html.escape(generation)} <mark>{html.escape(revision)}</mark>"


if __name__ == "__main__":
    main()

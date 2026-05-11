import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def main() -> None:
    parser = argparse.ArgumentParser(description="Export interruption logs and a blank report scaffold from a simulation JSON.")
    parser.add_argument("input", type=Path, help="Path to the raw simulation JSON.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Directory for exported audit files.")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    output_dir = args.output_dir or args.input.with_suffix("")
    output_dir.mkdir(parents=True, exist_ok=True)

    step_rows = build_step_rows(payload)
    (output_dir / "interruption_audit.json").write_text(json.dumps(step_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "interruption_audit.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in step_rows),
        encoding="utf-8",
    )
    (output_dir / "simulation_summary.json").write_text(
        json.dumps(payload.get("summary", {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(build_report(args.input.name, payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "files": [
                    "interruption_audit.json",
                    "interruption_audit.jsonl",
                    "simulation_summary.json",
                    "report.md",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def build_step_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for result in payload.get("results", []):
        for step in result.get("steps", []):
            rows.append(
                {
                    "user_id": result.get("user_id", ""),
                    "task": result.get("task", ""),
                    "target_profile": result.get("target_profile", []),
                    "step_index": step.get("step_index", 0),
                    "interrupted": step.get("interrupted", False),
                    "generation_text": step.get("generation_text", ""),
                    "interruption_reason": step.get("interruption_reason", ""),
                    "interruption_point": step.get("interruption_point", {}),
                    "replacement_options": step.get("replacement_options", []),
                    "selected_action": step.get("selected_action", ""),
                    "selected_reason_id": step.get("selected_reason_id", ""),
                    "selected_reason": step.get("selected_reason", ""),
                    "selected_revision": step.get("selected_revision", ""),
                    "manual_input": step.get("manual_input", ""),
                    "profile_summary_added": step.get("profile_summary_added", ""),
                    "memory_scope": step.get("memory_scope", ""),
                    "helper_profile_after_step": step.get("helper_profile_after_step", []),
                    "helper_local_memory_after_step": step.get("helper_local_memory_after_step", []),
                    "helper_observations_after_step": step.get("helper_observations_after_step", []),
                    "final_helper_profile": result.get("helper_profile", []),
                    "similarity": result.get("similarity", {}),
                }
            )
    return rows


def build_report(input_name: str, payload: Dict[str, Any]) -> str:
    metadata = payload.get("metadata", {})
    summary = payload.get("summary", {})
    results = payload.get("results", [])
    scenario_count = metadata.get("scenario_count", len(results))
    elapsed = float(metadata.get("finished_at", 0) or 0) - float(metadata.get("started_at", 0) or 0)
    interrupted_steps = [step for result in results for step in result.get("steps", []) if step.get("interrupted")]
    manual_steps = [step for step in interrupted_steps if step.get("selected_action") in {"manual_describe", "manual_write"}]
    final_recalls = [float(result.get("similarity", {}).get("recall_ratio", 0.0) or 0.0) for result in results]
    final_precisions = [float(result.get("similarity", {}).get("precision_ratio", 0.0) or 0.0) for result in results]
    timeline = build_time_recovery_timeline(results)

    lines = [
        "# Simulation Report",
        "",
        f"Source file: `{input_name}`",
        f"Scenario count: {scenario_count}",
        f"Model: {metadata.get('model', '')}",
        f"Max steps per user: {metadata.get('max_steps', '')}",
        f"Wall-clock runtime: {elapsed:.1f} seconds",
    ]
    if metadata.get("note"):
        lines.append(f"Run note: {metadata.get('note')}")
    lines.extend([
        "",
        "## Summary",
        "",
        f"- Average final profile recall: {_average(final_recalls):.3f}",
        f"- Average final profile precision: {_average(final_precisions):.3f}",
        f"- Average overlap word count: {float(summary.get('average_overlap_word_count', 0.0)):.2f}",
        f"- Interruptions: {len(interrupted_steps)}",
        f"- Manual/custom actions: {len(manual_steps)}",
        f"- Average elapsed seconds per scenario: {float(summary.get('average_elapsed_seconds', 0.0)):.2f}",
        "",
        "## Recovery Over Time",
        "",
        "| Time cap | Samples observed | Average recall | Median recall | Users at >= 0.25 recall | Users at >= 0.50 recall |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in timeline:
        lines.append(
            f"| {row['label']} | {row['sample_count']} | {row['average_recall']:.3f} | "
            f"{row['median_recall']:.3f} | {row['at_25_recall']} | {row['at_50_recall']} |"
        )

    lines.extend(
        [
            "",
            "## Step Recovery",
            "",
            "| Step | Samples | Average recall |",
            "| ---: | ---: | ---: |",
        ]
    )
    for row in summary.get("recovery_timeline", []):
        lines.append(
            f"| {row.get('step_index', 0)} | {row.get('sample_count', 0)} | "
            f"{float(row.get('average_recall_ratio', 0.0)):.3f} |"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Recall is lexical overlap between the generated helper profile and the hidden target profile.",
            "- The 10-minute scale uses each step's cumulative elapsed time when present; older simulation files without timing are treated as final-only observations.",
            "- Exact item matches are expected to be low because the helper stores paraphrased preferences.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_time_recovery_timeline(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    caps = [
        (30, "30 sec"),
        (60, "1 min"),
        (120, "2 min"),
        (300, "5 min"),
        (600, "10 min"),
    ]
    rows = []
    for cap, label in caps:
        values = []
        for result in results:
            best_value = None
            for step in result.get("steps", []):
                cumulative = float(step.get("cumulative_elapsed_seconds", 0.0) or 0.0)
                if cumulative and cumulative <= cap:
                    best_value = float(step.get("recovery_after_step", {}).get("recall_ratio", 0.0) or 0.0)
            if best_value is None and not any(step.get("cumulative_elapsed_seconds") for step in result.get("steps", [])):
                best_value = float(result.get("similarity", {}).get("recall_ratio", 0.0) or 0.0)
            if best_value is not None:
                values.append(best_value)
        rows.append(
            {
                "label": label,
                "sample_count": len(values),
                "average_recall": _average(values),
                "median_recall": _median(values),
                "at_25_recall": sum(1 for value in values if value >= 0.25),
                "at_50_recall": sum(1 for value in values if value >= 0.50),
            }
        )
    return rows


def _average(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _median(values: List[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


if __name__ == "__main__":
    main()

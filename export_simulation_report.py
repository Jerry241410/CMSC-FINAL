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
    (output_dir / "report.md").write_text(build_blank_report(args.input.name, payload), encoding="utf-8")

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


def build_blank_report(input_name: str, payload: Dict[str, Any]) -> str:
    scenario_count = payload.get("metadata", {}).get("scenario_count", 0)
    return (
        f"# Simulation Report\n\n"
        f"Source file: `{input_name}`\n\n"
        f"Scenario count: {scenario_count}\n\n"
        f"## Summary\n\n"
        f"TBD\n\n"
        f"## Interruption Analysis\n\n"
        f"TBD\n\n"
        f"## Selection Analysis\n\n"
        f"TBD\n\n"
        f"## Profile Memory Evolution\n\n"
        f"TBD\n\n"
        f"## Similarity Findings\n\n"
        f"TBD\n"
    )


if __name__ == "__main__":
    main()

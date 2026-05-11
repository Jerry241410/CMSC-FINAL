import argparse
import json
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

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "files": ["interruption_audit.jsonl", "simulation_summary.json"],
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
                    "step_index": step.get("step_index", 0),
                    "interrupted": step.get("interrupted", False),
                    "cumulative_elapsed_seconds": step.get("cumulative_elapsed_seconds", 0.0),
                    "interruption_reason": step.get("interruption_reason", ""),
                    "system_interpretation": top_reason,
                    "selected_action": step.get("selected_action", ""),
                    "selected_revision": step.get("selected_revision", ""),
                    "recovery_recall": step.get("recovery_after_step", {}).get("recall_ratio", 0.0),
                }
            )
    return rows


if __name__ == "__main__":
    main()

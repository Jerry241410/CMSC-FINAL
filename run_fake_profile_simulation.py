import argparse
import asyncio
import json
import os
from pathlib import Path

from writing_helper.simulation import default_simulation_output_path, run_default_fake_profile_simulation


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a headless fake-profile simulation for the writing helper.")
    parser.add_argument("--count", type=int, default=100, help="Number of fake users to simulate.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for fake user generation.")
    parser.add_argument("--model", type=str, default="gpt-4o-mini", help="Model name for helper and judge agents.")
    parser.add_argument("--max-steps", type=int, default=6, help="Maximum interruption cycles per fake user.")
    parser.add_argument("--output", type=Path, default=None, help="Path to save the raw simulation JSON.")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set. Set it before running the simulation.")

    output_path = args.output or default_simulation_output_path()
    payload = asyncio.run(
        run_default_fake_profile_simulation(
            count=args.count,
            seed=args.seed,
            model=args.model,
            max_steps=args.max_steps,
            output_path=output_path,
        )
    )
    print(json.dumps({"output_path": str(output_path), "summary": payload["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

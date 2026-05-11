# Writing Helper

Local browser prototype for interruption-aware AI writing. The app streams a draft, lets the user stop when the current sentence feels wrong, proposes local rewrites, and stores recurring writing preferences in a local profile.

## Current App

- `python writing.py` starts the web UI at `http://127.0.0.1:8765`.
- The UI includes user/task input, live document, replacement options, custom revision input, profile memory, logs, and timing status.
- The old Tkinter UI still exists in `writing_helper/ui.py`, but the default app now uses `writing_helper/web.py` and `writing_helper/web_static/`.
- Streaming response time was improved by removing the artificial `0.2s` per-token delay.

## Core Flow

1. Enter a user name and writing task.
2. Start streaming.
3. Stop when the generated text goes off track.
4. The interpreter diagnoses why the sentence may be wrong.
5. The replacement agent proposes rewrite options.
6. Applying a rewrite updates the text and local preference memory.
7. Repeated or explicit durable preferences are saved into the user profile.

## Simulation Status

The code includes fake-profile recovery simulation in `writing_helper/simulation.py`.

Latest available run was offline because `OPENAI_API_KEY` was not set in this shell. It used `100` samples, complex hidden profiles averaging `11.44` items, and `8` interruption steps per sample.

Offline sanity results:

- Samples: `100`
- Interruptions: `800`
- Average recovered profile size: `8.00` items
- Average final recall: `0.700`
- Median final recall: `0.688`
- P10/P90 final recall: `0.608 / 0.796`
- Average final precision: `1.000`
- Average recall by step: `0.087`, `0.176`, `0.262`, `0.351`, `0.437`, `0.527`, `0.611`, `0.700`
- Average recall by time: `0.089` at 1 min, `0.122` at 2 min, `0.370` at 5 min, `0.694` at 10 min

Example hidden profile item and interruption:

- Hidden preference: `Open paragraphs with a debatable claim rather than a broad topic sentence.`
- Simulator interruption reason: generated text missed that hidden preference.
- System interpretation: the interrupted sentence was under-specified relative to that preference.
- Selected repair: revise the sentence to follow that stable preference.
- Recovery after first step in the example: `0.101`.

This offline run checks the recovery/reporting pipeline. It is not a real AI evaluation. Run the non-offline simulation with an API key for model-based results.

## Run

Install dependencies:

```bash
pip install -U "autogen-agentchat" "autogen-ext[openai]" openai
```

Set the API key:

```powershell
$env:OPENAI_API_KEY="your_key_here"
```

Start the app:

```bash
python writing.py
```

Choose a different port:

```bash
python -m writing_helper.web --port 8766
```

## Simulation

Real AI simulation:

```bash
python run_fake_profile_simulation.py --count 100 --max-steps 8
```

Offline sanity simulation:

```bash
python run_fake_profile_simulation.py --count 100 --max-steps 8 --offline
```

Compact audit export:

```bash
python export_simulation_report.py simulation_outputs/your_run.json
```

The exporter now writes only `interruption_audit.jsonl` and `simulation_summary.json`; the human-readable summary belongs in this README.

## Main Files

- `writing_helper/web.py`: local web server and API.
- `writing_helper/web_static/`: browser UI.
- `writing_helper/orchestrator.py`: workflow coordination.
- `writing_helper/agents.py`: writer, interpreter, replacement, and memory agents.
- `writing_helper/simulation.py`: fake-profile recovery simulation.
- `writing_helper/storage.py`: local profile persistence.

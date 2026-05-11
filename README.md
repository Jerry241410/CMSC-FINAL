# Writing Helper

This project is a local browser-based prototype for interruption-aware AI writing. It streams draft text, lets the user stop when a sentence goes off track, interprets why the stop likely happened, proposes local rewrites, and saves the user's emerging preferences into a per-user local profile.

## What We Have Now

### Core app flow

- `python writing.py` launches the local web app at `http://127.0.0.1:8765`.
- The user enters a `User Name` and a `Task / Purpose`.
- The main writer streams text into the live document view.
- The user can stop generation at any point.
- The app extracts the current interrupted sentence plus the previous sentence.
- An interpreter agent proposes likely reasons for the interruption.
- A replacement agent generates one rewrite option per reason.
- The user can apply a generated option or use `Other` to:
  - describe the kind of revision they want
  - write their own replacement text
- The selected revision is applied back into the live document.
- Standardized option selections apply immediately as local passage memory.
- Repeated similar selections are promoted into the saved profile after they recur three times.
- Custom user input is interpreted as either a one-time local fix or a reusable global preference.

### Current UI

The web UI currently includes:

- username input
- task/purpose input
- live document panel
- system log panel
- interpreter output panel
- replacement options list
- `Other` action mode selector
- custom input box for `Other`
- user preference profile panel
- status/busy/mode indicators

Current buttons:

- `Start Streaming`
- `Stop Streaming`
- `Accept Current Text`
- `Continue Generation`
- `Export Session JSON`
- `Apply Selected Option`

### Current code structure

- `writing_helper/main.py`: startup and API key check
- `writing_helper/ui.py`: Tkinter app and event handling
- `writing_helper/orchestrator.py`: workflow coordination and background loop
- `writing_helper/agents.py`: writer/interpreter/replacement/profile logic
- `writing_helper/models.py`: shared dataclasses and session state
- `writing_helper/storage.py`: local profile persistence
- `writing_helper/text_utils.py`: interruption-context and JSON extraction helpers
- `writing_helper/constants.py`: shared limits and regex constants

### LLM agent behavior

The app currently has four main agent roles:

- `StreamingWriterAgent`: continues the draft using task, accepted text, live text, saved profile, and recent revision history
- `InterruptionInterpreterAgent`: infers likely reasons the user stopped generation
- `BehaviorInterpreterAgent`: handles the `Other` path when the user provides custom revision behavior
- `ReplacementAgent`: generates local replacement options or a custom revision

There is also a `PreferenceMemoryAgent` that tracks local memory, counts repeated similar choices, and promotes durable preferences into the profile.

### Revision memory and export

The app stores revision events containing:

- stop-point context
- interpreter output
- selected reason
- selected revision
- custom input when used
- updated preference profile
- local preference memory applied at the time of revision

`Export Session JSON` currently shows a JSON snapshot in a popup window.

## Whats Missing

### Robustness

The JSON handling :

- model output is parsed by extracting the first outer JSON object
- there is fallback behavior if parsing fails
- there is no strict schema validation

### Editing precision

Interruption handling is still fairly heuristic:

- replacement is based on sentence-pattern extraction
- applied revisions replace text from a computed `replacement_start`
- there is no paragraph-aware or user-selection-based edit span

### Option quality control

- replacement generation is standardized into 10 recurring slots
- 5 options are language-level choices
- 5 options are content-level choices
- the wording and replacement text still adapt to the current interruption context

### Export and reporting polish

- `Export Session JSON` shows the JSON in a popup, but does not save directly to a file
- there is no dedicated history browser or analytics view

### Validation in real runs

The architecture is in place, but it still needs more runtime verification:

- real-world streaming behavior should be tested with actual OpenAI credentials
- interruption timing and UI responsiveness need live validation

## Current Workflow

1. Start the app.
2. Enter a username and writing task.
3. Begin streaming.
4. Stop when the current sentence feels wrong.
5. Review interpreter output and rewrite options.
6. Apply a generated option or use `Other`.
7. Continue generation with the updated text, local passage memory, and saved profile.

## Requirements

Install the packages currently used by the code:

```bash
pip install -U "autogen-agentchat" "autogen-ext[openai]" openai
```

Recommended Python version:


## API Key

Set `OPENAI_API_KEY` before launching the app.

### PowerShell

```powershell
$env:OPENAI_API_KEY="your_key_here"
```

### CMD

```cmd
set OPENAI_API_KEY=your_key_here
```

### macOS / Linux

```bash
export OPENAI_API_KEY="your_key_here"
```

## Run

```bash
python writing.py
```

Or choose a port explicitly:

```bash
python -m writing_helper.web --port 8766
```

## Headless Simulation

Run the fake-profile batch simulation:

```bash
python run_fake_profile_simulation.py --count 100 --max-steps 6
```

This writes a raw simulation JSON file under `simulation_outputs/`. It requires `OPENAI_API_KEY`.

For a no-API-key sanity check of the scenario and reporting pipeline:

```bash
python run_fake_profile_simulation.py --count 100 --max-steps 6 --offline
```

Export flattened interruption logs plus a blank report scaffold from that raw file:

```bash
python export_simulation_report.py simulation_outputs/your_run.json
```

The report includes step-level profile recovery plus recovery at 30 seconds, 1 minute, 2 minutes, 5 minutes, and 10 minutes when timing data is available.

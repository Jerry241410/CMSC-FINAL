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

## Simulation Report

The code includes fake-profile recovery simulation in `writing_helper/simulation.py`. The real AI path asks a profile-satisfaction simulator to interrupt only when the latest generation misses, contradicts, or ignores the hidden user profile.

The latest available run here was offline because `OPENAI_API_KEY` was not set. It used `100` samples, style-only hidden profiles, and `12` generated passage steps per sample. Interruption was decision-based: each generated passage was assessed against a hidden wording/style/structure preference, and the simulator interrupted only when the passage missed an unrecovered preference.

### Summary Statistics

| Metric | Mean | Median | Min | Max |
| --- | ---: | ---: | ---: | ---: |
| Target profile items | `10.47` | `10.00` | `9` | `12` |
| Target profile words | `102.32` | `102.50` | `79` | `125` |
| Unique words per profile | `78.22` | `78.00` | `63` | `92` |
| Duplicate word count | `24.10` | `23.00` | `9` | `41` |
| Duplicate word ratio | `0.233` | `0.228` | `0.108` | `0.333` |
| Recovered profile items | `7.75` | `8.00` | `5` | `11` |
| Final recall | `0.742` | `0.751` | `0.516` | `1.000` |

Most frequent words across generated profiles: `the` 458, `and` 247, `avoid` 230, `with` 228, `a` 222, `to` 217, `use` 208, `more` 186, `prefer` 178, `keep` 174, `or` 170, `when` 163.

Most common exact profile items:

| Exact profile item | Profiles containing it |
| --- | ---: |
| Keep wording flexible enough to avoid sounding overly narrow too early. | `51%` |
| Use a brief opposing idea or contrast when it strengthens the point. | `43%` |
| Use more specific wording instead of broad or generic phrasing. | `41%` |
| Prefer clearer, lighter, and more concise sentences. | `41%` |
| Avoid repetition and let each sentence make a fresh move. | `40%` |
| Keep the tone aligned with the intended voice of the piece. | `39%` |
| State the core claim more precisely and with a more refined point. | `35%` |
| Make each sentence connect more explicitly to the prior idea and task. | `34%` |
| Explain the mechanism or reasoning behind important claims. | `34%` |
| Use one governing idea per paragraph and subordinate examples to that idea. | `33%` |
| Support abstract points with concrete examples when needed. | `33%` |
| Avoid generic academic filler. | `29%` |

| Run metric | Value |
| --- | ---: |
| Samples | `100` |
| Total generated steps | `1200` |
| Interruptions | `775` |
| Non-interruptions | `425` |
| Mean interruptions per user | `7.75` |
| Final precision, mean / median | `1.000 / 1.000` |
| Selected option actions | `621` |
| Manual describe actions | `154` |

### Recovery Plots

Black-line plot by step:

<svg width="620" height="210" viewBox="0 0 620 210" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Profile recovery by step">
  <rect x="0" y="0" width="620" height="210" fill="white"/>
  <line x1="48" y1="170" x2="590" y2="170" stroke="#444" stroke-width="1"/>
  <line x1="48" y1="20" x2="48" y2="170" stroke="#444" stroke-width="1"/>
  <polyline fill="none" stroke="black" stroke-width="3" points="48,154 97,139 147,124 196,111 245,97 294,83 344,70 393,59 442,47 491,39 541,32 590,28"/>
  <g fill="black">
    <circle cx="48" cy="154" r="3"/><circle cx="97" cy="139" r="3"/><circle cx="147" cy="124" r="3"/><circle cx="196" cy="111" r="3"/>
    <circle cx="245" cy="97" r="3"/><circle cx="294" cy="83" r="3"/><circle cx="344" cy="70" r="3"/><circle cx="393" cy="59" r="3"/>
    <circle cx="442" cy="47" r="3"/><circle cx="491" cy="39" r="3"/><circle cx="541" cy="32" r="3"/><circle cx="590" cy="28" r="3"/>
  </g>
  <text x="48" y="198" font-size="12" fill="#111">Step 1</text>
  <text x="540" y="198" font-size="12" fill="#111">Step 12</text>
  <text x="8" y="24" font-size="12" fill="#111">0.70</text>
  <text x="14" y="174" font-size="12" fill="#111">0</text>
</svg>

| Step | Interruptions | Average recall |
| ---: | ---: | ---: |
| 1 | 86 | `0.083` |
| 2 | 82 | `0.162` |
| 3 | 82 | `0.244` |
| 4 | 71 | `0.310` |
| 5 | 78 | `0.384` |
| 6 | 78 | `0.459` |
| 7 | 69 | `0.525` |
| 8 | 60 | `0.582` |
| 9 | 63 | `0.645` |
| 10 | 46 | `0.688` |
| 11 | 37 | `0.722` |
| 12 | 23 | `0.742` |

Black-line plot by time:

<svg width="620" height="210" viewBox="0 0 620 210" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Profile recovery by time">
  <rect x="0" y="0" width="620" height="210" fill="white"/>
  <line x1="48" y1="170" x2="590" y2="170" stroke="#444" stroke-width="1"/>
  <line x1="48" y1="20" x2="48" y2="170" stroke="#444" stroke-width="1"/>
  <polyline fill="none" stroke="black" stroke-width="3" points="48,154 184,148 319,113 455,52 590,22"/>
  <g fill="black">
    <circle cx="48" cy="154" r="3"/><circle cx="184" cy="148" r="3"/><circle cx="319" cy="113" r="3"/><circle cx="455" cy="52" r="3"/><circle cx="590" cy="22" r="3"/>
  </g>
  <text x="44" y="198" font-size="12" fill="#111">1m</text>
  <text x="176" y="198" font-size="12" fill="#111">2m</text>
  <text x="310" y="198" font-size="12" fill="#111">5m</text>
  <text x="442" y="198" font-size="12" fill="#111">10m</text>
  <text x="570" y="198" font-size="12" fill="#111">End</text>
  <text x="8" y="24" font-size="12" fill="#111">0.70</text>
  <text x="14" y="174" font-size="12" fill="#111">0</text>
</svg>

| Time cap | Samples observed | Average recall | Median recall |
| --- | ---: | ---: | ---: |
| 1 min | 33 | `0.079` | `0.089` |
| 2 min | 100 | `0.106` | `0.100` |
| 5 min | 100 | `0.298` | `0.296` |
| 10 min | 100 | `0.587` | `0.582` |
| End of 12 steps | 100 | `0.742` | `0.751` |

### Fully Demonstrated Example

Example user: `fake_user_001`.

Task: `Draft a research-style essay on the major debates in bioethics, with attention to mechanism, counterargument, and evidence.`

Full hidden profile, limited to wording style, writing style, and structural preferences:

1. Avoid generic academic filler.
2. Favor conceptual synthesis over listing disconnected claims.
3. Make each sentence connect more explicitly to the prior idea and task.
4. Use cautious qualifiers only when they clarify uncertainty, not as padding.
5. Open paragraphs with a debatable claim rather than a broad topic sentence.
6. Avoid vague intensifiers and let the sentence's logic carry emphasis.
7. Use more specific wording instead of broad or generic phrasing.
8. Keep wording flexible enough to avoid sounding overly narrow too early.
9. Explain the mechanism or reasoning behind important claims.
10. Keep sentence rhythm varied: short claim, longer explanation, concise implication.

Legend: <span style="color:red">&#9679;</span> interruption point; <mark>yellow</mark> chosen repair.

| Step | Time | Generated text | Simulator decision | Interpreter record | Recorded memory | Recall |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | `104.5s` | <span style="color:red">&#9679;</span> The essay opens by saying that bioethics is complex and widely debated. It gestures toward evidence, values, and institutions, but it does not yet state a contestable claim. The paragraph feels smooth while leaving the reader unsure what kind of argument will follow. | Interrupt: the passage is fluent but misses `Avoid generic academic filler.` | The interrupted passage is under-specified relative to that hidden writing-style preference. | <mark>Revise the passage so it follows: Avoid generic academic filler.</mark> Stored as `offline_global`. | `0.042` |
| 2 | `184.3s` | The next passage begins by naming its relation to the prior point. Because the earlier claim depends on evidence, this paragraph turns to the structure that makes evidence persuasive. The transition carries the argument forward instead of simply adding another topic. | No interruption. The passage satisfied the expected transition/connection preference. | No interpreter call. | No update. | `0.042` |
| 3 | `278.0s` | <span style="color:red">&#9679;</span> The draft then notes that different approaches can produce different outcomes. It treats this point as important without explaining what changes, who is affected, or why the distinction matters. As a result, the paragraph sounds plausible but thin. | Interrupt: the passage misses `Make each sentence connect more explicitly to the prior idea and task.` | The interrupted passage is under-specified relative to that hidden writing-style preference. | <mark>Revise the passage so it follows: Make each sentence connect more explicitly to the prior idea and task.</mark> Stored as `offline_global`. | `0.168` |
| 4 | `323.1s` | The passage keeps the prose analytical and controlled. It states a claim, explains why the claim matters, and avoids drifting into generic summary. The style remains readable while still carrying argumentative weight. | No interruption. The passage was acceptable for the expected style preference. | No interpreter call. | No update. | `0.168` |
| 5 | `406.7s` | <span style="color:red">&#9679;</span> The draft tries to transition into a new section by announcing another aspect of bioethics. It names the topic but not the argumentative pressure behind it. The reader receives a new heading in sentence form rather than a developed turn in the essay. | Interrupt: the passage misses `Open paragraphs with a debatable claim rather than a broad topic sentence.` | The interrupted passage is under-specified relative to that hidden writing-style preference. | <mark>Revise the passage so it follows: Open paragraphs with a debatable claim rather than a broad topic sentence.</mark> Stored as `offline_global`. | `0.295` |
| 6 | `472.7s` | <span style="color:red">&#9679;</span> The essay next claims that evidence should be balanced with caution. Yet it does not explain what kind of evidence carries the most weight or how caution changes the claim. The result is orderly, but the paragraph remains too general to guide revision. | Interrupt: the passage misses `Avoid vague intensifiers and let the sentence's logic carry emphasis.` | The interrupted passage is under-specified relative to that hidden writing-style preference. | <mark>Revise the passage so it follows: Avoid vague intensifiers and let the sentence's logic carry emphasis.</mark> Stored as `offline_global`. | `0.400` |
| 7 | `581.4s` | <span style="color:red">&#9679;</span> The passage introduces a possible objection and then moves past it quickly. It says critics may disagree, but it does not give their concern enough shape to test the main argument. The prose gestures toward contrast without making the contrast do analytical work. | Interrupt: the passage misses `Use more specific wording instead of broad or generic phrasing.` | The interrupted passage is under-specified relative to that hidden writing-style preference. | <mark>Revise the passage so it follows: Use more specific wording instead of broad or generic phrasing.</mark> Stored as `offline_global`. | `0.505` |
| 8 | `646.5s` | <span style="color:red">&#9679;</span> The draft describes bioethics as a field with practical and theoretical stakes. It joins those stakes with smooth connective phrases, but the sentences do not clearly depend on one another. The paragraph reads like adjacent observations rather than a single developing claim. | Interrupt: the passage misses `Keep wording flexible enough to avoid sounding overly narrow too early.` | The interrupted passage is under-specified relative to that hidden writing-style preference. | <mark>Revise the passage so it follows: Keep wording flexible enough to avoid sounding overly narrow too early.</mark> Stored as `offline_global`. | `0.621` |
| 9 | `757.4s` | The paragraph explains the mechanism behind the claim. The reader can see how a change in incentives alters interpretation, then how that altered interpretation changes the evidence a writer can use. The paragraph therefore gives a reason, not just a conclusion. | No interruption. The passage satisfied the expected mechanism preference. | No interpreter call. | No update. | `0.621` |
| 10 | `792.8s` | The paragraph uses a compact rhythm. A short claim sets the direction; a longer sentence explains the pressure behind it. The final sentence lands cleanly. | No interruption. The passage satisfied the expected rhythm preference. | No interpreter call. | No update. | `0.621` |
| 11 | `876.3s` | The passage keeps the prose analytical and controlled. It states a claim, explains why the claim matters, and avoids drifting into generic summary. The style remains readable while still carrying argumentative weight. | No interruption. The passage was acceptable. | No interpreter call. | No update. | `0.621` |
| 12 | `989.0s` | The next passage begins by naming its relation to the prior point. Because the earlier claim depends on evidence, this paragraph turns to the structure that makes evidence persuasive. The transition carries the argument forward instead of simply adding another topic. | No interruption. The passage was acceptable. | No interpreter call. | No update. | `0.621` |

Recovered helper profile for this example:

1. Avoid generic academic filler.
2. Make each sentence connect more explicitly to the prior idea and task.
3. Open paragraphs with a debatable claim rather than a broad topic sentence.
4. Avoid vague intensifiers and let the sentence's logic carry emphasis.
5. Use more specific wording instead of broad or generic phrasing.
6. Keep wording flexible enough to avoid sounding overly narrow too early.

When an interruption happens, the system records the stop point, simulator rationale, interpreter reason, selected repair, memory scope, and recovery score in the raw simulation JSON. The compact exporter keeps those fields in `interruption_audit.jsonl`.

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
python run_fake_profile_simulation.py --count 100 --max-steps 12
```

Offline sanity simulation:

```bash
python run_fake_profile_simulation.py --count 100 --max-steps 12 --offline
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

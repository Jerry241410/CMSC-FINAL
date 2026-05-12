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

The latest available run here was offline because `OPENAI_API_KEY` was not set. It used `100` samples, complex hidden profiles, and `12` generated steps per sample. Interruption was decision-based: each chunk was assessed against the next hidden preference and the simulator interrupted only when the chunk missed an unrecovered preference.

### Summary Statistics

| Metric | Mean | Median | Min | Max | P10 | P90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Target profile items | `11.44` | `11.00` | `10` | `13` | `10.00` | `13.00` |
| Target profile words | `118.60` | `119.00` | `94` | `139` | `103.00` | `132.10` |
| Unique words per profile | `89.21` | `89.00` | `75` | `104` | `79.90` | `99.10` |
| Duplicate word count | `29.39` | `29.00` | `15` | `45` | `21.00` | `38.00` |
| Duplicate word ratio | `0.246` | `0.243` | `0.153` | `0.324` | `0.201` | `0.288` |
| Recovered profile items | `7.49` | `8.00` | `4` | `11` | `6.00` | `9.00` |
| Final recall | `0.656` | `0.653` | `0.383` | `0.916` | `0.500` | `0.817` |

Most frequent words across generated profiles: `the` 476, `a` 338, `or` 265, `prefer` 264, `with` 253, `and` 237, `avoid` 210, `to` 198, `use` 194, `that` 193, `when` 192, `concrete` 189.

| Run metric | Value |
| --- | ---: |
| Samples | `100` |
| Total generated steps | `1200` |
| Interruptions | `749` |
| Non-interruptions | `451` |
| Mean interruptions per user | `7.49` |
| Final precision, mean / median | `1.000 / 1.000` |
| Selected option actions | `587` |
| Manual describe actions | `162` |

### Recovery Plots

Black-line plot by step:

<svg width="620" height="210" viewBox="0 0 620 210" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Profile recovery by step">
  <rect x="0" y="0" width="620" height="210" fill="white"/>
  <line x1="48" y1="170" x2="590" y2="170" stroke="#444" stroke-width="1"/>
  <line x1="48" y1="20" x2="48" y2="170" stroke="#444" stroke-width="1"/>
  <polyline fill="none" stroke="black" stroke-width="3" points="48,156 97,141 147,127 196,116 245,99 294,83 344,71 393,59 442,47 491,36 541,28 590,22"/>
  <g fill="black">
    <circle cx="48" cy="156" r="3"/><circle cx="97" cy="141" r="3"/><circle cx="147" cy="127" r="3"/><circle cx="196" cy="116" r="3"/>
    <circle cx="245" cy="99" r="3"/><circle cx="294" cy="83" r="3"/><circle cx="344" cy="71" r="3"/><circle cx="393" cy="59" r="3"/>
    <circle cx="442" cy="47" r="3"/><circle cx="491" cy="36" r="3"/><circle cx="541" cy="28" r="3"/><circle cx="590" cy="22" r="3"/>
  </g>
  <text x="48" y="198" font-size="12" fill="#111">Step 1</text>
  <text x="540" y="198" font-size="12" fill="#111">Step 12</text>
  <text x="8" y="24" font-size="12" fill="#111">0.70</text>
  <text x="14" y="174" font-size="12" fill="#111">0</text>
</svg>

| Step | Interruptions | Average recall |
| ---: | ---: | ---: |
| 1 | 72 | `0.062` |
| 2 | 74 | `0.129` |
| 3 | 72 | `0.191` |
| 4 | 66 | `0.251` |
| 5 | 79 | `0.319` |
| 6 | 68 | `0.381` |
| 7 | 64 | `0.435` |
| 8 | 61 | `0.489` |
| 9 | 60 | `0.543` |
| 10 | 55 | `0.591` |
| 11 | 43 | `0.628` |
| 12 | 35 | `0.656` |

Black-line plot by time:

<svg width="620" height="210" viewBox="0 0 620 210" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Profile recovery by time">
  <rect x="0" y="0" width="620" height="210" fill="white"/>
  <line x1="48" y1="170" x2="590" y2="170" stroke="#444" stroke-width="1"/>
  <line x1="48" y1="20" x2="48" y2="170" stroke="#444" stroke-width="1"/>
  <polyline fill="none" stroke="black" stroke-width="3" points="48,156 184,152 319,119 455,64 590,22"/>
  <g fill="black">
    <circle cx="48" cy="156" r="3"/><circle cx="184" cy="152" r="3"/><circle cx="319" cy="119" r="3"/><circle cx="455" cy="64" r="3"/><circle cx="590" cy="22" r="3"/>
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
| 1 min | 33 | `0.062` | `0.080` |
| 2 min | 100 | `0.083` | `0.080` |
| 5 min | 100 | `0.239` | `0.239` |
| 10 min | 100 | `0.492` | `0.492` |
| End of 12 steps | 100 | `0.656` | `0.653` |

### Fully Demonstrated Example

Example user: `fake_user_001`.

Task: `Draft a research-style essay on the major debates in bioethics, with attention to mechanism, counterargument, and evidence.`

Full hidden profile:

1. Open paragraphs with a debatable claim rather than a broad topic sentence.
2. Make each sentence connect more explicitly to the prior idea and task.
3. Avoid overusing `important` and replace it with the exact reason something matters.
4. For bioethics, prefer examples that name a concrete case, actor, or mechanism before generalizing.
5. Use more specific wording instead of broad or generic phrasing.
6. Avoid generic academic filler such as `in today's society` or `throughout history`.
7. Favor conceptual synthesis over listing disconnected claims.
8. Use cautious qualifiers only when they clarify uncertainty, not as padding.
9. Keep wording flexible enough to avoid sounding overly narrow too early.
10. Explain the mechanism or reasoning behind important claims.
11. Keep sentence rhythm varied: short claim, longer explanation, concise implication.

Legend: <span style="color:red">●</span> interruption point; <mark>yellow</mark> chosen repair.

| Step | Time | Generated text | Simulator decision | Interpreter record | Recorded memory | Recall |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | `104.5s` | In bioethics, the draft has established a broad claim. This sentence stays broad and fluent, but it does not make the specific profile-sensitive move the user expects. | No interruption. The simulator judged the chunk acceptable for this step. | No interpreter call. | No update. | `0.000` |
| 2 | `184.3s` | This sentence deliberately follows the user's preference to make each sentence connect more explicitly to the prior idea and task. | No interruption. The generated chunk already follows the expected preference. | No interpreter call. | No update. | `0.000` |
| 3 | `278.0s` | In bioethics, the draft has established a broad claim. <span style="color:red">●</span> This sentence stays broad and fluent, but it does not make the specific profile-sensitive move the user expects. | Interrupt: generated chunk missed `Avoid overusing important and replace it with the exact reason something matters.` | The interrupted sentence is under-specified relative to that hidden preference. | <mark>Revise the sentence so it follows: Avoid overusing important and replace it with the exact reason something matters.</mark> Stored as `offline_global`. | `0.101` |
| 4 | `323.1s` | This sentence deliberately follows the user's preference to use a concrete bioethics case, actor, or mechanism before generalizing. | No interruption. The expected preference was satisfied. | No interpreter call. | No update. | `0.101` |
| 5 | `406.7s` | In bioethics, the draft has established a broad claim. <span style="color:red">●</span> This sentence stays broad and fluent, but it does not make the specific profile-sensitive move the user expects. | Interrupt: generated chunk missed `Use more specific wording instead of broad or generic phrasing.` | The interrupted sentence is under-specified relative to that hidden preference. | <mark>Revise the sentence so it follows: Use more specific wording instead of broad or generic phrasing.</mark> Stored as `offline_global`. | `0.185` |
| 6 | `472.7s` | In bioethics, the draft has established a broad claim. <span style="color:red">●</span> This sentence stays broad and fluent, but it does not make the specific profile-sensitive move the user expects. | Interrupt: generated chunk missed `Avoid generic academic filler such as in today's society or throughout history.` | The interrupted sentence is under-specified relative to that hidden preference. | <mark>Revise the sentence so it follows: Avoid generic academic filler such as in today's society or throughout history.</mark> Stored as `offline_global`. | `0.286` |
| 7 | `581.4s` | In bioethics, the draft has established a broad claim. <span style="color:red">●</span> This sentence stays broad and fluent, but it does not make the specific profile-sensitive move the user expects. | Interrupt: generated chunk missed `Favor conceptual synthesis over listing disconnected claims.` | The interrupted sentence is under-specified relative to that hidden preference. | <mark>Revise the sentence so it follows: Favor conceptual synthesis over listing disconnected claims.</mark> Stored as `offline_global`. | `0.345` |
| 8 | `646.5s` | In bioethics, the draft has established a broad claim. <span style="color:red">●</span> This sentence stays broad and fluent, but it does not make the specific profile-sensitive move the user expects. | Interrupt: generated chunk missed `Use cautious qualifiers only when they clarify uncertainty, not as padding.` | The interrupted sentence is under-specified relative to that hidden preference. | <mark>Revise the sentence so it follows: Use cautious qualifiers only when they clarify uncertainty, not as padding.</mark> Stored as `offline_global`. | `0.437` |
| 9 | `757.4s` | This sentence deliberately follows the user's preference to keep wording flexible enough to avoid sounding overly narrow too early. | No interruption. The expected preference was satisfied. | No interpreter call. | No update. | `0.437` |
| 10 | `792.8s` | This sentence deliberately follows the user's preference to explain the mechanism or reasoning behind important claims. | No interruption. The expected preference was satisfied. | No interpreter call. | No update. | `0.437` |
| 11 | `876.3s` | This sentence deliberately follows the user's preference to keep sentence rhythm varied: short claim, longer explanation, concise implication. | No interruption. The expected preference was satisfied. | No interpreter call. | No update. | `0.437` |
| 12 | `989.0s` | This sentence stays broad and fluent, but the simulator treated the relevant preference as already acceptable or recovered for this step. | No interruption. | No interpreter call. | No update. | `0.437` |

Recovered helper profile for this example:

1. Avoid overusing `important` and replace it with the exact reason something matters.
2. Use more specific wording instead of broad or generic phrasing.
3. Avoid generic academic filler such as `in today's society` or `throughout history`.
4. Favor conceptual synthesis over listing disconnected claims.
5. Use cautious qualifiers only when they clarify uncertainty, not as padding.

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

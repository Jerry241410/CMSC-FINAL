# Writing Helper

Local browser prototype for interruption-aware AI writing. The app streams a draft, lets the user stop when the current sentence feels wrong, proposes local rewrites, and stores recurring writing preferences in a local profile.

## Research Question

Can interruption behavior during AI-assisted writing be used to reconstruct a user's latent writing profile, including preferences about wording, tone, structure, specificity, and argumentative style?

The current prototype explores a workflow where:

1. The AI writes interactively.
2. The user stops generation when something feels wrong.
3. The system interprets why the user interrupted.
4. It proposes revision options.
5. The selected revision becomes evidence about the user's preferences.
6. Over time, the assistant builds a reusable writing profile.

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

The latest available run here was offline because `OPENAI_API_KEY` was not set. It used `100` samples, style-only hidden profiles, and `30` generated passage steps per sample. Every simulated task now generates domain-specific essay content, not placeholder prose: bioethics uses autonomy/end-of-life/reproductive ethics examples, climate policy uses carbon pricing/adaptation/transition examples, HCI uses usability/automation/trust examples, and so on. Interruption was decision-based: each generated passage was assessed against a hidden wording/style/structure preference, and the simulator interrupted only when the passage missed an unrecovered preference.

The simulated feedback loop now follows the intended interaction: after interruption, the writing assistant offers a writing-fill menu of candidate revisions; the simulator selects the best option if one fits; if none fits, it gives a custom request; the interpreter infers a preference from that selected option or custom request. A preference is only promoted into the recovered profile after `3` repeated observations.

### Summary Statistics

| Metric | Mean | Median | Min | Max |
| --- | ---: | ---: | ---: | ---: |
| Target profile items | `10.47` | `10.00` | `9` | `12` |
| Target profile words | `102.32` | `102.50` | `79` | `125` |
| Unique words per profile | `78.22` | `78.00` | `63` | `92` |
| Duplicate word count | `24.10` | `23.00` | `9` | `41` |
| Duplicate word ratio | `0.233` | `0.228` | `0.108` | `0.333` |
| Recovered profile items | `5.00` | `5.00` | `1` | `9` |
| Final recall | `0.489` | `0.495` | `0.096` | `0.923` |

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

### Recovery Rate Line Plot

![Average recovery rate line plot](docs/avg_recovery_rate_line_plot.svg)

Average recovery by selected steps:

| Step | Interruptions | Average recall |
| ---: | ---: | ---: |
| 1 | 86 | `0.000` |
| 5 | 86 | `0.000` |
| 10 | 86 | `0.000` |
| 15 | 89 | `0.000` |
| 20 | 79 | `0.031` |
| 25 | 80 | `0.260` |
| 30 | 57 | `0.489` |

| Time cap | Samples observed | Average recall | Median recall |
| --- | ---: | ---: | ---: |
| 10 min | 100 | `0.000` | `0.000` |
| 20 min | 100 | `0.004` | `0.000` |
| 30 min | 100 | `0.251` | `0.227` |
| 40 min | 100 | `0.487` | `0.495` |
| End of 30 steps | 100 | `0.489` | `0.495` |

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

The table below shows selected steps from the `30`-step run. It demonstrates the actual mechanism: the simulator does not reveal the answer directly; it chooses from writing-fill options, or uses custom feedback when no option fits. The interpreter then infers a reusable preference from that choice. A preference is promoted only after `3` similar observations.

| Step | Time | Generated passage | Writing-fill choice | Interpreter record | Memory state | Recall |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | `104.5s` | <span style="color:red">&#9679;</span> Bioethics is a broad field that deals with medicine, technology, public health, and social values. Many issues in the field are important because they affect patients, professionals, and society. The main point is that new medical capacities create many complicated questions that require careful discussion. | Options included `Make more specific`, `Improve transition`, <mark>`Match latent style: Avoid generic academic filler.`</mark>, `Explain mechanism`, `Open with claim`, and `None fit`. Simulator selected the highlighted option. | Interpreted from selected option: prefer avoiding generic academic filler. | Local observation `1/3`; no global profile update. | `0.000` |
| 3 | `281.8s` | <span style="color:red">&#9679;</span> Informed consent is also significant because it helps patients understand medical decisions. It involves information, understanding, and voluntary choice, but the process can be difficult in real clinical settings. For this reason, informed consent remains a central topic in medical ethics. | Simulator selected <mark>`Improve the argumentative transition.`</mark> | Interpreted from selected option: make each sentence connect more explicitly to the prior idea and task. | Local observation `1/3`; no global profile update. | `0.000` |
| 6 | `531.5s` | <span style="color:red">&#9679;</span> Reproductive ethics includes abortion, embryo selection, surrogacy, and genetic testing. These issues are complicated because they involve bodies, families, future children, and social values. Different people disagree because they begin from different moral assumptions. | No offered option fit, so simulator chose <mark>`None fit`</mark> and wrote custom feedback: avoid vague intensifiers; let sentence logic carry emphasis. | Interpreted from custom feedback: emphasis should come from reasoning rather than vague intensifiers. | Local observation `1/3`; no global profile update. | `0.000` |
| 9 | `843.1s` | <span style="color:red">&#9679;</span> Gene editing is one of the most important issues in modern bioethics because it can change future generations. It raises concerns about safety, consent, inequality, and the role of scientists. The debate shows that new technologies require strong ethical rules. | Simulator selected <mark>`Explain the mechanism behind the claim.`</mark> | Interpreted from selected option: explain the mechanism or reasoning behind important claims. | Local observation `1/3`; no global profile update. | `0.000` |
| 11 | `927.6s` | <span style="color:red">&#9679;</span> Public health ethics is important because it affects everyone in society. Vaccination, quarantine, and surveillance involve many competing values and can be controversial. These debates show why public health requires careful ethical thinking. | Simulator selected <mark>`Match latent style: Avoid generic academic filler.`</mark> | Same inferred preference as step 1. | Local observation `2/3`; still not promoted. | `0.000` |
| 13 | `1035.7s` | <span style="color:red">&#9679;</span> The debates discussed above are connected in many ways. They all involve values, choices, risks, and social consequences. A good essay should discuss these issues clearly and carefully. | Simulator selected <mark>`Improve the argumentative transition.`</mark> | Same inferred preference as step 3. | Local observation `2/3`; still not promoted. | `0.000` |
| 21 | `1639.5s` | <span style="color:red">&#9679;</span> Bioethics is an important field because it helps society think about medicine and technology. It covers many controversial issues and asks people to consider different values. These debates matter because they affect patients, doctors, researchers, and the public. | No offered option fit, so simulator chose <mark>`None fit`</mark> and wrote custom feedback: avoid generic academic filler. | Interpreted from custom feedback as the same preference observed in steps 1 and 11. | Observation `3/3`; promoted to recovered profile. | `0.042` |
| 23 | `1771.8s` | <span style="color:red">&#9679;</span> Informed consent is important in research and clinical care. It gives patients information and helps them make choices. It is also connected to autonomy, trust, and professional responsibility. | Simulator selected <mark>`Improve the argumentative transition.`</mark> | Same inferred connection preference observed in steps 3 and 13. | Observation `3/3`; promoted to recovered profile. | `0.168` |
| 24 | `1851.3s` | <span style="color:red">&#9679;</span> End-of-life care may be complicated and sensitive in many cases. Patients might want comfort, families might disagree, and clinicians might be uncertain about what to do. This area of bioethics requires careful judgment. | No offered option fit, so simulator chose <mark>`None fit`</mark> and wrote custom feedback: use cautious qualifiers only when they clarify uncertainty. | Interpreted from custom feedback: avoid padding the prose with unnecessary caution. | Observation `3/3`; promoted to recovered profile. | `0.284` |
| 25 | `1955.4s` | <span style="color:red">&#9679;</span> Assisted dying is a topic in bioethics that involves autonomy, suffering, and professional responsibility. People disagree about whether it should be allowed and how it should be regulated. The debate includes both individual rights and social risks. | Simulator selected <mark>`Open with a debatable claim.`</mark> | Same inferred structure preference observed earlier. | Observation `3/3`; promoted to recovered profile. | `0.411` |
| 29 | `2226.3s` | <span style="color:red">&#9679;</span> Medical AI is a growing issue in bioethics because it can affect diagnosis, treatment, and trust. It may improve care, but it can also create bias and responsibility problems. These issues show why technology needs ethical oversight. | Simulator selected <mark>`Explain the mechanism behind the claim.`</mark> | Same inferred mechanism preference observed earlier. | Observation `3/3`; promoted to recovered profile. | `0.495` |
| 30 | `2334.9s` | <span style="color:red">&#9679;</span> The major debates in bioethics show that medicine involves science, values, and policy. Each debate has supporters and critics. A strong essay should be clear, balanced, and thoughtful. | Simulator selected <mark>`Match latent style: Keep sentence rhythm varied.`</mark> | Interpreted from selected option: prefer varied sentence rhythm. | Observation `3/3`; promoted to recovered profile. | `0.600` |

Recovered helper profile for this example:

1. Avoid generic academic filler.
2. Make each sentence connect more explicitly to the prior idea and task.
3. Use cautious qualifiers only when they clarify uncertainty, not as padding.
4. Open paragraphs with a debatable claim rather than a broad topic sentence.
5. Explain the mechanism or reasoning behind important claims.
6. Keep sentence rhythm varied: short claim, longer explanation, concise implication.

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
python run_fake_profile_simulation.py --count 100 --max-steps 30
```

Offline sanity simulation:

```bash
python run_fake_profile_simulation.py --count 100 --max-steps 30 --offline
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

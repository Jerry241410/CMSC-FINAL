# Writing Helper: An Interruption-Aware AI Writing Assistant

Project C (Design): profile-based AI writing helper.

## Abstract

Writing Helper is a profile-based AI writing assistant that learns from the moment a writer stops the machine. Instead of treating interruption as a failure, the prototype treats it as feedback: when the user stops a generated sentence, chooses a rewrite, or writes a custom repair, the system infers a possible writing preference and stores it in a local profile. The project matters because many AI writing tools produce fluent text that still feels wrong for a particular writer. This prototype asks whether ordinary revision behavior can become a more transparent and less prompt-heavy way to personalize AI writing support.

## AI Disclosure

![AI disclosure statement](docs/full_statement.svg)

I designed the whole system and communicated with Professor Lee about the design. AI was used only for coding support and revision of code. AI-generated code or code edits were reviewed and approved. The following model(s) or application(s) were used: Chatgpt 5.4.

I chose a direct disclosure approach for both the report and the project. A generic sentence like "AI was used" would not fit the values of the system. The disclosure names the kind of contribution AI made, the degree of human review, and the model used. I designed the project concept and system logic myself, with feedback from Professor Lee, while using AI as a coding and code-revision assistant. I use vibe coding in this assignment so the limitation is this disclosure is still a compact label rather than a full process log.

## Motivation

Most AI writing assistants are good at producing coherent prose. The harder problem is producing prose that feels like the writer's intended voice, argument, and level of specificity. A sentence can be grammatical and still be wrong because the user doens't like it. In other words, a good writing assitant shall understand users' preference. 

This project responds to a gap between fluent generation and writer agency. Current assistants often rely on explicit prompting: "make this more concise," "sound more academic," or "use my style." That favors users who already know how to describe their preferences. Writing Helper explores a different signal. It asks whether the system can learn from behavior the writer already performs: stopping the AI when something feels off and selecting a better direction.

The project connects to human-AI writing research such as CoAuthor, which shows that interaction traces are useful evidence in collaborative writing, not just leftover metadata. It also connects to GhostWriter and other preference-learning systems that treat edits and annotations as a way to personalize assistance while preserving user control. My design borrows that general insight but narrows the focus to interruption: the stop point becomes a small but meaningful expression of taste, judgment, and frustration.

## Intended Users and Use Contexts

The intended users are students, researchers, and reflective writers who use AI for drafting but do not want to hand over their voice. The prototype is especially aimed at writers who can recognize when a sentence feels wrong but may not immediately know how to explain the preference behind that feeling.

Typical use contexts include drafting course essays, research-style paragraphs, reflective writing, memos, and project reports. The system is not designed as a one-click essay generator. It is designed as a slower, more inspectable writing partner: the user starts a draft, interrupts at bad moments, compares replacement options, optionally writes a custom repair, and watches a local writing profile form over time.

## Prototype

Run the prototype locally:

```bash
python writing.py
```

The app starts a local web UI at:

```text
http://127.0.0.1:8765
```

The current interface includes:

- user and task input
- a live generated document
- stop, accept, continue, and export controls
- replacement options after interruption
- a custom revision box
- interpreter output explaining the likely reason for the stop
- profile memory showing local observations and durable preferences
- an activity log and timing status

Main implementation files:

- `writing_helper/web.py`: local web server and API
- `writing_helper/web_static/`: browser UI
- `writing_helper/orchestrator.py`: workflow coordination
- `writing_helper/agents.py`: writer, interpreter, replacement, and memory agents
- `writing_helper/simulation.py`: fake-profile recovery simulation
- `writing_helper/storage.py`: local profile persistence

The multi-agent system uses AutoGen Core to coordinate the writer, interpreter, replacement, and memory agents.

## Design Rationale

I chose interruption instead because the stop moment is high-signal: it marks the exact sentence where the user's expectation and the AI's output diverged.

The second major decision is to use a profile, not only immediate rewrites. A local rewrite solves the sentence in front of the user, but it does not help the assistant remember the writer. The profile turns repeated choices into durable preferences, such as "explain the mechanism behind important claims." This matters because personalization should be inspectable. The user can see the memory.

The third decision is to separate local observations from global profile items. In an earlier version, every selected revision was immediately treated as a lasting preference. That was too reactive. The current design requires repeated evidence before promoting a preference. This protects the profile from one-off choices and makes the system less likely to overfit a single sentence.

I vibe-coded the prototype, but I designed the full system structure and workflow myself and discussed the design with Professor Lee. The project is organized as a multi-agent writing system rather than a single chatbot. The writer agent produces draft text, the user interrupts at the sentence that feels wrong, the interpreter agent analyzes the stop point, the replacement agent generates possible repairs, and the memory layer records repeated preferences in a local profile. The web interface, profile storage, orchestration code, and simulation pipeline are all built around that sequence.

My main design choices were about how the whole system should work:

- The system begins from interruption because the exact stop point gives more useful evidence than a general request like "make this better."
- The agents are separated by role because writing, interpreting a problem, proposing revisions, and updating memory are different tasks that need different prompts and outputs.
- The profile has local and global memory because one selected rewrite should not immediately become a permanent claim about the writer.
- The interface keeps the draft, replacement choices, interpreter output, and profile memory visible because each part represents one stage of the system's reasoning loop.


Alternatives I considered:

- A pre-written profile setup, where the user describes their preferred style before writing. I did not choose this as the main design because writers often discover what they want only after seeing a sentence that feels wrong.
- A single-agent system, where one model handles writing, diagnosis, revision, and memory. I chose a multi-agent structure because each stage has a different job and should be easier to inspect.
- Immediate permanent profile updates after every selected rewrite. This would make the profile grow quickly, but it could misread a temporary choice as a stable writing preference.



## Process and Iterations

### Iteration 1: From Simple Rewrite Tool to Interruption Signal

The first version treated interruption mostly as a trigger for replacement. The user could stop generation, and the system would offer a small set of rewrite options. This proved useful, but shallow. It helped repair a sentence without explaining what the repair revealed about the writer.


Before:

```text
User stops generation -> replacement options appear -> selected replacement is inserted.
```

After:

```text
User stops generation -> interpreter diagnoses the stop -> replacement options appear -> selected repair becomes evidence for profile.
```

### Iteration 2: From Immediate Memory to Repeated Evidence

The second version wrote selected preferences directly into the global profile. This felt satisfying because the profile changed quickly, but it created a problem: one interruption could become a permanent statement about the writer. That is not how writing preferences work. A writer may want more detail in one paragraph and less detail in another.

I changed the memory design so the system stores local observations first. A preference is promoted only after repeated evidence. In the current simulation, the threshold is `3` similar observations. This makes the profile slower but more credible.

Failure case:

```text
One selected option implies: "Use a more cautious qualifier."
Old behavior: save as a permanent preference.
Problem: the writer may only need caution for this one claim.
New behavior: store as local evidence until it repeats.
```

### Iteration 3: Fake-Profile Simulation

The third pivot was evaluation. At first, I could demonstrate the interface but could not clearly say whether the system recovered anything meaningful. To test the mechanism, I added fake-profile simulation. The simulator creates hidden user profiles, generates writing tasks, interrupts when generated prose violates the hidden profile, chooses from replacement options or writes custom feedback, and measures how many hidden preferences are recovered.

The latest available run was offline because `OPENAI_API_KEY` was not set. It used `100` samples, style-only hidden profiles, and `30` generated passage steps per sample. This is not a real model-based evaluation, but it checks whether the recovery and reporting pipeline works.

Summary from the offline simulation:

| Metric | Mean | Median | Min | Max |
| --- | ---: | ---: | ---: | ---: |
| Target profile items | `10.47` | `10.00` | `9` | `12` |
| Recovered profile items | `5.00` | `5.00` | `1` | `9` |
| Final recall | `0.489` | `0.495` | `0.096` | `0.923` |

![Average recovery rate line plot](docs/avg_recovery_rate_line_plot.svg)

One representative hidden profile included preferences such as:

- Make each sentence connect more explicitly to the prior idea and task.
- Use cautious qualifiers only when they clarify uncertainty, not as padding.
- Open paragraphs with a debatable claim rather than a broad topic sentence.
- Explain the mechanism or reasoning behind important claims.

In the demonstrated run, repeated interruptions eventually promoted six recovered profile items. The recovery curve was slow at first because the threshold prevented immediate promotion, then increased once repeated evidence accumulated.

### Example Process Trace

Example user: `fake_user_001`.

Task: `Draft a research-style essay on the major debates in bioethics, with attention to mechanism, counterargument, and evidence.`

Hidden profile preferences included:

- Avoid generic academic filler.
- Make each sentence connect more explicitly to the prior idea and task.
- Use cautious qualifiers only when they clarify uncertainty, not as padding.
- Open paragraphs with a debatable claim rather than a broad topic sentence.
- Explain the mechanism or reasoning behind important claims.
- Keep sentence rhythm varied: short claim, longer explanation, concise implication.

The trace below shows how the system moves from interruption to revision to profile memory.

| Step | Generated passage at interruption | Selected repair | Interpreter record | Memory state |
| ---: | --- | --- | --- | --- |
| 1 | `Bioethics is a broad field that deals with medicine, technology, public health, and social values.` | `Match latent style: Avoid generic academic filler.` | Prefer avoiding generic academic filler. | Local observation `1/3`; no global profile update. |
| 3 | `Informed consent is also significant because it helps patients understand medical decisions.` | `Improve the argumentative transition.` | Make each sentence connect more explicitly to the prior idea and task. | Local observation `1/3`; no global profile update. |
| 6 | `Reproductive ethics includes abortion, embryo selection, surrogacy, and genetic testing. These issues are complicated...` | Custom feedback: avoid vague intensifiers; let sentence logic carry emphasis. | Emphasis should come from reasoning rather than vague intensifiers. | Local observation `1/3`; no global profile update. |
| 21 | `Bioethics is an important field because it helps society think about medicine and technology.` | Custom feedback: avoid generic academic filler. | Same preference observed in steps 1 and 11. | Observation `3/3`; promoted to recovered profile. |
| 23 | `Informed consent is important in research and clinical care. It gives patients information and helps them make choices.` | `Improve the argumentative transition.` | Same connection preference observed in earlier steps. | Observation `3/3`; promoted to recovered profile. |
| 29 | `Medical AI is a growing issue in bioethics because it can affect diagnosis, treatment, and trust.` | `Explain the mechanism behind the claim.` | Explain the mechanism or reasoning behind important claims. | Observation `3/3`; promoted to recovered profile. |

Recovered helper profile for this example:

1. Avoid generic academic filler.
2. Make each sentence connect more explicitly to the prior idea and task.
3. Use cautious qualifiers only when they clarify uncertainty, not as padding.
4. Open paragraphs with a debatable claim rather than a broad topic sentence.
5. Explain the mechanism or reasoning behind important claims.
6. Keep sentence rhythm varied: short claim, longer explanation, concise implication.

## Ethical Implications

The main ethical issue is that the writing profile is built from behavioral data. An interruption may look small, but it can reveal information about a user's writing habits, confidence, style, academic needs, or even the kinds of arguments they struggle with. If this profile were stored insecurely, shared without consent, or used outside the writing context, it could become a privacy problem.

The second issue is overinterpretation. The system might treat one local revision as evidence of a stable preference, even when the user only wanted that change for one sentence or one assignment. This is why the prototype separates local observations from global profile memory and requires repeated evidence before promoting a preference. Still, this does not fully solve the problem. A more complete version should let users approve, edit, delete, or reject inferred profile items, and it should make clear which interruptions produced each profile claim.


## Reflection and Limitations

I learned that "personalization" is too vague unless the system can show what it thinks it has learned. The profile view became more important than I expected because it changes the assistant from a mysterious generator into a negotiable writing partner. I also learned that interruption is a richer design object than I first assumed. A stop is not just a command; it can be a complaint, a preference, a diagnosis, or a request for a different direction.

I also learned something about my own writing and design process. Because I vibe-coded the prototype, I sometimes moved faster than my explanations. Writing this report forced me to justify decisions that initially came from intuition: why the profile is visible, why promotion should be delayed, why the live document stays central, and why the system should not silently personalize.

The main limitation is that the strongest evaluation is simulated. The offline simulation demonstrates the mechanism, but it does not prove that real writers interrupt in stable enough patterns for accurate profile recovery. The prototype also depends on the quality of the interpreter. If the interpreter misreads the user's reason for stopping, the profile can drift. Another limitation is that the current profile treats preferences as fairly general, while real writing preferences are contextual: a lab report, reflective essay, and policy memo may require different voices.

In the future, I would add user controls for approving, editing, and deleting inferred profile items. I would also run a small user study where participants draft with the tool, then judge whether the recovered profile actually describes them. Finally, I would improve the UI so each profile item links back to the concrete interruptions that produced it.

## Run Instructions

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

Run the real AI simulation:

```bash
python run_fake_profile_simulation.py --count 100 --max-steps 30
```

Run the offline sanity simulation:

```bash
python run_fake_profile_simulation.py --count 100 --max-steps 30 --offline
```

Export a compact audit:

```bash
python export_simulation_report.py simulation_outputs/your_run.json
```

## References

Lee, M., Liang, P., & Yang, Q. (2022). *CoAuthor: Designing a human-AI collaborative writing dataset for exploring language model capabilities*. arXiv. https://arxiv.org/abs/2201.06796

Yeh, C., Ramos, G., Ng, R., Huntington, M., & Banks, R. (2024). *GhostWriter: Augmenting collaborative human-AI writing experiences through personalization and agency*. arXiv. https://arxiv.org/abs/2402.08855

Chen, V., et al. (2024). *Aligning LLM agents by learning latent preference from user edits*. arXiv. https://arxiv.org/abs/2404.15269

PAIR. (n.d.). *People + AI Guidebook*. Google. https://pair.withgoogle.com/guidebook/

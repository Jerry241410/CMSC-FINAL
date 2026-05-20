# Writing Helper Simulation Report

This report keeps the original recovery audit and adds the common, rare personal, and mixed-profile comparison.

## Run Setup

- Model: `offline-deterministic`
- Steps per profile: `50`
- Total profiles: `150`
- Count per group: `50`

## Group Recovery Comparison

| Group | Profiles | Avg recall | Interruptions | Manual actions | Avg elapsed seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| common | `50` | `0.852` | `1469` | `254` | `3596.31` |
| rare | `50` | `0.850` | `1491` | `358` | `3544.59` |
| mix | `50` | `0.851` | `1456` | `299` | `3538.54` |

## Overall Recovery

- Average recall: `0.851`
- Total interruptions: `4416`
- Manual/custom actions: `911`

## Profile Size Check

| Group | Mean profile items | Median | Min | Max |
| --- | ---: | ---: | ---: | ---: |
| common | `10.44` | `10.00` | `9` | `12` |
| rare | `10.54` | `11.00` | `9` | `12` |
| mix | `10.34` | `10.00` | `9` | `12` |

## Highlighted Samples

### Common Profile Sample

- User: `fake_common_001`
- Step: `1`
- Exact stopping time: `104.46` seconds
- Repair or simulator decision: The selected feedback indicates this reusable writing preference: Avoid generic academic filler.

Bioethics is a broad field that deals with medicine, technology, public health, and social values. Many issues in the field are important because they affect patients, professionals, and society. The main point is that new medical capacities create many complicated questions that require careful discussion. <mark>The passage keeps the prose analytical and controlled. It states a claim, explains why the claim matters, and avoids drifting into generic summary. The style remains readable while still carrying argumentative weight.</mark>

### Rare Profile Sample

- User: `fake_rare_001`
- Step: `1`
- Exact stopping time: `47.18` seconds
- Repair or simulator decision: The selected feedback indicates this reusable writing preference: Allow a warmer tone when describing vulnerable people affected by the issue.

Bioethics is a broad field that deals with medicine, technology, public health, and social values. Many issues in the field are important because they affect patients, professionals, and society. The main point is that new medical capacities create many complicated questions that require careful discussion. <mark>The revision keeps the analysis of bioethics grounded in people who must live with its consequences. It names harm without turning suffering into decoration, and it lets the human stake clarify why the argument matters. The tone becomes warmer while still remaining evidence-minded.</mark>

### Mix Profile Sample

- User: `fake_mix_001`
- Step: `2`
- Exact stopping time: `158.59` seconds
- Repair or simulator decision: The selected feedback indicates this reusable writing preference: Avoid overusing 'important' and replace it with the exact reason something matters.

Another major issue in human-computer interaction is automation. It matters because it affects people, institutions, and future research. The draft sounds relevant, but it relies on broad claims instead of showing how the argument works. <mark>The passage keeps the prose analytical and controlled. It states a claim, explains why the claim matters, and avoids drifting into generic summary. The style remains readable while still carrying argumentative weight.</mark>

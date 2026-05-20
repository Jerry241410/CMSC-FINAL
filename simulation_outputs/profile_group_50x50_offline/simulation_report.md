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
| common | `50` | `0.387` | `1634` | `115` | `3515.00` |
| rare | `50` | `0.171` | `1843` | `76` | `3526.07` |
| mix | `50` | `0.306` | `1699` | `136` | `3576.80` |

## Overall Recovery

- Average recall: `0.288`
- Total interruptions: `5176`
- Manual/custom actions: `327`

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

Bioethics is a broad field that deals with medicine, technology, public health, and social values. Many issues in the field are important because they affect patients, professionals, and society. The main point is that new medical capacities create many complicated questions that require careful discussion. <mark>Patient autonomy turns bioethics into a question of accountable decision-making. Clinical authority shapes which choices appear reasonable to patients before consent is formally requested. Hospital ethics cases show that formal choice can coexist with pressure, confusion, and unequal access to advocacy.</mark>

### Rare Profile Sample

- User: `fake_rare_001`
- Step: `1`
- Exact stopping time: `102.54` seconds
- Repair or simulator decision: The selected feedback indicates this reusable writing preference: Use more specific wording instead of broad or generic phrasing.

Bioethics is a broad field that deals with medicine, technology, public health, and social values. Many issues in the field are important because they affect patients, professionals, and society. The main point is that new medical capacities create many complicated questions that require careful discussion. <mark>Patient autonomy should be judged through concrete evidence rather than broad claims about impact. Hospital ethics cases show that formal choice can coexist with pressure, confusion, and unequal access to advocacy. The practical limit becomes clearer when the mechanism and affected setting are named together.</mark>

### Mix Profile Sample

- User: `fake_mix_001`
- Step: `1`
- Exact stopping time: `102.63` seconds
- Repair or simulator decision: The selected feedback indicates this reusable writing preference: Make counterarguments concrete enough that they feel like real objections.

Human-computer interaction includes an important debate about usability. Many scholars have different views, and the issue has broad implications for theory and practice. The controversy remains difficult because evidence, values, and institutional pressures point in different directions. <mark>Usability shows the tradeoff in concrete terms. Usability affects behavior by shaping attention, error recovery, and the cost of changing a decision. The same arrangement can improve consistency while narrowing judgment in borderline cases.</mark>

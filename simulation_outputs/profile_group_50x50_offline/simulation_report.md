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
| common | `50` | `0.857` | `1477` | `297` | `3572.10` |
| rare | `50` | `0.815` | `1465` | `364` | `3562.74` |
| mix | `50` | `0.879` | `1472` | `355` | `3556.19` |

## Overall Recovery

- Average recall: `0.851`
- Total interruptions: `4414`
- Manual/custom actions: `1016`

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

Bioethics is a broad field that deals with medicine, technology, public health, and social values. Many issues in the field are important because they affect patients, professionals, and society. The main point is that new medical capacities create many complicated questions that require careful discussion. <mark>Revise the passage so it follows this writing preference: Avoid generic academic filler.</mark>

### Rare Profile Sample

- User: `fake_rare_001`
- Step: `1`
- Exact stopping time: `71.35` seconds
- Repair or simulator decision: The selected feedback indicates this reusable writing preference: Allow a warmer tone when describing vulnerable people affected by the issue.

Bioethics is a broad field that deals with medicine, technology, public health, and social values. Many issues in the field are important because they affect patients, professionals, and society. The main point is that new medical capacities create many complicated questions that require careful discussion. <mark>Revise the passage so it follows this writing preference: Allow a warmer tone when describing vulnerable people affected by the issue.</mark>

### Mix Profile Sample

- User: `fake_mix_001`
- Step: `1`
- Exact stopping time: `58.39` seconds
- Repair or simulator decision: The selected feedback indicates this reusable writing preference: Prefer sentences that move from concrete scene to abstract claim.

Human-computer interaction includes an important debate about usability. Many scholars have different views, and the issue has broad implications for theory and practice. The paragraph names the controversy but does not yet explain the mechanism, evidence, or counterargument. <mark>Prefer sentences that move from concrete scene to abstract claim.</mark>

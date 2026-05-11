# Simulation Report

Source file: `offline_profile_recovery_100.json`
Scenario count: 100
Model: offline-deterministic
Max steps per user: 6
Wall-clock runtime: 0.0 seconds
Run note: Offline sanity run. It does not call an AI model.

## Summary

- Average final profile recall: 1.000
- Average final profile precision: 1.000
- Average overlap word count: 44.11
- Interruptions: 600
- Manual/custom actions: 0
- Average elapsed seconds per scenario: 329.95

## Recovery Over Time

| Time cap | Samples observed | Average recall | Median recall | Users at >= 0.25 recall | Users at >= 0.50 recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| 30 sec | 9 | 0.276 | 0.286 | 6 | 0 |
| 1 min | 66 | 0.232 | 0.223 | 26 | 0 |
| 2 min | 100 | 0.400 | 0.389 | 77 | 31 |
| 5 min | 100 | 0.950 | 1.000 | 100 | 100 |
| 10 min | 100 | 1.000 | 1.000 | 100 | 100 |

## Step Recovery

| Step | Samples | Average recall |
| ---: | ---: | ---: |
| 1 | 100 | 0.231 |
| 2 | 100 | 0.464 |
| 3 | 100 | 0.693 |
| 4 | 100 | 0.863 |
| 5 | 100 | 0.968 |
| 6 | 100 | 1.000 |

## Notes

- Recall is lexical overlap between the generated helper profile and the hidden target profile.
- The 10-minute scale uses each step's cumulative elapsed time when present; older simulation files without timing are treated as final-only observations.
- Exact item matches are expected to be low because the helper stores paraphrased preferences.

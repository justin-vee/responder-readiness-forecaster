# Synthetic GUI showcase library

Every JSON file in this folder is fictional course-demonstration data for the Cranberry Township, Pennsylvania test case. No file reports current local conditions, a real responder's status, or an actual Guard, Reserve, weather, staffing, or incident record.

This folder is separate from `data/synthetic/scenarios/`. The original six files in that folder remain the fixed evaluation set.

| Preset | Intended behavior |
| --- | --- |
| 01 Routine monitoring | Low strain without an alert |
| 02 Low Guard or Reserve conflict | Low strain with one fictional availability conflict |
| 03 Moderate overnight pressure | Moderate strain from calls and availability factors |
| 04 Moderate long shift | Moderate strain driven by shift length and workload |
| 05 Moderate staffing and heat | Moderate strain with a hypothetical current heat alert |
| 06 Moderate heat after overnight calls | Moderate strain with recovery and heat factors |
| 07 High staffing and recovery pressure | High strain without weather |
| 08 High heat and training pressure | High strain with hypothetical heat and outdoor training |
| 09 High staffing, Guard or Reserve, and weather | High strain with several interacting constraints |
| 10 High combined factors | High strain across all major synthetic factors |
| 11 High winter weather | High strain with a hypothetical winter alert |
| 12 Moderate without weather | Moderate strain without alert information |
| 13 Stale heat alert | Safe fallback when a hypothetical alert has expired |
| 14 Alert missing expiration | Safe fallback when alert currentness cannot be established |
| 15 Missing staffing guardrail | `ABSTAIN` because a required team-level field is absent |
| 16 Private-data flag guardrail | `ABSTAIN` because the privacy flag is set; contains no actual private data |

Use these files only to demonstrate system behavior. An authorized human must verify live evidence and approve any real operational decision.

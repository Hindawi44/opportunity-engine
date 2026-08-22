# Creative V2 question-ID repair invariant

- Model-supplied valid internal question IDs are preserved.
- Unknown IDs are never accepted as provenance.
- If all supplied IDs are unknown, the idea is deterministically linked to the closest real internal question by lexical overlap.
- `apply_open_payload` still performs a strict final subset validation against the actual internal-question universe.
- The repair is local and deterministic and does not make a second model/API request.

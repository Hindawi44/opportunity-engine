from __future__ import annotations

import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"patch target missing: {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


orchestrator = root / "mind_forge" / "orchestrator.py"
text = orchestrator.read_text(encoding="utf-8")
needle = "def validate_council_contract(ideas: IdeaSet, council: CouncilReport, critique: CrossCritique) -> None:\n"
insert = '''def normalize_cross_critique_idea_references(ideas: IdeaSet, critique: CrossCritique) -> CrossCritique:\n    \"\"\"Normalize verbose critique entries back to exact generated idea titles.\n\n    Structured-output models can occasionally place explanatory prose in the\n    *_ideas fields even when the prompt asks for exact titles. We only recover\n    an idea when its exact canonical title appears in the prose; we never use\n    fuzzy matching or invent a title. The original prose is preserved in\n    conflicts so later adversarial/evidence stages retain the observation.\n    \"\"\"\n    title_by_key = {_canonical(idea.title): idea.title for idea in ideas.ideas}\n    recovered_notes: list[str] = []\n\n    def normalize(entries: list[str]) -> list[str]:\n        normalized: list[str] = []\n        seen: set[str] = set()\n        for entry in entries:\n            entry_key = _canonical(entry)\n            matched_keys: list[str]\n            if entry_key in title_by_key:\n                matched_keys = [entry_key]\n            else:\n                matched_keys = [key for key in title_by_key if key and key in entry_key]\n                recovered_notes.append(entry)\n\n            for key in matched_keys:\n                if key not in seen:\n                    normalized.append(title_by_key[key])\n                    seen.add(key)\n        return normalized\n\n    consensus = normalize(critique.consensus_ideas)\n    disputed = normalize(critique.disputed_ideas)\n    disputed_keys = {_canonical(title) for title in disputed}\n    consensus = [title for title in consensus if _canonical(title) not in disputed_keys]\n\n    conflicts = list(critique.conflicts)\n    for note in recovered_notes:\n        preserved = f\"Normalized critique observation: {note}\"\n        if preserved not in conflicts:\n            conflicts.append(preserved)\n\n    return critique.model_copy(\n        update={\n            \"consensus_ideas\": consensus,\n            \"disputed_ideas\": disputed,\n            \"conflicts\": conflicts,\n        }\n    )\n\n\n'''
if insert not in text:
    if needle not in text:
        raise SystemExit("orchestrator contract target missing")
    text = text.replace(needle, insert + needle, 1)
old = "            critique: CrossCritique = critiqued.final_output\n        else:\n"
new = "            critique: CrossCritique = normalize_cross_critique_idea_references(ideas, critiqued.final_output)\n        else:\n"
if old not in text:
    raise SystemExit("orchestrator critique assignment target missing")
text = text.replace(old, new, 1)
orchestrator.write_text(text, encoding="utf-8")

replace_once(
    root / "mind_forge" / "agents.py",
    '        "Compare the ten independent expert reviews. Identify real consensus, genuine disagreements, hidden assumptions, "\n        "and missing evidence. Do not use majority vote as proof. Refer only to supplied candidate idea titles. "\n        "Synthesize what survives the criticism without inventing a new candidate idea."\n',
    '        "Compare the ten independent expert reviews. Identify real consensus, genuine disagreements, hidden assumptions, "\n        "and missing evidence. Do not use majority vote as proof. Refer only to supplied candidate idea titles. "\n        "The consensus_ideas and disputed_ideas fields MUST contain only exact candidate idea titles, never explanatory prose. "\n        "Put explanatory sentences only in conflicts, challenged_assumptions, missing_evidence, or synthesis. "\n        "Synthesize what survives the criticism without inventing a new candidate idea."\n',
)

replace_once(
    root / "mind_forge" / "schemas.py",
    'class CrossCritique(BaseModel):\n    consensus_ideas: list[str] = Field(default_factory=list)\n    disputed_ideas: list[str] = Field(default_factory=list)\n',
    'class CrossCritique(BaseModel):\n    consensus_ideas: list[str] = Field(\n        default_factory=list,\n        description="Exact generated candidate idea titles only; no explanatory prose.",\n    )\n    disputed_ideas: list[str] = Field(\n        default_factory=list,\n        description="Exact generated candidate idea titles only; no explanatory prose.",\n    )\n',
)

print("mind_forge_live_patch=v1.9.1")

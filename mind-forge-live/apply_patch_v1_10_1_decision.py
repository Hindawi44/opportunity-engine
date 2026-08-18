from __future__ import annotations

import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()

orch = root / "mind_forge" / "orchestrator.py"
text = orch.read_text(encoding="utf-8")

needle = "def validate_pipeline_contract(ideas: IdeaSet, logic: LogicReview, decision: Decision) -> None:\n"
insert = '''def normalize_decision_against_logic(ideas: IdeaSet, logic: LogicReview, decision: Decision) -> Decision:\n    \"\"\"Fail closed when the decision model makes a non-survivor actionable.\n\n    Preserve the selected idea and score, but downgrade an actionable verdict to\n    HOLD when Logic Review did not classify that idea as a survivor. Never switch\n    to a different idea automatically.\n    \"\"\"\n    idea_by_key = {_canonical(idea.title): idea.title for idea in ideas.ideas}\n    score_by_key = {_canonical(card.idea_title): card for card in logic.scorecards}\n    selected_key = _canonical(decision.selected_idea)\n\n    if selected_key not in idea_by_key:\n        matches = [key for key in idea_by_key if key and key in selected_key]\n        if len(matches) == 1:\n            selected_key = matches[0]\n            decision = decision.model_copy(update={\n                \"selected_idea\": idea_by_key[selected_key],\n                \"score\": score_by_key[selected_key].total,\n            })\n\n    actionable = {Verdict.PROMOTE, Verdict.TEST, Verdict.MODIFY}\n    survivor_keys = {_canonical(name) for name in logic.survivors}\n    if decision.verdict in actionable and selected_key in idea_by_key and selected_key not in survivor_keys:\n        note = (\n            \"Guardrail downgrade: the selected idea did not survive Logic Review, \"\n            \"so an actionable verdict was downgraded to HOLD.\"\n        )\n        rationale = list(decision.rationale)\n        if note not in rationale:\n            rationale.append(note)\n        decision = decision.model_copy(update={\"verdict\": Verdict.HOLD, \"rationale\": rationale})\n\n    return decision\n\n\n'''
if "def normalize_decision_against_logic" not in text:
    if needle not in text:
        raise SystemExit("decision normalization insertion target missing")
    text = text.replace(needle, insert + needle, 1)

old = "        decision: Decision = judged.final_output\n\n        validate_pipeline_contract(ideas, logic, decision)\n"
new = "        decision: Decision = normalize_decision_against_logic(ideas, logic, judged.final_output)\n\n        validate_pipeline_contract(ideas, logic, decision)\n"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("decision assignment target missing")

old_prompt = '''            + "\\n\\nChoose the best next action. Do not invent a new idea. "\n            "The decision score must exactly match the selected idea's logic scorecard total."\n'''
new_prompt = '''            + "\\n\\nChoose the best next action. Do not invent a new idea. "\n            "The decision score must exactly match the selected idea's logic scorecard total. "\n            "PROMOTE, TEST, or MODIFY may select only an idea listed in Logic Review survivors. "\n            "If the best candidate is in holds or rejects, use HOLD or REJECT rather than overriding Logic Review."\n'''
if old_prompt in text:
    text = text.replace(old_prompt, new_prompt, 1)
elif new_prompt not in text:
    raise SystemExit("decision runtime prompt target missing")
orch.write_text(text, encoding="utf-8")

agents = root / "mind_forge" / "agents.py"
a = agents.read_text(encoding="utf-8")
old_agent = '''        "You are a decision judge, not an idea generator. Select only from the reviewed ideas. "\n        "Use logic scores, expert disagreement, evidence quality, economics, feasibility, risk, and reversibility. "\n        "Consensus is not evidence. Prefer TEST when evidence is incomplete. Provide an explicit experiment and stop conditions."\n'''
new_agent = '''        "You are a decision judge, not an idea generator. Select only from the reviewed ideas. "\n        "Use logic scores, expert disagreement, evidence quality, economics, feasibility, risk, and reversibility. "\n        "PROMOTE, TEST, and MODIFY may select only an idea explicitly listed in Logic Review survivors. "\n        "If your preferred idea is in holds or rejects, return HOLD or REJECT rather than overriding the Logic Engine bucket. "\n        "Consensus is not evidence. Prefer TEST when evidence is incomplete. Provide an explicit experiment and stop conditions."\n'''
if old_agent in a:
    a = a.replace(old_agent, new_agent, 1)
elif new_agent not in a:
    raise SystemExit("decision agent prompt target missing")
agents.write_text(a, encoding="utf-8")

print("mind_forge_live_patch=v1.10.1-decision-contract")

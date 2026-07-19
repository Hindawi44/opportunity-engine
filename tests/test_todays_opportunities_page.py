import ast
from pathlib import Path


def test_todays_opportunities_page_is_valid_and_contains_decision_fields() -> None:
    path = Path("pages/Todays_Opportunities.py")
    source = path.read_text(encoding="utf-8")

    ast.parse(source)
    for marker in (
        "فرص اليوم",
        "الربح المتوقع NOK",
        "ROI %",
        "الحد الأقصى للمزايدة NOK",
        "فتح الإعلان الأصلي",
        "todays_opportunities.json",
    ):
        assert marker in source

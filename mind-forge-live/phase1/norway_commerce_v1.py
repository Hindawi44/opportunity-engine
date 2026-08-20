from __future__ import annotations

from dataclasses import dataclass


NORWAY_MARKERS = (
    "norway",
    "norge",
    "norsk",
    "النرويج",
    "النرويجي",
    "النرويجية",
)

COMMERCE_MARKERS = (
    "تجارة",
    "تجاره",
    "بيع",
    "شراء",
    "استيراد",
    "تصدير",
    "مخزون",
    "ستوك",
    "stock",
    "stocklot",
    "liquidation",
    "تصفية",
    "مزاد",
    "مزادات",
    "سيارات",
    "سيارة",
    "أقمشة",
    "اقمشة",
    "ملابس",
    "أثاث",
    "اثاث",
    "معدات",
    "قطع غيار",
    "ماكينات",
    "آلات",
    "الات",
    "wholesale",
    "resale",
    "resell",
    "trade",
    "trading",
    "import",
    "export",
    "inventory",
    "auction",
    "auctions",
    "cars",
    "vehicles",
    "furniture",
    "machinery",
    "equipment",
    "parts",
    "handel",
    "kjøp",
    "kjop",
    "salg",
    "importere",
    "eksportere",
    "lager",
    "vareparti",
    "konkursbo",
    "auksjon",
    "biler",
    "maskiner",
    "utstyr",
    "reservedeler",
)


NORWAY_COMMERCE_RESEARCH_TEMPLATES = (
    (
        "norway demand and turnover",
        "Current Norwegian demand and realistic sales velocity for {seed} are strong enough to justify testing the opportunity.",
        "A trade opportunity is only useful if goods can actually move in Norway. Verify demand, transaction activity, turnover proxies, and buyer interest in the Norwegian market.",
        ["Norwegian marketplace data", "official Norwegian statistics", "direct seller/buyer evidence", "credible Norwegian public source"],
    ),
    (
        "sourcing and acquisition",
        "There are repeatable sourcing channels for {seed} at acquisition prices that leave room for resale profit in Norway.",
        "The opportunity depends on buying well before selling well. Verify liquidation, auction, wholesaler, importer, surplus, and direct-owner acquisition routes.",
        ["direct supplier or auction source", "liquidation/insolvency source", "wholesale offer", "primary commercial source"],
    ),
    (
        "norway resale pricing and margin",
        "Observed Norwegian resale prices for {seed} leave a practical gross-margin buffer after acquisition, transport, tax, fees, repairs, and selling costs.",
        "Revenue without margin is not an opportunity. Compare real Norwegian asking/sold prices with the full landed and resale cost stack.",
        ["Norwegian marketplace listing", "direct dealer price", "auction result", "official fee/tax source"],
    ),
    (
        "competition and sales channels",
        "Competition and available sales channels for {seed} in Norway still leave a reachable buyer segment and a workable route to market.",
        "A profitable item can still fail if channels are saturated or buyers are expensive to reach. Verify competitors, marketplaces, dealers, B2B channels, and geographic coverage.",
        ["Norwegian marketplace", "direct competitor", "dealer/business directory", "credible market source"],
    ),
    (
        "norway rules taxes and logistics",
        "Norwegian taxes, VAT, registration, product rules, transport, storage, and import obligations for {seed} are compatible with the intended business model.",
        "Regulatory or logistics friction can erase the margin. Verify the exact Norwegian obligations and the realistic movement/storage path before commitment.",
        ["Norwegian government source", "official regulator", "customs/tax authority", "direct logistics source"],
    ),
    (
        "risk and execution test",
        "The main inventory, condition, fraud, liquidity, warranty, capital-lockup, and execution risks for {seed} can be bounded with a small measurable pilot in Norway.",
        "MIND FORGE should not scale an untested trade thesis. Define the smallest purchase/resale experiment that can falsify demand, margin, and operational assumptions.",
        ["primary transaction evidence", "marketplace history", "official risk guidance", "direct operational evidence"],
    ),
)


IDEA_BOX_SEEDS = (
    "شراء وبيع سيارات مستعملة بهامش إعادة بيع في النرويج",
    "شراء مخزون تصفية ملابس وإعادة بيعه داخل النرويج",
    "شراء أقمشة stocklot بالجملة وإعادة بيعها للمحلات والخياطين في النرويج",
    "شراء أثاث مستعمل من الشركات والمنازل وإعادة بيعه في النرويج",
    "شراء معدات ورش مستعملة وإعادة بيعها في السوق النرويجي",
    "شراء ماكينات خياطة صناعية مستعملة وإعادة بيعها في النرويج",
    "تجارة قطع غيار سيارات مستعملة ومجددة في النرويج",
    "شراء بضائع liquidation من المزادات وإعادة بيعها في النرويج",
    "شراء مخزون شركات مغلقة أو konkursbo وإعادة بيعه في النرويج",
    "تجارة أدوات ومعدات المطاعم المستعملة في النرويج",
    "تجارة معدات البناء الخفيفة المستعملة في النرويج",
    "تجارة الدراجات الكهربائية والمستعملة في النرويج",
    "تجارة إطارات وجنوط السيارات المستعملة في النرويج",
    "شراء وبيع القوارب الصغيرة ومعداتها المستعملة في النرويج",
    "تجارة معدات المكاتب المستعملة من تصفيات الشركات في النرويج",
    "تجارة أجهزة وأدوات التنظيف المهنية المستعملة في النرويج",
    "شراء مخزون أحذية وملابس عمل وإعادة بيعه في النرويج",
    "تجارة معدات الحدائق والثلج المستعملة في النرويج",
    "شراء أدوات كهربائية مستعملة من المزادات وإعادة بيعها في النرويج",
    "تجارة رفوف وتجهيزات المحلات المستعملة في النرويج",
)


COMMERCE_SEMANTIC_MARKERS = {
    "norway demand and turnover": (
        "demand", "sales", "sold", "turnover", "buyer", "buyers", "transactions",
        "etterspørsel", "salg", "solgt", "omsetning", "kjøper", "kjøpere",
    ),
    "sourcing and acquisition": (
        "supplier", "auction", "liquidation", "wholesale", "surplus", "inventory", "stock",
        "leverandør", "auksjon", "konkursbo", "vareparti", "lager", "parti",
    ),
    "norway resale pricing and margin": (
        "price", "prices", "margin", "cost", "fee", "fees", "nok", "kr", "kroner",
        "pris", "priser", "kostnad", "kostnader", "gebyr", "fortjeneste", "dekningsbidrag",
    ),
    "competition and sales channels": (
        "competitor", "competition", "marketplace", "dealer", "channel", "listing",
        "konkurrent", "konkurranse", "markedsplass", "forhandler", "kanal", "annonse",
    ),
    "norway rules taxes and logistics": (
        "vat", "tax", "customs", "registration", "transport", "storage", "import", "rule", "rules",
        "mva", "avgift", "skatt", "toll", "registrering", "transport", "lager", "import", "regel", "regler",
    ),
    "risk and execution test": (
        "risk", "fraud", "condition", "warranty", "pilot", "test", "liquidity", "inventory",
        "risiko", "svindel", "tilstand", "garanti", "pilot", "test", "likviditet", "lager",
    ),
}

NORWAY_EVIDENCE_REQUIRED_LABELS = frozenset(
    {
        "norway demand and turnover",
        "norway resale pricing and margin",
        "competition and sales channels",
        "norway rules taxes and logistics",
    }
)


def is_norway_seed(seed: str) -> bool:
    text = seed.casefold()
    return any(marker.casefold() in text for marker in NORWAY_MARKERS)


def is_norway_commerce_seed(seed: str) -> bool:
    text = seed.casefold()
    return is_norway_seed(seed) and any(
        marker.casefold() in text for marker in COMMERCE_MARKERS
    )


def norway_commerce_templates():
    return NORWAY_COMMERCE_RESEARCH_TEMPLATES


def norway_commerce_idea_box(*, limit: int = 20) -> list[str]:
    if limit < 1:
        return []
    return list(IDEA_BOX_SEEDS[: min(limit, len(IDEA_BOX_SEEDS))])

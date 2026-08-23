# Opportunity Engine

منصة تشغيلية محافظة لاكتشاف فرص مخزون الملابس وإشارات التصفية والمزادات والإفلاس/الإغلاق، توحيد الأدلة، تحليل الفرص المؤهلة، وإصدار نتيجة تحتاج دائمًا إلى مراجعة بشرية.

## الحالة الحالية

يوجد فرق مقصود بين **أسواق الفرص الأساسية** و**الروافد التجارية المساندة**.

## حد المجال التجاري الملزم

`PROJECT_DOMAIN_BOUNDARY_V1` هو بوابة المجال الحاكمة قبل التعلم أو الترويج أو التأهيل التجاري.

المجال المسموح فقط هو:

```text
CLOTHING_INVENTORY
FABRIC_PROCUREMENT
```

بالمعنى التالي:

- `CLOTHING_INVENTORY`: مخزون الملابس/الموضة/الألبسة/الأحذية وملابس الزفاف عندما تكون جزءًا من فرصة مخزون أو تصفية تجارية؛
- `FABRIC_PROCUREMENT`: الأقمشة والمنسوجات داخل مسار الشراء المحدود الموجود أصلًا.

أي بضائع أخرى مثل مواد البناء، الأجهزة، الإلكترونيات، الأثاث أو `general merchandise` هي:

```text
OUT_OF_DOMAIN
```

الكلمات العامة مثل `stock` أو `liquidation` أو `lot` أو `price` لا تكفي وحدها لإثبات أن السجل داخل مجال المشروع. عند غياب دليل إيجابي على الملابس أو الأقمشة يفشل التصنيف مغلقًا إلى `OUT_OF_DOMAIN`.

تُطبق هذه الحدود قبل:

1. قبول أمثلة خارجية في `Source Learning`؛
2. خروج مرشح Production من مصدر واسع مروّج؛
3. خروج فرصة من `Promoted Learned Core`؛
4. تصنيف صفحة Exa كـ exact-lot candidate.

الترقيات التي فقدت إثباتها داخل المجال تبقى معطلة حتى إعادة إثباتها على بيانات ملابس مستقلة:

```text
Stocklear Production — DISABLED
avviklingssalg Production promotion — DISABLED
```

المرجع:

```text
docs/PROJECT_DOMAIN_BOUNDARY_V1.md
```

### أسواق الفرص الأساسية

```text
NO — النرويج
SE — السويد
DE — ألمانيا
```

هذه هي الأسواق التي تحمل نطاق فرص `CLOTHING_INVENTORY` الأساسي. اكتمال بنية الدولة لا يعني أن كل مصدر داخلها `ACTIVE`، ولا يعني وجود فرصة شراء نشطة اليوم.

### الظهور اليومي الموسع

التقرير اليومي يعرض حاليًا:

```text
NO | SE | DE | IT
```

لكن إيطاليا لها دور مختلف:

```text
IT — FABRIC_PROCUREMENT
```

أي أنها **رافد شراء أقمشة** داخل الاستخبارات الموحدة، وليست سوق تصفيات رابعًا ولا تدخل تلقائيًا في `Top 5` لفرص المخزون.

## البنية الحالية

```text
NO / SE / DE discovery
        +
market / closure / insolvency signals
        +
bridal + bounded B2B intelligence
        +
IT fabric procurement
        ↓
UNIFIED MARKET INTELLIGENCE RIVER
        ↓
linked intelligence items / market cases
        ↓
daily decision brief
        ↓
human review
```

السجلات لا تُجبر على أن تكون كلها فرصًا. النهر الموحد يحافظ على أنواع مستقلة مثل:

```text
MARKET_SIGNAL
BUSINESS_EVENT_SIGNAL
B2B_STOCK_OFFER
AUCTION_LOT
BRIDAL_LIQUIDATION_SIGNAL
FABRIC_PROCUREMENT_ITEM
CANONICAL_OPPORTUNITY
HISTORICAL_EVIDENCE
```

لكن وجود سجل في نهر الاستخبارات لا يمنحه حق التأهل التجاري إذا كان خارج `PROJECT_DOMAIN_BOUNDARY_V1`.

## Discovery وAnalysis

### Discovery Engine

مسؤول عن:

- البحث حسب السيناريو التجاري؛
- جمع الصفحات العامة والأدلة؛
- التحقق من الهوية والحالة؛
- إزالة التكرار؛
- حفظ البيانات الناقصة كقيم مجهولة؛
- إنتاج سجل موحد قابل للتتبع.

### Analysis Engine

مسؤول عن:

- المقارنات السوقية الموثقة؛
- تكلفة الشراء والنقل والرسوم عند وجود أدلة؛
- التقييم الاقتصادي؛
- الترتيب؛
- تقرير المراجعة البشرية.

لا يحسب Discovery ربحًا غير موثق، ولا يحول Analysis إشارة غير مؤكدة إلى شراء.

## AI Fabric Procurement Advisor

مسار الأقمشة يعمل داخل نفس النظام ولا ينشئ محركًا منفصلًا:

```text
FABRIC PROCUREMENT WATCH
→ OPENAI FABRIC PROCUREMENT ADVISOR
→ UNIFIED MARKET INTELLIGENCE RIVER
```

الـAI يستطيع:

- تحليل حتى 7 موردين بحد أقصى، واحد لكل مورد؛
- استخدام طلب OpenAI واحد فقط في التشغيل المؤهل؛
- ترتيب المراجعة `HIGH / MEDIUM / LOW`؛
- تلخيص الحقائق الموجودة في الأدلة؛
- تحديد ما ينقص قبل الشراء: السعر، `MOQ`، الكمية، التركيب، العرض، VAT، المهلة، والشحن/اللوجستيات إلى النرويج.

ولا يستطيع:

- اختراع بيانات تجارية ناقصة؛
- الترويج التلقائي إلى Opportunity Top 5؛
- التواصل أو الحجز أو الشراء أو الدفع تلقائيًا.

المرجع:

```text
docs/OPENAI_FABRIC_PROCUREMENT_ADVISOR_V1.md
```

## Multi-Market Daily Operator Checkpoint

المسار `MULTI_MARKET_DAILY_OPERATOR_CHECKPOINT` منفذ ومندمج بالفعل، ويعمل كجزء من التشغيل اليومي الموحد. لا يُعاد اعتباره مرحلة غير منفذة.

الـworkflow الحالي مجدول يوميًا ويمكن تشغيله يدويًا أيضًا:

```text
.github/workflows/multi-market-daily-operator-checkpoint.yaml
```

## التشغيل من GitHub Actions

سطح التشغيل الحالي مبسط إلى خمسة workflows فقط:

```text
germany-clothing-inventory-live.yaml
multi-market-daily-operator-checkpoint.yaml
one-opportunity-commercial-analysis.yaml
sweden-clothing-inventory-live.yaml
tests.yml
```

ملفات تدقيق الـworkflows القديمة داخل `docs/` هي سجلات تاريخية ولا تمثل العدد التشغيلي الحالي.

## التشغيل المحلي

### Pipeline الآلي الكامل

```bash
python scripts/run_v2_3_automated_pipeline.py
```

### لوحة التشغيل

```bash
streamlit run pages/Operational_Dashboard.py
```

### الاختبارات

```bash
pytest -v
```

## المراجع التشغيلية

- `docs/00_PROJECT_STATUS.md`: الحالة الحالية المختصرة والمرجع الأول للجلسة.
- `docs/PROJECT_DOMAIN_BOUNDARY_V1.md`: حد المجال التجاري الملزم قبل التعلم والترويج والتأهيل.
- `config/market_completion_matrix.json`: حالة اكتمال الدول وتنفيذ المصادر والمراقبات.
- `config/source_expansion_plan.json`: خطة المصادر وحالات التنفيذ والتفعيل.
- `data/source_gap_matrix.json`: لقطة حالات المصادر التشغيلية.
- `data/decision_intelligence.json`: القرارات الرسمية.
- `data/action_queue.json`: مركز الإجراءات.
- `data/follow_up_status.json`: حالات المتابعة.
- `data/discovery_health.json`: صحة المراحل والمصادر.
- `data/source_funnel.json`: التغطية الفعلية لكل مصدر.
- `docs/UNIFIED_MARKET_INTELLIGENCE_RIVER_V1.md`: النهر الموحد وربط الحالات.

## معنى حالات المصادر

- `ACTIVE`: مصدر مفعّل وله دليل تشغيل معتمد.
- `CODE_READY`: الكود جاهز لكن التفعيل أو الإعداد لم يكتمل.
- `BLOCKED_AUTH`: يحتاج API أو Feed أو إذنًا رسميًا.
- `PLANNED`: المصدر غير مفعّل تشغيليًا؛ يجب قراءة `implementation_status` أيضًا.
- `DEPRECATED`: مصدر أُخرج من الخطة بقرار موثق.

حالة التنفيذ المنفصلة:

```text
NOT_IMPLEMENTED
BOUNDED_PILOT_IMPLEMENTED
DAILY_WATCH_IMPLEMENTED
ACTIVE_IMPLEMENTATION
```

## قواعد القرار والأمان

- `final_decision` هو القرار الرسمي الوحيد.
- `BUY_REVIEW` يحتاج مراجعة بشرية ولا يعني شراءً تلقائيًا.
- الأدلة الناقصة تبقى مجهولة ولا تُستبدل بتقديرات مصطنعة.
- لا يتم اختراع سعر أو كمية أو ضريبة أو نقل أو ربح أو ROI.
- فشل المصدر لا يُسجل على أنه صفر فرص.
- نتيجة الصفر الصحيحة ليست فشلًا.
- لا يوجد شراء أو مزايدة أو تواصل أو دفع تلقائي.
- لا تُشغّل المسارات المقيدة دون إذن رسمي.
- لا يُسمح لـSource Learning أو Query Learning أن يتعلما من `OUT_OF_DOMAIN`.
- لا تعاد أي ترقية Production معطلة إلا بعد إعادة إثباتها داخل المجال المسموح وبقرار صريح.

## أولوية التطوير الآن

لا نعيد بناء ما تم إنجازه ولا نضيف أداة أو دولة لمجرد أنها متاحة.

الأولوية هي حماية دقة المجال ثم جعل الموجود يعمل كمنظومة واحدة أكثر ذكاءً:

```text
حماية PROJECT_DOMAIN_BOUNDARY_V1
→ جمع الأدلة الموجودة داخل المجال فقط
→ ربط الإشارات المتصلة
→ قرار يومي مركزي أوضح
→ تحقق تجاري لأفضل المرشحين
→ إجراء بشري واحد مفيد
```

أي توسع في مصدر أو أداة أو تعلم يجب أن يثبت أولًا أنه يخدم `CLOTHING_INVENTORY` أو `FABRIC_PROCUREMENT` بدل تحويل المشروع إلى محرك تصفيات عام.

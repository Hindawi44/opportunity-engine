# Opportunity Engine

منصة تشغيلية محافظة لاكتشاف فرص مخزون الملابس في المزادات والتصفية، توحيد بياناتها، حفظ الأدلة، تحليل الفرص المؤهلة، وإصدار نتيجة تحتاج دائمًا إلى مراجعة بشرية.

## النطاق الحالي

الدومين الوحيد المعتمد هو:

```text
CLOTHING_INVENTORY
```

الأسواق التي اكتملت بنيتها الأساسية:

```text
النرويج NO
السويد SE
ألمانيا DE
```

اكتمال بنية الدولة لا يعني أن كل مصدر داخلها `ACTIVE`، ولا يعني وجود فرصة شراء نشطة اليوم. حالة الدولة، تنفيذ المصدر، تشغيل المراقبة، تفعيل المصدر، ووجود فرصة حالية هي حالات منفصلة.

المرجع الرسمي:

```text
config/market_completion_matrix.json
docs/MARKET_COMPLETION_MATRIX_v1.0.md
```

## الحالة الحالية حسب الدولة

### النرويج

- ملف السوق: `NO_DOMESTIC_V1`
- العملة: `NOK`
- النطاق: محلي
- البنية الأساسية: `COMPLETE`
- المصادر النشطة: `Auksjonen.no` و`Konkurs.app` و`Politiet.no`
- `FINN.no` و`Konkurskupp` و`Bjarøy`: تحتاج وصولًا رسميًا أو Feed مصرحًا
- لا يعاد بناء السوق النرويجي من البداية

### السويد

- ملف السوق: `SE_CROSS_BORDER_V1`
- العملة: `SEK`
- النطاق: استيراد إلى النرويج
- البنية الأساسية: `COMPLETE`
- توجد مسارات محدودة لـ`Blinto` و`Klaravik` و`PS Auction`
- نجح تشغيل Blinto وحفظ السجلات التاريخية في SQLite دون أخطاء تحويل
- عدم وجود فرصة نشطة في آخر تشغيل لا يعني فشل السوق أو الحاجة إلى إعادة بنائه

### ألمانيا

- ملف السوق: `DE_CROSS_BORDER_V1`
- العملة: `EUR`
- النطاق: استيراد إلى النرويج
- البنية الأساسية: `COMPLETE`
- `Riegermann`: مصدر `ACTIVE` ويعمل يوميًا الساعة `05:17 UTC`
- `VENTA`: مراقبة يومية الساعة `05:47 UTC` وتنتظر مزاد ملابس فعليًا
- `Deutsche Pfandverwertung`: مراقبة يومية الساعة `06:17 UTC` وتنتظر كتالوج ملابس نشطًا
- نتيجة الصفر الصحيحة مقبولة ولا تتحول إلى فرصة مصطنعة

## البنية التشغيلية

النظام يفصل بين محركين:

```text
Opportunity Map
  -> Discovery Engine
  -> Opportunity Dossier
  -> Analysis Engine
  -> Human Review
```

### Discovery Engine

مسؤول عن:

- البحث حسب السيناريو التجاري؛
- جمع الصفحات العامة؛
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

لا يقوم Discovery بحساب ربح غير موثق، ولا يقوم Analysis بتحويل Lead غير مؤكد إلى فرصة شراء.

## التشغيل من GitHub Actions

المساران الرئيسيان للمستخدم:

```text
1 — Discover Clothing Inventory Opportunities
2 — Review One Opportunity End to End
```

المسارات الجغرافية ومراقبات المصادر هي مسارات دعم إضافية، وليست بدائل عن المسارين الرئيسيين.

بوابة الاختبار الكاملة للمستودع:

```text
.github/workflows/tests.yml
```

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

## الملفات التشغيلية الرسمية

- `config/market_completion_matrix.json`: حالة اكتمال الدول وتنفيذ المصادر والمراقبات.
- `config/source_expansion_plan.json`: خطة المصادر وحالات التنفيذ والتفعيل.
- `data/source_gap_matrix.json`: لقطة حالات المصادر التشغيلية.
- `data/decision_intelligence.json`: القرارات الرسمية.
- `data/action_queue.json`: مركز الإجراءات.
- `data/follow_up_status.json`: حالات المتابعة.
- `data/discovery_health.json`: صحة المراحل والمصادر.
- `data/source_funnel.json`: التغطية الفعلية لكل مصدر.
- `data/smart_alerts_v2.json`: التنبيهات الذكية.
- `data/learning_history.json` و`data/learning_metrics.json`: التعلم الآمن.
- `data/automated_pipeline_status.json` و`data/automated_pipeline_history.json`: سجل التشغيل الآلي.

## معنى حالات المصادر

- `ACTIVE`: مصدر مفعّل وله دليل تشغيل معتمد.
- `CODE_READY`: الكود جاهز لكن التفعيل أو الإعداد لم يكتمل.
- `BLOCKED_AUTH`: يحتاج API أو Feed أو إذنًا رسميًا.
- `PLANNED`: المصدر غير مفعّل تشغيليًا؛ وقد يكون غير منفذ أو لديه Pilot أو مراقبة يومية، لذلك يجب قراءة `implementation_status` أيضًا.
- `DEPRECATED`: مصدر أُخرج من الخطة بقرار موثق.

حالة التنفيذ المنفصلة:

```text
NOT_IMPLEMENTED
BOUNDED_PILOT_IMPLEMENTED
DAILY_WATCH_IMPLEMENTED
ACTIVE_IMPLEMENTATION
```

## المرحلة التالية

التوسع بمصدر أو دولة جديدة متوقف مؤقتًا. المهمة التالية هي:

```text
MULTI_MARKET_DAILY_OPERATOR_CHECKPOINT
```

والهدف هو إنشاء تقرير واحد للـ`NO` و`SE` و`DE` يوضح ما تم البحث عنه، نجاح أو فشل كل مصدر، النتائج النشطة والتاريخية، وأفضل إجراء بشري واحد فقط.

مرجع المهمة:

```text
docs/MULTI_MARKET_DAILY_OPERATOR_CHECKPOINT_TASK_v1.0.md
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

## ملاحظة

هذه المنصة أداة دعم قرار محافظة. لا تستبدل فحص البضاعة، شروط المزاد، الضريبة، العمولة، النقل، التخزين، أو التحقق القانوني والمالي قبل أي التزام.

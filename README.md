# Opportunity Engine

منصة تشغيلية محافظة لاكتشاف فرص المزادات والتصفية في السوق النرويجي، توحيد بياناتها، جمع الأدلة، تقييم الجدوى، إصدار قرار بشري المراجعة، المتابعة، والتنبيه.

## الحالة الحالية

النظام يعمل عبر Pipeline موحد يشمل:

1. جمع المصادر وفحص التغطية.
2. التطبيع وإزالة التكرار.
3. تسجيل الفرص ومتابعة دورة حياتها.
4. جمع الأدلة السوقية والتكاليف.
5. التقييم الاقتصادي ومحرك النقاط الموحد.
6. قرار رسمي واحد عبر `final_decision`.
7. Action Center ومحرك المتابعة.
8. Learning Engine في وضع `OBSERVATION_ONLY`.
9. Operational Dashboard للهاتف.
10. Smart Alert Engine.
11. تشغيل آلي مجدول مع سجل تدقيق.

## المصادر

- `Auksjonen.no`: ACTIVE.
- `Konkurs.app`: ACTIVE كقناة إشارات إفلاس، وليس دليل بيع مباشر.
- `Politiet.no`: ACTIVE كقناة أحداث مزادات عامة.
- `FINN.no`: BLOCKED_AUTH حتى توفير الوصول الرسمي.
- `Konkurskupp` و`Bjarøy`: BLOCKED_AUTH حتى توفير Feed مصرح.
- بقية المصادر موثقة في `data/source_gap_matrix.json` كـ `PLANNED` أو `DEPRECATED` عند اتخاذ القرار بذلك.

## التشغيل

### Pipeline الآلي الكامل

```bash
python scripts/run_v2_3_automated_pipeline.py
```

كما يعمل تلقائيًا عبر GitHub Actions وفق الجدول المحدد في `.github/workflows/`.

### لوحة التشغيل

```bash
streamlit run pages/Operational_Dashboard.py
```

### الاختبارات

```bash
pytest -v
```

## الملفات التشغيلية الرسمية

- `data/decision_intelligence.json`: القرارات الرسمية.
- `data/action_queue.json`: مركز الإجراءات.
- `data/follow_up_status.json`: حالات المتابعة.
- `data/discovery_health.json`: صحة المراحل والمصادر.
- `data/source_funnel.json`: التغطية الفعلية لكل مصدر.
- `data/source_gap_matrix.json`: تصنيف فجوات المصادر.
- `data/smart_alerts_v2.json`: التنبيهات الذكية.
- `data/learning_history.json` و`data/learning_metrics.json`: التعلم الآمن.
- `data/automated_pipeline_status.json` و`data/automated_pipeline_history.json`: سجل التشغيل الآلي.

## قواعد القرار والأمان

- `final_decision` هو القرار الرسمي الوحيد.
- الأدلة الناقصة تبقي الفرصة في `WATCH` ولا تتحول إلى توصية شراء.
- التقييم الاقتصادي والترتيب يعملان فقط على البيانات المتاحة، مع إبقاء القرارات المحافظة عند نقص الأدلة.
- لا يتم اختراع سعر أو ربح أو ROI.
- لا يوجد شراء تلقائي.
- لا توجد مزايدة تلقائية.
- لا يوجد إرسال عروض أو تنفيذ مالي خارجي.
- جميع قرارات الشراء تحتاج مراجعة بشرية.

## تصنيف فجوات المصادر

يستخدم التقرير الرسمي الحالات التالية فقط:

- `ACTIVE`: مصدر مفعّل ويجمع بيانات دون خطأ.
- `CODE_READY`: التكامل البرمجي جاهز لكنه غير مفعّل.
- `BLOCKED_AUTH`: يحتاج API أو Feed رسميًا مصرحًا.
- `PLANNED`: مصدر معتمد للخطة ولم يُنفذ بعد.
- `DEPRECATED`: مصدر أُخرج من الخطة بقرار موثق.

## ملاحظة

هذه المنصة أداة دعم قرار محافظة. لا تستبدل فحص البضاعة، شروط المزاد، الضريبة، العمولة، النقل، الفك، التخزين، أو التحقق القانوني والمالي قبل أي التزام.

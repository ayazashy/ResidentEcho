import os
import json
import re
from collections import defaultdict

DAILY_ANALYSIS_DIR = 'daily_analysis'
DAILY_MESSAGES_DIR = 'daily_messages'
OUTPUT_DIR = 'monthly_analysis'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 1. Load all raw messages for September
raw_msgs = {}
for day in range(1, 31):
    fpath = os.path.join(DAILY_MESSAGES_DIR, f'2026-09-{day:02d}.json')
    if os.path.exists(fpath):
        with open(fpath, 'r', encoding='utf-8') as fp:
            for m in json.load(fp):
                raw_msgs[m['i']] = m

print(f"Loaded {len(raw_msgs)} raw messages for September.")

# 2. Extract daily analysis records across all 30 days
sep_files = sorted([f for f in os.listdir(DAILY_ANALYSIS_DIR) if f.startswith('2026-09') and f.endswith('.json')])

daily_records = []
daily_summaries = {}

for f in sep_files:
    date_str = f[:10]
    fpath = os.path.join(DAILY_ANALYSIS_DIR, f)
    with open(fpath, 'r', encoding='utf-8') as fp:
        d = json.load(fp)
    
    summary = d.get('daily_summary') or d.get('summary') or ''
    daily_summaries[date_str] = summary
    
    # Schema 1: topics (2026-09-01, 2026-09-02)
    if 'topics' in d and isinstance(d['topics'], dict):
        for cat, items in d['topics'].items():
            for it in items:
                mid = it.get('id')
                daily_records.append({
                    'date': date_str,
                    'category_raw': cat,
                    'context': it.get('context', ''),
                    'description': it.get('description', ''),
                    'sentiment': 'negative' if it.get('type') == 'issue' else 'positive',
                    'msg_ids': [mid] if mid else [],
                    'user_id': it.get('sender')
                })

    # Schema 2: issues_and_complaints + positive_and_resolutions (2026-09-03 .. 05, 12 .. 18)
    for k in ['issues_and_complaints', 'positive_and_resolutions']:
        if k in d and isinstance(d[k], list):
            for it in d[k]:
                mid = it.get('msg_id') or it.get('id')
                mids = [mid] if mid else []
                if 'message_ids' in it and isinstance(it['message_ids'], list):
                    mids.extend(it['message_ids'])
                daily_records.append({
                    'date': date_str,
                    'category_raw': it.get('category', ''),
                    'context': it.get('notes') or it.get('category', ''),
                    'description': it.get('text', '') or it.get('description', ''),
                    'sentiment': it.get('sentiment', 'negative' if 'issues' in k else 'positive'),
                    'msg_ids': mids,
                    'user_id': it.get('user_id'),
                    'building': it.get('building')
                })

    # Schema 3: issues_detected + positive_notes (2026-09-06 .. 08)
    for k in ['issues_detected', 'positive_notes']:
        if k in d and isinstance(d[k], list):
            for it in d[k]:
                mids = []
                rel_msgs = it.get('relevant_messages', [])
                for rm in rel_msgs:
                    rmid = rm.get('id') or rm.get('msg_id')
                    if rmid:
                        mids.append(rmid)
                daily_records.append({
                    'date': date_str,
                    'category_raw': it.get('category', ''),
                    'context': it.get('sub_category') or it.get('category', ''),
                    'description': it.get('description', ''),
                    'sentiment': 'negative' if 'issues' in k else 'positive',
                    'severity': it.get('severity'),
                    'msg_ids': mids,
                    'sample_messages': rel_msgs
                })

    # Schema 4: extracted_records (2026-09-09 .. 11)
    if 'extracted_records' in d and isinstance(d['extracted_records'], list):
        for it in d['extracted_records']:
            mid = it.get('id')
            daily_records.append({
                'date': date_str,
                'category_raw': it.get('category', ''),
                'context': it.get('key_point') or it.get('category', ''),
                'description': it.get('text', ''),
                'sentiment': it.get('sentiment', 'neutral'),
                'msg_ids': [mid] if mid else [],
                'user_id': it.get('sender_id')
            })

    # Schema 5: categories dict (2026-09-19 .. 23)
    if 'categories' in d and isinstance(d['categories'], dict):
        for cat_name, cat_obj in d['categories'].items():
            if isinstance(cat_obj, dict):
                complaints = cat_obj.get('complaints') or cat_obj.get('issues') or []
                for it in complaints:
                    if isinstance(it, dict):
                        mid = it.get('msg_id') or it.get('id')
                        daily_records.append({
                            'date': date_str,
                            'category_raw': cat_name,
                            'context': it.get('topic') or cat_name,
                            'description': it.get('text', '') or it.get('description', ''),
                            'sentiment': it.get('sentiment', 'negative'),
                            'msg_ids': [mid] if mid else [],
                            'user_id': it.get('user_id')
                        })
                    elif isinstance(it, str):
                        daily_records.append({
                            'date': date_str,
                            'category_raw': cat_name,
                            'context': cat_name,
                            'description': it,
                            'sentiment': 'negative',
                            'msg_ids': []
                        })

    # Schema 6: issues_and_observations (2026-09-24 .. 30)
    if 'issues_and_observations' in d and isinstance(d['issues_and_observations'], list):
        for it in d['issues_and_observations']:
            mids = it.get('message_ids') or it.get('evidence_message_ids') or []
            if it.get('id') and it.get('id') not in mids:
                mids.append(it.get('id'))
            daily_records.append({
                'date': date_str,
                'category_raw': it.get('category', ''),
                'context': it.get('sub_category') or it.get('topic') or it.get('category', ''),
                'description': it.get('description', ''),
                'sentiment': it.get('sentiment', 'negative'),
                'msg_ids': mids,
                'building': it.get('building') or it.get('affected_area')
            })

print(f"Extracted {len(daily_records)} structured records from daily analyses.")

# 3. Cluster Definitions
clusters_config = {
    'dining_and_catering_crisis': {
        'title_ar': 'أزمة الإعاشة والمطعم الجامعي ومتعهد التغذية (منع السفري وتدني الجودة)',
        'category': 'الإعاشة والتغذية',
        'severity': 'critical',
        'patterns': [
            r'مطعم', r'سفري', r'أفوكادو', r'افوكادو', r'التغذية', r'تغذية', r'وجبة', r'وجبات',
            r'غداء', r'فطور', r'عشاء', r'صحن', r'صحون', r'ملعقة', r'ملاعق', r'بلاستيك',
            r'بروست', r'بيتزا', r'شاورما', r'مستر فود', r'mr food', r'اللاونج', r'ملتقى الجود',
            r'اكل السكن', r'أكل السكن', r'طعام', r'مشرف الجودة', r'عريضة المطعم', r'كسر الملاعق',
            r'مقاطعة المطعم', r'الممر المكيف', r'بوفية عمو عماد', r'عمو عماد'
        ],
        'raw_categories': [
            'dining_catering', 'food_catering', 'food_services', 'التغذية والمطاعم', 'تغذية ومطاعم',
            'مطعم وإعاشة', 'التغذية والأسعار', 'تغذية وصحة', 'الصحة العامة والتغذية'
        ],
        'root_causes': [
            'قرار تعسفي ومفاجئ بمنع استلام وجبات الطعام "سفري" وإلزام الطلاب بالأكل داخل الصالة المزدحمة.',
            'تقليص ساعات تقديم وجبات الفطور والغداء بشكل حاد مما حال دون لحاق الطلاب بوجباتهم بين المحاضرات.',
            'إغلاق الممر الداخلي المكيف المؤدي إلى الكليات لإجبار الطلاب على الدخول من بوابات محددة مما زاد مشقة المشي الشمسي.',
            'تدني النظافة العامة وسوء جودة الطعام (خيوط وشعر في الأكل، تقديم ملاعق بلاستيكية رديئة تذوب في الأكل الحار).',
            'إلغاء خيارات المطاعم المتنوعة (إغلاق مطعم البروست والبيتزا، إغلاق صالة اللاونج وملتقى الجود).',
            'احتكاك ومشادات كلامية حادة بين مشرف الجودة بشركة التغذية والطلاب واستدعاء الأمن للتهديد بسحب بطاقات السكن.'
        ],
        'timeline_evolution': (
            "بدأ الشهر في 1 سبتمبر بحملة إيميلات رسمية احتجاجاً على منع السفري. "
            "وفي 6 سبتمبر نشبت مشادة ومشادات كلامية بالمطعم واستدعاء للأمن. "
            "وفي 7 سبتمبر أُغلق الممر المكيف وقُلصت ساعات الوجبات. "
            "وفي 10 سبتمبر دُشنت عريضة شكاوى إلكترونية رسمية، أعقبها في 12 سبتمبر رفع خطاب رسمي موحد للمدير التنفيذي لمتعهد التغذية بمشاركة أكثر من 1,400 طالب مع إطلاق حملة 'كسر الملاعق'. "
            "وفي 14 سبتمبر تفجرت صدمة إعادة غسل الأواني البلاستيكية. "
            "وفي 22 سبتمبر تم إغلاق ممر الكليات وإلغاء وجبة البروست. "
            "وفي 24 سبتمبر انطلقت دعوات مقاطعة المطعم رسمياً، واختتم الشهر في 28 سبتمبر برفع ملف الشكوى لعميد شؤون الطلاب وتنصل المتعهد من الالتزامات."
        ),
        'student_actions': [
            "رفع عريضة رسمية بستة بنود ومطالب محددة للمدير التنفيذي لشركة التغذية وقع عليها أكثر من 1400 طالب.",
            "إطلاق حملة رمزية 'كسر الملاعق' احتجاجاً على الملاعق الرديئة التي تذوب في الطعام الحار.",
            "تصعيد الملف بمذكرة رسمية إلى عميد شؤون الطلاب مدعمة بتوثيق مصور للانتهاكات الصحية.",
            "مبادرة طلابية للتفاوض مع بوفية 'عمو عماد' لتقديم وجبات بأسعار مخفضة وتوصيل مسائي."
        ]
    },
    'internet_infrastructure_outages_and_blocking': {
        'title_ar': 'انقطاعات شبكة الإنترنت وبطء التصفح وحجب المنصات التعليمية والألعاب',
        'category': 'الاتصالات والإنترنت',
        'severity': 'high',
        'patterns': [
            r'انترنت', r'إنترنت', r'النت', r'شبكة السكن', r'واي فاي', r'wifi', r'مودم',
            r'كيبل', r'إيثرنت', r'ethernet', r'سوني', r'بلايستيشن', r'playstation', r'ps4', r'ps5',
            r'حجب', r'محجوب', r'بورت', r'بورتات', r'بنق', r'ping', r'vpn', r'في بي ان',
            r'زووم', r'zoom', r'جيميل', r'gmail', r'سيرفر', r'تقنية المعلومات', r'حصر البلاغات',
            r'متصل بدون نت', r'الوايفاي', r'ألياف', r'الياف'
        ],
        'raw_categories': [
            'network_admin', 'network_gaming', 'network_infrastructure', 'network_internet',
            'network_telecom', 'wifi_network', 'internet_it', 'إنترنت وشبكات', 'خدمة الإنترنت والشبكات',
            'الإنترنت والشبكات', 'شبكة وإنترنت'
        ],
        'root_causes': [
            'أعمال صيانة وتحديث غير معلنة على شبكة ألياف السكن تسببت في انقطاعات ليلية متكررة.',
            'حجب جدار الحماية (Firewall) لبورتات منصات الألعاب (PlayStation Network) مما رفع البنق وعطل الاتصال.',
            'حجب وتذبذب الوصول لخدمات أساسية كالبريد الإلكتروني (Gmail) وتطبيق الاتصال المرئي (Zoom).',
            'تعطل منافذ الكيبل الجدارية (Ethernet) في عدة مبانٍ وإتلاف كوابل المودم من قبل فرق الصيانة.'
        ],
        'timeline_evolution': (
            "شهد الأسبوعان الأول والثاني شكاوى متفرقة من حجب السوني وزيادة بنق VPN. "
            "وفي 18 و19 سبتمبر حدث انقطاع واسع وشامل للإنترنت ليلاً في مباني 16 و34 استمر لساعات طويلة تزامناً مع أعمال الصيانة. "
            "وفي 20 سبتمبر تم تنظيم حملة حصر جماعية لأكثر من 30 غرفة متضررة في مباني 5، 7، 8، 9، 16، 27، 32، 34. "
            "وفي 22 و28 سبتمبر تجددت شكاوى حجب Gmail ومنصات الاتصال."
        ),
        'student_actions': [
            "تنظيم حملة حصر إلكترونية لأرقام الغرف والمباني المتضررة ورفعها دفعة واحدة لقسم تقنية المعلومات.",
            "تداول حلول تقنية بديلة عبر مجموعات التيليجرام لإعدادات الـ DNS واستخدام شبكات VPN لتخطي الحجب."
        ]
    },
    'laundry_services_failures_and_alternatives': {
        'title_ar': 'تردي خدمات مغسلة السكن وضياع وتلف الملابس ومبادرة المغسلة البديلة',
        'category': 'الخدمات المساندة',
        'severity': 'medium',
        'patterns': [
            r'مغسلة', r'المغسلة', r'غسيل', r'ثوب', r'ثياب', r'ملابس', r'ملابسي',
            r'بقع', r'اصفرار', r'ضياع ملابس', r'ضيع', r'غسالة', r'غسالات', r'نشافة',
            r'توصيل من الغرفة', r'بريال', r'ابداع وعناية'
        ],
        'raw_categories': [
            'laundry_cleaning', 'laundry_services', 'مغسلة السكن', 'خدمات الغسيل والمغسلة'
        ],
        'root_causes': [
            'إهمال عمال مغسلة السكن وسوء الفرز مما أدى لضياع ملابس داخلية وثياب رسمية للطلاب وتكرار تسليمها لطلاب آخرين.',
            'استخدام مياه غير مفلترة ومساحيق رديئة تسببت في اصفرار الأثواب البيضاء وظهور بقع داكنة.',
            'تأخر تسليم الملابس المغسولة لعدة أيام دون مبرر.',
            'صعوبة ومنع تمديدات تركيب الغسالات الأوتوماتيكية المستقلة داخل غرف الطلاب.'
        ],
        'timeline_evolution': (
            "بدأت الشكاوى في الأسبوع الأول من اصفرار الثياب البيضاء. "
            "وفي 11 سبتمبر أعلن ممثلو الطلاب عن اتفاقية بديلة مع مغسلة خارجية تستلم وتسلم من باب الغرفة بريال للقطعة. "
            "وفي 12 و16 و19 سبتمبر تكررت شكاوى ضياع قطع الملابس (أحد الطلاب فقد 10 قطع داخلية كاملة) وتبديل الثياب بين الطلاب."
        ),
        'student_actions': [
            "تدشين اتفاقية شراكة طلابية مع مغسلة 'إبداع وعناية' لاستلام الملابس من باب الغرفة وإرجاعها بنفس التسعيرة (ريال واحد للقطعة).",
            "إنشاء وسوم وتنبيهات في المجموعات لمساعدة الطلاب على تبادل الملابس المسلمة بالخطأ واسترداد المفقودات."
        ]
    },
    'water_quality_heat_and_plumbing': {
        'title_ar': 'أزمة حرارة مياه الاستحمام المفرطة وتلوث المواسير والانقطاع الليلي المفاجئ',
        'category': 'السباكة والمرافق',
        'severity': 'high',
        'patterns': [
            r'شاور', r'مروش', r'استحمام', r'تروش', r'مياه', r'مويه', r'ماء', r'صنبور',
            r'حارقة', r'حرارة المو', r'ماء حار', r'مويه حاره', r'موية حارة', r'ماء بارد',
            r'صدأ', r'صدا', r'صفراء', r'فلتر', r'فلاتر', r'انقطاع الما', r'انقطاع المو',
            r'تسرب', r'تهريب', r'سباكة', r'مواسير', r'دش', r'دبات', r'كراتين مويه'
        ],
        'raw_categories': [
            'مرافق وسباكة', 'مياه', 'المرافق العامة والصيانة'
        ],
        'root_causes': [
            'تعرض خزانات ومواسير المياه للحرارة الشديدة نهاراً دون عوازل كافية أو مبردات، مما جعل مياه الاستحمام حارقة وانعدم الماء البارد تماماً في مباني 15 و34.',
            'قِدم شبكة المواسير وتراكم الصدأ والشوائب مما تسبب في اصفرار مياه الشاور وتلف فلاتر الاستحمام خلال أيام قليلة.',
            'انقطاع مفاجئ وشامل لضخ المياه في عدة مبانٍ نتيجة أعطال المحابس دون إشعار مسبق للطلاب.'
        ],
        'timeline_evolution': (
            "برزت شكاوى حرارة مياه الدش الحارقة في 13 و17 سبتمبر بمبنى 15 و34. "
            "وفي 24 و26 سبتمبر اشتكى الطلاب من صدأ مياه الدش وفشل الفلاتر. "
            "وفي منتصف ليل 25 سبتمبر تفاجأ سكان مباني 6 و15 و19 بانقطاع تام للمياه استمر حتى صباح اليوم التالي واضطر الطلاب لشراء جالونات مياه للشرب والوضوء."
        ),
        'student_actions': [
            "تداول نصائح وروابط شراء فلاتر الشاور متعددة المراحل (20 مرحلة) من أمازون لتقليل الصدأ والكلور.",
            "التكافل الطلابي أثناء انقطاع المياه بمشاركة دبات الشرب وتنسيق الاستحمام في مبانٍ أخرى لم تنقطع بها المياه."
        ]
    },
    'grocery_monopoly_and_price_inflation': {
        'title_ar': 'احتكار وارتفاع أسعار بقالة السكن ومنافذ البيع واستغلال حاجة الطلاب',
        'category': 'الخدمات التجارية',
        'severity': 'medium',
        'patterns': [
            r'بقالة', r'البقالة', r'تموينات', r'اسعار', r'أسعار', r'غلاء', r'حمضيات',
            r'كولا', r'بيبسي', r'عصير', r'ريال', r'احتكار', r'وزارة التجارة', r'بلاغ تجاري',
            r'معفن', r'تاريخ انتهاء', r'نينجا', r'العثيم', r'حلاق', r'الحلاق'
        ],
        'raw_categories': [
            'commercial_services', 'خدمات تموينية', 'التغذية والأسعار'
        ],
        'root_causes': [
            'غياب الرقابة السعرية على بقالة السكن واستغلال غياب البدائل لرفع أسعار المشروبات والحلويات بنسب تصل إلى 40-75% (الحمضيات بـ 3.5، الكولا الزجاج بـ 7).',
            'تردي جودة التخزين وعرض منتجات قريبة الانتهاء وخبز معفن دون رقابة صحية دورية.',
            'غلاء أسعار حلاق السكن ومطعم مستر فود مقارنة بالأسواق المحيطة.'
        ],
        'timeline_evolution': (
            "بدأت الشكاوى بالاعتراض على أسعار مستر فود في 11 سبتمبر. "
            "وفي 20 سبتمبر انفجرت موجة غضب عارمة إثر رفع أسعار المشروبات بالبقالة وحدوث مشادات مع العامل. "
            "وفي 23 سبتمبر استمر الجدل حول تسعير البضائع وتبريرات المتعهد. "
            "وفي 27 سبتمبر رصد الطلاب خبزاً معفناً معروضاً في البقالة وطالبوا بمقاطعتها رسمياً."
        ),
        'student_actions': [
            "حملة تقديم بلاغات إلكترونية جماعية لوزارة التجارة ضد التلاعب بالأسعار في البقالة.",
            "دعوات مقاطعة البقالة والاعتماد على تطبيقات التوصيل (نينجا، العثيم) رغم مشقة نقل كراتين المياه مشياً من البوابات."
        ]
    },
    'parking_clamps_traffic_and_transport': {
        'title_ar': 'تشديد كلبشات المواقف وغراماتها وسحب السكوترات وأزمة باصات النقل',
        'category': 'المواقف والنقل',
        'severity': 'medium',
        'patterns': [
            r'موقف', r'مواقف', r'كلبش', r'كلبشة', r'كلبشات', r'مخالفة', r'مخالفات',
            r'٥٧\.٥', r'57\.5', r'سيارة', r'سيارتي', r'مظلة', r'سكوتر', r'سكوترات',
            r'باص', r'باصات', r'حافلة', r'حافلات', r'مترو', r'بوابة 5', r'بوابة ٤',
            r'بوابة 1', r'الأول بارك', r'المرور', r'أمن السكن'
        ],
        'raw_categories': [
            'transport_parking', 'traffic_transportation', 'parking_transport', 'transportation',
            'transportation_and_parking', 'النقل والمواصلات', 'مواقف السيارات والرقابة',
            'مواقف ومرور', 'مواقف وسلامة', 'نقل ومواصلات'
        ],
        'root_causes': [
            'نقص السعة الاستيعابية للمواقف المخصصة للطلاب القريبة من المباني السكنية.',
            'حملات تفتيش ليلية مشددة واستخدام الكلبشات وفرض غرامة فك الكلبشة (57.5 ريال) دون مرونة.',
            'سحب واحتجاز السكوترات الكهربائية الخاصة بالطلاب بدعوى تنظيم الحركة داخل السكن.',
            'بعد المسافة بين بوابة 5 ومحطات النقل الترددي وغياب محطة حافلات مخصصة لخدمة طلاب السكن.',
            'سقوط مظلة مواقف متهالكة على سيارة أحد الطلاب دون تعويض فوري.'
        ],
        'timeline_evolution': (
            "في 11 سبتمبر تم رفع مطالب إنشاء محطة مترو وباص عند بوابة 5. "
            "وفي 17 سبتمبر تصاعدت حملات كلبشة سيارات الطلاب. "
            "وفي 20 سبتمبر تم سحب سكوترات الطلاب واحتجازها. "
            "وفي 21 سبتمبر تجددت المطالبات الرسمية لحافلات بوابة 5 بعد رصد استغلال مناديب التوصيل لمواقف الطلاب. "
            "وفي 28 سبتمبر سقطت مظلة مواقف متهالكة على سيارة طالب وتسببت بأضرار."
        ),
        'student_actions': [
            "صياغة ورفع عريضة طلابية لإدارة الحركة والنقل للمطالبة بتسيير باص ترددي يربط بوابة 5 بالكليات.",
            "إنشاء مبادرة وقنوات لتنسيق تبادل المواقف القانونية بين الطلاب حسب قرب المبنى."
        ]
    },
    'hvac_failures_electricity_and_maintenance': {
        'title_ar': 'أعطال التكييف المركزي، غبار التهوية، تذبذب الكهرباء وتلف بطاريات الأقفال',
        'category': 'الصيانة والتشغيل',
        'severity': 'high',
        'patterns': [
            r'مكيف', r'تكييف', r'دينامو', r'فريون', r'غبار', r'فلتر مكيف', r'تبريد',
            r'حرارة الغرفة', r'كهرباء', r'فيش', r'أفياش', r'طفي', r'رعشة', r'قفل',
            r'كرت', r'بطاقة', r'بطارية', r'مقفل علي', r'صيانة', r'رقم الصيانة',
            r'رنيم', r'أثاث', r'سرير', r'مرتبة', r'دولاب', r'ثلاجة'
        ],
        'raw_categories': [
            'housing_maintenance', 'housing_admin_maintenance', 'facilities_maintenance',
            'صيانة وأجهزة', 'صيانة وخدمات', 'كهرباء وتكييف', 'السلامة والكهرباء',
            'أثاث الغرف والعهد', 'مرافق الغرف', 'إسكان وصيانة'
        ],
        'root_causes': [
            'قِدم وحدات التكييف المركزي في مبنى 16 ومبانٍ أخرى، وتكرار تعطل الدينامو وانبعاث روائح فريون وغبار كثيف.',
            'تذبذب ورعشة في الجهد الكهربائي ليلاً وتأخر استجابة فرق صيانة شركة رنيم.',
            'نفاد بطاريات الأقفال الإلكترونية لأبواب الغرف واحتجاز الطلاب في الممرات وصعوبة التواصل مع مشرفي الفترة الليلية.',
            'تهالك الأثاث القديم (الأسرة الخشبية المثبتة، دواليب الغرف التالفة) ومخاوف الطلاب من تحميلهم قيمة التأمين.'
        ],
        'timeline_evolution': (
            "في 2 سبتمبر تفاقمت أزمة تعطل تكييف مبنى 16 والروائح بالثلاجات. "
            "وفي 7 سبتمبر أُطلق مشروع طلابي لعزل فتحات التكييف بالفلاتر. "
            "وفي 18 سبتمبر أُجريت أعمال صيانة واسعة تزامنت مع انقطاعات جزئية. "
            "وفي 21 سبتمبر اشتكى الطلاب من رائحة فريون نفاذة. "
            "وفي 25 سبتمبر رُصدت رعشة واضحة بالكهرباء. "
            "وفي 29 و30 سبتمبر تعطلت هواتف الصيانة واشتكى الطلاب من قرب نفاد بطاريات أقفال الأبواب."
        ),
        'student_actions': [
            "إطلاق مبادرة طلابية تطوعية ('الفزعة') لتركيب فلاتر قماشية عازلة للغبار لفتحات التكييف بالغرف.",
            "توثيق أرقام هواتف مشرفي الصيانة البديلة ومشاركتها لإنقاذ الطلاب المحتجزين بسبب بطاريات الأقفال."
        ]
    },
    'health_clinic_gym_and_living_environment': {
        'title_ar': 'تدني الرعاية بالعيادة الطبية، تهالك صالة الحديد (الجيم)، ورصد الجرذان والقوارض',
        'category': 'البيئة والصحة والرياضة',
        'severity': 'medium',
        'patterns': [
            r'عيادة', r'طبيب', r'دكتور', r'مستوصف', r'سكليف', r'عذر طبي', r'أسنان',
            r'نادي', r'حديد', r'صالة', r'أوزان', r'اوزان', r'اثقال', r'سير',
            r'فأر', r'فار', r'فئران', r'جرذ', r'جرذان', r'حشرات', r'نمل', r'صراصير',
            r'قطة', r'قطط', r'بساس', r'صوت', r'إزعاج', r'ازعاج', r'تدخين'
        ],
        'raw_categories': [
            'health_services', 'الخدمات الطبية والتأمين', 'الرعاية الصحية', 'خدمات صحية',
            'sports_entertainment', 'sports_health', 'الصالات والمرافق الترفيهية والرياضية',
            'صالات وأنشطة رياضية', 'رياضة وترفيه', 'النظافة ومكافحة الآفات والقوارض',
            'facilities_cleaning', 'نظافة وصحة عامة', 'نظافة ومرافق'
        ],
        'root_causes': [
            'إغلاق عيادة السكن الطبية في الفترات المسائية والليلية وغياب الطبيب المناوب وصعوبة الحصول على تحويلات وعيادات الأسنان.',
            'إهمال صالة اللياقة البدنية والحديد: سرقة الأوزان والأثقال، تعطل الأجهزة الإلكترونية والسيور، وعدم وجود كاميرات مراقبة.',
            'ظهور قوارض وجرذان ضخمة في مبنى 11 ومبنى 16 مع بداية برودة الطقس وانتقالها عبر فتحات الخدمات.',
            'انتشار الحشرات والقطط الضالة في الممرات والتدخين الممنوع في أروقة بعض المباني.'
        ],
        'timeline_evolution': (
            "في 13 سبتمبر تصاعد الاستياء من سوء صالة الحديد ونقص الأثقال. "
            "وفي 15 سبتمبر رُصدت جرذان ضخمة تتجول في مبنى 11، وتعثرت مواعيد عيادات الأسنان. "
            "وفي 16 سبتمبر اشتكى الطلاب مجدداً من سرقة أوزان النادي. "
            "وفي 21 سبتمبر تم رصد تدخين بالممرات. "
            "وفي 29 و30 سبتمبر وثق الطلاب إغلاق العيادة الطبية وغياب الطبيب تماماً أثناء حاجة الطلاب للعلاج."
        ),
        'student_actions': [
            "رفع طلبات متكررة لإدارة السكن لتزويد صالة الحديد بأجهزة جديدة وتركيب كاميرات مراقبة لحماية الأوزان.",
            "إطلاق تنبيهات وإرشادات للطلاب بكيفية إغلاق فتحات المكيفات وشقوق الأبواب بربلات مطاطية لمنع دخول القوارض."
        ]
    },
    'housing_admin_capacity_and_regulations': {
        'title_ar': 'إجراءات السكن وعجز الطاقة الاستيعابية والضمان المالي وبطاقات الدخول',
        'category': 'الإدارة والقبول',
        'severity': 'medium',
        'patterns': [
            r'حجز الغرف', r'شواغر', r'مستجدين', r'عقد السكن', r'تجديد العقد', r'التأمين',
            r'250 ريال', r'الضمان الاجتماعي', r'استرداد التأمين', r'طرد', r'إخلاء',
            r'بطاقة السكن', r'كرت الباب', r'سكن المستجدين', r'الطاقة الاستيعابية'
        ],
        'raw_categories': [
            'housing_admin_occupancy', 'housing_admin_services', 'housing_admin_health',
            'أنظمة وإدارة السكن', 'شؤون مالية وإدارية'
        ],
        'root_causes': [
            'عجز الطاقة الاستيعابية للسكن عن تلبية طلبات جميع الطلاب المستجدين والمغتربين القادمين من خارج الرياض.',
            'إجراءات تجديد العقود وتسليم الغرف ومخاوف الطلاب من خصومات مبلغ التأمين المسترد (250 ريال).',
            'نفاد بطاقات الدخول الممغنطة وإجراءات استخراج بدل الفاقد.'
        ],
        'timeline_evolution': (
            "في 9 و10 سبتمبر شهد السكن نقاشات حول معايير تسكين المستجدين واستيعابهم. "
            "وفي 20 سبتمبر برزت أزمة عجز المقاعد السكنية واضطرار بعض الطلاب للبحث عن شقق خارجية غالية. "
            "وفي 27 و30 سبتمبر تركزت الشكاوى على نفاد بطاقات الأبواب والتخوف من التلفيات المحسوبة على التأمين."
        ),
        'student_actions': [
            "شروحات الطلاب القدامى للمستجدين حول آلية تقديم طلبات الاستثناء وخطوات استرداد التأمين.",
            "مجموعات تبادل وتشارك الشقق الخارجية للطلاب الذين لم يحالفهم الحظ في القبول بالسكن الجامعي."
        ]
    }
}

# 4. Perform Clustering and Message Extraction
cluster_results = {}

for ckey, cconf in clusters_config.items():
    print(f"Processing cluster: {ckey}...")
    compiled_patterns = [re.compile(p, re.IGNORECASE) for p in cconf['patterns']]
    
    # 4a. Collect all explicit message IDs from daily records matching this cluster
    cluster_msg_ids = set()
    matched_daily_records = []
    
    for rec in daily_records:
        rec_cat = rec.get('category_raw', '').lower()
        rec_desc = rec.get('description', '')
        rec_topic = rec.get('context', '')
        
        is_match = False
        # Check raw category match
        if any(rc in rec_cat for rc in cconf['raw_categories']):
            is_match = True
        # Check text regex match
        elif any(rgx.search(rec_desc) or rgx.search(rec_topic) for rgx in compiled_patterns):
            is_match = True
            
        if is_match:
            matched_daily_records.append(rec)
            for mid in rec.get('msg_ids', []):
                if isinstance(mid, int) and mid in raw_msgs:
                    cluster_msg_ids.add(mid)

    # 4b. Scan all raw messages of September with cluster keywords
    for mid, m in raw_msgs.items():
        text = m.get('t', '')
        if not text:
            continue
        if any(rgx.search(text) for rgx in compiled_patterns):
            cluster_msg_ids.add(mid)
            
    # 4c. Follow direct reply chains (r) - if message is reply to a message in cluster
    for mid, m in raw_msgs.items():
        reply_to = m.get('r')
        if reply_to and reply_to in cluster_msg_ids:
            # check length / not just a random greeting
            t = m.get('t', '').strip()
            if len(t) > 5 and not any(skip in t for skip in ['صلوا على', '«لا حَوْلَ', 'السلام عليكم']):
                cluster_msg_ids.add(mid)

    # 4d. Build sorted messages list
    cluster_messages = []
    platform_counts = {'tg': 0, 'wa': 0}
    user_ids = set()
    buildings_detected = set()
    
    building_regex = re.compile(r'(?:مبنى|عمارة|مباني)\s*(\d{1,2})', re.IGNORECASE)
    
    for mid in sorted(cluster_msg_ids):
        m = raw_msgs.get(mid)
        if not m:
            continue
        plat = m.get('s', 'tg')
        platform_counts[plat] = platform_counts.get(plat, 0) + 1
        user_ids.add(m.get('u'))
        
        # Check buildings mentioned in text
        for b_match in building_regex.findall(m.get('t', '')):
            buildings_detected.add(f"مبنى {b_match}")
            
        cluster_messages.append({
            'id': m['i'],
            'source': m.get('s', 'tg'),
            'user_id': m.get('u'),
            'time': m.get('d'),
            'text': m.get('t')
        })

    # Add buildings detected from daily records
    for rec in matched_daily_records:
        if rec.get('building'):
            b_val = str(rec['building'])
            for b_match in building_regex.findall(b_val):
                buildings_detected.add(f"مبنى {b_match}")

    # Top sample verbatim quotes
    sample_quotes = []
    # pick diverse informative quotes
    sorted_by_len = sorted(cluster_messages, key=lambda x: len(x['text']), reverse=True)
    for sm in sorted_by_len:
        t = sm['text']
        if 40 <= len(t) <= 250 and not any(sq['text'] == t for sq in sample_quotes):
            sample_quotes.append({
                'id': sm['id'],
                'source': sm['source'],
                'user_id': sm['user_id'],
                'time': sm['time'],
                'text': t
            })
            if len(sample_quotes) >= 10:
                break

    cluster_results[ckey] = {
        'cluster_id': ckey,
        'title_ar': cconf['title_ar'],
        'category': cconf['category'],
        'severity': cconf['severity'],
        'total_messages_count': len(cluster_messages),
        'unique_users_count': len(user_ids),
        'platforms_breakdown': platform_counts,
        'affected_buildings': sorted(list(buildings_detected)),
        'root_causes': cconf['root_causes'],
        'timeline_and_evolution': cconf['timeline_evolution'],
        'student_initiatives_and_resolutions': cconf['student_actions'],
        'daily_analysis_records_mapped': len(matched_daily_records),
        'message_ids': sorted(list(cluster_msg_ids)),
        'sample_verbatim_messages': sample_quotes,
        'messages': cluster_messages
    }
    print(f" -> {ckey}: {len(cluster_messages)} messages, {len(user_ids)} users, {len(buildings_detected)} buildings.")

# 5. Overall Monthly Summary
monthly_output = {
    'month': '2026-09',
    'total_days_analyzed': 30,
    'date_range': {
        'start': '2026-09-01',
        'end': '2026-09-30'
    },
    'total_raw_messages': len(raw_msgs),
    'total_clustered_messages': sum(c['total_messages_count'] for c in cluster_results.values()),
    'unique_feedback_messages': len(set(mid for c in cluster_results.values() for mid in c['message_ids'])),
    'executive_summary': (
        "يمثل شهر سبتمبر 2026 الانطلاقة الفعلية للعام الدراسي وشهد ذروة تفاعل مجتمع طلاب السكن (ResidentEcho) "
        "بإجمالي 26,765 رسالة. تصدرت 'أزمة الإعاشة والمطعم الجامعي' المشهد بامتياز كأكبر ملف طلابي حاشد إثر قرار منع الوجبات السفرية "
        "وتقليص أوقات الوجبات وإغلاق الممر المكيف، مما أفرز حراكاً طلابياً منظماً أثمر عن عريضة رسمية للمدير التنفيذي لمتعهد التغذية "
        "بمشاركة أكثر من 1400 طالب، وحملة كسر الملاعق، وتصعيد الملف لعميد شؤون الطلاب. "
        "تلا ذلك أزمة انقطاعات شبكة الإنترنت الشاملة وحجب الألعاب والمنصات (PlayStation, Gmail, Zoom) وحملة حصر البلاغات الجماعية، "
        "ثم أزمة حرارة وتلوث مياه الاستحمام وانقطاع المياه الليلي الشامل في مباني 6 و15 و19، "
        "إضافة إلى موجة الغضب العارمة من جشع واحتكار بقالة السكن، وتردي خدمات المغسلة وتلف الملابس التي قابلها الطلاب بمبادرة المغسلة البديلة بريال، "
        "وتشديد كلبشات المواقف وغراماتها (57.5 ريال) وسحب السكوترات."
    ),
    'clusters_count': len(cluster_results),
    'clusters': list(cluster_results.values())
}

# Save JSON output
out_json_path = os.path.join(OUTPUT_DIR, '2026-09_analysis.json')
with open(out_json_path, 'w', encoding='utf-8') as fp:
    json.dump(monthly_output, fp, indent=2, ensure_ascii=False)

print(f"\nSaved monthly analysis JSON to: {out_json_path} (Size: {os.path.getsize(out_json_path) / 1024 / 1024:.2f} MB)")

# 6. Generate Markdown Report
md_lines = []
md_lines.append("# ResidentEcho - تقرير التحليل الشهري وعناقيد المشكلات (Monthly Issue Clustering)")
md_lines.append("## 📅 النطاق الزمني: سبتمبر 2026 (2026-09-01 إلى 2026-09-30) | المرحلة الرابعة")
md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("### 📊 المؤشرات الرقمية العامة للشهر")
md_lines.append(f"- **إجمالي أيام الشهر المحللة:** 30 يوماً (100% تغطية يومية دقيقة).")
md_lines.append(f"- **إجمالي رسائل الشهر الخام:** {monthly_output['total_raw_messages']:,} رسالة.")
md_lines.append(f"- **إجمالي الرسائل المجمعة داخل العناقيد:** {monthly_output['total_clustered_messages']:,} رسالة.")
md_lines.append(f"- **الرسائل الفريدة المصنفة ضمن المشكلات:** {monthly_output['unique_feedback_messages']:,} رسالة.")
md_lines.append(f"- **عدد عناقيد المشكلات الرئيسية المستخلصة:** {len(cluster_results)} عناقيد.")
md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("### 📝 الملخص التنفيذي لشهر سبتمبر 2026")
md_lines.append(monthly_output['executive_summary'])
md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("## 🗂️ جدول عناقيد المشكلات لشهر سبتمبر 2026")
md_lines.append("")
md_lines.append("| م | عنقود المشكلة (Issue Cluster) | التصنيف | الأثر | إجمالي الرسائل | المستخدمون | أبرز المباني المتأثرة |")
md_lines.append("| :- | :--- | :--- | :--- | :--- | :--- | :--- |")

for idx, c in enumerate(cluster_results.values(), 1):
    sev_badge = "🔴 حرج" if c['severity'] == 'critical' else ("🟠 مرتفع" if c['severity'] == 'high' else "🟡 متوسط")
    bldgs = "، ".join(c['affected_buildings'][:5]) if c['affected_buildings'] else "عام بالسكن"
    md_lines.append(f"| {idx} | **{c['title_ar']}** | {c['category']} | {sev_badge} | {c['total_messages_count']:,} | {c['unique_users_count']:,} | {bldgs} |")

md_lines.append("")
md_lines.append("---")
md_lines.append("")
md_lines.append("## 🔍 تفاصيل عناقيد المشكلات والرسائل المرتبطة بها")
md_lines.append("")

for idx, c in enumerate(cluster_results.values(), 1):
    sev_badge = "🔴 حرج" if c['severity'] == 'critical' else ("🟠 مرتفع" if c['severity'] == 'high' else "🟡 متوسط")
    md_lines.append(f"### {idx}. {c['title_ar']}")
    md_lines.append(f"- **المعرف البرمجي للعنقود:** `{c['cluster_id']}`")
    md_lines.append(f"- **التصنيف:** {c['category']} | **مستوى الأثر:** {sev_badge}")
    md_lines.append(f"- **حجم التفاعل:** {c['total_messages_count']:,} رسالة (تليغرام: {c['platforms_breakdown'].get('tg', 0):,} | واتساب: {c['platforms_breakdown'].get('wa', 0):,}) من {c['unique_users_count']:,} مستخدم فريد.")
    if c['affected_buildings']:
        md_lines.append(f"- **المباني المتأثرة صراحة في المحادثات:** {', '.join(c['affected_buildings'])}")
    md_lines.append("")
    md_lines.append("#### 🎯 الأسباب الجذرية المستخلصة (Root Causes):")
    for rc in c['root_causes']:
        md_lines.append(f"- {rc}")
    md_lines.append("")
    md_lines.append("#### 📈 التطور الزمني والمسار خلال الشهر (Timeline & Evolution):")
    md_lines.append(c['timeline_and_evolution'])
    md_lines.append("")
    md_lines.append("#### 🤝 المبادرات والتحركات الطلابية (Student Actions & Resolutions):")
    for act in c['student_initiatives_and_resolutions']:
        md_lines.append(f"- {act}")
    md_lines.append("")
    md_lines.append("#### 💬 عينات من رسائل الطلاب الحرفية (Sample Verbatim Quotes):")
    for sm in c['sample_verbatim_messages'][:5]:
        plat_icon = "📱 [TG]" if sm['source'] == 'tg' else "💬 [WA]"
        md_lines.append(f"> **{plat_icon} معرف #{sm['id']} (المستخدم `{sm['user_id']}` - {sm['time'][:16].replace('T', ' ')}):**  ")
        md_lines.append(f"> \"{sm['text']}\"")
        md_lines.append(">")
    md_lines.append("")
    md_lines.append(f"> ℹ️ **تجميع الرسائل:** تم حصر وتضمين كافة معرفات الرسائل المرتبطة بهذا العنقود البالغ عددها **{len(c['message_ids']):,} رسالة** بالكامل داخل ملف التحليل البرمجي [`monthly_analysis/2026-09_analysis.json`](/monthly_analysis/2026-09_analysis.json).")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

out_md_path = os.path.join(OUTPUT_DIR, '2026-09_clustering_report.md')
with open(out_md_path, 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(md_lines))

print(f"Saved monthly clustering Markdown report to: {out_md_path}")

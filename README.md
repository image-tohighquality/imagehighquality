# 🖼️ Image Quality Bot

> بوت تيليجرام ذكي يحلل صورك ويُنتج برومبت احترافي مخصص لتحسين جودتها عبر ChatGPT أو Gemini

---

## كيف يعمل البوت؟

```
المستخدم يرسل صورة
        ↓
البوت يحللها بـ Claude AI
        ↓
يُنتج برومبت احترافي مخصص 100% لتلك الصورة
        ↓
المستخدم يستخدمه في ChatGPT أو Gemini مع نفس الصورة
```

---

## المميزات

- **تحليل ذكي** — يكتشف تلقائياً نوع الصورة ومشاكلها
- **8 أنواع صور مدعومة** — بورتريه، مجموعة، منظر طبيعي، عمارة، وثيقة، لوحة فنية، ليلية، مختلطة
- **معالجة الوجوه بدقة** — يُحدد اتجاه الوجه وحجمه ويختار استراتيجية مناسبة
- **وضع Patch** — يشخص نتائج فاشلة ويُنتج برومبت إصلاح مخصص
- **دعم منصتين** — ChatGPT و Gemini مع تعليمات مخصصة لكل منهما
- **Rate Limiting** — حماية من الإفراط في الاستخدام
- **اشتراك إلزامي** — يشترط الانضمام لقناة تيليجرام قبل الاستخدام

---

## استراتيجية معالجة الوجوه

| الوضع | الحالة | ما يفعله البرومبت |
|-------|--------|-----------------|
| **FULL MODE** | وجه أمامي + بارز | تحليل كامل للتعبير وإعادة بناء دقيقة |
| **LIMITED MODE** | وجه أمامي + صغير | تنظيف فقط بدون إعادة بناء للتعبير |
| **TEXTURE MODE** | وجه جانبي أو نصفي | معاملته كسطح — تنظيف بدون تفسير |
| **HANDS-OFF** | ظهر الرأس أو بعيد | لا يُمسّ الوجه نهائياً |

---

## هيكل المشروع

```
image-quality-bot/
├── bot.py              ← نقطة الدخول الرئيسية
├── claude_client.py    ← تكامل Claude API
├── subscription.py     ← بوابة الاشتراك في القناة
├── system_prompt.py    ← منطق التحليل (Skill v4)
├── rate_limiter.py     ← الحد الأقصى للاستخدام
├── messages.py         ← نصوص رسائل البوت
├── config.py           ← الإعدادات
├── railway.json        ← إعدادات Railway
├── Procfile            ← أمر التشغيل
├── runtime.txt         ← Python 3.11
├── requirements.txt    ← المكتبات
└── .env.example        ← قالب متغيرات البيئة
```

---

## متطلبات التشغيل

- Python 3.11+
- Telegram Bot Token — من [@BotFather](https://t.me/BotFather)
- Claude API Key — من [console.anthropic.com](https://console.anthropic.com)
- حساب [Railway](https://railway.app) للنشر

---

## الإعداد المحلي

```bash
# 1. استنسخ المشروع
git clone https://github.com/YOUR_USERNAME/image-quality-bot.git
cd image-quality-bot

# 2. أنشئ بيئة افتراضية
python -m venv venv
source venv/bin/activate  # أو: venv\Scripts\activate على Windows

# 3. ثبّت المكتبات
pip install -r requirements.txt

# 4. أنشئ ملف البيئة
cp .env.example .env
# افتح .env وأضف الـ tokens

# 5. شغّل البوت
python bot.py
```

---

## متغيرات البيئة

| المتغير | الوصف | مطلوب |
|---------|-------|--------|
| `TELEGRAM_BOT_TOKEN` | Token البوت من BotFather | ✅ |
| `CLAUDE_API_KEY` | مفتاح Claude API | ✅ |
| `CLAUDE_MODEL` | اسم الموديل (افتراضي: `claude-sonnet-4-5`) | اختياري |
| `MAX_IMAGES_PER_HOUR` | الحد الأقصى للصور لكل مستخدم في الساعة (افتراضي: `5`) | اختياري |

---

## النشر على Railway

راجع ملف [`DEPLOY_RAILWAY.md`](./DEPLOY_RAILWAY.md) للدليل الكامل خطوة بخطوة.

> **تنبيه:** أضف البوت كمشرف في قناة `@forca91` لكي تعمل خاصية التحقق من الاشتراك.

---

## المكتبات المستخدمة

| المكتبة | الغرض |
|---------|-------|
| `python-telegram-bot` | التواصل مع Telegram API |
| `anthropic` | التواصل مع Claude AI |
| `python-dotenv` | تحميل متغيرات البيئة |

---

## الترخيص

هذا المشروع خاص وغير مرخص للاستخدام العام.

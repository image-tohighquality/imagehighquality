# دليل رفع البوت على Railway
## من الصفر — خطوة بخطوة

---

## ما الذي ستحصل عليه

بوت تيليجرام يعمل **24/7** بدون انقطاع على Railway:
- يعيد التشغيل تلقائياً عند أي خطأ
- لا timeout على عمليات Claude
- logs مباشرة في Railway Dashboard
- تحديث الكود بـ `git push` فقط

---

## المتطلبات

- حساب GitHub
- حساب Railway (railway.app) — يمكن التسجيل بـ GitHub مباشرة
- Telegram Bot Token (من @BotFather)
- Claude API Key (من console.anthropic.com)
- Git مثبت على جهازك

---

## الخطوة 1 — إنشاء بوت تيليجرام

**إذا لم يكن لديك بوت بعد:**

1. افتح تيليجرام ← ابحث عن `@BotFather`
2. أرسل: `/newbot`
3. اختر اسماً (مثال: `Image Quality Bot`)
4. اختر username ينتهي بـ `bot` (مثال: `imagequalityai_bot`)
5. احفظ الـ Token:
   ```
   7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

**ضبط البوت:**

أرسل لـ BotFather: `/setdescription` ثم:
```
أرسل لي صورة وسأحللها وأعطيك برومبت احترافي لتحسينها في ChatGPT أو Gemini
```

أرسل: `/setcommands` ثم:
```
start - بدء استخدام البوت
```

---

## الخطوة 2 — Claude API Key

1. اذهب إلى `console.anthropic.com`
2. سجّل دخول ← **API Keys** ← **Create Key**
3. سمّه: `railway-image-bot`
4. احفظ المفتاح — **لن يظهر مرة ثانية**
5. أضف رصيداً من **Billing** (5 دولار تكفي للبداية)

---

## الخطوة 3 — رفع الكود على GitHub

**3.1** اذهب إلى `github.com` ← **New repository**
- الاسم: `image-quality-bot`
- الوضع: **Private** (لحماية كودك)
- لا تضف أي ملفات تلقائية

**3.2** على جهازك، افتح Terminal في مجلد المشروع:

```bash
git init
git add .
git commit -m "Initial Railway deploy"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/image-quality-bot.git
git push -u origin main
```

> استبدل `YOUR_USERNAME` باسم حساب GitHub.

---

## الخطوة 4 — إنشاء مشروع على Railway

**4.1** اذهب إلى `railway.app` ← سجّل دخول بحساب GitHub

**4.2** اضغط **New Project**

**4.3** اختر **Deploy from GitHub repo**

**4.4** اختر `image-quality-bot` من القائمة

**4.5** Railway سيكتشف المشروع تلقائياً — **لا تضغط Deploy بعد**

---

## الخطوة 5 — إضافة Environment Variables

هذه الخطوة الأهم. بدونها البوت لن يعمل.

**5.1** في صفحة المشروع، اضغط على الـ Service

**5.2** من القائمة العلوية اختر **Variables**

**5.3** اضغط **New Variable** وأضف المتغيرين:

```
TELEGRAM_BOT_TOKEN  =  7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CLAUDE_API_KEY      =  sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxx
```

> للإضافة السريعة: اضغط **RAW Editor** والصق:
> ```
> TELEGRAM_BOT_TOKEN=YOUR_TOKEN
> CLAUDE_API_KEY=YOUR_KEY
> ```

**5.4** اضغط **Save** أو **Update Variables**

---

## الخطوة 6 — التأكد من إعدادات الـ Deploy

**6.1** اذهب إلى **Settings** في الـ Service

**6.2** تأكد من:
- **Start Command**: `python bot.py`
  (إذا كان فارغاً اتركه — الـ `Procfile` يتولى هذا تلقائياً)

**6.3** تأكد من أن **Restart Policy** مضبوط على `ON_FAILURE`
(موجود في `railway.json` تلقائياً)

---

## الخطوة 7 — النشر

**7.1** اضغط **Deploy** أو انتظر Railway ينشر تلقائياً

**7.2** اذهب إلى تبويب **Deployments** وراقب الـ logs

**7.3** يجب أن ترى هذا في الـ logs:
```
Starting Image Quality Bot...
Bot is running. Polling for updates...
```

إذا ظهر هذا → البوت يعمل ✅

---

## الخطوة 8 — الاختبار

**8.1** افتح تيليجرام وابحث عن بوتك

**8.2** أرسل: `/start`
يجب أن تصل رسالة ترحيب خلال ثانية.

**8.3** أرسل أي صورة:
- يجب أن يصل رد فوري: "جاري تحليل صورتك..."
- خلال 15–40 ثانية يصل البرومبت الكامل

---

## الخطوة 9 — تحديث الكود مستقبلاً

أي تغيير تدفعه لـ GitHub يُنشر تلقائياً:

```bash
git add .
git commit -m "تحديث"
git push
```

Railway يكتشف الـ push وينشر النسخة الجديدة خلال دقيقة.

---

## مراقبة البوت

### عرض الـ Logs المباشرة
Railway Dashboard ← مشروعك ← **Deployments** ← آخر deployment ← **View Logs**

كل رسالة يعالجها البوت تظهر هنا.

### تحقق من حالة البوت في أي وقت
إذا توقف البوت عن الرد، اذهب إلى Deployments وتحقق من الـ logs.

---

## مشاكل شائعة وحلولها

### البوت لا يرد على /start

**السبب الأول: Build فشل**
اذهب إلى Deployments ← آخر deployment ← Logs
ابحث عن كلمة `ERROR` أو `error`

**السبب الثاني: متغيرات البيئة ناقصة**
Variables ← تأكد من وجود `TELEGRAM_BOT_TOKEN` و `CLAUDE_API_KEY`
بعد إضافتها: اضغط **Redeploy**

---

### خطأ: `TELEGRAM_BOT_TOKEN is not set`

المتغير غير موجود أو مكتوب بشكل خاطئ.
تأكد من الاسم بالضبط: `TELEGRAM_BOT_TOKEN` (حساس لحالة الأحرف)

---

### البوت يعمل ثم يتوقف فجأة

Railway يُعيد التشغيل تلقائياً. اذهب إلى Deployments لترى سبب التوقف في Logs.

الأسباب الشائعة:
- خطأ في Claude API (يختفي بعد إعادة التشغيل)
- انقطاع مؤقت في الشبكة (يُصحَّح تلقائياً)

---

### رسالة "جاري التحليل" تبقى معلّقة

هذا لا يحدث على Railway لأنه لا يوجد timeout.
إذا حدث: الصورة كبيرة جداً أو Claude بطيء مؤقتاً.
انتظر دقيقة وأعد الإرسال.

---

### خطأ 429 من Claude

Claude API rate limit — انتظر دقيقة.
البوت يرسل رسالة تلقائية للمستخدم عند هذا الخطأ.

---

## هيكل ملفات المشروع

```
image-quality-bot/
├── bot.py              ← نقطة الدخول الرئيسية
├── claude_client.py    ← تكامل Claude API (async)
├── system_prompt.py    ← الـ Skill v4 كاملة
├── messages.py         ← نصوص رسائل البوت
├── rate_limiter.py     ← الحد الأقصى للاستخدام
├── config.py           ← الإعدادات
├── railway.json        ← إعدادات Railway (restart policy)
├── Procfile            ← أمر تشغيل البوت
├── runtime.txt         ← إصدار Python (3.11)
├── requirements.txt    ← المكتبات
├── .env.example        ← قالب ملف البيئة
└── DEPLOY_RAILWAY.md  ← هذا الملف
```

---

## التكاليف على Railway

| الاستخدام | التكلفة الشهرية التقريبية |
|-----------|--------------------------|
| خطة Hobby (مجانية) | 5$ رصيد أولي، ثم ~1–2$/شهر |
| خطة Pro | 20$/شهر (غير ضروري لبوت عادي) |

بوت بـ 100–500 مستخدم يومياً يكلّف ~1–3 دولار/شهر على Railway.

---

## ملاحظة على الخطة المجانية

Railway يعطيك **5 دولار رصيد مجاني** عند التسجيل.
بعد نفاده تحتاج لإضافة بطاقة ائتمان والدفع.
السعر بعد ذلك ~0.01$/ساعة لـ service صغير = ~7$/شهر كحد أقصى.

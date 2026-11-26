# ISH UI — يوسف الحازمي

واجهة إدارة احترافية تعمل داخل تطبيق iSH على iPhone وiPad.
المشروع مكتوب بـ Python ويستخدم مكتبات Python القياسية فقط، لذلك لا يحتاج إلى pip أو مكتبات خارجية.

> ملاحظة: iSH بيئة طرفية Linux على iOS، لذلك هذه النسخة واجهة تفاعلية داخل الطرفية وليست سطح مكتب رسومي مثل Windows أو macOS.

## التثبيت من تطبيق iSH

نفّذ الأوامر التالية بالترتيب:

```sh
apk update
apk add git python3
git clone https://github.com/youef/ishUI.git
cd ishUI
chmod +x install.sh
./install.sh
```

بعد التثبيت شغّل:

```sh
ishui
```

أو مباشرة:

```sh
python3 ishui.py
```

## المزايا

- لوحة رئيسية تعرض معلومات الجهاز ومساحة التخزين.
- إدارة حزم Alpine Linux عبر apk.
- متصفح ملفات بسيط.
- تشغيل أوامر Linux.
- معلومات النظام وبيئة iSH.
- واجهة ملونة تدعم الطرفيات التي تدعم ANSI.
- لا يجمع بيانات ولا يتصل بأي خادم خارجي.

## المتطلبات

- تطبيق iSH مثبت على iPhone أو iPad.
- Python 3.
- Git (للاستيراد من GitHub).

## المطور

**يوسف الحازمي**

ISH UI — Designed & Developed by Youssef Alhazmi

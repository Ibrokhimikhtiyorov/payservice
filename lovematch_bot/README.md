# LoveMatch Bot

O'zbekiston uchun tanishuv (dating) Telegram boti — aiogram 3 + PostgreSQL.

## Imkoniyatlar
- Ro'yxatdan o'tish (ism, yosh 18+, jins, shahar, rasm, bio, kimni qidiryapti)
- Anketa ko'rish, like/super like/skip, o'zaro like -> match
- Matchdan keyin chat yopiq; chatni ochish uchun to'lov (**5000 so'm**, sozlanadi)
- Bir marta to'langan chat uchun qayta to'lov yo'q; to'lovlar DBda saqlanadi, idempotent tasdiqlash
- Premium: kim like bosganini ko'rish, cheksiz like, VIP, boost (narxlar admin tomonidan sozlanadi)
- Bloklash, shikoyat, qidiruv filtrlari (jins/shahar/yosh)
- Admin panel (`/admin`): statistika, foydalanuvchilar, to'lovlar, shikoyatlar, bloklash, reklama, narxlar
- Tillar: O'zbekcha / Русский
- Render uchun web/health endpoint va to'lov callbacklar

## O'rnatish (lokal)
1. Python 3.11+, PostgreSQL.
2. `cp .env.example .env` va qiymatlarni to'ldiring (`BOT_TOKEN`, `DATABASE_URL`, `ADMIN_IDS`, Hamyon kalitlari).
3. `pip install -r requirements.txt`
4. `python main.py`

## HamyonAPI integratsiyasi
- `.env`: `PAYMENT_PROVIDER=hamyon`, `HAMYON_SHOP_ID`, `HAMYON_SHOP_KEY`.
- Bot to'lov yaratganda Hamyon `/payment/create` chaqiriladi va foydalanuvchiga to'lov havolasi/karta yuboriladi.
- Hamyon callbacklarini botning ochiq URL manziliga yo'naltiring:
  - Prepare: `https://<YOUR-SERVICE>/hamyon/prepare`
  - Complete: `https://<YOUR-SERVICE>/hamyon/complete`
- Imzo `md5(SHOP_ID + payment_id + amount + SHOP_KEY)` orqali tekshiriladi, `order_id`/`amount` DB bilan solishtiriladi, tasdiqlash idempotent (bir to'lov ikki marta hisoblanmaydi).
- `PAYMENT_PROVIDER=test` — demo (avto-tasdiq), `webhook` — umumiy JSON callback (`/payment/webhook`).

## Render
`render.yaml` blueprint mavjud (`rootDir: lovematch_bot`, web service + PostgreSQL). Muhit o'zgaruvchilarini Render dashboardda to'ldiring.

## Eslatma
Ma'lumotlar PostgreSQLda saqlanadi, bot qayta ishga tushganda yo'qolmaydi. `.env` va sirlarni repoga commit qilmang. Haqiqiy pul oqimi uchun Hamyon do'kon sozlamalari va callback yo'nalishini o'zingizning Hamyon hisobingizda tasdiqlang.

PAY SERVICE BOT — O‘RNATISH
===========================

MUHIM: Eski akkaunt savdo botini to‘xtatmang va uning BOT_TOKEN/DB qiymatlarini o‘zgartirmang.

1. BotFather orqali yangi Telegram bot oching va token oling.
2. Shu loyihani alohida GitHub repository'ga yuklang.
3. Render'da New -> Web Service qilib shu repository'ni ulang.
4. Build: pip install -r requirements.txt
   Start: python main.py
5. Environment'ga .env.example dagi qiymatlarni kiriting:
   - yangi BOT_TOKEN
   - ADMIN_IDS
   - eski do‘koningizning HAMYON_SHOP_ID va HAMYON_SHOP_KEY
   - OLD_BOT_BASE_URL = eski botning https://...onrender.com manzili
6. Render yangi servis URL'ini olgach, HamyonAPI do‘konidagi callback manzillarini
   yangi servisga yo‘naltirish talab qilinadi:
   Prepare: https://YANGI-SERVIS.onrender.com/hamyon/prepare
   Complete: https://YANGI-SERVIS.onrender.com/hamyon/complete

SHARED SHOP CALLBACK ROUTING:
Bu bot yangi to‘lovlar uchun PSV- prefiksli order_id ishlatadi. Yangi callback gateway
PSV- bo‘lmagan callbacklarni OLD_BOT_BASE_URL dagi eski /hamyon/prepare va /hamyon/complete
endpointlariga uzatadi. Shu sabab eski bot ishlashda davom etadi.

DIQQAT — ISHGA TUSHIRISHDAN OLDIN:
HamyonAPI complete callback POST maydonlarida order_id yuborishini tasdiqlang.
Agar HamyonAPI complete callback'da order_id bo‘lmasa, bu gateway eski botga uzatadi;
yangi bot to‘lovini avtomatik ajratib bo‘lmaydi. HamyonAPI texnik yordamidan callback
formatini tasdiqlang yoki callback misolini oling. Callback URL'ni o‘zgartirishdan oldin
eski do‘kon callback sozlamalarini yozib oling.

Hozirgi kodda HamyonAPI orqali balans to‘ldirish va telefon/karta/kommunal/internet
xizmatlariga admin arizasi mavjud. Operator, bank, kommunal provayder va Payme/Click
merchant API integratsiyasi berilmaganligi sababli bu xizmatlar haqiqiy avtomatik
pul o‘tkazmaydi. QR ham hozircha real QR-ekvayring emas. Cashback stavkasi ham
provayder va biznes qoidalari belgilanmaguncha avtomatik qo‘shilmaydi.

XAVFSIZLIK:
- SHOP_KEY va BOT_TOKEN'ni chatga yoki GitHub'ga yozmang.
- Yangi botga alohida ma'lumotlar bazasi/disk ulang; Render ephemeral diskda SQLite
  ma'lumotlari deploy/restartdan keyin yo‘qolishi mumkin.
- Dastlab kichik summa bilan test qiling. Eski botning to‘lovini ham tekshiring.

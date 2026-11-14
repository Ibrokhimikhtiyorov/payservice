import asyncio,logging,uuid,os
from aiohttp import web
from aiogram import Bot,Dispatcher,F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart,Command
from aiogram.types import Message,CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton,ReplyKeyboardMarkup,KeyboardButton
from aiogram.fsm.state import State,StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from config import *
import db,hamyon
logging.basicConfig(level=logging.INFO)
log=logging.getLogger('pay-service')

class Flow(StatesGroup): topup=State(); phone=State(); card=State(); utility=State(); internet=State()

def menu():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='💰 Hamyonim'),KeyboardButton(text='➕ Balans to‘ldirish')],[KeyboardButton(text='📱 Telefon'),KeyboardButton(text='💳 Karta')],[KeyboardButton(text='🏠 Kommunal'),KeyboardButton(text='🌐 Internet / TV')],[KeyboardButton(text='📷 QR to‘lov'),KeyboardButton(text='🎁 Bonuslar')],[KeyboardButton(text='📜 Tarix'),KeyboardButton(text='🆘 Yordam')]],resize_keyboard=True)

def admin_kb(reqid): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Bajarildi',callback_data=f'reqdone:{reqid}'),InlineKeyboardButton(text='❌ Rad etish',callback_data=f'reqno:{reqid}')]])

async def start(m:Message):
    await db.upsert_user(m.from_user)
    await m.answer('Assalomu alaykum! 👋\n\nPAY SERVICE — to‘lov va elektron xizmatlar botiga xush kelibsiz.',reply_markup=menu())
async def help_cmd(m:Message): await m.answer('Yordam uchun administratorga murojaat qiling.'+(f' @{SUPPORT_USERNAME}' if SUPPORT_USERNAME else ''))
async def balance_cmd(m:Message): await db.upsert_user(m.from_user); await m.answer(f"👛 Balansingiz: <b>{await db.balance(m.from_user.id):,} so‘m</b>")
async def topup_start(m:Message,s: FSMContext): await s.set_state(Flow.topup); await m.answer(f'Qancha summa kiritmoqchisiz? Minimum: {MIN_TOPUP:,} so‘m')
async def topup_amount(m:Message,s:FSMContext,bot:Bot):
    try: amount=int(m.text.replace(' ','').replace(',',''))
    except: return await m.answer('Summani raqam bilan kiriting.')
    if amount<MIN_TOPUP: return await m.answer(f'Minimum {MIN_TOPUP:,} so‘m.')
    order='PSV-'+uuid.uuid4().hex[:20].upper()
    await db.create_payment(order,m.from_user.id,amount)
    try: data=await hamyon.create(order,amount)
    except Exception as e:
        log.exception('Hamyon payment create failed'); await m.answer('❌ To‘lov yaratilmadi. Keyinroq urinib ko‘ring.'); return await s.clear()
    url=data.get('url') or data.get('payment_url') or data.get('checkout_url')
    card=data.get('card')
    text=f'💳 <b>To‘lov yaratildi</b>\n\n💰 Summa: {amount:,} so‘m\n🧾 Buyurtma: <code>{order}</code>'
    if card: text+=f'\n💳 Karta: <code>{card}</code>'
    if url: text+='\n\nTo‘lovni davom ettirish uchun quyidagi havolani bosing.'
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='💳 To‘lash',url=str(url))]]) if url else None
    await m.answer(text,reply_markup=kb); await s.clear()

async def request_start(m:Message,s:FSMContext,kind:str,prompt:str): await s.update_data(kind=kind); await s.set_state(Flow.phone if kind=='Telefon' else Flow.card if kind=='Karta' else Flow.utility if kind=='Kommunal' else Flow.internet); await m.answer(prompt)
async def request_text(m:Message,s:FSMContext,bot:Bot):
    data=await s.get_data(); kind=data.get('kind','Xizmat'); rid=await db.add_request(m.from_user.id,kind,m.text)
    await m.answer(f'✅ So‘rovingiz qabul qilindi. Ariza №{rid}. Administrator tekshiradi.')
    for a in ADMIN_IDS:
        try: await bot.send_message(a,f'🆕 <b>Yangi xizmat arizasi №{rid}</b>\nXizmat: {kind}\nFoydalanuvchi: {m.from_user.full_name} ({m.from_user.id})\nMa’lumot: {m.text}',reply_markup=admin_kb(rid))
        except Exception: pass
    await s.clear()
async def generic(m:Message,s:FSMContext):
    t=m.text or ''
    if t=='➕ Balans to‘ldirish': return await topup_start(m,dp.fsm.get_context(bot=m.bot,chat_id=m.chat.id,user_id=m.from_user.id))
    if t=='💰 Hamyonim': return await balance_cmd(m)
    if t=='📱 Telefon':
        await s.update_data(kind='Telefon'); await s.set_state(Flow.phone); return await m.answer('Operator, telefon raqami va summani yuboring. Masalan: Beeline, 90XXXXXXX, 20 000 so‘m')
    if t=='💳 Karta':
        await s.update_data(kind='Karta'); await s.set_state(Flow.card); return await m.answer('Karta bo‘yicha so‘rovingizni yozing. To‘liq karta raqami yoki CVV yubormang!')
    if t=='🏠 Kommunal':
        await s.update_data(kind='Kommunal'); await s.set_state(Flow.utility); return await m.answer('Xizmat turi, abonent/shaxsiy hisob raqami va summani yozing.')
    if t=='🌐 Internet / TV':
        await s.update_data(kind='Internet / TV'); await s.set_state(Flow.internet); return await m.answer('Provayder, shaxsiy hisob raqami va summani yozing.')
    if t=='📷 QR to‘lov': return await m.answer('QR to‘lov hozircha hamyon identifikatori/so‘rov rejimida. To‘lov QR-ekvayring provayderi ulangandan keyin faollashadi.')
    if t=='🎁 Bonuslar': return await m.answer('🎁 Bonus dasturi: har bir tasdiqlangan to‘lov uchun aksiya qoidalariga muvofiq bonus beriladi. Hozircha bonus kampaniyasi admin tomonidan yoqiladi.')
    if t=='📜 Tarix': return await m.answer('To‘lovlar tarixi bo‘limi keyingi versiyada kengaytiriladi.')
    if t=='🆘 Yordam': return await help_cmd(m)
    await m.answer('Menyudan kerakli xizmatni tanlang.',reply_markup=menu())

async def req_action(c:CallbackQuery):
    if c.from_user.id not in ADMIN_IDS: return await c.answer('Ruxsat yo‘q',show_alert=True)
    action,rid=c.data.split(':'); status='done' if action=='reqdone' else 'rejected'
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as d: await d.execute('UPDATE requests SET status=? WHERE id=?',(status,int(rid))); await d.commit()
    await c.message.edit_text(c.message.text+('\n\n✅ Bajarildi' if status=='done' else '\n\n❌ Rad etildi')); await c.answer('Saqlandi')

async def health(req): return web.json_response({'status':'ok','service':'pay-service-bot'})
async def run():
    if not BOT_TOKEN: raise RuntimeError('BOT_TOKEN kerak')
    await db.init_db()
    bot=Bot(BOT_TOKEN,default=DefaultBotProperties(parse_mode=ParseMode.HTML)); global dp; dp=Dispatcher(storage=MemoryStorage())
    dp.message.register(start,CommandStart()); dp.message.register(help_cmd,Command('help'))
    dp.message.register(topup_start,F.text=='➕ Balans to‘ldirish'); dp.message.register(balance_cmd,F.text=='💰 Hamyonim')
    dp.message.register(topup_amount,Flow.topup)
    dp.message.register(request_text,Flow.phone); dp.message.register(request_text,Flow.card); dp.message.register(request_text,Flow.utility); dp.message.register(request_text,Flow.internet)
    dp.callback_query.register(req_action,F.data.startswith('reqdone:')|F.data.startswith('reqno:'))
    dp.message.register(generic)
    app=web.Application(); app['bot']=bot; app.router.add_get('/',health); app.router.add_get('/health',health); app.router.add_post('/hamyon/prepare',hamyon.prepare); app.router.add_post('/hamyon/complete',hamyon.complete)
    runner=web.AppRunner(app); await runner.setup(); await web.TCPSite(runner,'0.0.0.0',PORT).start()
    try: await dp.start_polling(bot)
    finally: await runner.cleanup(); await bot.session.close()
if __name__=='__main__': asyncio.run(run())

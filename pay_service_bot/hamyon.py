import hashlib,hmac,logging
from aiohttp import ClientSession,ClientTimeout,web
from config import HAMYON_SHOP_ID,HAMYON_SHOP_KEY,HAMYON_API_BASE,HAMYON_TIMEOUT,OLD_BOT_BASE_URL
import db
log=logging.getLogger(__name__)

def valid(form):
    pid=str(form.get('payment_id','')); amount=str(form.get('amount','')); sign=str(form.get('sign','')).lower()
    if not (HAMYON_SHOP_ID and HAMYON_SHOP_KEY and pid and amount and sign): return False
    expected=hashlib.md5(f'{HAMYON_SHOP_ID}{pid}{amount}{HAMYON_SHOP_KEY}'.encode()).hexdigest()
    return hmac.compare_digest(expected,sign)

async def create(order,amount):
    if not HAMYON_SHOP_ID or not HAMYON_SHOP_KEY: raise RuntimeError('HamyonAPI SHOP_ID/SHOP_KEY sozlanmagan')
    timeout=ClientTimeout(total=HAMYON_TIMEOUT)
    async with ClientSession(timeout=timeout) as s:
        async with s.post(HAMYON_API_BASE+'/payment/create',data={'shop_id':HAMYON_SHOP_ID,'shop_key':HAMYON_SHOP_KEY,'amount':str(amount),'order_id':order}) as r:
            data=await r.json(content_type=None)
            if r.status>=400 or not isinstance(data,dict) or data.get('error'): raise RuntimeError(str(data))
    pid=data.get('payment_id')
    if not pid: raise RuntimeError('HamyonAPI payment_id qaytarmadi')
    await db.set_payment_id(order,str(pid)); return data

async def proxy_old(path,form):
    if not OLD_BOT_BASE_URL: return web.json_response({'error':'old_bot_proxy_not_configured'},status=503)
    timeout=ClientTimeout(total=15)
    async with ClientSession(timeout=timeout) as s:
        async with s.post(OLD_BOT_BASE_URL+path,data=dict(form)) as r:
            body=await r.text(); return web.Response(text=body,status=r.status,content_type=r.headers.get('Content-Type','application/json'))

async def prepare(request):
    form=await request.post()
    if not valid(form): return web.json_response({'error':'signature'},status=403)
    order=str(form.get('order_id',''))
    if not order.startswith('PSV-'): return await proxy_old('/hamyon/prepare',form)
    try: amount=int(form.get('amount','0'))
    except ValueError: return web.json_response({'error':'amount'},status=400)
    p=await db.payment_by_order(order)
    if not p or p['amount']!=amount: return web.json_response({'error':'order_not_found_or_amount_mismatch'},status=404)
    await db.set_payment_id(order,str(form.get('payment_id','')))
    return web.json_response({'result':'ok'})

async def complete(request):
    form=await request.post()
    if not valid(form): return web.json_response({'error':'signature'},status=403)
    order=str(form.get('order_id',''))
    pid=str(form.get('payment_id',''))
    # Some gateways omit order_id in complete callback; payment_id lookup disambiguates safely.
    if not order.startswith('PSV-'):
        local=await db.payment_by_id(pid)
        if local and str(local['order_id']).startswith('PSV-'): order=local['order_id']
        else: return await proxy_old('/hamyon/complete',form)
    status=str(form.get('status','')).lower()
    try: amount=int(form.get('amount','0'))
    except ValueError: return web.json_response({'error':'amount'},status=400)
    if status!='paid': return web.json_response({'result':'ok'})
    p=await db.payment_by_id(pid)
    if not p or p['order_id']!=order: return web.json_response({'error':'payment_not_found'},status=404)
    result,credited=await db.mark_paid(pid,amount)
    if result is None: return web.json_response({'error':'amount_mismatch'},status=400)
    bot=request.app['bot']
    if credited:
        try: await bot.send_message(result['tg_id'],f"✅ To‘lov qabul qilindi!\n💰 Summa: {result['amount']:,} so‘m\n👛 Balans: {result['balance']:,} so‘m")
        except Exception: log.exception('User notification failed')
        from config import ADMIN_IDS
        for admin in ADMIN_IDS:
            try: await bot.send_message(admin,f"💳 Yangi to‘lov: {result['amount']:,} so‘m\n👤 Telegram ID: {result['tg_id']}\n🧾 {order}")
            except Exception: pass
    return web.json_response({'result':'ok'})

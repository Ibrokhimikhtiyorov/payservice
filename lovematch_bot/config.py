import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
ADMIN_IDS = [
    int(x)
    for x in os.getenv("ADMIN_IDS", "").replace(";", ",").split(",")
    if x.strip().isdigit()
]

# test | hamyon | webhook (generic)
PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "test").strip().lower()
PAYMENT_WEBHOOK_SECRET = os.getenv("PAYMENT_WEBHOOK_SECRET", "").strip()
PAYMENT_PAY_URL = os.getenv("PAYMENT_PAY_URL", "").strip()  # fallback: {ref} {amount}

# HamyonAPI
HAMYON_SHOP_ID = os.getenv("HAMYON_SHOP_ID", "").strip()
HAMYON_SHOP_KEY = os.getenv("HAMYON_SHOP_KEY", "").strip()
HAMYON_API_BASE = os.getenv("HAMYON_API_BASE", "https://hamyon-api.uz").rstrip("/")
HAMYON_TIMEOUT = int(os.getenv("HAMYON_TIMEOUT", "20"))

WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "10000"))

DEFAULT_CHAT_PRICE = int(os.getenv("CHAT_PRICE", "5000"))
DEFAULT_PREMIUM_PRICES = {
    "week": int(os.getenv("PREMIUM_WEEK_PRICE", "15000")),
    "month": int(os.getenv("PREMIUM_MONTH_PRICE", "39000")),
    "vip": int(os.getenv("PREMIUM_VIP_PRICE", "79000")),
}

DAILY_LIKES_FREE = int(os.getenv("DAILY_LIKES_FREE", "30"))
SUPER_LIKES_FREE = int(os.getenv("SUPER_LIKES_FREE", "1"))

import os
from pathlib import Path
from dotenv import load_dotenv
BASE_DIR=Path(__file__).resolve().parent
load_dotenv(BASE_DIR/'.env')
BOT_TOKEN=os.getenv('BOT_TOKEN','').strip()
ADMIN_IDS=[int(x) for x in os.getenv('ADMIN_IDS','').replace(';',',').split(',') if x.strip().isdigit()]
HAMYON_SHOP_ID=os.getenv('HAMYON_SHOP_ID','').strip()
HAMYON_SHOP_KEY=os.getenv('HAMYON_SHOP_KEY','').strip()
HAMYON_API_BASE=os.getenv('HAMYON_API_BASE','https://hamyon-api.uz').rstrip('/')
HAMYON_TIMEOUT=int(os.getenv('HAMYON_TIMEOUT','20'))
OLD_BOT_BASE_URL=os.getenv('OLD_BOT_BASE_URL','').rstrip('/')
DB_PATH=os.getenv('DB_PATH',str(BASE_DIR/'data'/'pay_service.sqlite3'))
MIN_TOPUP=int(os.getenv('MIN_TOPUP','1000'))
SUPPORT_USERNAME=os.getenv('SUPPORT_USERNAME','').lstrip('@')
PORT=int(os.getenv('PORT','10000'))

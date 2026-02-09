import threading
import requests
from bs4 import BeautifulSoup
import schedule
import time
from datetime import datetime
import telebot
import random
import re
from requests_html import HTMLSession
import jdatetime
import asyncio # ⬅️ اضافه شدن کتابخانه asyncio برای حل مشکل Thread


# ==========================================================
# 1. تنظیمات ربات و کانال و متغیرهای پیکربندی
# ==========================================================
# ⚠️ توکن و آیدی ادمین خود را اینجا جایگزین کنید
TELEGRAM_BOT_TOKEN = 'YOUE-API' 
ADMIN_ID = YOUE-NUMBER-ID

# نقشه روزهای هفته (برای نمایش به کاربر و تبدیل)
DAY_MAP = {
    'شنبه': 5, 'یکشنبه': 6, 'دوشنبه': 0, 'سه‌شنبه': 1,
    'چهارشنبه': 2, 'پنجشنبه': 3, 'جمعه': 4
}
REV_DAY_MAP = {v: k for k, v in DAY_MAP.items()}

CONFIG = {
    'CHANNEL_ID': '@YOUR CHANNEL USERNAME', 
    'POST_INTERVAL_MINUTES': 5,
    'START_HOUR': 10,
    'END_HOUR': 22,
    'WORKING_DAYS': [0, 1, 2, 3, 5, 6], 
    'HASHTAGS': [
        "#قیمت_لحظه_ای", "#دلار_آزاد", "#قیمت_طلا", "#طلا18",
        "#سکه_امامی", "#سکه_بهار", "#طلا_دست_دوم", "#گرم_نقره",
        "#ارز_تهران", "#یورو"
    ]
}

TARGET_URL = 'https://www.tgju.org/'
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
LAST_PRICES = {} 
USER_STATE = {}
IS_BOT_ACTIVE = True 

# متغیرهای جدید برای دکمه‌ها، گزارش روزانه و حذف پیام
INSTAGRAM_ID = 'YOUE COMPANY NAME'
WEBSITE_URL = 'YOUR WEBSITE URL'
TRACKED_KEYS = ['usd', 'eur', 'gold_18', 'gold_24', 'gold_2nd', 'silver', 'seke_emami', 'seke_bahar']
DAILY_MIN_MAX = {} 
LAST_MESSAGE_ID = None # متغیر ذخیره ID آخرین پیام

# لیست User-Agentها
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:56.0) Gecko/20100101 Firefox/91.0',
]
# ==========================================================
# 2. توابع کمکی (تبدیل به تومان، محاسبه تغییرات، تاریخ شمسی، گزارش)
# ==========================================================

def get_shamsi_date():
    """تبدیل تاریخ میلادی به شمسی با فرمت: شنبه 26 مهر 1404"""
    now = jdatetime.datetime.now()
    weekday_int = datetime.now().weekday()
    day_name = REV_DAY_MAP.get(weekday_int, 'نامشخص')
    
    shamsi_date_str = now.strftime("%d %B %Y")
    return f"{day_name} {shamsi_date_str}"

def get_day_name(weekday_int):
    """تبدیل عدد روز هفته (0=دوشنبه) به نام فارسی."""
    return REV_DAY_MAP.get(weekday_int, 'نامشخص')

def get_working_days_names():
    """تبدیل لیست عددی روزهای کاری به نام‌های فارسی برای نمایش."""
    sorted_days = sorted(CONFIG['WORKING_DAYS'])
    names = [get_day_name(d) for d in sorted_days]
    return '، '.join(names)

def is_working_day():
    """بررسی می‌کند که آیا امروز روز کاری است."""
    current_day = datetime.now().weekday()
    return current_day in CONFIG['WORKING_DAYS']

def clean_price(price_str):
    """تمیز کردن رشته قیمت و تبدیل آن به عدد صحیح."""
    return price_str.replace(',', '').replace(' ', '').strip()

def format_price_toman(price_str):
    """تبدیل قیمت (ریال) به تومان و فرمت‌دهی سه‌رقمی."""
    if price_str == 'یافت نشد': return price_str
    try:
        number_rial = int(clean_price(price_str))
        number_toman = int(number_rial / 10)
        return f"{number_toman:,}"
    except ValueError:
        return price_str

def get_toman_and_get_change(price_str, market_key):
    """محاسبه قیمت بر حسب تومان، مقایسه با قیمت قبلی، تولید فلش تغییر و درصد تغییر."""
    global LAST_PRICES

    cleaned_price_str = clean_price(price_str)
    try:
        current_price_rial = int(cleaned_price_str)
        current_price_toman = int(current_price_rial / 10)
    except ValueError:
        return 'یافت نشد', "⚪️", "(0.00%)", None 

    old_price_toman = LAST_PRICES.get(market_key)

    indicator = "➖"
    percent_change_str = "(0.00%)"

    if old_price_toman is not None:
        
        # محاسبه درصد تغییر
        if old_price_toman != 0:
            change = current_price_toman - old_price_toman
            percent_change = (change / old_price_toman) * 100
            
            # فرمت دهی درصد
            percent_change_str = f"({percent_change:+.2f}%)" 

        if current_price_toman > old_price_toman:
            indicator = "🔺" 
        elif current_price_toman < old_price_toman:
            indicator = "🔻" 
        else:
            indicator = "➖"
    
    LAST_PRICES[market_key] = current_price_toman 
    formatted_toman = format_price_toman(cleaned_price_str)
    
    # به‌روزرسانی داده‌های کمینه/بیشینه
    if market_key in TRACKED_KEYS:
        update_daily_min_max(market_key, current_price_toman)

    return formatted_toman, indicator, percent_change_str, current_price_toman 

def reset_daily_min_max():
    """بازنشانی (ریست) داده‌های کمینه/بیشینه روزانه."""
    global DAILY_MIN_MAX
    
    DAILY_MIN_MAX = {
        'date': datetime.now().date(),
        'prices': {key: {'min': float('inf'), 'max': float('-inf')} for key in TRACKED_KEYS}
    }
    print("داده‌های کمینه/بیشینه روزانه بازنشانی شدند.") 

def update_daily_min_max(market_key, current_price_toman):
    """به‌روزرسانی کمینه و بیشینه قیمت برای یک کلید خاص."""
    global DAILY_MIN_MAX
    
    data = DAILY_MIN_MAX['prices'][market_key]
    
    if current_price_toman < data['min']:
        data['min'] = current_price_toman
        
    if current_price_toman > data['max']:
        data['max'] = current_price_toman

def generate_report_message(for_admin=True):
    """تولید پیام گزارش روزانه کمینه/بیشینه."""
    
    report = [f"📊 <b>گزارش روزانه کمینه و بیشینه قیمت (تومان)</b>"]
    
    if not for_admin:
         report.append(f"🗓️ <b>تاریخ:</b> {get_shamsi_date()}")
         report.append("➖➖➖➖➖➖➖➖➖➖")

    price_labels = {
        'usd': "🇺🇸 دلار آزاد", 'eur': "🇪🇺 یورو آزاد", 'gold_18': "🏅 طلای ۱۸ عیار",
        'gold_24': "🏅 طلای ۲۴ عیار", 'gold_2nd': "🏅 طلای دست دوم", 'silver': "🥈 گرم نقره ۹۹۹",
        'seke_emami': "🔸 سکه امامی", 'seke_bahar': "🔸 سکه بهار آزادی"
    }

    for key, label in price_labels.items():
        data = DAILY_MIN_MAX['prices'].get(key)
        
        if data and data['min'] != float('inf') and data['max'] != float('-inf'):
            min_price = format_price_toman(str(data['min'] * 10))
            max_price = format_price_toman(str(data['max'] * 10))
            
            report.append(f"{label}\n🔹 کمینه: <code>{min_price}</code> | 🔸 بیشینه: <code>{max_price}</code>")
    
    if for_admin:
        report.append("\n⚠️ این داده‌ها بر اساس رصد ربات از زمان آخرین بازنشانی است.")
    else:
        report.append("\n⏱️ <i>زمان گزارش:</i> " + datetime.now().strftime("%H:%M:%S"))
        report.append(f"📣 <b>کانال رسمی:</b> {CONFIG['CHANNEL_ID']}")

    return '\n'.join(report)


# ==========================================================
# 3. تابع Web Scraping (با requests-html و حل مشکلات Thread/Async)
# ==========================================================

def extract_price_from_soup(soup, slug):
    """استخراج قیمت از ستون دوم جدول با استفاده از slug."""
    row = soup.find('tr', {'data-market-nameslug': slug})
    if not row:
        return 'یافت نشد'

    td_tags = row.find_all(['td', 'th'])
    if len(td_tags) > 1:
        price_tag = td_tags[1]
        return price_tag.text.strip()
    return 'یافت نشد'

def get_html_soup():
    """اجرای جاوا اسکریپت با requests-html برای دریافت محتوای نهایی."""
    session = HTMLSession()
    
    # ⬅️ حل مشکل 'There is no current event loop in thread'
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        print("در حال شروع جلسه requests-html و رندر جاوا اسکریپت...")
        
        response = session.get(TARGET_URL, headers=headers)
        
        # رندرینگ با پارامترهای پایدارکننده
        response.html.render(
            timeout=40,  
            sleep=7,     
            scrolldown=1, 
        ) 
        
        soup = BeautifulSoup(response.html.html, 'html.parser')
        
        return soup

    except Exception as e:
        print(f"خطای جدی در اجرای requests-html یا دریافت صفحه: {e}")
        return None
        
    finally:
        session.close() 

def get_latest_prices(soup=None):
    """استخراج، تمیزکاری و محاسبه تغییرات تمام قیمت‌های مورد نظر."""
    global DAILY_MIN_MAX
    
    if not DAILY_MIN_MAX or datetime.now().date() != DAILY_MIN_MAX['date']:
        reset_daily_min_max()

    if soup is None:
        soup = get_html_soup()
        if soup is None:
            return None

    raw_prices = {}
    processed_data = {}

    try:
        raw_prices['usd'] = extract_price_from_soup(soup, 'price_dollar_rl')
        raw_prices['eur'] = extract_price_from_soup(soup, 'price_eur')
        raw_prices['gold_18'] = extract_price_from_soup(soup, 'geram18')
        raw_prices['gold_24'] = extract_price_from_soup(soup, 'geram24')
        raw_prices['gold_2nd'] = extract_price_from_soup(soup, 'gold_mini_size')
        raw_prices['silver'] = extract_price_from_soup(soup, 'silver_999')
        raw_prices['seke_emami'] = extract_price_from_soup(soup, 'sekee')
        raw_prices['seke_bahar'] = extract_price_from_soup(soup, 'sekeb')

        for key, raw_price in raw_prices.items():
            formatted_toman, indicator, percent_change_str, raw_number_toman = get_toman_and_get_change(raw_price, key)
            processed_data[key] = {
                'price': formatted_toman, 
                'change': indicator, 
                'percent': percent_change_str, 
                'raw_number': raw_number_toman
            }

        if not processed_data or not all(p['price'] != 'یافت نشد' for p in processed_data.values() if p['price'] is not None):
            return None

        return processed_data

    except Exception as e:
        print(f"خطای کلی در پردازش اسکرپینگ: {e}")
        return None


# ==========================================================
# 4. تابع ارسال پیام اصلی (جدول قیمت کلی - با منطق حذف پیام قبلی)
# ==========================================================

def send_prices_core(force_send=False):
    global IS_BOT_ACTIVE
    global LAST_MESSAGE_ID 
    
    if not IS_BOT_ACTIVE and not force_send:
        return

    if not force_send and not is_working_day():
        return

    current_hour = datetime.now().hour

    if force_send or (CONFIG['START_HOUR'] <= current_hour <= CONFIG['END_HOUR']):
        prices = get_latest_prices()

        if prices:
            hashtag_string = ' '.join(CONFIG['HASHTAGS'])
            shamsi_date = get_shamsi_date() 

            # قالب پیام نهایی
            message = f"""
📢 <b>قیمت‌های لحظه‌ای طلا و ارز (تومان)</b>
🗓️ <b>تاریخ:</b> {shamsi_date}
➖➖➖➖➖➖➖➖➖➖
💵 <b>ارز‌های رایج</b>
➖➖➖➖➖➖➖➖➖➖
{prices['usd']['change']} 🇺🇸 <b>دلار آزاد:</b> {prices['usd']['price']} <code>{prices['usd']['percent']}</code>
{prices['eur']['change']} 🇪🇺 <b>یورو آزاد:</b> {prices['eur']['price']} <code>{prices['eur']['percent']}</code>
➖➖➖➖➖➖➖➖➖➖
🟡 <b>انواع طلا (هر گرم)</b>
➖➖➖➖➖➖➖➖➖➖
{prices['gold_18']['change']} 🏅 <b>طلا۱۸ عیار:</b> {prices['gold_18']['price']} <code>{prices['gold_18']['percent']}</code>
{prices['gold_24']['change']} 🏅 <b>طلا۲۴ عیار:</b> {prices['gold_24']['price']} <code>{prices['gold_24']['percent']}</code>
{prices['gold_2nd']['change']} 🏅 <b>طلادست دو:</b> {prices['gold_2nd']['price']} <code>{prices['gold_2nd']['percent']}</code>
{prices['silver']['change']} 🥈 <b>گرم نقره ۹۹۹:</b> {prices['silver']['price']} <code>{prices['silver']['percent']}</code>
➖➖➖➖➖➖➖➖➖➖
🪙 <b>انواع سکه</b>
➖➖➖➖➖➖➖➖➖➖
{prices['seke_emami']['change']} 🔸 <b>سکه امامی:</b> {prices['seke_emami']['price']} <code>{prices['seke_emami']['percent']}</code>
{prices['seke_bahar']['change']} 🔸 <b>سکه بهار:</b> {prices['seke_bahar']['price']} <code>{prices['seke_bahar']['percent']}</code>
➖➖➖➖➖➖➖➖➖➖
⏱️ <i>آخرین به‌روزرسانی: {datetime.now().strftime("%H:%M:%S")}</i>

📣 <b>کانال رسمی:</b> {CONFIG['CHANNEL_ID']}

{hashtag_string}
            """
            
            markup = telebot.types.InlineKeyboardMarkup()
            instagram_btn = telebot.types.InlineKeyboardButton(
                text="📌 اینستاگرام", 
                url=f"https://www.instagram.com/{INSTAGRAM_ID}"
            )
            website_btn = telebot.types.InlineKeyboardButton(
                text="📌 وبسایت", 
                url=WEBSITE_URL
            )
            markup.add(instagram_btn, website_btn)

            try:
                # ⬅️ ۱. حذف پیام قبلی در صورت وجود
                if LAST_MESSAGE_ID is not None:
                    try:
                        bot.delete_message(CONFIG['CHANNEL_ID'], LAST_MESSAGE_ID)
                        print(f"پیام قبلی با ID: {LAST_MESSAGE_ID} حذف شد.")
                    except telebot.apihelper.ApiTelegramException as e:
                        print(f"خطا در حذف پیام قبلی (ID: {LAST_MESSAGE_ID}): {e}")
                
                # ⬅️ ۲. ارسال پیام جدید
                sent_message = bot.send_message(
                    chat_id=CONFIG['CHANNEL_ID'],
                    text=message,
                    parse_mode='HTML',
                    reply_markup=markup
                )
                
                # ⬅️ ۳. ذخیره ID پیام جدید برای حذف در چرخه بعدی
                LAST_MESSAGE_ID = sent_message.message_id
                print(f"پیام جدول اصلی با موفقیت ارسال شد و ID جدید ({LAST_MESSAGE_ID}) ذخیره شد.")

            except Exception as e:
                print(f"خطا در ارسال پیام به تلگرام: {e}")
        else:
            print("اطلاعات قیمت دریافت نشدند یا ناقص بودند، پیام ارسال نشد.")
# ==========================================================
# 5. منطق قیمت لحظه‌ای (حذف کامل شده) + گزارش‌گیری
# ==========================================================

@bot.callback_query_handler(func=lambda call: call.data == 'gold_price_update')
def handle_gold_price_callback(call):
    """هندلر دکمه‌های قدیمی (برای جلوگیری از خطای API)."""
    try:
        bot.answer_callback_query(call.id, text="این دکمه دیگر کاربردی ندارد. 🔔")
    except Exception as e:
        print(f"خطا در پاسخ به Callback Query: {e}")

@bot.message_handler(func=lambda message: is_admin(message) and message.text == '📈 گزارش روزانه (کمینه/بیشینه)')
def handle_daily_report_start(message):
    
    if not DAILY_MIN_MAX or all(v['min'] == float('inf') for v in DAILY_MIN_MAX['prices'].values()):
        bot.send_message(message.chat.id, "❌ هنوز داده‌ای برای گزارش روزانه ثبت نشده است. لطفا صبر کنید تا ربات چند بار قیمت‌ها را به‌روز کند.")
        show_admin_menu(message.chat.id)
        return
        
    report_message = generate_report_message(for_admin=True)
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("✅ تایید و ارسال به کانال", callback_data='confirm_daily_report'),
        telebot.types.InlineKeyboardButton("❌ لغو", callback_data='cancel_daily_report')
    )
    
    bot.send_message(
        chat_id=message.chat.id,
        text=report_message,
        parse_mode='HTML',
        reply_markup=markup
    )
    USER_STATE[message.chat.id] = 'awaiting_report_confirmation'

@bot.callback_query_handler(func=lambda call: call.data in ['confirm_daily_report', 'cancel_daily_report'])
def handle_daily_report_callback(call):
    if call.data == 'confirm_daily_report':
        report_message = generate_report_message(for_admin=False)
        try:
            bot.send_message(CONFIG['CHANNEL_ID'], report_message, parse_mode='HTML')
            reset_daily_min_max()
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="✅ گزارش روزانه با موفقیت به کانال ارسال و داده‌های کمینه/بیشینه بازنشانی شدند.",
            )
            bot.answer_callback_query(call.id, "گزارش ارسال شد.")
        except Exception as e:
            bot.answer_callback_query(call.id, "خطا در ارسال گزارش به کانال.")
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"❌ خطای ارسال: {e}",
            )
    else:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="❌ ارسال گزارش روزانه لغو شد.",
        )
        bot.answer_callback_query(call.id, "لغو شد.")
    
    if call.message.chat.id in USER_STATE:
        USER_STATE[call.message.chat.id] = None
    show_admin_menu(call.message.chat.id)


# ==========================================================
# 6. منطق کنترل پنل مدیریت (Admin Panel Handlers)
# ==========================================================

def is_admin(message):
    return message.chat.id == ADMIN_ID

def show_admin_menu(chat_id):
    global IS_BOT_ACTIVE
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)

    status_text = "🟢 ربات روشن" if IS_BOT_ACTIVE else "🔴 ربات خاموش"
    toggle_button = "🔴 خاموش کردن ربات" if IS_BOT_ACTIVE else "🟢 روشن کردن ربات"

    markup.row(status_text)
    markup.row(toggle_button)
    markup.row('🔄 ارسال لیست قیمت فوری')
    markup.row('📈 گزارش روزانه (کمینه/بیشینه)', '⚙️ تنظیمات فعلی')
    markup.row('⏱️ تنظیم فاصله ارسال', '📅 تنظیم روزهای کاری')
    markup.row('⏰ تنظیم ساعت شروع', '⏰ تنظیم ساعت پایان')
    markup.row('💬 مدیریت هشتگ‌ها')
    bot.send_message(chat_id, "به پنل مدیریت خوش آمدید. لطفا گزینه مورد نظر را انتخاب کنید:", reply_markup=markup)

@bot.message_handler(commands=['start', 'menu'])
def handle_start(message):
    if is_admin(message):
        USER_STATE[message.chat.id] = None 
        show_admin_menu(message.chat.id)
    else:
        bot.send_message(message.chat.id, "شما دسترسی مدیریت ندارید.")

@bot.message_handler(func=lambda message: is_admin(message) and message.text == '🔄 ارسال لیست قیمت فوری')
def handle_instant_send(message):
    bot.send_message(message.chat.id, "در حال اسکرپینگ و ارسال لیست قیمت فوری به کانال...", reply_markup=telebot.types.ReplyKeyboardRemove())
    send_prices_core(force_send=True)
    show_admin_menu(message.chat.id)

@bot.message_handler(func=lambda message: is_admin(message) and message.text == '📅 تنظیم روزهای کاری')
def handle_set_working_days_start(message):
    USER_STATE[message.chat.id] = 'awaiting_working_days'
    
    current_names = get_working_days_names()
    
    prompt = f"""
لطفا روزهای کاری جدید را وارد کنید.
روزهای کاری فعلی: *{current_names}*
-------------------------------
روزهای هفته به صورت زیر وارد شوند (با فاصله از هم):
`شنبه یکشنبه دوشنبه سه شنبه چهارشنبه پنجشنبه جمعه`

*مثال:* `شنبه یکشنبه دوشنبه سه شنبه چهارشنبه پنجشنبه`
*مثال:* `یکشنبه دوشنبه جمعه`
"""
    bot.send_message(message.chat.id, prompt, parse_mode='Markdown')

@bot.message_handler(func=lambda message: is_admin(message) and USER_STATE.get(message.chat.id) == 'awaiting_working_days')
def handle_set_working_days_finish(message):
    input_days = message.text.split()
    new_days_numbers = set()
    invalid_days = []
    
    for day_name in input_days:
        day_name_standard = day_name.strip().lower().replace('سه شنبه', 'سه‌شنبه').replace('چهار شنبه', 'چهارشنبه').replace('پنج شنبه', 'پنجشنبه')
        
        day_number = DAY_MAP.get(day_name_standard.capitalize())
        
        if day_number is not None:
            new_days_numbers.add(day_number)
        else:
            invalid_days.append(day_name)
            
    if invalid_days:
        error_msg = f"❌ روزهای زیر نامعتبر هستند: {', '.join(invalid_days)}\nلطفا دوباره تلاش کنید."
        bot.send_message(message.chat.id, error_msg)
    elif not new_days_numbers:
        bot.send_message(message.chat.id, "❌ لطفا حداقل یک روز کاری معتبر وارد کنید.")
    else:
        CONFIG['WORKING_DAYS'] = list(new_days_numbers)
        new_names = get_working_days_names()
        bot.send_message(message.chat.id, f"✅ روزهای کاری با موفقیت به *{new_names}* تغییر یافت.", parse_mode='Markdown')
        
    USER_STATE[message.chat.id] = None
    show_admin_menu(message.chat.id)


@bot.message_handler(func=lambda message: is_admin(message) and (message.text == '🟢 روشن کردن ربات' or message.text == '🔴 خاموش کردن ربات'))
def handle_toggle_bot(message):
    global IS_BOT_ACTIVE
    
    if message.text == '🔴 خاموش کردن ربات':
        IS_BOT_ACTIVE = False
        schedule.clear('main_table')
        bot.send_message(message.chat.id, "❌ ربات خاموش شد. ارسال جدول‌های قیمت متوقف شد.")
    elif message.text == '🟢 روشن کردن ربات':
        IS_BOT_ACTIVE = True
        schedule.every(CONFIG['POST_INTERVAL_MINUTES']).minutes.do(send_prices_core).tag('main_table')
        bot.send_message(message.chat.id, f"✅ ربات روشن شد. ارسال جدول اصلی هر {CONFIG['POST_INTERVAL_MINUTES']} دقیقه فعال شد.")

    show_admin_menu(message.chat.id)
    
@bot.message_handler(func=lambda message: is_admin(message) and message.text.startswith('🟢 ربات روشن') or message.text.startswith('🔴 ربات خاموش'))
def handle_status_display(message):
    show_admin_menu(message.chat.id)

@bot.message_handler(func=lambda message: is_admin(message) and message.text == '⚙️ تنظیمات فعلی')
def handle_show_config(message):
    global IS_BOT_ACTIVE
    status = "فعال" if IS_BOT_ACTIVE else "غیرفعال"
    working_days_names = get_working_days_names()
    
    config_text = f"""
*تنظیمات فعلی ربات:*
-------------------------------
*وضعیت کلی:* `{status}`
*روزهای کاری:* `{working_days_names}`
*کانال هدف (Channel ID):* `{CONFIG['CHANNEL_ID']}`
*حد فاصل ارسال (دقیقه):* `{CONFIG['POST_INTERVAL_MINUTES']}`
*محدوده ارسال:* `{CONFIG['START_HOUR']}:00 تا {CONFIG['END_HOUR']}:00`
*هشتگ‌های فعلی:*
`{' '.join(CONFIG['HASHTAGS'])}`
*آدرس اینستاگرام:* `{INSTAGRAM_ID}`
*آدرس وبسایت:* `{WEBSITE_URL}`
-------------------------------
"""
    bot.send_message(chat_id=message.chat.id, text=config_text, parse_mode='Markdown')
    show_admin_menu(message.chat.id)

@bot.message_handler(func=lambda message: is_admin(message) and message.text == '⏰ تنظیم ساعت شروع')
def handle_set_start_hour_start(message):
    USER_STATE[message.chat.id] = 'awaiting_start_hour'
    bot.send_message(message.chat.id,
                     f"لطفا ساعت شروع ارسال پیام‌های روزانه (فقط عدد بین ۰ تا ۲۳) را وارد کنید (فعلی: {CONFIG['START_HOUR']}):")

@bot.message_handler(func=lambda message: is_admin(message) and USER_STATE.get(message.chat.id) == 'awaiting_start_hour')
def handle_set_start_hour_finish(message):
    try:
        new_hour = int(message.text)
        if not (0 <= new_hour <= 23):
            raise ValueError

        CONFIG['START_HOUR'] = new_hour
        bot.send_message(message.chat.id, f"✅ ساعت شروع ارسال جدول اصلی با موفقیت به {new_hour}:00 تغییر یافت.")

    except ValueError:
        bot.send_message(message.chat.id, "❌ ورودی نامعتبر. لطفا یک عدد صحیح بین ۰ تا ۲۳ وارد کنید.")

    USER_STATE[message.chat.id] = None
    show_admin_menu(message.chat.id)


@bot.message_handler(func=lambda message: is_admin(message) and message.text == '⏰ تنظیم ساعت پایان')
def handle_set_end_hour_start(message):
    USER_STATE[message.chat.id] = 'awaiting_end_hour'
    bot.send_message(message.chat.id,
                     f"لطفا ساعت پایان ارسال پیام‌های روزانه (فقط عدد بین ۰ تا ۲۳) را وارد کنید (فعلی: {CONFIG['END_HOUR']}):")

@bot.message_handler(func=lambda message: is_admin(message) and USER_STATE.get(message.chat.id) == 'awaiting_end_hour')
def handle_set_end_hour_finish(message):
    try:
        new_hour = int(message.text)
        if not (0 <= new_hour <= 23):
            raise ValueError

        CONFIG['END_HOUR'] = new_hour
        bot.send_message(message.chat.id, f"✅ ساعت پایان ارسال جدول اصلی با موفقیت به {new_hour}:00 تغییر یافت.")

    except ValueError:
        bot.send_message(message.chat.id, "❌ ورودی نامعتبر. لطفا یک عدد صحیح بین ۰ تا ۲۳ وارد کنید.")

    USER_STATE[message.chat.id] = None
    show_admin_menu(message.chat.id)

@bot.message_handler(func=lambda message: is_admin(message) and message.text == '⏱️ تنظیم فاصله ارسال')
def handle_set_interval_start(message):
    USER_STATE[message.chat.id] = 'awaiting_interval'
    bot.send_message(message.chat.id,
                     f"لطفا حد فاصل زمانی جدید برای ارسال پیام را بر حسب دقیقه وارد کنید (فعلی: {CONFIG['POST_INTERVAL_MINUTES']}):")

@bot.message_handler(func=lambda message: is_admin(message) and USER_STATE.get(message.chat.id) == 'awaiting_interval')
def handle_set_interval_finish(message):
    global IS_BOT_ACTIVE
    try:
        new_interval = int(message.text)
        if new_interval < 1:
            raise ValueError

        CONFIG['POST_INTERVAL_MINUTES'] = new_interval

        if IS_BOT_ACTIVE:
            schedule.clear('main_table')
            schedule.every(CONFIG['POST_INTERVAL_MINUTES']).minutes.do(send_prices_core).tag('main_table')
            bot.send_message(message.chat.id, f"✅ حد فاصل ارسال جدول اصلی با موفقیت به {new_interval} دقیقه تغییر و زمان‌بندی اعمال شد.")
        else:
            bot.send_message(message.chat.id, f"✅ حد فاصل ارسال جدول اصلی با موفقیت به {new_interval} دقیقه تغییر یافت. (ربات خاموش است، زمان‌بندی اعمال نشد.)")

    except ValueError:
        bot.send_message(message.chat.id, "❌ ورودی نامعتبر. لطفا یک عدد صحیح بزرگتر از ۰ وارد کنید.")

    USER_STATE[message.chat.id] = None
    show_admin_menu(message.chat.id)

@bot.message_handler(func=lambda message: is_admin(message) and message.text == '💬 مدیریت هشتگ‌ها')
def handle_set_hashtags_start(message):
    USER_STATE[message.chat.id] = 'awaiting_hashtags'
    current_hashtags = ' '.join(CONFIG['HASHTAGS'])
    bot.send_message(message.chat.id,
                     f"لطفا لیست هشتگ‌های جدید را وارد کنید. هر هشتگ را با فاصله از هم جدا کنید:\n(فعلی: `{current_hashtags}`)",
                     parse_mode='Markdown')

@bot.message_handler(func=lambda message: is_admin(message) and USER_STATE.get(message.chat.id) == 'awaiting_hashtags')
def handle_set_hashtags_finish(message):
    new_hashtags = [h.strip() for h in message.text.split() if h.strip().startswith('#')]

    if not new_hashtags:
        bot.send_message(message.chat.id, "❌ لیست هشتگ‌ها خالی است یا فرمت صحیح ندارد (باید با # شروع شوند).")
    else:
        CONFIG['HASHTAGS'] = new_hashtags
        bot.send_message(message.chat.id, f"✅ هشتگ‌ها با موفقیت به‌روز شدند:\n`{' '.join(new_hashtags)}`", parse_mode='Markdown')

    USER_STATE[message.chat.id] = None
    show_admin_menu(message.chat.id)


# ==========================================================
# 7. زمان‌بندی و اجرای دائمی
# ==========================================================

def run_schedule_and_poll():
    """حلقه اصلی اجرای زمان‌بندی‌ها و دریافت پیام‌ها."""
    global IS_BOT_ACTIVE
    
    reset_daily_min_max()

    # 1. اجرای اولین به‌روزرسانی قیمت جدول اصلی بلافاصله پس از شروع ربات
    print("✅ اجرای اولین به‌روزرسانی قیمت جدول اصلی...")
    send_prices_core(force_send=True)

    # 2. تنظیم زمان‌بندی جدول اصلی (فقط اگر ربات فعال باشد)
    if IS_BOT_ACTIVE:
        schedule.every(CONFIG['POST_INTERVAL_MINUTES']).minutes.do(send_prices_core).tag('main_table')
        print(f"ربات شروع به کار کرد. زمان ارسال جدول اصلی: هر {CONFIG['POST_INTERVAL_MINUTES']} دقیقه.")
    else:
        print("ربات در حالت خاموش آغاز شد. زمان‌بندی ارسال جدول غیرفعال است.")

    # 3. اجرای Polling و Schedule در Thread اصلی
    try:
        polling_thread = threading.Thread(target=lambda: bot.polling(none_stop=True, interval=0.1), daemon=True)
        polling_thread.start()

        while True:
            schedule.run_pending()
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[INFO] ربات با موفقیت متوقف شد.")
    except Exception as e:
        print(f"خطای جدی در حلقه اصلی: {e}")


if __name__ == '__main__':
    run_schedule_and_poll()
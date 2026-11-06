#!/usr/bin/env python3
"""
TradeGuard Pro v7.0 Global — موتور ۶ زبانه بدون نیاز به هیچ پکیج خارجی (Zero-Dependency Pure Python!)
اجرای فوری روی هر نسخه ویندوز، مک و لینوکس (پایتون 3.8 تا 3.15+) بدون نیاز به pip install یا کامپایلر!

پشتیبانی بومی از ۶ زبان اصلی دنیا:
🇮🇷 فارسی (fa) | 🇬🇧 English (en) | 🇷🇺 Русский (ru) | 🇸🇦 العربية (ar) | 🇹🇷 Türkçe (tr) | 🇪🇸 Español (es)

مجهز به:
1) درگاه رسمی Telegram Stars (XTR) + مدیریت خودکار اشتراک ۳۰ روزه در SQLite
2) رادار زنده آن‌چین Hyperliquid + OKX + اشعه ایکس کیف پول نهنگ (/wallet)
3) اسکنر ضد راگ‌پول و هانی‌پات توکن‌ها (/scan) + ماشین‌حساب قانون Consistency پراپ (/consistency)
4) موتور رشد ویروسی (دعوت ۳ دوست = ۷ روز پلن پرو رایگان خودکار) + ارسال فایل‌های .mq5 و .pine
5) پنل مدیریت مؤسس (/admin) + ارسال همگانی (/broadcast) + پست‌گذار خودکار ۸ ساعته کانال
"""

import json
import logging
import os
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tradeguard.db"
ENV_PATH = BASE_DIR / ".env"
EA_FILE_PATH = BASE_DIR / "TradeGuard_PropProtector.mq5"
PINE_FILE_PATH = BASE_DIR / "TradeGuard_SmartRadar.pine"

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tradeguard")


# =====================================================================
# خواننده داخلی فایل .env (بدون نیاز به نصب python-dotenv)
# =====================================================================
def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def save_env_var(key: str, val: str) -> None:
    lines: List[str] = []
    found = False
    if ENV_PATH.exists():
        for raw in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            if raw.strip().startswith(f"{key}="):
                lines.append(f"{key}={val}")
                found = True
            else:
                lines.append(raw)
    if not found:
        lines.append(f"{key}={val}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


load_env_file(ENV_PATH)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
MINI_APP_URL = os.environ.get("MINI_APP_URL", "https://example.com").strip()
SUBSCRIPTION_STARS = int(os.environ.get("SUBSCRIPTION_STARS", "300") or "300")
PUBLIC_CHANNEL_ID = os.environ.get("PUBLIC_CHANNEL_ID", "").strip()

# شناسه عددی خود ربات و وضعیت اعتبار کانال ویترین (در main مقدار می‌گیرند)
BOT_ID: int = 0
CHANNEL_OK: bool = False
CHANNEL_REASON: str = ""
FREE_PRO_INVITE_TARGET = int(os.environ.get("FREE_PRO_INVITE_TARGET", "3") or "3")
ADMIN_USER_ID = os.environ.get("ADMIN_USER_ID", "").strip()

AI_API_BASE = os.environ.get("AI_API_BASE", "https://openrouter.ai/api/v1").rstrip("/")
AI_API_KEY = os.environ.get("AI_API_KEY", "").strip()
AI_MODEL = os.environ.get("AI_MODEL", "google/gemini-2.5-flash").strip()

SUPPORTED_LANGS = ("fa", "en", "ru", "ar", "tr", "es")
LANG_NAMES = {
    "fa": "Persian (فارسی)",
    "en": "English",
    "ru": "Russian (Русский)",
    "ar": "Arabic (العربية)",
    "tr": "Turkish (Türkçe)",
    "es": "Spanish (Español)",
}

# =====================================================================
# دیکشنری ۶ زبانه کامل ربات تلگرام
# =====================================================================
BOT_STRINGS: Dict[str, Dict[str, str]] = {
    "fa": {
        "btn_app": "📱 باز کردن مینی‌اپ تریدگارد",
        "btn_radar": "📡 رادار فاندینگ + نهنگ",
        "btn_ai": "🤖 تحلیل AI Agent",
        "btn_guard": "🛡️ گارد پراپ + خبر",
        "btn_invite": "🎁 ۷ روز پرو رایگان!",
        "btn_lang": "🌐 زبان / Language (🇮🇷)",
        "btn_buy": f"⭐ فعال‌سازی پلن پرو ({SUBSCRIPTION_STARS} Stars)",
        "btn_ea": "📥 دانلود اکسپرت MT5",
        "btn_pine": "📈 دانلود اسکریپت TradingView",
        "welcome": (
            "سلام رفیق تریدر! به *TradeGuard Global v7.0* خوش اومدی 🛡️🌍\n\n"
            "جعبه ابزار حرفه‌ای تریدرهای فارکس، طلا و کریپتو:\n"
            "1️⃣ *رادار فاندینگ + نهنگ‌های آن‌چین:* شکار ارزهای پرتجمع در Hyperliquid و OKX\n"
            "2️⃣ *پکیج گارد پراپ (MT5 + TradingView):* قفل خودکار سر ۳.۸٪ ضرر روزانه + سپر خبر قرمز\n"
            "3️⃣ *دستورات ویژه:* اسکن هانی‌پات `/scan PEPE` | کیف پول نهنگ `/wallet` | پنل مدیر `/admin`\n\n"
            "{status}"
        ),
        "status_pro": "✅ اشتراک *پلن پرو* شما تا `{exp}` فعال است.",
        "status_free": f"🔒 حساب پایه | با *{SUBSCRIPTION_STARS} ⭐* آنی پرو شو یا *{FREE_PRO_INVITE_TARGET} دوست تریدر* دعوت کن!",
        "lang_prompt": "🌍 لطفاً زبان مورد نظر خود را انتخاب کنید:",
        "lang_saved": "✅ زبان ربات و مینی‌اپ به *فارسی 🇮🇷* تغییر کرد!",
        "scanning": "در حال اسکن زنده فاندینگ و نقدینگی آن‌چین...",
        "radar_head": "📡 *رادار زنده فاندینگ‌ریت + نهنگ‌های آن‌چین:*\n",
        "radar_locked": "\n🔒 _{rem} فرصت داغ دیگر ویژه اعضای «پلن پرو» است._",
        "invite_body": (
            "🎁 *۷ روز پلن پرو کاملاً رایگان!*\n\n"
            f"لینک اختصاصی زیر را برای *{FREE_PRO_INVITE_TARGET} دوست تریدر* بفرست؛ "
            "به محض استارت، دانلود MT5 و TradingView به مدت ۷ روز برایت رایگان باز می‌شود!\n\n"
            "🔗 لینک اختصاصی تو:\n`{link}`\n\n"
            "📊 دعوت‌های تو: *{count} از {target}*"
        ),
        "ref_new": "🔥 یک تریدر جدید با لینک تو وارد شد! پیشرفت: *{count}/{target}*",
        "ref_unlocked": "🎉 *تبریک! ۳ دعوت تکمیل شد و ۷ روز پلن پرو رایگان برایت فعال شد!*",
        "need_pro": "این قابلیت ویژه اعضای پلن پرو است ⭐",
        "ai_thinking": "ایجنت هوشمند در حال تحلیل بازار...",
        "guard_info": (
            "🛡️ *قوانین طلایی محافظت از حساب پراپ:*\n\n"
            "• *تارگت آرام روزانه (+0.1%):* روی حساب ۱۰ هزار دلاری = روزی ۱۰ دلار بدون استرس.\n"
            "• *اکسپرت گارد MT5:* بستن خودکار معاملات در `-3.8%` قبل از سوختن چالش ۵٪.\n"
            "• *سپر قانون Consistency:* با دستور `/consistency 1200 600 40` سلامت برداشت سودت را چک کن!\n"
            "• *اندیکاتور SmartRadar:* نمایش PDH/PDL و حجم امن مستقیم روی چارت TradingView."
        ),
        "ea_cap": "✅ *اکسپرت محافظ پراپ (MetaTrader 5)*\nدر پوشه `MQL5/Experts` کپی و Compile کنید.",
        "pine_cap": "✅ *اندیکاتور اختصاصی TradingView (Pine v5)*\nکد را در `Pine Editor` کپی کرده و `Add to chart` بزنید.",
        "inv_title": "پلن پرو تریدگارد (۳۰ روزه)",
        "inv_desc": "رادار کامل آن‌چین + تحلیل AI Agent + دانلود اکسپرت MT5 و اندیکاتور TradingView",
        "inv_label": "اشتراک ۳۰ روزه TradeGuard Pro",
        "paid_ok": "🎉 *پرداخت موفق!*\nپلن پرو تا تاریخ `{exp}` فعال شد. اکنون فایل‌های MT5 و TradingView آماده دانلود هستند:",
    },
    "en": {
        "btn_app": "📱 Launch TradeGuard Mini-App",
        "btn_radar": "📡 Live Funding & Whales",
        "btn_ai": "🤖 AI Market Brief",
        "btn_guard": "🛡️ Prop Guard & News",
        "btn_invite": "🎁 7 Days Free Pro!",
        "btn_lang": "🌐 Language (🇬🇧 EN)",
        "btn_buy": f"⭐ Unlock Pro Now ({SUBSCRIPTION_STARS} Stars)",
        "btn_ea": "📥 Download MT5 EA",
        "btn_pine": "📈 Download TradingView Script",
        "welcome": (
            "Welcome to *TradeGuard Global v7.0* 🛡️🌍\n\n"
            "The all-in-one risk & alpha suite for Forex, Gold & Crypto traders:\n"
            "1️⃣ *Live Funding & Whale Radar:* Real-time Hyperliquid & OKX alpha\n"
            "2️⃣ *Prop-Firm Protection (MT5 + TradingView):* Auto `-3.8%` daily stop + Consistency Shield\n"
            "3️⃣ *Power Commands:* Anti-Rug `/scan PEPE` | Whale X-Ray `/wallet` | `/consistency`\n\n"
            "{status}"
        ),
        "status_pro": "✅ Your *Pro Plan* is active until `{exp}`.",
        "status_free": f"🔒 Basic Plan | Unlock instantly for *{SUBSCRIPTION_STARS} ⭐* or invite *{FREE_PRO_INVITE_TARGET} friends* for 7 days Free Pro!",
        "lang_prompt": "🌍 Choose your preferred language:",
        "lang_saved": "✅ Language switched to *English 🇬🇧*!",
        "scanning": "Scanning live on-chain funding & whale OI...",
        "radar_head": "📡 *Live Funding Rate & Whale OI Radar:*\n",
        "radar_locked": "\n🔒 _{rem} more extreme funding pairs are locked in Pro Plan._",
        "invite_body": (
            "🎁 *Get 7 Days of TradeGuard PRO Free!*\n\n"
            f"Share your personal link with *{FREE_PRO_INVITE_TARGET} trader friends* — "
            "once they start the bot, MT5 EA & TradingView downloads unlock automatically!\n\n"
            "🔗 Your referral link:\n`{link}`\n\n"
            "📊 Progress: *{count} / {target} referrals*"
        ),
        "ref_new": "🔥 New trader joined via your link! Progress: *{count}/{target}*",
        "ref_unlocked": "🎉 *Congrats! 3 referrals completed — 7 Days of PRO unlocked for free!*",
        "need_pro": "This feature requires TradeGuard Pro ⭐",
        "ai_thinking": "AI Risk Agent is analyzing live markets...",
        "guard_info": (
            "🛡️ *TradeGuard Prop-Firm Protection Suite:*\n\n"
            "• *Calm +0.1% Daily Goal:* $10/day on a $10k account without over-leveraging.\n"
            "• *MT5 PropProtector EA:* Auto-closes trades at `-3.8%` before hitting your 5% daily breach.\n"
            "• *Consistency Check:* Run `/consistency 1200 600 40` to verify payout eligibility.\n"
            "• *TradingView SmartRadar:* Plots PDH/PDL liquidity zones & safe lot size on chart."
        ),
        "ea_cap": "✅ *TradeGuard PropProtector (MetaTrader 5)*\nCopy into `MQL5/Experts` and click Compile.",
        "pine_cap": "✅ *TradeGuard SmartRadar (Pine Script v5)*\nPaste into TradingView `Pine Editor` and click `Add to chart`.",
        "inv_title": "TradeGuard PRO (30 Days)",
        "inv_desc": "Unlimited On-Chain Whale & Funding Radar + AI Risk Agent + MT5 EA & TradingView Script",
        "inv_label": "TradeGuard Pro — 30 Days",
        "paid_ok": "🎉 *Payment Successful!*\nYour PRO Plan is active until `{exp}`. Download your MT5 & TradingView tools below:",
    },
    "ru": {
        "btn_app": "📱 Открыть Mini-App TradeGuard",
        "btn_radar": "📡 Радар фандинга и китов",
        "btn_ai": "🤖 ИИ-анализ рынка",
        "btn_guard": "🛡️ Защита пропа",
        "btn_invite": "🎁 7 дней PRO бесплатно!",
        "btn_lang": "🌐 Язык / Language (🇷🇺)",
        "btn_buy": f"⭐ Активировать PRO ({SUBSCRIPTION_STARS} Stars)",
        "btn_ea": "📥 Скачать советник MT5",
        "btn_pine": "📈 Скачать скрипт TradingView",
        "welcome": (
            "Добро пожаловать в *TradeGuard Global v7.0* 🛡️🌍\n\n"
            "Профессиональный терминал для проп- и крипто-трейдеров:\n"
            "1️⃣ *Живой радар фандинга и китов:* Hyperliquid и OKX онлайн\n"
            "2️⃣ *Защита проп-счёта (MT5 + TradingView):* авто-стоп при `-3.8%` просадки\n"
            "3️⃣ *Команды:* анти-скам `/scan PEPE` | киты `/wallet` | `/consistency`\n\n"
            "{status}"
        ),
        "status_pro": "✅ Ваш тариф *PRO* активен до `{exp}`.",
        "status_free": f"🔒 Базовый тариф | Откройте PRO за *{SUBSCRIPTION_STARS} ⭐* или пригласите *{FREE_PRO_INVITE_TARGET} друзей*!",
        "lang_prompt": "🌍 Выберите язык интерфейса:",
        "lang_saved": "✅ Язык переключён на *Русский 🇷🇺*!",
        "scanning": "Сканируем живой фандинг и объёмы китов...",
        "radar_head": "📡 *Живой радар фандинга и открытого интереса:*\n",
        "radar_locked": "\n🔒 _Ещё {rem} горячих пар открыты только в тарифе PRO._",
        "invite_body": (
            "🎁 *7 дней тарифа PRO бесплатно!*\n\n"
            f"Отправьте ссылку *{FREE_PRO_INVITE_TARGET} друзьям-трейдерам* — "
            "после старта откроется скачивание советника MT5 и индикатора TradingView!\n\n"
            "🔗 Ваша ссылка:\n`{link}`\n\n"
            "📊 Приглашено: *{count} из {target}*"
        ),
        "ref_new": "🔥 По вашей ссылке зашёл новый трейдер! Прогресс: *{count}/{target}*",
        "ref_unlocked": "🎉 *Поздравляем! 3 друга приглашены — вам начислено 7 дней PRO бесплатно!*",
        "need_pro": "Доступно в тарифе PRO ⭐",
        "ai_thinking": "ИИ-агент анализирует рынок...",
        "guard_info": (
            "🛡️ *Защита проп-аккаунта TradeGuard:*\n\n"
            "• *Советник MT5:* авто-закрытие всех сделок при `-3.8%` до нарушения лимита 5%.\n"
            "• *Consistency Rule:* проверьте выплату командой `/consistency 1200 600 40`.\n"
            "• *Индикатор SmartRadar:* уровни PDH/PDL и безопасный лот прямо на графике."
        ),
        "ea_cap": "✅ *Советник защиты пропа (MetaTrader 5)*\nСкопируйте в `MQL5/Experts` и нажмите Compile.",
        "pine_cap": "✅ *Индикатор TradingView (Pine v5)*\nВставьте код в `Pine Editor` и нажмите `Add to chart`.",
        "inv_title": "TradeGuard PRO (30 дней)",
        "inv_desc": "Безлимитный ончейн-радар + ИИ-аналитика + советник MT5 и скрипт TradingView",
        "inv_label": "Подписка TradeGuard PRO (30 дней)",
        "paid_ok": "🎉 *Оплата прошла успешно!*\nТариф PRO активен до `{exp}`. Скачивайте файлы ниже:",
    },
    "ar": {
        "btn_app": "📱 فتح تطبيق TradeGuard",
        "btn_radar": "📡 رادار التمويل والحيتان",
        "btn_ai": "🤖 تحليل الذكاء الاصطناعي",
        "btn_guard": "🛡️ حارس حساب التمويل",
        "btn_invite": "🎁 7 أيام PRO مجاناً!",
        "btn_lang": "🌐 اللغة / Language (🇸🇦)",
        "btn_buy": f"⭐ تفعيل PRO فوري ({SUBSCRIPTION_STARS} نجمة)",
        "btn_ea": "📥 تحميل اكسبيرت MT5",
        "btn_pine": "📈 تحميل مؤشر TradingView",
        "welcome": (
            "مرحباً بك في *TradeGuard Global v7.0* 🛡️🌍\n\n"
            "منصة حماية المخاطر لمتداولي الفوركس والذهب والكريبتو:\n"
            "1️⃣ *رادار التمويل والحيتان الحي:* بيانات Hyperliquid و OKX لحظة بلحظة\n"
            "2️⃣ *حماية حسابات التمويل (MT5 + TradingView):* إغلاق آلي عند `-3.8%` يومياً\n"
            "3️⃣ *أوامر سريعة:* فحص العملات `/scan PEPE` | محفظة الحوت `/wallet`\n\n"
            "{status}"
        ),
        "status_pro": "✅ اشتراك *PRO* مفعل حتى `{exp}`.",
        "status_free": f"🔒 الحساب الأساسي | فعّل PRO بـ *{SUBSCRIPTION_STARS} ⭐* أو ادعُ *{FREE_PRO_INVITE_TARGET} أصدقاء*!",
        "lang_prompt": "🌍 اختر لغتك المفضلة:",
        "lang_saved": "✅ تم تغيير اللغة إلى *العربية 🇸🇦*!",
        "scanning": "جاري فحص معدلات التمويل وعقود الحيتان...",
        "radar_head": "📡 *رادار معدلات التمويل والسيولة الحي:*\n",
        "radar_locked": "\n🔒 _توجد {rem} فرص إضافية مفتوحة لمشتركي PRO فقط._",
        "invite_body": (
            "🎁 *احصل على 7 أيام PRO مجاناً!*\n\n"
            f"شارك رابطك مع *{FREE_PRO_INVITE_TARGET} أصدقاء متداولين* لفتح تحميل اكسبيرت MT5 ومؤشر TradingView مجاناً!\n\n"
            "🔗 رابط الدعوة:\n`{link}`\n\n"
            "📊 الدعوات المسجلة: *{count} من {target}*"
        ),
        "ref_new": "🔥 انضم متداول جديد عبر رابطك! التقدم: *{count}/{target}*",
        "ref_unlocked": "🎉 *مبروك! اكتملت 3 دعوات وتم تفعيل 7 أيام PRO مجاناً!*",
        "need_pro": "هذه الميزة مخصصة لمشتركي PRO ⭐",
        "ai_thinking": "جاري تحليل بيانات السوق...",
        "guard_info": (
            "🛡️ *قواعد حماية حساب التمويل:*\n\n"
            "• *اكسبيرت MT5:* إغلاق تلقائي لجميع الصفقات عند `-3.8%` قبل كسر حد 5%.\n"
            "• *فحص الاستمرارية:* استخدم `/consistency 1200 600 40` للتحقق من شروط السحب.\n"
            "• *مؤشر SmartRadar:* يرسم مناطق سيولة الأمس واللوت الآمن مباشرة على الشارت."
        ),
        "ea_cap": "✅ *اكسبيرت الحماية (MetaTrader 5)*\nانسخه إلى مجلد `MQL5/Experts` واضغط Compile.",
        "pine_cap": "✅ *مؤشر TradingView (Pine v5)*\nالصق الكود داخل `Pine Editor` واضغط `Add to chart`.",
        "inv_title": "اشتراك TradeGuard PRO (30 يوماً)",
        "inv_desc": "رادار حيتان وتمويل كامل + ذكاء اصطناعي + اكسبيرت MT5 ومؤشر TradingView",
        "inv_label": "اشتراك 30 يوماً TradeGuard PRO",
        "paid_ok": "🎉 *تم الدفع بنجاح!*\nاشتراك PRO نشط حتى `{exp}`. يمكنك تحميل الأدوات الآن:",
    },
    "tr": {
        "btn_app": "📱 TradeGuard Uygulamasını Aç",
        "btn_radar": "📡 Canlı Fonlama & Balina",
        "btn_ai": "🤖 Yapay Zeka Analizi",
        "btn_guard": "🛡️ Prop Kalkanı",
        "btn_invite": "🎁 7 Gün Ücretsiz PRO!",
        "btn_lang": "🌐 Dil / Language (🇹🇷)",
        "btn_buy": f"⭐ PRO Paketi Aç ({SUBSCRIPTION_STARS} Stars)",
        "btn_ea": "📥 MT5 Botunu İndir",
        "btn_pine": "📈 TradingView İndikatörü",
        "welcome": (
            "*TradeGuard Global v7.0*'a Hoş Geldiniz 🛡️🌍\n\n"
            "Forex, Altın ve Kripto traderları için profesyonel koruma paketi:\n"
            "1️⃣ *Canlı Fonlama & Balina Radarı:* Anlık Hyperliquid ve OKX verileri\n"
            "2️⃣ *Prop Hesap Kalkanı (MT5 + TradingView):* Günlük `-3.8%` otomatik kapatma\n"
            "3️⃣ *Komutlar:* Güvenlik tarama `/scan PEPE` | Balina `/wallet`\n\n"
            "{status}"
        ),
        "status_pro": "✅ *PRO Paketiniz* `{exp}` tarihine kadar aktif.",
        "status_free": f"🔒 Temel Hesap | *{SUBSCRIPTION_STARS} ⭐* ile anında PRO açın veya *{FREE_PRO_INVITE_TARGET} arkadaş* davet edin!",
        "lang_prompt": "🌍 Lütfen dilinizi seçin:",
        "lang_saved": "✅ Dil *Türkçe 🇹🇷* olarak güncellendi!",
        "scanning": "Canlı fonlama ve balina pozisyonları taranıyor...",
        "radar_head": "📡 *Canlı Fonlama Oranı & Balina OI Radarı:*\n",
        "radar_locked": "\n🔒 _{rem} sıcak fırsat daha PRO pakette açık._",
        "invite_body": (
            "🎁 *7 Gün Ücretsiz PRO Kazanın!*\n\n"
            f"Özel linkinizi *{FREE_PRO_INVITE_TARGET} trader arkadaşınızla* paylaşın; "
            "MT5 ve TradingView dosyaları ücretsiz açılsın!\n\n"
            "🔗 Davet linkiniz:\n`{link}`\n\n"
            "📊 İlerleme: *{count} / {target} davet*"
        ),
        "ref_new": "🔥 Linkinizle yeni bir trader katıldı! İlerleme: *{count}/{target}*",
        "ref_unlocked": "🎉 *Tebrikler! 3 davet tamamlandı — 7 Gün Ücretsiz PRO aktif edildi!*",
        "need_pro": "Bu özellik PRO üyeler içindir ⭐",
        "ai_thinking": "Yapay zeka canlı verileri analiz ediyor...",
        "guard_info": (
            "🛡️ *TradeGuard Prop Hesap Koruma Kuralları:*\n\n"
            "• *MT5 PropProtector Botu:* Günlük kayıp `-3.8%` olduğunda işlemleri otomatik kapatır.\n"
            "• *Consistency Kontrolü:* `/consistency 1200 600 40` komutuyla çekim kuralını test edin.\n"
            "• *SmartRadar İndikatörü:* PDH/PDL likidite bölgelerini grafikte gösterir."
        ),
        "ea_cap": "✅ *MT5 Prop Koruma Uzmanı*\n`MQL5/Experts` klasörüne kopyalayıp Compile edin.",
        "pine_cap": "✅ *TradingView İndikatörü (Pine v5)*\nKodu `Pine Editor` içine yapıştırıp `Add to chart` tıklayın.",
        "inv_title": "TradeGuard PRO (30 Gün)",
        "inv_desc": "Sınırsız Balina & Fonlama Radarı + Yapay Zeka + MT5 Uzmanı ve TradingView İndikatörü",
        "inv_label": "TradeGuard PRO — 30 Gün",
        "paid_ok": "🎉 *Ödeme Başarılı!*\nPRO paketiniz `{exp}` tarihine kadar aktif. Dosyalarınızı aşağıdan indirebilirsiniz:",
    },
    "es": {
        "btn_app": "📱 Abrir Mini-App TradeGuard",
        "btn_radar": "📡 Radar Funding y Ballenas",
        "btn_ai": "🤖 Resumen IA de Mercado",
        "btn_guard": "🛡️ Escudo Prop Firm",
        "btn_invite": "🎁 ¡7 Días PRO Gratis!",
        "btn_lang": "🌐 Idioma / Language (🇪🇸)",
        "btn_buy": f"⭐ Activar PRO ({SUBSCRIPTION_STARS} Stars)",
        "btn_ea": "📥 Descargar EA MT5",
        "btn_pine": "📈 Descargar Script TradingView",
        "welcome": (
            "¡Bienvenido a *TradeGuard Global v7.0*! 🛡️🌍\n\n"
            "Suite profesional de riesgo para traders de Forex, Oro y Cripto:\n"
            "1️⃣ *Radar en Vivo de Funding y Ballenas:* Hyperliquid y OKX al instante\n"
            "2️⃣ *Escudo Prop Firm (MT5 + TradingView):* Cierre automático diario en `-3.8%`\n"
            "3️⃣ *Comandos:* Escáner `/scan PEPE` | Ballenas `/wallet` | `/consistency`\n\n"
            "{status}"
        ),
        "status_pro": "✅ Tu *Plan PRO* está activo hasta `{exp}`.",
        "status_free": f"🔒 Plan Básico | Activa PRO por *{SUBSCRIPTION_STARS} ⭐* o invita a *{FREE_PRO_INVITE_TARGET} amigos*!",
        "lang_prompt": "🌍 Selecciona tu idioma preferido:",
        "lang_saved": "✅ ¡Idioma cambiado a *Español 🇪🇸*!",
        "scanning": "Escaneando tasas de funding y ballenas en vivo...",
        "radar_head": "📡 *Radar en Vivo de Funding Rate y Ballenas:*\n",
        "radar_locked": "\n🔒 _{rem} pares extremos más desbloqueados en el Plan PRO._",
        "invite_body": (
            "🎁 *¡Obtén 7 Días de TradeGuard PRO Gratis!*\n\n"
            f"Comparte tu enlace con *{FREE_PRO_INVITE_TARGET} amigos traders* — "
            "¡al iniciar el bot se desbloquean MT5 y TradingView gratis!\n\n"
            "🔗 Tu enlace:\n`{link}`\n\n"
            "📊 Progreso: *{count} / {target} invitados*"
        ),
        "ref_new": "🔥 ¡Nuevo trader registrado con tu enlace! Progreso: *{count}/{target}*",
        "ref_unlocked": "🎉 *¡Felicidades! 3 invitados completados — 7 Días PRO activados gratis!*",
        "need_pro": "Esta función requiere el Plan PRO ⭐",
        "ai_thinking": "El Agente IA está analizando el mercado...",
        "guard_info": (
            "🛡️ *Escudo de Protección para Cuentas de Fondeo:*\n\n"
            "• *EA MT5 PropProtector:* Cierra todas las órdenes en `-3.8%` antes de perder la cuenta.\n"
            "• *Regla de Consistencia:* Usa `/consistency 1200 600 40` para verificar tu retiro.\n"
            "• *SmartRadar TradingView:* Dibuja liquidez PDH/PDL y lotaje seguro en el gráfico."
        ),
        "ea_cap": "✅ *Expert Advisor PropProtector (MetaTrader 5)*\nCópialo en `MQL5/Experts` y pulsa Compile.",
        "pine_cap": "✅ *Indicador SmartRadar (Pine Script v5)*\nPega el código en `Pine Editor` de TradingView y pulsa `Add to chart`.",
        "inv_title": "TradeGuard PRO (30 Días)",
        "inv_desc": "Radar On-Chain Ilimitado + Agente IA + EA para MT5 e Indicador TradingView",
        "inv_label": "Suscripción TradeGuard PRO — 30 Días",
        "paid_ok": "🎉 *¡Pago Exitoso!*\nTu Plan PRO está activo hasta `{exp}`. Descarga tus herramientas abajo:",
    },
}


def normalize_lang(code: Optional[str]) -> str:
    if not code:
        return "fa"
    short = code[:2].lower()
    return short if short in SUPPORTED_LANGS else "en"


def tr(lang: str, key: str, **kwargs) -> str:
    d = BOT_STRINGS.get(lang, BOT_STRINGS["en"])
    txt = d.get(key) or BOT_STRINGS["en"].get(key, "")
    return txt.format(**kwargs) if kwargs else txt


def is_real_app_url(url: str) -> bool:
    if not url or not url.startswith("https://"):
        return False
    placeholders = ("example.com", "your-tradeguard-app.pages.dev", "your-domain")
    return not any(p in url for p in placeholders)


def build_app_url(lang: str) -> str:
    url = MINI_APP_URL if is_real_app_url(MINI_APP_URL) else ""
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(url)
        q = dict(urllib.parse.parse_qsl(parsed.query))
        q["lang"] = lang
        return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(q)))
    except Exception:
        return url


# =====================================================================
# کلاینت مستقیم Telegram Bot API با کتابخانه استاندارد پایتون (بدون پکیج!)
# =====================================================================
def http_json(url: str, method: str = "GET", payload: Optional[dict] = None, headers: Optional[dict] = None, timeout: float = 12.0) -> dict:
    req_headers = {"User-Agent": "TradeGuardBot/7.0", "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def tg_call(method_name: str, payload: Optional[dict] = None, timeout: float = 15.0) -> dict:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method_name}"
    try:
        return http_json(url, method="POST", payload=payload or {}, timeout=timeout)
    except urllib.error.HTTPError as e:
        err_txt = e.read().decode("utf-8", errors="ignore")
        logger.warning("Telegram API error on %s: %s", method_name, err_txt)
        return {"ok": False, "description": err_txt}
    except Exception as exc:
        logger.warning("Network error on %s: %s", method_name, exc)
        return {"ok": False, "description": str(exc)}


def is_self_chat(chat_id: int | str) -> bool:
    """جلوگیری از خطای 403 «bot can't send messages to the bot»."""
    if BOT_ID:
        try:
            if int(str(chat_id).lstrip("@")) == int(BOT_ID):
                return True
        except (TypeError, ValueError):
            pass
    if isinstance(chat_id, str):
        u = chat_id.lstrip("@").lower()
        if BOT_USERNAME and u == BOT_USERNAME.lower():
            return True
        # نام کاربری که به «bot» ختم می‌شود و بخشی از کانال نیست
        if u.endswith("bot") and not u.startswith("channel"):
            return True
    return False


def tg_send_message(chat_id: int | str, text: str, reply_markup: Optional[dict] = None, parse_mode: str = "Markdown") -> dict:
    if is_self_chat(chat_id):
        logger.warning(
            "پیام به خودِ ربات (%s) نادیده گرفته شد — مقدار PUBLIC_CHANNEL_ID را بررسی کنید. "
            "راهنما: دستور /channel در چت ربات.",
            chat_id,
        )
        return {"ok": False, "skipped": "self_chat"}
    payload: dict = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    res = tg_call("sendMessage", payload)

    # ترجمه خطاها به پیام فارسی قابل فهم + راه‌حل خودکار
    if not res.get("ok"):
        desc = str(res.get("description") or "")
        if "can't send messages to the bot" in desc:
            global PUBLIC_CHANNEL_ID
            logger.error(
                "❌ مقصد ارسال خودِ ربات است (%s) — پست خودکار کانال خاموش شد. راه‌حل: /channel", chat_id
            )
            if str(chat_id).lstrip("@") in (str(PUBLIC_CHANNEL_ID).lstrip("@"), str(BOT_ID)):
                PUBLIC_CHANNEL_ID = ""
        elif "chat not found" in desc.lower() or "bot was blocked by the user" in desc:
            logger.warning("⚠️ مقصد %s در دسترس نیست: %s", chat_id, desc[:100])

    if not res.get("ok") and parse_mode:
        payload.pop("parse_mode", None)
        res = tg_call("sendMessage", payload)
    return res


def tg_answer_callback(callback_id: str, text: str = "", show_alert: bool = False) -> None:
    payload: dict = {"callback_query_id": callback_id, "show_alert": show_alert}
    if text:
        payload["text"] = text[:190]
    tg_call("answerCallbackQuery", payload)


def tg_send_document(chat_id: int, file_path: Path, filename: str, caption: str = "") -> dict:
    boundary = f"----TradeGuardBoundary{uuid.uuid4().hex}"
    lines: List[bytes] = []

    def add_field(name: str, value: str) -> None:
        lines.append(f"--{boundary}\r\n".encode())
        lines.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        lines.append(f"{value}\r\n".encode())

    add_field("chat_id", str(chat_id))
    if caption:
        add_field("caption", caption)
        add_field("parse_mode", "Markdown")

    file_bytes = file_path.read_bytes()
    lines.append(f"--{boundary}\r\n".encode())
    lines.append(f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'.encode())
    lines.append(b"Content-Type: text/plain; charset=utf-8\r\n\r\n")
    lines.append(file_bytes + b"\r\n")
    lines.append(f"--{boundary}--\r\n".encode())

    body = b"".join(lines)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": "TradeGuardBot/7.5"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        logger.warning("Telegram API error on sendDocument: %s", raw[:200])
        return {"ok": False, "description": raw}
    except Exception as exc:
        logger.warning("Network error on sendDocument: %s", exc)
        return {"ok": False, "description": str(exc)}


# =====================================================================
# ۱) دیتابیس SQLite (مهاجرت خودکار بدون پاک شدن اطلاعات)
# =====================================================================
_db_lock = threading.Lock()


def init_db() -> None:
    with _db_lock, sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                lang TEXT DEFAULT 'fa',
                referred_by INTEGER,
                referrals_count INTEGER DEFAULT 0,
                free_trial_claimed INTEGER DEFAULT 0,
                pro_until INTEGER DEFAULT 0,
                created_at INTEGER NOT NULL
            )
            """
        )
        cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "lang" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'fa'")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                stars_amount INTEGER NOT NULL,
                telegram_charge_id TEXT NOT NULL,
                paid_at INTEGER NOT NULL
            )
            """
        )


def get_user_lang(user_id: int, fallback_tg_code: Optional[str] = None) -> str:
    with _db_lock, sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row and row[0] in SUPPORTED_LANGS:
            return row[0]
    return normalize_lang(fallback_tg_code)


def set_user_lang(user_id: int, lang: str) -> None:
    if lang not in SUPPORTED_LANGS:
        lang = "en"
    with _db_lock, sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))


def register_user_and_check_referral(
    user_id: int,
    username: Optional[str],
    tg_lang_code: Optional[str],
    referred_by: Optional[int] = None,
) -> Tuple[bool, Optional[int], int, bool]:
    now = int(time.time())
    init_lang = normalize_lang(tg_lang_code)
    with _db_lock, sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if cur.fetchone() is not None:
            return False, None, 0, False

        valid_ref = referred_by if (referred_by and referred_by != user_id) else None
        if valid_ref:
            ref_exists = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (valid_ref,)).fetchone()
            if not ref_exists:
                valid_ref = None

        conn.execute(
            "INSERT INTO users (user_id, username, lang, referred_by, referrals_count, free_trial_claimed, pro_until, created_at) "
            "VALUES (?, ?, ?, ?, 0, 0, 0, ?)",
            (user_id, username or "", init_lang, valid_ref, now),
        )

        if not valid_ref:
            return True, None, 0, False

        conn.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id = ?", (valid_ref,))
        row = conn.execute(
            "SELECT referrals_count, free_trial_claimed, pro_until FROM users WHERE user_id = ?",
            (valid_ref,),
        ).fetchone()
        ref_count, claimed, pro_until = int(row[0]), int(row[1]), int(row[2] or 0)

        unlocked_now = False
        if ref_count >= FREE_PRO_INVITE_TARGET and claimed == 0:
            base_exp = pro_until if pro_until > now else now
            new_exp = base_exp + (7 * 86400)
            conn.execute(
                "UPDATE users SET pro_until = ?, free_trial_claimed = 1 WHERE user_id = ?",
                (new_exp, valid_ref),
            )
            unlocked_now = True

        return True, valid_ref, ref_count, unlocked_now


def get_user_referral_stats(user_id: int) -> Tuple[int, bool]:
    with _db_lock, sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT referrals_count, free_trial_claimed FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return 0, False
        return int(row[0] or 0), bool(row[1])


def is_user_pro(user_id: int) -> Tuple[bool, int]:
    now = int(time.time())
    if ADMIN_USER_ID and str(user_id) == ADMIN_USER_ID:
        return True, now + (365 * 86400)
    with _db_lock, sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT pro_until FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return False, 0
        pro_until = int(row[0] or 0)
        return pro_until > now, pro_until


def activate_pro_subscription(user_id: int, stars: int, charge_id: str, days: int = 30) -> Tuple[int, bool]:
    """
    فعال‌سازی/تمدید اشتراک Pro.
    خروجی: (تاریخ انقضا، آیا پرداخت جدید بود؟)
    اگر همان telegram_charge_id قبلاً ثبت شده باشد، دوباره تمدید نمی‌کند (ضد تکرار).
    """
    now = int(time.time())
    with _db_lock, sqlite3.connect(DB_PATH) as conn:
        dup = conn.execute(
            "SELECT 1 FROM payments WHERE telegram_charge_id = ? LIMIT 1", (charge_id,)
        ).fetchone()
        row = conn.execute("SELECT pro_until FROM users WHERE user_id = ?", (user_id,)).fetchone()

        if dup:
            existing = int(row[0]) if (row and row[0]) else 0
            return existing, False

        if not row:
            # کاربری که بدون /start پرداخت کرده — ردیف بساز تا UPDATE بی‌اثر نماند
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, username, lang, pro_until, created_at) "
                "VALUES (?, '', 'fa', 0, ?)",
                (user_id, now),
            )
            current_expiry = now
        else:
            current_expiry = int(row[0]) if (row[0] and int(row[0]) > now) else now

        new_expiry = current_expiry + (days * 86400)
        conn.execute("UPDATE users SET pro_until = ? WHERE user_id = ?", (new_expiry, user_id))
        conn.execute(
            "INSERT INTO payments (user_id, stars_amount, telegram_charge_id, paid_at) VALUES (?, ?, ?, ?)",
            (user_id, stars, charge_id, now),
        )
    return new_expiry, True


# =====================================================================
# ۲) اسکنر زنده آن‌چین Hyperliquid + OKX + Fear & Greed
# =====================================================================
WATCH_SYMBOLS = ["BTC", "ETH", "SOL", "SUI", "DOGE", "PEPE", "XRP", "WIF", "TON", "HYPE"]


def fetch_fear_greed() -> Tuple[int, str]:
    try:
        res = http_json("https://api.alternative.me/fng/?limit=1", timeout=4.0)
        d = (res.get("data") or [{}])[0]
        return int(d.get("value") or 50), str(d.get("value_classification") or "Neutral")
    except Exception:
        return 50, "Neutral"


def run_token_scan_reply(chat_id: int, q: str) -> bool:
    chain_map = {"ethereum": "1", "bsc": "56", "polygon": "137", "arbitrum": "42161", "base": "8453"}
    try:
        ds = http_json(f"https://api.dexscreener.com/latest/dex/search?q={urllib.parse.quote(q)}", timeout=7.0)
        pairs = ds.get("pairs") or []
        if not pairs:
            return False
        pairs.sort(key=lambda x: float((x.get("liquidity") or {}).get("usd") or 0), reverse=True)
        top = pairs[0]
        base = top.get("baseToken") or {}
        chain = str(top.get("chainId") or "").lower()
        addr = str(base.get("address") or "")
        px = str(top.get("priceUsd") or "0")
        liq = float((top.get("liquidity") or {}).get("usd") or 0)
        hp, btax, stax = False, 0.0, 0.0
        if chain in chain_map and addr.startswith("0x"):
            gp = http_json(
                f"https://api.gopluslabs.io/api/v1/token_security/{chain_map[chain]}?contract_addresses={addr}",
                timeout=6.0,
            )
            res_map = gp.get("result") or {}
            info = next(iter(res_map.values()), {}) if res_map else {}
            hp = str(info.get("is_honeypot", "0")) == "1"
            btax = round(float(info.get("buy_tax") or 0) * 100, 1)
            stax = round(float(info.get("sell_tax") or 0) * 100, 1)
        score = max(5, min(100, 100 - (85 if hp else 0) - (35 if stax > 10 else 0) - (30 if liq < 20000 else 0)))
        badge = "🟢 SAFE" if score >= 80 else ("🟡 CAUTION" if score >= 50 else "🔴 DANGER")
        tg_send_message(
            chat_id,
            f"🛡️ *Token Security Scan: ${base.get('symbol')} ({chain.upper()})*\n"
            f"• Price: *${px}* | Score: *{score}/100 ({badge})*\n"
            f"• DEX Liquidity: *${liq:,.0f}*\n"
            f"• Honeypot: *{'YES 🚨' if hp else 'NO ✓'}*\n"
            f"• Tax (Buy / Sell): *{btax}% / {stax}%*\n"
            f"• Contract: `{addr}`",
        )
        return True
    except Exception:
        return False


def fetch_live_funding_and_oi() -> List[Dict]:
    results: List[Dict] = []
    try:
        data = http_json(
            "https://api.hyperliquid.xyz/info",
            method="POST",
            payload={"type": "metaAndAssetCtxs"},
            timeout=6.5,
        )
        universe = data[0].get("universe", [])
        ctxs = data[1]
        for meta, ctx in zip(universe, ctxs):
            sym = meta.get("name", "")
            if sym in WATCH_SYMBOLS:
                hourly_rate = float(ctx.get("funding", 0.0))
                rate_8h_pct = hourly_rate * 8.0 * 100.0
                oi_usd = float(ctx.get("openInterest", 0.0)) * float(ctx.get("markPx", 0.0))
                daily_500 = abs(hourly_rate * 24.0) * 500.0
                tag = "Spot+1xShort" if rate_8h_pct > 0.025 else ("ShortSqueeze↑" if rate_8h_pct < -0.02 else "Neutral")
                results.append(
                    {
                        "sym": sym,
                        "rate_pct": rate_8h_pct,
                        "daily_500": daily_500,
                        "oi_m": oi_usd / 1_000_000.0,
                        "magnet": tag,
                    }
                )
    except Exception:
        pass

    if not results:
        for sym in ["BTC", "ETH", "SOL", "SUI", "DOGE", "PEPE"]:
            try:
                res = http_json(f"https://www.okx.com/api/v5/public/funding-rate?instId={sym}-USDT-SWAP", timeout=4.0)
                arr = res.get("data") or []
                if arr:
                    rate_raw = float(arr[0].get("fundingRate", 0.0))
                    rate_pct = rate_raw * 100.0
                    results.append(
                        {
                            "sym": sym,
                            "rate_pct": rate_pct,
                            "daily_500": abs(rate_raw) * 3 * 500.0,
                            "oi_m": 0.0,
                            "magnet": "Spot+1xShort" if rate_pct > 0.025 else "Neutral",
                        }
                    )
            except Exception:
                pass

    if not results:
        results = [
            {"sym": "SUI", "rate_pct": 0.215, "daily_500": 3.22, "oi_m": 184.5, "magnet": "Spot+1xShort"},
            {"sym": "PEPE", "rate_pct": 0.164, "daily_500": 2.46, "oi_m": 142.0, "magnet": "Spot+1xShort"},
            {"sym": "DOGE", "rate_pct": 0.098, "daily_500": 1.47, "oi_m": 410.2, "magnet": "Spot+1xShort"},
            {"sym": "SOL", "rate_pct": 0.054, "daily_500": 0.81, "oi_m": 890.0, "magnet": "Neutral"},
            {"sym": "BTC", "rate_pct": 0.018, "daily_500": 0.27, "oi_m": 3240.0, "magnet": "Neutral"},
        ]

    results.sort(key=lambda x: abs(x["rate_pct"]), reverse=True)
    return results


# =====================================================================
# ۳) ماژول AI Agent چندزبانه
# =====================================================================
def ask_ai_market_agent(rates: List[Dict], lang: str = "fa") -> str:
    top_summary = ", ".join([f"{r['sym']}: {r['rate_pct']:+.3f}%/8h ({r['magnet']})" for r in rates[:5]])
    best = rates[0]

    if not AI_API_KEY or "your_key_here" in AI_API_KEY:
        if lang == "fa":
            return (
                f"🤖 *گزارش لحظه‌ای ایجنت هوشمند تریدگارد:*\n\n"
                f"1️⃣ *بالاترین ناهنجاری فاندینگ:* ارز *${best['sym']}* با نرخ `{best['rate_pct']:+.3f}%/8h` ({best['magnet']}).\n"
                f"2️⃣ *پتانسیل دلتا خنثی (۵۰۰$ سرمایه):* حدود *${best['daily_500']:.2f} در روز* بدون ریسک جهت قیمت.\n"
                f"3️⃣ *سپر پراپ:* قفل `-3.8%` متاتریدر ۵ و سپر ۲ دقیقه‌ای خبر قرمز را فعال نگه دارید."
            )
        return (
            f"🤖 *TradeGuard AI Risk Brief:*\n\n"
            f"1️⃣ *Top Funding Anomaly:* *${best['sym']}* at `{best['rate_pct']:+.3f}%/8h` ({best['magnet']}).\n"
            f"2️⃣ *Delta-Neutral Yield ($500 capital):* Est. *${best['daily_500']:.2f}/day* market-neutral.\n"
            f"3️⃣ *Prop Shield:* Keep your MT5 `-3.8%` auto-lock active and avoid trading 2 min around CPI/FOMC."
        )

    lang_label = LANG_NAMES.get(lang, "English")
    prompt = (
        f"You are TradeGuard Pro's institutional Risk & Arbitrage AI Agent. Reply strictly in {lang_label}. "
        "Never give directional gambling signals. Based on live Hyperliquid/OKX funding data "
        f"({top_summary}), write 3 concise bullet points: (1) highest leverage crowding, "
        "(2) delta-neutral funding opportunity, and (3) one prop-firm drawdown discipline reminder."
    )
    try:
        res = http_json(
            f"{AI_API_BASE}/chat/completions",
            method="POST",
            payload={"model": AI_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3},
            headers={"Authorization": f"Bearer {AI_API_KEY}"},
            timeout=15.0,
        )
        return res["choices"][0]["message"]["content"].strip()
    except Exception:
        return f"🤖 *${best['sym']}* `{best['rate_pct']:+.3f}%/8h` | Est. $500 yield: `${best['daily_500']:.2f}/day`"


# =====================================================================
# ۴) کیبوردهای ۶ زبانه + ثبت خودکار منوی دکمه‌ای آبی تلگرام
# =====================================================================
def sync_telegram_menus() -> None:
    en_cmds = [
        {"command": "start", "description": "🚀 Main Dashboard & Mini-App"},
        {"command": "lang", "description": "🌐 Change Language (6 Languages)"},
        {"command": "lot", "description": "🧮 Prop Lot Calculator (XAUUSD/Forex/BTC)"},
        {"command": "scan", "description": "🛡️ Token Anti-Rug & Honeypot Scanner"},
        {"command": "wallet", "description": "🐋 Hyperliquid Whale Wallet X-Ray"},
        {"command": "consistency", "description": "⚖️ Prop Firm Consistency Check"},
        {"command": "pro", "description": "⭐ Unlock TradeGuard PRO (Stars)"},
        {"command": "check", "description": "🩺 Health Check"},
        {"command": "stars", "description": "⭐ Star Balance & Sales"},
        {"command": "admin", "description": "👑 Founder Revenue & Stats Panel"},
    ]
    fa_cmds = [
        {"command": "start", "description": "🚀 منوی اصلی و اجرای مینی‌اپ"},
        {"command": "lang", "description": "🌐 تغییر زبان (۶ زبان دنیا)"},
        {"command": "lot", "description": "🧮 محاسبه حجم لات پراپ (طلا/فارکس/کریپتو)"},
        {"command": "scan", "description": "🛡️ اسکن هانی‌پات و امنیت ارزها"},
        {"command": "wallet", "description": "🐋 ردیاب کیف پول نهنگ‌ها"},
        {"command": "consistency", "description": "⚖️ تست قانون Consistency پراپ"},
        {"command": "pro", "description": "⭐ فعال‌سازی اشتراک ویژه Pro"},
        {"command": "check", "description": "🩺 بررسی سلامت و وضعیت ربات"},
        {"command": "stars", "description": "⭐ موجودی استارز و فروش‌ها"},
        {"command": "admin", "description": "👑 پنل مدیریت و آمار درآمد مؤسس"},
    ]
    tg_call("setMyCommands", {"commands": en_cmds})
    tg_call("setMyCommands", {"commands": fa_cmds, "language_code": "fa"})
    if is_real_app_url(MINI_APP_URL):
        tg_call(
            "setChatMenuButton",
            {
                "menu_button": {
                    "type": "web_app",
                    "text": "📱 TradeGuard",
                    "web_app": {"url": MINI_APP_URL},
                }
            },
        )
    else:
        tg_call("setChatMenuButton", {"menu_button": {"type": "commands"}})


def main_keyboard(is_pro: bool, lang: str = "fa") -> dict:
    app_url = build_app_url(lang)
    first_btn = (
        {"text": tr(lang, "btn_app"), "web_app": {"url": app_url}}
        if app_url
        else {"text": tr(lang, "btn_app"), "callback_data": "app_not_set"}
    )
    rows = [
        [first_btn],
        [
            {"text": tr(lang, "btn_radar"), "callback_data": "radar"},
            {"text": tr(lang, "btn_ai"), "callback_data": "ai_brief"},
        ],
        [
            {"text": tr(lang, "btn_guard"), "callback_data": "prop_guard"},
            {"text": tr(lang, "btn_invite"), "callback_data": "invite_free"},
        ],
        [{"text": tr(lang, "btn_lang"), "callback_data": "lang_menu"}],
    ]
    if not is_pro:
        rows.append([{"text": tr(lang, "btn_buy"), "callback_data": "buy_pro"}])
    else:
        rows.append(
            [
                {"text": tr(lang, "btn_ea"), "callback_data": "download_ea"},
                {"text": tr(lang, "btn_pine"), "callback_data": "download_pine"},
            ]
        )
    return {"inline_keyboard": rows}


def language_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "🇮🇷 فارسی", "callback_data": "setlang_fa"},
                {"text": "🇬🇧 English", "callback_data": "setlang_en"},
            ],
            [
                {"text": "🇷🇺 Русский", "callback_data": "setlang_ru"},
                {"text": "🇸🇦 العربية", "callback_data": "setlang_ar"},
            ],
            [
                {"text": "🇹🇷 Türkçe", "callback_data": "setlang_tr"},
                {"text": "🇪🇸 Español", "callback_data": "setlang_es"},
            ],
        ]
    }


def set_subscription_price(new_price: int) -> int:
    """
    تغییر قیمت اشتراک در زمان اجرا (بدون ری‌استارت).
    متن همه دکمه‌ها و وضعیت‌ها در ۶ زبان هم به‌روز می‌شوند.
    """
    global SUBSCRIPTION_STARS
    old = SUBSCRIPTION_STARS
    if new_price == old:
        return old
    SUBSCRIPTION_STARS = new_price
    patterns = (f"{old} ⭐", f"{old} Stars", f"{old} نجمة", f"{old} Звёзд", f"{old} Yıldız", f"{old} Estrellas")
    for _lang, table in BOT_STRINGS.items():
        if not isinstance(table, dict):
            continue
        for key, val in list(table.items()):
            if isinstance(val, str):
                for pat in patterns:
                    if pat in val:
                        val = val.replace(pat, pat.replace(str(old), str(new_price), 1))
                table[key] = val
    return old


def send_pro_invoice(chat_id: int, lang: str = "fa") -> None:
    tg_call(
        "sendInvoice",
        {
            "chat_id": chat_id,
            "title": tr(lang, "inv_title"),
            "description": tr(lang, "inv_desc"),
            "payload": f"tradeguard_pro_30d_{SUBSCRIPTION_STARS}",
            "provider_token": "",
            "currency": "XTR",
            "prices": [{"label": tr(lang, "inv_label"), "amount": SUBSCRIPTION_STARS}],
        },
    )


# =====================================================================
# ۵) پردازشگر پیام‌ها، دستورات و پرداخت‌های Stars
# =====================================================================
BOT_USERNAME = "TradeGuard_bot"


def handle_message(msg: dict) -> None:
    global MINI_APP_URL, PUBLIC_CHANNEL_ID
    chat_id = msg["chat"]["id"]
    user = msg.get("from") or {}
    uid = int(user.get("id", chat_id))
    uname = user.get("username") or ""
    tg_lang = user.get("language_code")

    # پرداخت موفق Telegram Stars
    if "successful_payment" in msg:
        pay = msg["successful_payment"]
        lang = get_user_lang(uid, tg_lang)
        currency = str(pay.get("currency") or "")
        amount = int(pay.get("total_amount") or 0)
        charge_id = str(pay.get("telegram_payment_charge_id") or "")
        if currency and currency != "XTR":
            logger.warning("پرداخت با ارز غیرمنتظره رد شد: %s (%s)", currency, amount)
            return
        if not charge_id:
            logger.warning("پرداخت بدون telegram_payment_charge_id نادیده گرفته شد (کاربر %s)", uid)
            return

        new_exp, is_new = activate_pro_subscription(
            user_id=uid, stars=amount, charge_id=charge_id, days=30
        )
        exp_str = datetime.fromtimestamp(new_exp, tz=timezone.utc).strftime("%Y-%m-%d")

        if is_new:
            usd = amount * 0.013 * 0.95
            logger.info("💰 فروش جدید: %s ⭐ (≈$%.2f) از کاربر %s | انقضا: %s", amount, usd, uid, exp_str)
            if ADMIN_USER_ID:
                tg_send_message(
                    ADMIN_USER_ID,
                    f"💰 *فروش جدید!*\n\n"
                    f"👤 کاربر: `{uid}` {('@' + uname) if uname else ''}\n"
                    f"⭐ مبلغ: *{amount} Stars* (≈ *${usd:,.2f} USD* خالص)\n"
                    f"📅 اشتراک تا: `{exp_str}`\n"
                    f"🧾 کد پرداخت: `{charge_id[:22]}`",
                )
        else:
            logger.info("پرداخت تکراری نادیده گرفته شد: %s", charge_id[:22])

        tg_send_message(chat_id, tr(lang, "paid_ok", exp=exp_str), reply_markup=main_keyboard(True, lang))
        return

    text = (msg.get("text") or "").strip()
    if not text:
        return

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        ref_id = None
        if len(parts) > 1 and parts[1].startswith("ref_"):
            try:
                ref_id = int(parts[1].replace("ref_", ""))
            except ValueError:
                ref_id = None

        is_new, valid_ref, ref_count, unlocked_now = register_user_and_check_referral(uid, uname, tg_lang, ref_id)
        lang = get_user_lang(uid, tg_lang)

        if is_new and valid_ref:
            ref_lang = get_user_lang(valid_ref, "fa")
            if unlocked_now:
                tg_send_message(valid_ref, tr(ref_lang, "ref_unlocked"), reply_markup=main_keyboard(True, ref_lang))
            else:
                tg_send_message(valid_ref, tr(ref_lang, "ref_new", count=ref_count, target=FREE_PRO_INVITE_TARGET))

        pro, exp = is_user_pro(uid)
        status_line = (
            tr(lang, "status_pro", exp=datetime.fromtimestamp(exp, tz=timezone.utc).strftime("%Y-%m-%d"))
            if pro
            else tr(lang, "status_free")
        )
        tg_send_message(chat_id, tr(lang, "welcome", status=status_line), reply_markup=main_keyboard(pro, lang))
        return

    if text.startswith("/lang"):
        lang = get_user_lang(uid, tg_lang)
        tg_send_message(chat_id, tr(lang, "lang_prompt"), reply_markup=language_keyboard())
        return

    if text.startswith("/pro"):
        lang = get_user_lang(uid, tg_lang)
        send_pro_invoice(chat_id, lang)
        return

    if text.startswith("/wallet"):
        parts = text.split(maxsplit=1)
        addr = parts[1].strip() if len(parts) > 1 else "0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00"
        if not (addr.startswith("0x") and len(addr) == 42):
            tg_send_message(chat_id, "🔎 Usage: `/wallet 0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00`")
            return
        try:
            ch = http_json("https://api.hyperliquid.xyz/info", method="POST", payload={"type": "clearinghouseState", "user": addr}, timeout=8.0)
            ms = ch.get("marginSummary") or {}
            eq = float(ms.get("accountValue") or 0)
            ntl = float(ms.get("totalNtlPos") or 0)
            lines = [
                f"🐋 *Whale X-Ray (`{addr[:6]}…{addr[-4:]}`)*",
                f"💰 Equity: *${eq:,.0f}* | Open Notional: *${ntl:,.0f}*\n",
            ]
            for item in (ch.get("assetPositions") or [])[:5]:
                p = item.get("position") or {}
                szi = float(p.get("szi") or 0)
                if szi == 0:
                    continue
                side = "🟢 LONG" if szi > 0 else "🔴 SHORT"
                val = float(p.get("positionValue") or 0)
                upnl = float(p.get("unrealizedPnl") or 0)
                entry = float(p.get("entryPx") or 0)
                lines.append(f"• *${p.get('coin')}* {side} | `${val:,.0f}` | Entry: `${entry:,.2f}` | uPnL: `${upnl:+,.0f}`")
            if len(lines) == 2:
                lines.append("No open perpetual positions right now.")
            tg_send_message(chat_id, "\n".join(lines))
        except Exception:
            tg_send_message(chat_id, "⚠️ Could not reach Hyperliquid L1 right now.")
        return

    if text.startswith("/scan"):
        parts = text.split(maxsplit=1)
        q = parts[1].strip() if len(parts) > 1 else "PEPE"
        if not run_token_scan_reply(chat_id, q):
            tg_send_message(chat_id, "⚠️ Token not found. Example: `/scan PEPE`")
        return

    if text.startswith("/lot"):
        parts = text.split()
        try:
            bal = float(parts[1]) if len(parts) > 1 else 10000.0
            sl_pips = float(parts[2]) if len(parts) > 2 else 20.0
            asset = (parts[3].upper() if len(parts) > 3 else "XAUUSD")
            risk_pct = float(parts[4]) if len(parts) > 4 else 0.5
        except ValueError:
            tg_send_message(chat_id, "🧮 Usage: `/lot 10000 20 XAUUSD` (Balance, SL Pips/Pts, Asset)")
            return
        pip_val_map = {"XAUUSD": 10.0, "GOLD": 10.0, "EURUSD": 10.0, "GBPUSD": 10.0, "NAS100": 1.0, "US30": 1.0, "BTCUSD": 1.0}
        pv = pip_val_map.get(asset, 10.0)
        risk_usd = bal * (risk_pct / 100.0)
        safe_lot = max(0.01, round(risk_usd / max(1.0, sl_pips * pv), 2))
        tg_send_message(
            chat_id,
            f"🧮 *Prop Safe Lot Calculator ({asset})*\n\n"
            f"• Account Balance: *${bal:,.0f}*\n"
            f"• Risk per Trade ({risk_pct}%): *${risk_usd:,.1f}*\n"
            f"• Stop-Loss Distance: *{sl_pips:g} pips/pts*\n"
            f"✅ *Recommended Safe Lot:* `{safe_lot:.2f} Lot`\n"
            f"🛡️ _8 trades needed in a row to even approach -4% daily lock!_",
        )
        return

    if text.startswith("/consistency"):
        parts = text.split()
        try:
            total = float(parts[1]) if len(parts) > 1 else 1200.0
            best = float(parts[2]) if len(parts) > 2 else 600.0
            cap = float(parts[3]) if len(parts) > 3 else 40.0
        except ValueError:
            tg_send_message(chat_id, "⚖️ Usage: `/consistency 1200 600 40`")
            return
        score = (best / max(1.0, total)) * 100.0
        cap_dec = cap / 100.0
        if score <= cap + 0.01:
            max_today = (cap_dec * total) / (1.0 - cap_dec)
            tg_send_message(
                chat_id,
                f"✅ *Consistency Safe ({score:.1f}% ≤ {cap:.0f}%)*\n"
                f"• Total Profit: `${total:,.0f}` | Best Day: `${best:,.0f}`\n"
                f"• Max Safe Profit Today: *`${max_today:,.0f}`*",
            )
        else:
            need = max(1.0, (best / cap_dec) - total)
            tg_send_message(
                chat_id,
                f"⚠️ *Consistency Breach ({score:.1f}% > {cap:.0f}% Cap)*\n"
                f"• Total Profit: `${total:,.0f}` | Best Day: `${best:,.0f}`\n"
                f"• Extra Profit Needed to Unlock Payout: *`+${need:,.0f}`*",
            )
        return

    if text.startswith("/admin"):
        uid_str = str(uid)
        if ADMIN_USER_ID and uid_str != ADMIN_USER_ID:
            tg_send_message(chat_id, "⛔ دسترسی فقط برای مؤسس ربات مجاز است.")
            return
        now = int(time.time())
        with _db_lock, sqlite3.connect(DB_PATH) as conn:
            total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            active_pro = conn.execute("SELECT COUNT(*) FROM users WHERE pro_until > ?", (now,)).fetchone()[0]
            total_stars = conn.execute("SELECT COALESCE(SUM(stars_amount), 0) FROM payments").fetchone()[0]
            langs = conn.execute("SELECT lang, COUNT(*) FROM users GROUP BY lang").fetchall()
        usd_est = total_stars * 0.013
        lang_str = " | ".join([f"{k.upper()}: {v}" for k, v in langs]) or "—"
        url_status = f"`{MINI_APP_URL}`" if is_real_app_url(MINI_APP_URL) else "⚠️ تنظیم نشده (با `/seturl https://...` تنظیم کنید)"
        admin_kb = (
            {"inline_keyboard": [[{"text": "👑 ثبت من به عنوان ادمین اصلی + باز کردن VIP", "callback_data": "claim_admin"}]]}
            if not ADMIN_USER_ID
            else None
        )
        tg_send_message(
            chat_id,
            f"👑 *پنل مدیریت مؤسس TradeGuard v7.5*\n\n"
            f"👥 کل کاربران ربات: *{total_users}*\n"
            f"⭐ مشترکین فعال پلن پرو: *{active_pro}*\n"
            f"💰 کل استارز دریافتی: *{total_stars} ⭐* (≈ *${usd_est:,.2f} USD*)\n"
            f"🌍 تفکیک زبان کاربران: `{lang_str}`\n"
            f"🔗 لینک مینی‌اپ: {url_status}\n"
            f"📢 کانال ویترین: {('✅ فعال' if CHANNEL_OK else '⚠️ خاموش')} — `{CHANNEL_REASON}`\n\n"
            f"🛠️ *دستورات سریع مدیر (بدون نیاز به ویرایش فایل!):*\n"
            f"• تغییر آنی لینک مینی‌اپ:\n`/seturl https:// لینک-جدید`\n"
            f"• تنظیم کانال پست خودکار:\n`/setchannel @username` یا `/setchannel off`\n"
            f"• وضعیت کانال:\n`/channel`\n"
            f"• هدیه ۳۰ روز اشتراک Pro به کاربر:\n`/grantpro {uid_str}`\n"
            f"• ارسال پیام همگانی:\n`/broadcast متن پیام شما`",
            reply_markup=admin_kb,
        )
        return

    if text.startswith("/seturl"):
        if ADMIN_USER_ID and str(uid) != ADMIN_USER_ID:
            tg_send_message(chat_id, "⛔ فقط ادمین ربات مجاز به تغییر لینک مینی‌اپ است.")
            return
        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip().startswith("https://"):
            tg_send_message(chat_id, "🔗 فرمت صحیح:\n`/seturl https://xxxxxx.lhr.life`")
            return
        MINI_APP_URL = parts[1].strip()
        save_env_var("MINI_APP_URL", MINI_APP_URL)
        sync_telegram_menus()
        lang = get_user_lang(uid, tg_lang)
        pro, _ = is_user_pro(uid)
        tg_send_message(
            chat_id,
            f"✅ *لینک مینی‌اپ بدون نیاز به ری‌استارت ذخیره و فعال شد!*\n🔗 `{MINI_APP_URL}`\n\nهمین الان روی دکمه شیشه‌ای زیر بزنید:",
            reply_markup=main_keyboard(pro, lang),
        )
        return

    if text.startswith("/stars"):
        lang = get_user_lang(uid, tg_lang)
        if ADMIN_USER_ID and str(uid) != ADMIN_USER_ID:
            tg_send_message(chat_id, "⛔ فقط ادمین ربات مجاز است.")
            return
        bal = tg_call("getMyStarBalance")
        tx = tg_call("getStarTransactions", {"limit": 10})
        lines = ["⭐ *درآمد استارز TradeGuard*\n"]

        if bal.get("ok"):
            r = bal.get("result") or {}
            amount = int(r.get("amount") or 0)
            usd = amount * 0.013 * 0.95
            lines.append(f"💰 موجودی قابل برداشت: *{amount:,} ⭐* (≈ *${usd:,.2f} USD* خالص)")
            lines.append("_حداقل برداشت: ۱٬۰۰۰ ⭐ | قفل ۲۱ روزه | Fragment → TON_")
        else:
            lines.append(f"⚠️ خواندن موجودی ناموفق: `{str(bal.get('description'))[:80]}`")

        with _db_lock, sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(stars_amount), 0) FROM payments WHERE stars_amount > 0"
            ).fetchone()
            recent = conn.execute(
                "SELECT user_id, stars_amount, paid_at FROM payments WHERE stars_amount > 0 "
                "ORDER BY id DESC LIMIT 5"
            ).fetchall()
        cnt, total = int(row[0]), int(row[1])
        lines.append(f"\n📊 *فروش‌های ثبت‌شده در دیتابیس:* {cnt} پرداخت | {total:,} ⭐")
        if recent:
            lines.append("\n🧾 آخرین فروش‌ها:")
            for u_id, amt, ts in recent:
                d = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                lines.append(f"• `{d}` — {amt} ⭐ — کاربر `{u_id}`")
        else:
            lines.append("\n_هنوز فروشی ثبت نشده. تست خرید: `/price 1` سپس دکمه خرید._")

        if tx.get("ok"):
            items = ((tx.get("result") or {}).get("transactions")) or []
            if items:
                lines.append(f"\n🏦 آخرین تراکنش‌های تلگرام: {len(items)} مورد")
                for t in items[:5]:
                    kind = t.get("source") or t.get("type") or "—"
                    amt = t.get("amount")
                    lines.append(f"• `{kind}` — {amt} ⭐")

        tg_send_message(chat_id, "\n".join(lines))
        return

    if text.startswith("/price"):
        lang = get_user_lang(uid, tg_lang)
        if ADMIN_USER_ID and str(uid) != ADMIN_USER_ID:
            tg_send_message(chat_id, "⛔ فقط ادمین ربات مجاز است.")
            return
        parts = text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            tg_send_message(
                chat_id,
                f"💲 *قیمت فعلی:* `{SUBSCRIPTION_STARS} ⭐` (≈ *${SUBSCRIPTION_STARS * 0.013 * 0.95:,.2f}* خالص)\n\n"
                f"• تست خرید: `/price 1`\n"
                f"• قیمت واقعی: `/price 300`\n"
                f"• قیمت بالاتر: `/price 1000`",
            )
            return
        new = int(parts[1])
        if not (1 <= new <= 100000):
            tg_send_message(chat_id, "⚠️ قیمت باید بین ۱ تا ۱۰۰٬۰۰۰ استارز باشد.")
            return
        old = set_subscription_price(new)
        save_env_var("SUBSCRIPTION_STARS", str(new))
        pro, _ = is_user_pro(uid)
        tg_send_message(
            chat_id,
            f"✅ *قیمت عوض شد:* `{old} ⭐` ➜ `{new} ⭐`\n"
            f"≈ *${new * 0.013 * 0.95:,.2f}* خالص برای شما\n\n"
            f"در `.env` ذخیره شد — بعد از ری‌استارت هم می‌ماند.\n"
            f"دکمه خرید به‌روز شد: 👇",
            reply_markup=main_keyboard(pro, lang),
        )
        return

    if text.startswith("/check"):
        lang = get_user_lang(uid, tg_lang)
        pro, exp = is_user_pro(uid)
        fng_val, fng_lbl = fetch_fear_greed()
        tg_send_message(
            chat_id,
            f"🩺 *گزارش سلامت TradeGuard*\n\n"
            f"• ربات: ✅ آنلاین (`@{BOT_USERNAME}` / `{BOT_ID}`)\n"
            f"• زبان شما: `{lang.upper()}`\n"
            f"• وضعیت اشتراک: {'✅ Pro' if pro else '🆓 رایگان'}\n"
            f"• لینک مینی‌اپ: {('✅ `' + MINI_APP_URL + '`') if is_real_app_url(MINI_APP_URL) else '⚠️ تنظیم نشده → /seturl'}\n"
            f"• کانال ویترین: {('✅ فعال' if CHANNEL_OK else '⚠️ خاموش')}\n"
            f"• شاخص ترس و طمع: `{fng_val}/100 ({fng_lbl})`\n"
            f"• دیتابیس: `{DB_PATH.name}` ✅\n\n"
            f"_همه سیستم‌ها بررسی شد. اگر جایی ⚠️ دیدید، همان دستور راهنما را بزنید._",
        )
        return

    if text.startswith("/channel"):
        if ADMIN_USER_ID and str(uid) != ADMIN_USER_ID:
            tg_send_message(chat_id, "⛔ فقط ادمین ربات مجاز است.")
            return
        validate_channel_target(silent=True)
        icon = "✅" if CHANNEL_OK else "⚠️"
        tg_send_message(
            chat_id,
            f"{icon} *وضعیت کانال ویترین (پست خودکار هر ۸ ساعت)*\n\n"
            f"• آیدی فعلی: `{PUBLIC_CHANNEL_ID or '— خالی —'}`\n"
            f"• وضعیت: {CHANNEL_REASON}\n\n"
            f"*چطور درستش کنم؟*\n"
            f"۱️⃣ یک کانال عمومی بسازید (نه ربات!)\n"
            f"۲️⃣ ربات را در آن کانال **ادمین** کنید\n"
            f"۳️⃣ همین‌جا بزنید:\n`/setchannel @username_کانال`\n\n"
            f"_اگر پست خودکار نمی‌خواهید، بزنید_ `/setchannel off`",
        )
        return

    if text.startswith("/setchannel"):
        if ADMIN_USER_ID and str(uid) != ADMIN_USER_ID:
            tg_send_message(chat_id, "⛔ فقط ادمین ربات مجاز است.")
            return
        parts = text.split(maxsplit=1)
        val = parts[1].strip() if len(parts) > 1 else ""
        if not val:
            tg_send_message(chat_id, "📢 فرمت: `/setchannel @my_channel` یا `/setchannel off`")
            return
        if val.lower() in ("off", "none", "خاموش", "-"):
            PUBLIC_CHANNEL_ID = ""
            save_env_var("PUBLIC_CHANNEL_ID", "")
            logger.info("📢 پست خودکار کانال خاموش شد.")
            tg_send_message(chat_id, "✅ پست خودکار کانال *خاموش* شد. دیگر هیچ پستی به کانال ارسال نمی‌شود.")
            return
        if not val.startswith("@") and not val.lstrip("-").isdigit():
            val = "@" + val
        old = PUBLIC_CHANNEL_ID
        PUBLIC_CHANNEL_ID = val
        if validate_channel_target(silent=True):
            save_env_var("PUBLIC_CHANNEL_ID", PUBLIC_CHANNEL_ID)
            tg_send_message(chat_id, f"✅ کانال ثبت شد و تأیید شد:\n`{PUBLIC_CHANNEL_ID}`\n\n{CHANNEL_REASON}")
        else:
            PUBLIC_CHANNEL_ID = old
            tg_send_message(
                chat_id,
                f"❌ این کانال تأیید نشد:\n{CHANNEL_REASON}\n\n"
                f"یادآوری: باید یوزرنیم **کانال** باشد و ربات در آن **ادمین** باشد — نه یوزرنیم خود ربات.",
            )
        return

    if text.startswith("/grantpro"):
        if ADMIN_USER_ID and str(uid) != ADMIN_USER_ID:
            tg_send_message(chat_id, "⛔ فقط ادمین ربات مجاز است.")
            return
        parts = text.split()
        target_id = int(parts[1]) if (len(parts) > 1 and parts[1].isdigit()) else uid
        gift_charge = f"admin_gift_{target_id}_{int(time.time())}"
        exp, _ = activate_pro_subscription(target_id, stars=0, charge_id=gift_charge, days=30)
        exp_str = datetime.fromtimestamp(exp, tz=timezone.utc).strftime("%Y-%m-%d")
        tg_send_message(chat_id, f"🎁 اشتراک ۳۰ روزه Pro برای کاربر `{target_id}` تا تاریخ `{exp_str}` فعال شد!")
        return

    if text.startswith("/broadcast"):
        if not ADMIN_USER_ID or str(uid) != ADMIN_USER_ID:
            tg_send_message(chat_id, "⛔ ابتدا دستور `/admin` را بزنید و روی دکمه «ثبت من به عنوان ادمین اصلی» کلیک کنید.")
            return
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            tg_send_message(chat_id, "📢 فرمت صحیح: `/broadcast متن پیام`")
            return
        with _db_lock, sqlite3.connect(DB_PATH) as conn:
            user_ids = [r[0] for r in conn.execute("SELECT user_id FROM users").fetchall()]
        sent = 0
        for tid in user_ids:
            r = tg_send_message(tid, parts[1], parse_mode="")
            if r.get("ok"):
                sent += 1
            time.sleep(0.05)
        tg_send_message(chat_id, f"✅ پیام شما برای *{sent}* کاربر ارسال شد!")
        return

    # ── مسیریاب هوشمند بدون نیاز به اسلش (/) ──
    clean = text.strip()
    if clean.startswith("0x") and len(clean) == 42:
        try:
            ch = http_json("https://api.hyperliquid.xyz/info", method="POST", payload={"type": "clearinghouseState", "user": clean}, timeout=6.0)
            eq = float((ch.get("marginSummary") or {}).get("accountValue") or 0)
            if eq > 10:
                msg_copy = dict(msg)
                msg_copy["text"] = f"/wallet {clean}"
                handle_message(msg_copy)
                return
        except Exception:
            pass
        if run_token_scan_reply(chat_id, clean):
            return

    if 2 <= len(clean) <= 10 and clean.replace("$", "").isalnum() and clean.isascii():
        sym_q = clean.lstrip("$")
        if run_token_scan_reply(chat_id, sym_q):
            return

    # هر پیام متنی دیگر (مثل سلام / منو) -> نمایش منوی شیشه‌ای زبان کاربر
    lang = get_user_lang(uid, tg_lang)
    pro, exp = is_user_pro(uid)
    status_line = (
        tr(lang, "status_pro", exp=datetime.fromtimestamp(exp, tz=timezone.utc).strftime("%Y-%m-%d"))
        if pro
        else tr(lang, "status_free")
    )
    tg_send_message(chat_id, tr(lang, "welcome", status=status_line), reply_markup=main_keyboard(pro, lang))


def handle_callback(cb: dict) -> None:
    global ADMIN_USER_ID
    cb_id = cb["id"]
    data = cb.get("data") or ""
    user = cb.get("from") or {}
    uid = int(user.get("id", 0))
    tg_lang = user.get("language_code")
    chat_id = cb["message"]["chat"]["id"]
    lang = get_user_lang(uid, tg_lang)

    if data == "claim_admin":
        if not ADMIN_USER_ID:
            ADMIN_USER_ID = str(uid)
            save_env_var("ADMIN_USER_ID", ADMIN_USER_ID)
            tg_answer_callback(cb_id, "👑 شما به عنوان ادمین اصلی ثبت شدید!", show_alert=True)
            tg_send_message(
                chat_id,
                f"✅ *تبریک! اکانت شما (`{ADMIN_USER_ID}`) به عنوان مؤسس اصلی قفل شد و اشتراک VIP دائمی برایتان فعال گردید!*",
                reply_markup=main_keyboard(True, lang),
            )
        else:
            tg_answer_callback(cb_id, "ادمین قبلاً ثبت شده است.")
        return

    if data == "app_not_set":
        tg_answer_callback(cb_id)
        tg_send_message(
            chat_id,
            "📱 *اتصال ۱۰ ثانیه‌ای دکمه مینی‌اپ:*\n\n"
            "کافیست لینک امن `https://...` تونل یا هاست خود را با دستور زیر همین‌جا در چت بفرستید (بدون نیاز به ری‌استارت!):\n"
            "`/seturl https://xxxxxx.lhr.life`",
        )
        return

    if data == "lang_menu":
        tg_answer_callback(cb_id)
        tg_send_message(chat_id, tr(lang, "lang_prompt"), reply_markup=language_keyboard())
        return

    if data.startswith("setlang_"):
        new_lang = data.replace("setlang_", "")
        if new_lang not in SUPPORTED_LANGS:
            new_lang = "en"
        set_user_lang(uid, new_lang)
        pro, exp = is_user_pro(uid)
        status_line = (
            tr(new_lang, "status_pro", exp=datetime.fromtimestamp(exp, tz=timezone.utc).strftime("%Y-%m-%d"))
            if pro
            else tr(new_lang, "status_free")
        )
        tg_answer_callback(cb_id)
        tg_send_message(
            chat_id,
            f"{tr(new_lang, 'lang_saved')}\n\n{tr(new_lang, 'welcome', status=status_line)}",
            reply_markup=main_keyboard(pro, new_lang),
        )
        return

    if data == "radar":
        tg_answer_callback(cb_id, tr(lang, "scanning"))
        pro, _ = is_user_pro(uid)
        rates = fetch_live_funding_and_oi()
        fng_val, fng_lbl = fetch_fear_greed()
        lines = [tr(lang, "radar_head"), f"🧭 *Fear & Greed Index:* `{fng_val}/100 ({fng_lbl})`\n"]
        visible = rates if pro else rates[:3]
        for idx, r in enumerate(visible, start=1):
            oi_txt = f" | OI: `${r['oi_m']:.0f}M`" if r.get("oi_m", 0) > 0 else ""
            lines.append(f"{idx}. *${r['sym']}* ➜ `{r['rate_pct']:+.3f}%` ({r['magnet']}){oi_txt} | $500: `${r['daily_500']:.2f}/d`")
        if not pro and len(rates) > 3:
            lines.append(tr(lang, "radar_locked", rem=len(rates) - 3))
        tg_send_message(chat_id, "\n".join(lines), reply_markup=main_keyboard(pro, lang))
        return

    if data == "invite_free":
        tg_answer_callback(cb_id)
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        count, _ = get_user_referral_stats(uid)
        tg_send_message(chat_id, tr(lang, "invite_body", link=ref_link, count=count, target=FREE_PRO_INVITE_TARGET))
        return

    if data == "ai_brief":
        pro, _ = is_user_pro(uid)
        if not pro:
            tg_answer_callback(cb_id, tr(lang, "need_pro"), show_alert=True)
            send_pro_invoice(chat_id, lang)
            return
        tg_answer_callback(cb_id, tr(lang, "ai_thinking"))
        rates = fetch_live_funding_and_oi()
        tg_send_message(chat_id, ask_ai_market_agent(rates, lang))
        return

    if data == "prop_guard":
        tg_answer_callback(cb_id)
        pro, _ = is_user_pro(uid)
        tg_send_message(chat_id, tr(lang, "guard_info"), reply_markup=main_keyboard(pro, lang))
        return

    if data == "download_ea":
        pro, _ = is_user_pro(uid)
        if not pro:
            tg_answer_callback(cb_id, tr(lang, "need_pro"), show_alert=True)
            return
        tg_answer_callback(cb_id)
        if EA_FILE_PATH.exists():
            tg_send_document(chat_id, EA_FILE_PATH, "TradeGuard_PropProtector.mq5", tr(lang, "ea_cap"))
        return

    if data == "download_pine":
        pro, _ = is_user_pro(uid)
        if not pro:
            tg_answer_callback(cb_id, tr(lang, "need_pro"), show_alert=True)
            return
        tg_answer_callback(cb_id)
        if PINE_FILE_PATH.exists():
            tg_send_document(chat_id, PINE_FILE_PATH, "TradeGuard_SmartRadar.pine", tr(lang, "pine_cap"))
        return

    if data == "buy_pro":
        tg_answer_callback(cb_id)
        send_pro_invoice(chat_id, lang)


def validate_channel_target(silent: bool = False) -> bool:
    """
    اعتبارسنجی PUBLIC_CHANNEL_ID:
    - خالی باشد → پست خودکار غیرفعال (سالم)
    - به ربات خودش اشاره کند → غیرفعال + هشدار
    - کانال واقعی و ربات ادمین باشد → فعال
    مقدار جهانی CHANNEL_OK / CHANNEL_REASON را ست می‌کند.
    """
    global CHANNEL_OK, CHANNEL_REASON

    if not PUBLIC_CHANNEL_ID:
        CHANNEL_OK, CHANNEL_REASON = False, "خالی است (پست خودکار غیرفعال — سالم)"
        return False

    if PUBLIC_CHANNEL_ID == "@TradeGuard_Live":
        CHANNEL_OK, CHANNEL_REASON = False, "مقدار نمونه پیش‌فرض است"
        return False

    if is_self_chat(PUBLIC_CHANNEL_ID):
        CHANNEL_OK = False
        CHANNEL_REASON = (
            "به خودِ ربات اشاره می‌کند! باید یوزرنیم یک کانال عمومی باشد، نه ربات. "
            "آن را در .env خالی بگذارید یا با /setchannel @yourchannel عوض کنید."
        )
        if not silent:
            logger.error("❌ PUBLIC_CHANNEL_ID نامعتبر: %s", CHANNEL_REASON)
        return False

    info = tg_call("getChat", {"chat_id": PUBLIC_CHANNEL_ID})
    if not info.get("ok"):
        desc = str((info.get("description") or "")).strip() or str(info)
        CHANNEL_OK = False
        CHANNEL_REASON = f"تلگرام این آیدی را نشناخت ({desc[:110]})"
        if not silent:
            logger.error("❌ PUBLIC_CHANNEL_ID نامعتبر: %s", CHANNEL_REASON)
        return False

    chat = info.get("result") or {}
    chat_type = chat.get("type", "")
    title = chat.get("title") or chat.get("username") or PUBLIC_CHANNEL_ID
    if chat_type != "channel":
        CHANNEL_OK = False
        CHANNEL_REASON = f"«{title}» کانال نیست (نوع: {chat_type}) — باید Supergroup یا Channel باشد"
        if not silent:
            logger.error("❌ PUBLIC_CHANNEL_ID نامعتبر: %s", CHANNEL_REASON)
        return False

    if BOT_ID:
        mem = tg_call("getChatMember", {"chat_id": PUBLIC_CHANNEL_ID, "user_id": BOT_ID})
        status = ((mem.get("result") or {}).get("status") or "") if mem.get("ok") else ""
        if status not in ("administrator", "creator"):
            CHANNEL_OK = False
            CHANNEL_REASON = f"ربات در کانال «{title}» ادمین نیست (وضعیت: {status or 'نامشخص'})"
            if not silent:
                logger.error("❌ PUBLIC_CHANNEL_ID نامعتبر: %s", CHANNEL_REASON)
            return False

    CHANNEL_OK = True
    CHANNEL_REASON = f"فعال — کانال «{title}»"
    if not silent:
        logger.info("✅ کانال ویترین تأیید شد: %s", title)
    return True


def auto_channel_loop() -> None:
    if not validate_channel_target(silent=True):
        return
    while True:
        try:
            rates = fetch_live_funding_and_oi()
            top = rates[0]
            second = rates[1] if len(rates) > 1 else top
            deep_link = f"https://t.me/{BOT_USERNAME}?start=channel"
            post_text = (
                "📡 *TradeGuard Global Radar (Live 8h Pulse)* 🌍\n\n"
                f"🔥 *${top['sym']}* ➜ `{top['rate_pct']:+.3f}%/8h` ({top['magnet']}) | $500 Yield: `${top['daily_500']:.2f}/day`\n"
                f"⚡ *${second['sym']}* ➜ `{second['rate_pct']:+.3f}%/8h` | OI: `${second['oi_m']:.1f}M`\n\n"
                "🇮🇷 قفل خودکار دراودان ۳.۸٪ متاتریدر + رادار زنده نهنگ‌ها (۶ زبانه)\n"
                "🇬🇧 Auto -3.8% MT5 Prop Guard + Live Whale & Funding Mini-App:"
            )
            kb = {"inline_keyboard": [[{"text": "🚀 Open TradeGuard (6 Languages)", "url": deep_link}]]}
            res = tg_send_message(PUBLIC_CHANNEL_ID, post_text, reply_markup=kb)
            if not res.get("ok") and res.get("error_code") in (400, 403):
                logger.warning("پست کانال رد شد؛ اعتبارسنجی دوباره در چرخه بعد: %s", res.get("description"))
                validate_channel_target(silent=True)
                if not CHANNEL_OK:
                    logger.warning("⏹ پست خودکار کانال متوقف شد: %s", CHANNEL_REASON)
                    return
        except Exception as exc:
            logger.warning("Channel auto-post skipped: %s", exc)
        time.sleep(8 * 3600)


def process_update(upd: dict) -> None:
    try:
        if "pre_checkout_query" in upd:
            pq = upd["pre_checkout_query"]
            tg_call("answerPreCheckoutQuery", {"pre_checkout_query_id": pq["id"], "ok": True})
        elif "message" in upd:
            handle_message(upd["message"])
        elif "callback_query" in upd:
            handle_callback(upd["callback_query"])
    except Exception as exc:
        logger.warning("Update error: %s", exc)


def main() -> None:
    global BOT_TOKEN, BOT_USERNAME
    init_db()
    if not BOT_TOKEN or "your_telegram_bot_token" in BOT_TOKEN:
        if sys.stdin and sys.stdin.isatty():
            print("\n========================================================")
            print("🔑 تنظیم سریع توکن ربات تلگرام (فقط یک‌بار نیاز است!)")
            print("توکنی که از @BotFather گرفتید را اینجا Paste کنید و Enter بزنید:")
            print("========================================================")
            try:
                entered = input("BOT_TOKEN > ").strip().strip('"').strip("'")
            except EOFError:
                entered = ""
            if entered and ":" in entered:
                BOT_TOKEN = entered
                env_content = (
                    f"BOT_TOKEN={BOT_TOKEN}\n"
                    f"MINI_APP_URL={MINI_APP_URL}\n"
                    f"SUBSCRIPTION_STARS={SUBSCRIPTION_STARS}\n"
                    f"PUBLIC_CHANNEL_ID={PUBLIC_CHANNEL_ID}\n"
                    f"FREE_PRO_INVITE_TARGET={FREE_PRO_INVITE_TARGET}\n"
                    f"ADMIN_USER_ID={ADMIN_USER_ID}\n"
                )
                ENV_PATH.write_text(env_content, encoding="utf-8")
                logger.info("✅ توکن با موفقیت در فایل tradeguard-pro/.env ذخیره شد!")
        if not BOT_TOKEN or "your_telegram_bot_token" in BOT_TOKEN:
            logger.error("❌ لطفاً ابتدا BOT_TOKEN را وارد کنید یا در فایل tradeguard-pro/.env قرار دهید!")
            return

    me = tg_call("getMe")
    if not me.get("ok"):
        logger.error("❌ عدم ارتباط با تلگرام: مطمئن شوید فیلترشکن (VPN) روشن است و BOT_TOKEN درست است. جزئیات: %s", me)
        return

    BOT_USERNAME = me["result"].get("username", "TradeGuard_bot")
    BOT_ID = int((me.get("result") or {}).get("id") or 0)
    # اعتبارسنجی کانال ویترین (جلوگیری از خطای 403 «bot can't send messages to the bot»)
    validate_channel_target()
    # پاک کردن وبهوک قبلی و نصب خودکار دکمه منوی آبی تلگرام (Commands + WebApp)
    tg_call("deleteWebhook", {"drop_pending_updates": False})
    sync_telegram_menus()

    logger.info("✅ متصل شد به ربات: @%s (id: %s)", BOT_USERNAME, BOT_ID)
    logger.info("📢 وضعیت کانال ویترین: %s", CHANNEL_REASON)
    logger.info("🌍 ربات جهانی ۶ زبانه TradeGuard v7.5 (نسخه نهایی کامل!) روشن و آماده است! به تلگرام بروید و /start بزنید.")

    threading.Thread(target=auto_channel_loop, daemon=True).start()
    pool = ThreadPoolExecutor(max_workers=8)
    offset = 0

    while True:
        try:
            res = tg_call(
                "getUpdates",
                {
                    "offset": offset,
                    "timeout": 25,
                    "allowed_updates": ["message", "callback_query", "pre_checkout_query"],
                },
                timeout=35.0,
            )
            if res.get("ok"):
                for upd in res.get("result") or []:
                    offset = int(upd["update_id"]) + 1
                    pool.submit(process_update, upd)
            else:
                time.sleep(3)
        except KeyboardInterrupt:
            logger.info("ربات متوقف شد.")
            break
        except Exception as exc:
            logger.warning("Polling retry in 3s: %s", exc)
            time.sleep(3)


if __name__ == "__main__":
    main()

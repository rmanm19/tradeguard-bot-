#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TradeGuard — Supervisor / نگهبان ربات
=====================================
ربات را در یک زیرفرآیند اجرا می‌کند و اگر کرش کرد یا خروجی گرفت،
خودکار دوباره بالا می‌آوردش. صفر وابستگی.

    python run_forever.py              # اجرای دائمی (روی VPS / PC)
    python run_forever.py --status     # وضعیت فعلی
    python run_forever.py --max-seconds 19800   # برای GitHub Actions
    python run_forever.py --no-alert   # بدون پیام هشدار به ادمین
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = Path(__file__).resolve().parent
BOT = BASE / "bot.py"
STATE = BASE / "supervisor_state.json"
LOG = BASE / "bot_run.log"
ENV = BASE / ".env"

READY_MARKERS = ("آماده است", "connected as", "متصل شد", "ready")
CRASH_WINDOW = 30.0          # اگر کمتر از این ثانیه زنده ماند = کرش سریع
MAX_FAST_CRASHES = 6
ALERT_COOLDOWN = 600.0


MAX_LOG_BYTES = 5 * 1024 * 1024


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        if LOG.exists() and LOG.stat().st_size > MAX_LOG_BYTES:
            old = LOG.with_suffix(".log.1")
            try:
                if old.exists():
                    old.unlink()
                LOG.rename(old)
            except Exception:
                LOG.write_text("", encoding="utf-8")
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_env() -> dict:
    env = dict(os.environ)
    if ENV.exists():
        for raw in ENV.read_text(encoding="utf-8", errors="replace").splitlines():
            raw = raw.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            k, v = raw.split("=", 1)
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def tg_notify(env: dict, text: str) -> None:
    token = env.get("BOT_TOKEN", "").strip()
    admin = env.get("ADMIN_USER_ID", "").strip()
    if not token or not admin or ":" not in token:
        return
    try:
        data = urllib.parse.urlencode(
            {"chat_id": admin, "text": text[:3800], "parse_mode": "HTML"}
        ).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data,
            timeout=15,
        ).close()
    except Exception as exc:
        log(f"(هشدار تلگرام ارسال نشد: {exc})")


def write_state(**kw) -> None:
    data = {}
    if STATE.exists():
        try:
            data = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.update(kw)
    data["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def show_status() -> None:
    if not STATE.exists():
        print("\n  هیچ وضعیتی ثبت نشده — ربات هنوز با run_forever اجرا نشده.\n")
        return
    d = json.loads(STATE.read_text(encoding="utf-8"))
    pid = d.get("pid")
    alive = False
    if pid:
        try:
            os.kill(int(pid), 0)
            alive = True
        except Exception:
            alive = False
    print(f"""
  ┌─────────────────────────────────────────────┐
  │  وضعیت نگهبان TradeGuard                    │
  ├─────────────────────────────────────────────┤
     ربات زنده      : {'✅ بله' if alive else '❌ نه'}
     PID            : {pid or '-'}
     تعداد ری‌استارت: {d.get('restarts', 0)}
     آخرین شروع    : {d.get('started', '-')}
     آخرین خروج    : {d.get('last_exit', '-')}
     آپدیت         : {d.get('updated', '-')}
  └─────────────────────────────────────────────┘
""")


def main() -> int:
    ap = argparse.ArgumentParser(description="TradeGuard bot supervisor")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--max-seconds", type=int, default=0,
                    help="بعد از این مدت با خیال راحت خارج شو (برای GitHub Actions)")
    ap.add_argument("--no-alert", action="store_true", help="بدون پیام تلگرام")
    ap.add_argument("--once", action="store_true", help="فقط یک بار اجرا کن (بدون ری‌استارت)")
    args = ap.parse_args()

    if args.status:
        show_status()
        return 0

    if not BOT.exists():
        log(f"❌ bot.py پیدا نشد در {BOT}")
        return 1

    env = load_env()
    token = env.get("BOT_TOKEN", "").strip()
    if not token or "your_telegram_bot_token" in token:
        log("❌ BOT_TOKEN تنظیم نشده. فایل tradeguard-pro/.env را بساز.")
        return 1

    stopping = {"flag": False}

    def on_signal(signum, _frame):
        stopping["flag"] = True
        log(f"سیگنال {signum} دریافت شد — خروج تمیز…")

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, on_signal)
        except Exception:
            pass

    t_start = time.time()
    restarts = 0
    fast_crashes = 0
    backoff = 5
    last_alert = 0.0

    log("═" * 56)
    log("🛡  نگهبان TradeGuard فعال شد — ربات را زنده نگه می‌دارم")
    log("═" * 56)

    while not stopping["flag"]:
        if args.max_seconds and (time.time() - t_start) >= args.max_seconds:
            log(f"⏱  سقف زمان ({args.max_seconds}s) پر شد — خروج تمیز برای ادامه در اجرای بعدی")
            break

        write_state(pid=None, started=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    restarts=restarts, status="starting")
        log(f"▶  اجرای bot.py (تلاش #{restarts + 1})")

        child = None
        ran_ok = False
        try:
            child = subprocess.Popen(
                [sys.executable, "-u", str(BOT)],
                cwd=str(BASE),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            write_state(pid=child.pid, status="running")
            started = time.time()

            assert child.stdout is not None
            for line in child.stdout:
                line = line.rstrip("\n")
                if line:
                    log("   " + line)
                    low = line.lower()
                    if any(m in low for m in READY_MARKERS):
                        ran_ok = True
                        if fast_crashes:
                            fast_crashes = 0
                            backoff = 5
                if stopping["flag"]:
                    child.terminate()
                    break

            rc = child.wait(timeout=20)
        except Exception as exc:
            log(f"⚠  خطا در اجرای زیرفرآیند: {exc}")
            rc = -1
        finally:
            if child and child.poll() is None:
                try:
                    child.terminate()
                    child.wait(timeout=10)
                except Exception:
                    try:
                        child.kill()
                    except Exception:
                        pass

        if stopping["flag"]:
            break

        lived = time.time() - (started if 'started' in dir() else time.time())
        if args.once:
            log(f"■  اجرای تک‌باره تمام شد (کد {rc})")
            write_state(status="stopped", last_exit=f"rc={rc}")
            return 0

        restarts += 1
        write_state(restarts=restarts, last_exit=f"rc={rc} after {int(lived)}s", pid=None, status="restarting")

        if lived < CRASH_WINDOW:
            fast_crashes += 1
        else:
            fast_crashes = 0
            backoff = 5

        if fast_crashes >= MAX_FAST_CRASHES:
            log(f"⛔ {fast_crashes} کرش سریع پشت‌سرهم — نگهبان متوقف شد تا لاگ را ببینی.")
            log(f"   لاگ: {LOG}")
            if not args.no_alert:
                tg_notify(env, "⛔ <b>TradeGuard</b>\nربات ۶ بار پشت‌سرهم کرش کرد و نگهبان متوقف شد.\n"
                               f"کد خروج: <code>{rc}</code>\nلاگ را در سرور ببین.")
            return 1

        if fast_crashes >= 1 and time.time() - last_alert > ALERT_COOLDOWN:
            last_alert = time.time()
            if not args.no_alert and not ran_ok:
                tg_notify(env, f"⚠️ <b>TradeGuard</b>\nربات کرش کرد (کد {rc}) — در حال راه‌اندازی مجدد…")
        elif ran_ok and time.time() - last_alert > ALERT_COOLDOWN and restarts > 1:
            last_alert = time.time()
            if not args.no_alert:
                tg_notify(env, "✅ <b>TradeGuard</b>\nربات دوباره آنلاین شد.")

        wait = backoff if fast_crashes else 3
        log(f"↻  ری‌استارت در {wait} ثانیه (کد خروج {rc})")
        for _ in range(int(wait * 2)):
            if stopping["flag"]:
                break
            time.sleep(0.5)
        backoff = min(backoff * 2, 300)

    write_state(status="stopped", pid=None)
    log("■  نگهبان خاموش شد.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

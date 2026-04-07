"""
Telegram Grup Dinleme Botu + API Sunucusu
==========================================
Kurulum:
    pip install -r requirements.txt

Çalıştırma:
    python files/main.py
"""

import json
import os
import asyncio
import threading
from datetime import datetime
from flask import Flask, jsonify, send_from_directory, redirect
from flask_cors import CORS
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import (
    MessageMediaPhoto, MessageMediaDocument,
    MessageMediaWebPage, MessageEntityUrl, MessageEntityTextUrl
)

# ─── AYARLAR (Railway environment variables'dan okunur) ────────────────────────
API_ID       = int(os.environ.get("API_ID", "0"))
API_HASH     = os.environ.get("API_HASH", "")
TELEGRAM_SESSION = os.environ.get("TELEGRAM_SESSION", "").strip()
TARGET_GROUP = os.environ.get("TARGET_GROUP", "")   # @grupadi veya sayısal ID
PORT         = int(os.environ.get("PORT", "8000"))
DATA_FILE    = "messages.json"
# ───────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)  # Dashboard farklı domain'den erişebilsin


# ─── VERİ FONKSİYONLARI ───────────────────────────────────────────────────────

def load_messages():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_message(entry):
    messages = load_messages()
    messages.append(entry)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
    print(f"[+] {entry['type']:12} | {str(entry.get('text',''))[:60]}")


# ─── FLASK API ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect("/dashboard")


@app.route("/api")
def api_status():
    return jsonify({"status": "ok", "message": "Telegram Analiz API çalışıyor"})


@app.route("/dashboard")
def dashboard():
    return send_from_directory(".", "dashboard.html")


@app.route("/messages")
def get_messages():
    return jsonify(load_messages())


@app.route("/stats")
def get_stats():
    messages = load_messages()
    if not messages:
        return jsonify({"total": 0})

    senders  = list({m.get("sender_username") or m.get("sender_name", "") for m in messages if m.get("sender_name") or m.get("sender_username")})
    types    = {}
    by_day   = {}
    by_hour  = [0] * 24
    links    = []

    for m in messages:
        t = m.get("type", "other")
        types[t] = types.get(t, 0) + 1

        if m.get("date"):
            day = m["date"][:10]
            by_day[day] = by_day.get(day, 0) + 1
            try:
                hour = datetime.fromisoformat(m["date"]).hour
                by_hour[hour] += 1
            except Exception:
                pass

        links.extend(m.get("links", []))

    return jsonify({
        "total":    len(messages),
        "senders":  senders[:20],
        "types":    types,
        "by_day":   by_day,
        "by_hour":  by_hour,
        "links":    list(set(links))[:50],
        "latest":   messages[-20:][::-1],
    })


# ─── TELEGRAM USERBOT ──────────────────────────────────────────────────────────

def extract_links(message):
    links = []
    if message.entities:
        for e in message.entities:
            if isinstance(e, MessageEntityUrl):
                links.append(message.raw_text[e.offset: e.offset + e.length])
            elif isinstance(e, MessageEntityTextUrl):
                links.append(e.url)
    if message.media and isinstance(message.media, MessageMediaWebPage):
        wp = message.media.webpage
        if hasattr(wp, "url"):
            links.append(wp.url)
    return list(set(links))


def get_media_type(message):
    if isinstance(message.media, MessageMediaPhoto):
        return "photo"
    if isinstance(message.media, MessageMediaDocument):
        mime = getattr(message.media.document, "mime_type", "") or ""
        if mime.startswith("video"):   return "video"
        if mime.startswith("audio"):   return "audio"
        if mime.startswith("image"):   return "image"
        return "document"
    if isinstance(message.media, MessageMediaWebPage):
        return "webpage"
    return "other"


def normalize_target(target):
    raw = (target or "").strip()
    if not raw:
        return ""
    return raw.lstrip("@")


def target_matches(chat, target):
    normalized_target = normalize_target(target)
    if not normalized_target:
        return False

    username = (getattr(chat, "username", None) or "").lower()
    if username and username == normalized_target.lower():
        return True

    chat_id = str(getattr(chat, "id", "")).strip()
    if not chat_id:
        return False

    # Telegram grup id'leri bazen -100 ile gelir; kullanıcı farklı formatta girebilir.
    id_candidates = {chat_id}
    if chat_id.startswith("-100"):
        id_candidates.add(chat_id[4:])
    elif chat_id.startswith("-"):
        id_candidates.add(chat_id[1:])
    else:
        id_candidates.add("-" + chat_id)
        id_candidates.add("-100" + chat_id)

    return normalized_target in id_candidates


def validate_config():
    missing = []
    if API_ID <= 0:
        missing.append("API_ID")
    if not API_HASH:
        missing.append("API_HASH")
    if not TARGET_GROUP:
        missing.append("TARGET_GROUP")

    if missing:
        print("❌ Eksik environment variable:", ", ".join(missing))
        print("Railway Variables kısmına bu değerleri ekleyip yeniden deploy edin.")
        return False
    return True


def build_client():
    if TELEGRAM_SESSION:
        print("🔐 TELEGRAM_SESSION bulundu, StringSession ile baglaniliyor.")
        return TelegramClient(StringSession(TELEGRAM_SESSION), API_ID, API_HASH)

    print("ℹ️ TELEGRAM_SESSION yok, yerel session dosyasi kullaniliyor.")
    return TelegramClient("session", API_ID, API_HASH)


async def run_bot():
    if not validate_config():
        return

    client = build_client()
    await client.start()
    me = await client.get_me()
    print(f"✅ Giriş yapıldı: {me.first_name} (@{me.username})")

    @client.on(events.NewMessage)
    async def handler(event):
        msg  = event.message
        chat = await event.get_chat()

        chat_id = str(getattr(chat, "id", ""))
        if not target_matches(chat, TARGET_GROUP):
            return

        sender = await event.get_sender()
        sender_name     = ""
        sender_username = ""
        if sender:
            first = getattr(sender, "first_name", "") or ""
            last  = getattr(sender, "last_name",  "") or ""
            sender_name     = (first + " " + last).strip()
            sender_username = getattr(sender, "username", "") or ""

        links     = extract_links(msg)
        has_media = msg.media is not None
        media_type = get_media_type(msg) if has_media else None

        if not has_media and not links:
            msg_type = "text"
        elif links and not has_media:
            msg_type = "link"
        elif has_media and links:
            msg_type = "media+link"
        elif has_media:
            msg_type = media_type
        else:
            msg_type = "other"

        entry = {
            "id":              msg.id,
            "type":            msg_type,
            "chat_id":         chat_id,
            "chat_title":      getattr(chat, "title", "") or "",
            "sender_name":     sender_name,
            "sender_username": sender_username,
            "text":            msg.raw_text or "",
            "links":           links,
            "has_media":       has_media,
            "media_type":      media_type,
            "date":            msg.date.isoformat(),
            "saved_at":        datetime.now().isoformat(),
            "views":           getattr(msg, "views", None),
            "forwards":        getattr(msg, "forwards", None),
        }
        save_message(entry)

    print(f"👂 Dinleniyor: {TARGET_GROUP}")
    await client.run_until_disconnected()


# ─── BAŞLATMA ──────────────────────────────────────────────────────────────────

def start_flask():
    app.run(host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    # Flask'ı ayrı thread'de başlat
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()
    print(f"🌐 API sunucusu başlatıldı: http://0.0.0.0:{PORT}")

    # Telethon ana thread'de çalışsın
    asyncio.run(run_bot())

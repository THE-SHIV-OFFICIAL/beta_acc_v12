"""Social Media Services hub + Virtual OTP Numbers (Grizzly SMS).

User flow
  🚀 Social Media Services  ->  Telegram / Instagram / Facebook / YouTube / WhatsApp
                            ->  service type (Members, Reactions, Followers ...)
                            ->  service -> Order (link + qty) -> Confirm -> charged
  📲 Virtual Numbers        ->  platform -> buy number -> OTP arrives automatically

Admin commands
  /smmlist                       list all social services with local IDs
  /setsmm <id> <fansmm_id> [price_per_1000]   connect a service to FanSMM
  /smmoff <id>  /smmon <id>      hide / show a service
  /addbal <user_id> <amount> [reason]   add money to any user
  /cutbal <user_id> <amount> [reason]   deduct money from any user
  /checkbal <user_id>            see a user balance
"""
import asyncio
import html
import os
from telethon import events, Button
from telethon.errors import MessageNotModifiedError
from database import cur, db, to_usd
from config import (PE_LIGHTNING, PE_CHECK, PE_GIFT, PE_CROWN, PE_HEART, PE_FLOWER,
                    PE_ANGEL, P_INR, P_WARN, P_NO, ADMIN_IDS, logger, tg_emoji)
from utils.keyboards import style_btn, style_url
from utils.states import get_user_lock

PE_ROCKET = tg_emoji("lightning", "🚀")
PE_STAR = tg_emoji("flower", "✨")

# id (custom premium emoji) used as button icons
ICON = {
    "telegram": 5409271925014801629, "instagram": 5408995930416362034,
    "facebook": 5409166771330494453, "youtube": 5375125990118793401,
    "whatsapp": 5409098988156629257, "status": 5409119256107297715,
    "history": 5440627033111557670, "close": 6064310143380625195,
    "back": 6129812419028982717, "buy": 5409320020058584473,
    "type": 6203982793379154737,
}

PLATFORMS = {
    "telegram": ("✈️", "Telegram"),
    "instagram": ("📸", "Instagram"),
    "facebook": ("📘", "Facebook"),
    "youtube": ("▶️", "YouTube"),
    "whatsapp": ("💬", "WhatsApp"),
}

# name, type, min, max, price_per_1000 (INR), description
CATALOG = {
    "Telegram": [
        ("Channel / Group Members", "Members", 100, 50000, 120, "Real-looking members for channel or group. Send public t.me link."),
        ("Premium Members (Non-Drop)", "Members", 100, 20000, 450, "High quality, low drop members."),
        ("Post Views (Last 1 Post)", "Views", 100, 1000000, 8, "Views on a single post. Send post link."),
        ("Views (Last 10 Posts)", "Views", 100, 100000, 40, "Views spread on last 10 posts."),
        ("Positive Reactions 👍❤️🔥", "Reactions", 50, 100000, 25, "Mixed positive reactions on a post."),
        ("Premium Emoji Reactions", "Reactions", 50, 50000, 60, "Premium animated reactions."),
        ("Custom Reaction (Single emoji)", "Reactions", 50, 50000, 35, "One chosen reaction emoji."),
        ("Post Shares", "Shares", 100, 100000, 30, "Shares / forwards on a post."),
        ("Poll Votes", "Votes", 50, 50000, 90, "Votes on a poll option."),
        ("Bot Start / Referral", "Bot Starts", 50, 20000, 150, "Starts on your bot link."),
        ("Story Views", "Views", 100, 50000, 50, "Views on your story."),
    ],
    "Instagram": [
        ("Followers (Real Mix)", "Followers", 100, 100000, 180, "Send profile link. Account must be public."),
        ("Followers (Non-Drop)", "Followers", 100, 50000, 320, "Refill-quality followers."),
        ("Post Likes", "Likes", 50, 100000, 40, "Likes on post / reel."),
        ("Reel Views", "Views", 100, 10000000, 6, "Views on reels."),
        ("Story Views", "Views", 100, 100000, 25, "Views on all active stories."),
        ("Custom Comments", "Comments", 10, 5000, 600, "Your own comments."),
        ("Random Comments", "Comments", 10, 5000, 350, "Positive random comments."),
        ("Saves", "Saves", 100, 50000, 30, "Post saves."),
        ("Shares", "Shares", 100, 100000, 25, "Post shares."),
        ("Live Views (30 min)", "Live", 50, 5000, 900, "Live stream viewers."),
    ],
    "Facebook": [
        ("Page Likes + Followers", "Followers", 100, 50000, 260, "Send page link."),
        ("Profile Followers", "Followers", 100, 50000, 220, "Send profile link."),
        ("Post Likes", "Likes", 50, 50000, 90, "Likes on a post."),
        ("Post Reactions (Love/Wow)", "Reactions", 50, 50000, 110, "Mixed emoji reactions."),
        ("Video Views", "Views", 500, 1000000, 20, "Views on video / reel."),
        ("Custom Comments", "Comments", 10, 2000, 700, "Your own comments."),
        ("Group Members", "Members", 100, 20000, 350, "Members for public group."),
        ("Post Shares", "Shares", 100, 50000, 120, "Shares on a post."),
    ],
    "YouTube": [
        ("Subscribers", "Subscribers", 50, 20000, 1800, "Send channel link."),
        ("Video Views", "Views", 500, 1000000, 120, "Views on video."),
        ("Shorts Views", "Views", 500, 1000000, 60, "Views on Shorts."),
        ("Video Likes", "Likes", 50, 50000, 140, "Likes on a video."),
        ("Custom Comments", "Comments", 10, 2000, 900, "Your own comments."),
        ("Watch Time (Hours)", "Watch Time", 100, 4000, 2500, "Watch hours for monetisation."),
        ("Live Stream Views", "Live", 50, 10000, 700, "Concurrent live viewers."),
    ],
    "WhatsApp": [
        ("Channel Followers", "Followers", 100, 50000, 280, "Send WhatsApp channel link."),
        ("Channel Post Reactions", "Reactions", 50, 20000, 150, "Emoji reactions on channel post."),
        ("Group Members", "Members", 50, 5000, 900, "Members for invite link group."),
    ],
}


def seed_catalog():
    for platform, items in CATALOG.items():
        for name, typ, mn, mx, price, desc in items:
            cat = f"{platform} • {typ}"
            exists = cur.execute("SELECT 1 FROM smm_services WHERE category=? AND name=?", (cat, name)).fetchone()
            if not exists:
                cur.execute(
                    "INSERT INTO smm_services (name, category, fansmm_service_id, min_qty, max_qty, price_per_1000, description, available) VALUES (?,?,?,?,?,?,?,1)",
                    (name, cat, "", mn, mx, price, desc))
    db.commit()


async def _edit_or_send(e, msg, btns):
    if isinstance(e, events.CallbackQuery.Event):
        try:
            return await e.edit(msg, buttons=btns)
        except MessageNotModifiedError:
            return
        except Exception:
            pass
    return await e.respond(msg, buttons=btns)


def _bal(uid):
    r = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
    return r[0] if r else 0


# ───────────── SOCIAL HUB ─────────────
async def show_social_hub(e):
    uid = e.sender_id
    open_orders = cur.execute(
        "SELECT COUNT(*) FROM smm_orders WHERE user_id=? AND lower(status) NOT IN ('completed','canceled','cancelled','refunded','partial')",
        (uid,)).fetchone()[0]
    msg = (f"<blockquote>{PE_ROCKET} <b>𝐒ᴏᴄɪᴀʟ 𝐌ᴇᴅɪᴀ 𝐒ᴇʀᴠɪᴄᴇs</b></blockquote>\n\n"
           f"<blockquote>{PE_STAR} 𝐅ᴀsᴛ ᴅᴇʟɪᴠᴇʀʏ · ʏᴏᴜ ᴀʀᴇ ᴄʜᴀʀɢᴇᴅ ᴏɴʟʏ ᴀғᴛᴇʀ ᴄᴏɴғɪʀᴍ\n"
           f"👇 𝐂ʜᴏᴏsᴇ ᴀ ᴘʟᴀᴛғᴏʀᴍ ᴛᴏ sᴛᴀʀᴛ\n"
           f"{PE_ANGEL} <b>𝐔sᴇʀ 𝐈𝐃:</b> <code>{uid}</code>\n"
           f"{PE_CROWN} <b>𝐁ᴀʟᴀɴᴄᴇ:</b> {P_INR}{_bal(uid)} | ${to_usd(_bal(uid)):.2f}\n"
           f"📦 <b>𝐎ᴘᴇɴ ᴏʀᴅᴇʀs:</b> {open_orders}</blockquote>")
    btns = [
        [style_btn("Telegram", b"soc_p|telegram", "primary", ICON["telegram"]),
         style_btn("Instagram", b"soc_p|instagram", "primary", ICON["instagram"])],
        [style_btn("Facebook", b"soc_p|facebook", "primary", ICON["facebook"]),
         style_btn("YouTube", b"soc_p|youtube", "danger", ICON["youtube"])],
        [style_btn("WhatsApp", b"soc_p|whatsapp", "success", ICON["whatsapp"])],
        [style_btn("Check Order Status", b"soc_status", None, ICON["status"]),
         style_btn("History", b"soc_hist", None, ICON["history"])],
        [style_btn("Close", b"soc_close", "danger", ICON["close"])],
    ]
    await _edit_or_send(e, msg, btns)


async def show_platform(e, key):
    emoji, name = PLATFORMS[key]
    rows = cur.execute(
        "SELECT category, COUNT(*) FROM smm_services WHERE category LIKE ? AND available=1 GROUP BY category ORDER BY category",
        (f"{name} •%",)).fetchall()
    btns, row = [], []
    for cat, cnt in rows:
        typ = cat.split("•", 1)[1].strip()
        row.append(style_btn(f"{typ} ({cnt})", f"soc_t|{key}|{typ}".encode(), "primary", ICON["type"]))
        if len(row) == 2:
            btns.append(row); row = []
    if row: btns.append(row)
    btns.append([style_btn("Back", b"soc_home", "danger", ICON["back"])])
    msg = (f"<blockquote>{emoji} <b>{name} 𝐒ᴇʀᴠɪᴄᴇs</b></blockquote>\n\n"
           f"<blockquote>{PE_LIGHTNING} 𝐒ᴇʟᴇᴄᴛ ᴡʜᴀᴛ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ɪɴᴄʀᴇᴀsᴇ:</blockquote>")
    if not rows:
        msg += f"\n<blockquote>{P_WARN} 𝐍ᴏ sᴇʀᴠɪᴄᴇs ʀɪɢʜᴛ ɴᴏᴡ.</blockquote>"
    await _edit_or_send(e, msg, btns)


async def show_type(e, key, typ):
    emoji, name = PLATFORMS[key]
    cat = f"{name} • {typ}"
    rows = cur.execute(
        "SELECT id, name, price_per_1000 FROM smm_services WHERE category=? AND available=1 ORDER BY price_per_1000",
        (cat,)).fetchall()
    btns = [[style_btn(f"{n[:32]} — {P_INR}{p}/1K", f"smm_svc|{sid}".encode(), "primary", ICON["buy"])]
            for sid, n, p in rows]
    btns.append([style_btn("Back", f"soc_p|{key}".encode(), "danger", ICON["back"])])
    msg = (f"<blockquote>{emoji} <b>{name} → {typ}</b></blockquote>\n\n"
           f"<blockquote>{PE_GIFT} 𝐏ʀɪᴄᴇ sʜᴏᴡɴ ᴘᴇʀ 1000. 𝐓ᴀᴘ ᴀ sᴇʀᴠɪᴄᴇ ғᴏʀ ᴅᴇᴛᴀɪʟs.</blockquote>")
    await _edit_or_send(e, msg, btns)


async def show_history(e):
    uid = e.sender_id
    rows = cur.execute(
        "SELECT fansmm_order_id, service_name, quantity, price, status, date FROM smm_orders WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (uid,)).fetchall()
    if not rows:
        msg = f"<blockquote>{PE_GIFT} <b>𝐇ɪsᴛᴏʀʏ</b></blockquote>\n\n<blockquote>𝐍ᴏ ᴏʀᴅᴇʀs ʏᴇᴛ.</blockquote>"
    else:
        msg = f"<blockquote>{PE_GIFT} <b>𝐇ɪsᴛᴏʀʏ</b> (𝐋ᴀsᴛ 10)</blockquote>\n"
        for oid, sn, q, p, st, dt in rows:
            msg += (f"<blockquote>🆔 <code>{oid}</code> · {html.escape(str(sn))}\n"
                    f"📊 {q} · {P_INR}{p} · <b>{st}</b> · 📅 {str(dt)[:10]}</blockquote>\n")
    await _edit_or_send(e, msg, [[style_btn("Back", b"soc_home", "danger", ICON["back"])]])


async def show_status_list(e):
    uid = e.sender_id
    rows = cur.execute(
        "SELECT fansmm_order_id, service_name FROM smm_orders WHERE user_id=? ORDER BY id DESC LIMIT 8", (uid,)).fetchall()
    btns = [[style_btn(f"🔄 #{oid} · {str(sn)[:25]}", f"soc_chk|{oid}".encode(), "primary")] for oid, sn in rows]
    btns.append([style_btn("Back", b"soc_home", "danger", ICON["back"])])
    msg = (f"<blockquote>{PE_CHECK} <b>𝐂ʜᴇᴄᴋ 𝐎ʀᴅᴇʀ 𝐒ᴛᴀᴛᴜs</b></blockquote>\n\n"
           f"<blockquote>{'𝐓ᴀᴘ ᴀɴ ᴏʀᴅᴇʀ ᴛᴏ ʀᴇғʀᴇsʜ ʟɪᴠᴇ sᴛᴀᴛᴜs.' if rows else '𝐍ᴏ ᴏʀᴅᴇʀs ʏᴇᴛ.'}</blockquote>")
    await _edit_or_send(e, msg, btns)


# ───────────── VIRTUAL NUMBERS (GRIZZLY) ─────────────
NUM_SERVICES = {  # grizzly service code
    "tg": ("✈️", "Telegram"), "wa": ("💬", "WhatsApp"), "ig": ("📸", "Instagram"),
    "fb": ("📘", "Facebook"), "go": ("▶️", "YouTube / Google"),
}


def number_price(code):
    return int(os.getenv(f"NUM_PRICE_{code.upper()}", os.getenv("NUM_PRICE_INR", "40")))


async def show_numbers(e):
    btns = [[style_btn(f"{em} {n} — {P_INR}{number_price(c)}", f"num_buy|{c}".encode(), "primary", ICON["buy"])]
            for c, (em, n) in NUM_SERVICES.items()]
    btns.append([style_btn("Back", b"menu_more", "danger", ICON["back"])])
    msg = (f"<blockquote>📲 <b>𝐕ɪʀᴛᴜᴀʟ 𝐍ᴜᴍʙᴇʀs (𝐎𝐓𝐏)</b></blockquote>\n\n"
           f"<blockquote>{PE_LIGHTNING} 𝐆ᴇᴛ ᴀ ɴᴜᴍʙᴇʀ ᴀɴᴅ ʀᴇᴄᴇɪᴠᴇ ᴛʜᴇ 𝐎𝐓𝐏 ʜᴇʀᴇ.\n"
           f"⏳ 𝐈ғ ɴᴏ 𝐎𝐓𝐏 ɪɴ 10 ᴍɪɴ, ɴᴜᴍʙᴇʀ ɪs ᴄᴀɴᴄᴇʟʟᴇᴅ ᴀɴᴅ ʙᴀʟᴀɴᴄᴇ ʀᴇᴛᴜʀɴᴇᴅ.</blockquote>")
    await _edit_or_send(e, msg, btns)


async def buy_number(bot, e, code):
    from plugins.grizzly import get_number, get_status, set_status
    uid = e.sender_id
    price = number_price(code)
    country = os.getenv("GRIZZLY_COUNTRY", "22")
    async with get_user_lock(uid):
        cur.execute("UPDATE users SET balance=balance-? WHERE user_id=? AND balance>=?", (price, uid, price))
        if cur.rowcount == 0:
            return await e.answer("❌ Insufficient Balance! Please recharge.", alert=True)
        db.commit()
    try:
        act_id, phone = await get_number(code, country)
    except Exception as ex:
        async with get_user_lock(uid):
            cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (price, uid)); db.commit()
        return await e.answer(f"No number available now ({ex}). Balance returned.", alert=True)
    em, name = NUM_SERVICES[code]
    await e.edit(f"<blockquote>{em} <b>{name} 𝐍ᴜᴍʙᴇʀ</b></blockquote>\n\n"
                 f"<blockquote>📱 <code>+{phone}</code>\n🆔 <code>{act_id}</code>\n{P_INR}{price} ᴅᴇᴅᴜᴄᴛᴇᴅ\n\n"
                 f"⏳ 𝐖ᴀɪᴛɪɴɢ ғᴏʀ 𝐎𝐓𝐏…</blockquote>")
    for _ in range(120):  # 10 minutes
        await asyncio.sleep(5)
        try:
            res = await get_status(act_id)
        except Exception:
            continue
        if res.startswith("STATUS_OK"):
            otp = res.split(":", 1)[1]
            try: await set_status(act_id, 6)
            except Exception: pass
            return await bot.send_message(uid, f"<blockquote>{PE_CHECK} <b>𝐎𝐓𝐏 𝐑ᴇᴄᴇɪᴠᴇᴅ</b>\n📱 +{phone}\n🔢 <code>{otp}</code></blockquote>")
        if res.startswith("STATUS_CANCEL"):
            break
    try: await set_status(act_id, 8)
    except Exception: pass
    async with get_user_lock(uid):
        cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (price, uid)); db.commit()
    await bot.send_message(uid, f"<blockquote>{P_WARN} 𝐍ᴏ 𝐎𝐓𝐏 ғᴏʀ +{phone}. 𝐍ᴜᴍʙᴇʀ ᴄᴀɴᴄᴇʟʟᴇᴅ, {P_INR}{price} ʀᴇᴛᴜʀɴᴇᴅ.</blockquote>")


# ───────────── TERMS ─────────────
TERMS_TEXT = (
    f"<blockquote>{PE_FLOWER} <b>𝐓ᴇʀᴍs & 𝐂ᴏɴᴅɪᴛɪᴏɴs</b></blockquote>\n\n"
    "<blockquote>1️⃣ <b>𝐍ᴏ 𝐑ᴇғᴜɴᴅ</b> — ᴏɴᴄᴇ ᴀɴ ᴏʀᴅᴇʀ ɪs ᴄᴏɴғɪʀᴍᴇᴅ, ᴍᴏɴᴇʏ ɪs ɴᴏᴛ ʀᴇғᴜɴᴅᴇᴅ.\n"
    "2️⃣ <b>𝐍ᴏ 𝐑ᴇᴛᴜʀɴ</b> — ᴅᴇʟɪᴠᴇʀᴇᴅ ᴀᴄᴄᴏᴜɴᴛs, ɴᴜᴍʙᴇʀs ᴀɴᴅ sᴇʀᴠɪᴄᴇs ᴄᴀɴɴᴏᴛ ʙᴇ ʀᴇᴛᴜʀɴᴇᴅ.\n"
    "3️⃣ <b>𝐍ᴏ 𝐄xᴄʜᴀɴɢᴇ</b> — ᴡᴇ ᴅᴏ ɴᴏᴛ ᴇxᴄʜᴀɴɢᴇ ᴏɴᴇ sᴇʀᴠɪᴄᴇ ғᴏʀ ᴀɴᴏᴛʜᴇʀ.</blockquote>\n"
    "<blockquote>• 𝐂ʜᴇᴄᴋ ʏᴏᴜʀ ʟɪɴᴋ ʙᴇғᴏʀᴇ ᴄᴏɴғɪʀᴍ — ᴡʀᴏɴɢ / ᴘʀɪᴠᴀᴛᴇ ʟɪɴᴋ = ɴᴏ ʀᴇғᴜɴᴅ.\n"
    "• 𝐃ᴏɴ'ᴛ ᴘʟᴀᴄᴇ 2 ᴏʀᴅᴇʀs ᴏɴ ᴛʜᴇ sᴀᴍᴇ ʟɪɴᴋ ᴀᴛ ᴛʜᴇ sᴀᴍᴇ ᴛɪᴍᴇ.\n"
    "• 𝐃ʀᴏᴘs ᴀғᴛᴇʀ ᴅᴇʟɪᴠᴇʀʏ ᴀʀᴇ ɴᴏᴛ ᴏᴜʀ ʀᴇsᴘᴏɴsɪʙɪʟɪᴛʏ.\n"
    "• 𝐃ᴇᴘᴏsɪᴛᴇᴅ ʙᴀʟᴀɴᴄᴇ ᴄᴀɴɴᴏᴛ ʙᴇ ᴡɪᴛʜᴅʀᴀᴡɴ.\n"
    "• 𝐎ɴʟʏ ɪғ ᴀ sᴇʀᴠɪᴄᴇ ғᴀɪʟs ᴛᴏ sᴛᴀʀᴛ / ɴᴏ 𝐎𝐓𝐏 ᴀʀʀɪᴠᴇs, ʙᴀʟᴀɴᴄᴇ ɪs ᴀᴜᴛᴏ-ʀᴇᴛᴜʀɴᴇᴅ ᴛᴏ ʙᴏᴛ ᴡᴀʟʟᴇᴛ.\n"
    "• 𝐌ɪsᴜsᴇ / ғʀᴀᴜᴅ = ᴘᴇʀᴍᴀɴᴇɴᴛ ʙᴀɴ.</blockquote>\n"
    f"<blockquote>{PE_HEART} 𝐁ʏ ᴛᴀᴘᴘɪɴɢ <b>𝐀ᴄᴄᴇᴘᴛ</b> ʏᴏᴜ ᴀɢʀᴇᴇ ᴛᴏ ᴀʟʟ ᴛᴇʀᴍs ᴀʙᴏᴠᴇ.</blockquote>"
)


def register_social(bot):
    seed_catalog()

    @bot.on(events.NewMessage(pattern=r"(?i)^(𝐒ᴏᴄɪᴀʟ 𝐌ᴇᴅɪᴀ|🚀 𝐒ᴏᴄɪᴀʟ 𝐌ᴇᴅɪᴀ|/social)$"))
    async def _m(e): await show_social_hub(e)

    @bot.on(events.NewMessage(pattern=r"^/terms$"))
    async def _t(e): await e.respond(TERMS_TEXT)

    @bot.on(events.CallbackQuery(pattern=b"^soc_home$"))
    async def _h(e): await show_social_hub(e)

    @bot.on(events.CallbackQuery(pattern=rb"^soc_p\|(\w+)$"))
    async def _p(e):
        key = e.pattern_match.group(1).decode()
        if key in PLATFORMS: await show_platform(e, key)

    @bot.on(events.CallbackQuery(pattern=rb"^soc_t\|(\w+)\|(.+)$"))
    async def _ty(e):
        key, typ = e.pattern_match.group(1).decode(), e.pattern_match.group(2).decode()
        if key in PLATFORMS: await show_type(e, key, typ)

    @bot.on(events.CallbackQuery(pattern=b"^soc_hist$"))
    async def _hi(e): await show_history(e)

    @bot.on(events.CallbackQuery(pattern=b"^soc_status$"))
    async def _st(e): await show_status_list(e)

    @bot.on(events.CallbackQuery(pattern=rb"^soc_chk\|(.+)$"))
    async def _chk(e):
        from plugins.smm import fansmm_request
        oid = e.pattern_match.group(1).decode()
        row = cur.execute("SELECT status FROM smm_orders WHERE fansmm_order_id=? AND user_id=?", (oid, e.sender_id)).fetchone()
        if not row: return await e.answer("Order not found.", alert=True)
        try:
            r = await fansmm_request({"action": "status", "order": oid})
            st = r.get("status", row[0]); rem = r.get("remains", "?")
            cur.execute("UPDATE smm_orders SET status=? WHERE fansmm_order_id=?", (st, oid)); db.commit()
            await e.answer(f"#{oid}\nStatus: {st}\nRemains: {rem}", alert=True)
        except Exception:
            await e.answer(f"#{oid}\nLast status: {row[0]}", alert=True)

    @bot.on(events.CallbackQuery(pattern=b"^soc_close$"))
    async def _c(e):
        try: await e.delete()
        except Exception: pass

    @bot.on(events.CallbackQuery(pattern=b"^menu_numbers$"))
    async def _n(e): await show_numbers(e)

    @bot.on(events.CallbackQuery(pattern=b"^menu_terms$"))
    async def _tt(e):
        await e.answer()
        await bot.send_message(e.sender_id, TERMS_TEXT)

    @bot.on(events.CallbackQuery(pattern=rb"^num_buy\|(\w+)$"))
    async def _nb(e):
        from utils.helpers import require_join
        if not await require_join(bot, e): return
        code = e.pattern_match.group(1).decode()
        if code in NUM_SERVICES:
            asyncio.create_task(buy_number(bot, e, code))

    # ── admin helpers ──
    @bot.on(events.NewMessage(pattern=r"^/smmlist$"))
    async def _l(e):
        if e.sender_id not in ADMIN_IDS: return
        rows = cur.execute("SELECT id, category, name, fansmm_service_id, price_per_1000, available FROM smm_services ORDER BY category, id").fetchall()
        out = ""
        for sid, cat, n, fid, p, av in rows:
            out += f"{'🟢' if av else '🔴'} <code>{sid}</code> {cat} · {n} · ₹{p} · FanSMM: <code>{fid or '—'}</code>\n"
        for i in range(0, len(out) or 1, 3800):
            await e.respond(out[i:i + 3800] or "No services.")

    @bot.on(events.NewMessage(pattern=r"^/setsmm (\d+) (\S+)(?: (\d+))?$"))
    async def _s(e):
        if e.sender_id not in ADMIN_IDS: return
        sid, fid, price = e.pattern_match.group(1), e.pattern_match.group(2), e.pattern_match.group(3)
        cur.execute("UPDATE smm_services SET fansmm_service_id=? WHERE id=?", (fid, sid))
        if price: cur.execute("UPDATE smm_services SET price_per_1000=? WHERE id=?", (int(price), sid))
        db.commit()
        await e.respond(f"{PE_CHECK} Service {sid} → FanSMM {fid}" + (f", ₹{price}/1K" if price else ""))

    @bot.on(events.NewMessage(pattern=r"^/smm(on|off) (\d+)$"))
    async def _o(e):
        if e.sender_id not in ADMIN_IDS: return
        on = e.pattern_match.group(1) == "on"
        cur.execute("UPDATE smm_services SET available=? WHERE id=?", (1 if on else 0, e.pattern_match.group(2))); db.commit()
        await e.respond(f"{PE_CHECK} Service {e.pattern_match.group(2)} {'enabled' if on else 'hidden'}")

    # ── admin / owner: add or deduct any user's balance ──
    @bot.on(events.NewMessage(pattern=r"^/(addbal|cutbal) (\d+) (\d+(?:\.\d+)?)(?: (.+))?$"))
    async def _bal_edit(e):
        if e.sender_id not in ADMIN_IDS: return
        act, t_uid = e.pattern_match.group(1), int(e.pattern_match.group(2))
        amt = float(e.pattern_match.group(3)); amt = int(amt) if amt.is_integer() else amt
        reason = e.pattern_match.group(4) or ""
        row = cur.execute("SELECT balance FROM users WHERE user_id=?", (t_uid,)).fetchone()
        if not row: return await e.respond(f"{P_NO} User <code>{t_uid}</code> not found.")
        async with get_user_lock(t_uid):
            if act == "addbal":
                cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, t_uid))
            else:
                cur.execute("UPDATE users SET balance=MAX(balance-?,0) WHERE user_id=?", (amt, t_uid))
            db.commit()
        new = cur.execute("SELECT balance FROM users WHERE user_id=?", (t_uid,)).fetchone()[0]
        sign = "➕ Added" if act == "addbal" else "➖ Deducted"
        await e.respond(f"<blockquote>{PE_CHECK} <b>{sign} {P_INR}{amt}</b>\n👤 <code>{t_uid}</code>\n{PE_CROWN} New balance: <b>{P_INR}{new}</b></blockquote>")
        try:
            await bot.send_message(t_uid, f"<blockquote>{PE_CROWN} <b>𝐁ᴀʟᴀɴᴄᴇ 𝐔ᴘᴅᴀᴛᴇᴅ</b>\n{sign} {P_INR}{amt}" + (f"\n📝 {html.escape(reason)}" if reason else "") + f"\n💰 𝐍ᴇᴡ ʙᴀʟᴀɴᴄᴇ: <b>{P_INR}{new}</b></blockquote>")
        except Exception: pass

    @bot.on(events.NewMessage(pattern=r"^/(checkbal|userbal) (\d+)$"))
    async def _bal_chk(e):
        if e.sender_id not in ADMIN_IDS: return
        r = cur.execute("SELECT balance FROM users WHERE user_id=?", (int(e.pattern_match.group(2)),)).fetchone()
        await e.respond(f"👤 <code>{e.pattern_match.group(2)}</code> → {P_INR}{r[0]}" if r else f"{P_NO} User not found.")

    logger.info("Social Media hub registered")

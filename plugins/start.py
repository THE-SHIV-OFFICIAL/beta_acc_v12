import os
from telethon import events, types
from telethon.errors import MessageNotModifiedError
from database import cur, db, ensure_user, is_user_banned, is_bot_online, is_admin
from utils.keyboards import get_persistent_menu, get_terms_buttons, get_join_buttons
from utils.helpers import check_channel_joined
from config import PE_FLOWER, PE_LOCATION, P_OFF, PE_HEART, PE_GIFT, P_GIFT, P_GLOBE, P_INR
from utils.states import session_buy_state, deposit_input

BANNER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "image.jpg")

async def send_main_menu(bot, event, uid):
    from utils.keyboards import get_main_inline_menu
    from database import to_usd
    me = await bot.get_me()
    bal_row = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
    bal = bal_row[0] if bal_row else 0
    name = "User"
    try:
        u = await bot.get_entity(uid)
        name = (u.first_name or "User").replace("<", "").replace(">", "")
    except Exception:
        pass
    msg = (f"<blockquote>{PE_HEART} <b>𝐇ᴇʟʟᴏ {name}, 𝐖ᴇʟᴄᴏᴍᴇ ᴛᴏ 𝐁ᴇᴛᴀ 𝐀ᴄᴄᴏᴜɴᴛ 𝐒ᴛᴏʀᴇ</b></blockquote>\n\n"
           f"🚀 <b>𝐄ɴᴊᴏʏ ғᴀsᴛ & sᴀғᴇ ᴀᴄᴄᴏᴜɴᴛ ʙᴜʏɪɴɢ ᴇxᴘᴇʀɪᴇɴᴄᴇ!</b>\n"
           f"━━━━━━━━━━━━━━━━━━\n"
           f"• <b>𝐘ᴏᴜʀ 𝐈𝐃:</b> <code>{uid}</code>\n"
           f"• <b>𝐘ᴏᴜʀ 𝐁ᴀʟᴀɴᴄᴇ:</b> {P_INR}{bal} | ${to_usd(bal):.2f}\n\n"
           f"<blockquote>{PE_GIFT} 𝐓ᴇʟᴇɢʀᴀᴍ 𝐀ᴄᴄᴏᴜɴᴛs • 𝐁ᴏᴛ 𝐑ᴇᴘᴏs • 𝐒𝐌𝐌 𝐒ᴇʀᴠɪᴄᴇs</blockquote>")
    # 1) bottom keyboard  2) banner with inline menu
    try:
        await bot.send_message(uid, f"{PE_FLOWER} <b>𝐌ᴀɪɴ 𝐌ᴇɴᴜ ʟᴏᴀᴅᴇᴅ</b>", buttons=get_persistent_menu(uid))
    except Exception:
        pass
    try:
        await bot.send_file(uid, BANNER, caption=msg, buttons=get_main_inline_menu())
    except Exception:
        await bot.send_message(uid, msg, buttons=get_main_inline_menu())

def register_start(bot):
    @bot.on(events.NewMessage(pattern=r"(?i)^(𝐒ᴛᴀʀᴛ|/start|🏠 𝐒ᴛᴀʀᴛ)"))
    async def handle_start(e):
        try:
            uid = e.sender_id
            if not uid: return
            
            is_new = cur.execute("SELECT 1 FROM users WHERE user_id=?", (uid,)).fetchone() is None
            
            ensure_user(uid)
            if is_user_banned(uid): return

            if not is_bot_online() and not is_admin(uid):
                return await e.respond(f"{P_OFF} <b>Bot is currently under maintenance.</b> Please try again later.")
            
            session_buy_state.pop(uid, None)
            deposit_input.pop(uid, None)

            text = e.text or ''
            if len(text.split()) > 1:
                start_param = text.split()[1]
                if start_param.startswith("ref_"):
                    ref = start_param.replace("ref_", "")
                    if ref.isdigit() and int(ref) != uid and is_new:
                        cur.execute("UPDATE users SET referred_by=? WHERE user_id=? AND referred_by IS NULL", (int(ref), uid))
                        db.commit()

            row = cur.execute("SELECT terms_accepted FROM users WHERE user_id=?", (uid,)).fetchone()
            terms_acc = row[0] if row else 0
            if not terms_acc:
                from plugins.social import TERMS_TEXT
                msg = TERMS_TEXT
                return await e.respond(msg, buttons=get_terms_buttons())

            await send_main_menu(bot, e, uid)
        except Exception as ex: 
            print(f"Start Error: {ex}")

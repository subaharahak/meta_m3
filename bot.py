import telebot
from flask import Flask
import threading
import re
import os
import threading
import time
import json
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
from p import check_card  # Make sure check_card(cc_line) is in p.py

# BOT Configuration
BOT_TOKEN = '7265564885:AAFZrs6Mi3aVf-hGT-b_iKBI3d7JCAYDo-A'   #ENTER UR BOT TOKEN
MAIN_ADMIN_ID = 5103348494  # Your main admin ID
ADMIN_IDS = [5103348494]  # Start with just you

bot = telebot.TeleBot(BOT_TOKEN)

AUTHORIZED_USERS = {}

# ---------------- Helper Functions ---------------- #

def load_admins():
    """Load admin list from file"""
    try:
        with open("admins.json", "r") as f:
            return json.load(f)
    except:
        return [MAIN_ADMIN_ID]

def save_admins(admins):
    """Save admin list to file"""
    with open("admins.json", "w") as f:
        json.dump(admins, f)

def is_admin(chat_id):
    """Check if user is an admin"""
    admins = load_admins()
    return chat_id in admins

def load_auth():
    try:
        with open("authorized.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_auth(data):
    with open("authorized.json", "w") as f:
        json.dump(data, f)

def is_authorized(msg):
    user_id = msg.from_user.id
    chat = msg.chat

    # ✅ Allow all admins anywhere
    if is_admin(user_id):
        return True

    # ✅ If message is from group and group is authorized
    if chat.type in ["group", "supergroup"]:
        return is_group_authorized(chat.id)

    # ✅ If private chat, only allow authorized users
    if chat.type == "private":
        if str(user_id) in AUTHORIZED_USERS:
            expiry = AUTHORIZED_USERS[str(user_id)]
            if expiry == "forever":
                return True
            if time.time() < expiry:
                return True
            else:
                del AUTHORIZED_USERS[str(user_id)]
                save_auth(AUTHORIZED_USERS)
        return False

    return False

def normalize_card(text):
    """
    Normalize credit card from any format to cc|mm|yy|cvv
    Similar to PHP normalize_card function
    """
    if not text:
        return None

    # Replace newlines and slashes with spaces
    text = text.replace('\n', ' ').replace('/', ' ')

    # Find all numbers in the text
    numbers = re.findall(r'\d+', text)

    cc = mm = yy = cvv = ''

    for part in numbers:
        if len(part) == 16:  # Credit card number
            cc = part
        elif len(part) == 4 and part.startswith('20'):  # 4-digit year starting with 20
            yy = part
        elif len(part) == 2 and int(part) <= 12 and mm == '':  # Month (2 digits <= 12)
            mm = part
        elif len(part) == 2 and not part.startswith('20') and yy == '':  # 2-digit year
            yy = '20' + part
        elif len(part) in [3, 4] and cvv == '':  # CVV (3-4 digits)
            cvv = part

    # Check if we have all required parts
    if cc and mm and yy and cvv:
        return f"{cc}|{mm}|{yy}|{cvv}"

    return None

# Load initial data
AUTHORIZED_USERS = load_auth()
ADMIN_IDS = load_admins()
#fr groups
GROUPS_FILE = 'authorized_groups.json'

def load_authorized_groups():
    if not os.path.exists(GROUPS_FILE):
        return []
    with open(GROUPS_FILE, 'r') as f:
        return json.load(f)

def save_authorized_groups(groups):
    with open(GROUPS_FILE, 'w') as f:
        json.dump(groups, f)

def is_group_authorized(group_id):
    return group_id in load_authorized_groups()
# ---------------- Admin Commands ---------------- #

@bot.message_handler(commands=['addadmin'])
def add_admin(msg):
    if msg.from_user.id != MAIN_ADMIN_ID:  # Only main admin can add other admins
        return bot.reply_to(msg, """✦━━━[ ᴀᴄᴄᴇꜱꜱ ᴅᴇɴɪᴇᴅ ]━━━✦

⟡ ᴏɴʟʏ ᴛʜᴇ ᴍᴀɪɴ ᴀᴅᴍɪɴ ᴄᴀɴ ᴀᴅᴅ ᴏᴛʜᴇʀ ᴀᴅᴍɪɴꜱ
⟡ ᴄᴏɴᴛᴀᴄᴛ ᴍᴀɪɴ ᴀᴅᴍɪɴ: @mhitzxg""")
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """✦━━━[ ɪɴᴠᴀʟɪᴅ ꜰᴏʀᴍᴀᴛ ]━━━✦

⟡ ᴜꜱᴀɢᴇ: `/addadmin <user_id>`
⟡ �xᴀᴍᴘʟᴇ: `/addadmin 1234567890`""")
        
        user_id = int(parts[1])
        admins = load_admins()
        
        if user_id in admins:
            return bot.reply_to(msg, """✦━━━[ ᴜꜱᴇʀ ᴀʟʀᴇᴀᴅʏ ᴀᴅᴍɪɴ ]━━━✦

⟡ ᴛʜɪꜱ ᴜꜱᴇʀ ɪꜱ ᴀʟʀᴇᴀᴅʏ ᴀɴ ᴀᴅᴍɪɴ""")
        
        admins.append(user_id)
        save_admins(admins)
        bot.reply_to(msg, f"""✦━━━[ ᴀᴅᴍɪɴ ᴀᴅᴅᴇᴅ ]━━━✦

⟡ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴀᴅᴅᴇᴅ `{user_id}` ᴀꜱ ᴀᴅᴍɪɴ
⟡ ᴛᴏᴛᴀʟ ᴀᴅᴍɪɴꜱ: {len(admins)}""")
        
    except ValueError:
        bot.reply_to(msg, """✦━━━[ ɪɴᴠᴀʟɪᴅ ᴜꜱᴇʀ ɪᴅ ]━━━✦

⟡ ᴘʟᴇᴀꜱᴇ ᴇɴᴛᴇʀ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍᴇʀɪᴄ ᴜꜱᴇʀ ɪᴅ
⟡ ᴜꜱᴀɢᴇ: `/addadmin 1234567890`""")
    except Exception as e:
        bot.reply_to(msg, f"""✦━━━[ ᴇʀʀᴏʀ ]━━━✦

⟡ ᴇʀʀᴏʀ: {str(e)}""")

@bot.message_handler(commands=['removeadmin'])
def remove_admin(msg):
    if msg.from_user.id != MAIN_ADMIN_ID:
        return bot.reply_to(msg, """✦━━━[ ᴀᴄᴄᴇꜱꜱ ᴅᴇɴɪᴇᴅ ]━━━✦

⟡ ᴏɴʟʏ ᴛʜᴇ ᴍᴀɪɴ ᴀᴅᴍɪɴ ᴄᴀɴ ʀᴇᴍᴏᴠᴇ ᴏᴛʜᴇʀ ᴀᴅᴍɪɴꜱ
⟡ ᴄᴏɴᴛᴀᴄᴛ ᴍᴀɪɴ ᴀᴅᴍɪɴ: @mhitzxg""")
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """✦━━━[ ɪɴᴠᴀʟɪᴅ ꜰᴏʀᴍᴀᴛ ]━━━✦

⟡ ᴜꜱᴀɢᴇ: `/removeadmin <user_id>`
⟡ ᴇxᴀᴍᴘʟᴇ: `/removeadmin 1234567890`""")
        
        user_id = int(parts[1])
        admins = load_admins()
        
        if user_id == MAIN_ADMIN_ID:
            return bot.reply_to(msg, """✦━━━[ ᴄᴀɴɴᴏᴛ ʀᴇᴍᴏᴠᴇ ᴍᴀɪɴ ᴀᴅᴍɪɴ ]━━━✦

⟡ ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʀᴇᴍᴏᴠᴇ ᴛʜᴇ ᴍᴀɪɴ ᴀᴅᴍɪɴ""")
        
        if user_id not in admins:
            return bot.reply_to(msg, """✦━━━[ ᴜꜱᴇʀ ɴᴏᴛ ᴀᴅᴍɪɴ ]━━━✦

⟡ ᴛʜɪꜱ ᴜꜱᴇʀ ɪꜱ ɴᴏᴛ ᴀɴ ᴀᴅᴍɪɴ""")
        
        admins.remove(user_id)
        save_admins(admins)
        bot.reply_to(msg, f"""✦━━━[ ᴀᴅᴍɪɴ ʀᴇᴍᴏᴠᴇᴅ ]━━━✦

⟡ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ʀᴇᴍᴏᴠᴇᴅ `{user_id}` ꜰʀᴏᴍ ᴀᴅᴍɪɴꜱ
⟡ ᴛᴏᴛᴀʟ ᴀᴅᴍɪɴꜱ: {len(admins)}""")
        
    except ValueError:
        bot.reply_to(msg, """✦━━━[ ɪɴᴠᴀʟɪᴇ ᴜꜱᴇʀ ɪᴅ ]━━━✦

⟡ ᴘʟᴇᴀꜱᴇ ᴇɴᴛᴇʀ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍᴇʀɪᴄ ᴜꜱᴇʀ ɪᴅ
⟡ ᴜꜱᴀɢᴇ: `/removeadmin 1234567890`""")
    except Exception as e:
        bot.reply_to(msg, f"""✦━━━[ ᴇʀʀᴏʀ ]━━━✦

⟡ ᴇʀʀᴏʀ: {str(e)}""")

@bot.message_handler(commands=['listadmins'])
def list_admins(msg):
    if not is_admin(msg.from_user.id):
        return bot.reply_to(msg, """✦━━━[ ᴀᴄᴄᴇꜱꜱ �ᴇɴɪᴇᴅ ]━━━✦

⟡ ᴏɴʟʏ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴠɪᴇᴡ ᴀᴅᴍɪɴ ʟɪꜱᴛ
⟡ ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ꜰᴏʀ ᴀᴜᴛʜᴏʀɪᴢᴀᴛɪᴏɴ""")
    
    admins = load_admins()
    if not admins:
        return bot.reply_to(msg, """✦━━━[ ɴᴏ ᴀᴅᴍɪɴꜱ ]━━━✦

⟡ ɴᴏ ᴀᴅᴍɪɴꜱ ꜰᴏᴜɴᴅ""")
    
    admin_list = ""
    for i, admin_id in enumerate(admins, 1):
        if admin_id == MAIN_ADMIN_ID:
            admin_list += f"• `{admin_id}` (ᴍᴀɪɴ ᴀᴅᴍɪɴ) 👑\n"
        else:
            admin_list += f"• `{admin_id}`\n"
    
    bot.reply_to(msg, f"""✦━━━[ ᴀᴅᴍɪɴ ʟɪꜱᴛ ]━━━✦

{admin_list}
⟡ ᴛᴏᴛᴀʟ ᴀᴅᴍɪɴꜱ: {len(admins)}""")
@bot.message_handler(commands=['authgroup'])
def authorize_group(msg):
    if msg.from_user.id != MAIN_ADMIN_ID:
        return bot.reply_to(msg, """✦━━━[ ᴀᴄᴄᴇꜱꜱ ᴅᴇɴɪᴇᴅ ]━━━✦

⟡ ᴏɴʟʏ ᴍᴀɪɴ ᴀᴅᴍɪɴ ᴄᴀɴ ᴀᴜᴛʜᴏʀɪᴢᴇ ɢʀᴏᴜᴘꜱ""")

    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """✦━━━[ ɪɴᴠᴀʟɪᴅ ꜰᴏʀᴍᴀᴛ ]━━━✦

⟡ ᴜꜱᴀɢᴇ: `/authgroup <group_id>`
⟡ ᴇxᴀᴍᴘʟᴇ: `/authgroup -1001234567890`""")

        group_id = int(parts[1])
        groups = load_authorized_groups()

        if group_id in groups:
            return bot.reply_to(msg, """✦━━━[ ᴀʟʀᴇᴀᴅʏ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ]━━━✦

⟡ ᴛʜɪꜱ ɢʀᴏᴜᴘ ɪꜱ ᴀʟʀᴇᴀᴅʏ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ""")

        groups.append(group_id)
        save_authorized_groups(groups)
        bot.reply_to(msg, f"""✦━━━[ ɢʀᴏᴜᴘ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ]━━━✦

⟡ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ɢʀᴏᴜᴘ: `{group_id}`
⟡ ᴛᴏᴛᴀʟ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ɢʀᴏᴜᴘꜱ: {len(groups)}""")

    except ValueError:
        bot.reply_to(msg, """✦━━━[ ɪɴᴠᴀʟɪᴅ ɢʀᴏᴜᴘ ɪᴅ ]━━━✦

⟡ ᴘʟᴇᴀꜱᴇ ᴇɴᴛᴇʀ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍᴇʀɪᴄ ɢʀᴏᴜᴘ ɪᴅ""")
    except Exception as e:
        bot.reply_to(msg, f"""✦━━━[ ᴇʀʀᴏʀ ]━━━✦

⟡ ᴇʀʀᴏʀ: {str(e)}""")

# ---------------- Bot Commands ---------------- #

@bot.message_handler(commands=['start'])
def start_handler(msg):
    bot.reply_to(msg, """ ★ 𝑲𝒓𝒂𝒕𝒐𝒔 𝑩3 𝑨𝑼𝑻𝑯 𝗖𝗛𝗘𝗖𝗞𝗘𝗥 ★

‪‪❤︎‬ ᴏɴʟʏ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴍᴇᴍʙᴇʀꜱ ᴄᴀɴ ᴜꜱᴇ ᴛʜɪꜱ ʙᴏᴛ
‪‪❤︎‬ ᴜꜱᴇ /b3 ᴛᴏ ᴄʜᴇᴄᴋ ꜱɪɴɢʟᴇ ᴄᴀʀᴅ
‪‪❤︎‬ ꜰᴏʀ ᴍᴀꜱꜱ ᴄʜᴇᴄᴋ, ʀᴇᴘʟʏ ᴄᴄ ꜰɪʟᴇ ᴡɪᴛʜ /mb3

☁︎ ʙᴏᴛ ᴘᴏᴡᴇʀᴇᴅ ʙʏ @mhitzxg""")

@bot.message_handler(commands=['auth'])
def authorize_user(msg):
    if not is_admin(msg.from_user.id):  # Changed to use is_admin function
        return
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, "❌ Usage: /auth <user_id> [days]")
        user = parts[1]
        days = int(parts[2]) if len(parts) > 2 else None

        if user.startswith('@'):
            return bot.reply_to(msg, "❌ Use numeric Telegram ID, not @username.")

        uid = int(user)
        expiry = "forever" if not days else time.time() + (days * 86400)
        AUTHORIZED_USERS[str(uid)] = expiry
        save_auth(AUTHORIZED_USERS)

        msg_text = f"✅ Authorized {uid} for {days} days." if days else f"✅ Authorized {uid} forever."
        bot.reply_to(msg, msg_text)
    except Exception as e:
        bot.reply_to(msg, f"❌ Error: {e}")

@bot.message_handler(commands=['rm'])
def remove_auth(msg):
    if not is_admin(msg.from_user.id):  # Changed to use is_admin function
        return
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, "❌ Usage: /rm <user_id>")
        uid = int(parts[1])
        if str(uid) in AUTHORIZED_USERS:
            del AUTHORIZED_USERS[str(uid)]
            save_auth(AUTHORIZED_USERS)
            bot.reply_to(msg, f"✅ Removed {uid} from authorized users.")
        else:
            bot.reply_to(msg, "❌ User is not authorized.")
    except Exception as e:
        bot.reply_to(msg, f"❌ Error: {e}")

@bot.message_handler(commands=['b3'])
def b3_handler(msg):
    if not is_authorized(msg):
        return bot.reply_to(msg, """✦━━━[  ᴀᴄᴄᴇꜱꜱ ᴅᴇɴɪᴇᴅ ]━━━✦

⟡ ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴛᴏ ᴜꜱᴇ �ʜɪꜱ ʙᴏᴛ
⟡ ᴏɴʟʏ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴍᴇᴍʙᴇʀꜱ ᴜꜱᴇ ᴛʜɪꜱ ʙᴏᴛ

✧ ᴘʟᴇᴀꜱᴇ ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ꜰᴏʀ ᴀᴜᴛʜᴏʀɪᴢᴀᴛɪᴏɴ
✧ ᴀᴅᴍɪɴ: @mhitzxg""")

    cc = None

    # Check if user replied to a message
    if msg.reply_to_message:
        # Extract CC from replied message
        replied_text = msg.reply_to_message.text or ""
        cc = normalize_card(replied_text)

        if not cc:
            return bot.reply_to(msg, "✦━━━[ ɪɴᴠᴀʟɪᴅ ꜰᴏʀᴍᴀᴛ ]━━━✦\n\n"
"⟡ ᴄᴏᴜʟᴅɴ'ᴛ ᴇxᴛʀᴀᴄᴛ ᴠᴀʟɪᴅ ᴄᴀʀᴅ ɪɴꜰᴏ ꜰʀᴏᴍ ʀᴇᴘʟɪᴇᴅ ᴍᴇꜱꜱᴀɢᴇ\n\n"
"ᴄᴏʀʀᴇᴄᴛ ꜰᴏʀᴍᴀᴛ\n\n"
"`/b3 4556737586899855|12|2026|123`\n\n"
"✧ ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ɪꜰ ʏᴏᴜ ɴᴇᴇᴅ ʜᴇʟᴘ")
    else:
        # Check if CC is provided as argument
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return bot.reply_to(msg, "✦━━━[ ɪɴᴠᴀʟɪᴅ ꜰᴏʀᴍᴀᴛ ]━━━✦\n\n"
"⟡ ᴘʟᴇᴀꜱᴇ ᴜꜱᴇ ᴛʜᴇ ᴄᴏʀʀᴇᴄᴛ ꜰᴏʀᴍᴀᴛ ᴛᴏ ᴄʜᴇᴄᴋ ᴄᴀʀᴅꜱ\n\n"
"ᴄᴏʀʀᴇᴄᴛ ꜰᴏʀᴍᴀᴛ\n\n"
"`/b3 4556737586899855|12|2026|123`\n\n"
"ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇꜱꜱᴀɢᴇ ᴄᴏɴᴛᴀɪɴɪɴɢ ᴄᴄ ᴡɪᴛʜ `/b3`\n\n"
"✧ ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ɪꜰ ʏᴏᴜ ɴᴇᴇᴅ ʜᴇʟᴘ")

        # Try to normalize the provided CC
        raw_input = args[1]

        # Check if it's already in valid format
        if re.match(r'^\d{16}\|\d{2}\|\d{2,4}\|\d{3,4}$', raw_input):
            cc = raw_input
        else:
            # Try to normalize the card
            cc = normalize_card(raw_input)

            # If normalization failed, use the original input
            if not cc:
                cc = raw_input

    processing = bot.reply_to(msg, "✦━━━[  ᴘʀᴏᴄᴇꜱꜱɪɴɢ ]━━━✦\n\n"
"⟡ ʏᴏᴜʀ ᴄᴀʀᴅ ɪꜱ ʙᴇɪɴɢ ᴄʜᴇᴄᴋ...\n"
"⟡ ᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ ᴀ ꜰᴇᴡ ꜱᴇᴄᴏɴᴅꜱ\n\n"
"✧ ᴅᴏ ɴᴏᴛ ꜱᴘᴀᴍ ᴏʀ ʀᴇꜱᴜʙᴍɪᴛ ✧")

    def check_and_reply():
        try:
            result = check_card(cc)  # This function must be in your p.py
            bot.edit_message_text(result, msg.chat.id, processing.message_id, parse_mode='HTML')
        except Exception as e:
            bot.edit_message_text(f"❌ Error: {str(e)}", msg.chat.id, processing.message_id)

    threading.Thread(target=check_and_reply).start()

@bot.message_handler(commands=['mb3'])
def mb3_handler(msg):
    if not is_authorized(msg):
        return bot.reply_to(msg, """✦━━━[  ᴀᴄᴄᴇꜱꜱ ᴅᴇɴɪᴇᴅ ]━━━✦

⟡ ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴛᴏ ᴜꜱᴇ ᴛʜɪꜱ ʙᴏᴛ
⟡ ᴏɴʟʏ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴍᴇᴍʙᴇʀꜱ ᴜꜱᴇ ᴛʜɪꜱ ʙᴏᴛ

✧ ᴘʟᴇᴀꜱᴇ ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ꜰᴏʀ ᴀᴜᴛʜᴏʀɪᴢᴀᴛɪᴏɴ
✧ ᴀᴅᴍɪɴ: @mhitzxg""")

    if not msg.reply_to_message:
        return bot.reply_to(msg, "✦━━━[ ᴡʀᴏɴɢ ᴜꜱᴀɢᴇ ]━━━✦\n\n"
"⟡ ᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀ `.txt` ꜰɪʟᴇ ᴏʀ ᴄʀᴇᴅɪᴛ ᴄᴀʀᴅ ᴛᴇxᴛ\n\n"
"✧ ᴏɴʟʏ ᴠᴀʟɪᴅ ᴄᴀʀᴅꜱ ᴡɪʟʟ ʙᴇ ᴄʜᴇᴄᴋᴇᴅ & ᴀᴘᴘʀᴏᴠᴇᴅ ᴄᴀʀᴅꜱ ꜱʜᴏᴡɴ ✧")

    reply = msg.reply_to_message

    # Detect whether it's file or raw text
    if reply.document:
        file_info = bot.get_file(reply.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        text = downloaded_file.decode('utf-8', errors='ignore')
    else:
        text = reply.text or ""
        if not text.strip():
            return bot.reply_to(msg, "❌ Empty text message.")

    # Extract CCs using improved normalization
    cc_lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Try to normalize each line
        normalized_cc = normalize_card(line)
        if normalized_cc:
            cc_lines.append(normalized_cc)
        else:
            # Fallback to original regex patterns
            found = re.findall(r'\b(?:\d[ -]*?){13,16}\b.*?\|.*?\|.*?\|.*', line)
            if found:
                cc_lines.extend(found)
            else:
                parts = re.findall(r'\d{12,16}[|: -]\d{1,2}[|: -]\d{2,4}[|: -]\d{3,4}', line)
                cc_lines.extend(parts)

    if not cc_lines:
        return bot.reply_to(msg, "✦━━━[ ⚠️ ɴᴏ ᴠᴀʟɪᴅ ᴄᴀʀᴅꜱ ꜰᴏᴜɴᴅ ]━━━✦\n\n"
"⟡ ɴᴏ ᴠᴀʟɪᴅ ᴄʀᴇᴅɪᴛ ᴄᴀʀᴅꜱ ᴅᴇᴛᴇᴄᴛᴇᴅ ɪɴ ᴛʜᴇ ꜰɪʟᴇ\n"
"⟡ ᴘʟᴇᴀꜱᴇ ᴍᴀᴋᴇ ꜱᴜʀᴇ ᴛʜᴇ ᴄᴀʀᴅꜱ ᴀʀᴇ ɪɴ ᴄᴏʀʀᴇᴄᴛ ꜰᴏʀᴍᴀᴛ\n\n"
"ᴄᴏʀʀᴇᴄᴛ ꜰᴏʀᴍᴀᴛ\n"
"`4556737586899855|12|2026|123`\n\n"
"✧ ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ɪꜰ ʏᴏᴜ ɴᴇᴇᴅ ʜᴇʟᴘ")

    if not reply.document and len(cc_lines) > 15:
        return bot.reply_to(msg, "✦━━━[ ⚠️ ʟɪᴍɪᴛ ᴇxᴄᴇᴇᴅᴇᴅ ]━━━✦\n\n"
"⟡ ᴏɴʟʏ 15 ᴄᴀʀᴅꜱ ᴀʟʟᴏᴡᴇᴅ ɪɴ ʀᴀᴡ ᴘᴀꜱᴛᴇ\n"
"⟡ ꜰᴏʀ ᴍᴏʀᴇ ᴄᴀʀᴅꜱ, ᴘʟᴇᴀꜱᴇ ᴜᴘʟᴏᴀᴅ ᴀ `.txt` ꜰɪʟᴇ")

    total = len(cc_lines)
    user_id = msg.from_user.id

    # Determine where to send messages (group or private)
    chat_id = msg.chat.id if msg.chat.type in ["group", "supergroup"] else user_id

    # Initial Message with Inline Buttons
    kb = InlineKeyboardMarkup(row_width=1)
    buttons = [
        InlineKeyboardButton(f"ᴀᴘᴘʀᴏᴠᴇᴅ 0 ✅", callback_data="none"),
        InlineKeyboardButton(f"ᴅᴇᴄʟɪɴᴇᴅ 0 ❌", callback_data="none"),
        InlineKeyboardButton(f"ᴛᴏᴛᴀʟ ᴄʜᴇᴄᴋᴇᴅ 0", callback_data="none"),
        InlineKeyboardButton(f"ᴛᴏᴛᴀʟ {total} ✅", callback_data="none"),
    ]
    for btn in buttons:
        kb.add(btn)

    status_msg = bot.send_message(chat_id, f"✦━━━[  ᴍᴀꜱꜱ ᴄʜᴇᴄᴋ ꜱᴛᴀʀᴛᴇᴅ ]━━━✦\n\n"
"⟡ ᴘʀᴏᴄᴇꜱꜱɪɴɢ ʏᴏᴜʀ ᴄᴀʀᴅꜱ...\n"
"⟡ ᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ ᴀ ꜰᴇᴡ ᴍᴏᴍᴇɴᴛꜱ\n\n"
" ʟɪᴠᴇ ꜱᴛᴀᴛᴜꜱ ᴡɪʟʟ ʙᴇ ᴜᴘᴅᴀᴛᴇᴅ ʙᴇʟᴏᴡ", reply_markup=kb)

    approved, declined, checked = 0, 0, 0
    approved_cards = []  # To store all approved cards

    def process_all():
        nonlocal approved, declined, checked, approved_cards
        for cc in cc_lines:
            try:
                checked += 1
                result = check_card(cc.strip())
                if "APPROVED CC ✅" in result:
                    approved += 1
                    approved_cards.append(result)  # Store approved card
                    if MAIN_ADMIN_ID != user_id:
                        bot.send_message(MAIN_ADMIN_ID, f"✅ Approved by {user_id}:\n{result}", parse_mode='HTML')
                else:
                    declined += 1

                # Update inline buttons
                new_kb = InlineKeyboardMarkup(row_width=1)
                new_kb.add(
                    InlineKeyboardButton(f"ᴀᴘᴘʀᴏᴠᴇᴅ {approved} 🔥", callback_data="none"),
                    InlineKeyboardButton(f"ᴅᴇᴄʟɪɴᴇᴅ {declined} ❌", callback_data="none"),
                    InlineKeyboardButton(f"ᴛᴏᴛᴀʟ ᴄʜᴇᴄᴋᴇᴅ {checked} ✔️", callback_data="none"),
                    InlineKeyboardButton(f"ᴛᴏᴛᴀʟ {total} ✅", callback_data="none"),
                )
                bot.edit_message_reply_markup(chat_id, status_msg.message_id, reply_markup=new_kb)
                time.sleep(2)
            except Exception as e:
                bot.send_message(user_id, f"❌ Error: {e}")

        # After processing all cards, send the approved cards in one message
        if approved_cards:
            approved_message = "✦━━━[ ᴀᴘᴘʀᴏᴠᴇᴅ ᴄᴀʀᴅꜱ ]━━━✦\n\n"
            approved_message += "\n".join(approved_cards)
            
            # Split the message if it's too long (Telegram has a 4096 character limit)
            if len(approved_message) > 4000:
                parts = [approved_message[i:i+4000] for i in range(0, len(approved_message), 4000)]
                for part in parts:
                    bot.send_message(chat_id, part, parse_mode='HTML')
                    time.sleep(1)
            else:
                bot.send_message(chat_id, approved_message, parse_mode='HTML')

        # Final status message
        bot.send_message(chat_id, "✦━━━[ ᴄʜᴇᴄᴋɪɴɢ ᴄᴏᴍᴘʟᴇᴛᴇᴅ ]━━━✦\n\n"
"⟡ ᴀʟʟ ᴄᴀʀᴅꜱ ʜᴀᴠᴇ ʙᴇᴇɴ ᴘʀᴏᴄᴇꜱꜱᴇᴅ\n"
f"⟡ ᴀᴘᴘʀᴏᴠᴇᴅ: {approved} | ᴅᴇᴄʟɪɴᴇᴅ: {declined}\n\n"
"✧ ᴛʜᴀɴᴋ ʏᴏᴜ ꜰᴏʀ ᴜꜱɪɴɢ ᴍᴀꜱꜱ ᴄʜᴇᴄᴋ ✧")

    threading.Thread(target=process_all).start()

# ---------------- Start Bot ---------------- #
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()

keep_alive()
bot.infinity_polling()
















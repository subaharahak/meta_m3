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
PREMIUM_USERS = {}

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

def load_premium():
    try:
        with open("premium_users.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_premium(data):
    with open("premium_users.json", "w") as f:
        json.dump(data, f)

def load_keys():
    try:
        with open("premium_keys.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_keys(data):
    with open("premium_keys.json", "w") as f:
        json.dump(data, f)

def is_premium(user_id):
    """Check if user has premium subscription"""
    user_id = str(user_id)
    if user_id in PREMIUM_USERS:
        expiry = PREMIUM_USERS[user_id]
        if expiry == "forever":
            return True
        if time.time() < expiry:
            return True
        else:
            del PREMIUM_USERS[user_id]
            save_premium(PREMIUM_USERS)
    return False

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
PREMIUM_USERS = load_premium()
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

def generate_key(length=16):
    """Generate a random premium key"""
    import random
    import string
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def get_user_info(user_id):
    """Get user info for display in responses"""
    try:
        user = bot.get_chat(user_id)
        username = f"@{user.username}" if user.username else f"User {user_id}"
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        
        if is_admin(user_id):
            user_type = "Admin 👑"
        elif is_premium(user_id):
            user_type = "Premium User 💎"
        else:
            user_type = "Free User 🆓"
            
        return {
            "username": username,
            "full_name": full_name,
            "user_type": user_type,
            "user_id": user_id
        }
    except:
        if is_admin(user_id):
            user_type = "Admin 👑"
        elif is_premium(user_id):
            user_type = "Premium User 💎"
        else:
            user_type = "Free User 🆓"
        return {
            "username": f"User {user_id}",
            "full_name": f"User {user_id}",
            "user_type": user_type,
            "user_id": user_id
        }

def check_proxy_status():
    """Check if proxy is live or dead"""
    try:
        # Simple check by trying to access a reliable site
        import requests
        test_url = "https://www.google.com"
        response = requests.get(test_url, timeout=5)
        if response.status_code == 200:
            return "Live ✅"
        else:
            return "Dead ❌"
    except:
        return "Dead ❌"

def get_subscription_info(user_id):
    """Get subscription information for a user"""
    user_id_str = str(user_id)
    
    # Check if user is admin first
    if is_admin(user_id):
        return "Unlimited ♾️", "Never"
    
    if user_id_str in PREMIUM_USERS:
        expiry = PREMIUM_USERS[user_id_str]
        if expiry == "forever":
            return "Forever 🎉", "Never"
        else:
            expiry_date = datetime.fromtimestamp(expiry)
            remaining_days = (expiry_date - datetime.now()).days
            return f"{remaining_days} days", expiry_date.strftime("%Y-%m-%d %H:%M:%S")
    else:
        return "No subscription ❌", "N/A"

# ---------------- Admin Commands ---------------- #

@bot.message_handler(commands=['addadmin'])
def add_admin(msg):
    if msg.from_user.id != MAIN_ADMIN_ID:  # Only main admin can add other admins
        return bot.reply_to(msg, """✦┌───[ ACCESS DENIED ]───┐✦

┠ ONLY THE MAIN ADMIN CAN ADD OTHER ADMINS
┠ CONTACT MAIN ADMIN: @mhitzxg""")
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """✦┌───[ INVALID FORMAT ]───┐✦

┠ USAGE: `/addadmin <user_id>`
┠  EXAMPLE: `/addadmin 1234567890`""")
        
        user_id = int(parts[1])
        admins = load_admins()
        
        if user_id in admins:
            return bot.reply_to(msg, """✦┌───[ USER ALREADY ADMIN ]───┐✦

┠ THIS USER IS ALREADY AN ADMIN""")
        
        admins.append(user_id)
        save_admins(admins)
        bot.reply_to(msg, f"""✦┌───[ ADMIN ADDED ]───┐✦

┠ SUCCESSFULLY ADDED `{user_id}` AS ADMIN
┠ TOTAL ADMINS: {len(admins)}""")
        
    except ValueError:
        bot.reply_to(msg, """✦┌───[ INVALID USER ID ]───┐✦

┠ PLEASE ENTER A VALID NUMERIC USER ID
┠ USAGE: `/addadmin 1234567890`""")
    except Exception as e:
        bot.reply_to(msg, f"""✦┌───[ ERROR ]───┐✦

┠ ERROR: {str(e)}""")

@bot.message_handler(commands=['removeadmin'])
def remove_admin(msg):
    if msg.from_user.id != MAIN_ADMIN_ID:
        return bot.reply_to(msg, """✦┌───[ ACCESS DENIED ]───┐✦

┠ ONLY THE MAIN ADMIN CAN REMOVE OTHER ADMINS
┠ CONTACT MAIN ADMIN: @mhitzxg""")
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """✦┌───[ INVALID FORMAT ]───┐✦

┠ USAGE: `/removeadmin <user_id>`
┠ EXAMPLE: `/removeadmin 1234567890`""")
        
        user_id = int(parts[1])
        admins = load_admins()
        
        if user_id == MAIN_ADMIN_ID:
            return bot.reply_to(msg, """✦┌───[ CANNOT REMOVE MAIN ADMIN ]───┐✦

┠ YOU CANNOT REMOVE THE MAIN ADMIN""")
        
        if user_id not in admins:
            return bot.reply_to(msg, """✦┌───[ USER NOT ADMIN ]───┐✦

┠ THIS USER IS NOT AN ADMIN""")
        
        admins.remove(user_id)
        save_admins(admins)
        bot.reply_to(msg, f"""✦┌───[ ADMIN REMOVED ]───┐✦

┠ SUCCESSFULLY REMOVED `{user_id}` FROM ADMINS
┠ TOTAL ADMINS: {len(admins)}""")
        
    except ValueError:
        bot.reply_to(msg, """✦┌───[ INVALID USER ID ]───┐✦

┠ PLEASE ENTER A VALID NUMERIC USER ID
┠ USAGE: `/removeadmin 1234567890`""")
    except Exception as e:
        bot.reply_to(msg, f"""✦┌───[ ERROR ]───┐✦

┠ ERROR: {str(e)}""")

@bot.message_handler(commands=['listadmins'])
def list_admins(msg):
    if not is_admin(msg.from_user.id):
        return bot.reply_to(msg, """✦┌───[ ACCESS DENIED ]───┐✦

┠ ONLY ADMINS CAN VIEW ADMIN LIST
┠ CONTACT ADMIN FOR AUTHORIZATION""")
    
    admins = load_admins()
    if not admins:
        return bot.reply_to(msg, """✦┌───[ NO ADMINS ]───┐✦

┠ NO ADMINS FOUND""")
    
    admin_list = ""
    for i, admin_id in enumerate(admins, 1):
        if admin_id == MAIN_ADMIN_ID:
            admin_list += f"• `{admin_id}` (MAIN ADMIN) 👑\n"
        else:
            admin_list += f"• `{admin_id}`\n"
    
    bot.reply_to(msg, f"""✦┌───[ ADMIN LIST ]───┐✦

{admin_list}
┠ TOTAL ADMINS: {len(admins)}""")

@bot.message_handler(commands=['authgroup'])
def authorize_group(msg):
    if msg.from_user.id != MAIN_ADMIN_ID:
        return bot.reply_to(msg, """✦┌───[ ACCESS DENIED ]───┐✦

┠ ONLY MAIN ADMIN CAN AUTHORIZE GROUPS""")

    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """✦┌───[ INVALID FORMAT ]───┐✦

┠ USAGE: `/authgroup <group_id>`
┠ EXAMPLE: `/authgroup -1001234567890`""")

        group_id = int(parts[1])
        groups = load_authorized_groups()

        if group_id in groups:
            return bot.reply_to(msg, """✦┌───[ ALREADY AUTHORIZED ]───┐✦

┠ THIS GROUP IS ALREADY AUTHORIZED""")

        groups.append(group_id)
        save_authorized_groups(groups)
        bot.reply_to(msg, f"""✦┌───[ GROUP AUTHORIZED ]───┐✦

┠ SUCCESSFULLY AUTHORIZED GROUP: `{group_id}`
┠ TOTAL AUTHORIZED GROUPS: {len(groups)}""")

    except ValueError:
        bot.reply_to(msg, """✦┌───[ INVALID GROUP ID ]───┐✦

┠ PLEASE ENTER A VALID NUMERIC GROUP ID""")
    except Exception as e:
        bot.reply_to(msg, f"""✦┌───[ ERROR ]───┐✦

┠ ERROR: {str(e)}""")

# ---------------- Subscription Commands ---------------- #

@bot.message_handler(commands=['subscription'])
def subscription_info(msg):
    """Show subscription plans"""
    user_id = msg.from_user.id
    
    if is_premium(user_id):
        expiry = PREMIUM_USERS[str(user_id)]
        if expiry == "forever":
            expiry_text = "Forever 🎉"
        else:
            expiry_date = datetime.fromtimestamp(expiry).strftime("%Y-%m-%d %H:%M:%S")
            expiry_text = f"Until {expiry_date}"
        
        bot.reply_to(msg, f"""✦┌───[ PREMIUM STATUS ]───┐✦

┠ YOU ARE A PREMIUM USER 💎
┠ EXPIRY: {expiry_text}
┠ UNLIMITED CARD CHECKS 🚀

┠ THANKS FOR PURCHASING 📩""")
    else:
        bot.reply_to(msg, """✦┌───[ FREE ACCOUNT ]───┐✦

┠ YOU ARE CURRENTLY A FREE USER 🆓
┠ LIMIT: 25 CARDS PER CHECK 📊

✦┌───[ PREMIUM PLANS ]───┐✦

┠ 7 DAYS - $3 💰
┠ 30 DAYS - $10 💰
┠ 90 DAYS - $25 💰
┠ 365 DAYS - $80 💰

✦┌───[ PREMIUM FEATURES ]───┐✦

💎 𝗣𝗿𝗲𝗺𝗶𝘂𝗺 𝗙𝗲𝗮𝘁𝘂𝗿𝗲𝘀:
• Unlimited card checks 🚀
• Priority processing ⚡
• No waiting time ⏰

┠ CONTACT @mhitzxg FOR PURCHASE 📩""")

@bot.message_handler(commands=['genkey'])
def generate_premium_key(msg):
    """Generate premium keys (admin only)"""
    if not is_admin(msg.from_user.id):
        return bot.reply_to(msg, """✦┌───[ ACCESS DENIED ]───┐✦

┠ ONLY ADMINS CAN GENERATE KEYS""")
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """✦┌───[ INVALID FORMAT ]───┐✦

┠ USAGE: `/genkey <duration>`
┠ EXAMPLES:
   `/genkey 7day`
   `/genkey 1month`
   `/genkey 3month`
   `/genkey 1year`
   `/genkey forever`""")
        
        duration = parts[1].lower()
        keys = load_keys()
        
        # Calculate expiry time
        if duration == "forever":
            expiry = "forever"
            duration_text = "Forever 🎉"
        elif "day" in duration:
            days = int(''.join(filter(str.isdigit, duration)))
            expiry = time.time() + (days * 86400)
            duration_text = f"{days} days 📅"
        elif "month" in duration:
            months = int(''.join(filter(str.isdigit, duration)))
            expiry = time.time() + (months * 30 * 86400)
            duration_text = f"{months} months 📅"
        elif "year" in duration:
            years = int(''.join(filter(str.isdigit, duration)))
            expiry = time.time() + (years * 365 * 86400)
            duration_text = f"{years} years 📅"
        else:
            return bot.reply_to(msg, """✦┌───[ INVALID DURATION ]───┐✦

┠ PLEASE USE ONE OF:
   `7day`, `1month`, `3month`, `1year`, `forever`""")
        
        # Generate key
        key = generate_key()
        keys[key] = {
            "expiry": expiry,
            "duration": duration_text,
            "created": time.time(),
            "used": False,
            "used_by": None
        }
        
        save_keys(keys)
        
        bot.reply_to(msg, f"""✦┌───[ PREMIUM KEY GENERATED ]───┐✦

┠ KEY: `{key}`
┠ DURATION: {duration_text}
┠ USE WITH: `/redeem {key}`""")
        
    except Exception as e:
        bot.reply_to(msg, f"""✦┌───[ ERROR ]───┐✦

┠ ERROR: {str(e)}""")

@bot.message_handler(commands=['redeem'])
def redeem_key(msg):
    """Redeem a premium key"""
    user_id = msg.from_user.id
    
    if is_premium(user_id):
        return bot.reply_to(msg, """✦┌───[ ALREADY PREMIUM ]───┐✦

┠ YOU ARE ALREADY A PREMIUM USER 💎""")
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """✦┌───[ INVALID FORMAT ]───┐✦

┠ USAGE: `/redeem <key>`
┠ EXAMPLE: `/redeem ABCDEF1234567890`""")
        
        key = parts[1].upper()
        keys = load_keys()
        
        if key not in keys:
            return bot.reply_to(msg, """✦┌───[ INVALID KEY ]───┐✦

┠ THE KEY YOU ENTERED IS INVALID""")
        
        key_data = keys[key]
        
        if key_data["used"]:
            return bot.reply_to(msg, """✦┌───[ KEY ALREADY USED ]───┐✦

┠ THIS KEY HAS ALREADY BEEN USED""")
        
        # Mark key as used
        keys[key]["used"] = True
        keys[key]["used_by"] = user_id
        keys[key]["redeemed_at"] = time.time()
        save_keys(keys)
        
        # Add user to premium
        PREMIUM_USERS[str(user_id)] = key_data["expiry"]
        save_premium(PREMIUM_USERS)
        
        if key_data["expiry"] == "forever":
            expiry_text = "Forever 🎉"
        else:
            expiry_date = datetime.fromtimestamp(key_data["expiry"]).strftime("%Y-%m-%d %H:%M:%S")
            expiry_text = f"Until {expiry_date}"
        
        bot.reply_to(msg, f"""✦┌───[ PREMIUM ACTIVATED ]───┐✦

┠ YOUR ACCOUNT HAS BEEN UPGRADED TO PREMIUM 💎
┠ DURATION: {key_data['duration']}
┠ EXPIRY: {expiry_text}

┠ YOU CAN NOW CHECK UNLIMITED CARDS 🚀""")
        
        # Notify admin
        bot.send_message(MAIN_ADMIN_ID, f"""✦┌───[ PREMIUM REDEEMED ]───┐✦

┠ USER: {user_id}
┠ KEY: {key}
┠ DURATION: {key_data['duration']}""")
        
    except Exception as e:
        bot.reply_to(msg, f"""✦┌───[ ERROR ]───┐✦

┠ ERROR: {str(e)}""")

# ---------------- Info Command ---------------- #

@bot.message_handler(commands=['info'])
def user_info(msg):
    """Show user information"""
    user_id = msg.from_user.id
    user_data = get_user_info(user_id)
    remaining, expiry_date = get_subscription_info(user_id)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    info_message = f"""✦┌───[ USER INFORMATION ]───┐✦

👤 𝗡𝗮𝗺𝗲: {user_data['full_name']}
🆔 𝗧𝗲𝗹𝗲𝗴𝗿𝗮𝗺 𝗜𝗗: `{user_data['user_id']}`
📛 𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲: {user_data['username']}
🎭 𝗨𝘀𝗲𝗿 𝗧𝘆𝗽𝗲: {user_data['user_type']}

💎 𝗦𝘂𝗯𝘀𝗰𝗿𝗶𝗽𝘁𝗶𝗼𝗻: {remaining}
📅 𝗘𝘅𝗽𝗶𝗿𝘆 𝗗𝗮𝘁𝗲: {expiry_date}
🕒 𝗖𝘂𝗿𝗿𝗲𝗻𝘁 𝗧𝗶𝗺𝗲: {current_time}

✦┌───[ BOT STATUS ]───┐✦

📌 𝗣𝗿𝗼𝘅𝘆: {check_proxy_status()}
📊 𝗔𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱: {'Yes ✅' if is_authorized(msg) else 'No ❌'}

☽︎ BOT POWERED BY @mhitzxg"""
    
    bot.reply_to(msg, info_message, parse_mode='Markdown')

# ---------------- Bot Commands ---------------- #

@bot.message_handler(commands=['start'])
def start_handler(msg):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    welcome_message = f"""✦┌─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┐✦
        ★ 𝘽𝙧𝙖𝙞𝙣 𝘽3 𝘼𝙐𝙏𝙃 𝗖𝗛𝗘𝗖𝗞𝗘𝗥 ★
✦└─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┘✦

┌────────────────────────────────────────────────────────┐
│ ✨ 𝗪𝗲𝗹𝗰𝗼𝗺𝗲 {msg.from_user.first_name or 'User'}! ✨                            
├────────────────────────────────────────────────────────┤
│ 🌟 𝗔𝗱𝘃𝗮𝗻𝗰𝗲𝗱 𝗖𝗮𝗿𝗱 𝗖𝗵𝗲𝗰𝗸𝗶𝗻𝗴 𝗕𝗼𝘁 🌟                          
├────────────────────────────────────────────────────────┤
│ 📋 𝗔𝘃𝗮𝗶𝗹𝗮𝗯𝗹𝗲 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀:                                  
│
│ • /start          - Start the Bot.      
│ • /b3             - Check single card.                  
│ • /mb3            - Mass check (reply to file).         
│ • /info           - Show your account information.      
│ • /subscription   - View premium plans.                 
├────────────────────────────────────────────────────────┤
│ 📓 𝗙𝗿𝗲𝗲 𝗧𝗶𝗲𝗿:                                        
│ • 25 cards per check 📊                                
│ • Standard processing speed 🐢                         
├────────────────────────────────────────────────────────┤
│ 🕒 𝗖𝘂𝗿𝗿𝗲𝗻𝘁 𝗧𝗶𝗺𝗲: {current_time}                       
│ 📌 𝗣𝗿𝗼𝘅𝘆 𝗦𝘁𝗮𝘁𝘂𝘀: {check_proxy_status()}                   
├────────────────────────────────────────────────────────┤
│ 📩 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 @mhitzxg 𝗳𝗼𝗿 𝗽𝗿𝗲𝗺𝗶𝘂𝗺 𝗮𝗰𝗰𝗲𝘀𝘀                   
│ ☽︎ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 @mhitzxg 𝗮𝗻𝗱 @pr0xy_xd                     
└────────────────────────────────────────────────────────┘"""
    
    bot.reply_to(msg, welcome_message)

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
        return bot.reply_to(msg, """✦┌───[  ACCESS DENIED ]───┐✦

┠ YOU ARE NOT AUTHORIZED TO USE THIS BOT
┠ ONLY AUTHORIZED MEMBERS USE THIS BOT

✧ PLEASE CONTACT ADMIN FOR AUTHORIZATION
✧ ADMIN: @mhitzxg""")

    cc = None

    # Check if user replied to a message
    if msg.reply_to_message:
        # Extract CC from replied message
        replied_text = msg.reply_to_message.text or ""
        cc = normalize_card(replied_text)

        if not cc:
            return bot.reply_to(msg, "✦┌───[ INVALID FORMAT ]───┐✦\n\n"
"┠ COULDN'T EXTRACT VALID CARD INFO FROM REPLIED MESSAGE\n\n"
"CORRECT FORMAT\n\n"
"`/b3 4556737586899855|12|2026|123`\n\n"
"✧ CONTACT ADMIN IF YOU NEED HELP")
    else:
        # Check if CC is provided as argument
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return bot.reply_to(msg, "✦┌───[ INVALID FORMAT ]───┐✦\n\n"
"┠ PLEASE USE THE CORRECT FORMAT TO CHECK CARDS\n\n"
"CORRECT FORMAT\n\n"
"`/b3 4556737586899855|12|2026|123`\n\n"
"OR REPLY TO A MESSAGE CONTAINING CC WITH `/b3`\n\n"
"✧ CONTACT ADMIN IF YOU NEED HELP")

        # Try to normalize the provided CC
        raw_input = args[1]

        # Check if it's already in valid format
        if re.match(r'^\d{16}\|\d{2}\|\d{2,4}\|\d{3,4}, raw_input):
            cc = raw_input
        else:
            # Try to normalize the card
            cc = normalize_card(raw_input)

            # If normalization failed, use the original input
            if not cc:
                cc = raw_input

    processing = bot.reply_to(msg, "✦┌───[  PROCESSING ]───┐✦\n\n"
"┠ YOUR CARD IS BEING CHECK...\n"
"┠ PLEASE WAIT A FEW SECONDS\n\n"
"✧ DO NOT SPAM OR RESUBMIT ✧")

    def check_and_reply():
        try:
            result = check_card(cc)  # This function must be in your p.py
            # Add user info and proxy status to the result
            user_info_data = get_user_info(msg.from_user.id)
            user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
            proxy_status = check_proxy_status()
            
            # Format the result with the new information
            formatted_result = result.replace(
                "☽︎𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 𝗮𝗻𝗱 @pr0xy_xd』",
                f"👤𝗖𝗵𝗲𝗰𝗸𝗲𝗱 𝗯𝘆: {user_info}\n"
                f"📌𝗣𝗿𝗼𝘅𝘆: {proxy_status}\n"
                f"☽︎𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 𝗮𝗻𝗱 @pr0xy_xd』"
            )
            
            bot.edit_message_text(formatted_result, msg.chat.id, processing.message_id, parse_mode='HTML')
        except Exception as e:
            bot.edit_message_text(f"❌ Error: {str(e)}", msg.chat.id, processing.message_id)

    threading.Thread(target=check_and_reply).start()

@bot.message_handler(commands=['mb3'])
def mb3_handler(msg):
    if not is_authorized(msg):
        return bot.reply_to(msg, """✦┌───[  ACCESS DENIED ]───┐✦

┠ YOU ARE NOT AUTHORIZED TO USE THIS BOT
┠ ONLY AUTHORIZED MEMBERS USE THIS BOT

✧ PLEASE CONTACT ADMIN FOR AUTHORIZATION
✧ ADMIN: @mhitzxg""")

    if not msg.reply_to_message:
        return bot.reply_to(msg, "✦┌───[ WRONG USAGE ]───┐✦\n\n"
"┠ PLEASE REPLY TO A `.txt` FILE OR CREDIT CARD TEXT\n\n"
"✧ ONLY VALID CARDS WILL BE CHECKED & APPROVED CARDS SHOWN ✧")

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
        return bot.reply_to(msg, "✦┌───[ ⚠️ NO VALID CARDS FOUND ]───┐✦\n\n"
"┠ NO VALID CREDIT CARDS DETECTED IN THE FILE\n"
"┠ PLEASE MAKE SURE THE CARDS ARE IN CORRECT FORMAT\n\n"
"CORRECT FORMAT\n"
"`4556737586899855|12|2026|123`\n\n"
"✧ CONTACT ADMIN IF YOU NEED HELP")

    # Check card limit for free users (admins have no limitations)
    user_id = msg.from_user.id
    if not is_admin(user_id) and not is_premium(user_id) and len(cc_lines) > 25:
        return bot.reply_to(msg, f"""✦┌───[ LIMIT EXCEEDED ]───┐✦

┠ FREE USERS ARE LIMITED TO 25 CARDS PER CHECK
┠ YOU ATTEMPTED TO CHECK {len(cc_lines)} CARDS

✦┌───[ UPGRADE TO PREMIUM ]───┐✦

┠ GET UNLIMITED CARD CHECKS
┠ USE /subscription FOR MORE INFO
┠ CONTACT @mhitzxg FOR PURCHASE""")

    if not reply.document and len(cc_lines) > 15:
        return bot.reply_to(msg, "✦┌───[ ⚠️ LIMIT EXCEEDED ]───┐✦\n\n"
"┠ ONLY 15 CARDS ALLOWED IN RAW PASTE\n"
"┠ FOR MORE CARDS, PLEASE UPLOAD A `.txt` FILE")

    total = len(cc_lines)
    user_id = msg.from_user.id

    # Determine where to send messages (group or private)
    chat_id = msg.chat.id if msg.chat.type in ["group", "supergroup"] else user_id

    # Initial Message with Inline Buttons
    kb = InlineKeyboardMarkup(row_width=1)
    buttons = [
        InlineKeyboardButton(f"APPROVED 0 ✅", callback_data="none"),
        InlineKeyboardButton(f"DECLINED 0 ❌", callback_data="none"),
        InlineKeyboardButton(f"TOTAL CHECKED 0", callback_data="none"),
        InlineKeyboardButton(f"TOTAL {total} ✅", callback_data="none"),
    ]
    for btn in buttons:
        kb.add(btn)

    status_msg = bot.send_message(chat_id, f"✦┌───[  MASS CHECK STARTED ]───┐✦\n\n"
"┠ PROCESSING YOUR CARDS...\n"
"┠ PLEASE WAIT A FEW MOMENTS\n\n"
" LIVE STATUS WILL BE UPDATED BELOW", reply_markup=kb)

    # Initialize approved cards message
    approved_msg = None
    approved_cards_text = "✦┌───[ APPROVED CARDS ]───┐✦\n\n"

    approved, declined, checked = 0, 0, 0

    def process_all():
        nonlocal approved, declined, checked, approved_msg, approved_cards_text
        for cc in cc_lines:
            try:
                checked += 1
                result = check_card(cc.strip())
                if "APPROVED CC ✅" in result:
                    approved += 1
                    
                    # Add user info and proxy status to approved cards
                    user_info_data = get_user_info(msg.from_user.id)
                    user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
                    proxy_status = check_proxy_status()
                    
                    formatted_result = result.replace(
                        "☽︎𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 𝗮𝗻𝗱 @pr0xy_xd』",
                        f"👤𝗖𝗵𝗲𝗰𝗸𝗲𝗱 𝗯𝘆: {user_info}\n"
                        f"📌𝗣𝗿𝗼𝘅𝘆: {proxy_status}\n"
                        f"☽︎𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 𝗮𝗻𝗱 @pr0xy_xd』"
                    )
                    
                    # Update approved cards message
                    approved_cards_text += formatted_result + "\n\n"
                    
                    # Send or update the approved cards message immediately
                    if approved_msg is None:
                        # First approved card - create the message
                        approved_msg = bot.send_message(chat_id, approved_cards_text, parse_mode='HTML')
                    else:
                        # Update existing message with new approved card
                        try:
                            if len(approved_cards_text) > 4000:
                                # If message too long, send a new one
                                approved_cards_text = f"✦┌───[ APPROVED CARDS - CONTINUED ]───┐✦\n\n{formatted_result}\n\n"
                                approved_msg = bot.send_message(chat_id, approved_cards_text, parse_mode='HTML')
                            else:
                                bot.edit_message_text(approved_cards_text, chat_id, approved_msg.message_id, parse_mode='HTML')
                        except Exception:
                            # If edit fails, send new message
                            approved_msg = bot.send_message(chat_id, f"✦┌───[ APPROVED CARDS - NEW ]───┐✦\n\n{formatted_result}\n\n", parse_mode='HTML')
                            approved_cards_text = f"✦┌───[ APPROVED CARDS - NEW ]───┐✦\n\n{formatted_result}\n\n"
                    
                    # Notify admin if not admin themselves
                    if MAIN_ADMIN_ID != user_id:
                        bot.send_message(MAIN_ADMIN_ID, f"✅ Approved by {user_id}:\n{formatted_result}", parse_mode='HTML')
                else:
                    declined += 1

                # Update inline buttons
                new_kb = InlineKeyboardMarkup(row_width=1)
                new_kb.add(
                    InlineKeyboardButton(f"APPROVED {approved} 🔥", callback_data="none"),
                    InlineKeyboardButton(f"DECLINED {declined} ❌", callback_data="none"),
                    InlineKeyboardButton(f"TOTAL CHECKED {checked} ✔️", callback_data="none"),
                    InlineKeyboardButton(f"TOTAL {total} ✅", callback_data="none"),
                )
                bot.edit_message_reply_markup(chat_id, status_msg.message_id, reply_markup=new_kb)
                time.sleep(2)
            except Exception as e:
                bot.send_message(user_id, f"❌ Error: {e}")

        # Final status message
        user_info_data = get_user_info(msg.from_user.id)
        user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
        proxy_status = check_proxy_status()
        
        final_message = f"""✦┌───[ CHECKING COMPLETED ]───┐✦

┠ ALL CARDS HAVE BEEN PROCESSED
┠ APPROVED: {approved} | DECLINED: {declined}

👤𝗖𝗵𝗲𝗰𝗸𝗲𝗱 𝗯𝘆: {user_info}
📌𝗣𝗿𝗼𝘅𝘆: {proxy_status}

✧ THANK YOU FOR USING MASS CHECK ✧"""
        
        bot.send_message(chat_id, final_message)

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

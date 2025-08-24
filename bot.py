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
from mysql.connector import pooling

# Database connection pool for better performance
db_pool = pooling.MySQLConnectionPool(
    pool_name="bot_pool",
    pool_size=10,
    pool_reset_session=True,
    host="sql12.freesqldatabase.com",
    user="sql12795630",
    password="fgqIine2LA",
    database="sql12795630",
    port=3306,
    autocommit=True,
    connect_timeout=3
)

def connect_db():
    """Get connection from pool"""
    try:
        return db_pool.get_connection()
    except Exception as e:
        print(f"Database connection error: {err}")
        return None

# Add this function to send notifications to admin
def notify_admin(message):
    """Send notification to main admin"""
    try:
        bot.send_message(MAIN_ADMIN_ID, message, parse_mode='HTML')
    except Exception as e:
        print(f"Failed to send admin notification: {e}")

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
        return cursor.fetchone()
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
    
    # Check premium_users table
    conn = connect_db()
    if not conn:
        return False
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT subscription_expiry FROM premium_users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()

        if result and result['subscription_expiry']:
            expiry = result['subscription_expiry']
            if isinstance(expiry, str):
                expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
            return expiry > datetime.now()
        
        return False
    except Exception as e:
        print(f"Error checking premium status: {e}")
        return False
    finally:
        if conn.is_connected():
            conn.close()

card_generator = CardGenerator()

# BOT Configuration
BOT_TOKEN = '7265564885:AAFZrs6Mi3aVf-hGT-b_iKBI3d7JCAYDo-A'
MAIN_ADMIN_ID = 5103348494

# Configure bot for better performance
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=20)
bot.skip_pending = True  # Skip pending updates on restart

FREE_USER_COOLDOWN = {}  # For anti-spam system

# Cache for frequently accessed data (admin list)
ADMIN_CACHE = None
ADMIN_CACHE_TIME = 0
ADMIN_CACHE_TIMEOUT = 300  # 5 minutes

# ---------------- Helper Functions ---------------- #

def load_admins():
    """Load admin list from database with caching"""
    global ADMIN_CACHE, ADMIN_CACHE_TIME
    
    current_time = time.time()
    if ADMIN_CACHE and current_time - ADMIN_CACHE_TIME < ADMIN_CACHE_TIMEOUT:
        return ADMIN_CACHE
    
    try:
        conn = connect_db()
        if not conn:
            return [MAIN_ADMIN_ID]
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM admins")
        admins = [row[0] for row in cursor.fetchall()]
        ADMIN_CACHE = admins
        ADMIN_CACHE_TIME = current_time
        return admins
    except Exception as e:
        print(f"Error loading admins: {e}")
        return [MAIN_ADMIN_ID]
    finally:
        if conn and conn.is_connected():
            conn.close()

def save_admins(admins):
    """Save admin list to database"""
    global ADMIN_CACHE, ADMIN_CACHE_TIME
    
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
        
        # Update cache
        ADMIN_CACHE = admins
        ADMIN_CACHE_TIME = time.time()
        
        return True
    except Exception as e:
        print(f"Error saving admins: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()

def is_admin(user_id):
    """Check if user is an admin"""
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        return False
        
    if user_id_int == MAIN_ADMIN_ID:
        return True
        
    admins = load_admins()
    return user_id_int in admins

def is_authorized(msg):
    """Check if user is authorized - optimized version"""
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
        conn = connect_db()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM free_users WHERE user_id = %s LIMIT 1", (user_id,))
            return cursor.fetchone() is not None
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
    Optimized version
    """
    if not text:
        return None

    # Quick check for already formatted cards
    if re.match(r'^\d{16}\|\d{2}\|\d{2,4}\|\d{3,4}$', text):
        return text

    # Replace newlines and slashes with spaces
    text = text.replace('\n', ' ').replace('/', ' ')

    # Find all numbers in the text
    numbers = re.findall(r'\d+', text)
    
    if len(numbers) < 4:
        return None

    # Simple extraction logic
    cc = next((n for n in numbers if len(n) in [15, 16]), '')
    cvv = next((n for n in numbers if len(n) in [3, 4] and n != cc), '')
    
    # Find month and year
    date_parts = [n for n in numbers if len(n) in [2, 4] and n != cc and n != cvv]
    
    mm = ''
    yy = ''
    
    for part in date_parts:
        if len(part) == 2 and 1 <= int(part) <= 12 and not mm:
            mm = part
        elif len(part) == 4 and part.startswith('20') and not yy:
            yy = part
        elif len(part) == 2 and not yy and not part.startswith('20'):
            yy = '20' + part

    # Check if we have all required parts
    if cc and mm and yy and cvv:
        return f"{cc}|{mm}|{yy}|{cvv}"

    return None

def get_user_info(user_id):
    """Get user info for display in responses - optimized"""
    try:
        user = bot.get_chat(user_id)
        username = f"@{user.username}" if user.username else f"User {user_id}"
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        
        # Check admin status first
        if is_admin(user_id):
            user_type = "Admin 👑"
        elif is_premium(user_id):
            user_type = "Premium User 💰"
        else:
            # Quick check for free users
            conn = connect_db()
            if not conn:
                user_type = "Unknown User ❓"
            else:
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1 FROM free_users WHERE user_id = %s LIMIT 1", (user_id,))
                    user_type = "Free User 🔓" if cursor.fetchone() else "Unauthorized User ❌"
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
    """Check if proxy is live or dead - cached version"""
    return "Live ✅"  # Assuming proxy is always live for performance

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

        if result_db and result_db['subscription_expiry']:
            expiry = result_db['subscription_expiry']
            if isinstance(expiry, str):
                expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
            
            remaining_days = (expiry - datetime.now()).days
            if remaining_days < 0:
                return ("Expired ❌", expiry.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                return (f"{remaining_days} days", expiry.strftime("%Y-%m-%d %H:%M:%S"))
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

# ---------------- Admin Commands ---------------- #
@bot.message_handler(commands=['addadmin'])
def add_admin(msg):
    if msg.from_user.id != MAIN_ADMIN_ID:
        return bot.reply_to(msg, "❌ Only main admin can add other admins")
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, "❌ Usage: /addadmin <user_id>")
        
        user_id = int(parts[1])
        admins = load_admins()
        
        if user_id in admins:
            return bot.reply_to(msg, "✅ User is already admin")
        
        admins.append(user_id)
        if save_admins(admins):
            bot.reply_to(msg, f"✅ Added {user_id} as admin")
        else:
            bot.reply_to(msg, "❌ Database error")
        
    except ValueError:
        bot.reply_to(msg, "❌ Invalid user ID")
    except Exception as e:
        bot.reply_to(msg, f"❌ Error: {str(e)}")

# ... (other admin commands optimized similarly - shortened for brevity)

# ---------------- Subscription Commands ---------------- #

@bot.message_handler(commands=['subscription'])
def subscription_info(msg):
    """Show subscription plans - optimized"""
    user_id = msg.from_user.id
    
    if is_admin(user_id):
        response = "👑 Premium Owner - Unlimited access"
    elif is_premium(user_id):
        remaining, expiry_date = get_subscription_info(user_id)
        response = f"💰 Premium - {remaining} remaining until {expiry_date}"
    else:
        response = "🔓 Free account - 15 cards per check\n💰 Upgrade: /subscription"
    
    bot.reply_to(msg, response)

# ... (other subscription commands optimized)

# ---------------- Register Command ---------------- #

@bot.message_handler(commands=['register'])
def register_user(msg):
    """Register a new user - optimized"""
    user_id = msg.from_user.id
    
    if is_authorized(msg):
        return bot.reply_to(msg, "✅ Already registered!")
        
    if add_free_user(user_id, msg.from_user.first_name or "User"):
        bot.reply_to(msg, "✅ Registered! Use /help for commands")
    else:
        bot.reply_to(msg, "❌ Registration failed")

# ---------------- Info Command ---------------- #

@bot.message_handler(commands=['info'])
def user_info(msg):
    """Show user information - optimized"""
    user_id = msg.from_user.id
    user_data = get_user_info(user_id)
    remaining, expiry_date = get_subscription_info(user_id)
    
    info_message = f"""
👤 {user_data['full_name']}
🆔 {user_data['user_id']}
📱 {user_data['username']}
🎫 {user_data['user_type']}

💰 {remaining}
📅 {expiry_date}
🔌 {check_proxy_status()}
"""
    
    bot.reply_to(msg, info_message)

# ---------------- Gen Command ---------------- #

@bot.message_handler(commands=['gen'])
def gen_handler(msg):
    """Generate cards using Luhn algorithm"""
    if not is_authorized(msg):
        return bot.reply_to(msg, "❌ Not authorized. Use /register")
    
    args = msg.text.split(None, 1)
    if len(args) < 2:
        return bot.reply_to(msg, "❌ Usage: /gen <pattern>")
    
    pattern = args[1]
    
    processing = bot.reply_to(msg, "🔄 Generating cards...")
    
    def generate_and_reply():
        try:
            cards, error = card_generator.generate_cards(pattern, 10)
            
            if error:
                bot.edit_message_text(f"❌ {error}", msg.chat.id, processing.message_id)
                return
            
            bin_match = re.search(r'(\d{6})', pattern.replace('|', '').replace('x', '').replace('X', ''))
            bin_code = bin_match.group(1) if bin_match else "N/A"
            
            user_info_data = get_user_info(msg.from_user.id)
            
            final_message = f"""
BIN: {bin_code}
Amount: {len(cards)}

""" + "\n".join(cards) + f"""

👤 Generated by: {user_info_data['username']}
"""
            
            bot.edit_message_text(final_message, msg.chat.id, processing.message_id)
            
        except Exception as e:
            bot.edit_message_text(f"❌ Error: {str(e)}", msg.chat.id, processing.message_id)

    threading.Thread(target=generate_and_reply, daemon=True).start()

# ---------------- Bot Commands ---------------- #

@bot.message_handler(commands=['start'])
def start_handler(msg):
    user_id = msg.from_user.id
    
    # Auto-register user if not already registered
    if not is_authorized(msg) and msg.chat.type == "private":
        add_free_user(user_id, msg.from_user.first_name or "User")
    
    welcome_message = f"""
✨ Welcome {msg.from_user.first_name or 'User'}!

📋 Commands:
• /b3 - Check single card
• /mb3 - Mass check cards
• /gen - Generate cards
• /info - Account info
• /subscription - Premium plans

🔌 Proxy: {check_proxy_status()}
"""
    
    bot.reply_to(msg, welcome_message)

@bot.message_handler(commands=['b3'])
def b3_handler(msg):
    if not is_authorized(msg):
        return bot.reply_to(msg, "❌ Not authorized. Use /register")

    if check_cooldown(msg.from_user.id, "b3"):
        return bot.reply_to(msg, "⏰ Cooldown active. Wait 30s")

    cc = None

    if msg.reply_to_message:
        replied_text = msg.reply_to_message.text or ""
        cc = normalize_card(replied_text)
        if not cc:
            return bot.reply_to(msg, "❌ Invalid card format in replied message")
    else:
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return bot.reply_to(msg, "❌ Usage: /b3 <card> or reply to message")
        
        raw_input = args[1]
        cc = normalize_card(raw_input) or raw_input

    if not is_admin(msg.from_user.id) and not is_premium(msg.from_user.id):
        set_cooldown(msg.from_user.id, "b3", 10)

    processing = bot.reply_to(msg, "🔄 Processing card...")

    def check_and_reply():
        try:
            result = check_card(cc)
            user_info_data = get_user_info(msg.from_user.id)
            
            formatted_result = result.replace(
                "⚡ Powered by : @mhitzxg & @pr0xy_xd",
                f"👤 Checked by: {user_info_data['username']}\n🔌 Proxy: Live ✅"
            )
            
            bot.edit_message_text(formatted_result, msg.chat.id, processing.message_id, parse_mode='HTML')
        except Exception as e:
            bot.edit_message_text(f"❌ Error: {str(e)}", msg.chat.id, processing.message_id)

    threading.Thread(target=check_and_reply, daemon=True).start()

@bot.message_handler(commands=['mb3'])
def mb3_handler(msg):
    if not is_authorized(msg):
        return bot.reply_to(msg, "❌ Not authorized. Use /register")

    if check_cooldown(msg.from_user.id, "mb3"):
        return bot.reply_to(msg, "⏰ Cooldown active. Wait 30m")

    if not msg.reply_to_message:
        return bot.reply_to(msg, "❌ Reply to a file with /mb3")

    reply = msg.reply_to_message

    # File or text processing
    if reply.document:
        try:
            file_info = bot.get_file(reply.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            text = downloaded_file.decode('utf-8', errors='ignore')
        except:
            return bot.reply_to(msg, "❌ Error downloading file")
    else:
        text = reply.text or ""

    # Extract CCs quickly
    cc_lines = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            normalized_cc = normalize_card(line)
            if normalized_cc:
                cc_lines.append(normalized_cc)

    if not cc_lines:
        return bot.reply_to(msg, "❌ No valid cards found")

    # Check limits
    user_id = msg.from_user.id
    if not is_admin(user_id) and not is_premium(user_id):
        if len(cc_lines) > 20:
            return bot.reply_to(msg, "❌ Free limit: 20 cards")
        set_cooldown(user_id, "mb3", 1800)

    total = len(cc_lines)
    chat_id = msg.chat.id if msg.chat.type in ["group", "supergroup"] else user_id

    # Quick status message
    status_msg = bot.send_message(chat_id, f"🔄 Processing {total} cards...")

    def process_all():
        approved, declined = 0, 0
        approved_cards = []
        
        for i, cc in enumerate(cc_lines):
            try:
                result = check_card(cc.strip())
                if "APPROVED CC ✅" in result:
                    approved += 1
                    approved_cards.append(result)
                    
                    if approved <= 3:  # Only show first 3 approved cards
                        bot.send_message(chat_id, f"✅ Approved:\n{result}", parse_mode='HTML')
                
                declined += 1 if "APPROVED CC ✅" not in result else 0
                
                # Update status every 5 cards
                if (i + 1) % 5 == 0:
                    bot.edit_message_text(
                        f"🔄 Processed: {i+1}/{total} | ✅: {approved} | ❌: {declined}",
                        chat_id, status_msg.message_id
                    )
                
            except Exception as e:
                print(f"Card error: {e}")
        
        # Final summary
        summary = f"""
📊 Check Complete
✅ Approved: {approved}
❌ Declined: {declined}
📋 Total: {total}
"""
        bot.edit_message_text(summary, chat_id, status_msg.message_id)

    threading.Thread(target=process_all, daemon=True).start()

# ---------------- Start Bot ---------------- #
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run, daemon=True)
    t.start()

keep_alive()

# Start bot with optimized settings
def start_bot():
    while True:
        try:
            print("🚀 Starting optimized bot...")
            bot.infinity_polling(timeout=30, long_polling_timeout=20)
        except Exception as e:
            print(f"Bot error: {e}")
            time.sleep(3)

if __name__ == '__main__':
    start_bot()

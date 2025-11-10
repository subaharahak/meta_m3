from gen import CardGenerator
from braintree_checker import check_card_braintree, check_cards_braintree, initialize_braintree
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
from ch import check_card_stripe, check_cards_stripe
from st import check_single_cc, check_mass_cc, test_charge
from payp import check_card_paypal  
from sh import check_card_shopify, check_cards_shopify
import mysql.connector
from mysql.connector import pooling

# Global variables to control mass checking
MASS_CHECK_ACTIVE = {
    'mch': False,
    'mbr': False, 
    'mpp': False,
    'msh': False,
    'mst': False
}

# Mass check tracking
MASS_CHECK_SESSIONS = {}
MASS_CHECK_APPROVED_CARDS = {}  # Store approved cards by session

# Temporary storage for mass check data
TEMP_MASS_DATA = {}

APPROVED_CHANNEL_ID = "-1003290219349"  # Channel to forward approved cards

initialize_braintree()
PAYPAL_MAINTENANCE = False

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
        send_long_message(APPROVED_CHANNEL_ID, message, parse_mode='HTML')
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
            "SELECT * FROM premium_keys WHERE `key` = %s AND used_by IS NULL AND revoked = 0",
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
            "UPDATE premium_keys SET used_by = %s, used_at = NOW() WHERE `key` = %s AND revoked = 0",
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

def revoke_key(key):
    """Revoke a premium key"""
    conn = connect_db()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE premium_keys SET revoked = 1 WHERE `key` = %s",
            (key,)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error revoking key: {e}")
        return False
    finally:
        if conn.is_connected():
            conn.close()

def delete_key(key):
    """Delete a premium key"""
    conn = connect_db()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM premium_keys WHERE `key` = %s",
            (key,)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting key: {e}")
        return False
    finally:
        if conn.is_connected():
            conn.close()

def get_all_keys():
    """Get all premium keys"""
    conn = connect_db()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM premium_keys ORDER BY created_at DESC")
        return cursor.fetchall()
    except Exception as e:
        print(f"Error getting keys: {e}")
        return []
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

def remove_premium(user_id):
    """Remove premium subscription from user"""
    conn = connect_db()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM premium_users WHERE user_id = %s", (user_id,))
        conn.commit()
        
        # Clear cache for this user
        user_id_str = str(user_id)
        for key in list(user_cache.keys()):
            if user_id_str in key:
                del user_cache[key]
                
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error removing premium user: {e}")
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

# SINGLE BOT INSTANCE - FIX FOR CONFLICT ERROR
bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
bot.skip_pending = True  # Skip pending messages on start

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

    # ✅ If message is from group and group is authorized - FIXED: Check database for authorized groups
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

# For groups - FIXED: Using database instead of JSON file
def load_authorized_groups():
    """Load authorized groups from database"""
    cache_key = "authorized_groups"
    if cache_key in user_cache and time.time() - user_cache[cache_key]['time'] < cache_timeout:
        return user_cache[cache_key]['result']
    
    try:
        conn = connect_db()
        if not conn:
            return []
        cursor = conn.cursor()
        cursor.execute("SELECT group_id FROM authorized_groups")
        groups = [row[0] for row in cursor.fetchall()]
        # Cache the result
        user_cache[cache_key] = {'result': groups, 'time': time.time()}
        return groups
    except Exception as e:
        print(f"Error loading authorized groups: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            conn.close()

def save_authorized_groups(group_id):
    """Save authorized group to database"""
    try:
        conn = connect_db()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute("INSERT IGNORE INTO authorized_groups (group_id) VALUES (%s)", (group_id,))
        conn.commit()
        # Clear cache
        if "authorized_groups" in user_cache:
            del user_cache["authorized_groups"]
        return True
    except Exception as e:
        print(f"Error saving authorized group: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()

def remove_authorized_group(group_id):
    """Remove authorized group from database"""
    try:
        conn = connect_db()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute("DELETE FROM authorized_groups WHERE group_id = %s", (group_id,))
        conn.commit()
        # Clear cache
        if "authorized_groups" in user_cache:
            del user_cache["authorized_groups"]
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error removing authorized group: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()

def is_group_authorized(group_id):
    """Check if group is authorized"""
    return group_id in load_authorized_groups()

# ---------------- Mass Check Session Management ---------------- #

def create_mass_check_session(user_id, gateway, total_cards, message_id, output_format="message"):
    """Create a new mass check session"""
    session_id = f"{user_id}_{gateway}_{int(time.time())}"
    MASS_CHECK_SESSIONS[session_id] = {
        'user_id': user_id,
        'gateway': gateway,
        'total_cards': total_cards,
        'current_card': 0,
        'approved': 0,
        'declined': 0,
        'message_id': message_id,
        'paused': False,
        'cancelled': False,
        'start_time': time.time(),
        'chat_id': None,
        'output_format': output_format  # "message" or "txt"
    }
    
    # Initialize approved cards storage
    MASS_CHECK_APPROVED_CARDS[session_id] = []
    
    return session_id

def get_mass_check_session(user_id, gateway):
    """Get active mass check session for user"""
    for session_id, session in MASS_CHECK_SESSIONS.items():
        if (session['user_id'] == user_id and 
            session['gateway'] == gateway and 
            not session['cancelled']):
            return session_id, session
    return None, None

def update_mass_check_progress(session_id, current_card, approved, declined):
    """Update mass check progress"""
    if session_id in MASS_CHECK_SESSIONS:
        MASS_CHECK_SESSIONS[session_id]['current_card'] = current_card
        MASS_CHECK_SESSIONS[session_id]['approved'] = approved
        MASS_CHECK_SESSIONS[session_id]['declined'] = declined

def add_approved_card(session_id, card_result):
    """Add approved card to session storage"""
    if session_id in MASS_CHECK_APPROVED_CARDS:
        MASS_CHECK_APPROVED_CARDS[session_id].append(card_result)

def get_approved_cards(session_id):
    """Get approved cards for session"""
    return MASS_CHECK_APPROVED_CARDS.get(session_id, [])

def pause_mass_check(session_id):
    """Pause a mass check session"""
    if session_id in MASS_CHECK_SESSIONS:
        MASS_CHECK_SESSIONS[session_id]['paused'] = True
        return True
    return False

def resume_mass_check(session_id):
    """Resume a mass check session"""
    if session_id in MASS_CHECK_SESSIONS:
        MASS_CHECK_SESSIONS[session_id]['paused'] = False
        return True
    return False

def cancel_mass_check(session_id):
    """Cancel a mass check session"""
    if session_id in MASS_CHECK_SESSIONS:
        MASS_CHECK_SESSIONS[session_id]['cancelled'] = True
        # Also update the global flag
        gateway_key = MASS_CHECK_SESSIONS[session_id]['gateway']
        MASS_CHECK_ACTIVE[gateway_key] = False
        return True
    return False

def get_mass_check_stats_message(session, gateway_name):
    """Generate mass check stats message with inline buttons"""
    elapsed_time = time.time() - session['start_time']
    progress = (session['current_card'] / session['total_cards']) * 100 if session['total_cards'] > 0 else 0
    
    message = f"""
🎯 *{gateway_name} Mass Check*

📊 *Progress*: `{session['current_card']}/{session['total_cards']}` ({progress:.1f}%)
⏱️ *Elapsed*: `{elapsed_time:.1f}s`

✅ *Approved*: `{session['approved']}`
❌ *Declined*: `{session['declined']}`

🔄 *Status*: {'⏸️ PAUSED' if session['paused'] else '▶️ RUNNING'}
📤 *Output*: {'📝 Text File' if session.get('output_format') == 'txt' else '💬 Message'}
"""

    # Create inline keyboard
    keyboard = InlineKeyboardMarkup()
    
    if session['paused']:
        keyboard.add(
            InlineKeyboardButton("▶️ Resume", callback_data=f"resume_{session['gateway']}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{session['gateway']}")
        )
    else:
        keyboard.add(
            InlineKeyboardButton("⏸️ Pause", callback_data=f"pause_{session['gateway']}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{session['gateway']}")
        )
    
    return message, keyboard

def get_gateway_display_name(gateway_key):
    """Get display name for gateway"""
    gateway_names = {
        'mch': 'Stripe Auth',
        'mbr': 'Braintree Auth', 
        'mpp': 'PayPal Charge',
        'msh': 'Shopify Charge',
        'mst': 'Stripe Charge'
    }
    return gateway_names.get(gateway_key, 'Unknown Gateway')

# ---------------- Mass Check with Format Selection ---------------- #

def start_mass_check_with_format_selection(msg, gateway_key, gateway_name, cc_lines, check_function):
    """Start mass check with format selection"""
    user_id = msg.from_user.id
    total = len(cc_lines)
    
    # Determine where to send messages (group or private)
    chat_id = msg.chat.id if msg.chat.type in ["group", "supergroup"] else user_id

    # Create format selection keyboard
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("💬 In Message Format", callback_data=f"format_message_{gateway_key}"),
        InlineKeyboardButton("📝 In TXT Format", callback_data=f"format_txt_{gateway_key}")
    )
    
    format_msg = bot.send_message(
        chat_id,
        f"""
🎯 *{gateway_name} Mass Check*

📋 *Cards to check*: {total}
⚡ *Please select output format:*

💬 *Message Format* - Approved cards sent individually as messages
📝 *TXT Format* - Approved cards collected and sent as text file after completion

Choose your preferred format:""",
        parse_mode='Markdown',
        reply_markup=keyboard,
        reply_to_message_id=msg.message_id
    )
    
    # Store the card data temporarily in global dict
    temp_key = f"{user_id}_{gateway_key}"
    TEMP_MASS_DATA[temp_key] = {
        'user_id': user_id,
        'gateway_key': gateway_key,
        'gateway_name': gateway_name,
        'cc_lines': cc_lines,
        'check_function': check_function,
        'format_msg_id': format_msg.message_id,
        'chat_id': chat_id
    }

@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    """Handle ALL callback queries in one place"""
    try:
        data = call.data
        user_id = call.from_user.id
        
        print(f"📲 Callback received: {data} from user {user_id}")
        
        if data.startswith('format_'):
            # Handle format selection
            _, output_format, gateway_key = data.split('_', 2)
            temp_key = f"{user_id}_{gateway_key}"
            
            if temp_key not in TEMP_MASS_DATA:
                bot.answer_callback_query(call.id, "❌ Session expired! Please start again.")
                return
            
            temp_data = TEMP_MASS_DATA[temp_key]
            
            # Answer callback immediately
            bot.answer_callback_query(call.id, f"✅ Starting mass check...")
            
            # Delete format selection message
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            
            # Start mass check directly
            start_fast_mass_check(temp_data, output_format)
            
            # Clean up temporary data
            if temp_key in TEMP_MASS_DATA:
                del TEMP_MASS_DATA[temp_key]
                
        elif data.startswith('pause_'):
            # Handle pause
            _, gateway = data.split('_', 1)
            session_id, session = get_mass_check_session(user_id, gateway)
            
            if session and pause_mass_check(session_id):
                bot.answer_callback_query(call.id, "⏸️ Mass check paused!")
                gateway_name = get_gateway_display_name(gateway)
                message, keyboard = get_mass_check_stats_message(session, gateway_name)
                bot.edit_message_text(
                    message,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            else:
                bot.answer_callback_query(call.id, "❌ No active session found!")
                
        elif data.startswith('resume_'):
            # Handle resume
            _, gateway = data.split('_', 1)
            session_id, session = get_mass_check_session(user_id, gateway)
            
            if session and resume_mass_check(session_id):
                bot.answer_callback_query(call.id, "▶️ Mass check resumed!")
                gateway_name = get_gateway_display_name(gateway)
                message, keyboard = get_mass_check_stats_message(session, gateway_name)
                bot.edit_message_text(
                    message,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            else:
                bot.answer_callback_query(call.id, "❌ No active session found!")
                
        elif data.startswith('cancel_'):
            # Handle cancel
            _, gateway = data.split('_', 1)
            session_id, session = get_mass_check_session(user_id, gateway)
            
            if session and cancel_mass_check(session_id):
                bot.answer_callback_query(call.id, "❌ Mass check cancelled!")
                try:
                    bot.delete_message(call.message.chat.id, call.message.message_id)
                except:
                    pass
            else:
                bot.answer_callback_query(call.id, "❌ No active session found!")
                
    except Exception as e:
        print(f"❌ Callback error: {e}")
        bot.answer_callback_query(call.id, "❌ Error processing request!")

def start_fast_mass_check(temp_data, output_format):
    """Start fast mass check - SIMPLIFIED VERSION"""
    try:
        user_id = temp_data['user_id']
        gateway_key = temp_data['gateway_key']
        gateway_name = temp_data['gateway_name']
        cc_lines = temp_data['cc_lines']
        check_function = temp_data['check_function']
        chat_id = temp_data['chat_id']
        total = len(cc_lines)

        # Create initial stats session
        initial_session = {
            'user_id': user_id,
            'gateway': gateway_key,
            'total_cards': total,
            'current_card': 0,
            'approved': 0,
            'declined': 0,
            'message_id': None,
            'paused': False,
            'cancelled': False,
            'start_time': time.time(),
            'chat_id': chat_id,
            'output_format': output_format
        }
        
        # Send initial stats message
        message, keyboard = get_mass_check_stats_message(initial_session, gateway_name)
        stats_msg = bot.send_message(chat_id, message, parse_mode='Markdown', reply_markup=keyboard)
        
        # Create session
        session_id = create_mass_check_session(user_id, gateway_key, total, stats_msg.message_id, output_format)
        MASS_CHECK_SESSIONS[session_id]['chat_id'] = chat_id
        
        # Set mass check as active
        MASS_CHECK_ACTIVE[gateway_key] = True

        # Start processing in background - SIMPLE AND FAST
        thread = threading.Thread(
            target=fast_process_cards,
            args=(user_id, gateway_key, gateway_name, cc_lines, check_function, output_format, chat_id, total, stats_msg.message_id)
        )
        thread.daemon = True
        thread.start()
        
        print(f"🚀 FAST Mass check started for user {user_id} with {gateway_key}, format: {output_format}")
        
    except Exception as e:
        print(f"❌ Error starting mass check: {e}")
        error_msg = f"❌ Error starting mass check: {str(e)}"
        bot.send_message(chat_id, error_msg)

def fast_process_cards(user_id, gateway_key, gateway_name, cc_lines, check_function, output_format, chat_id, total, stats_msg_id):
    """FAST card processing - NO DELAYS, SIMPLE APPROACH"""
    try:
        approved = 0
        declined = 0
        start_time = time.time()
        approved_cards_list = []
        
        print(f"⚡ Starting FAST processing of {total} cards...")
        
        for i, cc_line in enumerate(cc_lines, 1):
            # Check if cancelled or paused
            session_id, session = get_mass_check_session(user_id, gateway_key)
            if not session or session.get('cancelled'):
                print("❌ Mass check cancelled")
                break
                
            # Handle pause - SIMPLE CHECK
            if session and session.get('paused'):
                while session and session.get('paused') and not session.get('cancelled'):
                    time.sleep(0.5)  # Shorter sleep for pause
                    session_id, session = get_mass_check_session(user_id, gateway_key)
                    if not session:
                        break
            
            if not session or session.get('cancelled'):
                break
            
            # Process card - FAST AND SIMPLE
            try:
                # Process card immediately without delays
                result = check_function(cc_line.strip())
                
                if "APPROVED" in result:
                    approved += 1
                    # Simple formatting
                    user_info_data = get_user_info(user_id)
                    user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
                    proxy_status = check_proxy_status()
                    
                    formatted_result = result.replace(
                        "🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』",
                        f"👤 Checked by: {user_info}\n🔌 Proxy: {proxy_status}\n🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』"
                    )
                    
                    # Store approved card
                    add_approved_card(session_id, formatted_result)
                    approved_cards_list.append(formatted_result)
                    
                    # Send to channel
                    try:
                        notify_channel(formatted_result)
                    except:
                        pass
                    
                    # Send to user based on format - IMMEDIATELY
                    if output_format == 'message':
                        approved_msg = f"🎉 *NEW APPROVED CARD* 🎉\n\n{formatted_result}\n\n• *Progress*: {i}/{total}\n• *Approved*: {approved} | *Declined*: {declined}"
                        try:
                            send_long_message(chat_id, approved_msg, parse_mode='HTML')
                        except:
                            pass
                        
                else:
                    declined += 1
                
                # Update progress immediately
                update_mass_check_progress(session_id, i, approved, declined)
                
                # Update stats message - LESS FREQUENTLY FOR SPEED
                if i % 3 == 0 or i == total or "APPROVED" in result:
                    session_id, session = get_mass_check_session(user_id, gateway_key)
                    if session and not session.get('cancelled'):
                        message, keyboard = get_mass_check_stats_message(session, gateway_name)
                        try:
                            bot.edit_message_text(
                                message,
                                chat_id,
                                stats_msg_id,
                                parse_mode='Markdown',
                                reply_markup=keyboard
                            )
                        except:
                            pass
                
                # NO SLEEP DELAY - MAXIMUM SPEED
                # Only tiny sleep to prevent overwhelming the system
                if i % 5 == 0:  # Small sleep every 5 cards
                    time.sleep(0.1)
                
            except Exception as e:
                print(f"❌ Error processing card {i}: {e}")
                declined += 1
        
        # Final cleanup
        MASS_CHECK_ACTIVE[gateway_key] = False
        
        # Update stats
        update_stats(approved=approved, declined=declined)
        for _ in range(approved):
            update_user_stats(user_id, approved=True)
        for _ in range(declined):
            update_user_stats(user_id, approved=False)
        
        # Delete stats message
        try:
            bot.delete_message(chat_id, stats_msg_id)
        except:
            pass
        
        # Send final results - FAST AND SIMPLE
        total_time = time.time() - start_time
        
        final_message = f"""
✅ *Mass Check Completed* ✅

📊 *Final Results*
• ✅ *Approved*: {approved}
• ❌ *Declined*: {declined}
• 📋 *Total*: {total}
• ⏰ *Time*: {total_time:.2f}s
• 🚀 *Speed*: {total/total_time:.2f} cards/sec

🎯 *Gateway*: {gateway_name}
📤 *Output Format*: {'💬 Message' if output_format == 'message' else '📝 TXT File'}
⚡ *Processing complete!*

👤 *Checked by*: {get_user_info(user_id)['username']}
🔌 *Proxy*: {check_proxy_status()}
"""
        
        if approved > 0 and output_format == 'txt':
            # Send as file
            file_content = "\n\n".join(approved_cards_list)
            file_buffer = io.BytesIO(file_content.encode('utf-8'))
            file_buffer.name = f'approved_{gateway_key}_{int(time.time())}.txt'
            try:
                bot.send_document(chat_id, file_buffer, caption=final_message, parse_mode='Markdown')
            except:
                send_long_message(chat_id, final_message + "\n📁 *Failed to send file*", parse_mode='Markdown')
        else:
            if approved > 0:
                final_message += f"\n🎉 *Found {approved} approved cards*"
            else:
                final_message += f"\n😔 *No approved cards found*"
            try:
                send_long_message(chat_id, final_message, parse_mode='Markdown')
            except:
                pass
            
        print(f"✅ Mass check completed: {approved} approved, {declined} declined, {total_time:.2f}s")
            
    except Exception as e:
        print(f"❌ Mass check processing error: {e}")
        error_msg = f"❌ Mass check error: {str(e)}"
        try:
            bot.send_message(chat_id, error_msg)
        except:
            pass

# Update the mass check handler to use the fast version
@bot.message_handler(commands=['mch', 'mbr', 'mpp', 'msh', 'mst'])
def mass_check_handler(msg):
    """Handle all mass check commands with format selection"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
🔰 *AUTHORIZATION REQUIRED* 🔰
 
• You are not authorized to use this command
• Only authorized users can check cards

✗ Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # Check for cooldown (10 minutes for free users)
    command = msg.text.split('@')[0].lower()
    if check_cooldown(msg.from_user.id, command):
        return send_long_message(msg.chat.id, """
⏰ *Cooldown Active* ⏰

• You are in cooldown period
• Please wait 10 minutes before mass checking again

✗ Upgrade to premium to remove cooldowns""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    if not msg.reply_to_message:
        return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Please reply to a .txt file with /{command}
• The file should contain card details

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

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
❌ *No Valid Cards* ❌

• No valid card formats found in the file
• Please check the file format

*Valid format*
`4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # Check card limit for free users (10 cards)
    user_id = msg.from_user.id
    if not is_admin(user_id) and not is_premium(user_id) and len(cc_lines) > 10:
        return send_long_message(msg.chat.id, f"""
❌ *Limit Exceeded* ❌

• Free users can only check 10 cards at once
• You tried to check {len(cc_lines)} cards

💰 *Upgrade To Premium* 💰

• Upgrade to premium for unlimited checks
• Use /subscription to view plans
• Contact @mhitzxg to purchase""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # Check if it's a raw paste (not a file) and limit for free users
    if not reply.document and not is_admin(user_id) and not is_premium(user_id) and len(cc_lines) > 15:
        return send_long_message(msg.chat.id, """
❌ *Too Many Cards* ❌

• You can only check 15 cards in a message
• Please use a .txt file for larger checks""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # Set cooldown for free users (10 minutes)
    if not is_admin(user_id) and not is_premium(user_id):
        set_cooldown(user_id, command, 600)  # 10 minutes = 600 seconds

    # Map commands to gateway keys and functions
    command_map = {
        '/mch': ('mch', 'Stripe Auth', check_card_stripe),
        '/mbr': ('mbr', 'Braintree Auth', lambda cc: check_card_braintree(cc)),
        '/mpp': ('mpp', 'PayPal Charge', check_card_paypal),
        '/msh': ('msh', 'Shopify Charge', check_card_shopify),
        '/mst': ('mst', 'Stripe Charge', test_charge)
    }
    
    gateway_key, gateway_name, check_function = command_map.get(command, (None, None, None))
    
    if not gateway_key:
        return send_long_message(msg.chat.id, """
❌ *Invalid Command* ❌

• Available mass check commands:
• /mch - Mass Stripe Auth
• /mbr - Mass Braintree Auth
• /mpp - Mass PayPal Charge
• /msh - Mass Shopify Charge
• /mst - Mass Stripe Charge""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # Start mass check with format selection
    start_mass_check_with_format_selection(msg, gateway_key, gateway_name, cc_lines, check_function)
# ---------------- Shopify Commands ---------------- #

@bot.message_handler(commands=['sh'])
def sh_handler(msg):
    """Check single card using Shopify gateway"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 *AUTHORIZATION REQUIRED* 🔰         

• You are not authorized to use this command
• Only authorized users can check cards

• Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # Check for spam (30 second cooldown for free users)
    if check_cooldown(msg.from_user.id, "sh"):
        return send_long_message(msg.chat.id, """
❌ *Cooldown Active* ❌

• You are in cooldown period
• Please wait 30 seconds before checking again

✗ Upgrade to premium to remove cooldowns""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    cc = None

    # Check if user replied to a message
    if msg.reply_to_message:
        # Extract CC from replied message
        replied_text = msg.reply_to_message.text or ""
        cc = normalize_card(replied_text)

        if not cc:
            return send_long_message(msg.chat.id, """
❌ *Invalid Card Format* ❌

• The replied message doesn't contain a valid card
• Please use the correct format:

*Valid format*
`/sh 4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    else:
        # Check if CC is provided as argument
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Please provide a card to check
• Usage: `/sh <card_details>`

*Valid format*
`/sh 4556737586899855|12|2026|123`

• Or reply to a message containing card details with /sh

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

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
⚙️ *Gateway - Shopify Charge 13.98$*

🔮 Initializing Shopify Gateway...
🔄 Connecting to Shopify API
📡 Establishing secure connection

⏳ *Status*: [▒▒▒▒▒▒▒▒▒▒] 0%
⚡ Please wait while we process your card""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    if isinstance(processing, list) and len(processing) > 0:
        processing = processing[0]

    def update_shopify_loading(message_id, progress, status):
        """Update Shopify loading animation"""
        bars = int(progress / 10)
        bar = "█" * bars + "▒" * (10 - bars)
        loading_text = f"""
⚙️ *Gateway - Shopify Charge 13.98$*

🔮 {status}
🔄 Processing your request
📡 Contacting Shopify gateway

⏳ *Status*: [{bar}] {progress}%
⚡ Almost there..."""
        
        try:
            edit_long_message(msg.chat.id, message_id, loading_text, parse_mode='Markdown')
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
                f"👤 Checked by: {user_info}\n🔌 Proxy: {proxy_status}\n🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』"
            )
            
            edit_long_message(msg.chat.id, processing.message_id, formatted_result, parse_mode='HTML')
            
            # If card is approved, send to channel
            if "APPROVED CC ✅" in result:
                notify_channel(formatted_result)
                
        except Exception as e:
            edit_long_message(msg.chat.id, processing.message_id, f"❌ Error: {str(e)}")

    threading.Thread(target=check_and_reply).start()

# ---------------- Braintree Commands ---------------- #

@bot.message_handler(commands=['br'])
def br_handler(msg):
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 *AUTHORIZATION REQUIRED* 🔰         

• You are not authorized to use this command
• Only authorized users can check cards

• Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # Check for spam (30 second cooldown for free users)
    if check_cooldown(msg.from_user.id, "br"):
        return send_long_message(msg.chat.id, """
❌ *Cooldown Active* ❌

• You are in cooldown period
• Please wait 30 seconds before checking again

✗ Upgrade to premium to remove cooldowns""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    cc = None

    # Check if user replied to a message
    if msg.reply_to_message:
        # Extract CC from replied message
        replied_text = msg.reply_to_message.text or ""
        cc = normalize_card(replied_text)

        if not cc:
            return send_long_message(msg.chat.id, """
❌ *Invalid Card Format* ❌

• The replied message doesn't contain a valid card
• Please use the correct format:

*Valid format*
`/br 4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    else:
        # Check if CC is provided as argument
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Please provide a card to check
• Usage: `/br <card_details>`

*Valid format*
`/br 4556737586899855|12|2026|123`

• Or reply to a message containing card details with /br

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

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
⚙️ *Gateway - Braintree Auth - 1*

🔮 Initializing Braintree Gateway...
🔄 Connecting to Braintree API
📡 Establishing secure connection

⏳ *Status*: [▒▒▒▒▒▒▒▒▒▒] 0%
⚡ Please wait while we process your card""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    if isinstance(processing, list) and len(processing) > 0:
        processing = processing[0]

    def update_braintree_loading(message_id, progress, status):
        """Update Braintree loading animation"""
        bars = int(progress / 10)
        bar = "█" * bars + "▒" * (10 - bars)
        loading_text = f"""
⚙️ *Gateway - Braintree Auth - 1*

🔮 {status}
🔄 Processing your request
📡 Contacting payment gateway

⏳ *Status*: [{bar}] {progress}%
⚡ Almost there..."""
        
        try:
            edit_long_message(msg.chat.id, message_id, loading_text, parse_mode='Markdown')
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
            
            # Use Braintree checker instead of regular check_card
            import asyncio
            from braintree_checker import check_card_braintree
            
            # Create new event loop for async call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(check_card_braintree(cc))
            loop.close()
            
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
                f"🔱 𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』"
            )
            
            edit_long_message(msg.chat.id, processing.message_id, formatted_result, parse_mode='HTML')
            
            # If card is approved, send to channel
            if "APPROVED CC ✅" in result:
                notify_channel(formatted_result)
                
        except Exception as e:
            edit_long_message(msg.chat.id, processing.message_id, f"❌ Error: {str(e)}")

    threading.Thread(target=check_and_reply).start()

# ---------------- Stripe Auth Commands ---------------- #

@bot.message_handler(commands=['ch'])
def ch_handler(msg):
    """Check single card using Stripe gateway"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 *AUTHORIZATION REQUIRED* 🔰         

• You are not authorized to use this command
• Only authorized users can check cards

• Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # Check for spam (30 second cooldown for free users)
    if check_cooldown(msg.from_user.id, "ch"):
        return send_long_message(msg.chat.id, """
❌ *Cooldown Active* ❌

• You are in cooldown period
• Please wait 30 seconds before checking again

✗ Upgrade to premium to remove cooldowns""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    cc = None

    # Check if user replied to a message
    if msg.reply_to_message:
        # Extract CC from replied message
        replied_text = msg.reply_to_message.text or ""
        cc = normalize_card(replied_text)

        if not cc:
            return send_long_message(msg.chat.id, """
❌ *Invalid Card Format* ❌

• The replied message doesn't contain a valid card
• Please use the correct format:

*Valid format*
`/ch 4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    else:
        # Check if CC is provided as argument
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Please provide a card to check
• Usage: `/ch <card_details>`

*Valid format*
`/ch 4556737586899855|12|2026|123`

• Or reply to a message containing card details with /ch

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

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
⚙️ *Gateway - Stripe Auth - 1*

🔮 Initializing Gateway...
🔄 Connecting to Stripe API
📡 Establishing secure connection

⏳ *Status*: [▒▒▒▒▒▒▒▒▒▒] 0%
⚡ Please wait while we process your card""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    if isinstance(processing, list) and len(processing) > 0:
        processing = processing[0]

    def update_loading(message_id, progress, status):
        """Update loading animation"""
        bars = int(progress / 10)
        bar = "█" * bars + "▒" * (10 - bars)
        loading_text = f"""
⚙️ *Gateway - Stripe Auth - 1*

🔮 {status}
🔄 Processing your request
📡 Contacting payment gateway

⏳ *Status*: [{bar}] {progress}%
⚡ Almost there..."""
        
        try:
            edit_long_message(msg.chat.id, message_id, loading_text, parse_mode='Markdown')
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

# ---------------- Stripe Charge Commands ---------------- #
@bot.message_handler(commands=['st'])
def st_handler(msg):
    """Check single card using Stripe gateway"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 *AUTHORIZATION REQUIRED* 🔰         

• You are not authorized to use this command
• Only authorized users can check cards

• Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # Check for spam (30 second cooldown for free users)
    if check_cooldown(msg.from_user.id, "ch"):
        return send_long_message(msg.chat.id, """
❌ *Cooldown Active* ❌

• You are in cooldown period
• Please wait 30 seconds before checking again

✗ Upgrade to premium to remove cooldowns""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    cc = None

    # Check if user replied to a message
    if msg.reply_to_message:
        # Extract CC from replied message
        replied_text = msg.reply_to_message.text or ""
        cc = normalize_card(replied_text)

        if not cc:
            return send_long_message(msg.chat.id, """
❌ *Invalid Card Format* ❌

• The replied message doesn't contain a valid card
• Please use the correct format:

*Valid format*
`/ch 4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    else:
        # Check if CC is provided as argument
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Please provide a card to check
• Usage: `/ch <card_details>`

*Valid format*
`/ch 4556737586899855|12|2026|123`

• Or reply to a message containing card details with /ch

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

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
⚙️ *Gateway - Stripe Charge 1$*

🔮 Initializing Gateway...
🔄 Connecting to Stripe API
📡 Establishing secure connection

⏳ *Status*: [▒▒▒▒▒▒▒▒▒▒] 0%
⚡ Please wait while we process your card""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    if isinstance(processing, list) and len(processing) > 0:
        processing = processing[0]

    def update_loading(message_id, progress, status):
        """Update loading animation"""
        bars = int(progress / 10)
        bar = "█" * bars + "▒" * (10 - bars)
        loading_text = f"""
⚙️ *Gateway - Stripe Charge 1$*

🔮 {status}
🔄 Processing your request
📡 Contacting payment gateway

⏳ *Status*: [{bar}] {progress}%
⚡ Almost there..."""
        
        try:
            edit_long_message(msg.chat.id, message_id, loading_text, parse_mode='Markdown')
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

# ---------------- PayPal Charge Commands ---------------- #

# ⚙️ Maintenance flag (set to True to activate)
 # <---- Change to True when gateway is under maintenance

@bot.message_handler(commands=['pp'])
def pp_handler(msg):
    """Check single card using PayPal gateway"""
    # 🚧 Maintenance check
    if PAYPAL_MAINTENANCE:
        return send_long_message(msg.chat.id, """
🚧 *PayPal Gateway Under Maintenance* 🚧

• The PayPal charge gateway is temporarily unavailable
• We're performing updates or server maintenance
• Please try again later

⚙️ *Status*: UNDER MAINTENANCE
💬 *Contact*: @mhitzxg
        """, reply_to_message_id=msg.message_id, parse_mode='Markdown')

    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 *AUTHORIZATION REQUIRED* 🔰         

• You are not authorized to use this command
• Only authorized users can check cards

• Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # Check for spam (30 second cooldown for free users)
    if check_cooldown(msg.from_user.id, "pp"):
        return send_long_message(msg.chat.id, """
❌ *Cooldown Active* ❌

• You are in cooldown period
• Please wait 30 seconds before checking again

✗ Upgrade to premium to remove cooldowns""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    cc = None

    # Check if user replied to a message
    if msg.reply_to_message:
        # Extract CC from replied message
        replied_text = msg.reply_to_message.text or ""
        cc = normalize_card(replied_text)

        if not cc:
            return send_long_message(msg.chat.id, """
❌ *Invalid Card Format* ❌

• The replied message doesn't contain a valid card
• Please use the correct format:

*Valid format*
`/pp 4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    else:
        # Check if CC is provided as argument
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Please provide a card to check
• Usage: `/pp <card_details>`

*Valid format*
`/pp 4556737586899855|12|2026|123`

• Or reply to a message containing card details with /pp

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

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
⚙️ *Gateway - PayPal Charge - 2$*

🔮 Initializing PayPal Gateway...
🔄 Connecting to PayPal API
📡 Establishing secure connection

⏳ *Status*: [▒▒▒▒▒▒▒▒▒▒] 0%
⚡ Please wait while we process your card""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    if isinstance(processing, list) and len(processing) > 0:
        processing = processing[0]

    def update_paypal_loading(message_id, progress, status):
        """Update PayPal loading animation"""
        bars = int(progress / 10)
        bar = "█" * bars + "▒" * (10 - bars)
        loading_text = f"""
⚙️ *Gateway - PayPal Charge - 2$*

🔮 {status}
🔄 Processing your request
📡 Contacting PayPal gateway

⏳ *Status*: [{bar}] {progress}%
⚡ Almost there..."""
        
        try:
            edit_long_message(msg.chat.id, message_id, loading_text, parse_mode='Markdown')
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
                
            # Add user info and proxy status to the result - FIXED VERSION
            user_info_data = get_user_info(msg.from_user.id)
            user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
            proxy_status = check_proxy_status()
            
            # FIX: Simple string concatenation instead of replace()
            formatted_result = result + f"\n👤 Checked by: {user_info}\n🔌 Proxy: {proxy_status}"
            
            edit_long_message(msg.chat.id, processing.message_id, formatted_result, parse_mode='HTML')
            
            # If card is approved, send to channel
            if "APPROVED CC ✅" in result:
                notify_channel(formatted_result)
                
        except Exception as e:
            edit_long_message(msg.chat.id, processing.message_id, f"❌ Error: {str(e)}")

    threading.Thread(target=check_and_reply).start()
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
            print("🎯 MHITZXG AUTH CHECKER Started Successfully!")
            print("🤖 Bot is now running...")
            print("⚡ Powered by @mhitzxg & @pr0xy_xd")
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"❌ Bot error: {e}")
            print("🔄 Restarting bot in 5 seconds...")
            time.sleep(5)

if __name__ == '__main__':
    start_bot()

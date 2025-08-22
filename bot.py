from gen import CardGenerator
import telebot
from flask import Flask
import threading
import re
import os
import threading
import time
import json
import random
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
from datetime import datetime, timedelta
from p import check_card  # Make sure check_card(cc_line) is in p.py
import mysql.connector

def connect_db():
    return mysql.connector.connect(
        host="sql12.freesqldatabase.com",         # e.g., sql.freesqldatabase.com
        user="sql12795630",     # e.g., sql12345678
        password="fgqIine2LA", # your DB password
        database="sql12795630",  # e.g., sql12345678
        port=3306
    )
def add_free_user(user_id, first_name):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT IGNORE INTO free_users (user_id, first_name) VALUES (%s, %s)",
        (user_id, first_name)
    )
    conn.commit()
    conn.close()
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
def is_premium(user_id):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT subscription_expiry FROM premium_users WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        expiry = result['subscription_expiry']
        if expiry is None:
            return False
        return datetime.strptime(str(expiry), "%Y-%m-%d %H:%M:%S") > datetime.now()

    return False
card_generator = CardGenerator()

# BOT Configuration
BOT_TOKEN = '7265564885:AAFZrs6Mi3aVf-hGT-b_iKBI3d7JCAYDo-A'   # ENTER UR BOT TOKEN
MAIN_ADMIN_ID = 5103348494  # Your main admin ID

bot = telebot.TeleBot(BOT_TOKEN)

AUTHORIZED_USERS = {}
PREMIUM_USERS = {}
FREE_USER_COOLDOWN = {}  # For anti-spam system

# Replace the entire CardGenerator class with this updated version

class CardGenerator:
    """
    A class to generate valid credit card numbers based on a given BIN pattern
    using the Luhn algorithm. Always generates 16-digit card numbers.
    """
    def __init__(self):
        # Regex pattern to validate the user's input (only digits, 'x', and '|')
        self.bin_pattern = re.compile(r'^[0-9xX|]+$')

    def luhn_checksum(self, card_number):
        """
        Calculates the Luhn checksum for a given string of digits.
        Returns the check digit needed to make the number valid.
        """
        def digits_of(n):
            return [int(d) for d in str(n)]
        
        # Reverse the digits and split into odd & even indices
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]    # digits at odd positions (1-indexed)
        even_digits = digits[-2::-2]   # digits at even positions (1-indexed)
        
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
            
        return (checksum % 10)

    def calculate_check_digit(self, partial_number):
        """
        Given a partial number (without the last check digit),
        calculates the valid Luhn check digit and returns it.
        """
        # Calculate the checksum for partial_number + '0'
        checksum = self.luhn_checksum(partial_number + '0')
        # The check digit is the amount needed to reach a multiple of 10
        return (10 - checksum) % 10

    def generate_valid_card(self, pattern):
        """
        Generates a single valid 16-digit card number from a pattern.
        Pattern example: '439383xxxxxx'
        """
        # Count how many 'x' characters we need to replace
        x_count = pattern.count('x') + pattern.count('X')
        
        # If there are no 'x' characters, we need to generate the check digit
        if x_count == 0:
            # Ensure the card is 16 digits by truncating or padding
            if len(pattern) > 15:
                partial_number = pattern[:15]  # Truncate to 15 digits
            elif len(pattern) < 15:
                # Pad with zeros to make it 15 digits
                partial_number = pattern + '0' * (15 - len(pattern))
            else:
                partial_number = pattern
            
            check_digit = self.calculate_check_digit(partial_number)
            return partial_number + str(check_digit)
        
        # Generate random digits for each 'x'
        random_digits = ''.join(str(random.randint(0, 9)) for _ in range(x_count))
        
        # Build the card number by replacing each 'x' with a random digit
        card_without_check = []
        digit_index = 0
        for char in pattern:
            if char in 'xX':
                card_without_check.append(random_digits[digit_index])
                digit_index += 1
            else:
                card_without_check.append(char)
                
        card_without_check_str = ''.join(card_without_check)
        
        # Ensure the card is exactly 15 digits before adding check digit
        if len(card_without_check_str) > 15:
            card_without_check_str = card_without_check_str[:15]  # Truncate to 15 digits
        elif len(card_without_check_str) < 15:
            # Pad with zeros to make it 15 digits
            card_without_check_str = card_without_check_str + '0' * (15 - len(card_without_check_str))
        
        # Calculate the final check digit using the Luhn algorithm
        check_digit = self.calculate_check_digit(card_without_check_str)
        
        # Return the complete, valid 16-digit card number
        return card_without_check_str + str(check_digit)

    def parse_input_pattern(self, input_pattern):
        """
        Parse different input formats and return a standardized pattern
        that will generate 16-digit card numbers.
        """
        # Remove any spaces
        input_pattern = input_pattern.replace(' ', '')
        
        # Case 1: Just a BIN (6+ digits)
        if re.match(r'^\d{6,}$', input_pattern) and '|' not in input_pattern:
            bin_part = input_pattern[:6]  # Take first 6 digits as BIN
            remaining_length = 15 - len(bin_part)  # 15 digits + 1 check digit = 16
            if remaining_length > 0:
                return bin_part + 'x' * remaining_length
            else:
                return bin_part[:15]  # If longer than 15, truncate
        
        # Case 2: BIN|MM|YY|CVV format
        elif '|' in input_pattern:
            parts = input_pattern.split('|')
            if len(parts) >= 4:
                # This is a full card format, extract just the BIN part
                bin_part = parts[0][:6]  # Take first 6 digits as BIN
                remaining_length = 15 - len(bin_part)
                if remaining_length > 0:
                    return bin_part + 'x' * remaining_length
                else:
                    return bin_part[:15]
            else:
                # Partial format, extract digits and create pattern
                digits_only = re.sub(r'[^\d]', '', input_pattern)
                if len(digits_only) >= 6:
                    bin_part = digits_only[:6]
                    remaining_length = 15 - len(bin_part)
                    if remaining_length > 0:
                        return bin_part + 'x' * remaining_length
                    else:
                        return bin_part[:15]
                else:
                    return '483318xxxxxx'  # Default pattern if not enough digits
        
        # Case 3: Pattern with x's
        else:
            # Extract all digits and x's
            clean_pattern = re.sub(r'[^0-9xX]', '', input_pattern)
            if len(clean_pattern) >= 6:
                # Ensure we have exactly 15 characters (before check digit)
                if len(clean_pattern) > 15:
                    return clean_pattern[:15]
                elif len(clean_pattern) < 15:
                    return clean_pattern + 'x' * (15 - len(clean_pattern))
                else:
                    return clean_pattern
            else:
                return '483318xxxxxx'  # Default pattern if not enough characters

    def validate_pattern(self, pattern):
        """
        Validates the user's input pattern.
        Returns (True, cleaned_pattern) if valid, or (False, error_message) if invalid.
        """
        # Remove any spaces the user might have entered
        pattern = pattern.replace(' ', '')
        
        # Check if the pattern contains only numbers, 'x', and '|'
        if not self.bin_pattern.match(pattern):
            return False, "❌ Invalid pattern. Please use only digits (0-9), 'x', and '|' characters. Example: `/gen 439383xxxxxx` or `/gen 483318|12|25|123`"
        
        # Check if it's a BIN|MM|YY|CVV format
        if '|' in pattern:
            parts = pattern.split('|')
            if len(parts[0]) < 6:
                return False, "❌ BIN must be at least 6 digits. Example: `/gen 483318|12|25|123`"
        else:
            # Check if the pattern has at least 6 digits to work with
            digit_count = len(re.findall(r'\d', pattern))
            if digit_count < 6:
                return False, "❌ Pattern must contain at least 6 digits. Example: `/gen 483318` or `/gen 483318xxxxxx`"
        
        return True, pattern

    def generate_cards(self, input_pattern, amount=10):
        """
        The main function to be called from the bot.
        Generates 'amount' of valid 16-digit card numbers based on the pattern.
        Returns a list of cards and an optional error message.
        """
        # Validate the pattern first
        is_valid, result = self.validate_pattern(input_pattern)
        if not is_valid:
            return [], result  # result contains the error message
        
        # Parse the input pattern to standardized format
        parsed_pattern = self.parse_input_pattern(result)
        
        generated_cards = []
        
        # Generate the requested amount of cards
        for _ in range(amount):
            try:
                # Check if it's a BIN|MM|YY|CVV format
                if '|' in input_pattern and input_pattern.count('|') >= 3:
                    parts = input_pattern.split('|')
                    bin_part = parts[0]
                    mm = parts[1] if len(parts) > 1 else str(random.randint(1, 12)).zfill(2)
                    yy = parts[2] if len(parts) > 2 else str(random.randint(23, 33)).zfill(2)
                    cvv = parts[3] if len(parts) > 3 else str(random.randint(100, 999))
                    
                    # Generate card number from BIN (always 16 digits)
                    card_number = self.generate_valid_card(bin_part)
                    generated_cards.append(f"{card_number}|{mm}|{yy}|{cvv}")
                else:
                    # Regular pattern generation (with x's)
                    card_number = self.generate_valid_card(parsed_pattern)
                    # Add random MM/YY/CVV
                    mm = str(random.randint(1, 12)).zfill(2)
                    yy = str(random.randint(23, 33)).zfill(2)
                    cvv = str(random.randint(100, 999))
                    generated_cards.append(f"{card_number}|{mm}|{yy}|{cvv}")
            except Exception as e:
                # Catch any unexpected errors during generation
                return [], f"❌ An error occurred during generation: {str(e)}"
                
        # Return the list of cards and no error (None)
        return generated_cards, None

# ---------------- Helper Functions ---------------- #

def load_admins():
    """Load admin list from file"""
    try:
        with open("admins.json", "r") as f:
            data = json.load(f)
            # Ensure we return a list of integers
            if isinstance(data, list):
                return [int(admin_id) for admin_id in data]
            else:
                # If it's a dict or something else, return default
                return [MAIN_ADMIN_ID]
    except:
        return [MAIN_ADMIN_ID]

def save_admins(admins):
    """Save admin list to file"""
    with open("admins.json", "w") as f:
        # Ensure we save as list of integers
        json.dump([int(admin_id) for admin_id in admins], f)

def is_admin(chat_id):
    """Check if user is an admin"""
    # Convert to int for comparison
    try:
        chat_id_int = int(chat_id)
    except (ValueError, TypeError):
        return False
        
    admins = load_admins()
    return chat_id_int in admins

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
        # Try to load from authorized.json as fallback
        with open("authorized.json", "r") as f:
            data = json.load(f)
            # Extract premium users from authorized data
            premium_users = {}
            for user_id, expiry in data.items():
                if isinstance(expiry, (int, float)) and expiry > time.time() or expiry == "forever":
                    premium_users[user_id] = expiry
            return premium_users
    except:
        return {}

def save_premium(data):
    # Save premium users to authorized.json
    auth_data = load_auth()
    for user_id, expiry in data.items():
        auth_data[user_id] = expiry
    save_auth(auth_data)

def generate_key(length=16):
    """Generate a random premium key in MHITZXG-XXXXX-XXXXX format"""
    import random
    import string
    chars = string.ascii_uppercase + string.digits
    key = 'MHITZXG-' + ''.join(random.choice(chars) for _ in range(5)) + '-' + ''.join(random.choice(chars) for _ in range(5))
    return key

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
            user_type = "Premium User 💰"
        else:
            user_type = "Free User 🔓"
            
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
            user_type = "Free User 🔓"
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
    
    if is_admin(user_id):
        return "Unlimited ♾️", "Never"
    
    if user_id_str in PREMIUM_USERS:
        expiry = PREMIUM_USERS[user_id_str]
        if expiry == "forever":
            return "Forever ♾️", "Never"
        else:
            expiry_date = datetime.fromtimestamp(expiry)
            remaining_days = (expiry_date - datetime.now()).days
            return f"{remaining_days} days", expiry_date.strftime("%Y-%m-%d %H:%M:%S")
    else:
        return "No subscription ❌", "N/A"

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

def is_premium(user_id):
    """Check if user has premium subscription"""
    user_id_str = str(user_id)  # Convert to string for consistency
    if is_admin(user_id):  # This handles integer input
        return True
    if user_id_str in PREMIUM_USERS:
        expiry = PREMIUM_USERS[user_id_str]
        if expiry == "forever":
            return True
        if time.time() < expiry:
            return True
        else:
            del PREMIUM_USERS[user_id_str]
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
    if msg.from_user.id != MAIN_ADMIN_ID:  # Only main admin can add other admins
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
        expiry = PREMIUM_USERS[str(user_id)]
        if expiry == "forever":
            expiry_text = "Forever ♾️"
        else:
            expiry_date = datetime.fromtimestamp(expiry).strftime("%Y-%m-%d %H:%M:%S")
            expiry_text = f"Until {expiry_date}"
        
        bot.reply_to(msg, f"""
╔═══════════════════════╗
 💎 SUBSCRIPTION INFO 💎
╚═══════════════════════╝

• You have a Premium subscription 💰
• Expiry: {expiry_text}
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

# Simple in-memory key storage
PREMIUM_KEYS = {}

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
        return bot.reply_to(msg, "❌ You are not authorized to use this command.")

    try:
        user_id = int(msg.text.split()[1])
    except:
        return bot.reply_to(msg, "❌ Usage: /auth <user_id>")

    add_free_user(user_id, "FreeUser")
    bot.reply_to(msg, f"✅ User {user_id} is now authorized as a free user (private chat only).")

@bot.message_handler(commands=['rm'])
def remove_auth(msg):
    if not is_admin(msg.from_user.id):
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
            result = check_card(cc)  # This function must be in your p.py
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

 ❌ NO VALID CARDS ❌


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






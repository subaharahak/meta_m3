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
from p import check_card  # Make sure check_card(cc_line) is in p.py

# BOT Configuration
BOT_TOKEN = '7265564885:AAFZrs6Mi3aVf-hGT-b_iKBI3d7JCAYDo-A'   # ENTER UR BOT TOKEN
MAIN_ADMIN_ID = 5103348494  # Your main admin ID
ADMIN_IDS = [5103348494]  # Start with just you

bot = telebot.TeleBot(BOT_TOKEN)

AUTHORIZED_USERS = {}
PREMIUM_USERS = {}
FREE_USER_COOLDOWN = {}  # For anti-spam system

# ---------------- Card Generator Class ---------------- #
class CardGenerator:
    """
    A class to generate valid credit card numbers based on a given BIN pattern
    using the Luhn algorithm.
    """
    def __init__(self):
        # Regex pattern to validate the user's input (only digits and 'x')
        self.bin_pattern = re.compile(r'^[0-9xX]+$')

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
        Generates a single valid card number from a pattern.
        Pattern example: '439383xxxxxx'
        """
        # Count how many 'x' characters we need to replace
        x_count = pattern.count('x') + pattern.count('X')
        
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
        
        # Calculate the final check digit using the Luhn algorithm
        check_digit = self.calculate_check_digit(card_without_check_str)
        
        # Return the complete, valid card number
        return card_without_check_str + str(check_digit)

    def validate_pattern(self, pattern):
        """
        Validates the user's input pattern.
        Returns (True, cleaned_pattern) if valid, or (False, error_message) if invalid.
        """
        # Remove any spaces the user might have entered
        pattern = pattern.replace(' ', '')
        
        # Check if the pattern contains only numbers and 'x'
        if not self.bin_pattern.match(pattern):
            return False, "❌ Invalid pattern. Please use only digits (0-9) and 'x' characters. Example: `/gen 439383xxxxxx`"
        
        # Check if the pattern has at least one 'x' to generate from
        x_count = pattern.lower().count('x')
        if x_count < 1:
            return False, "❌ Pattern must contain at least one 'x' to generate numbers. Example: `/gen 439383xxxxxx`"
        
        # Basic length check for a card number
        if len(pattern) < 12 or len(pattern) > 19:
            return False, "❌ Invalid length. Card numbers are typically between 12-19 digits."
            
        return True, pattern

    def generate_cards(self, pattern, amount=10):
        """
        The main function to be called from the bot.
        Generates 'amount' of valid card numbers based on the pattern.
        Returns a list of cards and an optional error message.
        """
        # Validate the pattern first
        is_valid, result = self.validate_pattern(pattern)
        if not is_valid:
            return [], result  # result contains the error message
        
        cleaned_pattern = result
        generated_cards = []
        
        # Generate the requested amount of cards
        for _ in range(amount):
            try:
                card = self.generate_valid_card(cleaned_pattern)
                generated_cards.append(card)
            except Exception as e:
                # Catch any unexpected errors during generation
                return [], f"❌ An error occurred during generation: {str(e)}"
                
        # Return the list of cards and no error (None)
        return generated_cards, None

# Initialize card generator
card_generator = CardGenerator()

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
    if is_admin(user_id):
        return True
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
    
    # Admins have no cooldown
    if is_admin(user_id):
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
    
    if user_id_str not in FREE_USER_COOLDOWN:
        FREE_USER_COOLDOWN[user_id_str] = {}
    
    FREE_USER_COOLDOWN[user_id_str][command_type] = time.time() + duration

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
╔══════════════════════极
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
╚═══════════════════════�极

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
极═══════════════════════╝
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
def generate_premium_key(msg):
    """Generate premium keys (admin only)"""
    if not is_admin(msg.from_user.id):
        return bot.reply_to(msg, """
   
🔰 ADMIN PERMISSION REQUIRED 🔰
  

• Only admins can generate premium keys""")
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """

  ⚡ INVALID USAGE ⚡


• Usage: `/genkey <duration>`
• Examples:
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
            duration_text = "Forever ♾️"
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
            return bot.reply_to(msg, """

 ❌ INVALID DURATION ❌


• Valid durations:
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
        
        bot.reply_to(msg, f"""
  
🔑 PREMIUM KEY GENERATED 🔑
  

• Key: {key}
• Duration: {duration_text}
• Use: /redeem {key}""")
        
    except Exception as e:
        bot.reply_to(msg, f"""

     ⚠️ ERROR ⚠️

• Error: {str(e)}""")

@bot.message_handler(commands=['redeem'])
def redeem_key(msg):
    """Redeem a premium key"""
    user_id = msg.from_user.id
    
    if is_premium(user_id):
        return bot.reply_to(msg, """

  ✅ ALREADY PREMIUM ✅


• You already have a Premium subscription 💰""")
    
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, """

 ⚡ INVALID USAGE ⚡


• Usage: `/redeem <key>`
• Example: `/redeem MHITZXG-XXXXX-XXXXX`""")
        
        key = parts[1].upper()
        keys = load_keys()
        
        if key not in keys:
            return bot.reply_to(msg, """

  ❌ INVALID KEY ❌


• This key is not valid""")
        
        key_data = keys[key]
        
        if key_data["used"]:
            return bot.reply_to(msg, """

 ❌ KEY ALREADY USED ❌


• This key has already been used""")
        
        # Mark key as used
        keys[key]["used"] = True
        keys[key]["used_by"] = user极
        keys[key]["redeemed_at"] = time.time()
        save_keys(keys)
        
        # Add user to premium
        PREMIUM_USERS[str(user_id)] = key_data["expiry"]
        save_premium(PREMIUM_USERS)
        
        if key_data["expiry"] == "forever":
            expiry_text = "Forever ♾️"
        else:
            expiry_date = datetime.fromtimestamp(key_data["expiry"]).strftime("%Y-%m-%d %H:%M:%S")
            expiry_text = f"Until {expiry_date}"
        
        bot.reply_to(msg, f"""

 ✅ PREMIUM ACTIVATED ✅


• Your account has been upgraded to Premium 💰
• Duration: {key_data['duration']}
• Expiry: {expiry_text}
• Access to All Premium Gateways Unlocked!!.
• You can now enjoy unlimited card checks 🛒""")
        
        # Notify admin
        bot.send_message(MAIN_ADMIN_ID, f"""

 📩 PREMIUM REDEEMED 📩


• User: {user_id}
• Key: {key}
• Duration: {key_data['duration']}""")
        
    except Exception as e:
        bot.reply_to(msg, f"""

     ⚠️ ERROR ⚠️


• Error: {str(e)}""")

# ---------------- Info Command ---------------- #

@bot.message_handler(commands=['info'])
def user_info(msg):
    """Show user information"""
    user_id = msg.from_user.id
    user_data = get_user_info(user_id)
    remaining, expiry_date = get_subscription_info(user_id)
    current_time = datetime.now().strftime("%Y-%m-%极 %H:%M:%S")
    
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

Valid format:
`/gen 439383xxxxxx`
`/gen 516949xxxxxx1234`

• Use 'x' for random digits
• Example: `/gen 516949xxxxxx1234`

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
            
            # Format the cards with copy-on-click functionality
            formatted_cards = []
            for i, card in enumerate(cards, 1):
                formatted_cards.append(f"`{i}. {card}`")  # Using code formatting for copyability
            
            # Get user info
            user_info_data = get_user_info(msg.from_user.id)
            user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
            proxy_status = check_proxy_status()
            
            # Create the final message
            final_message = f"""
╔═══════════════════════╗
      ✅ CARDS GENERATED ✅
╚═══════════════════════╝

🎯 Pattern: `{pattern}`
📊 Generated: {len(cards)} cards

╔═══════════════════════╗
      🔢 GENERATED CARDS 🔢
╚═══════════════════════╝

""" + "\n".join(formatted_cards) + f"""

👤 Generated by: {user_info}
🔌 Proxy: {proxy_status}

⚡ Powered by @mhitzxg & @pr0xy_xd"""
            
            # Send the generated cards
            bot.edit_message_text(final_message, msg.chat.id, processing.message_id, parse_mode='Markdown')
            
        except Exception as e:
            bot.edit_message_text(f"""
❌ GENERATION ERROR ❌

Error: {str(e)}

✗ Contact admin if you need help: @mhitzxg""", msg.chat.id, processing.message_id)

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
│ • /start       - Start the Bot
│ • /b3          - Check single card
│ • /mb3         - Mass check (reply to file)
│ • /gen         - Generate cards (Luhn algo)
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
def authorize_user(msg):
    if not is_admin(msg.from_user.id):
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

        msg_text = f"✅ Authorized {uid极 for {days} days." if days else f"✅ Authorized {uid} forever."
        bot.reply_to(msg, msg_text)
    except Exception as e:
        bot.reply_to(msg, f"❌ Error: {e}")

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
        if re.match(r'^\d{16}\|\d{2}\|\极{2,4}\|\d{3,4}$', raw_input):
            cc = raw_input
        else:
            # Try to normalize the card
            cc = normalize_card(raw_input)

            # If normalization failed, use the original input
            if not cc:
                cc = raw_input

    # Set cooldown for free users (30 seconds)
    if not is_admin(msg.from_user.id) and not is_premium(msg.from_user.id):
        set_cooldown(msg.from_user.id, "b3", 30)

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
    if not is_author极(msg):
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


• No valid card formats found极 the file
• Please check the file format

Valid format:
`4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""")

    # Check card limit for free users (15 cards)
    user_id = msg.from_user.id
    if not is_admin(user_id) and not is_premium(user_id) and len(cc_lines) > 15:
        return bot.reply_to(msg, f"""

 ❌ LIMIT EXCEEDED ❌


• Free users can only check 15 cards at once
• You tried to check {len(cc_lines)} cards


💰 UPGRADE TO PREMIUM 💰


• Upgrade to premium for unlimited checks
• Use /subscription to view plans
• Contact @mhitzxg to purchase""")

    if not reply.document and len(cc_lines) > 15:
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
        InlineKeyboardButton(f"Checked 0 📊", callback_data="极one"),
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
                        f"⚡ Powered by: @mkhitzxg & @pr0xy_xd"
                    )
                    
                    approved_cards.append(formatted_result)  # Store approved card
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

        # After processing all cards, send the approved cards in one message
        if approved_cards:
            approved_message = """
╔═══════════════════════╗
       ✅ APPROVED CARDS ✅
╚═══════════════════════╝

"""
            approved_message += "\n".join(approved_cards)
            
            # Add user info and proxy status to the final message
            user_info_data = get_user_info(msg.from_user.id)
            user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
            proxy_status = check_proxy_status()
            
            approved_message += f"\n\n👤 Checked by: {user_info}"
            approved_message += f"\n🔌 Proxy: {proxy_status}"
            
            # Split the message if it's too long (Telegram has a 4096 character limit)
            if len(approved_message) > 4000:
                parts = [approved_message[i:i+4000] for i in range(0, len(approved_message), 4000)]
                for part in parts:
                    bot.send_message(chat_id, part, parse_mode='HTML')
                    time.sleep(1)
            else:
                bot.send_message(chat_id, approved_message, parse_mode='HTML')

        # Final status message
        user_info_data = get_user_info(msg.from_user.id)
        user_info = f"{user_info_data['username']} ({user_info_data['user_type']})"
        proxy_status = check_proxy_status()
        
        final_message = f"""
╔═══════════════════════╗
      📊 CHECK COMPLETED 📊
╚═══════════════════════╝

• All cards have been processed
• Approved: {approved} | Declined: {declined}

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



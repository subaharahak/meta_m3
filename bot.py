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

        msg_text = f"✅ Authorized {uid} for {days} days." if days else f"✅ Authorized {uid} forever."
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
╔═══════════════════════╗
🔰 AUTHORIZATION REQUIRED 🔰         
╚═══════════════════════╝

• You are not authorized to use this command
• Only authorized users can check cards

✗ Contact an admin for authorization
• Admin: @mhitzxg""")

    # Check for spam (30 second cooldown for free users)
    if check_cooldown(msg.from_user.id, "b3"):
        return bot.reply_to(msg, """
╔═══════════════════════╗
⏰ COOLDOWN ACTIVE ⏰
╚═══════════════════════╝

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
╔═══════════════════════╗
❌ INVALID CARD FORMAT ❌
╚═══════════════════════╝

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
╔═══════════════════════╗
⚡ INVALID USAGE ⚡
╚═══════════════════════╝

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
        set_cooldown(msg.from_user.id, "b3", 30)

    processing = bot.reply_to(msg, """
╔═══════════════════════╗
⏳ PROCESSING ⏳
╚═══════════════════════╝

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
╔═══════════════════════╗
🔰 AUTHORIZATION REQUIRED 🔰
╚═══════════════════════╝

• You are not authorized to use this command
• Only authorized users can check cards

✗ Contact an admin for authorization
• Admin: @mhitzxg""")

    # Check for cooldown (30 minutes for free users)
    if check_cooldown(msg.from_user.id, "mb3"):
        return bot.reply_to(msg, """
╔═══════════════════════╗
⏰ COOLDOWN ACTIVE ⏰
╚═══════════════════════╝

• You are in cooldown period
• Please wait 30 minutes before mass checking again

✗ Upgrade to premium to remove cooldowns""")

    if not msg.reply_to_message:
        return bot.reply_to(msg, """
╔═══════════════════════╗
⚡ INVALID USAGE ⚡
╚═══════════════════════╝

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
╔═══════════════════════╗
❌ NO VALID CARDS ❌
╚═══════════════════════╝

• No valid card formats found in the file
• Please check the file format

Valid format:
`4556737586899855|12|2026|123`

✗ Contact admin if you need help: @mhitzxg""")

    # Check card limit for free users (15 cards)
    user_id = msg.from_user.id
    if not is_admin(user_id) and not is_premium(user_id) and len(cc_lines) > 15:
        return bot.reply_to(msg, f"""
╔═══════════════════════╗
❌ LIMIT EXCEEDED ❌
╚═══════════════════════╝

• Free users can only check 15 cards at once
• You tried to check {len(cc_lines)} cards

╔═══════════════════════╗
💰 UPGRADE TO PREMIUM 💰
╚═══════════════════════╝

• Upgrade to premium for unlimited checks
• Use /subscription to view plans
• Contact @mhitzxg to purchase""")

    if not reply.document and len(cc_lines) > 15:
        return bot.reply_to(msg, """
╔═══════════════════════╗
❌ TOO MANY CARDS ❌
╚═══════════════════════╝

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
╔═══════════════════════╗
⏳ PROCESSING CARDS ⏳
╚═══════════════════════╝

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

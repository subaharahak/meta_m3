"""
Helper module for channel scraping - ALTERNATIVE APPROACH using scr.py functions
"""
import asyncio
import threading
import time
from pyrogram import Client
from pyrogram.errors import UsernameNotOccupied, UsernameInvalid, InviteHashExpired, InviteHashInvalid, FloodWait

# Import functions from scr.py
try:
    import scr
    is_approved_message = scr.is_approved_message
    extract_credit_cards = scr.extract_credit_cards
    get_bin_info = scr.get_bin_info
except:
    # Fallback if scr.py not available
    def is_approved_message(text):
        return False
    def extract_credit_cards(text):
        return []
    async def get_bin_info(bin_num):
        return None

def parse_channel_username(channel_input):
    """Parse channel username from various formats"""
    channel_input = channel_input.strip()
    if channel_input.startswith('@'):
        channel_input = channel_input[1:]
    if 't.me/' in channel_input:
        parts = channel_input.split('t.me/')
        if len(parts) > 1:
            channel_input = parts[-1].split('/')[0].split('?')[0]
    if channel_input.startswith('+'):
        return channel_input
    channel_input = channel_input.split('/')[0].split('?')[0]
    return channel_input

async def scrape_channel_async(channel_input, limit, filter_bin=None, filter_bank=None):
    """
    Scrape channel using proper async handling
    """
    API_ID = "29021447"
    API_HASH = "303c8886fed6409c9d0cda4cf5a41905"
    PHONE_NUMBER = "+84349253553"
    
    client = None
    try:
        # Use unique session name with timestamp
        session_name = f"cc_scraper_{int(time.time() * 1000)}"
        client = Client(session_name, api_id=API_ID, api_hash=API_HASH, phone_number=PHONE_NUMBER)
        await client.start()
        
        channel_username = parse_channel_username(channel_input)
        
        try:
            chat = await client.get_chat(channel_username)
        except (UsernameNotOccupied, UsernameInvalid, InviteHashExpired, InviteHashInvalid) as e:
            return None, f"❌ Channel not found or invalid: {channel_input}"
        except Exception as e:
            return None, f"❌ Error accessing channel: {str(e)}"
        
        all_cards = []
        approved_count = 0
        total_messages = 0
        
        try:
            async for message in client.get_chat_history(chat.id, limit=limit):
                total_messages += 1
                text = message.text or message.caption or ""
                if not text:
                    continue
                
                if is_approved_message(text):
                    approved_count += 1
                    cards = extract_credit_cards(text)
                    
                    if filter_bin:
                        cards = [c for c in cards if c.split('|')[0].startswith(filter_bin)]
                    
                    if filter_bank and cards:
                        filtered_cards = []
                        for card in cards:
                            bin_num = card.split('|')[0][:6]
                            bin_info = await get_bin_info(bin_num)
                            if bin_info:
                                bank_name = bin_info.get('bank', '').lower()
                                if filter_bank.lower() in bank_name:
                                    filtered_cards.append(card)
                        cards = filtered_cards
                    
                    all_cards.extend(cards)
                    
                    # Small delay to prevent rate limiting
                    if total_messages % 20 == 0:
                        await asyncio.sleep(0.05)
        
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            return None, f"❌ Error scraping messages: {str(e)}"
        
        all_cards = list(dict.fromkeys(all_cards))
        
        return {
            'channel': chat.title or channel_input,
            'cards': all_cards,
            'approved_messages': approved_count,
            'total_messages': total_messages
        }, None
        
    except Exception as e:
        return None, f"❌ Error: {str(e)}"
    finally:
        if client:
            try:
                await client.stop()
                await client.disconnect()
            except:
                pass

def run_scraper_in_thread(channel_input, limit, filter_bin, filter_bank, callback_func):
    """
    Run scraper in a thread with its own event loop - FIXED VERSION
    """
    def run():
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result, error = loop.run_until_complete(
                scrape_channel_async(channel_input, limit, filter_bin, filter_bank)
            )
            callback_func(result, error)
        except Exception as e:
            callback_func(None, f"❌ Error: {str(e)}")
        finally:
            try:
                # Clean up properly
                pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
                if pending:
                    for task in pending:
                        task.cancel()
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()
            except:
                pass
    
    return run

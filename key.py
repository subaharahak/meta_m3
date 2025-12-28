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
    Check Stripe Secret Key validity - simplified version
    Just checks if the API key is valid or not
    Returns: (status, message, currency, available_balance, pending_balance, time_taken)
    """
    start_time = time.time()
    
    try:
        # Simple check: Try to get account information
        account_url = 'https://api.stripe.com/v1/account'
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        account_response = requests.get(
            account_url,
            auth=(sk_key, ''),
            headers=headers,
            timeout=10
        )
        
        elapsed = time.time() - start_time
        account_result = account_response.text
        
        # Check for invalid/expired key
        if 'api_key_expired' in account_result:
            return ('DEAD', 'API Key Expired', 'USD', 0, 0, elapsed)
        
        if 'Invalid API Key provided' in account_result:
            return ('DEAD', 'Invalid API Key', 'USD', 0, 0, elapsed)
        
        if account_response.status_code == 200:
            # Key is valid, try to get balance for additional info
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
        else:
            return ('DEAD', 'Invalid API Key', 'USD', 0, 0, elapsed)
            
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        return ('ERROR', 'Request Timeout', 'USD', 0, 0, elapsed)
    except requests.exceptions.RequestException as e:
        elapsed = time.time() - start_time
        return ('ERROR', f'Connection Error: {str(e)}', 'USD', 0, 0, elapsed)
    except Exception as e:
        elapsed = time.time() - start_time
        return ('ERROR', f'Error: {str(e)}', 'USD', 0, 0, elapsed)


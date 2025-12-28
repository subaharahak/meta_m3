# gen.py
import random
import re
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class CardGenerator:
    """
    A class to generate valid credit card numbers based on a given BIN pattern
    using the Luhn algorithm.
    """
    def __init__(self):
        # Regex pattern to validate the user's input (only digits, 'x', and '|')
        self.bin_pattern = re.compile(r'^[0-9xX|]+$')

    def luhn_checksum(self, card_number):
        """
        Calculates the Luhn checksum for a given string of digits.
        Returns True if the number is valid, False otherwise.
        """
        def digits_of(n):
            return [int(d) for d in str(n)]
        
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
            
        return checksum % 10 == 0

    def calculate_check_digit(self, partial_number):
        """
        Given a partial number (without the last check digit),
        calculates the valid Luhn check digit and returns it.
        """
        # Calculate the checksum for partial_number + '0'
        checksum = 0
        digits = [int(d) for d in partial_number + '0']
        digits.reverse()
        
        for i, digit in enumerate(digits):
            if i % 2 == 0:
                digit *= 2
                if digit > 9:
                    digit -= 9
            checksum += digit
        
        check_digit = (10 - (checksum % 10)) % 10
        return check_digit

    def generate_valid_card_number(self, bin_pattern):
        """
        Generates a single valid 16-digit card number from a BIN pattern.
        """
        # Remove any non-digit characters except x
        clean_pattern = re.sub(r'[^0-9xX]', '', bin_pattern)
        
        # If pattern is empty or has no digits, return error
        if not clean_pattern or len(re.findall(r'\d', clean_pattern)) == 0:
            raise ValueError("Invalid BIN pattern: no digits found")
        
        # Count how many 'x' characters we need to replace
        x_count = clean_pattern.count('x') + clean_pattern.count('X')
        digit_count = len(re.findall(r'\d', clean_pattern))
        
        # If pattern has more than 15 digits, truncate to 15 (before check digit)
        if digit_count + x_count > 15:
            # Keep first 15 characters (digits and x's)
            clean_pattern = clean_pattern[:15]
            # Recalculate counts after truncation
            x_count = clean_pattern.count('x') + clean_pattern.count('X')
            digit_count = len(re.findall(r'\d', clean_pattern))
        
        # If pattern is less than 15 digits, add x's to make it 15 digits (before check digit)
        if digit_count + x_count < 15:
            needed_x = 15 - (digit_count + x_count)
            clean_pattern += 'x' * needed_x
            x_count += needed_x
        
        # Generate random digits for each 'x' (only if x_count > 0)
        if x_count > 0:
            random_digits = ''.join(str(random.randint(0, 9)) for _ in range(x_count))
        else:
            random_digits = ''
        
        # Build the card number by replacing each 'x' with a random digit
        card_without_check = []
        digit_index = 0
        for char in clean_pattern:
            if char in 'xX':
                if digit_index < len(random_digits):
                    card_without_check.append(random_digits[digit_index])
                    digit_index += 1
                else:
                    card_without_check.append(str(random.randint(0, 9)))
            else:
                card_without_check.append(char)
                
        card_without_check_str = ''.join(card_without_check)
        
        # Ensure we have exactly 15 digits before check digit
        if len(card_without_check_str) > 15:
            card_without_check_str = card_without_check_str[:15]
        elif len(card_without_check_str) < 15:
            # Pad with random digits if needed
            while len(card_without_check_str) < 15:
                card_without_check_str += str(random.randint(0, 9))
        
        # Calculate the final check digit using the Luhn algorithm
        check_digit = self.calculate_check_digit(card_without_check_str)
        
        # Return the complete, valid 16-digit card number
        full_card = card_without_check_str + str(check_digit)
        
        # Verify the card passes Luhn check
        if not self.luhn_checksum(full_card):
            # If not, recursively generate until we get a valid one
            return self.generate_valid_card_number(bin_pattern)
            
        return full_card

    def parse_input_pattern(self, input_pattern):
        """
        Parse different input formats and return standardized components
        """
        # Remove any spaces
        input_pattern = input_pattern.replace(' ', '')
        
        # Case 1: BIN|MM|YY|CVV format (or partial formats)
        if '|' in input_pattern:
            from datetime import datetime
            current_year = datetime.now().year
            current_month = datetime.now().month
            
            parts = input_pattern.split('|')
            bin_part = parts[0]
            
            # Validate and parse MM
            if len(parts) > 1 and parts[1] and parts[1].strip():
                try:
                    mm_int = int(parts[1].strip())
                    if 1 <= mm_int <= 12:
                        mm = str(mm_int).zfill(2)
                    else:
                        # Invalid month, generate random
                        mm = str(random.randint(1, 12)).zfill(2)
                except (ValueError, TypeError):
                    # Invalid month format, generate random
                    mm = str(random.randint(1, 12)).zfill(2)
            else:
                mm = str(random.randint(1, 12)).zfill(2)
            
            # Validate and parse YY
            if len(parts) > 2 and parts[2] and parts[2].strip():
                try:
                    yy_provided = parts[2].strip()
                    # Convert to full year if 2 digits
                    if len(yy_provided) == 2:
                        yy_int = int(yy_provided)
                        # Convert 00-99 to 2000-2099, but check if it's in the past
                        if yy_int < 100:
                            full_year = 2000 + yy_int
                            # If year is in the past or current year with past month, generate future
                            if full_year < current_year or (full_year == current_year and int(mm) < current_month):
                                # Generate future expiry instead
                                future_years = random.randint(1, 10)
                                expiry_year = current_year + future_years
                                yy = str(expiry_year)[-2:]
                                # Regenerate MM if needed for future expiry
                                if future_years == 1:
                                    if current_month >= 12:
                                        mm = str(random.randint(1, 12)).zfill(2)
                                    else:
                                        start_month = current_month + 1
                                        mm = str(random.randint(start_month, 12)).zfill(2)
                            else:
                                yy = yy_provided
                        else:
                            # Already 4 digits, use as is but validate
                            if yy_int < current_year or (yy_int == current_year and int(mm) < current_month):
                                # Generate future expiry instead
                                future_years = random.randint(1, 10)
                                expiry_year = current_year + future_years
                                yy = str(expiry_year)[-2:]
                                if future_years == 1:
                                    if current_month >= 12:
                                        mm = str(random.randint(1, 12)).zfill(2)
                                    else:
                                        start_month = current_month + 1
                                        mm = str(random.randint(start_month, 12)).zfill(2)
                            else:
                                yy = str(yy_int)[-2:]
                    else:
                        # Invalid format, generate future expiry
                        future_years = random.randint(1, 10)
                        expiry_year = current_year + future_years
                        yy = str(expiry_year)[-2:]
                        if future_years == 1:
                            if current_month >= 12:
                                mm = str(random.randint(1, 12)).zfill(2)
                            else:
                                start_month = current_month + 1
                                mm = str(random.randint(start_month, 12)).zfill(2)
                except (ValueError, TypeError):
                    # Invalid year format, generate future expiry
                    future_years = random.randint(1, 10)
                    expiry_year = current_year + future_years
                    yy = str(expiry_year)[-2:]
                    if future_years == 1:
                        if current_month >= 12:
                            mm = str(random.randint(1, 12)).zfill(2)
                        else:
                            start_month = current_month + 1
                            mm = str(random.randint(start_month, 12)).zfill(2)
            else:
                # No YY provided, generate future expiry
                future_years = random.randint(1, 10)
                expiry_year = current_year + future_years
                yy = str(expiry_year)[-2:]
                if future_years == 1:
                    if current_month >= 12:
                        mm = str(random.randint(1, 12)).zfill(2)
                    else:
                        start_month = current_month + 1
                        mm = str(random.randint(start_month, 12)).zfill(2)
            
            # Validate and parse CVV
            if len(parts) > 3 and parts[3] and parts[3].strip():
                try:
                    cvv_provided = parts[3].strip()
                    cvv_int = int(cvv_provided)
                    if 100 <= cvv_int <= 9999:  # CVV can be 3 or 4 digits
                        cvv = str(cvv_int)
                    else:
                        # Invalid CVV, generate random
                        cvv = str(random.randint(100, 999))
                except (ValueError, TypeError):
                    # Invalid CVV format, generate random
                    cvv = str(random.randint(100, 999))
            else:
                cvv = str(random.randint(100, 999))
            
            return {
                'type': 'full_format',
                'bin': bin_part,
                'mm': mm,
                'yy': yy,
                'cvv': cvv
            }
        
        # Case 2: Just a BIN or pattern
        else:
            # Extract just the digits and x's for the BIN/pattern
            clean_pattern = re.sub(r'[^0-9xX]', '', input_pattern)
            # If pattern is less than 6 digits, it's invalid
            # If pattern is 6-15 digits without x's, auto-add x's to make it 15 digits
            digit_count = len(re.findall(r'\d', clean_pattern))
            if digit_count >= 6 and 'x' not in clean_pattern.lower() and len(clean_pattern) < 15:
                # Auto-add x's to complete to 15 digits (before check digit)
                needed_x = 15 - len(clean_pattern)
                clean_pattern += 'x' * needed_x
            return {
                'type': 'bin_only',
                'bin': clean_pattern
            }

    def validate_pattern(self, pattern):
        """
        Validates the user's input pattern.
        Returns (True, cleaned_pattern) if valid, or (False, error_message) if invalid.
        """
        # Remove any spaces the user might have entered
        pattern = pattern.replace(' ', '')
        
        # Check if the pattern contains only numbers, 'x', and '|'
        if not self.bin_pattern.match(pattern):
            return False, "❌ Invalid pattern. Please use only digits (0-9), 'x', and '|' characters. Example: `/gen 439383xxxxxx` or `/gen 483318|12|25|123`"
        
        # Check if it's a BIN|MM|YY|CVV format (or partial)
        if '|' in pattern:
            parts = pattern.split('|')
            if len(parts[0]) < 6:
                return False, "❌ BIN must be at least 6 digits. Example: `/gen 483318|12|25|123` or `/gen 483318|12|25`"
        else:
            # Check if the pattern has at least 6 digits to work with
            digit_count = len(re.findall(r'\d', pattern))
            if digit_count < 6:
                return False, "❌ BIN must contain at least 6 digits. Example: `/gen 483318` or `/gen 483318xxxxxx`"
        
        return True, pattern

    def get_bin_info(self, bin_number):
        """Get BIN information using multiple APIs"""
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
                response = requests.get(api_url, headers=headers, timeout=5, verify=False)
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
                            'emoji': self.get_country_emoji(data.get('country', {}).get('alpha2', ''))
                        }
                    elif 'antipublic.cc' in api_url:
                        bin_info = {
                            'bank': data.get('bank', 'Unavailable'),
                            'country': data.get('country', 'Unknown'),
                            'brand': data.get('vendor', 'Unknown'),
                            'type': data.get('type', 'Unknown'),
                            'level': data.get('level', 'Unknown'),
                            'emoji': self.get_country_emoji(data.get('country_code', ''))
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
    
    def get_country_emoji(self, country_code):
        """Convert country code to emoji"""
        if not country_code or len(country_code) != 2:
            return ''
        try:
            country_code = country_code.upper()
            return ''.join(chr(127397 + ord(char)) for char in country_code)
        except:
            return ''

    def generate_cards(self, input_pattern, amount=10):
        """
        The main function to be called from the bot.
        Generates 'amount' of valid card numbers based on the pattern.
        Returns a list of cards in format "cc|mm|yy|cvv" and an optional error message.
        """
        # Validate the pattern first
        is_valid, result = self.validate_pattern(input_pattern)
        if not is_valid:
            return [], result  # result contains the error message
        
        # Parse the input pattern
        parsed = self.parse_input_pattern(result)
        
        generated_cards = []
        
        try:
            for _ in range(amount):
                if parsed['type'] == 'full_format':
                    # Generate card number from BIN
                    card_number = self.generate_valid_card_number(parsed['bin'])
                    generated_cards.append(f"{card_number}|{parsed['mm']}|{parsed['yy']}|{parsed['cvv']}")
                else:
                    # Generate card number from BIN with random MM/YY/CVV
                    # Make sure expiry is not expired (current year + future years)
                    from datetime import datetime
                    current_year = datetime.now().year
                    current_month = datetime.now().month
                    
                    # Generate future expiry (at least 1 year from now, up to 10 years)
                    future_years = random.randint(1, 10)
                    expiry_year = current_year + future_years
                    yy = str(expiry_year)[-2:]  # Last 2 digits
                    
                    # If it's the same year, make sure month is in the future
                    if future_years == 1:
                        # If current month is December (12), we need next year, so use any month 1-12
                        if current_month >= 12:
                            mm = str(random.randint(1, 12)).zfill(2)
                        else:
                            # Otherwise, use months from (current_month + 1) to 12
                            start_month = current_month + 1
                            mm = str(random.randint(start_month, 12)).zfill(2)
                    else:
                        mm = str(random.randint(1, 12)).zfill(2)
                    
                    card_number = self.generate_valid_card_number(parsed['bin'])
                    cvv = str(random.randint(100, 999))
                    generated_cards.append(f"{card_number}|{mm}|{yy}|{cvv}")
                    
        except Exception as e:
            return [], None, f"❌ An error occurred during generation: {str(e)}"
        
        # Get BIN info from first generated card
        bin_info = None
        if generated_cards:
            first_card_bin = generated_cards[0].split('|')[0][:6]
            bin_info = self.get_bin_info(first_card_bin)
                
        return generated_cards, bin_info, None


# Example usage and testing if this file is run directly
if __name__ == "__main__":
    print("Testing the CardGenerator module...\n")
    
    generator = CardGenerator()
    
    # Test different patterns
    test_patterns = [
        "483318",  # Just BIN
        "483318|12|25|123",  # BIN with MM/YY/CVV
        "472927xx",  # Short pattern with x's
        "4393830123456789",  # Complete card number (will be truncated to 16 digits)
    ]
    
    for pattern in test_patterns:
        print(f"Testing pattern: {pattern}")
        cards, error = generator.generate_cards(pattern, 2)
        
        if error:
            print(f"Error: {error}")
        else:
            print("✅ Generated cards:")
            for i, card in enumerate(cards, 1):
                print(f"{i}. {card}")
                # Verify Luhn algorithm
                card_number = card.split('|')[0]
                if generator.luhn_checksum(card_number):
                    print(f"   ✓ Luhn valid: {card_number}")
                else:
                    print(f"   ✗ Luhn invalid: {card_number}")
        print()

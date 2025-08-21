# gen.py
import random
import re

class CardGenerator:
    """
    A class to generate valid credit card numbers based on a given BIN pattern
    using the Luhn algorithm.
    """
    def __init__(self):
        # Regex pattern to validate the user's input (only digits and 'x')
        self.bin_pattern = re.compile(r'^[0-9xX]+$')

    def luhn_checksum(self, card_number):
        """
        Calculates the Luhn checksum for a given string of digits.
        Returns the check digit needed to make the number valid.
        """
        def digits_of(n):
            return [int(d) for d in str(n)]
        
        # Reverse the digits and split into odd & even indices
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]    # digits at odd positions (1-indexed)
        even_digits = digits[-2::-2]   # digits at even positions (1-indexed)
        
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
            
        return (checksum % 10)

    def calculate_check_digit(self, partial_number):
        """
        Given a partial number (without the last check digit),
        calculates the valid Luhn check digit and returns it.
        """
        # Calculate the checksum for partial_number + '0'
        checksum = self.luhn_checksum(partial_number + '0')
        # The check digit is the amount needed to reach a multiple of 10
        return (10 - checksum) % 10

    def generate_valid_card(self, pattern):
        """
        Generates a single valid card number from a pattern.
        Pattern example: '439383xxxxxx'
        """
        # Count how many 'x' characters we need to replace
        x_count = pattern.count('x') + pattern.count('X')
        
        # If there are no 'x' characters, we need to generate the check digit
        if x_count == 0:
            # Remove the last digit (current check digit) and calculate a new one
            partial_number = pattern[:-1]
            check_digit = self.calculate_check_digit(partial_number)
            return partial_number + str(check_digit)
        
        # Generate random digits for each 'x'
        random_digits = ''.join(str(random.randint(0, 9)) for _ in range(x_count))
        
        # Build the card number by replacing each 'x' with a random digit
        card_without_check = []
        digit_index = 0
        for char in pattern:
            if char in 'xX':
                card_without_check.append(random_digits[digit_index])
                digit_index += 1
            else:
                card_without_check.append(char)
                
        card_without_check_str = ''.join(card_without_check)
        
        # Calculate the final check digit using the Luhn algorithm
        check_digit = self.calculate_check_digit(card_without_check_str)
        
        # Return the complete, valid card number
        return card_without_check_str + str(check_digit)

    def validate_pattern(self, pattern):
        """
        Validates the user's input pattern.
        Returns (True, cleaned_pattern) if valid, or (False, error_message) if invalid.
        """
        # Remove any spaces the user might have entered
        pattern = pattern.replace(' ', '')
        
        # Check if the pattern contains only numbers and 'x'
        if not self.bin_pattern.match(pattern):
            return False, "❌ Invalid pattern. Please use only digits (0-9) and 'x' characters. Example: `/gen 439383xxxxxx`"
        
        # Check if the pattern has at least one 'x' to generate from OR is a complete card number
        x_count = pattern.lower().count('x')
        if x_count < 1 and len(pattern) not in [15, 16]:
            return False, "❌ Pattern must contain at least one 'x' to generate numbers or be a complete card number. Example: `/gen 439383xxxxxx` or `/gen 4939290123456789`"
        
        # Basic length check for a card number
        if len(pattern) < 12 or len(pattern) > 19:
            return False, "❌ Invalid length. Card numbers are typically between 12-19 digits."
            
        return True, pattern

    def generate_cards(self, pattern, amount=10):
        """
        The main function to be called from the bot.
        Generates 'amount' of valid card numbers based on the pattern.
        Returns a list of cards and an optional error message.
        """
        # Validate the pattern first
        is_valid, result = self.validate_pattern(pattern)
        if not is_valid:
            return [], result  # result contains the error message
        
        cleaned_pattern = result
        generated_cards = []
        
        # Generate the requested amount of cards
        for _ in range(amount):
            try:
                card = self.generate_valid_card(cleaned_pattern)
                generated_cards.append(card)
            except Exception as e:
                # Catch any unexpected errors during generation
                return [], f"❌ An error occurred during generation: {str(e)}"
                
        # Return the list of cards and no error (None)
        return generated_cards, None


# Example usage and testing if this file is run directly
if __name__ == "__main__":
    print("Testing the CardGenerator module...\n")
    
    generator = CardGenerator()
    
    # Test a valid pattern with x's
    test_pattern = "439383xxxxxx"
    cards, error = generator.generate_cards(test_pattern, 5)
    
    if error:
        print(f"Error: {error}")
    else:
        print("✅ Generated cards (test with x's):")
        for i, card in enumerate(cards, 1):
            print(f"{i}. {card}")
    
    # Test a complete card number (without x's)
    test_pattern2 = "4939290123456789"
    cards2, error2 = generator.generate_cards(test_pattern2, 3)
    
    if error2:
        print(f"Error: {error2}")
    else:
        print("\n✅ Generated cards (test with complete number):")
        for i, card in enumerate(cards2, 1):
            print(f"{i}. {card}")

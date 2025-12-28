import random
import faker
from faker import Faker

# Initialize Faker instances for different countries
_fakers = {}

def get_faker_for_country(country_code):
    """Get or create a Faker instance for a specific country"""
    country_code = country_code.upper()
    if country_code not in _fakers:
        try:
            _fakers[country_code] = Faker(country_code.lower())
        except:
            # Fallback to US if country not supported
            _fakers[country_code] = Faker('en_US')
    return _fakers[country_code]

def generate_identity(country_code='US'):
    """
    Generate a fake identity for a given country code
    Returns formatted identity information
    """
    try:
        fake = get_faker_for_country(country_code)
        
        # Generate identity components
        first_name = fake.first_name()
        last_name = fake.last_name()
        full_name = f"{first_name} {last_name}"
        
        # Generate address
        street_address = fake.street_address()
        city = fake.city()
        state = fake.state() if hasattr(fake, 'state') else fake.state_abbr()
        zip_code = fake.zipcode()
        country = fake.country()
        
        # Generate contact info
        email = fake.email()
        phone = fake.phone_number()
        
        # Format the output
        identity = f"""👤 Name: {full_name}
🏠 Street : {street_address}
🌆 City : {city}
🏢 State : {state}
🌍 Country : {country}
📮 Zip : {zip_code}
✉️ Email : {email}
📱 Mobile : {phone}"""
        
        return identity
        
    except Exception as e:
        # Fallback to US if country code fails
        if country_code.upper() != 'US':
            return generate_identity('US')
        else:
            fake = Faker('en_US')
            first_name = fake.first_name()
            last_name = fake.last_name()
            full_name = f"{first_name} {last_name}"
            street_address = fake.street_address()
            city = fake.city()
            state = fake.state_abbr()
            zip_code = fake.zipcode()
            country = "United States"
            email = fake.email()
            phone = fake.phone_number()
            
            return f"""👤 Name: {full_name}
🏠 Street : {street_address}
🌆 City : {city}
🏢 State : {state}
🌍 Country : {country}
📮 Zip : {zip_code}
✉️ Email : {email}
📱 Mobile : {phone}"""


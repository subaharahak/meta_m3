import random
import faker
from faker import Faker

# Country code to locale mapping
COUNTRY_LOCALE_MAP = {
    'US': 'en_US', 'GB': 'en_GB', 'CA': 'en_CA', 'AU': 'en_AU',
    'BR': 'pt_BR', 'PT': 'pt_PT',
    'MX': 'es_MX', 'ES': 'es_ES', 'AR': 'es_AR', 'CO': 'es_CO',
    'FR': 'fr_FR', 'DE': 'de_DE', 'IT': 'it_IT', 'NL': 'nl_NL',
    'PL': 'pl_PL', 'RU': 'ru_RU', 'JP': 'ja_JP', 'CN': 'zh_CN',
    'IN': 'en_IN', 'KR': 'ko_KR', 'TR': 'tr_TR', 'ID': 'id_ID',
    'PH': 'en_PH', 'TH': 'th_TH', 'VN': 'vi_VN', 'MY': 'en_MY',
    'SG': 'en_SG', 'NZ': 'en_NZ', 'IE': 'en_IE', 'ZA': 'en_ZA',
    'AE': 'ar_AE', 'SA': 'ar_SA', 'EG': 'ar_EG',
    'CH': 'de_CH', 'AT': 'de_AT', 'BE': 'nl_BE',
    'SE': 'sv_SE', 'NO': 'nb_NO', 'DK': 'da_DK', 'FI': 'fi_FI',
    'GR': 'el_GR', 'CZ': 'cs_CZ', 'HU': 'hu_HU', 'RO': 'ro_RO',
    'CL': 'es_CL', 'PE': 'es_PE', 'VE': 'es_VE', 'EC': 'es_EC',
}

# Initialize Faker instances for different countries
_fakers = {}

def get_faker_for_country(country_code):
    """Get or create a Faker instance for a specific country"""
    country_code = country_code.upper()
    locale = COUNTRY_LOCALE_MAP.get(country_code, 'en_US')
    
    if locale not in _fakers:
        try:
            _fakers[locale] = Faker(locale)
        except:
            # Fallback to US if locale not supported
            _fakers[locale] = Faker('en_US')
    return _fakers[locale]

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
        # Try to get state, fallback to state_abbr if not available
        try:
            state = fake.state()
        except:
            try:
                state = fake.state_abbr()
            except:
                state = fake.city()  # Fallback to city if state not available
        zip_code = fake.zipcode()
        # Get country name from locale
        country = fake.country()
        
        # Generate contact info
        email = fake.email()
        phone = fake.phone_number()
        
        # Format the output with code blocks for easy copying
        identity = f"""👤 *Name*: `{full_name}`
🏠 *Street*: `{street_address}`
🌆 *City*: `{city}`
🏢 *State*: `{state}`
🌍 *Country*: `{country}`
📮 *Zip*: `{zip_code}`
✉️ *Email*: `{email}`
📱 *Mobile*: `{phone}`"""
        
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
            
            return f"""👤 *Name*: `{full_name}`
🏠 *Street*: `{street_address}`
🌆 *City*: `{city}`
🏢 *State*: `{state}`
🌍 *Country*: `{country}`
📮 *Zip*: `{zip_code}`
✉️ *Email*: `{email}`
📱 *Mobile*: `{phone}`"""


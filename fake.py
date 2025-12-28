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
    country_code = country_code.upper().strip()
    
    # Direct mapping for common country codes
    if country_code not in COUNTRY_LOCALE_MAP:
        # Try to find by partial match
        for code, locale in COUNTRY_LOCALE_MAP.items():
            if code.upper() == country_code:
                country_code = code
                break
        else:
            # Default to US if not found
            country_code = 'US'
    
    locale = COUNTRY_LOCALE_MAP.get(country_code, 'en_US')
    
    if locale not in _fakers:
        try:
            _fakers[locale] = Faker(locale)
        except Exception as e:
            # Fallback to US if locale not supported
            print(f"Warning: Locale {locale} not supported, using en_US: {e}")
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
        # Get country name based on locale mapping
        country_name_map = {
            'en_US': 'United States', 'en_GB': 'United Kingdom', 'en_CA': 'Canada', 'en_AU': 'Australia',
            'pt_BR': 'Brazil', 'pt_PT': 'Portugal',
            'es_MX': 'Mexico', 'es_ES': 'Spain', 'es_AR': 'Argentina', 'es_CO': 'Colombia',
            'fr_FR': 'France', 'de_DE': 'Germany', 'it_IT': 'Italy', 'nl_NL': 'Netherlands',
            'pl_PL': 'Poland', 'ru_RU': 'Russia', 'ja_JP': 'Japan', 'zh_CN': 'China',
            'en_IN': 'India', 'ko_KR': 'South Korea', 'tr_TR': 'Turkey', 'id_ID': 'Indonesia',
            'en_PH': 'Philippines', 'th_TH': 'Thailand', 'vi_VN': 'Vietnam', 'en_MY': 'Malaysia',
            'en_SG': 'Singapore', 'en_NZ': 'New Zealand', 'en_IE': 'Ireland', 'en_ZA': 'South Africa',
            'ar_AE': 'United Arab Emirates', 'ar_SA': 'Saudi Arabia', 'ar_EG': 'Egypt',
            'de_CH': 'Switzerland', 'de_AT': 'Austria', 'nl_BE': 'Belgium',
            'sv_SE': 'Sweden', 'nb_NO': 'Norway', 'da_DK': 'Denmark', 'fi_FI': 'Finland',
            'el_GR': 'Greece', 'cs_CZ': 'Czech Republic', 'hu_HU': 'Hungary', 'ro_RO': 'Romania',
            'es_CL': 'Chile', 'es_PE': 'Peru', 'es_VE': 'Venezuela', 'es_EC': 'Ecuador',
        }
        locale = COUNTRY_LOCALE_MAP.get(country_code.upper(), 'en_US')
        country = country_name_map.get(locale, 'United States')
        
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


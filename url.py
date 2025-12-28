import requests
import re
import socket
import ssl
import whois
import asyncio
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

from telegram import Update, constants, InputFile
from telegram.ext import Application, CommandHandler, ContextTypes

# --- Configuration & Constants ---
BOT_TOKEN = "5937330270:AAGiVsbLmjXisi3uirKfI5mhUtBt61iPzbo" # Your bot token
DEVELOPER_USERNAME = "@mhitzxg"
DEVELOPER_LINK = "https://t.me/mhitzxg"
CHECKER_USERNAME = "mhitzxg "
CHECKER_LINK = "https://t.me/mhitzxg"
TEAM_LINK = "https://t.me/mhitzxg"
BOT_NAME = "[✦] 𝗚𝗮𝘁𝗲𝘄𝗮𝘆 𝗦𝗰𝗮𝗻𝗻𝗲𝗿 [✦]"
SAVED_RESULTS_FILE = "saved_sites.txt"
DIVIDER = f"[▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬]({TEAM_LINK})"

# --- MASSIVELY EXPANDED GATEWAY LIST ---
PAYMENT_GATEWAYS = sorted(list(set([
    # Major Global Players
    "Stripe", "PayPal", "Square", "Adyen", "Braintree", "Worldpay", "Checkout.com", 
    "Authorize.Net", "2Checkout", "Verifone", "Ingenico", "Global Payments",

    # E-commerce Platforms
    "Shopify", "Shopify Payments", "WooCommerce", "BigCommerce", "Magento", "Magento Payments", 
    "OpenCart", "PrestaShop", "Ecwid", "Volusion",

    # Regional & International
    "Mollie", "Klarna", "PayU", "Razorpay", "Paytm", "Mercado Pago", "PagSeguro", 
    "dLocal", "Alipay", "WeChat Pay", "Skrill", "Payoneer", "Afterpay", "Affirm", 
    "GoCardless", "SecurionPay", "Paysafe", "HiPay", "Paycomet", "Realex Payments",
    "eWay", "Paystack", "Flutterwave", "Yandex.Kassa", "Qiwi", "Dragonpay",

    # Subscription & Recurring Billing
    "Recurly", "Chargify", "Chargebee", "Zuora",

    # Crypto Gateways
    "Coinbase", "Coinbase Commerce", "BitPay", "CoinPayments", "Crypto.com Pay", "Utrust",

    # US & North America Focused
    "PayJunction", "PaySimple", "BluePay", "CardConnect", "Clover", "Heartland Payment Systems",
    "Elavon", "First Data", "Vantiv", "Chase Paymentech", "Moneris", "USAePay", 
    "eProcessing", "Cardknox", "Payeezy", "PayFlow", "Fluidpay", "LawPay",

    # Other Specific/Niche Gateways
    "Amazon Pay", "Apple Pay", "Google Pay", "WePay", "Blackbaud", "Sage Pay", "SagePayments",
    "Auruspay", "CyberSource", "Rocketgate", "NMI", "Network Merchants", "Paytrace",
    "Ebizcharge", "Convergepay", "Oceanpayments",
    
    # Common Variations & Technical Names
    "auth.net", "Authnet", "cybersource", "payflow", "worldpay.com", "securepay", 
    "hostedpayments", "geomerchant", "creo", "cpay", "matt sorra", "Ebiz"
])))


SECURITY_INDICATORS = {
    'captcha': ['captcha', 'protected by recaptcha', "i'm not a robot", 'recaptcha/api.js', 'hcaptcha'],
    'cloudflare': ['cloudflare', 'cdnjs.cloudflare.com', 'challenges.cloudflare.com', '/cdn-cgi/']
}

# --- Core Processing Logic (No changes needed) ---

def normalize_url(url):
    if not re.match(r'^https?://', url, re.I):
        return 'http://' + url
    return url

def get_server_details(url):
    try:
        hostname = urlparse(url).hostname
        if not hostname: return {'ip': 'N/A', 'host': 'N/A', 'ssl_active': 'N/A', 'ssl_issuer': 'N/A'}
        ip_address = socket.gethostbyname(hostname)
        host_org = 'N/A'
        try:
            w = whois.whois(hostname)
            if w and w.org: host_org = w.org
        except Exception: pass
        ssl_active, ssl_issuer = False, 'N/A'
        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=3) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    ssl_active = True
                    issuer = dict(x[0] for x in cert['issuer'])
                    ssl_issuer = issuer.get('organizationName', 'N/A')
        except Exception: pass
        return {'ip': ip_address, 'host': host_org, 'ssl_active': 'Yes' if ssl_active else 'No', 'ssl_issuer': ssl_issuer}
    except Exception:
        return {'ip': 'N/A', 'host': 'N/A', 'ssl_active': 'N/A', 'ssl_issuer': 'N/A'}

def process_url(url):
    normalized_url = normalize_url(url)
    result = {'url': normalized_url, 'gateways': [], 'captcha': False, 'cloudflare': False, 'server_details': {}, 'web_server': 'N/A', 'error': None}
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(normalized_url, timeout=10, headers=headers)
        response.raise_for_status()
        content = response.text
        # Use a case-insensitive search for better matching
        content_lower = content.lower()
        detected = set()
        for gateway in PAYMENT_GATEWAYS:
            if re.search(r'\b' + re.escape(gateway.lower()) + r'\b', content_lower):
                detected.add(gateway)
        result['gateways'] = sorted(list(detected))
        
        result['captcha'] = any(re.search(ind, content, re.I) for ind in SECURITY_INDICATORS['captcha'])
        result['cloudflare'] = any(re.search(ind, content, re.I) for ind in SECURITY_INDICATORS['cloudflare'])
        result['server_details'] = get_server_details(normalized_url)
        result['web_server'] = response.headers.get('Server', 'N/A')
    except requests.RequestException as e:
        result['error'] = str(e)
    return result

# --- Telegram Bot Handlers (No changes needed) ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        f"**{BOT_NAME}**\n"
        f"{DIVIDER}\n\n"
        "**»»——— 𝗖𝗢𝗠𝗠𝗔𝗡𝗗𝗦 ———««**\n\n"
        "➤ **/url** `<website.com>`\n"
        "▸ Analyzes a website for gateways, security, and server info.\n\n"
        "➤ **/save**\n"
        "▸ Saves all \"Clean\" sites from your last scan.\n\n"
        "➤ **/getfile**\n"
        "▸ Sends you the `saved_sites.txt` file.\n\n"
        "*Click a command to use it or type it in chat.*\n\n"
        f"{DIVIDER}\n\n"
        "**Bot Developer:**\n"
        f"👨‍💻 **{DEVELOPER_USERNAME}** » [{DEVELOPER_LINK.split('/')[-1]}]({DEVELOPER_LINK})\n\n"
        "**Checked By:**\n"
        f"✨ **{CHECKER_USERNAME}** » [{CHECKER_LINK.split('/')[-1]}]({CHECKER_LINK})"
    )
    await update.message.reply_text(message, parse_mode=constants.ParseMode.MARKDOWN, disable_web_page_preview=True)

async def url_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    urls = context.args
    if not urls:
        await update.message.reply_text("Please provide at least one URL.\n**Example:** `/url example.com`", parse_mode=constants.ParseMode.MARKDOWN)
        return

    total_urls = len(urls)
    progress_message = await update.message.reply_text(f"🚀 **Analyzing {total_urls} URLs...**\n`[                    ] 0%`", parse_mode=constants.ParseMode.MARKDOWN)

    results = []
    completed_count = 0

    def get_progress_bar(percentage):
        filled_length = int(20 * percentage // 100)
        bar = '█' * filled_length + ' ' * (20 - filled_length)
        return f"`[{bar}] {percentage}%`"

    async def update_progress():
        last_percentage = -1
        while completed_count < total_urls:
            percentage = (completed_count * 100) // total_urls
            if percentage > last_percentage:
                try:
                    await progress_message.edit_text(
                        f"🚀 **Analyzing {total_urls} URLs...**\n{get_progress_bar(percentage)}",
                        parse_mode=constants.ParseMode.MARKDOWN
                    )
                    last_percentage = percentage
                except Exception: pass
            await asyncio.sleep(1)

    progress_task = asyncio.create_task(update_progress())

    with ThreadPoolExecutor(max_workers=10) as executor:
        loop = asyncio.get_event_loop()
        futures = [loop.run_in_executor(executor, process_url, url) for url in urls]
        for future in asyncio.as_completed(futures):
            results.append(await future)
            completed_count += 1

    progress_task.cancel()
    await progress_message.edit_text("✅ **Analysis Complete!** Generating your report...", parse_mode=constants.ParseMode.MARKDOWN)
    
    context.user_data['last_results'] = results
    
    report_header = f"**{BOT_NAME}**\n\n**Analysis Report: {total_urls} URLs Processed**\n"
    report_parts = []

    for res in results:
        part = f"{DIVIDER}\n\n"
        security_detected = res['captcha'] or res['cloudflare']
        
        if res['error']:
            part += f"❗️ **URL:** `{res['url']}`\n\n"
            part += f"**» STATUS:** ❗️ **Error - Fetch Failed**\n`{res['error']}`\n"
        elif not res['gateways']:
            part += f"⚠️ **URL:** `{res['url']}`\n\n"
            part += "**» STATUS:** ⚠️ **No Gateways Found - Skipped**\n"
        else:
            status_icon = "❌" if security_detected else "✅"
            status_text = "Security Detected - Skipped" if security_detected else "Clean - Ready to Save"
            part += f"{status_icon} **URL:** `{res['url']}`\n\n"
            part += f"**» STATUS:** {status_icon} **{status_text}**\n\n"
            part += "**💳 Payment Gateways:**\n" + "\n".join([f"  ` • {g}`" for g in res['gateways']]) + "\n\n"
            part += "**🛡️ Security Scan:**\n"
            part += f"  ` • CAPTCHA:` {'Yes' if res['captcha'] else 'No'}\n"
            part += f"  ` • Cloudflare:` {'Yes' if res['cloudflare'] else 'No'}\n\n"
            sd = res['server_details']
            part += "**🌐 Server Details:**\n"
            part += f"  ` • IP Address:` {sd['ip']}\n"
            part += f"  ` • Host:` {sd['host']}\n"
            part += f"  ` • SSL Active:` {sd['ssl_active']} (Issued by: {sd['ssl_issuer']})\n"
            part += f"  ` • Web Server:` {res['web_server']}\n"
        report_parts.append(part)

    report_footer = f"{DIVIDER}\n**Checked by [{DEVELOPER_USERNAME}]({DEVELOPER_LINK})**"
    full_report = report_header + "\n".join(report_parts) + report_footer
    
    for i in range(0, len(full_report), 4096):
        await update.message.reply_text(full_report[i:i+4096], parse_mode=constants.ParseMode.MARKDOWN, disable_web_page_preview=True)

async def save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'last_results' not in context.user_data:
        await update.message.reply_text("You need to run a `/url` scan first before saving.")
        return
    clean_results = [res for res in context.user_data['last_results'] if res.get('gateways') and not res.get('captcha') and not res.get('cloudflare')]
    if not clean_results:
        await update.message.reply_text("No clean sites found in the last scan to save.")
        return
    count = 0
    with open(SAVED_RESULTS_FILE, "a") as f:
        for res in clean_results:
            f.write(f"URL: {res['url']}\nGateways: {', '.join(res['gateways'])}\n----------------------------------------\n")
            count += 1
    await update.message.reply_text(f"✅ **Success!** Saved {count} clean site(s) to `{SAVED_RESULTS_FILE}`.")
    context.user_data.pop('last_results')

async def getfile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open(SAVED_RESULTS_FILE, "rb") as f:
            await update.message.reply_document(document=InputFile(f, filename=SAVED_RESULTS_FILE), caption=f"Here is your file of saved sites.\n\n**Checked by [{DEVELOPER_USERNAME}]({DEVELOPER_LINK})**", parse_mode=constants.ParseMode.MARKDOWN)
    except FileNotFoundError:
        await update.message.reply_text(f"The file `{SAVED_RESULTS_FILE}` does not exist yet. Run a scan and use `/save` to create it.")

def main():
    print(f"Starting {BOT_NAME}...")
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("url", url_command))
    application.add_handler(CommandHandler("save", save_command))
    application.add_handler(CommandHandler("getfile", getfile_command))
    application.run_polling()

if __name__ == "__main__":
    main()

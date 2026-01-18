# Auto-install missing dependencies
import subprocess
import sys
import os
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

def install_package(package):
    """Install a package using pip."""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except subprocess.CalledProcessError:
        print(f"❌ Failed to install {package}")
        sys.exit(1)

def check_and_install_dependencies():
    """Check and install required packages with version support."""
    required_packages = [
        ("python-telegram-bot[job-queue]", "telegram", "20.7"),
        ("aiohttp", "aiohttp", "3.9.1"),
        ("requests", "requests", "2.31.0"),
        ("phonenumbers", "phonenumbers", "8.13.26")
    ]
    
    for package_info in required_packages:
        if len(package_info) == 3:
            package, import_name, version = package_info
            package_with_version = f"{package}=={version}"
        else:
            package, import_name = package_info
            package_with_version = package
            
        try:
            __import__(import_name)
        except ImportError:
            print(f"📦 Installing {package}...")
            # Try installing with version first, fallback to latest if fails
            try:
                install_package(package_with_version)
            except:
                print(f"⚠️  Version {version} failed, trying latest version...")
                install_package(package)
    print("✅ Dependencies ready")

# Check and install dependencies before importing
check_and_install_dependencies()

import asyncio
import logging
import re
import json
import requests
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    format='%(levelname)s: %(message)s',
    level=logging.INFO
)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# Country name to ISO 3166-1 alpha-2 code mapping
COUNTRY_CODES = {
    # Africa
    'algeria': 'DZ', 'angola': 'AO', 'benin': 'BJ', 'botswana': 'BW', 'burkina faso': 'BF',
    'burundi': 'BI', 'cameroon': 'CM', 'cape verde': 'CV', 'central african republic': 'CF',
    'chad': 'TD', 'comoros': 'KM', 'congo': 'CG', 'dr congo': 'CD',
    "cote d'ivoire": 'CI', 'ivory coast': 'CI', 'djibouti': 'DJ', 'egypt': 'EG',
    'eritrea': 'ER', 'ethiopia': 'ET', 'gabon': 'GA', 'gambia': 'GM', 'ghana': 'GH',
    'guinea': 'GN', 'kenya': 'KE', 'liberia': 'LR', 'libya': 'LY',
    'madagascar': 'MG', 'malawi': 'MW', 'mali': 'ML', 'mauritius': 'MU', 'morocco': 'MA',
    'mozambique': 'MZ', 'namibia': 'NA', 'niger': 'NE', 'nigeria': 'NG', 'rwanda': 'RW',
    'senegal': 'SN', 'sierra leone': 'SL', 'somalia': 'SO', 'south africa': 'ZA',
    'sudan': 'SD', 'tanzania': 'TZ', 'togo': 'TG', 'tunisia': 'TN', 'uganda': 'UG',
    'zambia': 'ZM', 'zimbabwe': 'ZW',
    # Asia
    'afghanistan': 'AF', 'bangladesh': 'BD', 'cambodia': 'KH', 'china': 'CN',
    'hong kong': 'HK', 'india': 'IN', 'indonesia': 'ID', 'iran': 'IR', 'iraq': 'IQ',
    'israel': 'IL', 'japan': 'JP', 'jordan': 'JO', 'kuwait': 'KW', 'laos': 'LA',
    'lebanon': 'LB', 'malaysia': 'MY', 'mongolia': 'MN', 'myanmar': 'MM',
    'nepal': 'NP', 'oman': 'OM', 'pakistan': 'PK', 'philippines': 'PH',
    'qatar': 'QA', 'saudi arabia': 'SA', 'singapore': 'SG', 'south korea': 'KR',
    'sri lanka': 'LK', 'syria': 'SY', 'taiwan': 'TW', 'thailand': 'TH',
    'turkey': 'TR', 'uae': 'AE', 'united arab emirates': 'AE', 'vietnam': 'VN', 'yemen': 'YE',
    # Europe
    'austria': 'AT', 'belgium': 'BE', 'bulgaria': 'BG', 'croatia': 'HR', 'czech republic': 'CZ',
    'denmark': 'DK', 'estonia': 'EE', 'finland': 'FI', 'france': 'FR', 'germany': 'DE', 'greece': 'GR',
    'hungary': 'HU', 'iceland': 'IS', 'ireland': 'IE', 'italy': 'IT', 'latvia': 'LV',
    'lithuania': 'LT', 'netherlands': 'NL', 'norway': 'NO', 'poland': 'PL', 'portugal': 'PT',
    'romania': 'RO', 'russia': 'RU', 'serbia': 'RS', 'slovakia': 'SK', 'slovenia': 'SI',
    'spain': 'ES', 'sweden': 'SE', 'switzerland': 'CH', 'ukraine': 'UA',
    'uk': 'GB', 'united kingdom': 'GB', 'england': 'GB',
    # Americas
    'argentina': 'AR', 'brazil': 'BR', 'canada': 'CA', 'chile': 'CL', 'colombia': 'CO',
    'cuba': 'CU', 'ecuador': 'EC', 'mexico': 'MX', 'peru': 'PE', 'usa': 'US', 'united states': 'US',
    'uruguay': 'UY', 'venezuela': 'VE',
    # Oceania
    'australia': 'AU', 'new zealand': 'NZ', 'fiji': 'FJ', 'papua new guinea': 'PG'
}

def get_country_flag(country_name):
    """Auto-generate flag emoji from country name"""
    if not country_name:
        return '🏳️'
    code = COUNTRY_CODES.get(country_name.lower().strip())
    if not code:
        return '🏳️'
    # Convert 2-letter code to flag emoji using regional indicator symbols
    return ''.join(chr(127397 + ord(c)) for c in code.upper())

# For backwards compatibility - use the function
COUNTRY_FLAGS = {}

class NumberBotWithOTP:
    def __init__(self, bot_token, chat_id, api_key):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_key = api_key
        self.application = Application.builder().token(self.bot_token).build()
        self.api_base_url = 'https://api.otprevenue.com/api'
        self.number_api_url = 'https://api.otprevenue.com/api/numbers'
        self.current_numbers = {}  # Track current number per user per country
        self.sent_numbers = set()
        self.start_time = None
        self.user_otp_messages = {}  # Track OTP message IDs per user for deletion
        self.active_users = set()  # Track all users who have started the bot
    
    async def get_available_countries(self):
        """Get list of countries with available numbers."""
        try:
            headers = {'X-API-Key': self.api_key, 'Content-Type': 'application/json'}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.number_api_url}/available-countries',
                    headers=headers,
                    json={}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success'):
                            return data.get('data', {}).get('countries', [])
                    return []
        except Exception as e:
            logging.error(f"Error getting countries: {e}")
            return []
    
    async def get_number(self, country):
        """Get one number for a country."""
        try:
            headers = {'X-API-Key': self.api_key, 'Content-Type': 'application/json'}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.number_api_url}/get-number',
                    headers=headers,
                    json={'country': country}
                ) as response:
                    data = await response.json()
                    if response.status == 200 and data.get('success'):
                        return data.get('data')
                    return None
        except Exception as e:
            logging.error(f"Error getting number: {e}")
            return None
    
    async def change_number(self, country):
        """Change to a new number for a country."""
        try:
            headers = {'X-API-Key': self.api_key, 'Content-Type': 'application/json'}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.number_api_url}/change-number',
                    headers=headers,
                    json={'country': country}
                ) as response:
                    data = await response.json()
                    if response.status == 200 and data.get('success'):
                        return data.get('data')
                    return None
        except Exception as e:
            logging.error(f"Error changing number: {e}")
            return None
    
    def build_country_keyboard(self, countries):
        """Build inline keyboard with country buttons."""
        keyboard = []
        row = []
        for i, country_data in enumerate(countries):
            country = country_data['country']
            flag = get_country_flag(country)
            button = InlineKeyboardButton(
                f"{flag} {country}",
                callback_data=f"country:{country}"
            )
            row.append(button)
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        return InlineKeyboardMarkup(keyboard)
    
    def build_number_keyboard(self, country):
        """Build keyboard for number actions."""
        keyboard = [
            [InlineKeyboardButton("🔄 Change Number", callback_data=f"change:{country}")],
            [InlineKeyboardButton("◀️ Back to Countries", callback_data="countries")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send welcome message with country buttons."""
        # Track this user for OTP notifications
        user_id = update.effective_user.id
        self.active_users.add(user_id)
        logging.info(f"User {user_id} started bot. Active users: {self.active_users}")
        
        countries = await self.get_available_countries()
        
        if not countries:
            await update.message.reply_text(
                "❌ No numbers available. Please download numbers from the OTP Revenue dashboard first."
            )
            return
        
        keyboard = self.build_country_keyboard(countries)
        welcome_text = (
            f"*📊 Welcome To Number Bot!*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"_Press country below ⤵️ to get numbers._"
        )
        
        # Send to bot DM only (not to group)
        await update.message.reply_text(
            welcome_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def show_countries(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show countries menu."""
        query = update.callback_query
        await query.answer()
        
        # Delete all OTP messages for this user when going back to countries
        user_id = query.from_user.id
        if user_id in self.user_otp_messages:
            for msg_id in self.user_otp_messages[user_id]:
                try:
                    await self.application.bot.delete_message(
                        chat_id=user_id,
                        message_id=msg_id
                    )
                except Exception as e:
                    logging.error(f"Could not delete message {msg_id}: {e}")
            # Clear the list
            self.user_otp_messages[user_id] = []
        
        countries = await self.get_available_countries()
        
        if not countries:
            await query.edit_message_text(
                "❌ No numbers available. Please download more numbers from the dashboard."
            )
            return
        
        keyboard = self.build_country_keyboard(countries)
        welcome_text = (
            f"*📊 Welcome To Number Bot!*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"_Press country below ⤵️ to get numbers._"
        )
        await query.edit_message_text(
            welcome_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def handle_country_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle country button press."""
        query = update.callback_query
        await query.answer()
        
        country = query.data.split(":")[1]
        user_id = query.from_user.id
        
        # Get a number for this country
        number_data = await self.get_number(country)
        
        if not number_data:
            await query.edit_message_text(
                f"❌ No numbers available for {country}.\n\n"
                f"Please download more numbers from the dashboard or try another country.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Back to Countries", callback_data="countries")
                ]])
            )
            return
        
        # Store current number for this user
        self.current_numbers[f"{user_id}:{country}"] = number_data
        
        # Format message
        flag = get_country_flag(country)
        phone_number = number_data.get('number', 'Unknown')
        range_name = number_data.get('range', 'Unknown')
        
        # Reply to user with updated format
        keyboard = self.build_number_keyboard(country)
        await query.edit_message_text(
            f"✅ *Number Assigned!*\n\n"
            f"📱 Number: `{phone_number}`\n"
            f"🌍 Country: {flag} {country}\n"
            f"📋 Range: {range_name}\n\n"
            f"🔐 Your OTP: _Waiting..._\n"
            f"💬 Full Message: _Waiting for OTP..._",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def handle_change_number(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle change number button press."""
        query = update.callback_query
        await query.answer("Getting new number...")
        
        country = query.data.split(":")[1]
        
        # Get a new number
        number_data = await self.change_number(country)
        
        if not number_data:
            await query.edit_message_text(
                f"❌ No more numbers available for {country}.\n\n"
                f"Please download more numbers from the dashboard.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Back to Countries", callback_data="countries")
                ]])
            )
            return
        
        # Update stored number
        user_id = query.from_user.id
        
        # Delete previous OTP messages for this user
        if user_id in self.user_otp_messages:
            for msg_id in self.user_otp_messages[user_id]:
                try:
                    await self.application.bot.delete_message(
                        chat_id=user_id,
                        message_id=msg_id
                    )
                except Exception as e:
                    logging.error(f"Could not delete message {msg_id}: {e}")
            # Clear the list
            self.user_otp_messages[user_id] = []
        
        self.current_numbers[f"{user_id}:{country}"] = number_data
        
        # Format and send (no group message for number change)
        flag = get_country_flag(country)
        phone_number = number_data.get('number', 'Unknown')
        range_name = number_data.get('range', 'Unknown')
        
        keyboard = self.build_number_keyboard(country)
        await query.edit_message_text(
            f"🔄 *Number Changed!*\n\n"
            f"📱 New Number: `{phone_number}`\n"
            f"🌍 Country: {flag} {country}\n"
            f"📋 Range: {range_name}\n\n"
            f"🔐 Your OTP: _Waiting..._\n"
            f"💬 Full Message: _Waiting for OTP..._",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Route callback queries to appropriate handlers."""
        query = update.callback_query
        data = query.data
        
        if data.startswith("country:"):
            await self.handle_country_selection(update, context)
        elif data.startswith("change:"):
            await self.handle_change_number(update, context)
        elif data == "countries":
            await self.show_countries(update, context)
    
    async def get_recent_success_numbers_after_start(self, limit=50):
        """Get success numbers created after bot start time."""
        try:
            if not self.start_time:
                return []
            
            headers = {'X-API-Key': self.api_key}
            start_time_iso = self.start_time.isoformat()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f'{self.api_base_url}/v1/success-numbers?page=1&limit={limit}&after={start_time_iso}',
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('data', {}).get('numbers', [])
                    return []
        except Exception as e:
            logging.error(f"Error getting success numbers: {e}")
            return []
    
    def escape_markdown(self, text):
        """Escape special characters for MarkdownV2."""
        if not isinstance(text, str):
            text = str(text)
        chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in chars:
            text = text.replace(char, f'\\{char}')
        return text

    def mask_number(self, number):
        """Mask phone number."""
        clean = re.sub(r'\D', '', number)
        if len(clean) > 6:
            return clean[:5] + "*****" + clean[-3:]
        return number
    
    async def send_success_numbers_to_group(self):
        """Fetch and send NEW success numbers to the group."""
        try:
            numbers = await self.get_recent_success_numbers_after_start(50)
            
            if not numbers:
                return
            
            for number in numbers:
                number_id = number.get('id')
                if number_id and number_id not in self.sent_numbers:
                    self.sent_numbers.add(number_id)
                    
                    # Format time
                    time_str = number.get('receivedAt', 'N/A')
                    if time_str != 'N/A':
                        try:
                            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                            bd_time = dt + timedelta(hours=6)
                            formatted_time = bd_time.strftime('%d-%m-%Y %I:%M:%S %p')
                        except:
                            formatted_time = time_str
                    else:
                        formatted_time = 'N/A'
                    
                    country = number.get('country', 'N/A')
                    phone_number = number.get('phoneNumber', 'N/A')
                    otp_code = number.get('otpCode', 'N/A')
                    service = number.get('service', 'N/A')
                    full_message = number.get('fullMessage', 'N/A')
                    
                    masked_phone = self.mask_number(phone_number)
                    if not masked_phone.startswith('+'):
                        masked_phone = '+' + masked_phone
                    
                    # Create formatted message using .format() to avoid escaping issues
                    text = (
                        "📬 \"{}\" OTP Received\\!\n\n"
                        "Number: `{}`\n"
                        "🔐OTP: `{}`\n"
                        "Country: {}\n"
                        "Time: {}\n\n"
                        "`{}`"
                    ).format(
                        self.escape_markdown(service),
                        self.escape_markdown(masked_phone),
                        self.escape_markdown(otp_code),
                        self.escape_markdown(country),
                        self.escape_markdown(formatted_time),
                        self.escape_markdown(full_message)
                    )
                    
                    keyboard = [
                        [
                            InlineKeyboardButton("Bot", url=f"https://t.me/lamixsmsbot"),
                            InlineKeyboardButton("Group", url="https://t.me/auroratechinc")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await self.application.bot.send_message(
                        chat_id=self.chat_id,
                        text=text,
                        parse_mode='MarkdownV2',
                        disable_web_page_preview=True,
                        reply_markup=reply_markup
                    )
                    
                    # Send to user who has this number
                    # Normalize phone numbers for comparison
                    normalized_phone = phone_number.replace('+', '').replace(' ', '').replace('-', '').strip()
                    
                    logging.info(f"Looking for user with number {phone_number} (normalized: {normalized_phone})")
                    logging.info(f"Current numbers stored: {self.current_numbers}")
                    
                    for key, num_data in self.current_numbers.items():
                        stored_number = str(num_data.get('number', ''))
                        normalized_stored = stored_number.replace('+', '').replace(' ', '').replace('-', '').strip()
                        
                        logging.info(f"Comparing: {normalized_phone} vs {normalized_stored}")
                        
                        if normalized_stored == normalized_phone or normalized_phone.endswith(normalized_stored[-10:]) or normalized_stored.endswith(normalized_phone[-10:]):
                            try:
                                user_id = int(key.split(':')[0])
                                logging.info(f"📨 Match found! Sending OTP to user {user_id}")
                                dm_msg = await self.application.bot.send_message(
                                    chat_id=user_id,
                                    text=text,
                                    parse_mode='MarkdownV2',
                                    disable_web_page_preview=True,
                                    reply_markup=reply_markup
                                )
                                if user_id not in self.user_otp_messages:
                                    self.user_otp_messages[user_id] = []
                                self.user_otp_messages[user_id].append(dm_msg.message_id)
                                logging.info(f"✅ Sent OTP to user DM: {user_id}")
                            except Exception as dm_error:
                                logging.error(f"❌ Could not send to user: {dm_error}")
                            break
                    
                    logging.info(f"Sent OTP for: {phone_number}")
            
        except Exception as e:
            logging.error(f"Error sending success numbers: {e}")
    
    async def check_and_send_success_numbers(self, context):
        """Check and send success numbers (called by job queue)."""
        try:
            await self.send_success_numbers_to_group()
        except Exception as e:
            logging.error(f"Error in check_and_send: {e}")
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check bot status."""
        countries = await self.get_available_countries()
        total = sum(c.get('available', 0) for c in countries)
        
        await update.message.reply_text(
            f"✅ *Bot Status: Active*\n\n"
            f"🤖 Bot: @@lamixsmsbot\n"
            f"💬 Group: https://t.me/auroratechinc\n"
            f"📱 Available Numbers: {total}\n"
            f"🌍 Countries: {len(countries)}\n"
            f"⏰ Running Since: {self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else 'N/A'}",
            parse_mode='Markdown'
        )
    
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help information."""
        await update.message.reply_text(
            f"🆘 *Help - Number Bot with OTP Fetcher*\n\n"
            f"This bot provides phone numbers from your OTP Revenue account "
            f"and automatically forwards received OTPs to your group.\n\n"
            f"*How to use:*\n"
            f"1. Use /start to see available countries\n"
            f"2. Click a country button to get a number\n"
            f"3. Use 'Change Number' to get a different number\n"
            f"4. OTPs are automatically forwarded to the group\n\n"
            f"*Commands:*\n"
            f"/start - Show country menu\n"
            f"/status - Check bot status\n"
            f"/help - Show this help",
            parse_mode='Markdown'
        )
    
    def run(self):
        """Start the bot."""
        self.start_time = datetime.now()
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("status", self.status))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CallbackQueryHandler(self.callback_handler))
        
        # Start OTP monitoring
        self.application.job_queue.run_repeating(
            self.check_and_send_success_numbers,
            interval=10,
            first=10
        )
        
        print("🚀 Number Bot with OTP Fetcher starting...")
        print(f"📱 Bot: @lamixsmsbot")
        print(f"💬 Group: https://t.me/auroratechinc")
        
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

def start_port_listener(port):
    try:
        server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        print(f"🌐 Listening on port {port}")
    except Exception as e:
        logging.error(f"Port listener failed: {e}")

if __name__ == '__main__':
    # Start a simple port listener (use PORT env var or default 8080)
    port = int(os.environ.get('PORT', '8080'))
    start_port_listener(port)

    bot = NumberBotWithOTP(
        bot_token="8205264851:AAHFV4DlltpT-U-k1kUn2cGazw72F1R-y9E",
        chat_id="7500869913",
        api_key="8343cb00e33c0ebc3459fc5831d962d36805bdbc954b044f0d1b91119e0a72b8"
    )
    bot.run()

# Features:
# ✅ Country selection with flag buttons
# ✅ Get numbers via Number API
# ✅ Change number functionality
# ✅ Real-time OTP forwarding to group
# ✅ Duplicate prevention
# ✅ Automatic dependency installation

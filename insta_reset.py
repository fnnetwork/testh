import logging
import random
import aiohttp
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters

# Enable logging with DEBUG level for detailed logs
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG)

# Define conversation states
ASKING_USERNAME = 1
CHOOSING_NEXT_ACTION = 2

# Telegram bot tokens and admin IDs
MAIN_BOT_TOKEN = "7840571530:AAEfJDlRPOX2A1MUTiWDn_dSzsh8sFezCIc"
LOG_BOT_TOKEN = "7564262913:AAFH3zNOPbJuRb-VmC1YGfndkuLPQY8INjk"
MAIN_ADMIN_ID = "7741973994"
LOG_BOT_ADMIN_ID = "7741973994"

# File paths for CSRF tokens, User-Agent strings, proxies, and app IDs
CSRF_FILE = "csrf_tokens.txt"
USER_AGENT_FILE = "user_agents.txt"
PROXY_FILE = "proxies.txt"
APP_ID_FILE = "ig_app_ids.txt"

# Function to load CSRF tokens from a file
def load_csrf_tokens():
    try:
        with open(CSRF_FILE, "r") as file:
            return [line.strip() for line in file.readlines() if line.strip()]
    except FileNotFoundError:
        logging.error("CSRF tokens file not found.")
        return []

# Function to load User-Agent strings from a file
def load_user_agents():
    try:
        with open(USER_AGENT_FILE, "r") as file:
            return [line.strip() for line in file.readlines() if line.strip()]
    except FileNotFoundError:
        logging.error("User-Agent file not found.")
        return []

# Function to load proxies from the file
def load_proxies():
    try:
        with open(PROXY_FILE, "r") as file:
            return [line.strip() for line in file.readlines() if line.strip()]
    except FileNotFoundError:
        logging.error(f"Proxy file {PROXY_FILE} not found.")
        return []

# Function to load app IDs from the file
def load_app_ids():
    try:
        with open(APP_ID_FILE, "r") as file:
            return [line.strip() for line in file.readlines() if line.strip()]
    except FileNotFoundError:
        logging.error(f"App ID file {APP_ID_FILE} not found.")
        return []

async def send_request_with_proxy_async(url, headers, data, proxies, username):
    random.shuffle(proxies)
    last_error = None

    for proxy in proxies:
        proxy_parts = proxy.split(":")
        if len(proxy_parts) == 4:
            proxy_host, proxy_port, proxy_user, proxy_pass = proxy_parts
            proxy_url = f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"  # Default to HTTP
        elif len(proxy_parts) == 2:
            proxy_url = f"http://{proxy_parts[0]}:{proxy_parts[1]}"
        else:
            last_error = f"Invalid proxy format: {proxy}"
            continue

        proxy_dict = {"http": proxy_url, "https": proxy_url}  # Support both HTTP and HTTPS
        try:
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(
                        url, headers=headers, data=data, proxy=proxy_dict["https"], timeout=20
                    ) as response:
                        if response.status == 200:
                            return True, "success", proxy
                        elif response.status == 429:
                            return False, "rate_limit", proxy
                        else:
                            try:
                                response_json = await response.json()
                                if (
                                    "message" in response_json
                                    and response_json["message"]
                                    == "Sorry, we can't send you a link to reset your password. Please contact Instagram for help."
                                ):
                                    return False, "specific_error", proxy
                            except Exception:
                                pass
                except aiohttp.ClientError as client_error:
                    last_error = f"Client error: {client_error}"
        except Exception as e:
            last_error = f"Unexpected error: {e}"
            continue

    return False, "error", last_error

# Function to notify log bot about each attempt
async def notify_log_bot(username, proxy, error, success, headers):
    log_bot_app = ApplicationBuilder().token(LOG_BOT_TOKEN).build()
    await log_bot_app.bot.send_message(
        chat_id=LOG_BOT_ADMIN_ID,
        text=(
            f"🔔 <b>Log Notification</b>\n\n"
            f"👤 Insta Username: {username}\n"
            f"🔗 Proxy: {proxy or 'None'}\n"
            f"🔄 <b>Status:</b> {'Success' if success else 'Failed'}\n"
            f"🛡️ <b>Headers:</b> {headers}\n"
            + (f"⚠️ <b>Error:</b> {error}\n" if not success else "")
        ),
        parse_mode='HTML'
    )

# Start/reset command handler for main bot
async def start_or_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"User {update.effective_user.id} triggered /start or /reset.")
    await update.message.reply_text("💬 Please enter the Instagram username for the password reset:")
    return ASKING_USERNAME

# Function to handle username input and send a single request attempt
async def handle_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text
    logging.info(f"Received username: {username} from user {update.effective_user.id}")

    # Load tokens, user agents, proxies, and app IDs
    csrf_tokens = load_csrf_tokens()
    user_agents = load_user_agents()
    proxies = load_proxies()
    app_ids = load_app_ids()

    if not csrf_tokens or not user_agents or not app_ids:
        logging.warning("Required tokens, User-Agent strings, or App IDs are missing.")
        await update.message.reply_text("❌ Missing required resources. Contact admin.")
        return ConversationHandler.END

    if not proxies:
        logging.warning("No proxies available.")
        await update.message.reply_text("❌ No proxies available. Contact admin.")
        return ConversationHandler.END

    url = 'https://i.instagram.com/api/v1/accounts/send_password_reset/'
    data = {"user_email": username}

    # Selecting multiple proxies for concurrent requests
    selected_proxies = random.sample(proxies, min(3, len(proxies)))  # Pick up to 3 proxies

    # Asynchronous request tasks
    tasks = []
    for proxy in selected_proxies:
        csrf_token = random.choice(csrf_tokens)
        user_agent = random.choice(user_agents)
        app_id = random.choice(app_ids)

        headers = {
            'authority': 'www.instagram.com',
            'accept': '*/*',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://www.instagram.com',
            'referer': 'https://www.instagram.com/accounts/password/reset/',
            'user-agent': user_agent,
            'x-csrftoken': csrf_token,
            'x-ig-app-id': app_id,
            'x-requested-with': 'XMLHttpRequest',
        }

        tasks.append(send_request_with_proxy_async(url, headers, data, [proxy], username))

    # Show attempt message
    attempt_message = await update.message.reply_text(
        f"🔄 <b>Reset in progress...</b>", parse_mode='HTML'
    )

    # Send the request with a random proxy
    success, error_type, proxy_info = await send_request_with_proxy_async(url, headers, data, proxies, username)

    logging.debug(f"Attempt {attempt_count}: Success: {success}, Error Type: {error_type}, Proxy: {proxy_info or 'None'}")

    # Delete current attempt message
    try:
        await attempt_message.delete()
        logging.debug(f"Deleted attempt message for attempt {attempt_count}.")
    except Exception as e:
        logging.error(f"Failed to delete attempt message for attempt {attempt_count}: {e}")

    # Send detailed logs to the log bot
    log_bot_app = ApplicationBuilder().token(LOG_BOT_TOKEN).build()
    await log_bot_app.bot.send_message(
        chat_id=LOG_BOT_ADMIN_ID,
        text=(
            f"🔔 <b>Log Notification</b>\n\n"
            f"👤 Telegram Username: @{update.effective_user.username or update.effective_user.id}\n"
            f"🆔 User ID: {update.effective_user.id}\n"
            f"🌐 Insta Username: {username}\n"
            f"🔗 Proxy: {proxy_info or 'None'}\n"
            f"🔄 <b>Status:</b> {'Success' if success else 'Failed'}\n"
            f"🛡️ <b>CSRF Token:</b> {csrf_token}\n"
            f"📱 <b>User-Agent:</b> {user_agent}\n"
            f"📱 <b>App ID:</b> {app_id}\n"
            + (f"⚠️ <b>Error Type:</b> {error_type.capitalize()}\n" if not success else "")
        ),
        parse_mode='HTML'
    )

    results = await asyncio.gather(*tasks)
    if success:
        logging.info(f"Password reset successful for username {username}.")
        await update.message.reply_text(
            f"🎉 <b>Password Reset Successful!</b>\n\n"
            f"🔐 <i>Username:</i> <b>{username}</b>\n"
            f"📥 <i>Please check your email for further instructions</i>\n"
            f"📢 <b>Join our channel @AL3X_G0D @RagnarServers</b>",
            parse_mode='HTML'
        )
    else:
        # Error handling if success is False
        error_message = "❌ "
    
        if error_type == "rate_limit":
            error_message += (
                "⚠️ Rate limit reached.\n\n"
                "This means Instagram has temporarily blocked requests from your IP address "
                "due to too many attempts in a short period of time.\n\n"
                "⏳ Please wait a while and try again later.\n\n"
                "👉 Join our channels for more updates:\n"
                "@AL3X_G0D\n"
                "@RagnarServers"
            )
        elif error_type == "specific_error":
            error_message += (
                "⚠️ Instagram-specific error.\n\n"
                "This issue comes directly from Instagram's side.\n"
                "It could be related to the account or the password reset process.\n\n"
                "📞 Please contact Instagram support for assistance.\n\n"
                "👉 Join our channels for more updates:\n"
                "@AL3X_G0D\n"
                "@RagnarServers"
            )
        elif error_type == "error":
            error_message += (
                "❗ An unknown error occurred.\n\n"
                "Please try again later or contact support.\n\n"
                "👉 Join our channels for more updates:\n"
                "@AL3X_G0D\n"
                "@RagnarServers"
            )    
        # Append the error message to the list and send it to the user
        error_messages.append(error_message)
        await update.message.reply_text(error_message)
    
    return ConversationHandler.END

# Main handler for the bot's start or reset command
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"User {update.effective_user.id} triggered /cancel.")
    await update.message.reply_text("❌ Process cancelled.")
    return ConversationHandler.END

# Set up the Telegram bot with conversation handler
def main():
    app = ApplicationBuilder().token(MAIN_BOT_TOKEN).build()

    # Set up the conversation handler
    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_or_reset), CommandHandler("reset", start_or_reset)],
        states={
            ASKING_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_username)],
            CHOOSING_NEXT_ACTION: [CallbackQueryHandler(cancel)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conversation_handler)

    app.run_polling()

if __name__ == '__main__':
    main()

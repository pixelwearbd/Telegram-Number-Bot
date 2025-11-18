# File: number_manager_bot_webhook.py
# This script is designed for Webhook deployment on platforms like Render.
# It uses the BOT_TOKEN and PORT environment variables for deployment.

import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# --- ১. প্রাথমিক সেটআপ ও লগিং ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ২. গ্লোবাল ভেরিয়েবল সেট করা ---
# Render/Heroku থেকে BOT_TOKEN, PORT এবং WEBHOOK_URL ভেরিয়েবলগুলি নিন।
# আপনার টোকেনটি সরাসরি এখানে দেওয়া আছে, যাতে Render-এ কোনো কনফিগারেশন মিস না হয়।
# টোকেনটি সুরক্ষিত রাখতে চাইলে, এটি Render-এর Environment Variable-এ সেট করাই শ্রেয়।

# WARNING: If you want to use the Environment Variable, use this line:
# BOT_TOKEN = os.environ.get("BOT_TOKEN") 
# But since you pasted it directly, we will use the direct value:
BOT_TOKEN = "8374666904:AAFk5fQWDC_MpXXtzTAUruGLUMWsTF84ptk" # আপনার টোকেনটি এখানে সেভ করা আছে

PORT = int(os.environ.get('PORT', 8080)) # Render অটোমেটিক পোর্ট সেট করে
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") # এটি Render সার্ভিসের URL

# ডেটা ফাইল পাথ - ফাইলগুলোর নামের বানান ঠিক করা হয়েছে (যদি GitHub-এ requirements.txt হয়ে থাকে)
DATA_FILES = {
    "sudan": {"number": "sudan_number.txt", "taken": "sudan_taken.txt"},
    "venezuela": {"number": "venezuela_number.txt", "taken": "venezuela_taken.txt"},
    "iran": {"number": "iran_number.txt", "taken": "iran_taken.txt"},
    "uganda": {"number": "uganda_number.txt", "taken": "uganda_taken.txt"},
}

# --- ৩. ফাইল হ্যান্ডলিং ফাংশন ---

def load_data(filename):
    """নির্দিষ্ট ফাইল থেকে নম্বর লোড করে"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        # যদি ফাইল না থাকে, তবে একটি ফাঁকা ফাইল তৈরি করে
        open(filename, 'a').close() 
        return []

def save_data(filename, data):
    """নম্বর ডেটা ফাইলে সেভ করে"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(data) + '\n')
    except Exception as e:
        logger.error(f"Error saving data to {filename}: {e}")

# --- ৪. ইউটিলিটি ফাংশন ---

def get_country_menu():
    """কান্ট্রি সিলেক্ট করার জন্য মেনু তৈরি করে"""
    keyboard = [
        [InlineKeyboardButton("🇸🇩 Sudan", callback_data='country_sudan')],
        [InlineKeyboardButton("🇻🇪 Venezuela", callback_data='country_venezuela')],
        [InlineKeyboardButton("🇮🇷 Iran", callback_data='country_iran')],
        [InlineKeyboardButton("🇺🇬 Uganda", callback_data='country_uganda')],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_action_menu(country_key):
    """নম্বর নেওয়া বা ফিরিয়ে দেওয়ার জন্য মেনু তৈরি করে"""
    keyboard = [
        [InlineKeyboardButton("নম্বর নিন", callback_data=f'get_{country_key}')],
        [InlineKeyboardButton("নম্বর ফিরিয়ে দিন", callback_data=f'return_{country_key}')],
        [InlineKeyboardButton("অন্য দেশ নির্বাচন করুন", callback_data='start')],
    ]
    return InlineKeyboardMarkup(keyboard)

# --- ৫. হ্যান্ডলার ফাংশন ---

async def start_command(update: Update, context):
    """'/start' কমান্ড হ্যান্ডেল করে এবং মেনু দেখায়"""
    chat_id = update.effective_chat.id
    reply_markup = get_country_menu()
    # \ এর সমস্যা এড়াতে Raw String ব্যবহার না করে শুধু স্ট্রিং ব্যবহার করা হয়েছে
    await context.bot.send_message(
        chat_id=chat_id,
        text="👋 স্বাগতম! আপনি কোন দেশের নম্বর ম্যানেজ করতে চান? 👇",
        reply_markup=reply_markup
    )

async def handle_button(update: Update, context):
    """ইনলাইন বাটনের ক্লিক হ্যান্ডেল করে"""
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id

    if data == 'start':
        await start_command(query, context)
        return

    # কান্ট্রি সিলেক্ট হলে
    if data.startswith('country_'):
        country_key = data.split('_')[1]
        reply_markup = get_action_menu(country_key)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=query.message.message_id,
            text=f"আপনি **{country_key.upper()}** নির্বাচন করেছেন। আপনি কী করতে চান?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return

    # নম্বর নেওয়ার অনুরোধ
    if data.startswith('get_'):
        country_key = data.split('_')[1]
        
        number_file = DATA_FILES[country_key]["number"]
        taken_file = DATA_FILES[country_key]["taken"]
        
        available_numbers = load_data(number_file)
        taken_numbers = load_data(taken_file)
        
        if available_numbers:
            number_to_give = available_numbers.pop(0)
            taken_numbers.append(number_to_give)
            
            save_data(number_file, available_numbers)
            save_data(taken_file, taken_numbers)

            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=query.message.message_id,
                text=f"✅ সফল! **{country_key.upper()}** এর নম্বর: `{number_to_give}`\n\nঅন্যান্য অপশনের জন্য আবার '/start' লিখুন বা নিচে মেনুতে ক্লিক করুন।",
                reply_markup=get_action_menu(country_key),
                parse_mode='Markdown'
            )
        else:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=query.message.message_id,
                text=f"❌ দুঃখিত, **{country_key.upper()}** এর জন্য আর কোনো নম্বর নেই।",
                reply_markup=get_action_menu(country_key),
                parse_mode='Markdown'
            )
        return

    # নম্বর ফিরিয়ে দেওয়ার অনুরোধ (ভুল করে নেওয়া হলে)
    if data.startswith('return_'):
        country_key = data.split('_')[1]
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=query.message.message_id,
            text=f"আপনি **{country_key.upper()}** এর নম্বর ফিরিয়ে দিতে চান। অনুগ্রহ করে সেই নম্বরটি মেসেজ করে পাঠান।",
            reply_markup=get_action_menu(country_key),
            parse_mode='Markdown'
        )
        # কনটেক্সট ডেটা সেভ করুন যাতে মেসেজ হ্যান্ডলার জানতে পারে কোন দেশের জন্য রিটার্ন করতে বলা হচ্ছে
        context.user_data['awaiting_return'] = country_key
        return

async def handle_return_message(update: Update, context):
    """ব্যবহারকারী যখন নম্বর ফিরিয়ে দেওয়ার জন্য মেসেজ পাঠায় তা হ্যান্ডেল করে"""
    chat_id = update.effective_chat.id
    
    # দেখুন ব্যবহারকারী কি কোনো নম্বর ফিরিয়ে দেওয়ার জন্য অপেক্ষা করছে?
    country_key = context.user_data.get('awaiting_return')

    if country_key:
        returned_number = update.message.text.strip()
        
        number_file = DATA_FILES[country_key]["number"]
        taken_file = DATA_FILES[country_key]["taken"]
        
        available_numbers = load_data(number_file)
        taken_numbers = load_data(taken_file)
        
        # নম্বরটি taken তালিকা থেকে সরান
        try:
            taken_numbers.remove(returned_number)
            available_numbers.insert(0, returned_number) # তালিকার প্রথমে আবার দিয়ে দিন
            
            save_data(taken_file, taken_numbers)
            save_data(number_file, available_numbers)
            
            del context.user_data['awaiting_return'] # স্টেট মুছে ফেলুন
            
            await update.message.reply_text(
                f"✅ সফল! **{country_key.upper()}** এর নম্বর `{returned_number}` তালিকায় ফিরিয়ে দেওয়া হয়েছে।",
                parse_mode='Markdown',
                reply_markup=get_action_menu(country_key)
            )

        except ValueError:
            await update.message.reply_text(
                f"❌ দুঃখিত, `{returned_number}` নম্বরটি **{country_key.upper()}** এর নেওয়া নম্বরের তালিকায় খুঁজে পাওয়া যায়নি।",
                parse_mode='Markdown',
                reply_markup=get_action_menu(country_key)
            )
        
        return

    # যদি কোনো স্টেট না থাকে, কিন্তু মেসেজ আসে
    await update.message.reply_text("বুঝেছি না। অন্য কোনো দেশের নম্বর ম্যানেজ করার জন্য /start টাইপ করুন।")


# --- ৬. মূল রান ফাংশন ---

def main():
    """প্রধান ফাংশন যা বট চালু করে"""
    logger.info("Starting bot application...")

    # অ্যাপ্লিকেশন ইনস্ট্যান্স তৈরি (এখানে Application ব্যবহার করা হয়েছে)
    application = Application.builder().token(BOT_TOKEN).build()

    # কমান্ড এবং মেসেজ হ্যান্ডলার যোগ করা
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(handle_button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_return_message))

    # যদি Render বা অন্য Webhook পরিবেশ হয়, তবে এটি ব্যবহার করুন
    if WEBHOOK_URL:
        logger.info(f"Running via Webhook. URL: {WEBHOOK_URL}")
        # Webhook সেট করুন:
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f'{WEBHOOK_URL}/{BOT_TOKEN}',
        )
    else:
        # লোকাল টেস্টিং বা পোলিং-এর জন্য
        logger.info("Running via Polling (Local Test Mode).")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    # গুরুত্বপূর্ণ: Render এর জন্য বট টোকেন এনভায়রনমেন্ট ভ্যারিয়েবল BOT_TOKEN এ সেট করতে হবে।
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN is not set. The bot cannot start.")
    elif not WEBHOOK_URL:
        logger.warning("⚠️ WEBHOOK_URL is not set. Assuming local polling mode.")
    
    main()


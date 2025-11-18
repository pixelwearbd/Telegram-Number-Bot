# File: number_manager_bot_webhook.py
# This code is an adaptation of the original bot to run using Webhooks
# on platforms like Render or Railway for 24/7 free hosting.

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.constants import ParseMode
import random
import logging
import traceback
import re
import os
import asyncio

# === লগিং সেটআপ ===
# ডিফল্টভাবে লগিং লেভেল সেট করা হয়েছে।
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# টেলিগ্রাম টোকেন ও ইউজার আইডি
BOT_TOKEN = "8374666904:AAFk5fQWDC_MpXXtzTAUruGLUMWsTF84ptk" # পরিবেশ ভেরিয়েবল থেকে টোকেন নিন
SUPPORT_USERNAME = '@kzishihab' # আপনার সাপোর্ট ইউজারের টেলিগ্রাম ইউজারনেম
ADMIN_USER_ID = 2035799771  # আপনার টেলিগ্রাম আইডি (সংখ্যা) এখানে বসান

# ফাইল কনফিগারেশন এবং দেশের তালিকা
# এই ডিকশনারির 'file_base' গুলো হলো আপনার .txt ফাইলের নাম, যেখানে ডট (.) নেই।
COUNTRIES = {
    "Sudan": {"file_base": "sudan", "emoji": "🇸🇩"},
    "Venezuela": {"file_base": "venezuela", "emoji": "🇻🇪"},
    "Iran": {"file_base": "iran", "emoji": "🇮🇷"},
    "Uganda": {"file_base": "uganda", "emoji": "🇺🇬"},
    # আপনি আরো দেশ যোগ করতে পারেন
}

# কলব্যাক ডেটা কনস্ট্যান্ট
CALLBACK_SELECT_COUNTRY_GET = "select_country_get"
CALLBACK_SELECT_COUNTRY_TAKE = "select_country_take"
CALLBACK_BACK_TO_COUNTRY = "back_to_country"

CALLBACK_SHOW_FIRST_NUMBER = "show_first_num"
CALLBACK_SHOW_ALL_NUMBERS = "next_available"
CALLBACK_NEXT_TAKEN = "next_taken"
CALLBACK_ACTION_DELETE = "delete_action"

# ফাইল রিড/রাইট ফাংশন
# এই ফাংশনগুলি ফাইল থেকে নম্বরগুলি লোড এবং সেভ করার জন্য ব্যবহৃত হয়।
def load_numbers(file_base, list_type):
    """'number' বা 'taken' তালিকা থেকে নম্বর লোড করে।"""
    filename = f"{file_base}_{list_type}.txt"
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            # প্রতিটি লাইন থেকে খালি স্থান মুছে একটি তালিকা তৈরি করে
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        # ফাইল না পাওয়া গেলে একটি খালি তালিকা ফেরত দেয়
        return []
    except Exception as e:
        logging.error(f"Error loading {filename}: {e}")
        return []

def save_numbers(file_base, list_type, numbers):
    """'number' বা 'taken' তালিকা সেভ করে।"""
    filename = f"{file_base}_{list_type}.txt"
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            for number in numbers:
                f.write(f"{number}\n")
        return True
    except Exception as e:
        logging.error(f"Error saving {filename}: {e}")
        return False

# === MarkdownV2 এস্কেপ ফাংশন (গুরুত্বপূর্ণ ফিক্স) ===
# এটি MarkdownV2 ত্রুটি (Can't parse entities) প্রতিরোধ করার জন্য অত্যন্ত প্রয়োজনীয়।
def escape_markdown_v2(text):
    """Telegram MarkdownV2 এ বিশেষ অক্ষরগুলিকে এস্কেপ করে।"""
    # Escaping characters: _, *, [, ], (, ), ~, `, >, #, +, -, =, |, {, }, ., !
    # এই তালিকার প্রতিটি অক্ষরকে \ দিয়ে এস্কেপ করতে হবে।
    special_chars = r'_*[]()~`>#+-=|{}.!'
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

# === ইউটিলিটি ফাংশন ===

def build_country_menu(action_type):
    """দেশ নির্বাচনের জন্য ইনলাইন কিবোর্ড তৈরি করে।"""
    keyboard = []
    # প্রতি সারি দুটি করে দেশ বাটন
    row = []
    for country, data in COUNTRIES.items():
        # দেশ এবং ইমোজি সহ বাটন
        button_text = f"{data['emoji']} {country}"
        # কলব্যাক ডেটা: অ্যাকশন_টাইপ|কান্ট্রি_নাম
        callback_data = f"{action_type}|{country}"
        row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

def build_country_action_menu(country_name):
    """একটি নির্দিষ্ট দেশের জন্য নম্বর নেওয়া ও ফেরত দেওয়ার বাটন তৈরি করে।"""
    file_base = COUNTRIES[country_name]['file_base']
    
    # বর্তমান নম্বর ও ব্যবহৃত নম্বরের তালিকা
    available_count = len(load_numbers(file_base, 'number'))
    taken_count = len(load_numbers(file_base, 'taken'))
    
    # বাটনগুলি তৈরি করা
    get_num_button = InlineKeyboardButton(
        f"নম্বর নিন ({available_count})", 
        callback_data=f"{CALLBACK_SELECT_COUNTRY_GET}|{country_name}"
    )
    return_num_button = InlineKeyboardButton(
        f"নম্বর ফিরিয়ে দিন ({taken_count})", 
        callback_data=f"{CALLBACK_SELECT_COUNTRY_TAKE}|{country_name}"
    )
    change_country_button = InlineKeyboardButton(
        "অন্য দেশ নির্বাচন করুন", 
        callback_data="start_menu" # এটা মেনুতে ফিরে যাবে
    )
    
    keyboard = [
        [get_num_button, return_num_button],
        [change_country_button]
    ]
    
    return InlineKeyboardMarkup(keyboard)

def build_taken_numbers_menu(country_name, start_index=0):
    """নেওয়া নম্বরগুলি দেখানোর জন্য মেনু তৈরি করে (অ্যাডমিন)।"""
    file_base = COUNTRIES[country_name]['file_base']
    taken_numbers = load_numbers(file_base, 'taken')
    
    if not taken_numbers:
        return None, "🚫 বর্তমানে কোনো নম্বর নেওয়া নেই\."
    
    # 5টি করে নম্বর দেখান
    numbers_per_page = 5
    end_index = min(start_index + numbers_per_page, len(taken_numbers))
    
    current_page_numbers = taken_numbers[start_index:end_index]
    
    # মেসেজ টেক্সট তৈরি
    message_text = f"*{escape_markdown_v2(country_name)}* - বর্তমানে ব্যবহৃত নম্বরসমূহ ({start_index + 1}-{end_index} / {len(taken_numbers)})\n"
    message_text += "```\n"
    for num in current_page_numbers:
        message_text += f"{num}\n"
    message_text += "```"

    # নম্বরগুলির জন্য ইনলাইন বাটন (এক্সেস কন্ট্রোল)
    number_buttons = []
    for num in current_page_numbers:
        # প্রতিটি নম্বরের জন্য একটি বাটন
        button_text = f"❌ ডিলিট: {num}"
        # কলব্যাক ডেটা: CALLBACK_ACTION_DELETE|কান্ট্রি|নম্বর
        callback_data = f"{CALLBACK_ACTION_DELETE}|{country_name}|{num}"
        number_buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
    # নেভিগেশন বাটন
    nav_buttons = []
    if start_index > 0:
        # কলব্যাক ডেটা: CALLBACK_NEXT_TAKEN|কান্ট্রি|নতুন_স্টার্ট_ইনডেক্স
        nav_buttons.append(InlineKeyboardButton("⬅️ পূর্বের", callback_data=f"{CALLBACK_NEXT_TAKEN}|{country_name}|{start_index - numbers_per_page}"))
    
    if end_index < len(taken_numbers):
        nav_buttons.append(InlineKeyboardButton("পরের ➡️", callback_data=f"{CALLBACK_NEXT_TAKEN}|{country_name}|{end_index}"))
        
    # মূল বাটন
    back_button = InlineKeyboardButton("⬅️ ফিরে যান", callback_data=f"{CALLBACK_BACK_TO_COUNTRY}|{country_name}")
    
    keyboard = number_buttons + [nav_buttons] + [[back_button]]
    
    return InlineKeyboardMarkup(keyboard), message_text

# === হ্যান্ডলার ফাংশনসমূহ ===

async def start_command(update: Update, context):
    """/start কমান্ড হ্যান্ডেল করে।"""
    # MarkdownV2 এস্কেপ করা মেসেজ টেক্সট
    escaped_support_user = escape_markdown_v2(SUPPORT_USERNAME)
    welcome_text = (
        "👋 স্বাগতম\! এই বটটি দিয়ে আপনি সক্রিয় নম্বরগুলি পরিচালনা করতে পারবেন\।"
        f"\n\n⚙️ কোনো সমস্যা হলে {escaped_support_user} এর সাথে যোগাযোগ করুন\।"
        "\n\nনিচের বাটন বা /start কমান্ড ব্যবহার করে শুরু করুন\।"
    )
    
    # এডমিন ইউজারকে অন্য মেনু দেখানো হবে
    if update.effective_user.id == ADMIN_USER_ID:
        menu = build_country_menu(CALLBACK_BACK_TO_COUNTRY)
        await update.effective_message.reply_text(
            f"*{welcome_text}*",
            reply_markup=menu,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        # সাধারণ ইউজারের জন্য অ্যাক্টিভ নম্বর বাটন
        active_numbers_button = InlineKeyboardButton(
            "Active Number", 
            callback_data=CALLBACK_SELECT_COUNTRY_GET # সরাসরি নম্বর নেওয়ার মেনুতে যায়
        )
        keyboard = InlineKeyboardMarkup([[active_numbers_button]])
        await update.effective_message.reply_text(
            f"*{welcome_text}*",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def handle_admin_action_menu(update: Update, context):
    """অ্যাডমিনের জন্য দেশ নির্বাচনের মেনু দেখায়।"""
    if update.effective_user.id != ADMIN_USER_ID:
        return # শুধু অ্যাডমিনের জন্য
        
    menu = build_country_menu(CALLBACK_BACK_TO_COUNTRY)
    # মেসেজ সম্পাদনা করুন
    await update.callback_query.edit_message_text(
        "⚙️ কোন দেশের নম্বরগুলি পরিচালনা করতে চান তা নির্বাচন করুন\:",
        reply_markup=menu,
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def handle_country_selection(update: Update, context):
    """যখন ব্যবহারকারী একটি দেশ নির্বাচন করে।"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('|')
    action = data[0]
    country_name = data[1]
    
    # MarkdownV2 এস্কেপ করা কান্ট্রি নাম
    escaped_country_name = escape_markdown_v2(country_name)

    if action == CALLBACK_SELECT_COUNTRY_GET:
        # সাধারণ ব্যবহারকারী নম্বর নিতে চায়
        file_base = COUNTRIES[country_name]['file_base']
        number_list = load_numbers(file_base, 'number')
        taken_list = load_numbers(file_base, 'taken')
        
        available_count = len(number_list)
        taken_count = len(taken_list)
        
        # দেশ নির্বাচন মেনু
        country_menu = build_country_menu(CALLBACK_SELECT_COUNTRY_GET)
        
        if available_count > 0:
            # নম্বর আছে, একটি নম্বর দিন
            number_to_send = random.choice(number_list)
            
            # নম্বর তালিকা থেকে সরাও এবং taken এ যোগ করো
            number_list.remove(number_to_send)
            taken_list.append(number_to_send)
            
            # ফাইল সেভ করো
            save_numbers(file_base, 'number', number_list)
            save_numbers(file_base, 'taken', taken_list)
            
            # এস্কেপ করা মেসেজ
            message_text = (
                f"✅ সফল\! আপনার জন্য *{escaped_country_name}* এর একটি নম্বর\:\n"
                f"```\n{escape_markdown_v2(number_to_send)}\n```\n"
                f"\nবর্তমানে উপলব্ধ\:\n"
                f"• নম্বর সংখ্যা\:\t `{available_count - 1}`\n"
                f"• ব্যবহৃত সংখ্যা\:\t `{taken_count + 1}`"
            )

            # নম্বর দেওয়ার পর আবার দেশ নির্বাচনের মেনু দেখাও
            await query.edit_message_text(
                message_text,
                reply_markup=country_menu,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        else:
            # নম্বর নেই
            message_text = (
                f"⚠️ দুঃখিত, বর্তমানে *{escaped_country_name}* এর কোনো নম্বর উপলব্ধ নেই\।"
                "\n\nঅন্য কোনো দেশের নম্বর নির্বাচন করুন\।"
            )
            await query.edit_message_text(
                message_text,
                reply_markup=country_menu,
                parse_mode=ParseMode.MARKDOWN_V2
            )

    elif action == CALLBACK_SELECT_COUNTRY_TAKE:
        # ব্যবহারকারী নম্বর ফিরিয়ে দিতে চায় (শুধুমাত্র অ্যাডমিনের জন্য)
        if query.from_user.id != ADMIN_USER_ID:
            await query.answer("🚫 আপনি এই অ্যাকশনের জন্য অনুমোদিত নন\।")
            return

        menu, message_text = build_taken_numbers_menu(country_name, start_index=0)
        
        # মেনু আপডেট করুন
        await query.edit_message_text(
            message_text,
            reply_markup=menu,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    elif action == CALLBACK_BACK_TO_COUNTRY:
        # অ্যাডমিন মেনু থেকে একটি দেশ নির্বাচন করেছে
        if query.from_user.id != ADMIN_USER_ID:
            await query.answer("🚫 আপনি এই অ্যাকশনের জন্য অনুমোদিত নন\।")
            return
            
        menu = build_country_action_menu(country_name)
        file_base = COUNTRIES[country_name]['file_base']
        
        available_count = len(load_numbers(file_base, 'number'))
        taken_count = len(load_numbers(file_base, 'taken'))
        
        # এস্কেপ করা মেসেজ
        message_text = (
            f"*{escaped_country_name}* পরিচালনা\n"
            f"\nউপলব্ধ নম্বর\:\t `{available_count}`"
            f"\nব্যবহৃত নম্বর\:\t `{taken_count}`"
            f"\n\nকোন কাজটি করতে চান, নির্বাচন করুন\:"
        )

        await query.edit_message_text(
            message_text,
            reply_markup=menu,
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def handle_taken_number_navigation(update: Update, context):
    """নেওয়া নম্বর মেনুতে নেভিগেশন হ্যান্ডেল করে (পরের পাতা/পূর্বের পাতা)।"""
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_USER_ID:
        return

    data = query.data.split('|')
    country_name = data[1]
    start_index = int(data[2])

    menu, message_text = build_taken_numbers_menu(country_name, start_index)
    
    if menu:
        await query.edit_message_text(
            message_text,
            reply_markup=menu,
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def handle_delete_action(update: Update, context):
    """নেওয়া নম্বর তালিকা থেকে একটি নম্বর ডিলিট করে দেয় (অ্যাডমিন)।"""
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_USER_ID:
        return

    data = query.data.split('|')
    country_name = data[1]
    number_to_act = data[2] # নম্বর যা ডিলিট করতে হবে

    file_base = COUNTRIES[country_name]['file_base']
    taken_list = load_numbers(file_base, 'taken')
    number_list = load_numbers(file_base, 'number') # নম্বরটিকে এখানেও যোগ করতে হবে

    message_text = ""
    
    if number_to_act in taken_list:
        # taken তালিকা থেকে নম্বর সরাও
        taken_list.remove(number_to_act)
        
        # মূল নম্বর তালিকায় নম্বরটি ফিরিয়ে দিন
        number_list.append(number_to_act)
        
        # ফাইল সেভ করো
        save_numbers(file_base, 'taken', taken_list)
        save_numbers(file_base, 'number', number_list)

        # এস্কেপ করা মেসেজ
        escaped_country_name = escape_markdown_v2(country_name)
        escaped_number = escape_markdown_v2(number_to_act)
        
        message_text = f"✅ সফল\! *{escaped_country_name}* এর নম্বর `{escaped_number}` তালিকা থেকে ডিলিট করা হয়েছে ও উপলব্ধ নম্বরের তালিকায় ফিরিয়ে দেওয়া হয়েছে\।"
    else:
        # এস্কেপ করা মেসেজ
        escaped_number = escape_markdown_v2(number_to_act)
        message_text = f"⚠️ দুঃখিত, নম্বর `{escaped_number}` ইতিমধ্যে তালিকায় নেই\।"

    # নতুন মেনু এবং মেসেজ দেখান
    menu, _ = build_taken_numbers_menu(country_name, start_index=0)
    
    if menu:
        await query.edit_message_text(
            message_text,
            reply_markup=menu,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        # যদি কোনো নম্বর না থাকে
        menu = build_country_action_menu(country_name)
        available_count = len(number_list)
        taken_count = len(taken_list)
        
        # এস্কেপ করা মেসেজ
        escaped_country_name = escape_markdown_v2(country_name)
        message_text = (
            f"*{escaped_country_name}* পরিচালনা\n"
            f"\nউপলব্ধ নম্বর\:\t `{available_count}`"
            f"\nব্যবহৃত নম্বর\:\t `{taken_count}`"
            f"\n\nকোন কাজটি করতে চান, নির্বাচন করুন\:"
        )

        await query.edit_message_text(
            message_text,
            reply_markup=menu,
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def handle_fallback(update: Update, context):
    """আননোন মেসেজ/কমান্ড হ্যান্ডেল করে।"""
    # MarkdownV2 এস্কেপ করা মেসেজ টেক্সট
    escaped_support_user = escape_markdown_v2(SUPPORT_USERNAME)
    fallback_message = (
        "বুঝেছি না\। অন্য কোনো দেশের নম্বর ম্যানেজ করার জন্য `/start` টাইপ করুন\।"
        f"\n\nঅথবা সাহায্যের জন্য {escaped_support_user} এ যোগাযোগ করুন\।"
    )
    if update.effective_message:
        await update.effective_message.reply_text(
            fallback_message,
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def error_handler(update: Update, context):
    """সব ধরনের ত্রুটি হ্যান্ডেল করে।"""
    logging.error("An error occurred: %s", context.error)
    traceback.print_exc() # লগ-এ বিস্তারিত ত্রুটি দেখানোর জন্য

    # অ্যাডমিনকে ত্রুটি বার্তা পাঠান
    if update and update.effective_chat:
        chat_id = update.effective_chat.id
        escaped_support_user = escape_markdown_v2(SUPPORT_USERNAME)
        error_message = (
            "⚠️ একটি অভ্যন্তরীণ ত্রুটি ঘটেছে\।"
            f"\n\nদয়া করে {escaped_support_user} এ যোগাযোগ করুন\।"
            f"\n\nত্রুটি কোড: `{escape_markdown_v2(str(context.error))}`"
        )
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=error_message,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            logging.error(f"Failed to send error message to user: {e}")

# === মেইন ফাংশন এবং ওয়েবহুক সেটআপ ===

def main():
    """বট অ্যাপ্লিকেশন তৈরি করে ও শুরু করে।"""
    
    # টোকেন পরিবেশ ভেরিয়েবল বা ডিফল্ট মান থেকে নেওয়া হচ্ছে
    token = os.environ.get("BOT_TOKEN")
    if not token:
        logging.error("BOT_TOKEN is not set in environment variables.")
        # এখানে ডিফল্ট টোকেন ব্যবহার করা হচ্ছে যদি পরিবেশ ভেরিয়েবলে না থাকে
        token = "আপনার_বট_টোকেন_এখানে_দিন"

    # অ্যাপ্লিকেশন তৈরি
    application = ApplicationBuilder().token(token).build()

    # কমান্ড এবং হ্যান্ডলার যোগ করুন
    application.add_handler(CommandHandler("start", start_command))
    
    # কলব্যাক ক্যোয়ারী হ্যান্ডলার
    application.add_handler(CallbackQueryHandler(handle_admin_action_menu, pattern="^start_menu$"))
    
    # দেশ নির্বাচন এবং অ্যাডমিন অ্যাকশন হ্যান্ডলিং
    # CALLBACK_SELECT_COUNTRY_GET|Country
    # CALLBACK_SELECT_COUNTRY_TAKE|Country
    # CALLBACK_BACK_TO_COUNTRY|Country
    country_selection_pattern = f"^(?:{CALLBACK_SELECT_COUNTRY_GET}|{CALLBACK_SELECT_COUNTRY_TAKE}|{CALLBACK_BACK_TO_COUNTRY})\\|"
    application.add_handler(CallbackQueryHandler(handle_country_selection, pattern=country_selection_pattern))
    
    # অ্যাডমিন নেওয়া নম্বর নেভিগেশন
    # CALLBACK_NEXT_TAKEN|Country|Index
    application.add_handler(CallbackQueryHandler(handle_taken_number_navigation, pattern=f"^{CALLBACK_NEXT_TAKEN}\\|"))
    
    # অ্যাডমিন নম্বর ডিলিট অ্যাকশন
    # CALLBACK_ACTION_DELETE|Country|Number
    application.add_handler(CallbackQueryHandler(handle_delete_action, pattern=f"^{CALLBACK_ACTION_DELETE}\\|"))
    
    # ফলব্যাক হ্যান্ডলার
    application.add_handler(MessageHandler(filters.ALL, handle_fallback))
    
    # ত্রুটি হ্যান্ডলার
    application.add_error_handler(error_handler)

    # ওয়েবহুক সেটআপ
    # Render পরিবেশ থেকে URL ও পোর্ট স্বয়ংক্রিয়ভাবে নেওয়া হবে
    PORT = int(os.environ.get('PORT', '8443'))
    # Render URL ফরম্যাট: [Service_ID].onrender.com
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL', 'https://your-service-name.onrender.com')

    # ওয়েবহুক সেট করুন এবং লিসেনিং শুরু করুন
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="",
        webhook_url=WEBHOOK_URL
    )

if __name__ == '__main__':
    main()

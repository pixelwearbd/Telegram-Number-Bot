# File: number_manager_bot_webhook.py
# This script integrates the user's original Polling logic with necessary Webhook configuration for Render.

import logging
import traceback
import re
import os 
from telegram.ext import (
    Application, # Changed from ApplicationBuilder for current best practice
    CommandHandler, 
    CallbackQueryHandler,
    MessageHandler, 
    filters 
)
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, Update, constants

# --- ১. কনফিগারেশন এবং লগিং ---

# লগিং সেটআপ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- অ্যাডমিন আইডি সেটআপ (পরিবর্তন করুন) ---
# IMPORTANT: আপনার টেলিগ্রাম User ID (সংখ্যা) এখানে দিন। এটি ছাড়া /addnumber কাজ করবে না।
# User ID পেতে @userinfobot ব্যবহার করুন।
ADMIN_USER_ID = 2035799771 # <--- আপনার আসল ইউজার ID এখানে বসান

# আপনার টেলিগ্রাম টোকেনটি এখানে বসান (অথবা এনভায়রনমেন্ট ভ্যারিয়েবল থেকে লোড করুন)
TOKEN = os.environ.get('BOT_TOKEN', '8374666904:AAFk5fQWDC_MpXXtzTAUruGLUMWsTF84ptk') # Fallback to hardcoded token if ENV not set
SUPPORT_USERNAME = '@kzishihab'

# Render-এর জন্য PORT এবং WEBHOOK_URL
PORT = int(os.environ.get('PORT', 8080))
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

# কান্ট্রি কনফিগারেশন এবং ফাইল নাম
COUNTRIES = {
    "Sudan": {"file_base": "sudan", "emoji": "🇸🇩"},
    "Venezuela": {"file_base": "venezuela", "emoji": "🇻🇪"},
    "Iran": {"file_base": "iran", "emoji": "🇮🇷"},
    "Uganda": {"file_base": "uganda", "emoji": "🇺🇬"},
}

# বাটন ডেটার কনস্ট্যান্ট
CALLBACK_SELECT_COUNTRY_GET = "select_country_get:"
CALLBACK_SELECT_COUNTRY_TAKEN = "select_country_taken:"
CALLBACK_SELECT_COUNTRY_ADD = "select_country_add:" # New: For adding numbers
CALLBACK_BACK_TO_COUNTRY = "back_to_country"
CALLBACK_SHOW_FIRST_NUMBER = "show_first_num:"
CALLBACK_NEXT_AVAILABLE = "next_available:"
CALLBACK_NEXT_TAKEN = "next_taken:" 
CALLBACK_ACTION_DELETE = "delete_action:"

# --- রিপ্লাই কীবোর্ড (স্থায়ী বাটন) ---
REPLY_KEYBOARD_GET = "📲 Get Number"
REPLY_KEYBOARD_ACTIVE = "📊 Active Number"

REPLY_KEYBOARD = [
    [REPLY_KEYBOARD_GET, REPLY_KEYBOARD_ACTIVE],
]
REPLY_MARKUP = ReplyKeyboardMarkup(REPLY_KEYBOARD, resize_keyboard=True, one_time_keyboard=False)

# --- ইউটিলিটি ফাংশন ---

def check_admin(user_id):
    """চেক করে ইউজার অ্যাডমিন কিনা"""
    return user_id == ADMIN_USER_ID

def escape_markdown_v2(text):
    """
    MarkdownV2 ফরমেটে সংরক্ষিত অক্ষরগুলিকে এস্কেপ করে। 
    'Can't parse entities' ত্রুটিটি এড়াতে এটি আরও শক্তিশালী করা হয়েছে।
    """
    # নিম্নলিখিত অক্ষরগুলি MarkdownV2-এ সংরক্ষিত এবং এস্কেপ করতে হবে:
    # _ * [ ] ( ) ~ ` > # + - = | { } . !
    
    # সব সংরক্ষিত অক্ষরগুলির জন্য একটি সাধারণ রেজেক্স
    # এটি * এবং ` কেও এস্কেপ করবে, তাই বোল্ড/কোড ফরম্যাটিং ব্যবহার করতে চাইলে, 
    # আপনাকে escape_markdown_v2-এ পাঠানোর আগে বোল্ড/কোড ম্যানুয়ালি যোগ করতে হবে না।
    # বরং, বোল্ড/কোড যোগ করার পরে escape_markdown_v2 কল করুন।
    # অথবা, কোডটি শুধু টেক্সট এস্কেপ করার জন্য ব্যবহার করুন এবং মেসেজে বোল্ড যোগ করুন।
    
    # আমরা এখানে শুধু সেই অক্ষরগুলিকে এস্কেপ করব যা অন্য কাজে লাগে না, যেমন . ! - + = ইত্যাদি।
    # বোল্ড/কোড ফরম্যাটিং এর জন্য * এবং ` কে ছাড় দেওয়া যেতে পারে।
    
    # সংরক্ষিত অক্ষরের তালিকা: _ * [ ] ( ) ~ ` > # + - = | { } . !
    # আমরা শুধুমাত্র সেইগুলি এস্কেপ করব যা ডেকোরেশন নয়: [ ] ( ) ~ > # + - = | { } . ! \
    
    # \ (Backslash) অবশ্যই প্রথমে এস্কেপ করতে হবে
    text = text.replace('\\', '\\\\')
    
    # ফিক্স: এখন শুধু ডেকোরেশন নয়, এমন চিহ্নগুলোকেই এস্কেপ করা হচ্ছে
    text = re.sub(r'([\[\]\(\)~>#\+\-=|\{\}\.!])', r'\\\1', text)
    
    # _ এবং * কে এস্কেপ করতে হবে যদি না এটি ফরম্যাটিং এর জন্য ব্যবহৃত হয়।
    # যেহেতু আমাদের টেক্সটে ফরম্যাটিং প্রায়শই দরকার, তাই এখানে শুধু আন্ডারস্কোর এস্কেপ করা হলো।
    text = text.sub(r'_', r'\_')
    
    return text

def load_numbers(file_base, is_taken_list=False):
    """নির্দিষ্ট ফাইল থেকে নম্বর লোড করে। যদি ফাইল না থাকে, তবে সেটি তৈরি করে।"""
    suffix = "_taken" if is_taken_list else "_number"
    filename = f"{file_base}{suffix}.txt"
    try:
        if not os.path.exists(filename):
            # ফাইল না থাকলে, খালি ফাইল তৈরি করা হলো (FileNotFoundError ফিক্স)
            with open(filename, 'w', encoding='utf-8') as f:
                pass
        
        with open(filename, 'r', encoding='utf-8') as f:
            numbers = [line.strip() for line in f if line.strip()]
        return numbers
    except Exception as e:
        logger.error(f"Error loading {filename}: {e}")
        return []

def save_numbers(file_base, numbers_list, is_taken_list=False):
    """নির্দিষ্ট ফাইলে নম্বর সেভ করে।"""
    suffix = "_taken" if is_taken_list else "_number"
    filename = f"{file_base}{suffix}.txt"
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(numbers_list) + '\n')
        return True
    except Exception as e:
        logger.error(f"Error saving to {filename}: {e}")
        return False

# --- মেনু তৈরি ফাংশন ---

def get_country_selection_keyboard(callback_prefix):
    """কান্ট্রি সিলেকশন মেনু তৈরি করে।"""
    keyboard = []
    current_row = []
    
    for name, data in COUNTRIES.items():
        button = InlineKeyboardButton(f"{data['emoji']} {name}", callback_data=f"{callback_prefix}{data['file_base']}")
        current_row.append(button)
        if len(current_row) == 2:
            keyboard.append(current_row)
            current_row = []
    if current_row:
        keyboard.append(current_row)
        
    return InlineKeyboardMarkup(keyboard)

# --- কীবোর্ড তৈরি ফাংশন (নম্বর দেখানোর সময়) ---

def get_number_options_keyboard(file_base, current_index, total_count, is_taken):
    """Take/Delete বাটন সহ নম্বর দেখানোর জন্য কীবোর্ড তৈরি করে।"""
    
    next_index = current_index + 1
    next_index_data = next_index if next_index < total_count else 0 
    
    if is_taken:
        # Active/Taken List এর জন্য বাটন: Next Number এবং Delete Permanently
        keyboard = [[
            InlineKeyboardButton("➡️ Next Number", callback_data=f"{CALLBACK_NEXT_TAKEN}{file_base}|{next_index_data}"),
            InlineKeyboardButton("❌ Delete Permanently", callback_data=f"{CALLBACK_ACTION_DELETE}{file_base}|{current_index}|taken")
        ]]
    else:
        # Available Number List এর জন্য বাটন: Next Number (Take) এবং Delete Number
        keyboard = [[
            InlineKeyboardButton("➡️ Next Number (Take)", callback_data=f"{CALLBACK_NEXT_AVAILABLE}{file_base}|{next_index_data}|{current_index}"), # next_index_data is used here instead of next_index
            InlineKeyboardButton("❌ Delete Number", callback_data=f"{CALLBACK_ACTION_DELETE}{file_base}|{current_index}|available") 
        ]]

    # "Back to Countries" বাটন
    keyboard.append([InlineKeyboardButton("⬅️ Back to Countries", callback_data=CALLBACK_BACK_TO_COUNTRY)])
    
    return InlineKeyboardMarkup(keyboard)

# --- টেক্সট তৈরি ফাংশন ---

def get_list_end_message(file_base, is_taken):
    """লিস্ট শেষ হলে দেখানো বার্তা তৈরি করে।"""
    country_name = next(name for name, data in COUNTRIES.items() if data['file_base'] == file_base)
    list_type = "Available" if not is_taken else "Active/Taken"
    
    # এখন raw_text এ কোনো \ ব্যবহার করা হয়নি, escape_markdown_v2 ফাংশন সব এস্কেপ করবে
    raw_text = (
        f"🚨 **{country_name}** {list_type} numbers are on countdown. "
        f"List ended at the last number. "
        f"Please wait and start from 1st number."
    )
    return escape_markdown_v2(raw_text)

# --- কমান্ড হ্যান্ডেলার ---

async def start(update: Update, context):
    """/start কমান্ড এবং রিপ্লাই কীবোর্ড দেখায়।"""
    # এখন raw_text এ কোনো \ ব্যবহার করা হয়নি
    raw_text = 'Muri khao ! Use the buttons below or command /number to start.'
    text = escape_markdown_v2(raw_text)
    await update.message.reply_text(
        text,
        reply_markup=REPLY_MARKUP,
        parse_mode=constants.ParseMode.MARKDOWN_V2
    )

async def help_command(update: Update, context):
    """/help কমান্ড এবং সাপোর্ট ইউজারনেম দেখায়।"""
    # এখন raw_text এ কোনো \ ব্যবহার করা হয়নি
    raw_text = (
        "Welcome to the Number Bot! Here are the available commands:\n\n"
        "• /number - Start the process to get a number\n"
        "• /taken - See the numbers you have taken\n"
        "• /start - Show the welcome message and main keyboard.\n"
        f"• /addnumber - [ADMIN ONLY] Add new numbers to a country list.\n"
        "\n*Support:*\n"
        f"• For any issue, contact the owner: {SUPPORT_USERNAME}"
    )
    text = escape_markdown_v2(raw_text).replace(r'\*', '*') # * (asterisk) কে ম্যানুয়ালি বাদ রাখা হলো, কারণ এটি বোল্ডের জন্য ব্যবহৃত হবে
    
    # যেহেতু escape_markdown_v2 এর ভেতরে সব Escaping করা হয়েছে, তাই এখন আমরা বোল্ড ফরম্যাটিং এর জন্য * ব্যবহার করতে পারব
    text = text.replace(escape_markdown_v2("[ADMIN ONLY]"), "[ADMIN ONLY]") # স্কোয়ার ব্র্যাকেট এস্কেপ না করতে চাইলে
    text = text.replace(escape_markdown_v2(SUPPORT_USERNAME), SUPPORT_USERNAME) # ইউজারনেম এস্কেপ না করতে চাইলে

    await update.message.reply_text(
        text,
        parse_mode=constants.ParseMode.MARKDOWN_V2
    )

async def handle_get_number_command(update: Update, context):
    """'/number' বাটন ক্লিক হলে কান্ট্রি সিলেকশন শুরু করে।"""
    raw_text = "Select a Country to get an available number:"
    text = escape_markdown_v2(raw_text)
    reply_markup = get_country_selection_keyboard(CALLBACK_SELECT_COUNTRY_GET)
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN_V2)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN_V2)

async def handle_taken_command(update: Update, context):
    """'/taken' বাটন ক্লিক হলে কান্ট্রি সিলেকশন শুরু করে।"""
    raw_text = "Select a Country to see your active (taken) numbers:"
    text = escape_markdown_v2(raw_text)
    reply_markup = get_country_selection_keyboard(CALLBACK_SELECT_COUNTRY_TAKEN)
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN_V2)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN_V2)
        
async def handle_reply_keyboard_buttons(update: Update, context):
    """রিপ্লাই কীবোর্ডের 'Get Number' এবং 'Active Number' বাটনগুলি হ্যান্ডেল করে।"""
    text = update.message.text
    
    if text == REPLY_KEYBOARD_GET:
        await handle_get_number_command(update, context)
    elif text == REPLY_KEYBOARD_ACTIVE:
        await handle_taken_command(update, context)


# --- নতুন অ্যাডমিন ফাংশন: নম্বর যোগ করা ---

async def add_number_command(update: Update, context):
    """[ADMIN ONLY] নম্বর যোগ করার প্রক্রিয়া শুরু করে।"""
    if not check_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access Denied. Only the bot admin can use this command.")
        return

    raw_text = "ADMIN: Select the Country where you want to add new numbers:"
    text = escape_markdown_v2(raw_text)
    reply_markup = get_country_selection_keyboard(CALLBACK_SELECT_COUNTRY_ADD)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN_V2)

async def select_country_for_add(query: Update.callback_query, context):
    """অ্যাডমিনের নির্বাচিত দেশকে user_data-তে সেভ করে নম্বর পাঠানোর জন্য অনুরোধ করে।"""
    file_base = query.data.replace(CALLBACK_SELECT_COUNTRY_ADD, "")
    country_name = next(name for name, data in COUNTRIES.items() if data['file_base'] == file_base)
    
    context.user_data['awaiting_add'] = file_base
    
    raw_text = (
        f"✅ Country **{country_name}** selected. "
        f"Now, send the list of numbers you want to add. "
        f"Each number must be on a new line."
    )
    # * এবং ** বোল্ডের জন্য ব্যবহার করা হয়েছে, escape_markdown_v2 তে এগুলো এস্কেপ না করার জন্য আমরা replace ব্যবহার করতে পারি
    text = escape_markdown_v2(raw_text).replace(r'\*', '*') 

    await query.edit_message_text(text, parse_mode=constants.ParseMode.MARKDOWN_V2)

async def handle_add_number_message(update: Update, context):
    """অ্যাডমিনের পাঠানো নম্বরগুলি নির্দিষ্ট ফাইলে সেভ করে।"""
    if not check_admin(update.effective_user.id):
        # যদি অ্যাডমিন না হয়, তবে এই মেসেজটি উপেক্ষা করা হবে বা অন্য হ্যান্ডেলারে যাবে
        return
        
    file_base = context.user_data.get('awaiting_add')

    if file_base:
        country_name = next(name for name, data in COUNTRIES.items() if data['file_base'] == file_base)
        new_numbers_text = update.message.text.strip()
        
        # নতুন নম্বরগুলি লাইন ব্রেক দিয়ে আলাদা করা হলো
        new_numbers_list = [n.strip() for n in new_numbers_text.split('\n') if n.strip()]
        
        if not new_numbers_list:
            await update.message.reply_text("❌ No valid numbers detected. Please send numbers, one per line.")
            return

        # বর্তমান নম্বর লোড করা
        available_numbers = load_numbers(file_base, is_taken_list=False)
        available_numbers.extend(new_numbers_list)
        
        # ফাইলে সেভ করা
        if save_numbers(file_base, available_numbers, is_taken_list=False):
            raw_text = (
                f"🎉 **SUCCESS!** {len(new_numbers_list)} new numbers have been added to **{country_name}** list."
                f"\nTotal available numbers now: {len(available_numbers)}."
            )
            text = escape_markdown_v2(raw_text).replace(r'\*', '*') 
            await update.message.reply_text(text, parse_mode=constants.ParseMode.MARKDOWN_V2)
        else:
            await update.message.reply_text("❌ ERROR: Failed to save numbers to file.")
        
        # স্টেট ক্লিয়ার করা
        del context.user_data['awaiting_add']
        
        return

    # যদি user_data-তে 'awaiting_add' না থাকে, তবে এটি সাধারণ মেসেজ হিসেবে বিবেচিত হবে।


# --- মাল্টি-স্টেপ হ্যান্ডেলার ---

async def handle_country_selection(query, file_base, is_taken_selection):
    """
    কান্ট্রি সিলেক্ট হলে মধ্যবর্তী স্ক্রিন দেখায়:
    - মোট সংখ্যা দেখাবে।
    - 'Get Number' বাটন দেখাবে, যা নম্বর দেখানো শুরু করবে।
    """
    
    numbers_list = load_numbers(file_base, is_taken_selection)
    total_count = len(numbers_list)
    country_data = next(data for name, data in COUNTRIES.items() if data['file_base'] == file_base)
    country_name = next(name for name, data in COUNTRIES.items() if data['file_base'] == file_base)
    
    list_type = "Available" if not is_taken_selection else "Active/Taken"
    
    if total_count == 0:
        # কোনো নম্বর না থাকলে
        raw_text = f"{country_data['emoji']} **{country_name}** - No {list_type} numbers available."
        keyboard = [[InlineKeyboardButton("⬅️ Back to Countries", callback_data=CALLBACK_BACK_TO_COUNTRY)]]
        text = escape_markdown_v2(raw_text).replace(r'\*', '*')
        await query.edit_message_text(text, parse_mode=constants.ParseMode.MARKDOWN_V2, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # --- মধ্যবর্তী স্ক্রিনের মেসেজ (মোট সংখ্যা দেখাবে) ---
    raw_text = (
        f"{country_data['emoji']} **{country_name}** - {list_type} List ({total_count} Total)."
        f"\n\nPress the button below to retrieve the number."
    )
    
    # নতুন বাটন তৈরি: যা প্রথম নম্বর দেখানোর জন্য handle_next_number কে কল করবে
    button_text = "➡️ Get Number" if not is_taken_selection else "👁️ See Active Numbers"
    
    # CALLBACK_SHOW_FIRST_NUMBER এ কান্ট্রি বেস এবং লিস্ট টাইপ পাঠানো হচ্ছে
    callback_data = f"{CALLBACK_SHOW_FIRST_NUMBER}{file_base}|{is_taken_selection}"
    
    keyboard = [
        [InlineKeyboardButton(button_text, callback_data=callback_data)],
        [InlineKeyboardButton("⬅️ Back to Countries", callback_data=CALLBACK_BACK_TO_COUNTRY)]
    ]
    text = escape_markdown_v2(raw_text).replace(r'\*', '*')

    await query.edit_message_text(text, parse_mode=constants.ParseMode.MARKDOWN_V2, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_next_number(query, file_base, current_index, is_taken):
    """
    পরবর্তী সিরিয়াল নম্বর দেখায় বা লিস্ট শেষ হওয়ার মেসেজ দেখায়।
    এখানে শুধু নম্বর এবং কীবোর্ড থাকবে।
    """
    numbers_list = load_numbers(file_base, is_taken)
    total_count = len(numbers_list)
    country_name = next(name for name, data in COUNTRIES.items() if data['file_base'] == file_base)

    if total_count == 0:
        raw_text = f"**{country_name}** - No numbers left."
        keyboard = [[InlineKeyboardButton("⬅️ Back to Countries", callback_data=CALLBACK_BACK_TO_COUNTRY)]]
        text = escape_markdown_v2(raw_text).replace(r'\*', '*')
        await query.edit_message_text(text, parse_mode=constants.ParseMode.MARKDOWN_V2, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if current_index >= total_count:
        text = get_list_end_message(file_base, is_taken)
        keyboard = [[InlineKeyboardButton("⬅️ Back to Countries", callback_data=CALLBACK_BACK_TO_COUNTRY)]]
        await query.edit_message_text(text, parse_mode=constants.ParseMode.MARKDOWN_V2, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # নম্বর এবং কীবোর্ড তৈরি
    current_number = numbers_list[current_index]
    
    # কোড ব্লক এবং বোল্ড ব্যবহার করা হয়েছে
    raw_text = (
        f"**{country_name}** :\n"
        f"`{current_number}`"
    )
    
    # এখানে escape_markdown_v2 ব্যবহার করে সব এস্কেপ করা হয়েছে, কিন্তু * এবং ` কে ম্যানুয়ালি ফিক্স করা হয়েছে 
    text = escape_markdown_v2(raw_text).replace(r'\*', '*').replace(r'\`', '`')
    
    reply_markup = get_number_options_keyboard(file_base, current_index, total_count, is_taken)
    
    # মেসেজ এডিট
    await query.edit_message_text(text, parse_mode=constants.ParseMode.MARKDOWN_V2, reply_markup=reply_markup)


# --- অ্যাকশন হ্যান্ডেলার: ডিলিট ও টেক ---

async def handle_action(query, data, is_delete):
    """নম্বর ডিলিট/টেক অ্যাকশন হ্যান্ডেল করে এবং পরবর্তী নম্বর দেখায়।"""
    try:
        # data format: file_base|index|list_type_str (e.g., sudan|2|taken)
        file_base, index_str, list_type = data.split('|')
        index_to_act = int(index_str)
        is_taken_list = (list_type == 'taken')
        country_name = next(name for name, data in COUNTRIES.items() if data['file_base'] == file_base)
        
        source_numbers = load_numbers(file_base, is_taken_list)
        
        if index_to_act < 0 or index_to_act >= len(source_numbers):
            logger.error(f"Index out of range: {index_to_act} for list size {len(source_numbers)}")
            await query.answer("❌ Error: Invalid index.", show_alert=True)
            return

        number_to_act = source_numbers[index_to_act]
        source_numbers.pop(index_to_act)
        
        if not save_numbers(file_base, source_numbers, is_taken_list):
            await query.answer("❌ Error: Failed to save source file.", show_alert=True)
            return
            
        if not is_taken_list and not is_delete: # Take Action (Next Available)
            taken_numbers = load_numbers(file_base, True)
            taken_numbers.append(number_to_act)
            if not save_numbers(file_base, taken_numbers, True):
                 await query.answer("❌ Error: Failed to save to taken file.", show_alert=True)
                 return
            
            logger.info(f"TAKE ACTION: {number_to_act} moved from {file_base}_number.txt to {file_base}_taken.txt")
            
            # সফল মেসেজ
            raw_text = f"✅ Success! **{country_name}** number `{number_to_act}` has been successfully taken."
            text = escape_markdown_v2(raw_text).replace(r'\*', '*').replace(r'\`', '`')
            await query.answer(text, show_alert=True)

        
        elif is_delete: # ডিলিট অ্যাকশন
             logger.info(f"DELETE ACTION: {number_to_act} deleted from {list_type} l

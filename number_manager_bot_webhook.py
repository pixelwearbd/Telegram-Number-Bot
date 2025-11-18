# File: number_manager_bot_webhook.py
# This code is an adaptation of the original bot to run using Webhooks 
# on platforms like Render or Railway for 24/7 free hosting.
# ... (এখানে পুরো কোডটি পেস্ট করুন)
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    CallbackQueryHandler,
    MessageHandler, 
    filters 
)
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
import random
import logging
import traceback
import re
import os 

# লগিং সেটআপ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# আপনার টেলিগ্রাম টোকেনটি এখানে বসান
TOKEN = '8374666904:AAFk5fQWDC_MpXXtzTAUruGLUMWsTF84ptk' 
SUPPORT_USERNAME = '@kzishihab'

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

def escape_markdown_v2(text):
    """
    MarkdownV2 ফরমেটে সংরক্ষিত অক্ষরগুলিকে এস্কেপ করে, কিন্তু 
    বোল্ড (**) এবং কোড ব্লক (`) এর চিহ্নগুলিকে এস্কেপ করবে না।
    """
    # \ (Backslash)
    text = text.replace('\\', '\\\\')
    
    # ফিক্স: '*' এবং '`' বাদ দিয়ে অন্যান্য সংরক্ষিত অক্ষর এস্কেপ করা হলো।
    # '*' (Bold), '`' (Code Block)
    text = re.sub(r'([\[\]\(\)~>#\+\-=|\{\}\.!])', r'\\\1', text)
    
    # _ (আন্ডারস্কোর) এস্কেপ:
    text = text.replace('_', r'\_')
    
    return text

def load_numbers(file_base, is_taken_list=False):
    """নির্দিষ্ট ফাইল থেকে নম্বর লোড করে।"""
    suffix = "_taken" if is_taken_list else "_number"
    filename = f"{file_base}{suffix}.txt"
    try:
        with open(filename, 'r') as f:
            numbers = [line.strip() for line in f if line.strip()]
        return numbers
    except FileNotFoundError:
        logging.error(f"Error: {filename} file not found.")
        # ফাইল না থাকলে খালি ফাইল তৈরি করা।
        if not os.path.exists(filename):
            with open(filename, 'w') as f:
                pass 
        return []

def save_numbers(file_base, numbers_list, is_taken_list=False):
    """নির্দিষ্ট ফাইলে নম্বর সেভ করে।"""
    suffix = "_taken" if is_taken_list else "_number"
    filename = f"{file_base}{suffix}.txt"
    try:
        with open(filename, 'w') as f:
            for number in numbers_list:
                f.write(number + '\n')
        return True
    except Exception as e:
        logging.error(f"Error saving to {filename}: {e}")
        return False

# --- মেনু তৈরি ফাংশন ---

def get_country_selection_keyboard(callback_prefix):
    """কান্ট্রি সিলেকশন মেনু তৈরি করে।"""
    keyboard = []
    current_row = []
    
    for name, data in COUNTRIES.items():
        # এখানে ফ্ল্যাগ ব্যবহার করা হয়েছে
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
    next_index_data = next_index if next_index < total_count else total_count 
    
    if is_taken:
        # Active/Taken List এর জন্য বাটন: Next Number এবং Delete Permanently
        keyboard = [[
            InlineKeyboardButton("➡️ Next Number", callback_data=f"{CALLBACK_NEXT_TAKEN}{file_base}|{next_index_data}"),
            InlineKeyboardButton("❌ Delete Permanently", callback_data=f"{CALLBACK_ACTION_DELETE}{file_base}|{current_index}|taken")
        ]]
    else:
        # Available Number List এর জন্য বাটন: Next Number (Take) এবং Delete Number
        keyboard = [[
            InlineKeyboardButton("➡️ Next Number (Take)", callback_data=f"{CALLBACK_NEXT_AVAILABLE}{file_base}|{next_index_data}|{current_index}"),
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
    
    # ফিক্স: এখানে বোল্ড ব্যবহার করে মেসেজটি এস্কেপ করা হলো।
    raw_text = (
        f"🚨 **{country_name}** {list_type} numbers are on countdown. "
        f"List ended at the last number. "
        f"Please wait and start from 1st number."
    )
    return escape_markdown_v2(raw_text)

# --- কমান্ড হ্যান্ডেলার ---

async def start(update, context):
    """/start কমান্ড এবং রিপ্লাই কীবোর্ড দেখায়।"""
    # শুধুমাত্র '!' এস্কেপ হবে
    text = escape_markdown_v2('Muri khao ! Use the buttons below or command /number to start.')
    await update.message.reply_text(
        text,
        reply_markup=REPLY_MARKUP,
        parse_mode='MarkdownV2'
    )

async def help_command(update, context):
    """/help কমান্ড এবং সাপোর্ট ইউজারনেম দেখায়।"""
    # সকল সংরক্ষিত অক্ষর এস্কেপ হবে (যেমন: *)
    text = escape_markdown_v2(
        "Welcome to the Number Bot! Here are the available commands:\n\n"
        "• /number \- Start the process to get a number\n"
        "• /taken \- See the numbers you have taken\n"
        "• /start \- Show the welcome message and main keyboard\.\n"
        "\n*Support:*\n"
        f"• For any issue, contact the owner: {SUPPORT_USERNAME}"
    )
    await update.message.reply_text(
        text,
        parse_mode='MarkdownV2'
    )

async def handle_get_number_command(update, context):
    """'/number' বাটন ক্লিক হলে কান্ট্রি সিলেকশন শুরু করে।"""
    # কোনো MarkdownV2 ফরমেটিং নেই, তাই escape_markdown_v2 ব্যবহার না করলেও চলে, তবে সুরক্ষার জন্য করা হলো।
    text = escape_markdown_v2("Select a Country to get an available number:")
    reply_markup = get_country_selection_keyboard(CALLBACK_SELECT_COUNTRY_GET)
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='MarkdownV2')
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='MarkdownV2')

async def handle_taken_command(update, context):
    """'/taken' বাটন ক্লিক হলে কান্ট্রি সিলেকশন শুরু করে।"""
    # "active (taken) numbers" এখানে () এস্কেপ করা প্রয়োজন।
    text = escape_markdown_v2("Select a Country to see your active \(taken\) numbers:")
    reply_markup = get_country_selection_keyboard(CALLBACK_SELECT_COUNTRY_TAKEN)
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='MarkdownV2')
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='MarkdownV2')
        
async def handle_reply_keyboard_buttons(update, context):
    """রিপ্লাই কীবোর্ডের 'Get Number' এবং 'Active Number' বাটনগুলি হ্যান্ডেল করে।"""
    text = update.message.text
    
    if text == REPLY_KEYBOARD_GET:
        await handle_get_number_command(update, context)
    elif text == REPLY_KEYBOARD_ACTIVE:
        await handle_taken_command(update, context)

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
        await query.edit_message_text(escape_markdown_v2(raw_text), parse_mode='MarkdownV2', reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # --- মধ্যবর্তী স্ক্রিনের মেসেজ (মোট সংখ্যা দেখাবে) ---
    raw_text = (
        f"{country_data['emoji']} **{country_name}** - {list_type} List \({total_count} Total\)."
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

    await query.edit_message_text(escape_markdown_v2(raw_text), parse_mode='MarkdownV2', reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_next_number(query, file_base, current_index, is_taken, action_index=None):
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
        # ফিক্স: এখানে escape_markdown_v2 ব্যবহার করা হয়েছে কারণ `country_name` এ কোনো বিশেষ অক্ষর থাকতে পারে।
        await query.edit_message_text(escape_markdown_v2(raw_text), parse_mode='MarkdownV2', reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if current_index >= total_count:
        text = get_list_end_message(file_base, is_taken)
        keyboard = [[InlineKeyboardButton("⬅️ Back to Countries", callback_data=CALLBACK_BACK_TO_COUNTRY)]]
        await query.edit_message_text(text, parse_mode='MarkdownV2', reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # নম্বর এবং কীবোর্ড তৈরি
    current_number = numbers_list[current_index]
    
    # --- নম্বর ডিসপ্লে ফরম্যাট (কপিযোগ্যতা নিশ্চিত করতে) ---
    # ফিক্স: **Country Name** বোল্ড রাখা হলো এবং নম্বরটি কোড ব্লক-এ রাখা হলো।
    # escape_markdown_v2 এখানে কল করা হয়নি, কারণ এটি ** এবং ` কে এস্কেপ করে দিচ্ছিল।
    # আমরা ধরে নিচ্ছি country_name টি সাধারণ এবং কোনো এরর তৈরি করবে না।
    raw_text = (
        f"**{country_name}** : \n"
        f"`{current_number}`"
    )
    
    reply_markup = get_number_options_keyboard(file_base, current_index, total_count, is_taken)
    
    # মেসেজ এডিট। এখানে raw_text সরাসরি MarkdownV2 হিসেবে পাঠানো হলো।
    await query.edit_message_text(raw_text, parse_mode='MarkdownV2', reply_markup=reply_markup)


# --- অ্যাকশন হ্যান্ডেলার: ডিলিট ও টেক ---

async def handle_action(query, data, is_delete):
    """নম্বর ডিলিট/টেক অ্যাকশন হ্যান্ডেল করে এবং পরবর্তী নম্বর দেখায়।"""
    try:
        # data format: file_base|index|list_type_str (e.g., sudan|2|taken)
        file_base, index_str, list_type = data.split('|')
        index_to_act = int(index_str)
        is_taken_list = (list_type == 'taken')
        
        source_numbers = load_numbers(file_base, is_taken_list)
        
        if index_to_act < 0 or index_to_act >= len(source_numbers):
            logging.error(f"Index out of range: {index_to_act} for list size {len(source_numbers)}")
            await query.answer("❌ Error: Invalid index.", show_alert=True)
            return

        number_to_act = source_numbers[index_to_act]
        source_numbers.pop(index_to_act)
        
        if not save_numbers(file_base, source_numbers, is_taken_list):
            await query.answer("❌ Error: Failed to save source file.", show_alert=True)
            return
            
        if not is_taken_list and not is_delete: # Next Available (Take)
            taken_numbers = load_numbers(file_base, True)
            taken_numbers.append(number_to_act)
            if not save_numbers(file_base, taken_numbers, True):
                 await query.answer("❌ Error: Failed to save to taken file.", show_alert=True)
                 return
            
            logging.info(f"TAKE ACTION: {number_to_act} moved from {file_base}_number.txt to {file_base}_taken.txt")
        
        elif is_delete: # ডিলিট অ্যাকশন
             logging.info(f"DELETE ACTION: {number_to_act} deleted from {list_type} list.")
            
        # অ্যাকশন সফল, এবার পরবর্তী নম্বরটি দেখান
        next_index = index_to_act 
        
        if not source_numbers:
            # ফিক্স: নম্বরটি code block (`...`) এর ভেতরে আছে।
            # escape_markdown_v2 ব্যবহার না করে, শুধুমাত্র নম্বরটিকে কোড ব্লকে রেখে মেসেজ পাঠানো হলো।
            raw_text = f"✅ `{number_to_act}` {'deleted' if is_delete else 'taken'}. No more numbers left in this list."
            keyboard = [[InlineKeyboardButton("⬅️ Back to Countries", callback_data=CALLBACK_BACK_TO_COUNTRY)]]
            await query.edit_message_text(raw_text, parse_mode='MarkdownV2', reply_markup=InlineKeyboardMarkup(keyboard))
            return

        if next_index >= len(source_numbers):
            text = get_list_end_message(file_base, is_taken_list)
            keyboard = [[InlineKeyboardButton("⬅️ Back to Countries", callback_data=CALLBACK_BACK_TO_COUNTRY)]]
            await query.edit_message_text(text, parse_mode='MarkdownV2', reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        # পরের নম্বরটি দেখান
        await handle_next_number(query, file_base, next_index, is_taken_list)

    except Exception as e:
        logging.error(f"Error in handle_action: {e}")
        logging.error(traceback.format_exc())
        await query.answer("❌ A critical error occurred while processing the number action.", show_alert=True)


# --- মূল ক্যলব্যাক হ্যান্ডেলার ---

async def button_callback(update, context):
    """Inline Keyboard বাটন ক্লিক হলে এই ফাংশনটি কাজ করবে।"""
    query = update.callback_query
    await query.answer() 
    
    data = query.data
    
    try:
        if data == CALLBACK_BACK_TO_COUNTRY:
            await handle_get_number_command(query, context)

        # ১. কান্ট্রি সিলেকশন (মধ্যবর্তী স্ক্রিন দেখাবে)
        elif data.startswith(CALLBACK_SELECT_COUNTRY_GET):
            file_base = data.replace(CALLBACK_SELECT_COUNTRY_GET, "")
            await handle_country_selection(query, file_base, is_taken_selection=False)
            
        elif data.startswith(CALLBACK_SELECT_COUNTRY_TAKEN):
            file_base = data.replace(CALLBACK_SELECT_COUNTRY_TAKEN, "")
            await handle_country_selection(query, file_base, is_taken_selection=True)

        # ২. মধ্যবর্তী স্ক্রিন থেকে প্রথম নম্বর দেখানো শুরু (Get Number/See Active Numbers ক্লিক)
        elif data.startswith(CALLBACK_SHOW_FIRST_NUMBER):
            # Format: file_base|is_taken_str
            file_base, is_taken_str = data.replace(CALLBACK_SHOW_FIRST_NUMBER, "").split('|')
            # 'True' স্ট্রিং কে বুলিয়ানে কনভার্ট করা
            is_taken = (is_taken_str == 'True') 
            # প্রথম নম্বরটি দেখাও
            await handle_next_number(query, file_base, 0, is_taken)

        # ৩. পরবর্তী নম্বর দেখা (Available List) - টেক অ্যাকশন সহ (Next Number বাটনে ক্লিক)
        elif data.startswith(CALLBACK_NEXT_AVAILABLE):
            # Format: file_base|next_index|current_index_to_take
            parts = data.replace(CALLBACK_NEXT_AVAILABLE, "").split('|')
            file_base = parts[0]
            next_index = int(parts[1])
            current_index_to_take = int(parts[2])
            
            # টেক অ্যাকশন
            await handle_action(query, f"{file_base}|{current_index_to_take}|available", is_delete=False)

        # ৪. পরবর্তী নম্বর দেখা (Taken List)
        elif data.startswith(CALLBACK_NEXT_TAKEN):
            # Format: file_base|next_index 
            parts = data.replace(CALLBACK_NEXT_TAKEN, "").split('|')
            file_base = parts[0]
            next_index = int(parts[1])
            
            # পরবর্তী নম্বর দেখাও
            await handle_next_number(query, file_base, next_index, is_taken=True)

        # ৫. অ্যাকশন: ডিলিট
        elif data.startswith(CALLBACK_ACTION_DELETE):
            # Format: file_base|index_to_delete|list_type (available or taken)
            data_to_act = data.replace(CALLBACK_ACTION_DELETE, "")
            # ডিলিট অ্যাকশন
            await handle_action(query, data_to_act, is_delete=True)

    except Exception as e:
        logging.error(f"Critical error in button_callback: {e}")
        logging.error(traceback.format_exc())
        # মেসেজ এডিটের সময় যদি parse error হয়, তবে একটি নিরাপদ মেসেজ দেখাও।
        await query.edit_message_text(escape_markdown_v2(f"❌ A critical error occurred: Can't parse entities\. Please contact support {SUPPORT_USERNAME}"), parse_mode='MarkdownV2')


# --- মূল রান ফাংশন ---

def main():
    application = ApplicationBuilder().token(TOKEN).build()
    
    print("বোট চালু করার জন্য প্রস্তুত হচ্ছে...")

    # কমান্ড হ্যান্ডলার 
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("number", handle_get_number_command))
    application.add_handler(CommandHandler("taken", handle_taken_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # রিপ্লাই কীবোর্ড বাটন হ্যান্ডেলার
    application.add_handler(MessageHandler(filters.Text([REPLY_KEYBOARD_GET, REPLY_KEYBOARD_ACTIVE]) & ~filters.COMMAND, handle_reply_keyboard_buttons))
    
    # ক্যলব্যাক হ্যান্ডেলার (Inline Button)
    application.add_handler(CallbackQueryHandler(button_callback))

    print("বোট চালু হয়েছে! টেলিগ্রামে কাজ করছে...")
    application.run_polling(poll_interval=1)


if __name__ == '__main__':
    main()
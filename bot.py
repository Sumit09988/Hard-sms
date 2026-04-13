import sqlite3
from datetime import date, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import requests
import re
import asyncio

from config import *
from database import *

application = None

# ========== API FUNCTION ==========
async def send_sms_api(phone, amount):
    try:
        url = f"{API_URL}?key={API_KEY}&phone={phone}&amount={amount}"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return True, f"✅ {amount} SMS sent to {phone}"
        else:
            return False, f"❌ API Error: {response.status_code}"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

# ========== CHECK ALL CHANNELS ==========
async def check_all_channels(bot, user_id):
    not_joined = []
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(channel['username'], user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                not_joined.append(channel)
        except:
            not_joined.append(channel)
    return not_joined

# ========== NOTIFICATIONS ==========
async def new_user_alert(user_id, username):
    try:
        await application.bot.send_message(ADMIN_ID, f"🆕 *NEW USER ALERT!*\n\n👤 ID: `{user_id}`\n📛 Username: @{username}\n📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", parse_mode='Markdown')
    except:
        pass

# ========== START COMMAND ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    not_joined = await check_all_channels(context.bot, user_id)
    
    if not_joined:
        keyboard = []
        for channel in not_joined:
            keyboard.append([InlineKeyboardButton(f"📢 JOIN {channel['name']}", url=channel['link'])])
        keyboard.append([InlineKeyboardButton("✅ CHECK AGAIN", callback_data='check_join')])
        
        await update.message.reply_text(f"❌ *ACCESS DENIED*\n\n*{len(not_joined)} channel(s) join karna compulsory hai!*\n\nSab channels join karo phir 'CHECK AGAIN' click karo.\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return
    
    check_daily_reset()
    
    db_user = get_user(user_id)
    referrer = None
    
    if context.args and context.args[0].startswith('ref_'):
        referrer = int(context.args[0].split('_')[1])
    
    if not db_user:
        create_user(user_id, user.username, referrer)
        await new_user_alert(user_id, user.username)
        credits = DAILY_FREE
    else:
        credits = db_user[2]
    
    keyboard = [
        [InlineKeyboardButton("📱 ENTER PHONE NUMBER", callback_data='enter_phone')],
        [InlineKeyboardButton("💰 CHECK CREDITS", callback_data='balance')],
        [InlineKeyboardButton("👥 REFERRAL SYSTEM", callback_data='referral')],
        [InlineKeyboardButton("📊 STATS", callback_data='stats')],
        [InlineKeyboardButton("📢 MAIN CHANNEL", url=CHANNELS[0]['link']), InlineKeyboardButton("🔥 LOKI NETWORK", url=CHANNELS[1]['link'])]
    ]
    
    await update.message.reply_text(f"🔥 *WELCOME {user.first_name}* 🔥\n\n💎 FREE SMS: {DAILY_FREE}/day\n💰 Your Credits: `{credits}`\n\n📌 *How to use:*\n1️⃣ Click 'ENTER PHONE NUMBER'\n2️⃣ Send phone number\n3️⃣ Select SMS amount\n4️⃣ Done!\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ========== CHECK JOIN BUTTON ==========
async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    not_joined = await check_all_channels(context.bot, user_id)
    
    if not_joined:
        keyboard = []
        for channel in not_joined:
            keyboard.append([InlineKeyboardButton(f"📢 JOIN {channel['name']}", url=channel['link'])])
        keyboard.append([InlineKeyboardButton("✅ CHECK AGAIN", callback_data='check_join')])
        
        await query.edit_message_text(f"❌ *Still not joined!*\n\nPlease join {len(not_joined)} channel(s) first:\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        keyboard = [
            [InlineKeyboardButton("📱 ENTER PHONE NUMBER", callback_data='enter_phone')],
            [InlineKeyboardButton("💰 CHECK CREDITS", callback_data='balance')],
            [InlineKeyboardButton("👥 REFERRAL SYSTEM", callback_data='referral')],
            [InlineKeyboardButton("📊 STATS", callback_data='stats')]
        ]
        
        await query.edit_message_text(f"✅ *All channels joined!*\n\nWelcome! Now you can use the bot.\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ========== ENTER PHONE NUMBER ==========
async def enter_phone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['awaiting_phone'] = True
    
    await query.edit_message_text(f"📱 *ENTER PHONE NUMBER*\n\nPlease send your target phone number with country code.\n\nExamples:\n• `7275915103`\n• `+917275915103`\n\nSend the number now:\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", parse_mode='Markdown')

# ========== HANDLE PHONE NUMBER ==========
async def handle_phone_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_phone'):
        return
    
    user_id = update.effective_user.id
    phone_raw = update.message.text.strip()
    
    phone = re.sub(r'[^\d+]', '', phone_raw)
    if phone.startswith('+'):
        phone = phone[1:]
    
    if not phone.isdigit() or len(phone) < 10 or len(phone) > 15:
        await update.message.reply_text(f"❌ *INVALID PHONE NUMBER*\n\nSend valid number (10-15 digits).\nExample: `7275915103`\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", parse_mode='Markdown')
        return
    
    update_phone(user_id, phone)
    context.user_data['awaiting_phone'] = False
    
    keyboard = [
        [InlineKeyboardButton("📱 500 SMS", callback_data='sms_500')],
        [InlineKeyboardButton("📱 1000 SMS", callback_data='sms_1000')],
        [InlineKeyboardButton("📱 3000 SMS", callback_data='sms_3000')],
        [InlineKeyboardButton("📱 5000 SMS", callback_data='sms_5000')],
        [InlineKeyboardButton("🔙 BACK TO MENU", callback_data='main_menu')]
    ]
    
    user = get_user(user_id)
    credits = user[2] if user else 0
    
    await update.message.reply_text(f"✅ *Phone Saved:* `{phone}`\n\n📱 *Select SMS Amount:*\n\n⚡ 1 credit = 1 SMS blast\n💰 Your balance: `{credits}` credits\n\n👇 Choose amount:\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ========== SMS AMOUNT HANDLER ==========
async def sms_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    amount = int(query.data.split('_')[1])
    
    check_daily_reset()
    
    user = get_user(user_id)
    if not user:
        await query.edit_message_text(f"❌ Use /start first!\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}")
        return
    
    if user[2] <= 0:
        keyboard = [[InlineKeyboardButton("👥 GET FREE CREDITS", callback_data='referral')]]
        await query.edit_message_text(f"❌ *NO CREDITS LEFT!*\n\nGet {DAILY_FREE} free credits daily at reset\nOr use referral system for +{REFER_REWARD} credits per friend!\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return
    
    phone = get_user_phone(user_id)
    if not phone:
        keyboard = [[InlineKeyboardButton("📱 ENTER PHONE NUMBER", callback_data='enter_phone')]]
        await query.edit_message_text(f"❌ *NO PHONE NUMBER FOUND*\n\nPlease save a phone number first!\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return
    
    update_credits(user_id, -1)
    new_credits = get_user(user_id)[2]
    
    await query.edit_message_text(f"⏳ *SENDING SMS...*\n\n📱 Phone: `{phone}`\n💥 Amount: `{amount}`\n💰 Credits left: `{new_credits}`\n\nPlease wait...\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", parse_mode='Markdown')
    
    success, message = await send_sms_api(phone, amount)
    
    if success:
        update_sent_count(user_id)
        keyboard = [
            [InlineKeyboardButton("📱 SEND AGAIN", callback_data='enter_phone')],
            [InlineKeyboardButton("💰 CHECK BALANCE", callback_data='balance')],
            [InlineKeyboardButton("🔙 MAIN MENU", callback_data='main_menu')]
        ]
        await query.edit_message_text(f"✅ *SUCCESS!*\n\n📱 Phone: `{phone}`\n💥 Amount: `{amount}`\n💰 Credits left: `{new_credits}`\n\nUse again! 👇\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        update_credits(user_id, 1)
        keyboard = [[InlineKeyboardButton("🔄 TRY AGAIN", callback_data='enter_phone')]]
        await query.edit_message_text(f"❌ *FAILED*\n\n{message}\n\nCredits refunded!\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ========== BALANCE ==========
async def balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if user:
        keyboard = [[InlineKeyboardButton("🔙 BACK", callback_data='main_menu')]]
        await query.edit_message_text(f"💰 *YOUR BALANCE*\n\n💎 Credits: `{user[2]}`\n📱 Total SMS Sent: `{user[5] or 0}`\n🔄 Resets daily at midnight\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await query.edit_message_text(f"❌ User not found! Use /start\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}")

# ========== REFERRAL ==========
async def referral_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user_id,))
    ref_count = c.fetchone()[0]
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("📤 SHARE LINK", url=f"https://t.me/share/url?url={link}")],
        [InlineKeyboardButton("🔙 BACK", callback_data='main_menu')]
    ]
    
    await query.edit_message_text(f"👥 *REFERRAL SYSTEM*\n\n🔗 Your Link:\n`{link}`\n\n👤 Referrals: `{ref_count}`\n🎁 Reward: `+{REFER_REWARD}` credits per referral\n\nShare and earn free credits!\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ========== STATS ==========
async def stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    total_users = get_total_users()
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT SUM(total_sent) FROM users")
    total_sms = c.fetchone()[0] or 0
    conn.close()
    
    keyboard = [[InlineKeyboardButton("🔙 BACK", callback_data='main_menu')]]
    
    await query.edit_message_text(f"📊 *BOT STATISTICS*\n\n👥 Total Users: `{total_users}`\n📱 Total SMS Sent: `{total_sms}`\n💎 Daily Free: `{DAILY_FREE}`\n🎁 Refer Reward: `+{REFER_REWARD}`\n\n🔥 Made with ❤️ by @{DEVELOPER_USERNAME}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ========== MAIN MENU ==========
async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = get_user(user_id)
    credits = user[2] if user else DAILY_FREE
    
    keyboard = [
        [InlineKeyboardButton("📱 ENTER PHONE NUMBER", callback_data='enter_phone')],
        [InlineKeyboardButton("💰 CHECK CREDITS", callback_data='balance')],
        [InlineKeyboardButton("👥 REFERRAL SYSTEM", callback_data='referral')],
        [InlineKeyboardButton("📊 STATS", callback_data='stats')],
        [InlineKeyboardButton("📢 MAIN CHANNEL", url=CHANNELS[0]['link']), InlineKeyboardButton("🔥 LOKI NETWORK", url=CHANNELS[1]['link'])]
    ]
    
    await query.edit_message_text(f"🔥 *MAIN MENU* 🔥\n\n💰 Credits: `{credits}`\n💎 Free: {DAILY_FREE}/day\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ========== ADMIN COMMANDS ==========
async def admin_add_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("Usage: `/addcredits USER_ID AMOUNT`", parse_mode='Markdown')
        return
    
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
        update_credits(user_id, amount)
        await update.message.reply_text(f"✅ Added {amount} credits to user {user_id}")
        
        try:
            await context.bot.send_message(user_id, f"🎁 Admin added +{amount} credits to your account!\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}")
        except:
            pass
    except:
        await update.message.reply_text("❌ Invalid input!")

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    message = ' '.join(context.args)
    if not message:
        await update.message.reply_text("Usage: `/broadcast MESSAGE`", parse_mode='Markdown')
        return
    
    users = get_all_users()
    success = 0
    
    status_msg = await update.message.reply_text(f"📡 Broadcasting to {len(users)} users...")
    
    for user_id in users:
        try:
            await context.bot.send_message(user_id, f"📢 *ANNOUNCEMENT*\n\n{message}\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", parse_mode='Markdown')
            success += 1
        except:
            pass
        await asyncio.sleep(0.05)
    
    await status_msg.edit_text(f"✅ Broadcast sent to {success}/{len(users)} users")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    total_users = get_total_users()
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT SUM(credits), SUM(total_sent) FROM users")
    total_credits, total_sent = c.fetchone()
    conn.close()
    
    await update.message.reply_text(f"📊 *ADMIN STATS*\n\n👥 Total Users: `{total_users}`\n📱 Total SMS: `{total_sent or 0}`\n💎 Total Credits: `{total_credits or 0}`\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", parse_mode='Markdown')

# ========== MAIN ==========
def main():
    global application
    application = Application.builder().token(BOT_TOKEN).build()
    
    init_db()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addcredits", admin_add_credits))
    application.add_handler(CommandHandler("broadcast", admin_broadcast))
    application.add_handler(CommandHandler("stats", admin_stats))
    
    application.add_handler(CallbackQueryHandler(enter_phone_callback, pattern='enter_phone'))
    application.add_handler(CallbackQueryHandler(sms_amount_handler, pattern='^sms_\\d+$'))
    application.add_handler(CallbackQueryHandler(balance_callback, pattern='balance'))
    application.add_handler(CallbackQueryHandler(referral_callback, pattern='referral'))
    application.add_handler(CallbackQueryHandler(stats_callback, pattern='stats'))
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern='main_menu'))
    application.add_handler(CallbackQueryHandler(check_join_callback, pattern='check_join'))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_message))
    
    print(f"✅ Bot @{BOT_USERNAME} is running...")
    print(f"👨‍💻 Developer: @{DEVELOPER_USERNAME}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

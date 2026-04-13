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

# ========== CHECK MEMBERSHIP ==========
async def check_channel_membership(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

# ========== NOTIFICATIONS ==========
async def new_user_alert(user_id, username):
    try:
        await application.bot.send_message(
            ADMIN_ID,
            f"🆕 *NEW USER ALERT!*\n\n👤 ID: `{user_id}`\n📛 Username: @{username}\n📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            parse_mode='Markdown'
        )
    except:
        pass

# ========== START COMMAND ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if not await check_channel_membership(context.bot, user_id):
        keyboard = [[InlineKeyboardButton("📢 JOIN CHANNEL", url=CHANNEL_LINK)]]
        await update.message.reply_text(
            "❌ *ACCESS DENIED*\n\nYou must join our channel first!\n\nClick below to join 👇",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
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
        [InlineKeyboardButton("📢 CHANNEL", url=CHANNEL_LINK), InlineKeyboardButton("👥 GROUP", url=GROUP_LINK)]
    ]
    
    await update.message.reply_text(
        f"🔥 *WELCOME {user.first_name}* 🔥\n\n"
        f"💎 FREE SMS: {DAILY_FREE}/day\n"
        f"💰 Your Credits: `{credits}`\n\n"
        f"📌 *How to use:*\n"
        f"1️⃣ Click 'ENTER PHONE NUMBER'\n"
        f"2️⃣ Send phone number (with country code)\n"
        f"3️⃣ Select SMS amount\n"
        f"4️⃣ Done!\n\n"
        f"👨‍💻 Developer: @{DEVELOPER_USERNAME}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ========== ENTER PHONE NUMBER ==========
async def enter_phone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['awaiting_phone'] = True
    
    await query.edit_message_text(
        f"📱 *ENTER PHONE NUMBER*\n\n"
        f"Please send your target phone number with country code.\n\n"
        f"Examples:\n"
        f"• `7275915103` (India)\n"
        f"• `+917275915103`\n\n"
        f"Send the number now:\n\n"
        f"👨‍💻 Developer: @{DEVELOPER_USERNAME}",
        parse_mode='Markdown'
    )

# ========== HANDLE PHONE NUMBER INPUT ==========
async def handle_phone_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_phone'):
        return
    
    user_id = update.effective_user.id
    phone_raw = update.message.text.strip()
    
    phone = re.sub(r'[^\d+]', '', phone_raw)
    if phone.startswith('+'):
        phone = phone[1:]
    
    if not phone.isdigit() or len(phone) < 10 or len(phone) > 15:
        await update.message.reply_text(
            "❌ *INVALID PHONE NUMBER*\n\nPlease send a valid number (10-15 digits).\nExample: `7275915103`\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}",
            parse_mode='Markdown'
        )
        return
    
    update_phone(user_id, phone)
    context.user_data['awaiting_phone'] = False
    context.user_data['target_phone'] = phone
    
    keyboard = [
        [InlineKeyboardButton("📱 500 SMS", callback_data='sms_500')],
        [InlineKeyboardButton("📱 1000 SMS", callback_data='sms_1000')],
        [InlineKeyboardButton("📱 3000 SMS", callback_data='sms_3000')],
        [InlineKeyboardButton("📱 5000 SMS", callback_data='sms_5000')],
        [InlineKeyboardButton("🔙 BACK TO MENU", callback_data='main_menu')]
    ]
    
    user = get_user(user_id)
    credits = user[2] if user else 0
    
    await update.message.reply_text(
        f"✅ *Phone Saved:* `{phone}`\n\n"
        f"📱 *Select SMS Amount:*\n\n"
        f"⚡ 1 credit = 1 SMS blast\n"
        f"💰 Your balance: `{credits}` credits\n\n"
        f"👇 Choose amount:\n\n"
        f"👨‍💻 Developer: @{DEVELOPER_USERNAME}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ========== SMS AMOUNT HANDLER ==========
async def sms_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    amount = int(query.data.split('_')[1])
    
    check_daily_reset()
    
    user = get_user(user_id)
    if not user:
        await query.edit_message_text("❌ Use /start first!\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}")
        return
    
    if user[2] <= 0:
        keyboard = [[InlineKeyboardButton("👥 GET FREE CREDITS", callback_data='referral')]]
        await query.edit_message_text(
            f"❌ *NO CREDITS LEFT!*\n\n"
            f"Get {DAILY_FREE} free credits daily at reset\n"
            f"Or use referral system for +{REFER_REWARD} credits per friend!\n\n"
            f"👨‍💻 Developer: @{DEVELOPER_USERNAME}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    phone = get_user_phone(user_id)
    if not phone:
        keyboard = [[InlineKeyboardButton("📱 ENTER PHONE NUMBER", callback_data='enter_phone')]]
        await query.edit_message_text(
            "❌ *NO PHONE NUMBER FOUND*\n\nPlease save a phone number first!\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    update_credits(user_id, -1)
    new_credits = get_user(user_id)[2]
    
    await query.edit_message_text(
        f"⏳ *SENDING SMS...*\n\n"
        f"📱 Phone: `{phone}`\n"
        f"💥 Amount: `{amount}`\n"
        f"💰 Credits left: `{new_credits}`\n\n"
        f"Please wait...\n\n"
        f"👨‍💻 Developer: @{DEVELOPER_USERNAME}",
        parse_mode='Markdown'
    )
    
    success, message = await send_sms_api(phone, amount)
    
    if success:
        update_sent_count(user_id)
        keyboard = [
            [InlineKeyboardButton("📱 SEND AGAIN", callback_data='enter_phone')],
            [InlineKeyboardButton("💰 CHECK BALANCE", callback_data='balance')],
            [InlineKeyboardButton("🔙 MAIN MENU", callback_data='main_menu')]
        ]
        await query.edit_message_text(
            f"✅ *SUCCESS!*\n\n"
            f"📱 Phone: `{phone}`\n"
            f"💥 Amount: `{amount}`\n"
            f"💰 Credits left: `{new_credits}`\n\n"
            f"Use again! 👇\n\n"
            f"👨‍💻 Developer: @{DEVELOPER_USERNAME}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        update_credits(user_id, 1)
        keyboard = [[InlineKeyboardButton("🔄 TRY AGAIN", callback_data='enter_phone')]]
        await query.edit_message_text(
            f"❌ *FAILED*\n\n"
            f"{message}\n\n"
            f"Credits refunded!\n\n"
            f"👨‍💻 Developer: @{DEVELOPER_USERNAME}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

# ========== BALANCE CHECK ==========
async def balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if user:
        keyboard = [[InlineKeyboardButton("🔙 BACK", callback_data='main_menu')]]
        await query.edit_message_text(
            f"💰 *YOUR BALANCE*\n\n"
            f"💎 Credits: `{user[2]}`\n"
            f"📱 Total SMS Sent: `{user[5] or 0}`\n"
            f"🔄 Resets daily at midnight\n\n"
            f"👨‍💻 Developer: @{DEVELOPER_USERNAME}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text("❌ User not found! Use /start\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}")

# ========== REFERRAL SYSTEM ==========
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
    
    await query.edit_message_text(
        f"👥 *REFERRAL SYSTEM*\n\n"
        f"🔗 Your Link:\n`{link}`\n\n"
        f"👤 Referrals: `{ref_count}`\n"
        f"🎁 Reward: `+{REFER_REWARD}` credits per referral\n\n"
        f"Share and earn free credits!\n\n"
        f"👨‍💻 Developer: @{DEVELOPER_USERNAME}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

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
    
    await query.edit_message_text(
        f"📊 *BOT STATISTICS*\n\n"
        f"👥 Total Users: `{total_users}`\n"
        f"📱 Total SMS Sent: `{total_sms}`\n"
        f"💎 Daily Free: `{DAILY_FREE}`\n"
        f"🎁 Refer Reward: `+{REFER_REWARD}`\n\n"
        f"🔥 Made with ❤️ by @{DEVELOPER_USERNAME}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

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
        [InlineKeyboardButton("📢 CHANNEL", url=CHANNEL_LINK), InlineKeyboardButton("👥 GROUP", url=GROUP_LINK)]
    ]
    
    await query.edit_message_text(
        f"🔥 *MAIN MENU* 🔥\n\n"
        f"💰 Credits: `{credits}`\n"
        f"💎 Free: {DAILY_FREE}/day\n\n"
        f"👨‍💻 Developer: @{DEVELOPER_USERNAME}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

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
    
    await update.message.reply_text(
        f"📊 *ADMIN STATS*\n\n"
        f"👥 Total Users: `{total_users}`\n"
        f"📱 Total SMS: `{total_sent or 0}`\n"
        f"💎 Total Credits: `{total_credits or 0}`\n\n"
        f"👨‍💻 Developer: @{DEVELOPER_USERNAME}",
        parse_mode='Markdown'
    )

async def admin_reset_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: `/resetuser USER_ID`", parse_mode='Markdown')
        return
    
    try:
        user_id = int(context.args[0])
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        today = date.today()
        c.execute("UPDATE users SET credits = ?, last_reset = ? WHERE user_id=?", (DAILY_FREE, today, user_id))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Reset user {user_id} to {DAILY_FREE} credits")
    except:
        await update.message.reply_text("❌ Invalid user ID!")

# ========== MAIN ==========
def main():
    global application
    application = Application.builder().token(BOT_TOKEN).build()
    
    init_db()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addcredits", admin_add_credits))
    application.add_handler(CommandHandler("broadcast", admin_broadcast))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CommandHandler("resetuser", admin_reset_user))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(enter_phone_callback, pattern='enter_phone'))
    application.add_handler(CallbackQueryHandler(sms_amount_handler, pattern='^sms_\\d+$'))
    application.add_handler(CallbackQueryHandler(balance_callback, pattern='balance'))
    application.add_handler(CallbackQueryHandler(referral_callback, pattern='referral'))
    application.add_handler(CallbackQueryHandler(stats_callback, pattern='stats'))
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern='main_menu'))
    
    # Message handler for phone number input
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_message))
    
    print(f"✅ Bot @{BOT_USERNAME} is running...")
    print(f"👨‍💻 Developer: @{DEVELOPER_USERNAME}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

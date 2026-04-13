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

# ========== CHECK CHANNEL MEMBERSHIP (SIRF COMPULSORY CHANNEL) ==========
async def check_compulsory_channel(bot, user_id):
    try:
        member = await bot.get_chat_member(COMPULSORY_CHANNEL['username'], user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

# ========== NOTIFICATIONS ==========
async def new_user_alert(user_id, username):
    try:
        await application.bot.send_message(
            ADMIN_ID,
            f"🆕 *NEW USER ALERT!*\n\n👤 ID: `{user_id}`\n📛 Username: @{username}\n📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            parse_modeboard = [
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

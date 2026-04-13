from config import *
import sqlite3
from datetime import date, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import requests
import re
import asyncio

application = None

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  credits INTEGER DEFAULT 5,
                  last_reset DATE,
                  referrer_id INTEGER,
                  total_sent INTEGER DEFAULT 0,
                  phone_number TEXT,
                  join_date DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS referrals
                 (referrer_id INTEGER, referred_id INTEGER, date DATE)''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(user_id, username, referrer_id=None):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    today = date.today()
    c.execute("INSERT INTO users (user_id, username, credits, last_reset, referrer_id, join_date) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, username, DAILY_FREE, today, referrer_id, today))
    if referrer_id:
        c.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (REFER_REWARD, referrer_id))
        c.execute("INSERT INTO referrals VALUES (?, ?, ?)", (referrer_id, user_id, today))
    conn.commit()
    conn.close()

def update_credits(user_id, amount):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def update_phone(user_id, phone):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET phone_number = ? WHERE user_id=?", (phone, user_id))
    conn.commit()
    conn.close()

def get_user_phone(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT phone_number FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def update_sent_count(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET total_sent = total_sent + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def check_daily_reset():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    today = date.today()
    c.execute("SELECT user_id, last_reset FROM users")
    users = c.fetchall()
    for user_id, last_reset in users:
        if last_reset is None or str(last_reset) != str(today):
            c.execute("UPDATE users SET credits = ?, last_reset = ? WHERE user_id=?", (DAILY_FREE, today, user_id))
    conn.commit()
    conn.close()

def get_total_users():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_all_users():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

def get_today_new_users():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    today = date.today()
    c.execute("SELECT COUNT(*) FROM users WHERE join_date=?", (today,))
    count = c.fetchone()[0]
    conn.close()
    return count

async def send_sms_in_background(phone, amount, user_id, selected_amount, chat_id, message_id):
    success = False
    for retry in range(3):
        try:
            url = f"{API_URL}?key={API_KEY}&phone={phone}&amount={amount}"
            response = requests.get(url, timeout=60)
            if response.status_code == 200:
                success = True
                update_sent_count(user_id)
                break
        except:
            if retry < 2:
                await asyncio.sleep(3)
            else:
                break
    new_credits = get_user(user_id)[2]
    keyboard = [
        [InlineKeyboardButton("📱 SEND AGAIN", callback_data='enter_phone')],
        [InlineKeyboardButton("💰 CHECK BALANCE", callback_data='balance')],
        [InlineKeyboardButton("🔙 MAIN MENU", callback_data='main_menu')]
    ]
    try:
        if success:
            await application.bot.edit_message_text(
                f"✅ *SUCCESSFUL {selected_amount}*\n\n"
                f"📱 Target: `{phone}`\n"
                f"💥 SMS Sent: `{selected_amount}`\n"
                f"💰 Credits Left: `{new_credits}`\n\n"
                f"👨‍💻 Developer: @{DEVELOPER_USERNAME}",
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await application.bot.edit_message_text(
                f"❌ *FAILED {selected_amount}*\n\n"
                f"📱 Target: `{phone}`\n"
                f"💥 SMS Sent: `0`\n"
                f"💰 Credits Left: `{new_credits}`\n\n"
                f"👨‍💻 Developer: @{DEVELOPER_USERNAME}",
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    except:
        pass

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

async def new_user_alert(user_id, username):
    today_new = get_today_new_users()
    total_users = get_total_users()
    try:
        await application.bot.send_message(
            ADMIN_ID,
            f"🆕 *NEW USER ALERT!*\n\n👤 ID: `{user_id}`\n📛 Username: @{username}\n📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n📊 Today New: {today_new}\n👥 Total Users: {total_users}",
            parse_mode='Markdown'
        )
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    not_joined = await check_all_channels(context.bot, user_id)
    if not_joined:
        keyboard = []
        for channel in not_joined:
            keyboard.append([InlineKeyboardButton(f"📢 JOIN {channel['name']}", url=channel['link'])])
        keyboard.append([InlineKeyboardButton("✅ CHECK AGAIN", callback_data='check_join')])
        await update.message.reply_text(
            f"❌ *ACCESS DENIED*\n\n{len(not_joined)} channel(s) join karna compulsory hai!\n\nSab channels join karo phir 'CHECK AGAIN' click karo.\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}",
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
    ]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("💸 ADD CREDITS", callback_data='admin_add_credits')])
        keyboard.append([InlineKeyboardButton("📢 BROADCAST", callback_data='admin_broadcast')])
    await update.message.reply_text(
        f"🎉 *WELCOME {user.first_name}* 🎉\n\n"
        f"💎 FREE SMS: {DAILY_FREE}/day\n"
        f"💰 Your Credits: `{credits}`\n\n"
        f"📌 *How to use:*\n"
        f"1️⃣ Click 'ENTER PHONE NUMBER'\n"
        f"2️⃣ Send phone number\n"
        f"3️⃣ Select SMS amount\n"
        f"4️⃣ Done!\n\n"
        f"👨‍💻 Developer: @{DEVELOPER_USERNAME}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def enter_phone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['awaiting_phone'] = True
    await query.edit_message_text(
        f"📱 *ENTER PHONE NUMBER*\n\nPlease send your target phone number with country code.\n\nExamples:\n• `7275915103`\n• `+917275915103`\n\nSend the number now:\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}",
        parse_mode='Markdown'
    )

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
        [InlineKeyboardButton("🔙 MAIN MENU", callback_data='main_menu')]
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

async def sms_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    amount = int(query.data.split('_')[1])
    check_daily_reset()
    user = get_user(user_id)
    if not user:
        await query.edit_message_text("❌ Use /start first!", parse_mode='Markdown')
        return
    if user[2] <= 0:
        keyboard = [[InlineKeyboardButton("👥 GET FREE CREDITS", callback_data='referral')]]
        await query.edit_message_text(
            "❌ *NO CREDITS LEFT!*\n\nGet 5 free daily or refer friends!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    phone = get_user_phone(user_id)
    if not phone:
        keyboard = [[InlineKeyboardButton("📱 ENTER PHONE NUMBER", callback_data='enter_phone')]]
        await query.edit_message_text(
            "❌ *NO NUMBER SAVED*\n\nPlease save a phone number first!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    update_credits(user_id, -1)
    new_credits = get_user(user_id)[2]
    msg = await query.edit_message_text(
        f"⏳ *PROCESSING...*\n\n📱 Target: `{phone}`\n💥 Amount: `{amount}`\n💰 Credits Left: `{new_credits}`\n\nPlease wait...",
        parse_mode='Markdown'
    )
    asyncio.create_task(send_sms_in_background(phone, amount, user_id, amount, msg.chat_id, msg.message_id))

async def balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    if user:
        keyboard = [[InlineKeyboardButton("🔙 BACK", callback_data='main_menu')]]
        await query.edit_message_text(
            f"💰 *YOUR BALANCE*\n\n💎 Credits: `{user[2]}`\n📱 Total SMS Sent: `{user[5] or 0}`\n🔄 Resets daily at midnight\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text(f"❌ User not found! Use /start\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}")

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
        f"👥 *REFERRAL SYSTEM*\n\n🔗 Your Link:\n`{link}`\n\n👤 Referrals: `{ref_count}`\n🎁 Reward: `+{REFER_REWARD}` credits per referral\n\nShare and earn free credits!\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    total_users = get_total_users()
    today_new = get_today_new_users()
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT SUM(total_sent) FROM users")
    total_sms = c.fetchone()[0] or 0
    conn.close()
    keyboard = [[InlineKeyboardButton("🔙 BACK", callback_data='main_menu')]]
    await query.edit_message_text(
        f"📊 *BOT STATISTICS*\n\n"
        f"👥 Total Users: `{total_users}`\n"
        f"🆕 Today New: `{today_new}`\n"
        f"📱 Total SMS Sent: `{total_sms}`\n"
        f"💎 Daily Free: `{DAILY_FREE}`\n"
        f"🎁 Refer Reward: `+{REFER_REWARD}`\n\n"
        f"🔥 Made with ❤️ by @{DEVELOPER_USERNAME}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

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
        await query.edit_message_text(
            f"❌ *Still not joined!*\n\nPlease join {len(not_joined)} channel(s) first.\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await main_menu_callback(update, context)

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
    ]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("💸 ADD CREDITS", callback_data='admin_add_credits')])
        keyboard.append([InlineKeyboardButton("📢 BROADCAST", callback_data='admin_broadcast')])
    await query.edit_message_text(
        f"🔥 *MAIN MENU* 🔥\n\n💰 Credits: `{credits}`\n💎 Free: {DAILY_FREE}/day\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def admin_add_credits_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Admin only!")
        return
    context.user_data['awaiting_admin_add'] = True
    await query.edit_message_text(
        "💸 *ADD CREDITS*\n\nSend: `USER_ID AMOUNT`\nExample: `7515864015 100`\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}",
        parse_mode='Markdown'
    )

async def admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Admin only!")
        return
    context.user_data['awaiting_admin_broadcast'] = True
    await query.edit_message_text(
        "📢 *BROADCAST*\n\nSend your message to broadcast to all users:\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}",
        parse_mode='Markdown'
    )

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    if context.user_data.get('awaiting_admin_add'):
        context.user_data['awaiting_admin_add'] = False
        try:
            parts = update.message.text.strip().split()
            target_id = int(parts[0])
            amount = int(parts[1])
            update_credits(target_id, amount)
            await update.message.reply_text(f"✅ Added {amount} credits to user {target_id}")
            try:
                await context.bot.send_message(target_id, f"🎁 Admin added +{amount} credits to your account!\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}")
            except:
                pass
        except:
            await update.message.reply_text("❌ Invalid format! Use: USER_ID AMOUNT")
    elif context.user_data.get('awaiting_admin_broadcast'):
        context.user_data['awaiting_admin_broadcast'] = False
        message = update.message.text.strip()
        users = get_all_users()
        success = 0
        status_msg = await update.message.reply_text(f"📡 Broadcasting to {len(users)} users...")
        for uid in users:
            try:
                await context.bot.send_message(uid, f"📢 *ANNOUNCEMENT*\n\n{message}\n\n👨‍💻 Developer: @{DEVELOPER_USERNAME}", parse_mode='Markdown')
                success += 1
            except:
                pass
            await asyncio.sleep(0.05)
        await status_msg.edit_text(f"✅ Broadcast sent to {success}/{len(users)} users")

def main():
    global application
    application = Application.builder().token(BOT_TOKEN).build()
    init_db()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(enter_phone_callback, pattern='enter_phone'))
    application.add_handler(CallbackQueryHandler(sms_amount_handler, pattern='^sms_\\d+$'))
    application.add_handler(CallbackQueryHandler(balance_callback, pattern='balance'))
    application.add_handler(CallbackQueryHandler(referral_callback, pattern='referral'))
    application.add_handler(CallbackQueryHandler(stats_callback, pattern='stats'))
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern='main_menu'))
    application.add_

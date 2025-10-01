from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# -----------------------
# CONFIGURATION
# -----------------------
TOKEN = "8456146335:AAG30bvxx0D3xKGzesZgiOuJsJATcaf-cNI"
OWNER_ID = 7670747174
ADMINS = [OWNER_ID]

# Data storage
all_users = set()
live_support_users = {}
pending_requests = {}
user_mapping = {}
user_language = {}  # Store user language preference

# -----------------------
# /start command
# -----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    all_users.add(user.id)

    # Default welcome text (bilingual)
    text = f"👋 Welcome / স্বাগতম to Kong's Club Help Support Bot\n\n" \
           f"🆔 Your ID / আপনার আইডি: <code>{user.id}</code>\n" \
           f"👤 Name / নাম: {user.full_name} (@{user.username if user.username else 'No Username'})"

    # Buttons for all users
    keyboard = [
        [InlineKeyboardButton("💬 Live Support / লাইভ সাপোর্ট", callback_data="live_support")],
        [InlineKeyboardButton("🌐 Language / ভাষা", callback_data="choose_language")]
    ]

    # Admin Panel button only for admins
    if user.id in ADMINS:
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel / এডমিন প্যানেল", callback_data="admin_panel")])

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# -----------------------
# Language selection
# -----------------------
async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("English", callback_data="set_lang_en")],
        [InlineKeyboardButton("বাংলা", callback_data="set_lang_bn")]
    ]
    await query.edit_message_text("🌐 Please choose your language / ভাষা নির্বাচন করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()

    if query.data == "set_lang_en":
        user_language[user.id] = "en"
        await query.edit_message_text("✅ Language set to English.")
    elif query.data == "set_lang_bn":
        user_language[user.id] = "bn"
        await query.edit_message_text("✅ ভাষা বাংলা হিসেবে সেট করা হয়েছে।")

# -----------------------
# Live Support Button
# -----------------------
async def live_support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()

    if user.id in live_support_users:
        msg = "⚠️ Already connected with an admin."
        if user_language.get(user.id) == "bn":
            msg = "⚠️ আপনি ইতিমধ্যেই কোনো এডমিনের সাথে সংযুক্ত।"
        await query.edit_message_text(msg)
        return

    for admin_id in ADMINS:
        try:
            keyboard = [[InlineKeyboardButton("✅ Accept", callback_data=f"accept_{user.id}")]]
            await context.bot.send_message(
                admin_id,
                f"📩 New Support Request / নতুন সাপোর্ট রিকোয়েস্ট\nFrom: {user.full_name} (@{user.username if user.username else 'No Username'})\nUser ID: {user.id}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            pending_requests.setdefault(user.id, []).append(admin_id)
        except:
            pass

    msg = "⏳ Support request sent to admins. Wait for acceptance."
    if user_language.get(user.id) == "bn":
        msg = "⏳ আপনার রিকোয়েস্ট পাঠানো হয়েছে এডমিনদের কাছে।"
    await query.edit_message_text(msg)

# -----------------------
# Admin Accept Button
# -----------------------
async def accept_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin = query.from_user
    await query.answer()

    if admin.id not in ADMINS:
        await query.edit_message_text("❌ You are not an admin / আপনি এডমিন নন।")
        return

    user_id = int(query.data.split("_")[1])
    if user_id in live_support_users:
        await query.edit_message_text("⚠️ Already accepted by another admin.")
        return

    live_support_users[user_id] = admin.id

    for other_admin_id in pending_requests.get(user_id, []):
        if other_admin_id != admin.id:
            try:
                await context.bot.send_message(other_admin_id, f"⚠️ User {user_id} accepted by {admin.full_name}.")
            except:
                pass
    pending_requests.pop(user_id, None)

    await query.edit_message_text("✅ You accepted the support request.")
    try:
        lang = user_language.get(user_id, "en")
        msg = "👨‍💻 Admin connected. You can now send messages and files."
        if lang == "bn":
            msg = "👨‍💻 এডমিন সংযুক্ত হয়েছে। আপনি এখন মেসেজ এবং ফাইল পাঠাতে পারবেন।"
        await context.bot.send_message(user_id, msg)
    except:
        pass

# -----------------------
# Forward User Messages
# -----------------------
async def forward_to_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admin_id = live_support_users.get(user.id)

    if admin_id:
        try:
            if update.message.text:
                msg = await context.bot.send_message(admin_id, f"📩 Message from {user.full_name} (@{user.username if user.username else 'No Username'}):\n\n{update.message.text}")
                user_mapping[msg.message_id] = user.id
            elif update.message.photo:
                msg = await context.bot.send_photo(admin_id, photo=update.message.photo[-1].file_id, caption=f"📩 Photo from {user.full_name}")
                user_mapping[msg.message_id] = user.id
            elif update.message.document:
                msg = await context.bot.send_document(admin_id, document=update.message.document.file_id, caption=f"📩 Document from {user.full_name}")
                user_mapping[msg.message_id] = user.id
        except:
            pass
    else:
        lang = user_language.get(user.id, "en")
        msg = "⏳ Waiting for an admin to accept your request"
        if lang == "bn":
            msg = "⏳ আপনার রিকোয়েস্ট এখনও গ্রহণ হয়নি"
        await update.message.reply_text(msg)

# -----------------------
# Admin reply
# -----------------------
async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin = update.effective_user
    if admin.id not in ADMINS:
        return

    if update.message.reply_to_message:
        replied_msg_id = update.message.reply_to_message.message_id
        target_user_id = user_mapping.get(replied_msg_id)
        if target_user_id and live_support_users.get(target_user_id) == admin.id:
            try:
                if update.message.text:
                    await context.bot.send_message(target_user_id, f"👨‍💻 Admin: {update.message.text}")
                elif update.message.photo:
                    await context.bot.send_photo(target_user_id, photo=update.message.photo[-1].file_id, caption="👨‍💻 Admin sent a photo")
                elif update.message.document:
                    await context.bot.send_document(target_user_id, document=update.message.document.file_id, caption="👨‍💻 Admin sent a document")
            except:
                pass

# -----------------------
# Admin Panel Inline
# -----------------------
async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()

    if user.id not in ADMINS:
        await query.edit_message_text("❌ You are not an admin / আপনি এডমিন নন।")
        return

    keyboard = [
        [InlineKeyboardButton("📢 Broadcast", callback_data="panel_broadcast")],
        [InlineKeyboardButton("👥 Users List", callback_data="panel_users")],
        [InlineKeyboardButton("➕ Add Admin", callback_data="panel_addadmin")],
        [InlineKeyboardButton("➖ Remove Admin", callback_data="panel_removeadmin")]
    ]
    await query.edit_message_text("⚙️ Admin Panel / এডমিন প্যানেল", reply_markup=InlineKeyboardMarkup(keyboard))

# -----------------------
# Admin Panel Actions
# -----------------------
async def admin_panel_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()

    if user.id not in ADMINS:
        return

    action = query.data
    if action == "panel_users":
        text = "👥 All Users / সমস্ত ইউজার:\n\n" + "\n".join([str(uid) for uid in all_users])
        await query.edit_message_text(text)
    else:
        await query.edit_message_text("⚠️ Use commands for this action / এই অ্যাকশন এখন কমান্ড দিয়ে করুন।")

# -----------------------
# Bot Runner
# -----------------------
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(live_support_handler, pattern="^live_support$"))
    app.add_handler(CallbackQueryHandler(choose_language, pattern="^choose_language$"))
    app.add_handler(CallbackQueryHandler(set_language, pattern="^set_lang_"))
    app.add_handler(CallbackQueryHandler(accept_request, pattern="^accept_"))
    app.add_handler(CallbackQueryHandler(admin_panel_handler, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_panel_actions, pattern="^panel_"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.User(ADMINS), forward_to_admins))
    app.add_handler(MessageHandler(filters.ALL & filters.User(ADMINS), admin_reply))

    print("🤖 Live Support Bot running. Bilingual (Bangla + English) with two buttons for users.")
    app.run_polling()

if __name__ == "__main__":
    main()

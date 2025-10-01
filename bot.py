from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# -----------------------
# CONFIGURATION
# -----------------------
TOKEN = "8456146335:AAG30bvxx0D3xKGzesZgiOuJsJATcaf-cNI"
OWNER_ID = 7670747174

# Admin list (Owner automatically admin)
ADMINS = [OWNER_ID]

# Data storage
all_users = set()
live_support_users = {}
pending_requests = {}
user_mapping = {}

# -----------------------
# /start command
# -----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    all_users.add(user.id)
    
    text = f"👋 Welcome to Kong's Club Help Support Bot\n\n🆔 Your ID: <code>{user.id}</code>\n👤 Name: {user.full_name} (@{user.username if user.username else 'No Username'})"
    
    keyboard = [
        [InlineKeyboardButton("💬 Live Support", callback_data="live_support")],
        [InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]
    ]
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# -----------------------
# Live Support Button
# -----------------------
async def live_support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()
    
    if user.id in live_support_users:
        await query.edit_message_text("⚠️ Already connected with an admin.")
        return
    
    for admin_id in ADMINS:
        try:
            keyboard = [[InlineKeyboardButton("✅ Accept", callback_data=f"accept_{user.id}")]]
            await context.bot.send_message(
                admin_id,
                f"📩 New Support Request from {user.full_name} (@{user.username if user.username else 'No Username'})\nUser ID: {user.id}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            pending_requests.setdefault(user.id, []).append(admin_id)
        except:
            pass
    
    await query.edit_message_text("⏳ Support request sent to admins. Wait for acceptance.")

# -----------------------
# Admin Accept Button
# -----------------------
async def accept_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin = query.from_user
    await query.answer()
    
    if admin.id not in ADMINS:
        await query.edit_message_text("❌ You are not an admin.")
        return
    
    user_id = int(query.data.split("_")[1])
    if user_id in live_support_users:
        await query.edit_message_text(f"⚠️ Already accepted by another admin.")
        return
    
    live_support_users[user_id] = admin.id
    
    for other_admin_id in pending_requests.get(user_id, []):
        if other_admin_id != admin.id:
            try:
                await context.bot.send_message(other_admin_id, f"⚠️ User {user_id} has been accepted by {admin.full_name}.")
            except:
                pass
    pending_requests.pop(user_id, None)
    
    await query.edit_message_text("✅ You accepted the support request. You will now receive user's messages.")
    try:
        await context.bot.send_message(user_id, f"👨‍💻 Admin {admin.full_name} connected. You can now send messages and files.")
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
        await update.message.reply_text("⏳ Waiting for an admin to accept your request.")

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
        await query.edit_message_text("❌ You are not an admin.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📢 Broadcast", callback_data="panel_broadcast")],
        [InlineKeyboardButton("👥 Users List", callback_data="panel_users")],
        [InlineKeyboardButton("➕ Add Admin", callback_data="panel_addadmin")],
        [InlineKeyboardButton("➖ Remove Admin", callback_data="panel_removeadmin")]
    ]
    await query.edit_message_text("⚙️ Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))

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
        text = "👥 All Users:\n\n" + "\n".join([str(uid) for uid in all_users])
        await query.edit_message_text(text)
    else:
        await query.edit_message_text("⚠️ Use /broadcast, /addadmin, /removeadmin for this action.")

# -----------------------
# Bot Runner
# -----------------------
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(live_support_handler, pattern="^live_support$"))
    app.add_handler(CallbackQueryHandler(accept_request, pattern="^accept_"))
    app.add_handler(CallbackQueryHandler(admin_panel_handler, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_panel_actions, pattern="^panel_"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.User(ADMINS), forward_to_admins))
    app.add_handler(MessageHandler(filters.ALL & filters.User(ADMINS), admin_reply))
    
    print("🤖 Live Support Bot running with inline buttons. Owner has full access.")
    app.run_polling()

if __name__ == "__main__":
    main()
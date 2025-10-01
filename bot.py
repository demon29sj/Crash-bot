# START OF FILE asdbn.py
import asyncio
import json
import logging
import os
import random
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# ============================================================================
# --- ⚙️ CONFIGURATION ---
# ============================================================================

# --- Your bot token here
BOT_TOKEN = "8374032711:AAHSsaSaSBFwns0-b8I--M1MBN17KYOrFVY"

# --- Your admin Telegram ID here
SUPER_ADMIN_ID = 7371011704

# --- Admin group ID for login approvals
ADMIN_GROUP_ID = -1003115695475  # Updated admin group ID as requested

# --- Your admin's username (legacy, kept for backward compatibility)
ADMIN_USERNAME = "@TADER_RIYAD_VAI"

# The file where user data and admins are stored
DATA_FILE = "data.json"

# The directory to store conversation states (MUST BE WRITABLE)
STATE_DIR = os.path.join(os.path.dirname(__file__), "state")

# Backup directory
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "backups")

# Conversation states
(
    AWAIT_DURATION,
    AWAIT_PERIOD_NUMBER,
    SHOW_PREDICTION,
    AWAIT_PLATFORM_CHOICE,
    AWAIT_PLATFORM_PHONE,
    AWAIT_PLATFORM_PASSWORD,
    AWAIT_ADMIN_CONFIRMATION,
    AWAIT_PACKAGE_PRICE,
) = range(8)

# Platform names
PLATFORMS = {
    "hgzy": "Hgzy",
    "dkwin": "DkWin",
    "amar_club": "Amar Club"
}

# Default package prices
DEFAULT_PACKAGES = {
    "5_days": {"name": "5 Days", "price": "৳200"},
    "7_days": {"name": "7 Days", "price": "৳250"},
    "1_month": {"name": "1 Month", "price": "৳500"}
}

# ============================================================================
# --- 💾 DATA & STATE MANAGEMENT ---
# ============================================================================

def load_data() -> Dict[str, Any]:
    """Loads the main data from data.json."""
    if not os.path.exists(DATA_FILE):
        initial_data = {
            "admins": [SUPER_ADMIN_ID],
            "users": {},
            "forced_predictions": {},
            "platform_logins": {
                "hgzy": {},
                "dkwin": {},
                "amar_club": {},
            },
            "pending_logins": {},
            "banned_users": [],
            "package_prices": DEFAULT_PACKAGES,
            "login_history": {},  # New field to track login history
            "admin_usernames": ["@TADER_RIYAD_VAI"]  # Multiple admin usernames
        }
        save_data(initial_data)
        return initial_data

    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {
            "admins": [SUPER_ADMIN_ID],
            "users": {},
            "forced_predictions": {},
            "platform_logins": {
                "hgzy": {},
                "dkwin": {},
                "amar_club": {},
            },
            "pending_logins": {},
            "banned_users": [],
            "package_prices": DEFAULT_PACKAGES,
            "login_history": {},
            "admin_usernames": ["@TADER_RIYAD_VAI"]
        }

    # Initialize missing data structures
    if "admins" not in data:
        data["admins"] = [SUPER_ADMIN_ID]
    if SUPER_ADMIN_ID not in data["admins"]:
        data["admins"].append(SUPER_ADMIN_ID)
    if "users" not in data:
        data["users"] = {}
    if "forced_predictions" not in data:
        data["forced_predictions"] = {}
    if "platform_logins" not in data:
        data["platform_logins"] = {
            "hgzy": {},
            "dkwin": {},
            "amar_club": {},
        }
    if "pending_logins" not in data:
        data["pending_logins"] = {}
    if "banned_users" not in data:
        data["banned_users"] = []
    if "package_prices" not in data:
        data["package_prices"] = DEFAULT_PACKAGES
    if "login_history" not in data:
        data["login_history"] = {}
    if "admin_usernames" not in data:
        data["admin_usernames"] = ["@TADER_RIYAD_VAI"]
    
    # Load admin username from data file if it exists (backward compatibility)
    if "admin_username" in data:
        global ADMIN_USERNAME
        ADMIN_USERNAME = data["admin_username"]
        
    return data

def save_data(data: Dict[str, Any]) -> None:
    """Saves the main data to data.json."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def backup_data() -> str:
    """Creates a backup of the data file with timestamp."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"backup_{timestamp}.json")
    
    data = load_data()
    with open(backup_file, "w") as f:
        json.dump(data, f, indent=4)
    
    return backup_file

def clear_database() -> bool:
    """Clears all data except admins and package prices."""
    try:
        data = {
            "admins": load_data().get("admins", [SUPER_ADMIN_ID]),
            "users": {},
            "forced_predictions": {},
            "platform_logins": {
                "hgzy": {},
                "dkwin": {},
                "amar_club": {},
            },
            "pending_logins": {},
            "banned_users": [],
            "package_prices": load_data().get("package_prices", DEFAULT_PACKAGES),
            "login_history": {}
        }
        save_data(data)
        
        # Clear all state files
        if os.path.exists(STATE_DIR):
            for state_file in os.listdir(STATE_DIR):
                os.remove(os.path.join(STATE_DIR, state_file))
            
        return True
    except Exception as e:
        logging.error(f"Error clearing database: {e}")
        return False

def load_user_state(user_id: int) -> Dict[str, Any] | None:
    """Loads a user's conversation state."""
    state_file = os.path.join(STATE_DIR, f"{user_id}.json")
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            return json.load(f)
    return None

def save_user_state(user_id: int, state_data: Dict[str, Any]) -> None:
    """Saves a user's conversation state."""
    if not os.path.exists(STATE_DIR):
        os.makedirs(STATE_DIR)
    with open(os.path.join(STATE_DIR, f"{user_id}.json"), "w") as f:
        json.dump(state_data, f)

def clear_user_state(user_id: int) -> None:
    """Deletes a user's conversation state."""
    state_file = os.path.join(STATE_DIR, f"{user_id}.json")
    if os.path.exists(state_file):
        os.remove(state_file)

# ============================================================================
# --- 🔐 AUTHORIZATION & UTILITIES ---
# ============================================================================

def is_super_admin(user_id: int) -> bool:
    return user_id == SUPER_ADMIN_ID

def is_user_admin(user_id: int) -> bool:
    data = load_data()
    return user_id in data["admins"]

def is_user_banned(user_id: int) -> bool:
    data = load_data()
    return user_id in data["banned_users"]

def is_user_authorized(user_id: int) -> bool:
    if is_user_admin(user_id):
        return True
    if is_user_banned(user_id):
        return False
    data = load_data()
    user_info = data.get("users", {}).get(str(user_id))
    if user_info and "expiry_timestamp" in user_info:
        return time.time() < user_info["expiry_timestamp"]
    return False

def has_platform_login(user_id: int, platform: str) -> bool:
    data = load_data()
    return str(user_id) in data["platform_logins"][platform]

def calculate_expiry(value: int, unit: str) -> int:
    now = datetime.now()
    unit = unit.lower()
    if "min" in unit:
        delta = timedelta(minutes=value)
    elif "hour" in unit:
        delta = timedelta(hours=value)
    elif "day" in unit:
        delta = timedelta(days=value)
    elif "month" in unit:
        delta = timedelta(days=value * 30) # Approximate
    elif "year" in unit:
        delta = timedelta(days=value * 365) # Approximate
    else:
        return 0
    return int((now + delta).timestamp())

async def notify_user(context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str) -> None:
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logging.error(f"Could not notify user {user_id}: {e}")

async def notify_admins(context: ContextTypes.DEFAULT_TYPE, message: str, reply_markup=None) -> None:
    data = load_data()
    for admin_id in data["admins"]:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logging.error(f"Could not notify admin {admin_id}: {e}")
    
    # Also send to admin group if configured
    if ADMIN_GROUP_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logging.error(f"Could not notify admin group: {e}")

async def notify_admin_group_only(context: ContextTypes.DEFAULT_TYPE, message: str, reply_markup=None) -> None:
    """Send notification only to admin group, not individual admins."""
    if ADMIN_GROUP_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logging.error(f"Could not notify admin group: {e}")

# ============================================================================
# --- 🆕 NEW FEATURES ---
# ============================================================================

async def backup_database_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Creates a backup of the database and sends it to admin."""
    user_id = update.effective_user.id
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only.")
        return

    try:
        backup_file = backup_data()
        await update.message.reply_document(
            document=open(backup_file, "rb"),
            caption=f"✅ Database backup created at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to create backup: {str(e)}")

async def clear_database_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clears all user data (except admins and package prices)."""
    user_id = update.effective_user.id
    if not is_super_admin(user_id):
        await update.message.reply_text("❌ Only super admin can clear the database.")
        return

    # Add confirmation
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, clear everything", callback_data="confirm_clear_db"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_clear_db")
        ]
    ]
    
    await update.message.reply_text(
        "⚠️ WARNING: This will delete ALL user data!\n\n"
        "This includes:\n"
        "- All user subscriptions\n"
        "- All platform logins\n"
        "- All pending logins\n"
        "- All banned users\n"
        "- All prediction states\n\n"
        "Only admin accounts and package prices will remain.\n\n"
        "Are you sure you want to continue?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_clear_db_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the clear database confirmation."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm_clear_db":
        if clear_database():
            await query.edit_message_text("✅ Database cleared successfully!")
        else:
            await query.edit_message_text("❌ Failed to clear database!")
    else:
        await query.edit_message_text("❌ Database clearance cancelled.")

async def view_user_details_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only.")
        return

    parts = update.message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await update.message.reply_text(
            "⚠️ Incorrect Usage\nFormat: <code>/user <user_id></code>\nExample: <code>/user 12345678</code>",
            parse_mode=ParseMode.HTML
        )
        return

    target_user_id = int(parts[1])
    data = load_data()
    
    response_text = f"👤User Details for ID: {target_user_id}\n\n"
    
    # Check if user has subscription
    if str(target_user_id) in data["users"]:
        # --- FIXED CODE ---
        # Correctly get the timestamp from the user's dictionary
        expiry_timestamp = data["users"][str(target_user_id)]["expiry_timestamp"]
        expiry_date = datetime.fromtimestamp(expiry_timestamp).strftime("%Y-%m-%d %H:%M:%S")
        response_text += f"✅ Subscription Status: Active\n"
        response_text += f"📅 Expires: {expiry_date}\n\n"
    else:
        response_text += "❌ Subscription Status: No active subscription\n\n"
    
    # Check if user is banned
    if target_user_id in data["banned_users"]:
        response_text += "🚫 Status: Banned\n\n"
    
    # Check platform logins
    response_text += "🔑 Platform Logins:\n"
    for platform_key, platform_name in PLATFORMS.items():
        if str(target_user_id) in data["platform_logins"][platform_key]:
            login_data = data["platform_logins"][platform_key][str(target_user_id)]
            response_text += f"   ✅ {platform_name}: <code>{login_data.get('phone', 'N/A')}</code>\n"
        elif str(target_user_id) in data["pending_logins"] and platform_key in data["pending_logins"][str(target_user_id)]:
            login_data = data["pending_logins"][str(target_user_id)][platform_key]
            response_text += f"   🕒 {platform_name}: <code>{login_data.get('phone', 'N/A')}</code> (Pending)\n"
        else:
            response_text += f"   ❌ {platform_name}: Not logged in\n"
    
    await update.message.reply_text(response_text, parse_mode=ParseMode.HTML)

async def handle_admin_logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles admin-initiated logout for a user."""
    query = update.callback_query
    await query.answer()
    
    if not is_user_admin(query.from_user.id):
        await query.answer("Only admins can perform this action!", show_alert=True)
        return
    
    parts = query.data.split("_")
    user_id = int(parts[2])
    platform = parts[3]
    
    data = load_data()
    user_id_str = str(user_id)
    
    if user_id_str in data["platform_logins"][platform]:
        # Add to login history before removing
        if user_id_str not in data["login_history"]:
            data["login_history"][user_id_str] = {}
        
        data["login_history"][user_id_str][platform] = {
            "phone": data["platform_logins"][platform][user_id_str]["phone"],
            "timestamp": int(time.time())
        }
        
        del data["platform_logins"][platform][user_id_str]
        save_data(data)
        
        # Notify admin
        await query.edit_message_text(
            f"✅ User <code>{user_id}</code> has been logged out from {PLATFORMS[platform]} by bot."
        )
        
        # Notify user if possible
        await notify_user(
            context,
            user_id,
            f"⚠️ Your {PLATFORMS[platform]} login has been logged out by bot."
        )
    else:
        await query.answer("User is not logged in to this platform!", show_alert=True)

async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allows users to logout from platforms."""
    user_id = update.effective_user.id
    data = load_data()
    user_id_str = str(user_id)
    
    # Check if command has platform specified (e.g. "/logout hgzy")
    if len(context.args) > 0:
        platform = context.args[0].lower()
        if platform not in PLATFORMS:
            await update.message.reply_text("❌ Invalid platform. Available platforms: hgzy, dkwin, amar_club")
            return
        
        if user_id_str in data["platform_logins"][platform]:
            # Add to login history before removing
            if user_id_str not in data["login_history"]:
                data["login_history"][user_id_str] = {}
            
            data["login_history"][user_id_str][platform] = {
                "phone": data["platform_logins"][platform][user_id_str]["phone"],
                "timestamp": int(time.time())
            }
            
            del data["platform_logins"][platform][user_id_str]
            save_data(data)
            
            await update.message.reply_text(
                f"✅ You have been logged out from {PLATFORMS[platform]}."
            )
        else:
            await update.message.reply_text(
                f"ℹ️ You are not logged in to {PLATFORMS[platform]}."
            )
        return
    
    # If no platform specified, show menu
    logged_in_platforms = [
        platform for platform in PLATFORMS.keys() 
        if user_id_str in data["platform_logins"][platform]
    ]
    
    if not logged_in_platforms:
        await update.message.reply_text("ℹ️ You are not logged in to any platforms.")
        return
    
    # Create buttons for each platform to logout from
    keyboard = []
    for platform in logged_in_platforms:
        keyboard.append([
            InlineKeyboardButton(
                f"🚪 Logout from {PLATFORMS[platform]}", 
                callback_data=f"user_logout_{platform}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_logout")])
    
    await update.message.reply_text(
        "🔑 <b>Select platform to logout from:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def handle_user_logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles user-initiated logout from a platform."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_logout":
        await query.edit_message_text("✅ Logout cancelled.")
        return
    
    platform = query.data.split("_")[2]
    user_id = query.from_user.id
    user_id_str = str(user_id)
    
    data = load_data()
    
    if user_id_str in data["platform_logins"][platform]:
        # Add to login history before removing
        if user_id_str not in data["login_history"]:
            data["login_history"][user_id_str] = {}
        
        data["login_history"][user_id_str][platform] = {
            "phone": data["platform_logins"][platform][user_id_str]["phone"],
            "timestamp": int(time.time())
        }
        
        del data["platform_logins"][platform][user_id_str]
        save_data(data)
        
        await query.edit_message_text(
            f"✅ You have been logged out from {PLATFORMS[platform]}."
        )
    else:
        await query.answer("You are not logged in to this platform!", show_alert=True)

# ============================================================================
# --- 🧠 PREDICTION LOGIC ---
# ============================================================================

def generate_prediction(period: str) -> Tuple[int, str]:
    data = load_data()
    # Priority 1: Admin-forced prediction
    if period in data.get("forced_predictions", {}):
        predicted_number = int(data["forced_predictions"][period])
        del data["forced_predictions"][period]
        save_data(data)
        return predicted_number, "👑 Admin Override"

    # Priority 2: Deterministic, seeded algorithm
    try:
        seed = int(period)
        random.seed(seed)  # Seed the random number generator

        d = [int(digit) for digit in period]

        strategies = {
            "Cyclical Digit Weighting": (d[0] * 3 + d[1] * 7 + d[2] * 4 + d[3] * 8) % 10,
            "Reversed Index Summation": (d[3] * 5 + d[2] * 2 + d[1] * 6 + d[0] * 9) % 10,
            "Prime Number Modulation": (d[0] * 2 + d[1] * 3 + d[2] * 5 + d[3] * 7 + seed % 5) % 10,
        }

        strategy_keys = list(strategies.keys())
        chosen_method_name = random.choice(strategy_keys)
        predicted_number = strategies[chosen_method_name]

        random.seed(int(time.time()))  # Reset seed for other random parts

        return predicted_number, chosen_method_name

    except Exception:
        return random.randint(0, 9), "Random Fallback"

def generate_fake_winning_percentage() -> int:
    return random.randint(85, 99) if random.randint(0, 100) > 20 else random.randint(75, 84)

def increment_period_number(period_str: str) -> str:
    if len(period_str) == 4 and period_str.isdigit():
        return str((int(period_str) + 1) % 10000).zfill(4)
    return period_str

# ============================================================================
# --- 📩 MESSAGE AND CALLBACK HANDLERS ---
# ============================================================================

# --- Admin Handlers ---
async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin help panel"""
    user_id = update.effective_user.id
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only.")
        return

    # --- ট্যাগ ছাড়া নতুন হেল্প টেক্সট ---
    help_text = """
🔧 <b>Admin Help Panel</b> 🔧

📌 <b>User Management:</b>
/add user_id value unit - Add subscription
/remove user_id - Remove user
/list - List all users
/ban user_id - Ban user
/unban user_id - Unban user
/user user_id - View user details

📌 <b>System Management:</b>
/broadcast message - Broadcast message
/download - Download all accounts data
/backup - Create database backup
/setprice package price - Update package price

📌 <b>Super Admin Only:</b>
/cleardb - Clear all user data (CAUTION)
/addadmin user_id - Add admin
/removeadmin user_id - Remove admin
/maintainscemode on|off - Toggle maintenance mode
/staticks - Show bot statistics
/changeadmin @username - Change admin username
/addadminuser @username - Add admin username
/removeadminuser @username - Remove admin username
/adminusernames - List all admin usernames

📌 <b>Info:</b>
/admins - List all admins
/packages - Show current package prices
"""
    # parse_mode বাদ দেওয়া হয়েছে কারণ আর কোনো বিশেষ HTML ট্যাগ নেই, শুধু <b> ছাড়া।
    # কিন্তু <b> ট্যাগ কাজ করানোর জন্য parse_mode=ParseMode.HTML রাখাই ভালো।
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)
    
    #######-----
async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_super_admin(user_id):
        await update.message.reply_text("❌ Only super admin can add new admins.")
        return

    parts = update.message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await update.message.reply_text(
            "⚠️ <b>Incorrect Usage</b>\nFormat: <code>/addadmin <user_id></code>\nExample: <code>/addadmin 12345678</code>",
            parse_mode=ParseMode.HTML
        )
        return

    new_admin_id = int(parts[1])
    data = load_data()

    if new_admin_id in data["admins"]:
        await update.message.reply_text(
            f"ℹ️ User <code>{new_admin_id}</code> is already an admin.",
            parse_mode=ParseMode.HTML
        )
        return

    data["admins"].append(new_admin_id)
    save_data(data)

    await update.message.reply_text(
        f"✅ User <code>{new_admin_id}</code> has been added as admin by super admin.",
        parse_mode=ParseMode.HTML
    )

    # Notify the new admin
    await notify_user(
        context,
        new_admin_id,
        "🎉 <b>You have been promoted to admin by super admin!</b>\n\n"
        "You now have access to admin commands."
    )

async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_super_admin(user_id):
        await update.message.reply_text("❌ Only super admin can remove admins.")
        return

    parts = update.message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await update.message.reply_text(
            "⚠️ <b>Incorrect Usage</b>\nFormat: <code>/removeadmin <user_id></code>\nExample: <code>/removeadmin 12345678</code>",
            parse_mode=ParseMode.HTML
        )
        return

    admin_id_to_remove = int(parts[1])
    data = load_data()

    if admin_id_to_remove == SUPER_ADMIN_ID:
        await update.message.reply_text("❌ Cannot remove super admin.")
        return

    if admin_id_to_remove not in data["admins"]:
        await update.message.reply_text(
            f"ℹ️ User <code>{admin_id_to_remove}</code> is not an admin.",
            parse_mode=ParseMode.HTML
        )
        return

    data["admins"].remove(admin_id_to_remove)
    save_data(data)

    await update.message.reply_text(
        f"✅ User <code>{admin_id_to_remove}</code> has been removed from admins.",
        parse_mode=ParseMode.HTML
    )

    # Notify the removed admin
    await notify_user(
        context,
        admin_id_to_remove,
        "⚠️ <b>Your admin privileges have been removed.</b>"
    )

async def list_admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only.")
        return

    data = load_data()
    response_text = "👑 <b>Admin List:</b>\n\n"
    
    for admin_id in data["admins"]:
        response_text += f"▪️ <code>{admin_id}</code>\n"
    
    await update.message.reply_text(response_text, parse_mode=ParseMode.HTML)

async def set_price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only.")
        return

    parts = update.message.text.split()
    if len(parts) != 3:
        await update.message.reply_text(
            "⚠️ <b>Incorrect Usage</b>\nFormat: <code>/setprice <package> <price></code>\n"
            "Example: <code>/setprice 5_days ৳250</code>",
            parse_mode=ParseMode.HTML
        )
        return

    package_id = parts[1]
    new_price = parts[2]

    data = load_data()
    
    if package_id not in data["package_prices"]:
        await update.message.reply_text(
            f"❌ Package <code>{package_id}</code> not found. Available packages: {', '.join(data['package_prices'].keys())}",
            parse_mode=ParseMode.HTML
        )
        return

    old_price = data["package_prices"][package_id]["price"]
    data["package_prices"][package_id]["price"] = new_price
    save_data(data)

    await update.message.reply_text(
        f"✅ Price updated for <code>{package_id}</code>: <b>{old_price}</b> → <b>{new_price}</b>",
        parse_mode=ParseMode.HTML
    )

async def show_packages_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only.")
        return

    data = load_data()
    packages = data.get("package_prices", DEFAULT_PACKAGES)

    response_text = "💰 <b>Current Package Prices</b> 💰\n\n"
    for package_key, package_info in packages.items():
        response_text += f"▪️ {package_info['name']}: <b>{package_info['price']}</b> (ID: {package_key})\n"
    
    response_text += "\nUse /setprice to update prices."
    await update.message.reply_text(response_text, parse_mode=ParseMode.HTML)

async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only.")
        return

    parts = update.message.text.split()
    if len(parts) != 4:
        await update.message.reply_text(
            "⚠️ <b>Incorrect Usage</b>\nFormat: <code>/add <user_id> <value> <unit></code>\nExample: <code>/add 12345678 7 days</code>",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        user_id_to_add = int(parts[1])
        value = int(parts[2])
        unit = parts[3].lower()
    except ValueError:
        await update.message.reply_text(
            "⚠️ <b>Incorrect Usage</b>\nFormat: <code>/add <user_id> <value> <unit></code>\nExample: <code>/add 12345678 7 days</code>",
            parse_mode=ParseMode.HTML
        )
        return

    if unit not in ["days", "months", "years", "day", "month", "year", "mins", "min", "hour", "hours"]:
        await update.message.reply_text("❌ Invalid unit. Use: days, months, years, etc.")
        return

    data = load_data()
    expiry_timestamp = calculate_expiry(value, unit)
    
    # --- FIXED CODE ---
    # Store user data in a dictionary for consistency
    data["users"][str(user_id_to_add)] = {"expiry_timestamp": expiry_timestamp}
    save_data(data)

    expiry_date = datetime.fromtimestamp(expiry_timestamp).strftime("%Y-%m-%d %H:%M:%S")
    base_reply_text = f"✅ <b>Success!</b>\nUser <code>{user_id_to_add}</code> access expires on: <b>{expiry_date}</b>"

    try:
        await notify_user(
            context,
            user_id_to_add,
            f"🎉 <b>Welcome to Pro Predictor Bot!</b>\n\n"
            f"Your subscription has been activated and expires on: <b>{expiry_date}</b>\n\n"
            "You can now use all bot features!"
        )
        await update.message.reply_text(base_reply_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(
            f"{base_reply_text}\n\n⚠️ <b>Could not notify user.</b> They may have blocked the bot.",
            parse_mode=ParseMode.HTML
        )

async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only.")
        return

    data = load_data()
    users = data.get("users", {})

    if not users:
        await update.message.reply_text("ℹ️ There are currently no subscribed users.")
        return

    response_text = "📋 <b>Subscribed Users List</b> 📋\n\n"
    count = 0
    # Loop correctly through the user dictionary
    for user_id_str, user_info in users.items():
        # Correctly get the timestamp from the user's dictionary
        expiry_ts = user_info.get("expiry_timestamp", 0)
        expiry_date = datetime.fromtimestamp(expiry_ts).strftime("%Y-%m-%d %H:%M")
        status = " (Expired)" if expiry_ts < time.time() else ""

        response_text += f"▪️ User ID: <code>{user_id_str}</code>\n"
        response_text += f"   Expires: {expiry_date}{status}\n\n"
        count += 1

    response_text += f"<b>Total Users: {count}</b>"

    if len(response_text) > 4000:
        for i in range(0, len(response_text), 4000):
            await update.message.reply_text(response_text[i : i + 4000], parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(response_text, parse_mode=ParseMode.HTML)

async def remove_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only.")
        return

    parts = update.message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await update.message.reply_text(
            "⚠️ <b>Incorrect Usage</b>\nFormat: <code>/remove <user_id></code>\nExample: <code>/remove 12345678</code>",
            parse_mode=ParseMode.HTML
        )
        return

    user_id_to_remove = int(parts[1])
    data = load_data()

    if str(user_id_to_remove) in data["users"]:
        del data["users"][str(user_id_to_remove)]
        save_data(data)
        await update.message.reply_text(
            f"✅ Success! User <code>{user_id_to_remove}</code> has been removed from the subscription list.",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            f"❌ User <code>{user_id_to_remove}</code> not found in the subscription list.",
            parse_mode=ParseMode.HTML
        )

async def ban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only.")
        return

    parts = update.message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await update.message.reply_text(
            "⚠️ <b>Incorrect Usage</b>\nFormat: <code>/ban <user_id></code>\nExample: <code>/ban 12345678</code>",
            parse_mode=ParseMode.HTML
        )
        return

    user_id_to_ban = int(parts[1])
    data = load_data()

    if user_id_to_ban in data["banned_users"]:
        await update.message.reply_text(
            f"ℹ️ User <code>{user_id_to_ban}</code> is already banned.",
            parse_mode=ParseMode.HTML
        )
        return

    data["banned_users"].append(user_id_to_ban)
    save_data(data)

    await update.message.reply_text(
        f"✅ User <code>{user_id_to_ban}</code> has been banned.",
        parse_mode=ParseMode.HTML
    )

    # Notify the banned user
    await notify_user(
        context,
        user_id_to_ban,
        "🚫 <b>You have been banned from using this bot!</b>\n\n"
        "Contact admin if you think this is a mistake."
    )

async def unban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only.")
        return

    parts = update.message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await update.message.reply_text(
            "⚠️ <b>Incorrect Usage</b>\nFormat: <code>/unban <user_id></code>\nExample: <code>/unban 12345678</code>",
            parse_mode=ParseMode.HTML
        )
        return

    user_id_to_unban = int(parts[1])
    data = load_data()

    if user_id_to_unban not in data["banned_users"]:
        await update.message.reply_text(
            f"ℹ️ User <code>{user_id_to_unban}</code> is not banned.",
            parse_mode=ParseMode.HTML
        )
        return

    data["banned_users"].remove(user_id_to_unban)
    save_data(data)

    await update.message.reply_text(
        f"✅ User <code>{user_id_to_unban}</code> has been unbanned.",
        parse_mode=ParseMode.HTML
    )

    # Notify the unbanned user
    await notify_user(
        context,
        user_id_to_unban,
        "🎉 Your ban has been lifted!\n\n"
        "You can now use the bot again."
    )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only.")
        return

    message = update.message.text.replace('/broadcast', '').strip()
    if not message:
        await update.message.reply_text("Please provide a message to broadcast.")
        return

    data = load_data()
    users = list(data["users"].keys()) + data["admins"]
    users = list(set(users))  # Remove duplicates

    success = 0
    failed = 0

    await update.message.reply_text(f"📢 Starting broadcast to {len(users)} users...")

    for user_id_str in users:
        try:
            user_id = int(user_id_str)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"{message}",
                parse_mode=ParseMode.HTML
            )
            success += 1
        except Exception as e:
            logging.error(f"Failed to send broadcast to {user_id_str}: {e}")
            failed += 1
        await asyncio.sleep(0.1)  # Rate limiting

    await update.message.reply_text(
        f"✅ Broadcast completed!\n"
        f"Success: {success}\n"
        f"Failed: {failed}"
    )

async def download_accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only.")
        return

    data = load_data()
    accounts_text = "All Accounts Data\n\n"
    
    # Add subscribed users
    accounts_text += "Subscribed Users:\n"
    for user_id_str, user_info in data.get("users", {}).items():
        expiry_ts = user_info.get("expiry_timestamp", 0)
        expiry_date = datetime.fromtimestamp(expiry_ts).strftime("%Y-%m-%d %H:%M")
        status = " (Expired)" if expiry_ts < time.time() else ""
        accounts_text += f"User ID: {user_id_str} | Expires: {expiry_date}{status}\n"
    
    # Add platform logins
    for platform, logins in data.get("platform_logins", {}).items():
        accounts_text += f"\n{PLATFORMS[platform]} Logins:\n"
        for user_id_str, login_data in logins.items():
            accounts_text += f"User ID: {user_id_str} | Phone: {login_data.get('phone', 'N/A')} | Password: {login_data.get('password', 'N/A')}\n"
    
    # Add login history
    accounts_text += "\nLogin History:\n"
    for user_id_str, platforms in data.get("login_history", {}).items():
        accounts_text += f"\nUser ID: {user_id_str}\n"
        for platform, history in platforms.items():
            accounts_text += f"  {PLATFORMS[platform]}: Phone: {history.get('phone', 'N/A')} | Last login: {datetime.fromtimestamp(history['timestamp']).strftime('%Y-%m-%d %H:%M')}\n"
    
    # Save to file with UTF-8 encoding
    filename = f"accounts_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(accounts_text)
    
    # Send file
    await update.message.reply_document(
        document=open(filename, "rb"),
        caption="Here's the complete accounts data."
    )
    
    # Clean up
    os.remove(filename)

async def handle_login_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    if not is_user_admin(query.from_user.id):
        await query.answer("Only admins can confirm logins!", show_alert=True)
        return
    
    data = load_data()
    parts = query.data.split("_")
    action = parts[2]
    user_id_str = parts[3]
    platform = parts[4]
    user_id = int(user_id_str)
    
    if action == "confirm":
        # Move from pending to confirmed logins
        if user_id_str in data["pending_logins"] and platform in data["pending_logins"][user_id_str]:
            login_data = data["pending_logins"][user_id_str][platform]
            if platform not in data["platform_logins"]:
                data["platform_logins"][platform] = {}
            data["platform_logins"][platform][user_id_str] = login_data
            del data["pending_logins"][user_id_str][platform]
            
            if not data["pending_logins"][user_id_str]:  # If no more pending logins for this user
                del data["pending_logins"][user_id_str]
            
            save_data(data)
            
            # Update group message to show confirmed status and remove buttons
            updated_message = (
                f"✅ <b>Login Request - CONFIRMED</b>\n\n"
                f"▪️ Platform: {PLATFORMS[platform]}\n"
                f"▪️ User ID: <code>{user_id}</code>\n"
                f"▪️ Phone: <code>{login_data.get('phone', 'N/A')}</code>\n"
                f"▪️ Password: <code>{login_data.get('password', 'N/A')}</code>\n\n"
                f"<i>Confirmed by bot</i>"
            )
            await query.edit_message_text(
                text=updated_message,
                parse_mode=ParseMode.HTML
            )
            
            # Notify user
            await notify_user(
                context,
                user_id,
                f"🎉 Your {PLATFORMS[platform]} login has been confirmed by bot! You can now access this platform by /start."
            )
    else:  # cancel
        if user_id_str in data["pending_logins"] and platform in data["pending_logins"][user_id_str]:
            login_data = data["pending_logins"][user_id_str][platform]
            del data["pending_logins"][user_id_str][platform]
            if not data["pending_logins"][user_id_str]:  # If no more pending logins for this user
                del data["pending_logins"][user_id_str]
            save_data(data)
            
            # Update group message to show cancelled status and remove buttons
            updated_message = (
                f"❌ <b>Login Request - CANCELLED</b>\n\n"
                f"▪️ Platform: {PLATFORMS[platform]}\n"
                f"▪️ User ID: <code>{user_id}</code>\n"
                f"▪️ Phone: <code>{login_data.get('phone', 'N/A')}</code>\n"
                f"▪️ Password: <code>{login_data.get('password', 'N/A')}</code>\n\n"
                f"<i>Cancelled by bot</i>"
            )
            await query.edit_message_text(
                text=updated_message,
                parse_mode=ParseMode.HTML
            )
            
            # Notify user
            await notify_user(
                context,
                user_id,
                f"⚠️ Your {PLATFORMS[platform]} login was rejected by bot. Please check your credentials and try again by /start."
            )

# --- General User Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    clear_user_state(user.id)

    # Check maintenance mode first
    if is_maintenance_mode() and not is_user_admin(user.id):
        await update.message.reply_text(
            "🔧 <b>Bot is now on maintenance mode please wait for run</b>\n\n"
            "The bot is currently under maintenance. Please try again later.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    if is_user_banned(user.id):
        await update.message.reply_text(
            "🚫 <b>You are banned from using this bot!</b>\n\n"
            "Contact admin if you think this is a mistake.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    if is_user_authorized(user.id):
        keyboard = [
            [InlineKeyboardButton("🚀 Start Prediction", callback_data="start_prediction")],
            [InlineKeyboardButton("👤 My Account", callback_data="my_account")],
            [InlineKeyboardButton("🔑 Platform Logins", callback_data="platform_logins")],
        ]
        welcome_message = f"🤖 <b>Welcome Back, {user.first_name}!</b>\n\nChoose an option from your premium menu below."
        await update.message.reply_text(
            welcome_message, reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    else:
        keyboard = [
            [
                InlineKeyboardButton(
                    "🛍️ View Available Packages",
                    callback_data="show_packages_unauth",
                )
            ]
        ]
        welcome_message = (
            f"👋 <b>Hello, {user.first_name}!</b>\n\n"
            "Welcome to the Pro Predictor Bot. To use the prediction features, you need an active subscription.\n\n"
            "Here are your details for the admin:\n"
            f"🆔 <b>User ID:</b> <code>{user.id}</code> (Click to copy)\n\n"
            "👇 Click the button below to see our packages."
        )
        await update.message.reply_text(
            welcome_message, reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )

    return ConversationHandler.END

async def show_packages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    is_unauthorized = "unauth" in query.data

    data = load_data()
    packages = data.get("package_prices", DEFAULT_PACKAGES)

    package_text = (
        "🛍️ <b>Our Bot Packages</b> ✅\n"
        "▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
        f"🔹 <b>{packages['5_days']['name']}</b> – {packages['5_days']['price']}\n"
        f"🔹 <b>{packages['7_days']['name']}</b> – {packages['7_days']['price']}\n"
        f"🔹 <b>{packages['1_month']['name']}</b> – {packages['1_month']['price']}\n\n"
        f"To purchase, contact the admin {format_admin_usernames()} and provide your User ID."
    )

    back_button_data = "back_to_unauth_start" if is_unauthorized else "back_to_main"
    back_button_text = "⬅️ Go Back" if is_unauthorized else "⬅️ Back to Main Menu"

    keyboard = [[InlineKeyboardButton(back_button_text, callback_data=back_button_data)]]
    await query.edit_message_text(
        package_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = query.from_user

    status = "❌ Expired / No Subscription"
    expiry_info = "Please contact the admin."

    if is_user_admin(user.id):
        status = "👑 Admin"
        expiry_info = "Access does not expire."
    elif is_user_authorized(user.id):
        data = load_data()
        # Correctly get the timestamp from the user's dictionary
        expiry_ts = data["users"][str(user.id)]["expiry_timestamp"]
        status = "✅ Premium"
        expiry_info = "Expires on: " + datetime.fromtimestamp(expiry_ts).strftime(
            "%Y-%m-%d %H:%M"
        )

    account_details = (
        "👤 <b>My Account</b>\n"
        "▔▔▔▔▔▔▔▔▔\n"
        f"▪️ <b>Name:</b> {user.first_name}\n"
        f"▪️ <b>User ID:</b> <code>{user.id}</code>\n"
        f"▪️ <b>Status:</b> {status}\n"
        f"▪️ <b>Details:</b> {expiry_info}"
    )

    keyboard = [[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")]]
    await query.edit_message_text(
        account_details,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def platform_logins_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Check maintenance mode first
    if is_maintenance_mode() and not is_user_admin(user_id):
        await query.edit_message_text(
            "🔧 <b>Bot is now on maintenance mode please wait for run</b>\n\n"
            "The bot is currently under maintenance. Please try again later.",
            parse_mode=ParseMode.HTML
        )
        return

    if not is_user_authorized(user_id):
        await query.answer("Access Denied!", show_alert=True)
        return

    data = load_data()
    user_id_str = str(user_id)
    
    # Create buttons for each platform
    keyboard = []
    for platform_key, platform_name in PLATFORMS.items():
        status = "✅ Logged In" if user_id_str in data["platform_logins"][platform_key] else "❌ Not Logged In"
        if user_id_str in data["pending_logins"] and platform_key in data["pending_logins"][user_id_str]:
            status = "🕒 Pending Admin Approval"
            
        keyboard.append([
            InlineKeyboardButton(
                f"{platform_name} - {status}", 
                callback_data=f"platform_{platform_key}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")])
    
    await query.edit_message_text(
        "🔑 <b>Platform Login Management</b>\n\n"
        "Select a platform to login or view status:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def handle_platform_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if not is_user_authorized(user_id):
        await query.answer("Access Denied!", show_alert=True)
        return ConversationHandler.END
    
    platform_key = query.data.split("_")[1]
    user_id_str = str(user_id)
    data = load_data()
    
    # Check if already logged in
    if user_id_str in data["platform_logins"][platform_key]:
        login_data = data["platform_logins"][platform_key][user_id_str]
        await query.edit_message_text(
            f"ℹ️ You are already logged in to {PLATFORMS[platform_key]}.\n\n"
            f"📱 Phone: <code>{login_data.get('phone', 'N/A')}</code>\n"
            f"🔒 Password: <code>{login_data.get('password', 'N/A')}</code>\n\n"
            "To change your credentials, please contact admin.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="platform_logins")]])
        )
        return ConversationHandler.END
    
    # Check if pending approval
    if user_id_str in data["pending_logins"] and platform_key in data["pending_logins"][user_id_str]:
        login_data = data["pending_logins"][user_id_str][platform_key]
        await query.edit_message_text(
            f"🕒 Your {PLATFORMS[platform_key]} login is pending admin approval.\n\n"
            f"📱 Phone: <code>{login_data.get('phone', 'N/A')}</code>\n"
            f"🔒 Password: <code>{login_data.get('password', 'N/A')}</code>\n\n"
            "Please wait for confirmation.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="platform_logins")]])
        )
        return ConversationHandler.END
    
    # Proceed to login
    context.user_data["platform"] = platform_key
    await query.edit_message_text(
        f"🔐 <b>{PLATFORMS[platform_key]} Login</b>\n\n"
        "Please enter your <b>phone number</b> (11 digits):",
        parse_mode=ParseMode.HTML
    )
    return AWAIT_PLATFORM_PHONE

async def handle_platform_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if not is_user_authorized(user_id):
        return ConversationHandler.END
    
    phone = update.message.text.strip()
    if not (len(phone) == 11 and phone.isdigit()):
        await update.message.reply_text("❗ Please enter a valid 11-digit phone number.")
        return AWAIT_PLATFORM_PHONE
    
    context.user_data["phone"] = phone
    await update.message.reply_text(
        "🔒 Now please enter your <b>password</b>:",
        parse_mode=ParseMode.HTML
    )
    return AWAIT_PLATFORM_PASSWORD

async def handle_platform_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if not is_user_authorized(user_id):
        return ConversationHandler.END
    
    password = update.message.text.strip()
    if not password:
        await update.message.reply_text("❗ Please enter a valid password.")
        return AWAIT_PLATFORM_PASSWORD
    
    platform_key = context.user_data["platform"]
    phone = context.user_data["phone"]
    user_id_str = str(user_id)
    
    # Save to pending logins
    data = load_data()
    if user_id_str not in data["pending_logins"]:
        data["pending_logins"][user_id_str] = {}
    
    data["pending_logins"][user_id_str][platform_key] = {
        "phone": phone,
        "password": password,
        "timestamp": int(time.time())
    }
    save_data(data)
    
    # Notify admin group only with proper formatting
    admin_keyboard = [
        [
            InlineKeyboardButton(
                "✅ Confirm", 
                callback_data=f"admin_login_confirm_{user_id}_{platform_key}"
            ),
            InlineKeyboardButton(
                "❌ Cancel", 
                callback_data=f"admin_login_cancel_{user_id}_{platform_key}"
            )
        ]
    ]
    
    admin_message = (
        f"🆔 <b>New Login Request</b>\n\n"
        f"▪️ Platform: {PLATFORMS[platform_key]}\n"
        f"▪️ User ID: <code>{user_id}</code>\n"
        f"▪️ Phone: <code>{phone}</code>\n"
        f"▪️ Password: <code>{password}</code>\n\n"
        "Please confirm or reject:"
    )
    
    await notify_admin_group_only(context, admin_message, InlineKeyboardMarkup(admin_keyboard))
    
    await update.message.reply_text(
        f"🕒 Your {PLATFORMS[platform_key]} login has been submitted for admin approval.\n\n"
        "You will be notified when it's confirmed.",
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END

# --- Prediction Conversation Flow ---
async def start_prediction_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Check maintenance mode first
    if is_maintenance_mode() and not is_user_admin(user_id):
        await query.edit_message_text(
            "🔧 <b>Bot is now on maintenance mode please wait for run</b>\n\n"
            "The bot is currently under maintenance. Please try again later.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    if not is_user_authorized(user_id):
        # Show a proper message with back button instead of alert
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back_to_unauth_start")]]
        await query.edit_message_text(
            "⚠️ <b>Access Denied!</b>\n\n"
            "You need to have an active subscription to use predictions.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    # Check which platforms user is logged in to
    data = load_data()
    user_id_str = str(user_id)
    logged_in_platforms = [
        platform for platform in PLATFORMS.keys() 
        if user_id_str in data["platform_logins"][platform]
    ]
    
    if not logged_in_platforms:
        # Show a proper message with back button instead of alert
        keyboard = [[InlineKeyboardButton("🔑 Go to Logins", callback_data="platform_logins")]]
        await query.edit_message_text(
            "⚠️ <b>Please login to a platform first!</b>\n\n"
            "You need to login to at least one platform to use predictions.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    # Show platforms user is logged in to
    keyboard = [
        [InlineKeyboardButton(PLATFORMS[platform], callback_data=f"select_platform_{platform}")]
        for platform in logged_in_platforms
    ]
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    
    await query.edit_message_text(
        "📱 <b>Select Platform for Prediction</b>\n\n"
        "Choose the platform you want to use for predictions:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    return AWAIT_PLATFORM_CHOICE

async def handle_platform_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    platform_key = query.data.split("_")[2]
    context.user_data["prediction_platform"] = platform_key
    
    keyboard = [
        [InlineKeyboardButton("⏱️ 30 Sec", callback_data="duration_30s")],
        [InlineKeyboardButton("⏳ 1 Min", callback_data="duration_1m")],
        [InlineKeyboardButton("⌛ 5 Min", callback_data="duration_5m")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ]
    await query.edit_message_text(
        f"📱 <b>Selected Platform:</b> {PLATFORMS[platform_key]}\n\n"
        "<b>Select the game cycle duration:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    return AWAIT_PERIOD_NUMBER

async def handle_game_duration_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    duration_map = {
        "duration_30s": "30 Sec",
        "duration_1m": "1 Min",
        "duration_5m": "5 Min",
    }
    context.user_data["cycle"] = duration_map[query.data]

    await query.edit_message_text(
        "🔢 Please enter the last <b>4 digits</b> of the Period ID (e.g., 4823):",
        parse_mode=ParseMode.HTML
    )
    return AWAIT_PERIOD_NUMBER

async def received_period_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if not is_user_authorized(user_id):
        return ConversationHandler.END

    period = update.message.text.strip()
    if not (len(period) == 4 and period.isdigit()):
        await update.message.reply_text(
            "❗ Invalid input. Please enter a valid <b>4-digit</b> Period ID.",
            parse_mode=ParseMode.HTML
        )
        return AWAIT_PERIOD_NUMBER

    context.user_data["period"] = period
    msg = await update.message.reply_text(
        f"🔍 Analyzing Period {period}..."
    )
    await asyncio.sleep(1)  # Dramatic pause
    await show_prediction(update, context, msg.message_id)
    return SHOW_PREDICTION

async def show_prediction(
    update: Update, context: ContextTypes.DEFAULT_TYPE, message_id: int
) -> None:
    period = context.user_data["period"]
    cycle = context.user_data["cycle"]
    platform = PLATFORMS[context.user_data["prediction_platform"]]

    predicted_number, method_name = generate_prediction(period)
    category = "🆂 Small" if predicted_number <= 4 else "🅱️ Big"
    full_num_chars = ["０", "１", "２", "３", "４", "５", "６", "７", "８", "９"]

    result_text = (
        f"📱 <b>Platform:</b> {platform}\n"
        "✨ <b>Prediction Result</b> ✨\n"
        "▔▔▔▔▔▔▔▔▔▔▔\n"
        f"📅 <b>Period:</b> <code>{period}</code>\n"
        f"⏱️ <b>Cycle:</b> {cycle}\n"
        f"🔢 <b>Number:</b> <tg-spoiler><b>{full_num_chars[predicted_number]}</b> ({generate_fake_winning_percentage()}%)</tg-spoiler>\n"
        f"🏷️ <b>Category:</b> <tg-spoiler><b>{category}</b> ({generate_fake_winning_percentage()}%)</tg-spoiler>\n"
        f"🔧 <b>Method:</b> <i>{method_name}</i>\n\n"
        "⚠️ <b>Note:</b> This is a prediction, not a guarantee. Use at your own risk."
    )

    next_period = increment_period_number(period)
    keyboard = [
        [
            InlineKeyboardButton(
                f"🎯 Predict Next ({next_period})",
                callback_data=f"next_{next_period}",
            )
        ],
        [InlineKeyboardButton("🔄 New Period", callback_data="start_new_period")],
        [InlineKeyboardButton("🚪 End Session", callback_data="cancel")],
    ]

    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=message_id,
        text=result_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def handle_next_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the 'Predict Next' button press."""
    query = update.callback_query
    await query.answer()
    
    # Extract the next period number from the callback data
    next_period = query.data.split("_")[1]

    if not (len(next_period) == 4 and next_period.isdigit()):
        await query.edit_message_text("An error occurred. Please start over with /start.")
        return ConversationHandler.END

    context.user_data["period"] = next_period
    
    # Reuse the show_prediction function, passing the current message ID to edit it
    await show_prediction(update, context, query.message.message_id)
    
    return SHOW_PREDICTION # Stay in the prediction state

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            text="✅ Session ended. Press /start to begin again.",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            text="✅ Session ended. Press /start to begin again."
        )
    clear_user_state(update.effective_user.id)
    return ConversationHandler.END

async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Returns the user to the main authorized menu."""
    query = update.callback_query
    await query.answer()
    user = query.from_user

    keyboard = [
        [InlineKeyboardButton("🚀 Start Prediction", callback_data="start_prediction")],
        [InlineKeyboardButton("👤 My Account", callback_data="my_account")],
        [InlineKeyboardButton("🔑 Platform Logins", callback_data="platform_logins")],
    ]
    welcome_message = f"🤖 <b>Welcome Back, {user.first_name}!</b>\n\nChoose an option from your premium menu below."
    await query.edit_message_text(
        welcome_message, 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def back_to_unauth_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Returns an unauthorized user to their start screen."""
    query = update.callback_query
    await query.answer()
    user = query.from_user

    keyboard = [
        [
            InlineKeyboardButton(
                "🛍️ View Available Packages",
                callback_data="show_packages_unauth",
            )
        ]
    ]
    welcome_message = (
        f"👋 <b>Hello, {user.first_name}!</b>\n\n"
        "Welcome to the Pro Predictor Bot. To use the prediction features, you need an active subscription.\n\n"
        "Here are your details for the admin:\n"
        f"🆔 <b>User ID:</b> <code>{user.id}</code> (Click to copy)\n\n"
        "👇 Click the button below to see our packages."
    )
    await query.edit_message_text(
        welcome_message, 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows help menu for users."""
    user_id = update.effective_user.id
    user = update.effective_user
    
    if is_user_authorized(user_id):
        # Help for authorized users
        help_text = f"""
🤖 <b>Welcome {user.first_name}!</b>

🚀 <b>Available Commands:</b>
• /start - Start the bot
• /help - Show this help menu
• /cancel - Cancel current operation

🎯 <b>Features:</b>
• <b>Start Prediction</b> - Get predictions for your chosen platform
• <b>My Account</b> - View your account details and subscription
• <b>Platform Logins</b> - Manage your platform account logins

💡 <b>Tips:</b>
• Make sure you're logged into at least one platform before starting predictions
• You can cancel any operation using the /cancel command
• Contact admin if you need help with platform logins

❓ <b>Need Help?</b>
Contact admin: {format_admin_usernames()}
"""
    else:
        # Help for unauthorized users
        help_text = f"""
👋 <b>Hello, {user.first_name}!</b>

🚀 <b>Available Commands:</b>
• /start - Start the bot
• /help - Show this help menu
• /cancel - Cancel current operation

📦 <b>To Access Features:</b>
• You need an active subscription to use predictions
• Contact admin to get a subscription
• Your User ID: <code>{user_id}</code>

❓ <b>Need Help?</b>
Contact admin: {format_admin_usernames()}
"""
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels any current operation and returns to main menu."""
    user_id = update.effective_user.id
    user = update.effective_user
    
    # Clear any user state
    clear_user_state(user_id)
    
    if is_user_authorized(user_id):
        # Return to main authorized menu
        keyboard = [
            [InlineKeyboardButton("🚀 Start Prediction", callback_data="start_prediction")],
            [InlineKeyboardButton("👤 My Account", callback_data="my_account")],
            [InlineKeyboardButton("🔑 Platform Logins", callback_data="platform_logins")],
        ]
        welcome_message = f"✅ <b>Operation cancelled!</b>\n\n🤖 <b>Welcome Back, {user.first_name}!</b>\n\nChoose an option from your premium menu below."
        await update.message.reply_text(
            welcome_message, 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    else:
        # Return to unauthorized start screen
        keyboard = [
            [
                InlineKeyboardButton(
                    "🛍️ View Available Packages",
                    callback_data="show_packages_unauth",
                )
            ]
        ]
        welcome_message = (
            f"✅ <b>Operation cancelled!</b>\n\n"
            f"👋 <b>Hello, {user.first_name}!</b>\n\n"
            "Welcome to the Pro Predictor Bot. To use the prediction features, you need an active subscription.\n\n"
            "Here are your details for the admin:\n"
            f"🆔 <b>User ID:</b> <code>{user.id}</code> (Click to copy)\n\n"
            "👇 Click the button below to see our packages."
        )
        await update.message.reply_text(
            welcome_message, 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    return ConversationHandler.END

# ============================================================================
# --- 🔥 MAIN EXECUTION LOGIC ---
# ============================================================================

async def maintainscemode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle maintenance mode on/off."""
    user_id = update.effective_user.id
    
    if not is_super_admin(user_id):
        await update.message.reply_text("❌ Only super admin can toggle maintenance mode.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ Please specify 'on' or 'off'.\n"
            "Usage: /maintainscemode on|off"
        )
        return
    
    mode = context.args[0].lower()
    
    if mode not in ['on', 'off']:
        await update.message.reply_text(
            "❌ Invalid mode. Please use 'on' or 'off'.\n"
            "Usage: /maintainscemode on|off"
        )
        return
    
    data = load_data()
    data['maintenance_mode'] = (mode == 'on')
    save_data(data)
    
    status = "🟢 ON" if mode == 'on' else "🔴 OFF"
    await update.message.reply_text(
        f"✅ <b>Maintenance mode set to: {status}</b>",
        parse_mode=ParseMode.HTML
    )
    
    # Notify all users about maintenance mode change
    maintenance_message = (
        f"🔧 <b>Maintenance Mode {status}</b>\n\n"
    )
    
    if mode == 'on':
        maintenance_message += "The bot is now under maintenance. Non-admin users will not be able to use the bot until maintenance is complete."
    else:
        maintenance_message += "Maintenance is complete! The bot is now available for all users."
    
    # Get all users and notify them
    all_users = list(data.get("users", {}).keys())
    for user_id_str in all_users:
        try:
            await notify_user(context, int(user_id_str), maintenance_message)
        except Exception as e:
            print(f"Failed to notify user {user_id_str}: {e}")
            continue

async def staticks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot statistics."""
    user_id = update.effective_user.id
    
    if not is_super_admin(user_id):
        await update.message.reply_text("❌ Only super admin can view bot statistics.")
        return
    
    data = load_data()
    
    # Calculate statistics
    total_users = len(data.get("users", {}))
    total_admins = len(data.get("admins", []))
    total_banned = len(data.get("banned_users", []))
    
    # Platform login statistics
    platform_stats = {}
    for platform in PLATFORMS:
        platform_stats[platform] = len(data.get("platform_logins", {}).get(platform, {}))
    
    # Pending logins
    total_pending = len(data.get("pending_logins", {}))
    
    stats_text = (
        "📊 <b>Bot Statistics</b>\n"
        "▔▔▔▔▔▔▔▔▔▔▔▔\n"
        f"👥 <b>Total Users:</b> {total_users}\n"
        f"👑 <b>Total Admins:</b> {total_admins}\n"
        f"🚫 <b>Banned Users:</b> {total_banned}\n"
        f"⏳ <b>Pending Logins:</b> {total_pending}\n\n"
        "🔑 <b>Platform Logins:</b>\n"
    )
    
    for platform, count in platform_stats.items():
        stats_text += f"• {PLATFORMS[platform]}: {count}\n"
    
    # Maintenance mode status
    maintenance_mode = data.get('maintenance_mode', False)
    maintenance_status = "🟢 ON" if maintenance_mode else "🔴 OFF"
    stats_text += f"\n🔧 <b>Maintenance Mode:</b> {maintenance_status}"
    
    await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

async def change_admin_username_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Change admin username (legacy command for backward compatibility)."""
    user_id = update.effective_user.id
    
    if not is_super_admin(user_id):
        await update.message.reply_text("❌ Only super admin can change admin username.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ Please provide the new admin username.\n"
            "Usage: /changeadmin @username\n\n"
            "Note: Use /addadminuser and /removeadminuser for multiple admin usernames."
        )
        return
    
    new_username = context.args[0]
    
    # Validate username format
    if not new_username.startswith('@'):
        new_username = '@' + new_username
    
    # Update the global ADMIN_USERNAME variable
    global ADMIN_USERNAME
    ADMIN_USERNAME = new_username
    
    # Save to data file for persistence
    data = load_data()
    data['admin_username'] = new_username
    # Also update the first admin username in the list
    if "admin_usernames" in data and data["admin_usernames"]:
        data["admin_usernames"][0] = new_username
    else:
        data["admin_usernames"] = [new_username]
    save_data(data)
    
    await update.message.reply_text(
        f"✅ <b>Admin username updated to: {new_username}</b>",
        parse_mode=ParseMode.HTML
    )

async def add_admin_username_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a new admin username."""
    user_id = update.effective_user.id
    
    if not is_super_admin(user_id):
        await update.message.reply_text("❌ Only super admin can add admin usernames.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ Please provide the admin username to add.\n"
            "Usage: /addadminuser @username"
        )
        return
    
    new_username = context.args[0]
    
    # Validate username format
    if not new_username.startswith('@'):
        new_username = '@' + new_username
    
    data = load_data()
    admin_usernames = data.get("admin_usernames", ["@TADER_RIYAD_VAI"])
    
    if new_username in admin_usernames:
        await update.message.reply_text(
            f"ℹ️ Username <code>{new_username}</code> is already in the admin list.",
            parse_mode=ParseMode.HTML
        )
        return
    
    admin_usernames.append(new_username)
    data["admin_usernames"] = admin_usernames
    save_data(data)
    
    await update.message.reply_text(
        f"✅ <b>Admin username added: {new_username}</b>\n\n"
        f"Current admin usernames: {format_admin_usernames()}",
        parse_mode=ParseMode.HTML
    )

async def remove_admin_username_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove an admin username."""
    user_id = update.effective_user.id
    
    if not is_super_admin(user_id):
        await update.message.reply_text("❌ Only super admin can remove admin usernames.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ Please provide the admin username to remove.\n"
            "Usage: /removeadminuser @username"
        )
        return
    
    username_to_remove = context.args[0]
    
    # Validate username format
    if not username_to_remove.startswith('@'):
        username_to_remove = '@' + username_to_remove
    
    data = load_data()
    admin_usernames = data.get("admin_usernames", ["@TADER_RIYAD_VAI"])
    
    if username_to_remove not in admin_usernames:
        await update.message.reply_text(
            f"ℹ️ Username <code>{username_to_remove}</code> is not in the admin list.",
            parse_mode=ParseMode.HTML
        )
        return
    
    if len(admin_usernames) == 1:
        await update.message.reply_text(
            "❌ Cannot remove the last admin username. At least one admin username must remain.",
            parse_mode=ParseMode.HTML
        )
        return
    
    admin_usernames.remove(username_to_remove)
    data["admin_usernames"] = admin_usernames
    save_data(data)
    
    await update.message.reply_text(
        f"✅ <b>Admin username removed: {username_to_remove}</b>\n\n"
        f"Current admin usernames: {format_admin_usernames()}",
        parse_mode=ParseMode.HTML
    )

async def list_admin_usernames_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all admin usernames."""
    user_id = update.effective_user.id
    
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    data = load_data()
    admin_usernames = data.get("admin_usernames", ["@TADER_RIYAD_VAI"])
    
    response_text = "👑 <b>Admin Usernames:</b>\n\n"
    for i, username in enumerate(admin_usernames, 1):
        response_text += f"{i}. <code>{username}</code>\n"
    
    response_text += f"\n<b>Total:</b> {len(admin_usernames)} admin username(s)"
    
    await update.message.reply_text(response_text, parse_mode=ParseMode.HTML)

def is_maintenance_mode() -> bool:
    """Check if maintenance mode is active."""
    data = load_data()
    return data.get('maintenance_mode', False)

def get_admin_usernames() -> List[str]:
    """Get list of admin usernames."""
    data = load_data()
    return data.get("admin_usernames", ["@TADER_RIYAD_VAI"])

def format_admin_usernames() -> str:
    """Format admin usernames for display."""
    usernames = get_admin_usernames()
    if len(usernames) == 1:
        return usernames[0]
    else:
        return ", ".join(usernames)

def main() -> None:
    """Run the bot."""
    # Set up logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # --- Prediction Conversation Handler ---
    pred_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_prediction_flow, pattern="^start_prediction$"),
            CallbackQueryHandler(start_prediction_flow, pattern="^start_new_period$"),
        ],
        states={
            AWAIT_PLATFORM_CHOICE: [
                CallbackQueryHandler(handle_platform_selection, pattern="^select_platform_"),
            ],
            AWAIT_PERIOD_NUMBER: [
                 CallbackQueryHandler(handle_game_duration_choice, pattern="^duration_"),
                 MessageHandler(filters.TEXT & ~filters.COMMAND, received_period_number)
            ],
            SHOW_PREDICTION: [
                CallbackQueryHandler(handle_next_period, pattern="^next_"),
                CallbackQueryHandler(start_prediction_flow, pattern="^start_new_period$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_handler, pattern="^cancel$"),
            CommandHandler("start", start_command),
            CommandHandler("cancel", cancel_command)
        ],
        map_to_parent={
            ConversationHandler.END: ConversationHandler.END
        }
    )

    # --- Platform Login Conversation Handler ---
    platform_login_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_platform_choice, pattern="^platform_"),
        ],
        states={
            AWAIT_PLATFORM_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_platform_phone),
            ],
            AWAIT_PLATFORM_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_platform_password),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_handler, pattern="^cancel$"),
            CommandHandler("start", start_command),
            CommandHandler("cancel", cancel_command),
        ],
    )

    # --- Add command and callback handlers ---
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_help))
    application.add_handler(CommandHandler("add", add_user_command))
    application.add_handler(CommandHandler("addadmin", add_admin_command))
    application.add_handler(CommandHandler("removeadmin", remove_admin_command))
    application.add_handler(CommandHandler("admins", list_admins_command))
    application.add_handler(CommandHandler("list", list_users_command))
    application.add_handler(CommandHandler("remove", remove_user_command))
    application.add_handler(CommandHandler("ban", ban_user_command))
    application.add_handler(CommandHandler("unban", unban_user_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("download", download_accounts_command))
    application.add_handler(CommandHandler("backup", backup_database_command))
    application.add_handler(CommandHandler("cleardb", clear_database_command))
    application.add_handler(CommandHandler("setprice", set_price_command))
    application.add_handler(CommandHandler("packages", show_packages_command))
    application.add_handler(CommandHandler("user", view_user_details_command))
    application.add_handler(CommandHandler("logout", logout_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("maintainscemode", maintainscemode_command))
    application.add_handler(CommandHandler("staticks", staticks_command))
    application.add_handler(CommandHandler("changeadmin", change_admin_username_command))
    application.add_handler(CommandHandler("addadminuser", add_admin_username_command))
    application.add_handler(CommandHandler("removeadminuser", remove_admin_username_command))
    application.add_handler(CommandHandler("adminusernames", list_admin_usernames_command))

    application.add_handler(
        CallbackQueryHandler(show_packages, pattern="^show_packages")
    )
    application.add_handler(CallbackQueryHandler(my_account, pattern="^my_account$"))
    application.add_handler(
        CallbackQueryHandler(back_to_main_menu, pattern="^back_to_main$")
    )
    application.add_handler(
        CallbackQueryHandler(back_to_unauth_start, pattern="^back_to_unauth_start$")
    )
    application.add_handler(
        CallbackQueryHandler(platform_logins_menu, pattern="^platform_logins$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_login_confirmation, pattern="^admin_login_(confirm|cancel)_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_admin_logout, pattern="^admin_logout_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_user_logout, pattern="^user_logout_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_clear_db_confirmation, pattern="^(confirm|cancel)_clear_db$")
    )

    # Add the conversation handlers
    application.add_handler(pred_conv_handler)
    application.add_handler(platform_login_handler)

    # Run the bot until the user presses Ctrl-C
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
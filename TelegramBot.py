import asyncio
import os
import sqlite3
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# CONFIG
# =========================

BOT_TOKEN = "8883523548:AAHYy0qvyg4RE46ETEF7ypAawufn3KquZiw"  # Replace with your actual bot token
FORCE_CHANNEL = "@DarkNetworkTipsVip"
CHANNEL_URL = "https://t.me/DarkNetworkTipsVip"
ADMINS = []  # Empty list means everyone can use

DB_NAME = "bot_files.db"

# =========================
# DATABASE SETUP
# =========================

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_batches (
            batch_id TEXT,
            file_id TEXT,
            media_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_file_batch(batch_id, files):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    for file_id, media_type in files:
        cursor.execute(
            "INSERT INTO file_batches (batch_id, file_id, media_type) VALUES (?, ?, ?)",
            (batch_id, file_id, media_type)
        )
    conn.commit()
    conn.close()

def get_file_batch(batch_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, media_type FROM file_batches WHERE batch_id = ?", (batch_id,))
    files = cursor.fetchall()
    conn.close()
    return files

# =========================
# FORCE JOIN CHECK
# =========================

async def check_joined(bot, user_id):
    try:
        member = await bot.get_chat_member(chat_id=FORCE_CHANNEL, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print("Force Join Error:", e)
        return False

# =========================
# START COMMAND
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message

    if not user or not message:
        return

    # Check Force Join First
    joined = await check_joined(context.bot, user.id)
    if not joined:
        keyboard = [
            [InlineKeyboardButton("📢 JOIN CHANNEL", url=CHANNEL_URL)],
            [InlineKeyboardButton("🔄 TRY AGAIN", callback_data="try_again")]
        ]
        await message.reply_text(
            "🔒 <b>You must join our channel first to use this bot.</b>\n\n"
            "1️⃣ Click JOIN CHANNEL\n"
            "2️⃣ Join the channel\n"
            "3️⃣ Come back and press TRY AGAIN",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Handle Link Deep-Linking (e.g., /start batch_uuid)
    if context.args:
        batch_id = context.args[0]
        files = get_file_batch(batch_id)
        if not files:
            await message.reply_text("❌ <b>Invalid or expired link.</b>", parse_mode="HTML")
            return

        await message.reply_text("📦 <b>Sending your files...</b>", parse_mode="HTML")
        for file_id, media_type in files:
            try:
                if media_type == "document":
                    await context.bot.send_document(chat_id=user.id, document=file_id)
                elif media_type == "photo":
                    await context.bot.send_photo(chat_id=user.id, photo=file_id)
                elif media_type == "video":
                    await context.bot.send_video(chat_id=user.id, video=file_id)
                elif media_type == "audio":
                    await context.bot.send_audio(chat_id=user.id, audio=file_id)
            except Exception as e:
                print(f"Error sending file {file_id}: {e}")
        return

    # Auto File Upload Mode - Always active for everyone
    keyboard = [
        [InlineKeyboardButton("📤 Start Auto Upload", callback_data="auto_upload")],
        [InlineKeyboardButton("📊 My Uploads", callback_data="my_uploads")]
    ]
    await message.reply_text(
        "📁 <b>Auto File Sharing Bot</b>\n\n"
        "📤 Send any file (photo, video, audio, document)\n"
        "🔄 Auto-generate shareable link for each file\n"
        "🔗 Create unlimited links for your files\n\n"
        "📢 Channel: @DarkNetworkTipsVip",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# BUTTON CALLBACK HANDLER
# =========================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "try_again":
        joined = await check_joined(context.bot, user_id)
        if joined:
            await query.message.edit_text("✅ Verification successful! Press /start to begin.")
        else:
            await query.answer("❌ You haven't joined the channel yet!", show_alert=True)

    elif query.data == "auto_upload":
        # Initialize auto upload session
        context.user_data["auto_upload"] = True
        context.user_data["file_count"] = 0
        
        await query.message.reply_text(
            "📤 <b>Auto Upload Mode Activated!</b>\n\n"
            "Send me any files (photos, videos, audio, documents)\n"
            "I'll automatically create a shareable link for each file.\n\n"
            "🔄 Send as many files as you want!\n"
            "📊 Each file gets its own unique link.",
            parse_mode="HTML"
        )

    elif query.data == "my_uploads":
        # Show user's uploaded files (you can implement this)
        await query.message.reply_text(
            "📊 <b>Your Uploads</b>\n\n"
            "Send files to create links.\n"
            "Use /start to begin.",
            parse_mode="HTML"
        )

# =========================
# AUTO FILE HANDLER - Creates link for each file automatically
# =========================

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user = update.effective_user
    
    # Check force join
    joined = await check_joined(context.bot, user.id)
    if not joined:
        await message.reply_text("🔒 Please join our channel first! Use /start")
        return

    file_id = None
    media_type = None
    file_name = None

    # Detect file type
    if message.document:
        file_id = message.document.file_id
        media_type = "document"
        file_name = message.document.file_name or "document"
    elif message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
        file_name = "photo.jpg"
    elif message.video:
        file_id = message.video.file_id
        media_type = "video"
        file_name = message.video.file_name or "video.mp4"
    elif message.audio:
        file_id = message.audio.file_id
        media_type = "audio"
        file_name = message.audio.file_name or "audio.mp3"
    else:
        await message.reply_text("⚠️ Unsupported file type. Send photo, video, audio, or document.")
        return

    # Create unique batch ID for this single file
    batch_id = str(uuid.uuid4())[:8]
    
    # Save to database
    save_file_batch(batch_id, [(file_id, media_type)])
    
    # Generate shareable link
    bot_username = (await context.bot.get_me()).username
    share_link = f"https://t.me/{bot_username}?start={batch_id}"
    
    # Send success message with link
    keyboard = [
        [InlineKeyboardButton("🔗 Open File", url=share_link)],
        [InlineKeyboardButton("📤 Upload More", callback_data="auto_upload")]
    ]
    
    await message.reply_text(
        f"✅ <b>File Saved & Link Generated!</b>\n\n"
        f"📄 <b>File:</b> <code>{file_name}</code>\n"
        f"📂 <b>Type:</b> {media_type.capitalize()}\n"
        f"🔗 <b>Share Link:</b>\n<code>{share_link}</code>\n\n"
        f"💡 Click below to open or share this link!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# MAIN
# =========================

def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ATTACHMENT, handle_media))

    print("================================")
    print("✅ AUTO FILE SHARE BOT STARTED")
    print("📤 Send any file to get a shareable link")
    print("================================")

    app.run_polling()

if __name__ == "__main__":
    main()
  

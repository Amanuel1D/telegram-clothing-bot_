import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import logging

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration - Set these as environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '0'))  # Your Telegram User ID
CHANNEL_USERNAME = os.environ.get('CHANNEL_USERNAME', '')  # e.g., @yourchannelname
YOUR_TELEGRAM = os.environ.get('YOUR_TELEGRAM', '')  # Your personal telegram username

# Data storage (in production, use a database)
items = {}  # Format: {item_id: {price, description, photo_id, comments: []}}
pending_posts = {}  # Temporary storage for items being created

# Helper function to save data
def save_data():
    with open('items.json', 'w') as f:
        json.dump(items, f)

# Helper function to load data
def load_data():
    global items
    try:
        with open('items.json', 'r') as f:
            items = json.load(f)
    except FileNotFoundError:
        items = {}

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id == ADMIN_ID:
        await update.message.reply_text(
            f"👋 Welcome Admin!\n\n"
            f"Commands:\n"
            f"/newitem - Create a new clothing post\n"
            f"/listitems - View all items\n"
            f"/deleteitem [id] - Delete an item\n"
            f"/help - Show help"
        )
    else:
        await update.message.reply_text(
            f"👋 Welcome to our Clothing Store!\n\n"
            f"Join our channel: {CHANNEL_USERNAME}\n"
            f"Browse our latest collections and interact with posts!"
        )

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text(
            "📝 Admin Guide:\n\n"
            "1️⃣ /newitem - Start posting a new item\n"
            "2️⃣ Send a photo of the clothing\n"
            "3️⃣ Send description text\n"
            "4️⃣ Send the price\n"
            "5️⃣ Bot will post to channel with buttons\n\n"
            "/listitems - See all posted items\n"
            "/deleteitem [id] - Remove an item"
        )
    else:
        await update.message.reply_text(
            f"Join our channel: {CHANNEL_USERNAME}\n"
            "Click buttons on posts to:\n"
            "💰 Ask Price\n"
            "📤 Share\n"
            "🛒 Buy Now\n"
            "💬 Comment"
        )

# New item command (Admin only)
async def new_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only command!")
        return
    
    pending_posts[ADMIN_ID] = {'step': 'photo'}
    await update.message.reply_text(
        "📸 Step 1: Send me a photo of the clothing item"
    )

# Handle photo from admin
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if ADMIN_ID not in pending_posts or pending_posts[ADMIN_ID].get('step') != 'photo':
        return
    
    photo = update.message.photo[-1]  # Get highest resolution
    pending_posts[ADMIN_ID]['photo_id'] = photo.file_id
    pending_posts[ADMIN_ID]['step'] = 'description'
    
    await update.message.reply_text(
        "✍️ Step 2: Send me the description\n"
        "(e.g., 'Summer Cotton T-Shirt\nComfortable casual wear, Size: S,M,L,XL')"
    )

# Handle text messages from admin
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if ADMIN_ID not in pending_posts:
        return
    
    step = pending_posts[ADMIN_ID].get('step')
    
    if step == 'description':
        pending_posts[ADMIN_ID]['description'] = update.message.text
        pending_posts[ADMIN_ID]['step'] = 'price'
        await update.message.reply_text(
            "💰 Step 3: Send me the price\n"
            "(e.g., '25' or '25.99')"
        )
    
    elif step == 'price':
        try:
            price = update.message.text.strip()
            pending_posts[ADMIN_ID]['price'] = price
            
            # Create item
            item_id = str(len(items) + 1)
            items[item_id] = {
                'photo_id': pending_posts[ADMIN_ID]['photo_id'],
                'description': pending_posts[ADMIN_ID]['description'],
                'price': price,
                'comments': []
            }
            save_data()
            
            # Post to channel
            await post_to_channel(context, item_id)
            
            await update.message.reply_text(
                f"✅ Item posted to channel!\n"
                f"Item ID: {item_id}\n\n"
                f"Use /newitem to post another item"
            )
            
            del pending_posts[ADMIN_ID]
            
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid price. Please send a number (e.g., 25 or 25.99)"
            )

# Post item to channel
async def post_to_channel(context: ContextTypes.DEFAULT_TYPE, item_id: str):
    item = items[item_id]
    
    # Create inline keyboard
    keyboard = [
        [
            InlineKeyboardButton("💰 Ask Price", callback_data=f"price_{item_id}"),
            InlineKeyboardButton("📤 Share", callback_data=f"share_{item_id}")
        ],
        [
            InlineKeyboardButton("🛒 Buy Now", callback_data=f"buy_{item_id}"),
            InlineKeyboardButton("💬 Comment", callback_data=f"comment_{item_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send to channel
    await context.bot.send_photo(
        chat_id=CHANNEL_USERNAME,
        photo=item['photo_id'],
        caption=f"{item['description']}\n\n🆔 Item: {item_id}",
        reply_markup=reply_markup
    )

# Handle button callbacks
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    action, item_id = data.split('_')
    
    if item_id not in items:
        await query.answer("❌ Item not found!", show_alert=True)
        return
    
    item = items[item_id]
    
    if action == 'price':
        await query.answer(f"💰 Price: ${item['price']}", show_alert=True)
    
    elif action == 'share':
        # Create share links
        bot_username = (await context.bot.get_me()).username
        share_text = f"Check out this item! 👕\n\n{item['description']}"
        
        # Telegram share link
        telegram_link = f"https://t.me/share/url?url={CHANNEL_USERNAME}&text={share_text}"
        
        # WhatsApp share link
        whatsapp_link = f"https://wa.me/?text={share_text}%20{CHANNEL_USERNAME}"
        
        keyboard = [
            [InlineKeyboardButton("📱 Share on Telegram", url=telegram_link)],
            [InlineKeyboardButton("💚 Share on WhatsApp", url=whatsapp_link)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            "📤 Share this item with your friends!",
            reply_markup=reply_markup
        )
    
    elif action == 'buy':
        await query.message.reply_text(
            f"🛒 To purchase this item:\n\n"
            f"Contact me directly: @{YOUR_TELEGRAM}\n\n"
            f"Item ID: {item_id}\n"
            f"Price: ${item['price']}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💬 Message Seller", url=f"https://t.me/{YOUR_TELEGRAM}")
            ]])
        )
    
    elif action == 'comment':
        await query.message.reply_text(
            f"💬 To leave a comment about item {item_id}:\n\n"
            f"Send a message to me starting with:\n"
            f"/comment {item_id} [your comment]\n\n"
            f"Example:\n"
            f"/comment {item_id} Looks great! Do you have it in blue?"
        )

# Handle comments
async def comment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /comment [item_id] [your comment]\n"
            "Example: /comment 1 I love this item!"
        )
        return
    
    item_id = context.args[0]
    comment_text = ' '.join(context.args[1:])
    
    if item_id not in items:
        await update.message.reply_text("❌ Item not found!")
        return
    
    # Add comment
    user = update.effective_user
    comment = {
        'user': user.first_name,
        'user_id': user.id,
        'text': comment_text
    }
    items[item_id]['comments'].append(comment)
    save_data()
    
    await update.message.reply_text(
        f"✅ Comment added to item {item_id}!\n\n"
        f"The seller will see your comment."
    )
    
    # Notify admin
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"💬 New comment on item {item_id}:\n\n"
                 f"From: {user.first_name} (@{user.username if user.username else 'no username'})\n"
                 f"Comment: {comment_text}"
        )
    except:
        pass

# List items (Admin only)
async def list_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only command!")
        return
    
    if not items:
        await update.message.reply_text("No items posted yet!")
        return
    
    message = "📋 All Items:\n\n"
    for item_id, item in items.items():
        comments_count = len(item.get('comments', []))
        message += f"🆔 {item_id} - ${item['price']} - {comments_count} comments\n"
        message += f"   {item['description'][:50]}...\n\n"
    
    await update.message.reply_text(message)

# Delete item (Admin only)
async def delete_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only command!")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /deleteitem [item_id]")
        return
    
    item_id = context.args[0]
    
    if item_id in items:
        del items[item_id]
        save_data()
        await update.message.reply_text(f"✅ Item {item_id} deleted!")
    else:
        await update.message.reply_text("❌ Item not found!")

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception while handling an update: {context.error}")

# Main function
def main():
    # Load existing data
    load_data()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("newitem", new_item))
    application.add_handler(CommandHandler("listitems", list_items))
    application.add_handler(CommandHandler("deleteitem", delete_item))
    application.add_handler(CommandHandler("comment", comment_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)
    
    # Start bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

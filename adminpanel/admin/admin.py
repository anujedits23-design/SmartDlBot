import asyncio
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ParseMode
from datetime import datetime, timedelta
import pymongo
from config import MONGO_URL, ADMIN_IDS

# MongoDB connection details
client = pymongo.MongoClient(MONGO_URL)
db = client["user_activity_db"]
user_activity_collection = db["user_activity"]


# Function to update user activity in the MongoDB database
def update_user_activity(user_id, is_group=False):
    now = datetime.utcnow()
    user = user_activity_collection.find_one({"user_id": user_id})
    if not user:
        user_activity_collection.insert_one({
            "user_id": user_id,
            "is_group": is_group,
            "last_activity": now,
            "daily": 0,
            "weekly": 0,
            "monthly": 0,
            "yearly": 0
        })
    else:
        user_activity_collection.update_one(
            {"user_id": user_id},
            {"$set": {"last_activity": now}},
            upsert=True
        )
        user_activity_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"daily": 1, "weekly": 1, "monthly": 1, "yearly": 1}},
        )

def is_admin(user_id):
    return user_id in ADMIN_IDS

async def broadcast_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply_text("🚫 **You are not authorized to use this command.**")
        return

    if message.reply_to_message:
        broadcast_message = message.reply_to_message
        await process_broadcast(client, broadcast_message)
    else:
        await message.reply_text("📢 **Please send the message you want to broadcast.**")
        broadcast_message_handler = None

        async def broadcast_message_callback(client: Client, broadcast_msg: Message):
            nonlocal broadcast_message_handler
            if broadcast_msg.chat.id == message.chat.id and is_admin(broadcast_msg.from_user.id):
                await process_broadcast(client, broadcast_msg)
                client.remove_handler(*broadcast_message_handler)

        broadcast_message_handler = client.add_handler(
            MessageHandler(broadcast_message_callback, filters.group & filters.chat(message.chat.id)),
            group=1
        )

async def process_broadcast(client: Client, broadcast_msg: Message):
    global total_users, blocked_users, broadcast_start_time
    total_users, blocked_users = 0, 0
    broadcast_start_time = datetime.now()

    # Notify admin that the broadcast is being processed
    processing_message = await broadcast_msg.reply_text('**⏳Processing Broadcast⚡️**')

    # Get the message to broadcast
    broadcast_message_id = broadcast_msg.id

    # Get all user ids and group ids
    user_ids = [user["user_id"] for user in user_activity_collection.find()]
    group_ids = [group["user_id"] for group in user_activity_collection.find({"is_group": True})]

    # Broadcast the message to users and groups
    for user_id in user_ids + group_ids:
        try:
            await client.copy_message(
                chat_id=user_id,
                from_chat_id=broadcast_msg.chat.id,
                message_id=broadcast_message_id,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Update Channel", url="https://t.me/anujeditbyak")]]
                )
            )
            total_users += 1
        except Exception as e:
            if "blocked" in str(e):
                blocked_users += 1
            continue

    # Calculate time taken for the broadcast
    broadcast_end_time = datetime.now()
    time_taken = (broadcast_end_time - broadcast_start_time).total_seconds()

    # Delete the processing message
    await processing_message.delete()

    # Send a completion message to the admin
    await broadcast_msg.reply_text(
        f"**✅ Successfully Broadcast Complete to {total_users} users in {time_taken:.2f} seconds**\n\n"
        f"**👥 To Users: {total_users}\n"
        f"🚫 Blocked: {blocked_users}**",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Update Channel", url="https://t.me/anujeditbyak")]]
        )
    )

async def stats_handler(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply_text("🚫 **You are not authorized to use this command.**")
        return

    now = datetime.utcnow()
    daily_users = user_activity_collection.count_documents({"last_activity": {"$gt": now - timedelta(days=1)}})
    weekly_users = user_activity_collection.count_documents({"last_activity": {"$gt": now - timedelta(weeks=1)}})
    monthly_users = user_activity_collection.count_documents({"last_activity": {"$gt": now - timedelta(days=30)}})
    yearly_users = user_activity_collection.count_documents({"last_activity": {"$gt": now - timedelta(days=365)}})
    total_users = yearly_users
    total_groups = user_activity_collection.count_documents({"is_group": True})

    stats_text = (
        "**📊 Bot Usage Report\n"
        "━━━━━━━━━━━\n"
        "🚀 User Engagements:\n"
        f"- Daily Starts: {daily_users}\n"
        f"- Weekly Starts: {weekly_users}\n"
        f"- Monthly Starts: {monthly_users}\n"
        f"- Annual Starts: {yearly_users}\n\n"
        "📈 Total Metrics:\n"
        f"- Total Groups: {total_groups}\n"
        f"- Users Registered: {total_users}**\n"
    )

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔔 Bot Updates", url="https://t.me/anujeditbyak")]])
    await message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard, disable_web_page_preview=True)

async def group_added_handler(client: Client, message: Message):
    for new_member in message.new_chat_members:
        if new_member.is_self:
            chat_id = message.chat.id
            update_user_activity(chat_id, is_group=True)
            await client.send_message(
                chat_id,
                "**Thank You For Adding Me In This Group! 👨‍💻**\n\n"
                "**I'm here to assist you with various tasks and make your group experience better. "
                "Feel free to explore my features and let me know if you need any help! 😊**",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add Me", url="https://t.me/social_media_downloader_ak_bot?startgroup=new&admin=post_messages+delete_messages+edit_messages+pin_messages+change_info+invite_users+promote_members"),
                     InlineKeyboardButton("My Dev👨‍💻", user_id=7892805795)]
                ])
            )

# Function to set up the admin handlers for the bot
def setup_admin_handler(app: Client):
    """
    Set up command handlers for the Pyrogram bot.
    This includes specific commands like /broadcast and /stats, as well as general activity tracking.
    """
    # Add the /broadcast, .broadcast, /send and .send command handlers for broadcasting messages
    app.add_handler(
        MessageHandler(broadcast_handler, (filters.command("broadcast") | filters.command("broadcast", prefixes=[".", "/"]) | filters.command("send") | filters.command("send", prefixes=[".", "/"])) & (filters.private | filters.group)),
        group=1,  # High priority to ensure it executes first
    )
    
    # Add the /stats, .stats, /report, .report, /status and .status command handlers for bot statistics (works in both private and group)
    app.add_handler(
        MessageHandler(stats_handler, (filters.command("stats") | filters.command("stats", prefixes=[".", "/"]) | filters.command("report") | filters.command("report", prefixes=[".", "/"]) | filters.command("status") | filters.command("status", prefixes=[".", "/"])) & (filters.private | filters.group)),
        group=1,  # High priority to ensure it executes first
    )
    
    # Add a general handler to track all user activity
    app.add_handler(
        MessageHandler(lambda client, message: update_user_activity(message.from_user.id) if message.from_user else None, filters.all),
        group=2,  # Lower priority so it runs after command handlers
    )

    # Add the handler for when the bot is added to a group
    app.add_handler(
        MessageHandler(group_added_handler, filters.group & filters.new_chat_members),
        group=1  # High priority to ensure it executes first
      )

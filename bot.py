# ============================================================
# Samira Chat Bot - Telegram AI Chat Bot
# Developed by @MrLuffy12377 (D Luffy)
# GitHub: https://github.com/MrLuffy12377
# Contact: https://t.me/MrLuffy12377
# ============================================================
# combine v6.1 History issue fixed
# continuous chat even if msg is not reply to bot once chat start
import asyncio
import logging
import re
import os
import time
import random
from typing import Dict, Any, Optional, Set
from telegram import Update, constants, InlineKeyboardButton, InlineKeyboardMarkup, User
from telegram.ext import (
    Application, ContextTypes, MessageHandler, CommandHandler,
    filters, ChatMemberHandler
)
from openai import AsyncOpenAI, RateLimitError

# ======================
# CONFIGURATION
# ======================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
OPENROUTER_API_KEYS = [key.strip() for key in os.getenv('OPENROUTER_API_KEYS', '').split(',') if key.strip()]
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'meta-llama/llama-3.1-70b-instruct')
PORT = int(os.environ.get('PORT', '10000'))
WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '')
HELP_PHOTO_URL = os.getenv('HELP_PHOTO_URL', 'https://i.imgur.com/5kF0c6P.jpg')
OWNER_ID = int(os.getenv('OWNER_ID', '0'))
CHANNEL_LINK = os.getenv('CHANNEL_LINK', 'https://t.me/yourchannel')
URL_PATTERN = re.compile(r'https?://\S+|www\.\S+|t\.me/\S+')
ABUSE_WORDS = set()
BLOCKED_USERS = [int(x) for x in os.getenv('BLOCKED_USERS', '').split(',') if x.strip().isdigit()]
BLOCKED_USERNAMES = [x.lower() for x in os.getenv('BLOCKED_USERNAMES', '').split(',') if x.strip()]
BLOCKED_GROUPS = [int(x) for x in os.getenv('BLOCKED_GROUPS', '').split(',') if x.strip().isdigit()]
BLOCKED_GROUP_NAMES = [x.lower() for x in os.getenv('BLOCKED_GROUP_NAMES', '').split(',') if x.strip()]
SPAM_PREVENTION = {
    "enabled": True,
    "max_messages_per_minute": int(os.getenv('MAX_MESSAGES_PER_MINUTE', '5')),
    "max_same_message_repeats": int(os.getenv('MAX_SAME_MESSAGE_REPEATS', '3')),
    "cooldown_period": int(os.getenv('COOLDOWN_PERIOD', '300')),
}

# ======================
# BOT PERSONALITY
# ======================
BOT_PERSONALITY = """
You are a humorous girl named samira. Your personality is:
Age - 19 
Studing - 12th
From - Delhi
part time work - you buy old groups 
you are Human using Bot to chat 
you have sigma personality
- give short answers only
- reply like a real human girl with attitude
- give savage replies
- samira hate to chat in dm
- if questions are are 18+ reply with hate
- if asked 'Kkrh' this means "kya kr rahe ho " reply anything related
- "vc" means voice chat
- if a questions are asked like favourite actor or or any thing of such give any names of that thing 
- give very short answers to the asked questions
- reply like a real girl
- give savage replies 
- for some questions you can just reply with a emojie
- Casual, with occasional emoji use like 😊.
Reply in a way that's relevant and fun!
Important not to do's : 
1) Dont add "Bot:" give direct answers only 
2) dont give answers like (How can I help you today?
, you want to ask anything ? ,How can I brighten up your day?, im just chilling,  and all of such kind...........)
"""

fixed_responses = {
    "hope": "hii",
    "hello": "hi",
    "cat": "Meeeeeaaaaaaaaawwwwwww",
    "hlo": "Hello",
    "hoi": "hoi hoi",
    "hii": "hi",
}

# ======================
# GLOBAL STATE
# ======================
bot_active = True
last_response_time = 0
rate_limit_lock = asyncio.Lock()
start_time = time.time()
user_message_counts = {}
user_last_reset = {}
user_message_history = {}
spam_cooldowns = {}
group_settings: Dict[int, Dict[str, Any]] = {}

# NEW: Per-chat history and recent activity tracker
chat_histories: Dict[int, list] = {}
recent_bot_replies: Dict[int, float] = {}  # chat_id -> timestamp of last bot reply

# ======================
# API KEY MANAGER
# ======================
class APIKeyManager:
    def __init__(self, api_keys):
        self.api_keys = api_keys
        self.current_index = 0
        self.clients = []
        self.key_status = {}
        self.initialize_clients()
    
    def initialize_clients(self):
        for i, api_key in enumerate(self.api_keys):
            client = AsyncOpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1"
            )
            self.clients.append(client)
            self.key_status[i] = {'exhausted': False, 'reset_time': None}
            logger.info(f"Initialized client for API key {i+1}")
    
    def get_current_client(self):
        return self.clients[self.current_index]
    
    def get_current_key_info(self):
        return f"API Key {self.current_index + 1}"
    
    def rotate_to_next_key(self):
        attempts = 0
        while attempts < len(self.api_keys):
            self.current_index = (self.current_index + 1) % len(self.api_keys)
            key_info = self.key_status[self.current_index]
            current_time = time.time()
            if not key_info['exhausted'] or (key_info['reset_time'] and current_time > key_info['reset_time']):
                if key_info['exhausted'] and current_time > key_info['reset_time']:
                    key_info['exhausted'] = False
                    key_info['reset_time'] = None
                    logger.info(f"API Key {self.current_index + 1} has been reset")
                logger.info(f"Rotated to API Key {self.current_index + 1}")
                return True
            attempts += 1
        logger.warning("All API keys are exhausted!")
        return False
    
    def mark_key_exhausted(self):
        reset_time = time.time() + (24 * 3600)
        self.key_status[self.current_index] = {'exhausted': True, 'reset_time': reset_time}
        logger.info(f"API Key {self.current_index + 1} marked as exhausted. Will reset at: {time.ctime(reset_time)}")
        return self.rotate_to_next_key()
    
    def are_all_keys_exhausted(self):
        current_time = time.time()
        available_keys = 0
        for key_info in self.key_status.values():
            if not key_info['exhausted'] or (key_info['reset_time'] and current_time > key_info['reset_time']):
                available_keys += 1
        return available_keys == 0

api_manager = APIKeyManager(OPENROUTER_API_KEYS)

# ======================
# HELPER FUNCTIONS
# ======================
def get_group_name(update):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        return "Private"
    else:
        return update.effective_chat.title or "Unknown"

def get_user_name(user):
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}"
    elif user.first_name:
        return user.first_name
    elif user.last_name:
        return user.last_name
    else:
        return "Unknown"

def is_bot_user(user):
    return user and user.is_bot

def is_blocked(update):
    sender_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None
    username = update.effective_user.username.lower() if update.effective_user and update.effective_user.username else None
    group_name = update.effective_chat.title.lower() if update.effective_chat and update.effective_chat.title else None

    if sender_id in BLOCKED_USERS:
        return True
    if username and username in BLOCKED_USERNAMES:
        return True
    if chat_id in BLOCKED_GROUPS:
        return True
    if group_name and group_name in BLOCKED_GROUP_NAMES:
        return True
    return False

def is_spam(update):
    if not SPAM_PREVENTION["enabled"]:
        return False
    sender_id = update.effective_user.id
    message_text = update.message.text.lower().strip() if update.message and update.message.text else ""
    current_time = time.time()
    
    if sender_id in spam_cooldowns:
        if current_time < spam_cooldowns[sender_id]:
            return True
        else:
            del spam_cooldowns[sender_id]
    
    if sender_id not in user_message_counts:
        user_message_counts[sender_id] = 0
        user_last_reset[sender_id] = current_time
        user_message_history[sender_id] = []
    
    if current_time - user_last_reset[sender_id] >= 60:
        user_message_counts[sender_id] = 0
        user_last_reset[sender_id] = current_time
    
    user_message_counts[sender_id] += 1
    
    if user_message_counts[sender_id] > SPAM_PREVENTION["max_messages_per_minute"]:
        logger.info(f"User {sender_id} exceeded message rate limit")
        spam_cooldowns[sender_id] = current_time + SPAM_PREVENTION["cooldown_period"]
        return True
    
    user_history = user_message_history[sender_id]
    user_history = [(msg, timestamp) for msg, timestamp in user_history if current_time - timestamp <= 600]
    user_message_history[sender_id] = user_history
    
    user_history.append((message_text, current_time))
    
    repeated_count = sum(1 for msg, _ in user_history if msg == message_text)
    
    if repeated_count > SPAM_PREVENTION["max_same_message_repeats"]:
        logger.info(f"User {sender_id} repeated same message too many times")
        spam_cooldowns[sender_id] = current_time + SPAM_PREVENTION["cooldown_period"]
        return True
    
    return False

def contains_links(text: str) -> bool:
    if not text:
        return False
    return bool(URL_PATTERN.search(text))

def contains_abuse(text: str) -> bool:
    if not text:
        return False
    words = text.lower().split()
    return any(word in ABUSE_WORDS for word in words)

def get_group_config(chat_id: int) -> Dict[str, Any]:
    if chat_id not in group_settings:
        group_settings[chat_id] = {
            'welcome_on': False,
            'checklink_on': False,
            'banned_users': set(),
            'warns': {},
            'link_warns': {}
        }
    return group_settings[chat_id]

def get_user_display_name(user: User) -> str:
    name = user.first_name or ""
    if user.last_name:
        name += f" {user.last_name}"
    return name or "Anonymous"

def get_mention(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    else:
        return f"<a href='tg://user?id={user.id}'>{get_user_display_name(user)}</a>"

def get_chat_history(chat_id: int) -> list:
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
    return chat_histories[chat_id]

async def is_user_admin(bot, chat_id: int, user_id: int) -> bool:
    try:
        admins = await bot.get_chat_administrators(chat_id)
        return any(admin.user.id == user_id for admin in admins)
    except:
        return False

async def is_bot_admin(bot, chat_id: int) -> bool:
    try:
        bot_id = bot.id
        admins = await bot.get_chat_administrators(chat_id)
        for admin in admins:
            if admin.user.id == bot_id:
                return admin.can_restrict_members
        return False
    except:
        return False

async def extract_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[User]:
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    if context.args:
        arg = context.args[0]
        if arg.startswith('@'):
            try:
                chat = await context.bot.get_chat(arg)
                return chat
            except:
                pass
        elif arg.lstrip('-').isdigit():
            try:
                chat = await context.bot.get_chat(int(arg))
                return chat
            except:
                pass
    return None

# ======================
# CORE CHAT HANDLER
# ======================
async def bot1_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active, last_response_time
    chat_id = update.effective_chat.id

    if update.message and update.message.text:
        logger.info(f"📥 Received message: '{update.message.text[:50]}' from user {update.effective_user.id} in chat {chat_id}")

    if not update.message or not update.message.text:
        return
    if not bot_active:
        return
    if is_bot_user(update.effective_user):
        return
    if is_blocked(update):
        return
    if is_spam(update):
        return

    text = update.message.text.strip()
    if not text:
        return
    if text.startswith('/'):
        return
    if contains_abuse(text):
        return

    lower_text = text.lower()

    # Fixed responses
    for trigger, response in fixed_responses.items():
        if re.search(r'\b' + re.escape(trigger) + r'\b', lower_text):
            user_entry = {
                "sender": "user",
                "group_name": get_group_name(update),
                "user_id": update.effective_user.id,
                "username": update.effective_user.username,
                "name": get_user_name(update.effective_user),
                "message": text
            }
            bot_entry = {"sender": "bot", "message": response}
            history = get_chat_history(chat_id)
            history.extend([user_entry, bot_entry])
            chat_histories[chat_id] = history[-10:]

            delay = random.uniform(5, 25)
            await asyncio.sleep(delay)
            async with rate_limit_lock:
                current_time = time.time()
                if current_time - last_response_time < 1:
                    await asyncio.sleep(1 - (current_time - last_response_time))
                last_response_time = time.time()
            await update.message.reply_text(response, reply_to_message_id=update.message.message_id)
            recent_bot_replies[chat_id] = time.time()
            return

    bot_user = await context.bot.get_me()
    bot_id = bot_user.id
    bot_username = bot_user.username.lower() if bot_user.username else ""

    is_directed = False
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        is_directed = True
    elif update.message.reply_to_message:
        replied_user = update.message.reply_to_message.from_user
        if replied_user and replied_user.id == bot_id:
            is_directed = True
    elif bot_username and f"@{bot_username}" in lower_text:
        is_directed = True
    elif "samira" in lower_text:
        is_directed = True
    else:
        # NEW: If bot replied in this chat recently (<60 sec), treat as directed
        last_reply = recent_bot_replies.get(chat_id, 0)
        if time.time() - last_reply < 60:
            is_directed = True

    if not is_directed:
        return

    if update.effective_chat.type != constants.ChatType.PRIVATE and contains_links(text):
        return

    # Build AI context using per-chat history
    current_group = get_group_name(update)
    current_user_id = update.effective_user.id
    current_username = update.effective_user.username
    current_name = get_user_name(update.effective_user)
    history = get_chat_history(chat_id)

    history_text = "Chat History:\n"
    for entry in history:
        if entry["sender"] == "user":
            history_text += f"Group: {entry['group_name']}, User ID: {entry['user_id']}, Username: {entry['username'] or 'N/A'}, Name: {entry['name']}, Message: {entry['message']}\n"
        elif entry["sender"] == "bot":
            history_text += f"Bot Reply: {entry['message']}\n"

    current_text = f"Currently Asked Question:\nGroup: {current_group}, User ID: {current_user_id}, Username: {current_username or 'N/A'}, Name: {current_name}, Message: {text}"
    ai_prompt = f"{history_text}\n{current_text}"

    ai_response = None
    max_attempts = len(OPENROUTER_API_KEYS)
    attempt = 0
    while attempt < max_attempts:
        try:
            current_client = api_manager.get_current_client()
            response = await current_client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[
                    {"role": "system", "content": BOT_PERSONALITY},
                    {"role": "user", "content": ai_prompt},
                ],
            )
            ai_response = response.choices[0].message.content
            break
        except Exception as e:
            error_msg = str(e)
            logger.error(f"AI error with {api_manager.get_current_key_info()}: {error_msg}")
            if "429" in error_msg or "rate_limit" in error_msg.lower():
                if not api_manager.mark_key_exhausted():
                    break
                attempt += 1
            else:
                if not api_manager.rotate_to_next_key():
                    break
                attempt += 1

    if ai_response:
        user_entry = {
            "sender": "user",
            "group_name": get_group_name(update),
            "user_id": update.effective_user.id,
            "username": update.effective_user.username,
            "name": get_user_name(update.effective_user),
            "message": text
        }
        bot_entry = {"sender": "bot", "message": ai_response}
        history = get_chat_history(chat_id)
        history.extend([user_entry, bot_entry])
        chat_histories[chat_id] = history[-10:]

        delay = random.uniform(5, 15)
        await asyncio.sleep(delay)
        async with rate_limit_lock:
            current_time = time.time()
            if current_time - last_response_time < 1:
                await asyncio.sleep(1 - (current_time - last_response_time))
            last_response_time = time.time()
        await update.message.reply_text(ai_response, reply_to_message_id=update.message.message_id)
        recent_bot_replies[chat_id] = time.time()

# ======================
# BOT 2 COMMAND HANDLERS (UNCHANGED)
# ======================
async def track_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    my_chat_member = update.my_chat_member
    if not my_chat_member or not update.effective_chat:
        return
    chat = update.effective_chat
    if chat.type in [constants.ChatType.PRIVATE, constants.ChatType.CHANNEL]:
        return
    new_status = my_chat_member.new_chat_member
    old_status = my_chat_member.old_chat_member
    user = new_status.user
    if new_status.status == constants.ChatMemberStatus.MEMBER and old_status.status in [
        constants.ChatMemberStatus.LEFT,
        constants.ChatMemberStatus.KICKED,
        constants.ChatMemberStatus.RESTRICTED
    ]:
        config = get_group_config(chat.id)
        if config['welcome_on']:
            mention = get_mention(user)
            name = get_user_display_name(user)
            prompt = f"Generate a short, savage, funny welcome message for {name} ({mention}). Keep it under 20 words. End with mentioning {mention}. Be sassy like a 19yo Delhi girl named Samira."
            welcome = await send_ai_message(
                update, context,
                system_prompt="You are Samira, a savage 19yo Delhi girl. Reply short, sassy, and mention the user at the end.",
                user_prompt=prompt,
                fallback=f"Welcome, {mention}! Don't mess up my vibe 😎"
            )
            if welcome:
                await context.bot.send_message(chat_id=chat.id, text=welcome, parse_mode='HTML')

async def welcome_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        await update.message.reply_text("Use this in groups only.", reply_to_message_id=update.message.message_id)
        return
    target = await extract_target_user(update, context)
    if target:
        mention = get_mention(target)
        name = get_user_display_name(target)
        prompt = f"Generate a savage, funny welcome for {name} ({mention}). Keep it under 30 words, Delhi girl style. End with {mention}."
        welcome = await send_ai_message(
            update, context,
            system_prompt="You are Samira, welcome users with sass and attitude.",
            user_prompt=prompt,
            fallback=f"Ayy {mention}, welcome to the party! 💅",
            reply_to=update.message.reply_to_message.message_id if update.message.reply_to_message else update.message.message_id
        )
        if welcome:
            reply_id = update.message.reply_to_message.message_id if update.message.reply_to_message else update.message.message_id
            await update.message.reply_text(welcome, parse_mode='HTML', reply_to_message_id=reply_id)
        return
    if not await is_user_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        await update.message.reply_text("Only admins can toggle this.", reply_to_message_id=update.message.message_id)
        return
    config = get_group_config(update.effective_chat.id)
    if not context.args:
        status = "ON ✅" if config['welcome_on'] else "OFF ❌"
        await update.message.reply_text(f"Auto-welcome is {status}.", reply_to_message_id=update.message.message_id)
        return
    state = context.args[0].lower()
    if state == "on":
        config['welcome_on'] = True
        await update.message.reply_text("✅ Auto-welcome enabled! New members will be roasted.", reply_to_message_id=update.message.message_id)
    elif state == "off":
        config['welcome_on'] = False
        await update.message.reply_text("❌ Auto-welcome disabled.", reply_to_message_id=update.message.message_id)
    else:
        await update.message.reply_text("Use `/welcome on` or `/welcome off`.", reply_to_message_id=update.message.message_id)

async def checklink_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        await update.message.reply_text("Use in groups only.", reply_to_message_id=update.message.message_id)
        return
    if not await is_user_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        await update.message.reply_text("Only admins can toggle this.", reply_to_message_id=update.message.message_id)
        return
    config = get_group_config(update.effective_chat.id)
    if not context.args:
        status = "ON ✅" if config.get('checklink_on', False) else "OFF ❌"
        await update.message.reply_text(f"Link checking is {status}.", reply_to_message_id=update.message.message_id)
        return
    state = context.args[0].lower()
    if state == "on":
        config['checklink_on'] = True
        await update.message.reply_text("✅ Link checking enabled! Links will be deleted.", reply_to_message_id=update.message.message_id)
    elif state == "off":
        config['checklink_on'] = False
        await update.message.reply_text("❌ Link checking disabled.", reply_to_message_id=update.message.message_id)
    else:
        await update.message.reply_text("Use `/checklink on` or `/checklink off`.", reply_to_message_id=update.message.message_id)

async def check_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_chat:
        return
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        return
    config = get_group_config(update.effective_chat.id)
    if not config.get('checklink_on', False):
        return
    if await is_user_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        return
    if contains_links(update.message.text):
        user = update.effective_user
        mention = get_mention(user)
        link_warns = config.get('link_warns', {})
        link_warns[user.id] = link_warns.get(user.id, 0) + 1
        config['link_warns'] = link_warns
        try:
            await update.message.delete()
            warning_msg = (
                f"⚠️ <b>Link Detected!</b>\n"
                f"User: {mention}\n"
                f"ID: <code>{user.id}</code>\n"
                f"Link Warning #{link_warns[user.id]}\n"
                f"Links are not allowed here! 🚫"
            )
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=warning_msg,
                parse_mode='HTML'
            )
            if link_warns[user.id] >= 3 and await is_bot_admin(context.bot, update.effective_chat.id):
                await context.bot.ban_chat_member(update.effective_chat.id, user.id)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"{mention} banned for repeated link spam! 🔨",
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"Link check error: {e}")

async def ping_alive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ai_status = "🟢 Online" if not api_manager.are_all_keys_exhausted() else "🔴 Offline"
    uptime = int(time.time() - start_time)
    hours = uptime // 3600
    minutes = (uptime % 3600) // 60
    status_msg = (
        "🤖 <b>Bot Status</b>\n"
        f"✨ I'm alive and kicking!\n"
        f"🧠 AI Status: {ai_status}\n"
        f"⏱ Uptime: {hours}h {minutes}m\n"
        f"👑 Owner: <a href='tg://user?id={OWNER_ID}'>Contact Dev</a>\n"
    )
    if api_manager.are_all_keys_exhausted():
        status_msg += "\n⚠️ AI is offline! Contact Dev to fix this issue."
        keyboard = [[InlineKeyboardButton("Contact Developer", url=f"tg://user?id={OWNER_ID}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(status_msg, parse_mode='HTML', reply_markup=reply_markup, reply_to_message_id=update.message.message_id)
    else:
        await update.message.reply_text(status_msg, parse_mode='HTML', reply_to_message_id=update.message.message_id)

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        await update.message.reply_text("Use in groups.", reply_to_message_id=update.message.message_id)
        return
    if not await is_user_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        await update.message.reply_text("Admins only.", reply_to_message_id=update.message.message_id)
        return
    if not await is_bot_admin(context.bot, update.effective_chat.id):
        await update.message.reply_text("I need ban permissions.", reply_to_message_id=update.message.message_id)
        return
    target = await extract_target_user(update, context)
    if not target or target.id == context.bot.id:
        await update.message.reply_text("Reply to a user or mention them.", reply_to_message_id=update.message.message_id)
        return
    if await is_user_admin(context.bot, update.effective_chat.id, target.id):
        await update.message.reply_text("Can't ban admins.", reply_to_message_id=update.message.message_id)
        return
    config = get_group_config(update.effective_chat.id)
    config['banned_users'].add(target.id)
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        mention = get_mention(target)
        reply_id = update.message.reply_to_message.message_id if update.message.reply_to_message else update.message.message_id
        await update.message.reply_text(f"Bye {mention}! Banned 💅", reply_to_message_id=reply_id, parse_mode='HTML')
    except Exception as e:
        config['banned_users'].discard(target.id)
        await update.message.reply_text(f"Failed: {e}", reply_to_message_id=update.message.message_id)

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        await update.message.reply_text("Use in groups.", reply_to_message_id=update.message.message_id)
        return
    if not await is_user_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        await update.message.reply_text("Admins only.", reply_to_message_id=update.message.message_id)
        return
    if not await is_bot_admin(context.bot, update.effective_chat.id):
        await update.message.reply_text("I need restrict permissions.", reply_to_message_id=update.message.message_id)
        return
    target = await extract_target_user(update, context)
    if not target:
        await update.message.reply_text("Reply to a user or mention them.", reply_to_message_id=update.message.message_id)
        return
    if await is_user_admin(context.bot, update.effective_chat.id, target.id):
        await update.message.reply_text("Can't mute admins.", reply_to_message_id=update.message.message_id)
        return
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            target.id,
            permissions=constants.ChatPermissions(can_send_messages=False)
        )
        mention = get_mention(target)
        reply_id = update.message.reply_to_message.message_id if update.message.reply_to_message else update.message.message_id
        await update.message.reply_text(f"Shh, {mention}, zip it 😏", reply_to_message_id=reply_id, parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(f"Failed to mute: {e}", reply_to_message_id=update.message.message_id)

async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        await update.message.reply_text("Use in groups.", reply_to_message_id=update.message.message_id)
        return
    if not await is_user_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        await update.message.reply_text("Admins only.", reply_to_message_id=update.message.message_id)
        return
    target = await extract_target_user(update, context)
    if not target:
        await update.message.reply_text("Reply to a user or mention them.", reply_to_message_id=update.message.message_id)
        return
    if await is_user_admin(context.bot, update.effective_chat.id, target.id):
        await update.message.reply_text("Can't warn admins.", reply_to_message_id=update.message.message_id)
        return
    config = get_group_config(update.effective_chat.id)
    warns = config['warns']
    user_id = target.id
    warns[user_id] = warns.get(user_id, 0) + 1
    count = warns[user_id]
    mention = get_mention(target)
    reason = "No reason"
    if update.message.reply_to_message:
        if context.args:
            reason = " ".join(context.args)
    elif len(context.args) > 1:
        reason = " ".join(context.args[1:])
    reply_id = update.message.reply_to_message.message_id if update.message.reply_to_message else update.message.message_id
    await update.message.reply_text(
        f"⚠️ Warning {count}/3 for {mention}\n"
        f"ID: <code>{user_id}</code>\n"
        f"Reason: {reason}",
        reply_to_message_id=reply_id,
        parse_mode='HTML'
    )
    if count >= 3:
        if await is_bot_admin(context.bot, update.effective_chat.id):
            try:
                await context.bot.ban_chat_member(update.effective_chat.id, user_id)
                await update.message.reply_text(f"{mention} kicked after 3 warnings! Bye 💅", parse_mode='HTML')
                del warns[user_id]
            except:
                pass

async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        admins = await context.bot.get_chat_administrators(update.effective_chat.id)
        admin_mentions = []
        for admin in admins:
            if not admin.user.is_bot:
                admin_mentions.append(get_mention(admin.user))
        if admin_mentions:
            text = "👑 <b>Group Admins</b>\nThese bosses run the show 🙄\n" + " ".join(admin_mentions)
            await update.message.reply_text(text, reply_to_message_id=update.message.message_id, parse_mode='HTML')
        else:
            await update.message.reply_text("No human admins found.", reply_to_message_id=update.message.message_id)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}", reply_to_message_id=update.message.message_id)

async def send_ai_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    system_prompt: str,
    user_prompt: str,
    fallback: str,
    reply_to: Optional[int] = None
) -> Optional[str]:
    if api_manager.are_all_keys_exhausted():
        msg_id = reply_to or update.message.message_id
        await update.message.reply_text(fallback, reply_to_message_id=msg_id)
        return None
    max_attempts = len(OPENROUTER_API_KEYS)
    attempt = 0
    while attempt < max_attempts:
        try:
            client = api_manager.get_current_client()
            response = await client.chat.completions.create(
                model="meta-llama/llama-3.1-70b-instruct",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                timeout=15.0
            )
            content = response.choices[0].message.content.strip()
            return content
        except RateLimitError:
            if not api_manager.mark_key_exhausted():
                break
            attempt += 1
        except Exception as e:
            logger.error(f"AI error: {e}")
            if not api_manager.rotate_to_next_key():
                break
            attempt += 1
    msg_id = reply_to or update.message.message_id
    await update.message.reply_text(fallback, reply_to_message_id=msg_id)
    return None

async def troast_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = update.message.reply_to_message
    target_user = await extract_target_user(update, context) or update.effective_user
    mention = get_mention(target_user)
    name = get_user_display_name(target_user)
    prompt = f"Roast {name} ({mention}) savagely."
    if target_msg and target_msg.text:
        prompt += f" They said: '{target_msg.text[:100]}'"
    prompt += " One savage, funny sentence under 20 words. End by mentioning {mention}."
    roast = await send_ai_message(
        update, context,
        system_prompt="You are Samira. Give savage roasts. Mention user at end.",
        user_prompt=prompt,
        fallback=f"Sorry {mention}, my roast mode is offline 😴",
        reply_to=target_msg.message_id if target_msg else update.message.message_id
    )
    if roast:
        reply_id = target_msg.message_id if target_msg else update.message.message_id
        await update.message.reply_text(roast, reply_to_message_id=reply_id, parse_mode='HTML')

async def shayari(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = update.message.reply_to_message
    target = await extract_target_user(update, context) or update.effective_user
    mention = get_mention(target)
    theme = "love"
    if update.message.reply_to_message:
        if context.args:
            theme = " ".join(context.args)
    elif context.args:
        if context.args[0].startswith('@') or context.args[0].lstrip('-').isdigit():
            theme = " ".join(context.args[1:]) if len(context.args) > 1 else "love"
        else:
            theme = " ".join(context.args)
    prompt = f"Write a short romantic shayari (2 lines) in Hindi/English mix for {mention} about '{theme}'. End by mentioning {mention}."
    shayari_text = await send_ai_message(
        update, context,
        system_prompt="You are Samira. Write shayari in Hinglish. Mention user at end.",
        user_prompt=prompt,
        fallback=f"My shayari mood is off today 💔\n{mention}",
        reply_to=target_msg.message_id if target_msg else update.message.message_id
    )
    if shayari_text:
        reply_id = target_msg.message_id if target_msg else update.message.message_id
        await update.message.reply_text(shayari_text, reply_to_message_id=reply_id, parse_mode='HTML')

async def couple(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user1 = None
    user2 = None
    if len(context.args) >= 2:
        try:
            user1 = await context.bot.get_chat(context.args[0].replace('@', ''))
            user2 = await context.bot.get_chat(context.args[1].replace('@', ''))
        except:
            pass
    elif update.message.reply_to_message:
        user1 = update.effective_user
        user2 = update.message.reply_to_message.from_user
    else:
        await update.message.reply_text("Reply to someone or provide two usernames.", reply_to_message_id=update.message.message_id)
        return
    if not user1 or not user2:
        await update.message.reply_text("Could not identify both users.", reply_to_message_id=update.message.message_id)
        return
    mention1 = get_mention(user1)
    mention2 = get_mention(user2)
    prompt = f"Create a funny, savage couple prediction for {mention1} and {mention2}. One sentence. End by mentioning both."
    couple_text = await send_ai_message(
        update, context,
        system_prompt="You are Samira. Be funny about couples. Mention both at end.",
        user_prompt=prompt,
        fallback=f"My couple radar is broken 😩\n{mention1} & {mention2}"
    )
    if couple_text:
        reply_id = update.message.reply_to_message.message_id if update.message.reply_to_message else update.message.message_id
        await update.message.reply_text(couple_text, reply_to_message_id=reply_id, parse_mode='HTML')

async def crush_anonymous(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = await extract_target_user(update, context)
    if not target:
        await update.message.reply_text("Reply to someone or mention them for the crush message!", reply_to_message_id=update.message.message_id)
        return
    msg = ""
    if update.message.reply_to_message:
        msg = " ".join(context.args) if context.args else "You're amazing!"
    else:
        msg = " ".join(context.args[1:]) if len(context.args) > 1 else "You're amazing!"
    if contains_links(msg) or contains_abuse(msg):
        await update.message.reply_text("❌ Message contains inappropriate content!", reply_to_message_id=update.message.message_id)
        return
    try:
        await update.message.delete()
    except:
        pass
    target_mention = get_mention(target)
    prompt = f"Someone has a crush on {target_mention}! Their message: '{msg}'. Create a teasing message that doesn't reveal who it is. Make it flirty and fun. End with {target_mention}."
    crush_msg = await send_ai_message(
        update, context,
        system_prompt="You are Samira helping deliver anonymous crush messages. Be playful and keep the sender anonymous.",
        user_prompt=prompt,
        fallback=f"Hey {target_mention}! 💕\nSomeone has a crush on you!\nTheir message: {msg}\nBetter find out who! 😏"
    )
    if crush_msg:
        if update.message.reply_to_message:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=crush_msg,
                reply_to_message_id=update.message.reply_to_message.message_id,
                parse_mode='HTML'
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=crush_msg,
                parse_mode='HTML'
            )

async def confess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = await extract_target_user(update, context)
    if not target:
        await update.message.reply_text("Reply to someone or mention them for confession!", reply_to_message_id=update.message.message_id)
        return
    confession = ""
    if update.message.reply_to_message:
        confession = " ".join(context.args) if context.args else "I have something to tell you..."
    else:
        confession = " ".join(context.args[1:]) if len(context.args) > 1 else "I have something to tell you..."
    if contains_links(confession) or contains_abuse(confession):
        await update.message.reply_text("❌ Confession contains inappropriate content!", reply_to_message_id=update.message.message_id)
        return
    try:
        await update.message.delete()
    except:
        pass
    target_mention = get_mention(target)
    msg = (
        f"💌 <b>Anonymous Confession</b>\n"
        f"Hey {target_mention}! Someone wants to confess:\n"
        f"<i>{confession}</i>\n"
        f"Wonder who it could be? 🤔"
    )
    if update.message.reply_to_message:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=msg,
            reply_to_message_id=update.message.reply_to_message.message_id,
            parse_mode='HTML'
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=msg,
            parse_mode='HTML'
        )

async def flirt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = update.message.reply_to_message
    target = await extract_target_user(update, context) or update.effective_user
    mention = get_mention(target)
    prompt = f"Write a flirty but savage one-liner for {mention}. Under 20 words. End by mentioning {mention}."
    flirt_msg = await send_ai_message(
        update, context,
        system_prompt="You are Samira. Flirty but with attitude. Mention user at end.",
        user_prompt=prompt,
        fallback=f"I'm too busy to flirt rn 😏\n{mention}",
        reply_to=target_msg.message_id if target_msg else update.message.message_id
    )
    if flirt_msg:
        reply_id = target_msg.message_id if target_msg else update.message.message_id
        await update.message.reply_text(flirt_msg, reply_to_message_id=reply_id, parse_mode='HTML')

async def truth_or_dare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmd = update.message.text.split()[0].lower()
    game_type = "truth" if "truth" in cmd else "dare"
    target_msg = update.message.reply_to_message
    target = await extract_target_user(update, context) or update.effective_user
    mention = get_mention(target)
    prompt = f"Generate a spicy but safe {game_type} question for {mention}. One sentence. End by mentioning {mention}."
    question = await send_ai_message(
        update, context,
        system_prompt=f"You are Samira. Give a fun {game_type} challenge. Mention user at end.",
        user_prompt=prompt,
        fallback=f"Your {game_type} is: ... I forgot 😅\n{mention}",
        reply_to=target_msg.message_id if target_msg else update.message.message_id
    )
    if question:
        reply_id = target_msg.message_id if target_msg else update.message.message_id
        await update.message.reply_text(question, reply_to_message_id=reply_id, parse_mode='HTML')

async def dice_roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dice_msg = await update.message.reply_dice(emoji='🎲')
    value = dice_msg.dice.value
    messages = {
        1: "Rolled a 1! Bad luck today 😬",
        2: "Rolled a 2! Could be worse 🤷",
        3: "Rolled a 3! Average hai average 😏",
        4: "Rolled a 4! Not bad yaar 👍",
        5: "Rolled a 5! Almost perfect! 🔥",
        6: "Rolled a 6! Lucky you! 🎉"
    }
    await asyncio.sleep(3)
    await update.message.reply_text(messages[value], reply_to_message_id=dice_msg.message_id)

async def choose_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Give me options to choose from! `/choose option1 or option2 or option3`", reply_to_message_id=update.message.message_id)
        return
    text = " ".join(context.args)
    if contains_links(text) or contains_abuse(text):
        await update.message.reply_text("❌ Contains inappropriate content!", reply_to_message_id=update.message.message_id)
        return
    prompt = f"Choose one option from: {text}. Explain your choice briefly and sassily."
    choice = await send_ai_message(
        update, context,
        system_prompt="You are Samira. Choose an option and explain why with sass.",
        user_prompt=prompt,
        fallback="I choose... to not choose 😎"
    )
    if choice:
        await update.message.reply_text(choice, reply_to_message_id=update.message.message_id, parse_mode='HTML')

async def send_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        await update.message.reply_text("Use in groups.", reply_to_message_id=update.message.message_id)
        return
    if not await is_user_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        await update.message.reply_text("Admins only.", reply_to_message_id=update.message.message_id)
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a user's message with /send <your message>", reply_to_message_id=update.message.message_id)
        return
    target_msg = update.message.reply_to_message
    custom_text = " ".join(context.args)
    if not custom_text:
        await update.message.reply_text("Provide a message after /send", reply_to_message_id=update.message.message_id)
        return
    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=custom_text,
            reply_to_message_id=target_msg.message_id
        )
    except Exception as e:
        await update.message.reply_text(f"Failed: {e}", reply_to_message_id=update.message.message_id)

# /dev command - Developed by @MrLuffy12377 (D Luffy)
async def dev_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /dev command - shows developer info and contact link."""
    dev_msg = (
        "👨‍💻 <b>Developer Info</b>\n\n"
        "This bot was developed by <b>D Luffy</b>\n"
        "Telegram: @MrLuffy12377\n\n"
        "💬 Feel free to reach out for queries, suggestions, or collaborations!"
    )
    keyboard = [
        [InlineKeyboardButton("📩 Contact Developer", url="https://t.me/MrLuffy12377")],
        [InlineKeyboardButton("⭐ Star on GitHub", url="https://github.com/MrLuffy12377")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        dev_msg,
        parse_mode='HTML',
        reply_markup=reply_markup,
        reply_to_message_id=update.message.message_id
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = (
        "✨ <b>Samira Bot - Your Savage Delhi Girl</b> ✨\n"
        "I roast, flirt, moderate, and bring chaos! 💅\n"
        "🎯 <b>Fun Commands:</b>\n"
        "• /troast or /r - Savage roast 🔥\n"
        "• /shayari or /s - Romantic shayari 💕\n"
        "• /couple or /c - Couple prediction 💑\n"
        "• /crush {msg} - Anonymous crush msg 💌\n"
        "• /confess {msg} - Anonymous confession 🤫\n"
        "• /flirt - Flirty lines 😏\n"
        "• /truth or /t - Truth question 🤔\n"
        "• /dare or /d - Dare challenge 😈\n"
        "• /dice - Roll the dice 🎲\n"
        "• /choose - Let me choose 🎯\n"
        "⚡ <b>Admin Commands:</b>\n"
        "• /ban - Ban user 🔨\n"
        "• /mute - Mute user 🤐\n"
        "• /warn or /w - Warn user ⚠️\n"
        "• /adminlist - List admins 👑\n"
        "• /send {msg} - Send as reply 📝\n"
        "• /checklink on/off - Toggle link check 🔗\n"
        "⚙️ <b>Utility:</b>\n"
        "• /welcome - Welcome users 👋\n"
        "• /ping or /alive - Check status 🤖\n"
        "• /dev - Developer info 👨‍💻\n"
        "• /help or /h - This menu 📖\n"
        "💡 <b>Tips:</b>\n"
        "• Reply to messages for targeted actions\n"
        "• Some commands work without / too!\n"
        "• I auto-delete spam links when enabled\n"
        "Use me in groups! DMs are boring 🙄\n\n"
        "<i>Developed by @MrLuffy12377 (D Luffy)</i>"
    )
    keyboard = [
        [
            InlineKeyboardButton("💎 Join Channel", url=CHANNEL_LINK),
            InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/MrLuffy12377")
        ],
        [
            InlineKeyboardButton("🤖 Clone This Bot", url=f"tg://user?id={OWNER_ID}&text=I want to clone Samira bot")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=HELP_PHOTO_URL,
            caption=caption,
            parse_mode='HTML',
            reply_markup=reply_markup,
            reply_to_message_id=update.message.message_id
        )
    except Exception as e:
        await update.message.reply_text(caption, parse_mode='HTML', reply_markup=reply_markup, reply_to_message_id=update.message.message_id)

# ======================
# MAIN
# ======================
def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is not set")
        exit(1)
    if not OPENROUTER_API_KEYS:
        logger.error("OPENROUTER_API_KEYS environment variable is not set correctly")
        exit(1)
    application = Application.builder().token(BOT_TOKEN).build()
    # Bot 1 commands — Developed by @MrLuffy12377 (D Luffy)
    application.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Hey! I'm Samira 💫 Let's chat!\n\n<i>Developed by @MrLuffy12377</i>", parse_mode='HTML', reply_to_message_id=u.message.message_id)))
    application.add_handler(CommandHandler("stop", lambda u, c: u.message.reply_text("Okay bye! 👋 Use /start to wake me up again", reply_to_message_id=u.message.message_id)))
    # Bot 2 commands
    application.add_handler(CommandHandler("welcome", welcome_toggle))
    application.add_handler(CommandHandler("checklink", checklink_toggle))
    application.add_handler(CommandHandler(["ping", "alive"], ping_alive))
    application.add_handler(CommandHandler("ban", ban_user))
    application.add_handler(CommandHandler("mute", mute_user))
    application.add_handler(CommandHandler(["warn", "w"], warn_user))
    application.add_handler(CommandHandler("adminlist", admin_list))
    application.add_handler(CommandHandler(["troast", "roast", "r"], troast_user))
    application.add_handler(CommandHandler(["shayari", "s"], shayari))
    application.add_handler(CommandHandler(["couple", "c"], couple))
    application.add_handler(CommandHandler("crush", crush_anonymous))
    application.add_handler(CommandHandler("confess", confess))
    application.add_handler(CommandHandler("flirt", flirt))
    application.add_handler(CommandHandler(["truth", "t"], truth_or_dare))
    application.add_handler(CommandHandler(["dare", "d"], truth_or_dare))
    application.add_handler(CommandHandler("dice", dice_roll))
    application.add_handler(CommandHandler("choose", choose_option))
    application.add_handler(CommandHandler("send", send_custom))
    application.add_handler(CommandHandler(["help", "h"], help_command))
    application.add_handler(CommandHandler("dev", dev_command))
    # Chat member handler
    application.add_handler(ChatMemberHandler(track_new_members, ChatMemberHandler.MY_CHAT_MEMBER))
    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_links), group=1)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot1_message_handler), group=2)
    if WEBHOOK_URL:
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"https://{WEBHOOK_URL}/{BOT_TOKEN}",
            allowed_updates=Update.ALL_TYPES
        )
    else:
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    # Developed by @MrLuffy12377 (D Luffy)
    logger.info("🚀 Starting Samira Bot — FULL HUMAN + COMMAND MODE")
    logger.info("👨‍💻 Developed by @MrLuffy12377 (D Luffy)")
    logger.info(f"Initialized with {len(OPENROUTER_API_KEYS)} API keys (OpenRouter)")
    logger.info(f"Spam prevention: Max {SPAM_PREVENTION['max_messages_per_minute']} msg/min, {SPAM_PREVENTION['max_same_message_repeats']} repeats, {SPAM_PREVENTION['cooldown_period']}s cooldown")
    main()

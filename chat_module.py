# ============================================================
# Samira Chat Bot - Chat Module
# Developed by @MrLuffy12377 (D Luffy)
# GitHub: https://github.com/MrLuffy12377
# Contact: https://t.me/MrLuffy12377
# ============================================================
import asyncio
import logging
import re
import os
import time
from typing import Optional
from telegram import Update, constants, User
from telegram.ext import ContextTypes
from openai import AsyncOpenAI, RateLimitError

logger = logging.getLogger(__name__)

# ======================
# CHAT MODULE CONFIGURATION
# ======================

# Define the bot's personality for AI responses
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

# Fixed responses dictionary
fixed_responses = {
    "hope": "hii",
    "hello": "hi",
    "cat": "Meeeeeaaaaaaaaawwwwwww",
    "hlo": "Hello",
    "hoi": "hoi hoi",
    "hii": "hi",
}

# Blocked users and groups configuration (from env)
BLOCKED_USERS = {int(x) for x in os.getenv('BLOCKED_USERS', '').split(',') if x.strip().isdigit()}
BLOCKED_USERNAMES = {x.lower() for x in os.getenv('BLOCKED_USERNAMES', '').split(',') if x.strip()}
BLOCKED_GROUPS = {int(x) for x in os.getenv('BLOCKED_GROUPS', '').split(',') if x.strip().isdigit()}
BLOCKED_GROUP_NAMES = {x.lower() for x in os.getenv('BLOCKED_GROUP_NAMES', '').split(',') if x.strip()}

# Spam prevention configuration
SPAM_PREVENTION = {
    "enabled": True,
    "max_messages_per_minute": int(os.getenv('MAX_MESSAGES_PER_MINUTE', '5')),
    "max_same_message_repeats": int(os.getenv('MAX_SAME_MESSAGE_REPEATS', '3')),
    "cooldown_period": int(os.getenv('COOLDOWN_PERIOD', '300')),
}

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
                    logger.info(f"API Key {self.current_index + 1} has been reset and is now available")
                logger.info(f"Rotated to API Key {self.current_index + 1}")
                return True
            attempts += 1
        logger.warning("All API keys are exhausted!")
        return False
    
    def mark_key_exhausted(self):
        reset_time = time.time() + (24 * 3600)
        self.key_status[self.current_index] = {
            'exhausted': True, 
            'reset_time': reset_time
        }
        logger.info(f"API Key {self.current_index + 1} marked as exhausted. Will reset at: {time.ctime(reset_time)}")
        return self.rotate_to_next_key()
    
    def are_all_keys_exhausted(self):
        current_time = time.time()
        available_keys = 0
        for key_info in self.key_status.values():
            if not key_info['exhausted'] or (key_info['reset_time'] and current_time > key_info['reset_time']):
                available_keys += 1
        return available_keys == 0

# Initialize API key manager from env
OPENROUTER_API_KEYS = [k.strip() for k in os.getenv('OPENROUTER_API_KEYS', '').split(',') if k.strip()]
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'meta-llama/llama-3.1-70b-instruct')
api_manager = APIKeyManager(OPENROUTER_API_KEYS)

# ======================
# CHAT MODULE STATE
# ======================
last_response_time = 0
message_history = []
rate_limit_lock = asyncio.Lock()

# Spam tracking dictionaries
user_message_counts = {}
user_last_reset = {}
user_message_history = {}
spam_cooldowns = {}

# Bot active status
bot_active = True

# ======================
# HELPER FUNCTIONS
# ======================
def is_bot_user(user: Optional[User]) -> bool:
    return user and user.is_bot

def is_blocked(update: Update) -> bool:
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

def is_spam(update: Update) -> bool:
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
        spam_cooldowns[sender_id] = current_time + SPAM_PREVENTION["cooldown_period"]
        return True
    
    user_history = user_message_history[sender_id]
    user_history = [(msg, timestamp) for msg, timestamp in user_history if current_time - timestamp <= 600]
    user_message_history[sender_id] = user_history
    user_history.append((message_text, current_time))
    
    repeated_count = sum(1 for msg, _ in user_history if msg == message_text)
    if repeated_count > SPAM_PREVENTION["max_same_message_repeats"]:
        spam_cooldowns[sender_id] = current_time + SPAM_PREVENTION["cooldown_period"]
        return True
    
    return False

def get_group_name(update: Update) -> str:
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        return "Private"
    else:
        return update.effective_chat.title or "Unknown"

def get_user_name(user: User) -> str:
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}"
    elif user.first_name:
        return user.first_name
    elif user.last_name:
        return user.last_name
    else:
        return "Unknown"

async def is_directed_at_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    bot = context.bot
    bot_username = (await bot.get_me()).username.lower()
    
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        return True
    
    if update.message.text and f"@{bot_username}" in update.message.text.lower():
        return True
    
    if update.message.reply_to_message:
        if update.message.reply_to_message.from_user.id == bot.id:
            return True
    
    return False

async def generate_ai_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
    logger.debug("Starting AI response generation")
    logger.debug(f"Using {api_manager.get_current_key_info()}")
    
    if api_manager.are_all_keys_exhausted():
        logger.warning("All API keys are currently exhausted!")
        return None
    
    current_group = get_group_name(update)
    current_user_id = update.effective_user.id
    current_username = update.effective_user.username
    current_name = get_user_name(update.effective_user)
    current_message = update.message.text
    
    history_text = "Chat History:\n"
    for entry in message_history:
        if entry["sender"] == "user":
            history_text += f"Group: {entry['group_name']}, User ID: {entry['user_id']}, Username: {entry['username'] or 'N/A'}, Name: {entry['name']}, Message: {entry['message']}\n"
        elif entry["sender"] == "bot":
            history_text += f"Bot Reply: {entry['message']}\n"
    
    current_text = f"Currently Asked Question:\nGroup: {current_group}, User ID: {current_user_id}, Username: {current_username or 'N/A'}, Name: {current_name}, Message: {current_message}"
    ai_prompt = f"{history_text}\n{current_text}"
    
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
            return response.choices[0].message.content
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to generate AI response with {api_manager.get_current_key_info()}: {error_msg}")
            
            if "429" in error_msg or "rate_limit" in error_msg.lower():
                if not api_manager.mark_key_exhausted():
                    break
            else:
                if not api_manager.rotate_to_next_key():
                    break
            attempt += 1
    
    logger.error("All API keys failed or are exhausted")
    return None

async def send_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, response_text: str):
    global last_response_time
    
    async with rate_limit_lock:
        current_time = time.time()
        if current_time - last_response_time < 1:
            wait_time = 1 - (current_time - last_response_time)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        last_response_time = time.time()
    
    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=response_text,
            reply_to_message_id=update.message.message_id
        )
        logger.info(f"Sent response: {response_text}")
    except Exception as e:
        logger.error(f"Failed to send message: {str(e)}")

# ======================
# MAIN CHAT HANDLER
# ======================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global message_history, bot_active
    
    if not update.message or not update.message.text:
        return
    
    if not bot_active:
        logger.debug("Bot is currently stopped, ignoring message")
        return
    
    if is_bot_user(update.effective_user):
        logger.debug("Message from bot detected, ignoring...")
        return
    
    if is_blocked(update):
        logger.debug("Message from blocked user/group, ignoring...")
        return
    
    if is_spam(update):
        logger.debug("Spam detected, ignoring message...")
        return
    
    text = update.message.text.lower()
    
    for trigger, response in fixed_responses.items():
        if re.search(r'\b' + re.escape(trigger) + r'\b', text):
            user_entry = {
                "sender": "user",
                "group_name": get_group_name(update),
                "user_id": update.effective_user.id,
                "username": update.effective_user.username,
                "name": get_user_name(update.effective_user),
                "message": update.message.text
            }
            bot_entry = {
                "sender": "bot",
                "message": response
            }
            message_history.extend([user_entry, bot_entry])
            message_history = message_history[-10:]
            
            delay = random.uniform(5, 25)
            await asyncio.sleep(delay)
            await send_reply(update, context, response)
            return
    
    is_directed = await is_directed_at_bot(update, context)
    
    if is_directed:
        if re.search(r'http\S+|www\S+', text):
            logger.debug("Message contains a link, ignoring it...")
            return
        
        # Placeholder for abuse check - no actual words in code
        # You will add your own ABUSE_WORDS set in main.py and pass it here if needed
        # For now, we skip this check in chat_module to keep it clean
        
        ai_response = await generate_ai_response(update, context)
        
        if ai_response:
            user_entry = {
                "sender": "user",
                "group_name": get_group_name(update),
                "user_id": update.effective_user.id,
                "username": update.effective_user.username,
                "name": get_user_name(update.effective_user),
                "message": update.message.text
            }
            bot_entry = {
                "sender": "bot",
                "message": ai_response
            }
            message_history.extend([user_entry, bot_entry])
            message_history = message_history[-10:]
            
            delay = random.uniform(5, 15)
            await asyncio.sleep(delay)
            await send_reply(update, context, ai_response)

import os
import re
import json
import base64
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from groq import Groq

# 1. Background Web Server for Render 24/7 uptime
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is online 24/7")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

# 2. Setup Bot & Groq
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

TEXT_MODEL = "openai/gpt-oss-120b"
VISION_MODEL = "qwen/qwen3.8-27b"

SYSTEM_PROMPT = (
    "You are a helpful, warm AI assistant. "
    "Always reply in the exact language the user asks in (e.g., English for English, Vietnamese for Vietnamese). "
    "Provide thorough, detailed, and complete answers without stopping early. "
    "Do NOT use markdown headers like ### or ##. "
    "Do NOT use bold asterisks like **. "
    "Use clean plain text with simple bullet points (-) when needed."
)

HISTORY_FILE = "chat_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_history(history_data):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False)
    except Exception:
        pass

user_conversations = load_history()

def clean_text(text):
    text = re.sub(r'#{1,6}\s*', '', text)
    text = text.replace('**', '')
    return text.strip()

def send_long_message(chat_id, text):
    max_len = 4000
    for i in range(0, len(text), max_len):
        bot.send_message(chat_id, text[i:i+max_len])

def get_user_history(user_id_str):
    if user_id_str not in user_conversations:
        user_conversations[user_id_str] = []
    return user_conversations[user_id_str]

def generate_complete_response(model_name, messages_payload, max_tokens=2000):
    full_content = ""
    for _ in range(3):
        response = client.chat.completions.create(
            model=model_name,
            max_tokens=max_tokens,
            messages=messages_payload
        )
        choice = response.choices[0]
        text_chunk = clean_text(choice.message.content)
        full_content += ("\n" + text_chunk if full_content else text_chunk)
        
        if choice.finish_reason != "length":
            break
            
        messages_payload.append({"role": "assistant", "content": text_chunk})
        messages_payload.append({"role": "user", "content": "Continue exactly where you left off without repeating."})
        
    return full_content

# Handle Text Prompts
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    bot.send_chat_action(message.chat.id, 'typing')
    user_id = str(message.chat.id)
    history = get_user_history(user_id)
    
    # Capture replied message text if user used Telegram reply feature
    user_input = message.text
    if message.reply_to_message and message.reply_to_message.text:
        quoted_text = message.reply_to_message.text
        user_input = f"[Quoting previous message: \"{quoted_text}\"]\nUser request: {message.text}"
    
    history.append({"role": "user", "content": user_input})
    if len(history) > 10:
        history = history[-10:]
        user_conversations[user_id] = history
        
    messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    try:
        reply = generate_complete_response(TEXT_MODEL, messages_payload, max_tokens=2000)
        history.append({"role": "assistant", "content": reply})
        user_conversations[user_id] = history
        save_history(user_conversations)
        send_long_message(message.chat.id, reply)
    except Exception as e:
        bot.reply_to(message, f"Text Error: {e}")

# Handle Image Prompts
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    bot.send_chat_action(message.chat.id, 'typing')
    user_id = str(message.chat.id)
    history = get_user_history(user_id)
    
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        img_b64 = base64.b64encode(downloaded).decode('utf-8')
        
        user_prompt = message.caption if message.caption else "Analyze and explain this image clearly."
        
        messages_payload = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]
            }
        ]
        
        reply = generate_complete_response(VISION_MODEL, messages_payload, max_tokens=800)
        history.append({"role": "user", "content": f"[Sent an image]: {user_prompt}"})
        history.append({"role": "assistant", "content": reply})
        user_conversations[user_id] = history
        save_history(user_conversations)
        send_long_message(message.chat.id, reply)
    except Exception as e:
        bot.reply_to(message, f"Photo Error: {e}")

print("Cloud bot is listening...")
bot.infinity_polling()

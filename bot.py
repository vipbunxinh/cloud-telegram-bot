import os
import re
import base64
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from groq import Groq

# 1. Giữ Render Web Service chạy liên tục 24/7
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

# 2. Khởi tạo Telegram & Groq
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

MODEL_NAME = "qwen/qwen3.8-27b"

# Bộ nhớ lưu lịch sử chat cho từng người dùng
user_conversations = {}

SYSTEM_PROMPT = (
    "You are a helpful, warm AI assistant. "
    "Always reply in the exact language the user asks in (e.g., English for English, Vietnamese for Vietnamese). "
    "Keep answers concise and natural. Do not write excessively long sentences. "
    "Do NOT use markdown headers like ### or ##. "
    "Do NOT use bold asterisks like **. "
    "Use simple plain text with clean bullet points (-) if listing."
)

def clean_text(text):
    text = re.sub(r'#{1,6}\s*', '', text)
    text = text.replace('**', '')
    return text.strip()

def send_long_message(chat_id, text):
    max_len = 4000
    for i in range(0, len(text), max_len):
        bot.send_message(chat_id, text[i:i+max_len])

# Lấy lịch sử chat (giữ tối đa 6 tin nhắn gần nhất để không bị quá tải token)
def get_user_history(user_id):
    if user_id not in user_conversations:
        user_conversations[user_id] = []
    return user_conversations[user_id]

# Xử lý tin nhắn văn bản (có nhớ ngữ cảnh)
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    bot.send_chat_action(message.chat.id, 'typing')
    user_id = message.chat.id
    history = get_user_history(user_id)
    
    # Thêm tin nhắn mới của bạn vào lịch sử
    history.append({"role": "user", "content": message.text})
    
    # Giới hạn giữ lại 6 tin nhắn gần nhất
    if len(history) > 6:
        history = history[-6:]
        user_conversations[user_id] = history
        
    messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            max_tokens=800,
            messages=messages_payload
        )
        reply = clean_text(response.choices[0].message.content)
        
        # Lưu câu trả lời của AI vào lịch sử để nhớ cho câu tiếp theo
        history.append({"role": "assistant", "content": reply})
        
        send_long_message(user_id, reply)
    except Exception as e:
        bot.reply_to(message, f"Text Error: {e}")

# Xử lý hình ảnh
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    bot.send_chat_action(message.chat.id, 'typing')
    user_id = message.chat.id
    history = get_user_history(user_id)
    
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        img_b64 = base64.b64encode(downloaded).decode('utf-8')
        
        user_prompt = message.caption if message.caption else "Analyze and explain this image clearly."
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            max_tokens=800,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                    ]
                }
            ]
        )
        reply = clean_text(response.choices[0].message.content)
        
        # Lưu ngữ cảnh ảnh vào lịch sử
        history.append({"role": "user", "content": f"[Sent an image]: {user_prompt}"})
        history.append({"role": "assistant", "content": reply})
        
        send_long_message(user_id, reply)
    except Exception as e:
        bot.reply_to(message, f"Photo Error: {e}")

print("Cloud bot is listening...")
bot.infinity_polling()

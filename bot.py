import os
import base64
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from groq import Groq

# 1. Giữ Render Web Service luôn chạy 24/7
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running 24/7!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# Chạy web server ngầm
threading.Thread(target=run_web_server, daemon=True).start()

# 2. Thiết lập Telegram & Groq
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

MODEL_NAME = "qwen/qwen3.8-27b"

# Xử lý tin nhắn văn bản
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": message.text}]
        )
        bot.reply_to(message, response.choices[0].message.content, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Lỗi text: {e}")

# Xử lý hình ảnh
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        img_b64 = base64.b64encode(downloaded).decode('utf-8')
        
        prompt = message.caption if message.caption else "Analyze and read this image in detail."
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                    ]
                }
            ]
        )
        bot.reply_to(message, response.choices[0].message.content, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Lỗi ảnh: {e}")

print("Cloud bot is listening...")
bot.infinity_polling()

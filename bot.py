import os
import re
import base64
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from groq import Groq

# 1. Máy chủ web mini để giữ Render chạy liên tục 24/7
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

# 2. Khởi tạo bot Telegram và Groq
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

MODEL_NAME = "qwen/qwen3.8-27b"

# Nhắc nhở để bot dùng câu ngắn gọn, từ ngữ tự nhiên và không dùng ký tự định dạng lạ
SYSTEM_PROMPT = (
    "Bạn là một trợ lý thông minh, thân thiện. "
    "Dùng từ ngữ đơn giản, dễ hiểu và tự nhiên. "
    "Không dùng câu quá dài. "
    "Tuyệt đối không dùng dấu thăng như ### hay ## để làm tiêu đề. "
    "Không dùng dấu hoa thị ** để in đậm. "
    "Dùng các dấu gạch đầu dòng (-) ngắn gọn khi liệt kê."
)

def clean_text(text):
    # Loại bỏ các ký tự ### và **
    text = re.sub(r'#{1,6}\s*', '', text)
    text = text.replace('**', '')
    return text.strip()

# Chia nhỏ tin nhắn nếu phản hồi dài hơn 4000 ký tự để không bị lỗi Telegram
def send_long_message(chat_id, text):
    max_len = 4000
    for i in range(0, len(text), max_len):
        bot.send_message(chat_id, text[i:i+max_len])

# Xử lý tin nhắn chữ
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text}
            ]
        )
        reply = clean_text(response.choices[0].message.content)
        send_long_message(message.chat.id, reply)
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
        
        user_prompt = message.caption if message.caption else "Hãy phân tích và đọc chi tiết bức ảnh này."
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
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
        send_long_message(message.chat.id, reply)
    except Exception as e:
        bot.reply_to(message, f"Lỗi ảnh: {e}")

print("Cloud bot is listening...")
bot.infinity_polling()

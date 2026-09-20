import os
import base64
import telebot
from groq import Groq

# Cloud variables (will be set in your host settings)
TELEGRAM_TOKEN = os.getenv("8955332069:AAEDfBcZOX90uVRAE5yU47stzKZi9nl5JVk")
GROQ_API_KEY = os.getenv("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")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# 1. Text handler (Llama 3.3 70B - fast reasoning)
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": message.text}]
        )
        bot.reply_to(message, response.choices[0].message.content)
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

# 2. Image handler (Llama 3.2 Vision - reads charts and homework)
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        img_b64 = base64.b64encode(downloaded).decode('utf-8')
        
        prompt = message.caption if message.caption else "Analyze and read this image in detail."
        
        response = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
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
        bot.reply_to(message, response.choices[0].message.content)
    except Exception as e:
        bot.reply_to(message, f"Photo Error: {e}")

print("Cloud bot is active!")
bot.infinity_polling()

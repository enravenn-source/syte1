from flask import Flask, request, render_template_string
from telethon import TelegramClient
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact, InputMediaContact
from telethon.tl.functions.messages import SendMediaRequest
import re
import asyncio
import os
import random
import logging

app = Flask(__name__)

API_ID = int(os.environ.get('API_ID', 30095316))
API_HASH = os.environ.get('API_HASH', 'fd5058fa304a371daf1216f110828222')
USER_PHONE = os.environ.get('USER_PHONE', '+79923018941')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = TelegramClient('session', API_ID, API_HASH)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Telegram Contact Share</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 500px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 { color: #2AABEE; text-align: center; margin-top: 0; }
        .greeting {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
            font-size: 16px;
        }
        input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            margin-bottom: 20px;
            box-sizing: border-box;
        }
        button {
            background: #2AABEE;
            color: white;
            border: none;
            padding: 14px;
            border-radius: 8px;
            width: 100%;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
        }
        button:hover { background: #2296d8; }
        .result {
            margin-top: 20px;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }
        .success { background: #d4edda; }
        .error { background: #f8d7da; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📱 Поиск контактов</h1>
        <div class="greeting">
            👋 Приветствую тебя, юный рекрутер!<br>
            Забрёл сюда в поисках контакта?<br>
            Вводи номер кандидата и свой тег.
        </div>
        
        <form method="POST" action="/send_contact">
            <input type="text" name="target_phone" placeholder="+79001234567" required>
            <input type="text" name="requester_username" placeholder="твой тег (без @)" required>
            <button type="submit">🔍 Найти и отправить контакт</button>
        </form>
        
        {% if result %}
        <div class="result {% if result.success %}success{% else %}error{% endif %}">
            {% if result.success %}
                <strong>✅ Готово, проверяй личные сообщения!</strong>
            {% else %}
                <strong>😕 Кажется, аккаунт полностью скрыт, либо я поломался.</strong>
            {% endif %}
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

async def find_and_send(target_phone, requester_username):
    try:
        # Ищем цель
        contact = InputPhoneContact(client_id=0, phone=target_phone, first_name="", last_name="")
        result = await client(ImportContactsRequest([contact]))
        
        if not result.users:
            return False
        
        user = result.users[0]
        
        # Ищем запросившего
        requester = await client.get_entity(requester_username)
        
        # Отправляем контакт
        await client.send_message(requester, "Контакт по запросу", file=user)
        
        # Удаляем из контактов
        await client(DeleteContactsRequest([user.id]))
        
        return True
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return False

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/send_contact', methods=['POST'])
def send_contact():
    target_phone = re.sub(r'[^\d+]', '', request.form['target_phone'])
    requester_username = request.form['requester_username']
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success = loop.run_until_complete(find_and_send(target_phone, requester_username))
    loop.close()
    
    return render_template_string(HTML, result={'success': success})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

from flask import Flask, request, render_template_string
from telethon import TelegramClient
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
import re
import asyncio
import os
import random
import logging

app = Flask(__name__)

# Настройки из переменных окружения
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
USER_PHONE = os.environ.get('USER_PHONE', '')

# Путь для сохранения сессии
SESSION_PATH = '/app/data/session'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# HTML шаблон
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
        h1 { color: #2AABEE; text-align: center; }
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
            font-size: 16px;
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
            <input type="text" name="target_phone" placeholder="Номер кандидата (например +79001234567)" required>
            <input type="text" name="requester_username" placeholder="Твой Telegram (без @)" required>
            <button type="submit">🔍 Найти и отправить контакт</button>
        </form>
        
        {% if result %}
        <div class="result {% if result.success %}success{% else %}error{% endif %}">
            {% if result.success %}
                <strong>✅ Готово, проверяй личные сообщения!</strong>
            {% else %}
                <strong>😕 Кажется, аккаунт полностью скрыт, либо я поломался.</strong>
                <p>Попробуй отправить себе контакт, который точно есть.</p>
            {% endif %}
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

# Создаем клиента один раз при старте
client = TelegramClient(SESSION_PATH, API_ID, API_HASH)

# Инициализация при старте (без before_first_request)
def init_client_sync():
    """Синхронная инициализация клиента"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        if not client.is_connected():
            loop.run_until_complete(client.connect())
            if not loop.run_until_complete(client.is_user_authorized()):
                logger.info("Клиент не авторизован. Требуется вход через консоль.")
                # Не отправляем код автоматически, ждем ручного ввода
    except Exception as e:
        logger.error(f"Ошибка при инициализации: {e}")
    finally:
        loop.close()

# Запускаем инициализацию при загрузке модуля
init_client_sync()

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/send_contact', methods=['POST'])
def send_contact():
    target_phone = request.form.get('target_phone', '')
    requester_username = request.form.get('requester_username', '')
    
    clean_phone = re.sub(r'[^\d+]', '', target_phone)
    
    async def process():
        try:
            # Подключаемся если нужно
            if not client.is_connected():
                await client.connect()
            
            # Проверяем авторизацию
            if not await client.is_user_authorized():
                return {'success': False, 'error': 'not_authorized'}
            
            # Ищем цель
            contact = InputPhoneContact(client_id=0, phone=clean_phone, first_name="", last_name="")
            result = await client(ImportContactsRequest([contact]))
            
            if not result.users:
                return {'success': False}
            
            user = result.users[0]
            
            # Ищем запросившего
            try:
                requester = await client.get_entity(requester_username)
            except:
                await client(DeleteContactsRequest([user.id]))
                return {'success': False}
            
            # Отправляем контакт
            await client.send_message(
                requester,
                f"🔍 Контакт по вашему запросу",
                file=user
            )
            
            # Удаляем из контактов
            await client(DeleteContactsRequest([user.id]))
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            return {'success': False}
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(process())
    loop.close()
    
    return render_template_string(HTML, result=result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

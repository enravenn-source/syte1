from flask import Flask, request, render_template_string
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
import re
import asyncio
import os
import logging

app = Flask(__name__)

API_ID = int(os.environ.get('API_ID', 30095316))
API_HASH = os.environ.get('API_HASH', 'fd5058fa304a371daf1216f110828222')
SESSION_STRING = os.environ.get('SESSION_STRING')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем клиента
if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    logger.info("✅ Загружена сессия из SESSION_STRING")
else:
    client = TelegramClient('session', API_ID, API_HASH)
    logger.info("⚠️ SESSION_STRING не найдена, использую файл")

# Глобальная переменная для статуса авторизации
auth_status = None

async def check_auth():
    """Проверка авторизации"""
    global auth_status
    try:
        if not client.is_connected():
            await client.connect()
        
        if await client.is_user_authorized():
            me = await client.get_me()
            auth_status = {
                'status': 'ok',
                'name': me.first_name,
                'id': me.id
            }
            return True
        else:
            auth_status = {
                'status': 'not_authorized',
                'message': 'Сессия есть, но аккаунт не авторизован'
            }
            return False
    except Exception as e:
        auth_status = {
            'status': 'error',
            'message': str(e)
        }
        return False

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
        .auth-status {
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
            font-weight: bold;
        }
        .auth-ok { background: #d4edda; color: #155724; }
        .auth-error { background: #f8d7da; color: #721c24; }
        .auth-warning { background: #fff3cd; color: #856404; }
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
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
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
        
        {% if auth %}
        <div class="auth-status {% if auth.status == 'ok' %}auth-ok{% elif auth.status == 'error' %}auth-error{% else %}auth-warning{% endif %}">
            {% if auth.status == 'ok' %}
                ✅ Аккаунт <strong>{{ auth.name }}</strong> (ID: {{ auth.id }}) авторизован
            {% elif auth.status == 'error' %}
                ❌ Ошибка авторизации: {{ auth.message }}
            {% else %}
                ⚠️ {{ auth.message }}
            {% endif %}
        </div>
        {% endif %}
        
        <form method="POST" action="/send_contact">
            <input type="text" name="target_phone" placeholder="+79001234567" required>
            <input type="text" name="requester_username" placeholder="твой тег (без @)" required>
            <button type="submit" {% if auth and auth.status != 'ok' %}disabled{% endif %}>
                🔍 Найти и отправить контакт
            </button>
        </form>
        
        {% if result %}
        <div class="result {% if result.success %}success{% else %}error{% endif %}">
            {% if result.success %}
                <strong>✅ Готово, проверяй личные сообщения!</strong>
            {% else %}
                <strong>😕 Кажется, аккаунт полностью скрыт, либо я поломался.</strong>
                <p style="font-size: 12px; margin-top: 10px;">Ошибка: {{ result.error }}</p>
            {% endif %}
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/')
async def index():
    """Главная страница с проверкой авторизации"""
    await check_auth()
    return render_template_string(HTML, auth=auth_status)

@app.route('/send_contact', methods=['POST'])
async def send_contact():
    """Отправка контакта"""
    # Проверяем авторизацию перед отправкой
    if not await check_auth():
        return render_template_string(HTML, 
                                    auth=auth_status, 
                                    result={'success': False, 'error': 'Аккаунт не авторизован'})
    
    target_phone = re.sub(r'[^\d+]', '', request.form['target_phone'])
    requester_username = request.form['requester_username']
    
    try:
        # Ищем цель
        contact = InputPhoneContact(client_id=0, phone=target_phone, first_name="", last_name="")
        result = await client(ImportContactsRequest([contact]))
        
        if not result.users:
            return render_template_string(HTML, 
                                        auth=auth_status, 
                                        result={'success': False, 'error': 'Пользователь не найден'})
        
        user = result.users[0]
        
        # Ищем запросившего
        try:
            requester = await client.get_entity(requester_username)
        except Exception as e:
            await client(DeleteContactsRequest([user.id]))
            return render_template_string(HTML, 
                                        auth=auth_status, 
                                        result={'success': False, 'error': f'Username не найден: {e}'})
        
        # Отправляем контакт
        await client.send_message(requester, "Контакт по запросу", file=user)
        
        # Удаляем из контактов
        await client(DeleteContactsRequest([user.id]))
        
        return render_template_string(HTML, auth=auth_status, result={'success': True})
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return render_template_string(HTML, 
                                    auth=auth_status, 
                                    result={'success': False, 'error': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

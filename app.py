from flask import Flask, request, render_template_string, session, redirect, url_for
from telethon import TelegramClient
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
from telethon.errors import SessionPasswordNeededError
import re
import asyncio
import os
import logging
from datetime import timedelta

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
app.permanent_session_lifetime = timedelta(days=30)

# Настройки из переменных окружения
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
USER_PHONE = os.environ.get('USER_PHONE', '')

# Проверка наличия настроек
if not all([API_ID, API_HASH, USER_PHONE]):
    print("❌ Ошибка: не все переменные окружения установлены")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальный клиент (будет инициализирован при первом запросе)
client = None

# HTML шаблон
INDEX_HTML = """
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
        .form-group {
            margin-bottom: 20px;
            text-align: left;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: 600;
        }
        input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
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
            margin-top: 10px;
        }
        button:hover { background: #2296d8; }
        .result {
            margin-top: 20px;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }
        .success { background: #d4edda; color: #155724; }
        .error { background: #f8d7da; color: #721c24; }
        .info { background: #d1ecf1; color: #0c5460; }
        .note {
            font-size: 14px;
            color: #666;
            margin-top: 20px;
            padding-top: 10px;
            border-top: 1px solid #ddd;
        }
        .code-input {
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📱 Поиск контактов Telegram</h1>
        
        <div class="greeting">
            👋 Приветствую тебя, юный рекрутер!<br>
            Забрёл сюда в поисках контакта?<br>
            Вводи номер кандидата и свой тег.
        </div>
        
        {% if waiting_code %}
            <div class="result info">
                <strong>🔐 Код отправлен на телефон {{ phone }}</strong>
                <p>Введи код из Telegram</p>
            </div>
            
            <div class="code-input">
                <form method="POST" action="/auth_code">
                    <input type="text" name="code" placeholder="12345" style="text-align: center; font-size: 24px; letter-spacing: 5px;" required>
                    <button type="submit">Подтвердить код</button>
                </form>
            </div>
            
            {% if message %}
                <div class="result info">{{ message }}</div>
            {% endif %}
            
        {% elif not authorized %}
            <div class="result info">
                <strong>🔄 Подготовка авторизации...</strong>
                <p>Пожалуйста, подожди</p>
            </div>
            
        {% else %}
            <form method="POST" action="/send_contact">
                <div class="form-group">
                    <label>📞 Номер кандидата</label>
                    <input type="text" name="target_phone" placeholder="+79001234567" required>
                </div>
                
                <div class="form-group">
                    <label>👤 Твой Telegram (без @)</label>
                    <input type="text" name="requester_username" placeholder="username" required>
                </div>
                
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
        {% endif %}
        
        <div class="note">
            ⚡️ Сервис работает через аккаунт Эдуард
        </div>
    </div>
</body>
</html>
"""

async def init_client():
    """Инициализация клиента"""
    global client
    try:
        client = TelegramClient('session', API_ID, API_HASH)
        await client.connect()
        logger.info("✅ Клиент инициализирован")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации: {e}")
        return False

async def check_auth():
    """Проверка авторизации"""
    if not client or not client.is_connected():
        await init_client()
    return await client.is_user_authorized()

@app.route('/')
async def index():
    """Главная страница"""
    authorized = await check_auth()
    
    if not authorized:
        # Отправляем код
        try:
            if not client.is_connected():
                await client.connect()
            
            result = await client.send_code_request(USER_PHONE)
            session['phone_code_hash'] = result.phone_code_hash
            session['phone'] = USER_PHONE
            logger.info(f"📱 Код отправлен на {USER_PHONE}")
            
            return render_template_string(INDEX_HTML, waiting_code=True, phone=USER_PHONE)
        except Exception as e:
            logger.error(f"❌ Ошибка отправки кода: {e}")
            return render_template_string(INDEX_HTML, authorized=False, message=f"Ошибка: {str(e)}")
    
    return render_template_string(INDEX_HTML, authorized=True)

@app.route('/auth_code', methods=['POST'])
async def auth_code():
    """Ввод кода подтверждения"""
    code = request.form.get('code', '')
    
    if 'phone_code_hash' not in session:
        return render_template_string(INDEX_HTML, authorized=False, message="❌ Сессия истекла, обнови страницу")
    
    try:
        if not client.is_connected():
            await client.connect()
        
        # Вводим код
        await client.sign_in(phone=USER_PHONE, code=code, phone_code_hash=session['phone_code_hash'])
        
        # Успешно!
        logger.info("✅ Авторизация успешна!")
        
        return render_template_string(INDEX_HTML, authorized=True)
        
    except SessionPasswordNeededError:
        return render_template_string(INDEX_HTML, authorized=False, message="❌ Требуется двухфакторная аутентификация (пароль)")
    except Exception as e:
        logger.error(f"❌ Ошибка авторизации: {e}")
        return render_template_string(INDEX_HTML, authorized=False, message=f"❌ Ошибка: {str(e)}")

@app.route('/send_contact', methods=['POST'])
async def send_contact():
    """Отправка контакта"""
    authorized = await check_auth()
    if not authorized:
        return render_template_string(INDEX_HTML, authorized=False, waiting_code=True)
    
    target_phone = request.form.get('target_phone', '')
    requester_username = request.form.get('requester_username', '')
    
    clean_phone = re.sub(r'[^\d+]', '', target_phone)
    
    try:
        # Ищем цель
        contact = InputPhoneContact(client_id=0, phone=clean_phone, first_name="", last_name="")
        result = await client(ImportContactsRequest([contact]))
        
        if not result.users:
            return render_template_string(INDEX_HTML, authorized=True, result={'success': False})
        
        user = result.users[0]
        
        # Ищем запросившего
        try:
            requester = await client.get_entity(requester_username)
        except:
            await client(DeleteContactsRequest([user.id]))
            return render_template_string(INDEX_HTML, authorized=True, result={'success': False})
        
        # Отправляем контакт
        await client.send_message(
            requester,
            f"🔍 Контакт по вашему запросу: {user.first_name or ''} {user.last_name or ''}",
            file=user
        )
        
        # Удаляем из контактов
        await client(DeleteContactsRequest([user.id]))
        
        return render_template_string(INDEX_HTML, authorized=True, result={'success': True})
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")
        return render_template_string(INDEX_HTML, authorized=True, result={'success': False})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

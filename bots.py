#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import urllib.request
import urllib.parse
import urllib.error
import time
import re
from typing import Dict, List, Optional, Any

class GeminiAPI:
    """Класс для работы с Google Gemini API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.model = "gemini-2.0-flash-exp"  # Используем доступную модель
        
    def _make_request(self, url: str, data: dict) -> dict:
        """Выполняет HTTP запрос к API"""
        try:
            json_data = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=json_data,
                headers={
                    'Content-Type': 'application/json',
                }
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f"HTTP Error {e.code}: {error_body}")
            return {"error": f"HTTP {e.code}: {error_body}"}
        except Exception as e:
            print(f"Request error: {e}")
            return {"error": str(e)}
    
    def generate_text(self, prompt: str, system_instruction: str = None) -> str:
        """Генерирует текст с помощью Gemini"""
        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
        
        # Формируем содержимое запроса
        contents = []
        
        # Добавляем системную инструкцию если есть
        if system_instruction:
            contents.append({
                "role": "user",
                "parts": [{"text": f"SYSTEM: {system_instruction}"}]
            })
            contents.append({
                "role": "model", 
                "parts": [{"text": "Понял системную инструкцию, готов помочь!"}]
            })
        
        # Добавляем основной запрос
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        
        data = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 2048,
            },
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH", 
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
        }
        
        response = self._make_request(url, data)
        
        if "error" in response:
            return f"❌ Ошибка API: {response['error']}"
        
        try:
            return response["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            return f"❌ Ошибка обработки ответа: {e}"

class TelegramBot:
    """Класс для работы с Telegram Bot API"""
    
    def __init__(self, token: str, gemini_api: GeminiAPI):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.gemini = gemini_api
        self.last_update_id = 0
        
        # Хранилище пользовательских настроек
        self.user_settings: Dict[int, Dict] = {}
        
        # Стандартные системные промпты
        self.system_prompts = {
            "assistant": "Ты полезный AI-ассистент. Отвечай информативно и дружелюбно. Используй форматирование Telegram: **жирный текст**, *курсив*, `код`, ```блок кода```. Структурируй ответы для лучшего восприятия.",
            "creative": "Ты креативный помощник. Пиши ярко, образно и творчески. Используй эмодзи и красивое форматирование. **Выделяй** важные моменты, создавай *атмосферные* описания.",
            "technical": "Ты технический эксперт. Давай точные, структурированные ответы. Используй:\n• **Заголовки** для разделов\n• `код` для технических терминов\n• Нумерованные списки для инструкций",
            "teacher": "Ты терпеливый учитель. Объясняй просто и понятно. Используй:\n📚 **Основные понятия**\n💡 *Примеры* для иллюстрации\n✅ **Выводы** в конце",
            "casual": "Общайся естественно и дружелюбно, как с хорошим другом. Используй эмодзи 😊 и неформальный стиль. **Подчеркивай** важное, но не будь слишком серьезным."
        }
    
    def _make_request(self, method: str, params: dict = None) -> dict:
        """Выполняет запрос к Telegram API"""
        url = f"{self.base_url}/{method}"
        
        if params:
            data = urllib.parse.urlencode(params).encode('utf-8')
            req = urllib.request.Request(url, data=data)
        else:
            req = urllib.request.Request(url)
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"Telegram API error: {e}")
            return {"ok": False, "error": str(e)}
    
    def get_updates(self) -> List[dict]:
        """Получает обновления от Telegram"""
        params = {
            'offset': self.last_update_id + 1,
            'timeout': 10,
            'allowed_updates': json.dumps(['message', 'callback_query'])
        }
        
        response = self._make_request('getUpdates', params)
        
        if response.get('ok'):
            updates = response['result']
            if updates:
                self.last_update_id = updates[-1]['update_id']
            return updates
        return []
    
    def send_message(self, chat_id: int, text: str, reply_markup: dict = None) -> bool:
        """Отправляет сообщение"""
        params = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': 'true'
        }
        
        if reply_markup:
            params['reply_markup'] = json.dumps(reply_markup)
        
        response = self._make_request('sendMessage', params)
        return response.get('ok', False)
    
    def answer_callback_query(self, callback_query_id: str, text: str = "") -> bool:
        """Отвечает на callback query"""
        params = {
            'callback_query_id': callback_query_id,
            'text': text
        }
        response = self._make_request('answerCallbackQuery', params)
        return response.get('ok', False)
    
    def get_user_settings(self, user_id: int) -> dict:
        """Получает настройки пользователя"""
        if user_id not in self.user_settings:
            self.user_settings[user_id] = {
                'system_prompt': 'assistant',
                'custom_prompt': '',
                'temperature': 0.7
            }
        return self.user_settings[user_id]
    
    def format_gemini_response(self, text: str) -> str:
        """Форматирует ответ Gemini для Telegram"""
        # Убираем лишние пробелы и переносы
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()
        
        # Ограничиваем длину сообщения
        if len(text) > 4000:
            text = text[:4000] + "\n\n*...сообщение обрезано*"
        
        return text
    
    def create_settings_keyboard(self, user_id: int) -> dict:
        """Создает клавиатуру настроек"""
        settings = self.get_user_settings(user_id)
        current_prompt = settings['system_prompt']
        
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": f"🤖 Ассистент {'✅' if current_prompt == 'assistant' else ''}", "callback_data": "prompt_assistant"},
                    {"text": f"🎨 Креативный {'✅' if current_prompt == 'creative' else ''}", "callback_data": "prompt_creative"}
                ],
                [
                    {"text": f"⚙️ Технический {'✅' if current_prompt == 'technical' else ''}", "callback_data": "prompt_technical"},
                    {"text": f"📚 Учитель {'✅' if current_prompt == 'teacher' else ''}", "callback_data": "prompt_teacher"}
                ],
                [
                    {"text": f"😊 Дружелюбный {'✅' if current_prompt == 'casual' else ''}", "callback_data": "prompt_casual"}
                ],
                [
                    {"text": "📝 Свой промпт", "callback_data": "custom_prompt"},
                    {"text": "❌ Закрыть", "callback_data": "close_settings"}
                ]
            ]
        }
        return keyboard
    
    def handle_message(self, message: dict):
        """Обрабатывает входящее сообщение"""
        chat_id = message['chat']['id']
        user_id = message['from']['id']
        text = message.get('text', '')
        
        # Команды
        if text.startswith('/start'):
            welcome_text = """🤖 **Добро пожаловать в Gemini Bot!**

Я использую модель **Gemini 2.5 Pro** от Google для ответов на ваши вопросы.

**Доступные команды:**
• `/settings` - настройки бота
• `/help` - справка
• Просто напишите любой вопрос!

✨ *Начните общение прямо сейчас!*"""
            self.send_message(chat_id, welcome_text)
            return
            
        elif text.startswith('/settings'):
            settings_text = "⚙️ **Настройки бота**\n\nВыберите стиль общения:"
            keyboard = self.create_settings_keyboard(user_id)
            self.send_message(chat_id, settings_text, keyboard)
            return
            
        elif text.startswith('/help'):
            help_text = """📖 **Справка по боту**

**Возможности:**
• Ответы на любые вопросы
• Разные стили общения
• Красивое форматирование
• Настраиваемые промпты

**Стили общения:**
🤖 **Ассистент** - информативные ответы
🎨 **Креативный** - яркие, образные ответы  
⚙️ **Технический** - точная техническая информация
📚 **Учитель** - обучающий стиль
😊 **Дружелюбный** - неформальное общение

Используйте `/settings` для настройки!"""
            self.send_message(chat_id, help_text)
            return
        
        # Обычный запрос к AI
        if text:
            # Показываем что бот думает
            self.send_message(chat_id, "🤔 *Думаю...*")
            
            settings = self.get_user_settings(user_id)
            
            # Определяем системный промпт
            if settings['custom_prompt']:
                system_instruction = settings['custom_prompt']
            else:
                system_instruction = self.system_prompts[settings['system_prompt']]
            
            # Получаем ответ от Gemini
            response = self.gemini.generate_text(text, system_instruction)
            formatted_response = self.format_gemini_response(response)
            
            self.send_message(chat_id, formatted_response)
    
    def handle_callback_query(self, callback_query: dict):
        """Обрабатывает callback query"""
        query_id = callback_query['id']
        user_id = callback_query['from']['id']
        chat_id = callback_query['message']['chat']['id']
        data = callback_query['data']
        
        if data.startswith('prompt_'):
            prompt_type = data.replace('prompt_', '')
            settings = self.get_user_settings(user_id)
            settings['system_prompt'] = prompt_type
            settings['custom_prompt'] = ''  # Сбрасываем кастомный промпт
            
            # Обновляем сообщение с настройками
            settings_text = f"⚙️ **Настройки бота**\n\nВыбран стиль: **{prompt_type.title()}** ✅"
            keyboard = self.create_settings_keyboard(user_id)
            
            # Редактируем сообщение
            params = {
                'chat_id': chat_id,
                'message_id': callback_query['message']['message_id'],
                'text': settings_text,
                'parse_mode': 'Markdown',
                'reply_markup': json.dumps(keyboard)
            }
            self._make_request('editMessageText', params)
            
            self.answer_callback_query(query_id, f"Выбран стиль: {prompt_type.title()}")
            
        elif data == 'custom_prompt':
            self.send_message(chat_id, "📝 **Настройка своего промпта**\n\nОтправьте свой системный промпт следующим сообщением.\n\n*Пример:* Ты эксперт по кулинарии. Давай рецепты с пошаговыми инструкциями...")
            self.answer_callback_query(query_id, "Отправьте свой промпт")
            
        elif data == 'close_settings':
            # Удаляем сообщение с настройками
            params = {
                'chat_id': chat_id,
                'message_id': callback_query['message']['message_id']
            }
            self._make_request('deleteMessage', params)
            self.answer_callback_query(query_id, "Настройки закрыты")
    
    def run(self):
        """Запускает бота"""
        print("🚀 Бот запущен!")
        print("Для остановки нажмите Ctrl+C")
        
        while True:
            try:
                updates = self.get_updates()
                
                for update in updates:
                    if 'message' in update:
                        self.handle_message(update['message'])
                    elif 'callback_query' in update:
                        self.handle_callback_query(update['callback_query'])
                
                time.sleep(1)  # Небольшая пауза между запросами
                
            except KeyboardInterrupt:
                print("\n👋 Бот остановлен!")
                break
            except Exception as e:
                print(f"❌ Ошибка в основном цикле: {e}")
                time.sleep(5)  # Пауза при ошибке

def main():
    """Главная функция"""
    
    # Конфигурация
    BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Замените на токен вашего бота
    GEMINI_API_KEY = "AIzaSyCs4lN-RNNs96EUSdWux3yBwz_7IoElnBo"  # ⚠️ ЗАМЕНИТЕ НА НОВЫЙ КЛЮЧ!
    
    print("🔧 Инициализация бота...")
    
    # Создаем экземпляры классов
    gemini_api = GeminiAPI(GEMINI_API_KEY)
    bot = TelegramBot(BOT_TOKEN, gemini_api)
    
    # Запускаем бота
    bot.run()

if __name__ == "__main__":
    main()
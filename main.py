#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram FleaMarket Sentinel - Автоматический фильтр и поисковик товаров в барахолках
Сгенерировано в консоли: 18.06.2026

Особенности:
1. Мониторит входящие посты в группах барахолок
2. Поддерживает интерактивное управление из целевого канала!
   Используйте команды:
   - /list — Вывод искомых предметов
   - /add <название> — Добавить предмет на лету без перезагрузки
   - /remove <название> — Удалить предмет без перезагрузки
3. Сохраняет список поиска в файл searched_items.json, чтобы настройки сохранялись при перезагрузке
4. Опционально подключает Gemini ИИ для концептуального сопоставления синонимов
"""

import os
import re
import json
import asyncio
from telethon import TelegramClient, events

# ================= НАСТРОЙКИ С ПАНЕЛИ УПРАВЛЕНИЯ =================

# Реквизиты Telegram API (из my.telegram.org)
api_id_env = os.getenv("TELEGRAM_API_ID", os.getenv("API_KEY", os.getenv("API_ID", "")))
if api_id_env and api_id_env.strip().isdigit():
    API_ID = int(api_id_env.strip())
else:
    API_ID = 1234567 # Вставьте ваш API_ID здесь

API_HASH = os.getenv("TELEGRAM_API_HASH", os.getenv("API_HASH", "ваш_api_hash_из_telegram"))
SESSION_NAME = os.getenv("TELEGRAM_SESSION_NAME", "fleamarket_sentinel_session")
SESSION_STRING = os.getenv("TELEGRAM_STRING_SESSION", os.getenv("STRING_SESSION", ""))

# Список целевых групп для прослушивания
TRACKED_CHATS = ['@baraxolka_in_armenia', '@erevan_baraxlanet', '@baraholka_yerevan_armenia', '@baraxolka_armenia', '@MarketYerevan0']

# Приватный чат/группа для отправки находок и удаленного управления ботом
FORWARD_TARGET_CHAT = '@myOwnGroup4651'

# Файл для сохранения списка искомых товаров
ITEMS_FILE = "searched_items.json"

# Начальный список искомых товаров, если файл searched_items.json еще не создан
DEFAULT_SEARCH_ITEMS = ['стол', 'кресло', 'стул']

SEARCH_ITEMS = []

# Интеграция с Gemini ИИ для расширенного анализа
AI_ENABLED = False

if AI_ENABLED:
    try:
        from google import genai
        from google.genai import types
        # API Ключ подставится из переменной окружения GEMINI_API_KEY
        ai = genai.Client()
    except ImportError:
        print("[Предупреждение] Библиотека 'google-genai' не установлена. Используйте: pip install google-genai")
        AI_ENABLED = False


# ================== ФУНКЦИИ ХРАНЕНИЯ СПИСКА ТОВАРОВ ==================

def load_items():
    """Загружает список искомых товаров из файла, либо создает его с дефолтными значениями"""
    global SEARCH_ITEMS
    if os.path.exists(ITEMS_FILE):
        try:
            with open(ITEMS_FILE, "r", encoding="utf-8") as f:
                SEARCH_ITEMS = json.load(f)
            print(f"📦 Загружен список товаров ({len(SEARCH_ITEMS)} шт.): {SEARCH_ITEMS}")
        except Exception as e:
            print(f"⚠️ Ошибка чтения {ITEMS_FILE}: {e}. Используем дефолтные товары.")
            SEARCH_ITEMS = list(DEFAULT_SEARCH_ITEMS)
    else:
        SEARCH_ITEMS = list(DEFAULT_SEARCH_ITEMS)
        save_items()

def save_items():
    """Сохраняет текущий список искомых товаров в JSON-файл"""
    try:
        with open(ITEMS_FILE, "w", encoding="utf-8") as f:
            json.dump(SEARCH_ITEMS, f, ensure_ascii=False, indent=4)
        print(f"💾 Персистентная копия списка сохранена в {ITEMS_FILE}")
    except Exception as e:
        print(f"⚠️ Ошибка записи списка в {ITEMS_FILE}: {e}")


# ================= ФУНКЦИИ АНАЛИЗА И ФИЛЬТРАЦИИ =================

def parse_with_gemini(text: str):
    """Вызывает Gemini 2.5 Flash для вычленения сущностей и интеллектуального мэтчинга"""
    if not AI_ENABLED or not SEARCH_ITEMS:
        return None
    try:
        prompt = f"Проанализируй текст объявления о продаже б/у вещи и определи параметры в формате JSON.\n\nСодержимое:\n{text}"
        
        response_schema = {
            "type": "OBJECT",
            "properties": {
                "itemName": {"type": "STRING", "description": "Название товара, например, 'Стол IKEA регулируемый'"},
                "price": {"type": "INTEGER", "description": "Сумма цены за штуку в виде целого числа (0 если не найдена)"},
                "currency": {"type": "STRING", "description": "Символ или буквенный код валюты (AMD, GEL, RUB, USD)"},
                "condition": {"type": "STRING", "description": "Состояние товара (например, 'новое', 'б/у в хорошем состоянии', 'б/у с дефектами')"},
                "matchedItem": {"type": "STRING", "nullable": True, "description": "Точное совпадение из переданного списка поиска, если товар концептуально подходит (например, 'столик' или 'парта' концептуально подходит под класс 'стол'). Если совпадений нет - верни null"},
                "matchReason": {"type": "STRING", "description": "Обоснование на русском языке, почему товар подходит или не подходит."}
            },
            "required": ["itemName", "price", "currency", "condition", "matchReason"]
        }

        # response = ai.models.generate_content(
        #     model='gemini-2.5-flash',
        #     contents=prompt,
        #     config=types.GenerateContentConfig(
        #         system_instruction=f"Ты профессиональный парсер объявлений о купле-продаже б/у товаров. Твоя задача — извлечь детали. Также проверь, продается ли в тексте предмет, который концептуально совпадает с одним из разделов нашего списка отслеживания: {json.dumps(SEARCH_ITEMS, ensure_ascii=False)}. Если обнаружено совпадение или близкий синоним, укажи это в 'matchedItem' (впиши туда точное написание из нашего списка!).",
        #         response_mime_type="application/json",
        #         response_schema=response_schema
        #     )
        # )
        return json.loads(response.text)
    except Exception as e:
        print(f"[ИИ Ошибка] Не удалось распарсить через Gemini: {e}. Переключаемся на локальный поиск.")
        return None

def check_local_match(text: str):
    """Буквенный поиск ключевых слов с регулярными выражениями"""
    norm_text = text.lower()
    for item in SEARCH_ITEMS:
        if not item.strip():
            continue
        # Ищем ключевое слово как подстроку
        if item.lower() in norm_text:
            return True, item, f"Прямое ручное совпадение со словом '{item}'"
    return False, None, "Совпадений не обнаружено"


# ================== СОЗДАНИЕ КЛИЕНТА TELETHON ==================

if SESSION_STRING:
    from telethon.sessions import StringSession
    try:
        client = TelegramClient(StringSession(SESSION_STRING.strip()), API_ID, API_HASH)
    except Exception as e:
        print(f"❌ Ошибка инициализации StringSession: {e}")
        client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
else:
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


# ================= ОБРАБОТЧИКИ СОБЫТИЙ ТЕЛЕГРАМ =================

@client.on(events.NewMessage(chats=FORWARD_TARGET_CHAT))
async def handle_commands_from_target_chat(event):
    """Слушает входящие сообщения в ЦЕЛЕВОЙ группе/канале на предмет управляющих команд"""
    message_text = event.raw_text.strip()
    if not message_text.startswith('/'):
        return

    parts = message_text.split(maxsplit=1)
    command = parts[0].lower()
    argument = parts[1].strip() if len(parts) > 1 else ""

    global SEARCH_ITEMS

    if command == '/list':
        if not SEARCH_ITEMS:
            await event.reply("📋 **Список искомых товаров сейчас пуст.**\nИспользуйте команду `/add название`, чтобы добавить товары в поиск.")
        else:
            items_str = "\n".join(f"{i+1}. — `{item}`" for i, item in enumerate(SEARCH_ITEMS))
            await event.reply(f"📋 **Список отслеживаемых товаров на барахолках:**\n\n{items_str}")

    elif command == '/add':
        if not argument:
            await event.reply("⚠️ **Ошибка!** Укажите название товара для добавления.\nПример: `/add стол`")
            return
        
        clean_arg = argument.lower().strip()
        if clean_arg in [i.lower() for i in SEARCH_ITEMS]:
            await event.reply(f"💡 Товар `{clean_arg}` уже отслеживается юзерботом.")
        else:
            SEARCH_ITEMS.append(clean_arg)
            save_items()
            await event.reply(f"✅ Товар **'{clean_arg}'** успешно добавлен в список поиска юзербота!")

    elif command == '/remove':
        if not argument:
            await event.reply("⚠️ **Ошибка!** Укажите название товара для удаления.\nПример: `/remove стол`")
            return
        
        clean_arg = argument.lower().strip()
        found = False
        for item in list(SEARCH_ITEMS):
            if item.lower() == clean_arg:
                SEARCH_ITEMS.remove(item)
                found = True
                break

        if found:
            save_items()
            await event.reply(f"❌ Товар **'{clean_arg}'** успешно удален из списка поиска юзербота.")
        else:
            await event.reply(f"⚠️ Товар `{clean_arg}` не найден в вашем списке поиска.")


@client.on(events.NewMessage(chats=TRACKED_CHATS))
async def handle_incoming_listings_handler(event):
    """Слушает новые объявления в отслеживаемых барахолках и фильтрует их"""
    message_text = event.raw_text
    
    if not message_text or not message_text.strip() or len(message_text.strip()) < 10:
        return

    sender_chat = await event.get_chat()
    sender_title = getattr(sender_chat, 'title', 'Канал Барахолка')
    sender_username = f"@{sender_chat.username}" if getattr(sender_chat, 'username', None) else "private"

    print(f"\n🔋 Обнаружено объявление в {sender_title} ({sender_username})...")

    matched = False
    matched_search_key = None
    reason = ""
    parsed_price = 0
    parsed_currency = "AMD"
    parsed_item_name = "Неизвестный товар"
    parsed_condition = "не указано"

    if AI_ENABLED:
        # Пробуем разобрать умным ИИ через Gemini
        ai_data = parse_with_gemini(message_text)
        if ai_data:
            matched_search_key = ai_data.get("matchedItem")
            reason = ai_data.get("matchReason", "Успешный мэтчинг ИИ")
            parsed_item_name = ai_data.get("itemName", "Неизвестно")
            parsed_condition = ai_data.get("condition", "не указано")
            parsed_price = ai_data.get("price", 0)
            parsed_currency = ai_data.get("currency", "AMD")
            matched = matched_search_key is not None
        else:
            # Откат в случае пробоев связи на обычные правила
            matched, matched_search_key, reason = check_local_match(message_text)
    else:
        # Без ИИ - простая проверка по вхождению слов
        matched, matched_search_key, reason = check_local_match(message_text)

    if matched and matched_search_key:
        print(f"🎯 СОВПАДЕНИЕ НАЙДЕНО! Категория: {matched_search_key}")
        
        # Строим ссылку на оригинальный пост в Телеграм
        message_id = event.message.id
        if getattr(sender_chat, 'username', None):
            msg_link = f"https://t.me/{sender_chat.username}/{message_id}"
        else:
            clean_id = str(event.chat_id).replace("-100", "").replace("-", "")
            msg_link = f"https://t.me/c/{clean_id}/{message_id}"

        # Декорируем форвард-сообщение
        alert_text = (
            f"🎯 **ТОВАР НАЙДЕН НА БАРАХОЛКЕ!**\n"
            f"📦 Категория подбора: **#{matched_search_key}**\n"
            f"🏷️ Что продают: *{parsed_item_name}*\n"
            f"💵 Оценка цены: **{parsed_price:,.0f} {parsed_currency}**\n"
            f"✨ Состояние: *{parsed_condition}*\n"
            f"📢 Источник: {sender_title} ({sender_username})\n"
            f"🔗 Оригинальный пост: {msg_link}\n"
            f"💡 Вердикт поиска: *{reason}*\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
            f"{message_text}"
        )

        try:
            await client.send_message(FORWARD_TARGET_CHAT, alert_text)
            print("🚀 Объявление успешно отправлено в ваш приватный канал!")
        except Exception as e:
            print(f"❌ Ошибка отправки уведомления в Телеграм: {e}")
    else:
        print(f"⏭ Мимо. Товар не входит в список поиска.")


# ================= ЗАПУСК СЕРВИСА =================

async def main():
    print("🤖 Запуск Telegram FleaMarket Sentinel Юзербота...")
    load_items()
    
    print("🔌 Подключение к серверам Telegram...")
    try:
        await client.connect()
    except Exception as e:
        print(f"❌ Критическая ошибка подключения: {e}")
        return

    if not await client.is_user_authorized():
        print("\n❌ КЛИЕНТ НЕ АВТОРИЗОВАН!")
        print("Пожалуйста, запустите этот скрипт локально в терминале для первоначального входа (ввода кода).")
        return

    print("✅ Юзербот успешно авторизован!")
    print(f"📡 Прослушиваемые барахолки ({len(TRACKED_CHATS)} шт.): {', '.join(TRACKED_CHATS)}")
    print(f"🛡️ Отправка находок и команды управления в чате: {FORWARD_TARGET_CHAT}")
    print("🤖 Бот заступил на дежурство. Ожидание объявлений...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    if not API_ID or API_HASH == "ваш_api_hash_из_telegram":
        print("❌ Ошибка! Укажите API_ID и API_HASH в коде или переменных окружения.")
    else:
        asyncio.run(main())

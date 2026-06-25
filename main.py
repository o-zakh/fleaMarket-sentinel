#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram FleaMarket Sentinel - Автоматический фильтр и поисковик товаров в барахолках
Сгенерировано в консоли: 25.06.2026

Особенности:
1. Мониторит входящие посты в группах барахолок
2. Поддерживает интерактивное управление из целевого канала!
   Используйте команды:
   - /help — Показать справку по командам
   - /listItem — Вывод списка искомых товаров
   - /addItem <название> — Добавить товар
   - /removeItem <название> — Удалить товар
   - /listPublic — Вывод прослушиваемых групп
   - /addPublic <@название> — Добавить группу в прослушивание
   - /removePublic <@название> — Удалить группу
   - /listStop — Вывод списка стоп-слов
   - /addStop <слово> — Добавить стоп-слово
   - /removeStop <слово> — Удалить стоп-слово
3. Сохраняет настройки в файлы, чтобы ничего не сбрасывалось при перезагрузке
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

# Файлы для сохранения настроек
ITEMS_FILE = "searched_items.json"
CHATS_FILE = "tracked_chats.json"
IGNORED_FILE = "ignored_words.json"

# Приватный чат/группа для отправки находок и удаленного управления ботом
FORWARD_TARGET_CHAT = '@myOwnGroup4651'

# Начальный список целевых групп
DEFAULT_TRACKED_CHATS = ['@baraxolka_in_armenia', '@erevan_baraxlanet', '@baraholka_yerevan_armenia', '@baraxolka_armenia', '@MarketYerevan0', '@myOwnGroup4651']
TRACKED_CHATS = []

# Начальный список искомых товаров
DEFAULT_SEARCH_ITEMS = ['стол', 'кресло', 'стул', 'a1000gl', 'kepler', '120см', 'velmoraofficiall', 'amvr', '120x', '120х']
SEARCH_ITEMS = []

# Начальный список стоп-слов
DEFAULT_IGNORED_WORDS = ['реклама', 'работа', 'вакансия']
IGNORED_WORDS = []

# Интеграция с Gemini ИИ для расширенного анализа
AI_ENABLED = True

if AI_ENABLED:
    try:
        from google import genai
        from google.genai import types
        # API Ключ подставится из переменной окружения GEMINI_API_KEY
        ai = genai.Client()
    except ImportError:
        print("[Предупреждение] Библиотека 'google-genai' не установлена. Используйте: pip install google-genai")
        AI_ENABLED = False


# ================== ФУНКЦИИ ХРАНЕНИЯ НАСТРОЕК ==================

def load_items():
    global SEARCH_ITEMS
    if os.path.exists(ITEMS_FILE):
        try:
            with open(ITEMS_FILE, "r", encoding="utf-8") as f:
                SEARCH_ITEMS = json.load(f)
            print(f"📦 Загружен список товаров ({len(SEARCH_ITEMS)} шт.): {SEARCH_ITEMS}")
        except Exception as e:
            print(f"⚠️ Ошибка чтения {ITEMS_FILE}: {e}")
            SEARCH_ITEMS = list(DEFAULT_SEARCH_ITEMS)
    else:
        SEARCH_ITEMS = list(DEFAULT_SEARCH_ITEMS)
        save_items()

def save_items():
    try:
        with open(ITEMS_FILE, "w", encoding="utf-8") as f:
            json.dump(SEARCH_ITEMS, f, ensure_ascii=False, indent=4)
        print(f"💾 Список товаров сохранен в {ITEMS_FILE}")
    except Exception as e:
        print(f"⚠️ Ошибка записи в {ITEMS_FILE}: {e}")

def load_chats():
    global TRACKED_CHATS
    if os.path.exists(CHATS_FILE):
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f:
                TRACKED_CHATS = json.load(f)
            print(f"📡 Загружен список групп ({len(TRACKED_CHATS)} шт.): {TRACKED_CHATS}")
        except Exception as e:
            print(f"⚠️ Ошибка чтения {CHATS_FILE}: {e}")
            TRACKED_CHATS = list(DEFAULT_TRACKED_CHATS)
    else:
        TRACKED_CHATS = list(DEFAULT_TRACKED_CHATS)
        save_chats()

def save_chats():
    try:
        with open(CHATS_FILE, "w", encoding="utf-8") as f:
            json.dump(TRACKED_CHATS, f, ensure_ascii=False, indent=4)
        print(f"💾 Список групп сохранен в {CHATS_FILE}")
    except Exception as e:
        print(f"⚠️ Ошибка записи в {CHATS_FILE}: {e}")

def load_ignored():
    global IGNORED_WORDS
    if os.path.exists(IGNORED_FILE):
        try:
            with open(IGNORED_FILE, "r", encoding="utf-8") as f:
                IGNORED_WORDS = json.load(f)
            print(f"🛑 Загружены стоп-слова ({len(IGNORED_WORDS)} шт.): {IGNORED_WORDS}")
        except Exception as e:
            print(f"⚠️ Ошибка чтения {IGNORED_FILE}: {e}")
            IGNORED_WORDS = list(DEFAULT_IGNORED_WORDS)
    else:
        IGNORED_WORDS = list(DEFAULT_IGNORED_WORDS)
        save_ignored()

def save_ignored():
    try:
        with open(IGNORED_FILE, "w", encoding="utf-8") as f:
            json.dump(IGNORED_WORDS, f, ensure_ascii=False, indent=4)
        print(f"💾 Стоп-слова сохранены в {IGNORED_FILE}")
    except Exception as e:
        print(f"⚠️ Ошибка записи в {IGNORED_FILE}: {e}")


# ================= ФУНКЦИИ АНАЛИЗА И ФИЛЬТРАЦИИ =================

def parse_with_gemini(text: str):
    """Вызывает Gemini 3.1 Flash Lite для вычленения характеристик товара"""
    if not AI_ENABLED or not SEARCH_ITEMS:
        return {"error": "ИИ выключен или список поиска пуст"}
    try:
        prompt = f"""Проанализируй текст объявления о продаже б/у вещи и определи параметры в формате JSON.

Содержимое:
{text}"""
        
        response_schema = {
            "type": "OBJECT",
            "properties": {
                "itemName": {"type": "STRING", "description": "Краткое название товара (например, 'Офисный стол')"},
                "price": {"type": "INTEGER", "description": "Сумма в виде чистого целого числа (например, если '27 000 др', то 27000. Если '8000рублей', то 8000)"},
                "currency": {"type": "STRING", "description": "Буквенный код валюты: AMD, RUB, USD, EUR или GEL."},
                "condition": {"type": "STRING", "description": "Состояние товара (например, 'новое', 'б/у', 'не указано')"}
            },
            "required": ["itemName", "price", "currency", "condition"]
        }

        response = ai.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="Ты парсер объявлений. Твоя задача — извлечь точные данные о товаре: название, чистая цена (integer), код валюты (AMD, RUB, USD) и состояние. Строго соблюдай типы.",
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.1
            )
        )
        
        # Очищаем ответ от маркдауна (некоторые модели ошибочно оборачивают JSON)
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            lines = raw_text.split('\n')
            if lines[0].startswith("```"): lines = lines[1:]
            if lines[-1].startswith("```"): lines = lines[:-1]
            raw_text = "\n".join(lines).strip()
            
        data = json.loads(raw_text)
        data["error"] = None
        return data
    except Exception as e:
        err_msg = str(e)
        print(f"[ИИ Ошибка] Не удалось распарсить через Gemini: {err_msg}")
        return {"error": err_msg}

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

    if command == '/help':
        help_text = (
            "📖 **Доступные команды:**\n\n"
            "**/help** — Показывает этот список всех команд.\n"
            "Пример: `/help`\n\n"
            "**/listItem** — Показывает список всех искомых товаров.\n"
            "Пример: `/listItem`\n\n"
            "**/addItem** — Добавляет новый товар в список поиска бота.\n"
            "Пример: `/addItem стол`\n\n"
            "**/removeItem** — Удаляет товар из списка поиска.\n"
            "Пример: `/removeItem стол`\n\n"
            "**/listPublic** — Показывает список всех прослушиваемых групп.\n"
            "Пример: `/listPublic`\n\n"
            "**/addPublic** — Добавляет группу в список ожидания для объявлений.\n"
            "Пример: `/addPublic @baraholka`\n\n"
            "**/removePublic** — Убирает группу из списка ожидания.\n"
            "Пример: `/removePublic @baraholka`\n\n"
            "**/listStop** — Показывает список стоп-слов.\n"
            "Пример: `/listStop`\n\n"
            "**/addStop** — Добавляет слово в список стоп-слов.\n"
            "Пример: `/addStop продано`\n\n"
            "**/removeStop** — Убирает слово из списка стоп-слов.\n"
            "Пример: `/removeStop продано`"
        )
        await event.reply(help_text)

    elif command == '/listitem':
        if not SEARCH_ITEMS:
            await event.reply("📋 **Список искомых товаров сейчас пуст.**\nИспользуйте команду `/addItem название`, чтобы добавить товары в поиск.")
        else:
            items_str = "\n".join(f"{i+1}. — `{item}`" for i, item in enumerate(SEARCH_ITEMS))
            await event.reply(f"📋 **Список отслеживаемых товаров на барахолках:**\n\n{items_str}")

    elif command == '/additem':
        if not argument:
            await event.reply("⚠️ **Ошибка!** Укажите название товара для добавления.\nПример: `/addItem стол`")
            return
        
        clean_arg = argument.lower().strip()
        if clean_arg in [i.lower() for i in SEARCH_ITEMS]:
            await event.reply(f"💡 Товар `{clean_arg}` уже отслеживается юзерботом.")
        else:
            SEARCH_ITEMS.append(clean_arg)
            save_items()
            await event.reply(f"✅ Товар **'{clean_arg}'** успешно добавлен в список поиска юзербота!")

    elif command == '/removeitem':
        if not argument:
            await event.reply("⚠️ **Ошибка!** Укажите название товара для удаления.\nПример: `/removeItem стол`")
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

    elif command == '/listpublic':
        if not TRACKED_CHATS:
            await event.reply("📡 **Список прослушиваемых групп пуст.**")
        else:
            chats_str = "\n".join(f"{i+1}. — `{c}`" for i, c in enumerate(TRACKED_CHATS))
            await event.reply(f"📡 **Список прослушиваемых барахолок:**\n\n{chats_str}")

    elif command == '/addpublic':
        if not argument:
            await event.reply("⚠️ **Ошибка!** Укажите юзернейм группы.\nПример: `/addPublic @yerevan_baraholka`")
            return
        
        clean_arg = argument.strip()
        if not clean_arg.startswith('@') and not clean_arg.startswith('https://'):
            clean_arg = '@' + clean_arg
            
        if clean_arg.lower() in [c.lower() for c in TRACKED_CHATS]:
            await event.reply(f"💡 Группа `{clean_arg}` уже прослушивается.")
        else:
            TRACKED_CHATS.append(clean_arg)
            save_chats()
            await event.reply(f"✅ Группа {clean_arg} добавлена в список поиска.")

    elif command == '/removepublic':
        if not argument:
            await event.reply("⚠️ **Ошибка!** Укажите юзернейм группы.\nПример: `/removePublic @yerevan_baraholka`")
            return
            
        clean_arg = argument.strip()
        if not clean_arg.startswith('@') and not clean_arg.startswith('https://'):
            clean_arg = '@' + clean_arg
            
        found = False
        for c in list(TRACKED_CHATS):
            if c.lower() == clean_arg.lower():
                TRACKED_CHATS.remove(c)
                found = True
                break

        if found:
            save_chats()
            await event.reply(f"❌ Группа {clean_arg} убрана из списка поиска.")
        else:
            await event.reply(f"⚠️ Группа `{clean_arg}` не найдена в списке.")

    elif command == '/liststop':
        if not IGNORED_WORDS:
            await event.reply("🛑 **Список стоп-слов пуст.**")
        else:
            words_str = "\n".join(f"{i+1}. — `{w}`" for i, w in enumerate(IGNORED_WORDS))
            await event.reply(f"🛑 **Список стоп-слов:**\n\n{words_str}")

    elif command == '/addstop':
        if not argument:
            await event.reply("⚠️ **Ошибка!** Укажите слово.\nПример: `/addStop продано`")
            return
        
        clean_arg = argument.lower().strip()
        if clean_arg in [w.lower() for w in IGNORED_WORDS]:
            await event.reply(f"💡 Стоп-слово `{clean_arg}` уже есть в списке.")
        else:
            IGNORED_WORDS.append(clean_arg)
            save_ignored()
            await event.reply(f"✅ Стоп-слово **'{clean_arg}'** добавлено.")

    elif command == '/removestop':
        if not argument:
            await event.reply("⚠️ **Ошибка!** Укажите слово.\nПример: `/removeStop продано`")
            return
        
        clean_arg = argument.lower().strip()
        found = False
        for w in list(IGNORED_WORDS):
            if w.lower() == clean_arg:
                IGNORED_WORDS.remove(w)
                found = True
                break

        if found:
            save_ignored()
            await event.reply(f"❌ Стоп-слово **'{clean_arg}'** удалено.")
        else:
            await event.reply(f"⚠️ Стоп-слово `{clean_arg}` не найдено.")


@client.on(events.NewMessage())
async def handle_incoming_listings_handler(event):
    """Слушает новые объявления и фильтрует их"""
    # Пропускаем сообщения из самого чата назначения (чтобы не зациклить)
    sender_chat = await event.get_chat()
    
    # Формируем имя или ID чата для проверки
    chat_username = f"@{sender_chat.username}" if getattr(sender_chat, 'username', None) else ""
    chat_id = str(event.chat_id)
    
    # Проверка, находится ли этот чат в TRACKED_CHATS
    is_tracked = False
    for c in TRACKED_CHATS:
        c_clean = c.lower()
        if chat_username and chat_username.lower() == c_clean:
            is_tracked = True
            break
        elif chat_id == c_clean:
            is_tracked = True
            break
            
    if not is_tracked:
        return

    message_text = event.raw_text
    
    if not message_text or not message_text.strip() or len(message_text.strip()) < 10:
        return

    sender_title = getattr(sender_chat, 'title', 'Канал Барахолка')
    sender_username = chat_username if chat_username else "private"

    print(f"\n🔋 Обнаружено объявление в {sender_title} ({sender_username})...")

    # Проверка на стоп-слова
    norm_text = message_text.lower()
    for w in IGNORED_WORDS:
        if w.strip() and w.lower() in norm_text:
            print(f"🚫 Пропущено: найдено стоп-слово: '{w}'")
            return

    # Локальная проверка
    matched, matched_search_key, reason = check_local_match(message_text)
    
    if not matched:
        print(f"⏭ Мимо. Товар не входит в список поиска.")
        return

    print(f"🎯 СОВПАДЕНИЕ НАЙДЕНО! Категория: {matched_search_key}")

    parsed_price = 0
    parsed_currency = "AMD"
    parsed_item_name = matched_search_key.capitalize()
    parsed_condition = "не указано"
    ai_status_text = ""

    if AI_ENABLED:
        print("🧠 Использование Gemini для аккуратного вычленения данных...")
        ai_data = parse_with_gemini(message_text)
        if ai_data and not ai_data.get("error"):
            parsed_item_name = ai_data.get("itemName", parsed_item_name)
            parsed_condition = ai_data.get("condition", "не указано")
            
            # Извлекаем цену корректно, даже если это 0
            price_val = ai_data.get("price")
            if price_val is not None:
                try:
                    parsed_price = int(price_val)
                except:
                    parsed_price = 0
            else:
                parsed_price = 0

            parsed_currency = ai_data.get("currency", "AMD")
            ai_status_text = "Анализ от ИИ: ✅"
        else:
            err_msg = ai_data.get("error", "Неизвестная ошибка") if ai_data else "Пустой ответ"
            ai_status_text = f"Анализ от ИИ: ❌ - '{err_msg}'"
    else:
        ai_status_text = "Анализ от ИИ: ❌ - 'Выключен'"

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
        f"📦 Категория подбора: **#{matched_search_key.replace(' ', '_')}**\n"
        f"🏷️ Что продают: *{parsed_item_name}*\n"
        f"💵 Оценка цены: **{parsed_price:,.0f} {parsed_currency}**\n"
        f"✨ Состояние: *{parsed_condition}*\n"
        f"📢 Источник: {sender_title} ({sender_username})\n"
        f"🔗 Оригинальный пост: {msg_link}\n"
        f"💡 Вердикт поиска: *{reason}*\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        f"{message_text}\n\n"
        f"{ai_status_text}"
    )

    try:
        await client.send_message(FORWARD_TARGET_CHAT, alert_text)
        print("🚀 Объявление успешно отправлено в ваш приватный канал!")
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления в Телеграм: {e}")


# ================= ЗАПУСК СЕРВИСА =================

async def main():
    print("🤖 Запуск Telegram FleaMarket Sentinel Юзербота...")
    load_items()
    load_chats()
    load_ignored()
    
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

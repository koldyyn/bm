import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import datetime
import os
import json
import re

# --- НАСТРОЙКИ ---
BOT_TOKEN = '8917345115:AAGODS3esMz2ZPi2vYll0IUcDPodLyDaZ4w'
OWNER_ID = 8131252768,8866218152

# Теперь список групп через запятую все ID нужных групп
TARGET_GROUP_IDS = [
    -1003750606290, 
    -1004381801720, 
    # Сюда можно добавить еще группы...
]

bot = telebot.TeleBot(BOT_TOKEN)

SUPPORTED_CONTENT_TYPES = [
    'text', 'photo', 'video', 'sticker', 
    'animation', 'document', 'voice', 'video_note'
]

waiting_users = set()

# Функция для создания кнопки
def get_contact_button():
    keyboard = InlineKeyboardMarkup()
    # url="https://t.me/kandi_9" - эта ссылка автоматически откроет ЛС
    button = InlineKeyboardButton(text="✅Провести сделку", url="https://t.me/D1LLER_BMll")
    keyboard.add(button)
    return keyboard

# Функция для записи логов в файл
def write_log(user, content_type):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    username = f"@{user.username}" if user.username else "Без юзернейма"
    full_name = user.first_name
    if user.last_name:
        full_name += f" {user.last_name}"
        
    log_text = f"[{now}] {full_name} ({username} | ID: {user.id}) отправил: {content_type}\n"
    
    with open("bot_logs.txt", "a", encoding="utf-8") as f:
        f.write(log_text)

        # --- СИСТЕМА БАНОВ ---
def load_bans():
    try:
        with open("banned_users.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_bans(bans):
    with open("banned_users.json", "w") as f:
        json.dump(bans, f)

def is_banned(user_id):
    bans = load_bans()
    uid_str = str(user_id)
    if uid_str in bans:
        expiry = bans[uid_str]
        if expiry == "forever":
            return True
        
        # Проверяем не истек ли временный бан
        expiry_date = datetime.datetime.fromisoformat(expiry)
        if datetime.datetime.now() < expiry_date:
            return True
        else:
            # Время вышло - снимаем бан
            del bans[uid_str]
            save_bans(bans)
            return False
    return False

# Обработчик секретной команды логи
@bot.message_handler(func=lambda message: message.text and message.text.lower() == 'логи')
def show_logs(message):
    if message.chat.id != OWNER_ID:
        return

    try:
        with open("bot_logs.txt", "r", encoding="utf-8") as f:
            logs = f.readlines()
        
        if not logs:
            bot.send_message(message.chat.id, "Логи пусты. Еще никто ничего не отправлял.")
            return

        recent_logs = "".join(logs[-20:])
        bot.send_message(
            message.chat.id, 
            f"<b>Последние 20 отправок:</b>\n\n{recent_logs}", 
            parse_mode='HTML'
        )
    except FileNotFoundError:
        bot.send_message(message.chat.id, "Файл с логами еще не создан.")

        # Команда "бан @username навсегда" или "бан @username 30 дней"
@bot.message_handler(func=lambda message: message.text and message.text.lower().startswith('бан '))
def ban_user(message):
    if message.chat.id != OWNER_ID:
        return

    parts = message.text.split()
    if len(parts) < 3:
        bot.send_message(message.chat.id, "⚠️ Формат: бан @username навсегда ИЛИ бан @username 30 дней")
        return
    
    target = parts[1] # Юзернейм или ID
    duration = parts[2].lower() # 'навсегда' или цифра '30'
    
    # 1. Пытаемся найти ID пользователя
    target_id = None
    if target.startswith('@'):
        try:
            with open("bot_logs.txt", "r", encoding="utf-8") as f:
                content = f.read()
                # Ищем строчку вида: (@username | ID: 123456)
                match = re.search(rf"\({re.escape(target)}\s*\|\s*ID:\s*(\d+)\)", content, re.IGNORECASE)
                if match:
                    target_id = match.group(1)
                else:
                    bot.send_message(message.chat.id, f"❌ Юзернейм {target} не найден в логах. Он еще ничего не отправлял боту.")
                    return
        except FileNotFoundError:
            bot.send_message(message.chat.id, "❌ Файл логов пуст, негде искать.")
            return
    elif target.isdigit():
        target_id = target # Если вы сразу ввели цифровой ID вместо юзернейма
    else:
        bot.send_message(message.chat.id, "❌ Укажите @username или ID (только цифры).")
        return

    # 2. Вычисляем срок
    if duration == 'навсегда':
        expiry_str = "forever"
        text_reply = f"🔨 Пользователь {target} (ID: {target_id}) забанен навсегда."
    elif duration.isdigit():
        days = int(duration)
        expiry_date = datetime.datetime.now() + datetime.timedelta(days=days)
        expiry_str = expiry_date.isoformat()
        text_reply = f"🔨 Пользователь {target} (ID: {target_id}) забанен на {days} дней."
    else:
         bot.send_message(message.chat.id, "❌ Укажите 'навсегда' или количество дней (например: 30).")
         return

    # 3. Сохраняем бан
    bans = load_bans()
    bans[str(target_id)] = expiry_str
    save_bans(bans)
    
    # Если забаненный висел в ожидании отправки - удаляем
    if int(target_id) in waiting_users:
        waiting_users.remove(int(target_id))

    bot.send_message(message.chat.id, text_reply)

# Команда разбана
@bot.message_handler(func=lambda message: message.text and message.text.lower().startswith('разбан '))
def unban_user(message):
    if message.chat.id != OWNER_ID:
        return

    # Работает только по ID (берем его из логов или из сообщения о бане)
    target_id = message.text.split()[1] 
    bans = load_bans()
    
    if target_id in bans:
        del bans[target_id]
        save_bans(bans)
        bot.send_message(message.chat.id, f"✅ Пользователь с ID {target_id} разбанен.")
    else:
        bot.send_message(message.chat.id, "Этот ID не найден в списке забаненных.")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    # ПРОВЕРКА НА БАН
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, "❌Вы забанены.")
        return

    waiting_users.add(message.chat.id)
    bot.send_message(
        message.chat.id,
        "Приветствую тебя на <b>BLACK MARKET II</b>, напиши сообщение для отправки.\n\nВот ссылки на две группы в которые будет отправлено сообщение: @blackMll2 @bmll2",
        parse_mode='HTML'
    )

@bot.message_handler(commands=['done'])
def stop_receiving(message):
    if message.chat.id in waiting_users:
        waiting_users.remove(message.chat.id)
        bot.send_message(message.chat.id, "Прием сообщений завершен! Чтобы отправить что-то новое, нажми на /start.")
    else:
        bot.send_message(message.chat.id, "Чтобы начать отправку, сначала нажми /start.")

@bot.message_handler(content_types=SUPPORTED_CONTENT_TYPES)
def handle_incoming_content(message):
    if is_banned(message.from_user.id):
        return
    if message.chat.id not in waiting_users:
        return

    success_count = 0
    keyboard = get_contact_button()

    # Проходимся по списку всех групп и отправляем в каждую
    for group_id in TARGET_GROUP_IDS:
        try:
            bot.copy_message(
                chat_id=group_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=keyboard
            )
            success_count += 1
        except Exception as e:
            
            print(f"Ошибка при отправке в группу {group_id}: {e}")

    # Отвечаем пользователю об итогах
    if success_count > 0:
        bot.reply_to(message, "✓ Сообщение отправлено, нажми ещё раз /start чтобы отправить новое сообщение")
        write_log(message.from_user, message.content_type)
    else:
        bot.reply_to(message, "❌ Ошибка отправки.")
        bot.reply_to(message, "Не удалось отправить сообщение ни в одну группу. Проверьте ID групп и права бота.")

if __name__ == '__main__':
    print("Бот запущен. Готов к работе")
    bot.infinity_polling()
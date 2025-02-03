import os
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import CallbackContext
import logging

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Получаем токен бота из переменных окружения
TOKEN = os.getenv('BOT_TOKEN')

if not TOKEN:
    raise ValueError("Не удалось получить токен бота из переменных окружения")

# Получаем учетные данные Google Sheets из переменных окружения
SERVICE_ACCOUNT_FILE = json.loads(os.getenv('SERVICE_ACCOUNT_FILE'))

if not SERVICE_ACCOUNT_FILE:
    raise ValueError("Не удалось получить учетные данные Google Sheets из переменных окружения")

# Настройки для доступа к Google Sheets
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Авторизация в Google Sheets
creds = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_FILE, SCOPE)
client = gspread.authorize(creds)

# ID вашего Google Sheets документа (можно найти в URL документа)
SPREADSHEET_ID = '1GTO6puJv3YUtoAooR27jQsVcXTqlHWpyLz2m511MZHo'

# Имя листа в Google Sheets
WORKSHEET_NAME = 'для Вадима'

# Максимальная длина сообщения в Telegram
MAX_MESSAGE_LENGTH = 4096

# Список администраторов (user_id)
ADMINS = [934606635, 1076176066]  # Замените на реальные user_id администраторов

# Функция для проверки, является ли пользователь администратором
def is_admin(user_id):
    return user_id in ADMINS

# Функция для команды /start
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Вас приветствует бот компании ООО МДФ г. Димитровграда. Бот предназначен для поиска ценовой категории пленок ПВХ. Напишите название или артикул пленки, и Вам будут предложены варианты из нашего ассортимента.')

# Функция для разбиения длинного текста на части
def split_message(text: str, max_length: int) -> list:
    messages = []
    while len(text) > max_length:
        split_point = text.rfind(' ', 0, max_length)
        if split_point == -1:
            split_point = max_length
        messages.append(text[:split_point])
        text = text[split_point:].lstrip()
    messages.append(text)
    return messages

# Функция для обработки текстовых сообщений
async def search_word(update: Update, context: CallbackContext) -> None:
    word = update.message.text.lower().strip()  # Убираем пробелы и приводим к нижнему регистру
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)  # Получаем нужный лист
    except gspread.exceptions.WorksheetNotFound:
        await update.message.reply_text(f'Лист "{WORKSHEET_NAME}" не найден.')
        return

    data = sheet.get_all_values()

    result = []
    for row in data:
        processed_row = [cell.lower().strip() for cell in row[:3]]
        if any(word in cell for cell in processed_row):  # Ищем только в первых трех столбцах (A, B, C)
            formatted_row = f"{row[0]} | {row[2]} | категория | {row[1]}"
            result.append(formatted_row)

    if result:
        message = '\n'.join(result)
        messages = split_message(message, MAX_MESSAGE_LENGTH)
        for msg in messages:
            await update.message.reply_text(msg)
    else:
        await update.message.reply_text('Ничего не найдено.')

# Функция для добавления новой строки
def add_row(sheet, row_data):
    sheet.append_row(row_data)

# Функция для обновления ячейки
def update_cell(sheet, row, col, value):
    sheet.update_cell(row, col, value)

# Функция для удаления строки
def delete_row(sheet, row_index):
    sheet.delete_row(row_index)

# Функция для команды /addrow
async def add_row_command(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text('У вас нет прав для выполнения этой команды.')
        return

    if len(context.args) < 1:
        await update.message.reply_text('Пожалуйста, укажите данные через запятые или точки: Название, Категория, Цена.')
        return

    input_text = ' '.join(context.args)
    parts = [part.strip() for part in input_text.split(',') if part.strip()]
    if len(parts) != 3:
        await update.message.reply_text('Пожалуйста, укажите три значения через запятую: Название, Категория, Цена.')
        return

    title, category, price = parts
    new_row = [title, category, price]

    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
        add_row(sheet, new_row)
        await update.message.reply_text('Новая строка успешно добавлена.')
    except Exception as e:
        logger.error(f"Ошибка при добавлении строки: {str(e)}")
        await update.message.reply_text('Произошла ошибка при добавлении строки. Пожалуйста, попробуйте позже.')

# Функция для команды /updatecell
async def update_cell_command(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text('У вас нет прав для выполнения этой команды.')
        return

    if len(context.args) < 3:
        await update.message.reply_text('Пожалуйста, укажите номер строки, номер столбца и новое значение через пробел.')
        return

    row, col = map(int, context.args[:2])
    value = ' '.join(context.args[2:])
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
    update_cell(sheet, row, col, value)
    await update.message.reply_text('Ячейка успешно обновлена.')

# Функция для команды /deleterow
async def delete_row_command(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text('У вас нет прав для выполнения этой команды.')
        return

    if len(context.args) < 1:
        await update.message.reply_text('Пожалуйста, укажите номер строки для удаления.')
        return

    row_index = int(context.args[0])
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
    delete_row(sheet, row_index)
    await update.message.reply_text('Строка успешно удалена.')

# Главная функция
def main() -> None:
    application = ApplicationBuilder().token(TOKEN).build()

    # Настройка Webhook
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')
    PORT = int(os.getenv('PORT', '8080'))

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="/",
        webhook_url=WEBHOOK_URL
    )

    # Добавление обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addrow", add_row_command))
    application.add_handler(CommandHandler("updatecell", update_cell_command))
    application.add_handler(CommandHandler("deleterow", delete_row_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_word))

if __name__ == '__main__':
    main()

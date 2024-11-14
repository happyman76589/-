import time
import requests
import schedule
import logging
from datetime import datetime, timedelta
from pytz import timezone
from telegram import Bot
from config import TELEGRAM_TOKEN, CHAT_ID, WB_API_KEY, WAREHOUSE_ID

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Инициализация бота
bot = Bot(token=TELEGRAM_TOKEN)

# Параметры для API Wildberries
WB_API_URL = 'https://supplies-api.wildberries.ru/api/v1/acceptance/coefficients'
HEADERS = {'Authorization': WB_API_KEY}

# Статистика
check_count = 0
free_date_count = 0

# Задаем московский часовой пояс
moscow_tz = timezone('Europe/Moscow')

# Функция проверки наличия свободных дат
def check_free_dates():
    global check_count, free_date_count
    check_count += 1

    try:
        response = requests.get(WB_API_URL, headers=HEADERS)
        response.raise_for_status()
        data = response.json()

        # Фильтрация данных по складу, типу поставки и доступности (коэффициент 0)
        filtered_dates = [
            entry for entry in data
            if entry['warehouseID'] == WAREHOUSE_ID and
               entry['coefficient'] >= 0 and
               entry['boxTypeID'] in [2, 5] and
               datetime.strptime(entry['date'], '%Y-%m-%dT%H:%M:%SZ').astimezone(moscow_tz) <= \
               datetime.now(moscow_tz) + timedelta(days=14)
        ]

        if filtered_dates:
            free_date_count += 1
            message = f"Найдены свободные даты для записи на складе {filtered_dates[0]['warehouseName']} ({WAREHOUSE_ID}):\n"
            for entry in filtered_dates:
                date_moscow = datetime.strptime(entry['date'], '%Y-%m-%dT%H:%M:%SZ').astimezone(moscow_tz)
                message += f"- Дата: {date_moscow.strftime('%Y-%m-%d %H:%M:%S')} | Тип поставки: {entry['boxTypeName']}\n"
            bot.send_message(chat_id=CHAT_ID, text=message)
            logging.info("Сообщение о свободных датах отправлено в чат.")
        else:
            logging.debug("Свободных дат не найдено на складе.")

    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при запросе: {e}")

# Планировщик для ежечасного отчета
def send_hourly_report():
    global check_count, free_date_count
    current_hour = datetime.now(moscow_tz).hour
    if 8 <= current_hour < 21:  # Ежечасный отчет только с 8 до 21 часов по московскому времени
        report = (
            f"Ежечасный отчет:\n"
            f"Склад: {WAREHOUSE_ID}\n"
            f"Проверок выполнено: {check_count}\n"
            f"Найдено свободных дат: {free_date_count}\n"
            f"Время: {datetime.now(moscow_tz).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        bot.send_message(chat_id=CHAT_ID, text=report)
        logging.info("Ежечасный отчет отправлен в чат.")

# Планировщик для ночного отчета
def send_night_report():
    global check_count, free_date_count
    report = (
        f"Ночной отчет:\n"
        f"Склад: {WAREHOUSE_ID}\n"
        f"Проверок за ночь выполнено: {check_count}\n"
        f"Найдено свободных дат за ночь: {free_date_count}\n"
        f"Время: {datetime.now(moscow_tz).strftime('%Y-%m-%d %H:%M:%S')}"
    )
    bot.send_message(chat_id=CHAT_ID, text=report)
    logging.info("Ночной отчет отправлен в чат.")

    # Сброс статистики
    check_count = 0
    free_date_count = 0

# Планировщик для полного дневного отчета в 21:00
def send_daily_report():
    global check_count, free_date_count
    report = (
        f"Дневной отчет:\n"
        f"Склад: {WAREHOUSE_ID}\n"
        f"Проверок за день выполнено: {check_count}\n"
        f"Найдено свободных дат за день: {free_date_count}\n"
        f"Время: {datetime.now(moscow_tz).strftime('%Y-%m-%d %H:%M:%S')}"
    )
    bot.send_message(chat_id=CHAT_ID, text=report)
    logging.info("Дневной отчет отправлен в чат.")

    # Сброс статистики
    check_count = 0
    free_date_count = 0

# Запуск проверки каждые 2 минуты
schedule.every(1).minutes.do(check_free_dates)

# Ежечасный отчет (с 8:00 до 21:00 по московскому времени)
schedule.every().hour.at(":00").do(send_hourly_report)

# Ночной отчет в 8:00 по московскому времени
schedule.every().day.at("08:00").do(send_night_report)

# Полный дневной отчет в 21:00 по московскому времени
schedule.every().day.at("21:00").do(send_daily_report)

# Основной цикл
while True:
    schedule.run_pending()
    time.sleep(1)

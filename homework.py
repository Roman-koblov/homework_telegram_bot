import logging
from logging.handlers import RotatingFileHandler
import os
import requests
import telegram
import time
from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('my_logger.log',
                              encoding='UTF-8',
                              maxBytes=50000000,
                              backupCount=5
                              )
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение в чат отправлено')
    except Exception:
        logger.error('Ошибка отправки сообщения')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса.
    В случае успешного запроса должна вернуть ответ API,
    преобразовав его из формата JSON к типам данных Python.
    """
    timestamp = current_timestamp or time.time_ns()
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params=params
                                         )
    except Exception as error:
        logging.error(f'Ошибка при запросе к API: {error}')
        raise Exception(f'Ошибка при запросе к API: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        status_code = homework_statuses.status_code
        logging.error(f'Ошибка {status_code}')
        raise Exception(f'Ошибка {status_code}')
    try:
        return homework_statuses.json()
    except ValueError:
        logger.error('Ошибка перевода ответа из json в Python')
        raise ValueError('Ошибка перевода ответа из json в Python')


def check_response(response):
    """Проверяет ответ API на корректность."""
    try:
        list_of_hworks = response['homeworks']
    except KeyError:
        logger.error('Ошибка словаря')
        raise KeyError('Ошибка словаря')
    try:
        homework = list_of_hworks[0]
    except IndexError:
        logger.error('Список работ пуст')
        raise IndexError('Список работ пуст')
    return homework


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе
    статус этой работы.
    """
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise Exception('Отсутствует ключ "status" в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise Exception(f'Неизвестный статус работы: {homework_status}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения, необходимых для работы.
    Если отсутствует хотя бы одна переменная окружения — функция
    должна вернуть False, иначе — True.
    """
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True
    else:
        return False


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = time.time_ns()
    if not check_tokens():
        logger.critical('Отсутствуют токены')
        raise Exception('Отсутствуют токены')
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            message = parse_status(check_response(response))
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        except Exception as error:
            logger.error(error)
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            pass


if __name__ == '__main__':
    main()

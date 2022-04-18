import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_TIME = 600
ONE_DAY = 86400
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s,'
    + '%(levelname)s, %(message)s, %(name)s, %(funcName)s, %(lineno)s'
)
handler.setFormatter(formatter)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    logger.info('Попытка отправки сообщения')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception:
        raise Exception('Ошибка отправки сообщения')
    else:
        logger.info('Сообщение в чат отправлено')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    headers_and_params = {
        'header': {'Authorization': f'OAuth {PRACTICUM_TOKEN}'},
        'param': {'from_date': timestamp}
    }
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=headers_and_params['header'],
            params=headers_and_params['param']
        )
    except Exception as error:
        raise Exception(f'Ошибка при запросе к API: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        status_code = homework_statuses.status_code
        raise Exception(f'Ошибка {status_code}')
    try:
        return homework_statuses.json()
    except ValueError:
        raise ValueError('Ошибка перевода ответа из json в Python')


def check_response(response):
    """Проверяет ответ API на корректность."""
    try:
        response['homeworks'] and response['current_date']
    except KeyError:
        raise KeyError('Ошибка словаря')
    try:
        homework = (response['homeworks'])[0]
        return homework
    except IndexError:
        raise IndexError('Список работ пуст')


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе.
    статус этой работы.
    """
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise Exception('Отсутствует ключ "status" в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise Exception(f'Неизвестный статус работы: {homework_status}')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения, необходимых для работы.
    Если отсутствует хотя бы одна переменная окружения — функция
    должна вернуть False, иначе — True.
    """
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    current_timestamp = int(time.time()) - ONE_DAY
    STATUS_MESSAGE = ''
    ERROR_MESSAGE = ''
    if not check_tokens():
        logger.critical('Отсутствуют токены')
        sys.exit(1)
    while True:
        try:
            bot = telegram.Bot(token=TELEGRAM_TOKEN)
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            message = parse_status(check_response(response))
            if message != STATUS_MESSAGE:
                send_message(bot, message)
                STATUS_MESSAGE = message
        except Exception as error:
            logger.error(error)
            message = f'Сбой в работе программы: {error}'
            if message != ERROR_MESSAGE:
                send_message(bot, message)
                ERROR_MESSAGE = message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()

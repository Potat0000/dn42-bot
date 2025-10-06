import pickle
from ipaddress import ip_network

import config
import sentry_sdk
import telebot


class ExceptionHandler(telebot.ExceptionHandler):
    def handle(exception):
        if exception:
            sentry_sdk.capture_exception(exception)


MIN_AGENT_VERSION = 24

bot = telebot.TeleBot(config.BOT_TOKEN, use_class_middlewares=True, exception_handler=ExceptionHandler)

servers = {}

AS_ROUTE = {}
ChinaIPv4 = []
ChinaIPv6 = []
ChinaWhitelist = [ip_network(i) for i in config.CN_WHITELIST_IP]

try:
    with open('./user_db.pkl', 'rb') as f:
        db, db_privilege = pickle.load(f)
except BaseException:
    db = {}
    db_privilege = set()

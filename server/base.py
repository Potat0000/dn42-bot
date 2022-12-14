# -*- coding: utf-8 -*-
import pickle

import config
import telebot


class ExceptionHandler(telebot.ExceptionHandler):
    def handle(exception):
        pass


bot = telebot.TeleBot(config.BOT_TOKEN, use_class_middlewares=True, exception_handler=ExceptionHandler)

try:
    with open("./user_db.pkl", "rb") as f:
        db, db_privilege = pickle.load(f)
except BaseException:
    db = {}
    db_privilege = set()

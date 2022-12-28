# -*- coding: utf-8 -*-
import pickle
import traceback

import config
import sentry_sdk
import telebot
from telebot.handler_backends import BaseMiddleware, CancelUpdate
from telebot.types import ReplyKeyboardRemove


class IsPrivateChat(telebot.custom_filters.SimpleCustomFilter):
    key = 'is_private_chat'

    @staticmethod
    def check(message):
        is_private = message.chat.type == "private"
        if not is_private:
            bot.reply_to(
                message,
                "This command can only be used in private chat.\n此命令只能在私聊中使用。",
                reply_markup=ReplyKeyboardRemove(),
            )
        return is_private


class IsForMe(telebot.custom_filters.SimpleCustomFilter):
    key = 'is_for_me'

    @staticmethod
    def check(message):
        command = message.text.strip().split(" ")[0].split("@")
        if len(command) > 1:
            return command[-1].lower() == config.BOT_USERNAME.lower()
        else:
            return True


class OnlyMentionMiddleware(BaseMiddleware):
    def __init__(self):
        self.update_types = ['message']

    def pre_process(self, message, data):
        if not message.text:
            return CancelUpdate()
        command = message.text.strip().split(" ")[0].split("@")
        if len(command) > 1:
            if command[-1].lower() != config.BOT_USERNAME.lower():
                return CancelUpdate()

    def post_process(self, message, data, exception):
        pass


class ExceptionHandlerMiddleware(BaseMiddleware):
    def __init__(self):
        self.update_types = ['message']

    def pre_process(self, message, data):
        pass

    def post_process(self, message, data, exception=None):
        if exception:
            bot.send_message(
                message.chat.id,
                f"Error encountered! Please contact {config.CONTACT}\n遇到错误！请联系 {config.CONTACT}",
                parse_mode='HTML',
                reply_markup=ReplyKeyboardRemove(),
            )


class ExceptionHandler(telebot.ExceptionHandler):
    def handle(exception):
        if config.SENTRY_DSN:
            sentry_sdk.capture_exception(exception)


bot = telebot.TeleBot(config.BOT_TOKEN, use_class_middlewares=True, exception_handler=ExceptionHandler)

try:
    with open("./user_db.pkl", "rb") as f:
        db, db_privilege = pickle.load(f)
except BaseException:
    db = {}
    db_privilege = set()

bot.add_custom_filter(IsPrivateChat())
bot.setup_middleware(ExceptionHandlerMiddleware())
bot.setup_middleware(OnlyMentionMiddleware())
bot.enable_save_next_step_handlers(delay=2, filename="./step.save")
bot.load_next_step_handlers(filename="./step.save")

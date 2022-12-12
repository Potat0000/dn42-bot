# -*- coding: utf-8 -*-
import pickle
import traceback

import telebot
from telebot.handler_backends import BaseMiddleware, CancelUpdate

import config

bot = telebot.TeleBot(config.BOT_TOKEN, use_class_middlewares=True)

try:
    with open("./user_db.pkl", "rb") as f:
        db, db_privilege = pickle.load(f)
except BaseException:
    db = {}
    db_privilege = set()


class IsPrivateChat(telebot.custom_filters.SimpleCustomFilter):
    key = 'is_private_chat'

    @staticmethod
    def check(message):
        is_private = message.chat.type == "private"
        if not is_private:
            bot.reply_to(message, "This command can only be used in private chat.\n此命令只能在私聊中使用。")
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


class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self, limit):
        self.last_time = {}
        self.limit = limit
        self.update_types = ['message']

    def pre_process(self, message, data):
        if message.from_user.id not in self.last_time:
            self.last_time[message.from_user.id] = message.date
            return
        if message.date - self.last_time[message.from_user.id] < self.limit:
            # User is flooding
            bot.send_message(
                message.chat.id,
                'You are making request too often\n请勿频繁发送请求',
                reply_markup=telebot.types.ReplyKeyboardRemove(),
            )
            return CancelUpdate()
        self.last_time[message.from_user.id] = message.date

    def post_process(self, message, data, exception):
        pass


class OnlyMentionMiddleware(BaseMiddleware):
    def __init__(self):
        self.update_types = ['message']

    def pre_process(self, message, data):
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
            )
            traceback.print_exception(exception)


bot.add_custom_filter(IsPrivateChat())
bot.setup_middleware(ExceptionHandlerMiddleware())
bot.setup_middleware(OnlyMentionMiddleware())
bot.setup_middleware(AntiFloodMiddleware(1))
bot.enable_save_next_step_handlers(delay=2, filename="./step.save")
bot.load_next_step_handlers(filename="./step.save")

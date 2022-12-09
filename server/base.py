# -*- coding: utf-8 -*-
import pickle

import telebot

import config

bot = telebot.TeleBot(config.BOT_TOKEN)

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


bot.add_custom_filter(IsPrivateChat())
bot.add_custom_filter(IsForMe())
bot.enable_save_next_step_handlers(delay=2, filename="./step.save")
bot.load_next_step_handlers(filename="./step.save")

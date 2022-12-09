# -*- coding: utf-8 -*-

from base import bot
from telebot.types import ReplyKeyboardRemove


@bot.message_handler(commands=['cancel'], is_for_me=True, is_private_chat=True)
def cancel(message):
    bot.reply_to(message, "No ongoing operations\n没有正在进行的操作", reply_markup=ReplyKeyboardRemove())

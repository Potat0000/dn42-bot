from base import bot
from telebot.types import ReplyKeyboardRemove


@bot.message_handler(commands=["cancel"], is_private_chat=True)
def cancel(message):
    bot.send_message(message.chat.id, "No ongoing operations\n没有正在进行的操作", reply_markup=ReplyKeyboardRemove())

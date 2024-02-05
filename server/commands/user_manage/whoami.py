import pickle

import tools
from base import bot, db, db_privilege
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove


@bot.message_handler(commands=['whoami'], is_private_chat=True)
def whoami(message):
    if message.chat.id not in db:
        bot.send_message(
            message.chat.id,
            "You are not logged in yet, please use /login first.\n你还没有登录，请先使用 /login",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    markup = ReplyKeyboardRemove()
    if message.chat.id in db_privilege:
        text = "*[Privilege]*\n"
        if len(message.text.split()) == 2:
            new_asn = message.text.split()[1]
            try:
                db[message.chat.id] = int(new_asn)
                with open('./user_db.pkl', 'wb') as f:
                    pickle.dump((db, db_privilege), f)
            except BaseException:
                pass
            else:
                markup = InlineKeyboardMarkup()
                markup.row_width = 1
                markup.add(
                    InlineKeyboardButton(
                        "Show info | 查看信息",
                        url=f"https://t.me/{bot.get_me().username}?start=info_{new_asn}_",
                    )
                )
    else:
        text = ""
    text += "Current login user:\n当前登录用户：\n" f"`{tools.get_asn_mnt_text(db[message.chat.id])}`"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

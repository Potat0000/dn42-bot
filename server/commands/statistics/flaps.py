import time
from datetime import datetime, timezone

import config
import tools
from base import bot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove

PAGE_SIZE = 5

flaps_rank_type_list = ["Count", "RateSec", "FirstSeen", "ASN"]


def gen_flaps_markup(page, rank_type):
    markup = InlineKeyboardMarkup()
    total = len(tools.get_flaps()[1])
    last_page = (total - 1) // PAGE_SIZE
    if page == 0:
        markup.row(
            InlineKeyboardButton(" ", callback_data=" "),
            InlineKeyboardButton("1", callback_data=f"flaps_0_{rank_type}"),
            InlineKeyboardButton("➡️", callback_data=f"flaps_1_{rank_type}"),
        )
    elif page == last_page:
        markup.row(
            InlineKeyboardButton("⬅️", callback_data=f"flaps_{page - 1}_{rank_type}"),
            InlineKeyboardButton(str(page + 1), callback_data=f"flaps_{page}_{rank_type}"),
            InlineKeyboardButton(" ", callback_data=" "),
        )
    else:
        markup.row(
            InlineKeyboardButton("⬅️", callback_data=f"flaps_{page - 1}_{rank_type}"),
            InlineKeyboardButton(str(page + 1), callback_data=f"flaps_{page}_{rank_type}"),
            InlineKeyboardButton("➡️", callback_data=f"flaps_{page + 1}_{rank_type}"),
        )
    for i in range(0, len(flaps_rank_type_list), 2):
        bottons = []
        if i + 1 < len(flaps_rank_type_list):
            key = flaps_rank_type_list[i : i + 2]
        else:
            key = flaps_rank_type_list[i : i + 1]
        for k in key:
            selected = "✅ " if k == rank_type else ""
            bottons.append(InlineKeyboardButton(f"{selected}{k}", callback_data=f"flaps_0_{k}"))
        markup.row(*bottons)
    return markup


def get_flaps_text(page, rank_type):
    update_time, flaps = tools.get_flaps()
    time_delta = int(time.time()) - update_time
    update_time = datetime.fromtimestamp(update_time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    if not flaps:
        return f"```Flaps\nNo recent flaps.\n```Updated {time_delta}s ago\n({update_time})"
    if rank_type == "RateSec":
        flaps.sort(key=lambda x: (-x["RateSec"], -x["TotalCount"], x["FirstSeen"], x["ASN"]))
    elif rank_type == "FirstSeen":
        flaps.sort(key=lambda x: (x["FirstSeen"], -x["TotalCount"], -x["RateSec"], x["ASN"]))
    elif rank_type == "ASN":
        flaps.sort(key=lambda x: (x["ASN"], -x["TotalCount"], -x["RateSec"], x["FirstSeen"]))
    else:  # rank_type == "Count" or others
        flaps.sort(key=lambda x: (-x["TotalCount"], -x["RateSec"], x["FirstSeen"], x["ASN"]))
    msg = []
    for flap in flaps[PAGE_SIZE * page : PAGE_SIZE * (page + 1)]:
        first_seen = datetime.fromtimestamp(flap["FirstSeen"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        msg.append(
            (
                f"- ASN:       {flap['ASN']}\n"
                f"  MNT:       {tools.get_whoisinfo_by_asn(flap['ASN'])}\n"
                f"  Prefix:    {flap['Prefix']}\n"
                f"  Count:     {flap['TotalCount']}\n"
                f"  RateSec:   {flap['RateSec']}\n"
                f"  FirstSeen: {first_seen}"
            )
        )
    return f"```Flaps\n{'\n\n'.join(msg)}\n```Updated {time_delta}s ago\n({update_time})"


@bot.callback_query_handler(func=lambda call: call.data.startswith("flaps_"))
def flaps_callback_query(call):
    _, page, rank_type = call.data.split("_", 2)
    choice = int(page), rank_type
    try:
        bot.edit_message_text(
            get_flaps_text(*choice),
            parse_mode="Markdown",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=gen_flaps_markup(*choice),
        )
    except BaseException:
        pass


@bot.message_handler(commands=["flaps", "flap", "flapalerted"])
def get_flaps(message):
    if not config.FLAPALERTED_URL:
        bot.send_message(
            message.chat.id,
            "Flapalerted integration is not configured.\n未配置 Flapalerted 集成。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    choice = 0, flaps_rank_type_list[0]
    bot.send_message(
        message.chat.id, get_flaps_text(*choice), parse_mode="Markdown", reply_markup=gen_flaps_markup(*choice)
    )

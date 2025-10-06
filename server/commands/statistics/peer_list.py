import time
from datetime import datetime, timezone

import tools
from base import bot, db


@bot.message_handler(commands=["peer_list", "peerlist"])
def peer_list(message):
    try:
        asn = tools.extract_asn(message.text.split()[1])
        if not asn:
            raise ValueError
    except (ValueError, IndexError):
        if message.chat.type == "private" and message.chat.id in db:
            asn = db[message.chat.id]
        else:
            command = message.text.split()[0].split("@")[0][1:]
            bot.reply_to(
                message,
                f"Usage: /{command} [asn]\n用法：/{command} [asn]",
                reply_markup=tools.gen_peer_me_markup(message),
            )
            return
    update_time, _, peer_map = tools.get_map()
    time_delta = int(time.time()) - update_time
    update_time = datetime.fromtimestamp(update_time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    update_str = f"Updated {time_delta}s ago\n({update_time})"
    if asn not in peer_map:
        bot.reply_to(
            message,
            f"```PeerList\nNo data available.\n暂无数据。```{update_str}",
            parse_mode="Markdown",
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    else:
        msg = ""
        for peer_asn in sorted(peer_map[asn]):
            msg += f"{peer_asn:<10}  {tools.get_whoisinfo_by_asn(peer_asn, 'as-name')}\n"
    if len(msg) > 4000:
        msg = tools.split_long_msg(msg)
        last_msg = message
        for index, m in enumerate(msg):
            if index < len(msg) - 1:
                last_msg = bot.reply_to(
                    last_msg,
                    f"```PeerList\n{m}```To be continued...",
                    parse_mode="Markdown",
                    reply_markup=tools.gen_peer_me_markup(message),
                )
            else:
                bot.reply_to(
                    last_msg,
                    f"```PeerList\n{m}````{len(peer_map[asn])}` peers in total\n{update_str}",
                    parse_mode="Markdown",
                    reply_markup=tools.gen_peer_me_markup(message),
                )
    else:
        bot.reply_to(
            message,
            f"```PeerList\n{msg}````{len(peer_map[asn])}` peers in total\n{update_str}",
            parse_mode="Markdown",
            reply_markup=tools.gen_peer_me_markup(message),
        )

import time
from datetime import datetime, timezone

import tools
from base import bot, db


def get_stats(asn):
    update_time, data, _ = tools.get_map()
    if not data:
        return update_time, None
    asn_list = [asn]
    if asn < 10000:
        asn_list.append(4242420000 + asn)
        asn_list.append(asn)
    elif 20000 <= asn < 30000:
        asn_list.append(4242400000 + asn)
        asn_list.append(asn)
    for asn in asn_list:
        mnt = tools.get_whoisinfo_by_asn(asn)
        try:
            centrality = next(i for i in data["centrality"] if i[1] == asn)
            centrality = f"{centrality[3]:.4f}  #{centrality[0]}"
        except StopIteration:
            centrality = "N/A"
        try:
            closeness = next(i for i in data["closeness"] if i[1] == asn)
            closeness = f"{closeness[3]:.5f}  #{closeness[0]}"
        except StopIteration:
            closeness = "N/A"
        try:
            betweenness = next(i for i in data["betweenness"] if i[1] == asn)
            betweenness = f"{betweenness[3]:.5f}  #{betweenness[0]}"
        except StopIteration:
            betweenness = "N/A"
        try:
            peer = next(i for i in data["peer"] if i[1] == asn)
            peer = f"{str(peer[3]).ljust(7)}  #{peer[0]}"
        except StopIteration:
            peer = "N/A"
        if not centrality == closeness == betweenness == peer == "N/A":
            return update_time, {
                "asn": asn,
                "mnt": mnt,
                "centrality": centrality,
                "closeness": closeness,
                "betweenness": betweenness,
                "peer": peer,
            }
    return update_time, None


@bot.message_handler(commands=["stats"])
def stats(message):
    try:
        asn = tools.extract_asn(message.text.split()[1])
        if not asn:
            raise ValueError
    except (ValueError, IndexError):
        if message.chat.type == "private" and message.chat.id in db:
            asn = db[message.chat.id]
        else:
            bot.reply_to(
                message,
                "Usage: /stats [asn]\n用法：/stats [asn]",
                reply_markup=tools.gen_peer_me_markup(message),
            )
            return
    update_time, stats_result = get_stats(asn)
    time_delta = int(time.time()) - update_time
    update_time = datetime.fromtimestamp(update_time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    update_str = f"Updated {time_delta}s ago\n({update_time})"
    if stats_result:
        bot.reply_to(
            message,
            (
                "```Statistics\n"
                f'asn          {stats_result["asn"]}\n'
                f'mnt          {stats_result["mnt"]}\n'
                f'centrality   {stats_result["centrality"]}\n'
                f'closeness    {stats_result["closeness"]}\n'
                f'betweenness  {stats_result["betweenness"]}\n'
                f'peer count   {stats_result["peer"]}'
                "```"
                f"{update_str}"
            ),
            parse_mode="Markdown",
            reply_markup=tools.gen_peer_me_markup(message),
        )
    else:
        bot.reply_to(
            message,
            f"```Statistics\nNo data available.\n暂无数据。```{update_str}",
            parse_mode="Markdown",
            reply_markup=tools.gen_peer_me_markup(message),
        )

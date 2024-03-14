import json
import random
import shlex
import socket
import string
import subprocess
from collections import namedtuple

import base
import config
import dns.resolver
import dns.reversename
import requests
from base import bot, db, db_privilege
from dns.exception import DNSException
from IPy import IP
from requests.adapters import HTTPAdapter, Retry
from requests_futures.sessions import FuturesSession
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


def gen_random_code(length):
    return ''.join(
        random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase + string.digits)
        for _ in range(length)
    )


def split_long_msg(msg, limit=4000):
    chunks = []
    not_chunked_text = msg
    while not_chunked_text:
        if len(not_chunked_text) <= limit:
            chunks.append(not_chunked_text)
            break
        split_index = not_chunked_text.rfind("\n", 0, limit)
        if split_index == -1:  # The chunk is too big
            return None
        else:
            chunks.append(not_chunked_text[: split_index + 1])
            not_chunked_text = not_chunked_text[split_index + 1 :]
    return chunks


def get_whoisinfo_by_asn(asn, item='mnt-by'):
    try:
        whois = subprocess.check_output(shlex.split(f'whois -h {config.WHOIS_ADDRESS} AS{asn}'), timeout=3).decode(
            "utf-8"
        )
        for i in whois.splitlines():
            if i.startswith(f'{item}:'):
                raw_name = i.split(':')[1].strip()
                for w in ['AS', 'DN42', 'MNT']:
                    if raw_name.endswith(f'-{w}'):
                        raw_name = raw_name[: -(len(w) + 1)]
                    if raw_name.startswith(f'{w}-'):
                        raw_name = raw_name[(len(w) + 1) :]
                return raw_name
    except BaseException:
        pass
    return str(asn)


def get_asn_mnt_text(asn):
    if (s := get_whoisinfo_by_asn(asn)) != str(asn):
        return f"{s} AS{asn}"
    else:
        return f"AS{asn}"


def basic_ip_domain_test(address):
    resolver = dns.resolver.Resolver()
    resolver.nameservers = ['127.0.0.1', '172.20.0.53', '172.23.0.53', '8.8.8.8', '8.8.4.4']
    resolver.timeout = 0.15
    resolver.lifetime = 1
    test_result = namedtuple('test_result', ['raw', 'ipv4', 'ipv6', 'domain'])
    try:  # Test for IPv4
        socket.inet_pton(socket.AF_INET, address)
        domain = None
        try:
            domain = str(resolver.resolve(dns.reversename.from_address(str(IP(address))), "PTR")[0])
            if domain.endswith('.'):
                domain = domain[:-1]
        except BaseException:
            pass
        if str(IP(address)) == domain:
            domain = None
        return test_result(str(IP(address)), str(IP(address)), None, domain)
    except (socket.error, OSError):
        try:  # Test for IPv6
            socket.inet_pton(socket.AF_INET6, address)
            domain = None
            try:
                domain = str(resolver.resolve(dns.reversename.from_address(str(IP(address))), "PTR")[0])
                if domain.endswith('.'):
                    domain = domain[:-1]
            except BaseException:
                pass
            if str(IP(address)) == domain:
                domain = None
            return test_result(str(IP(address)), None, str(IP(address)), domain)
        except (socket.error, OSError):  # Test for domain
            ipv4 = None
            ipv6 = None
            try:
                for i in resolver.resolve(address, 'A'):
                    try:
                        socket.inet_pton(socket.AF_INET, i.address)
                    except (socket.error, OSError):
                        pass
                    else:
                        ipv4 = i.address
                        break
            except DNSException:
                pass
            try:
                for i in resolver.resolve(address, 'AAAA'):
                    try:
                        socket.inet_pton(socket.AF_INET6, i.address)
                    except (socket.error, OSError):
                        pass
                    else:
                        ipv6 = i.address
                        break
            except DNSException:
                pass
            if ipv4 or ipv6:
                return test_result(address, ipv4, ipv6, address)
            else:
                return None


def test_ip_domain(testcase):
    IPv4_Bogon = [
        IP('0.0.0.0/8'),
        IP('10.0.0.0/8'),
        IP('100.64.0.0/10'),
        IP('127.0.0.0/8'),
        IP('127.0.53.53'),
        IP('169.254.0.0/16'),
        IP('172.16.0.0/12'),
        IP('192.0.0.0/24'),
        IP('192.0.2.0/24'),
        IP('192.168.0.0/16'),
        IP('198.18.0.0/15'),
        IP('198.51.100.0/24'),
        IP('203.0.113.0/24'),
        IP('224.0.0.0/4'),
        IP('240.0.0.0/4'),
        IP('255.255.255.255/32'),
    ]
    IPv6_Bogon = [
        IP('::/128'),
        IP('::1/128'),
        IP('::ffff:0:0/96'),
        IP('::/96'),
        IP('100::/64'),
        IP('2001:10::/28'),
        IP('2001:db8::/32'),
        IP('fc00::/7'),
        IP('fe80::/10'),
        IP('fec0::/10'),
        IP('ff00::/8'),
        IP('2002::/24'),
        IP('2002:a00::/24'),
        IP('2002:7f00::/24'),
        IP('2002:a9fe::/32'),
        IP('2002:ac10::/28'),
        IP('2002:c000::/40'),
        IP('2002:c000:200::/40'),
        IP('2002:c0a8::/32'),
        IP('2002:c612::/31'),
        IP('2002:c633:6400::/40'),
        IP('2002:cb00:7100::/40'),
        IP('2002:e000::/20'),
        IP('2002:f000::/20'),
        IP('2002:ffff:ffff::/48'),
        IP('2001::/40'),
        IP('2001:0:a00::/40'),
        IP('2001:0:7f00::/40'),
        IP('2001:0:a9fe::/48'),
        IP('2001:0:ac10::/44'),
        IP('2001:0:c000::/56'),
        IP('2001:0:c000:200::/56'),
        IP('2001:0:c0a8::/48'),
        IP('2001:0:c612::/47'),
        IP('2001:0:c633:6400::/56'),
        IP('2001:0:cb00:7100::/56'),
        IP('2001:0:e000::/36'),
        IP('2001:0:f000::/36'),
        IP('2001:0:ffff:ffff::/64'),
    ]
    testcase = testcase.strip()
    return_tuple = namedtuple('IP_Domain_Info', ['raw', 'ipv4', 'ipv6', 'domain', 'asn', 'mnt', 'dn42', 'clearnet'])
    asn = None
    mnt = None
    dn42 = False
    clearnet = False
    test_result = basic_ip_domain_test(testcase)
    if not test_result:
        return None
    raw = test_result.raw
    ipv4 = test_result.ipv4
    ipv6 = test_result.ipv6
    domain = test_result.domain

    if raw.endswith('.dn42'):
        dn42 = True
    elif domain and domain.endswith('.dn42'):
        dn42 = True
    elif (raw == ipv4 or raw == ipv6) and ((ipv4 and ipv4 in IP('172.20.0.0/14')) or (ipv6 and ipv6 in IP('fc00::/7'))):
        dn42 = True
    if dn42:
        try:
            whois4 = subprocess.check_output(
                shlex.split(f'whois -h {config.WHOIS_ADDRESS} -T route {ipv4}'), timeout=3
            ).decode("utf-8")
            whois6 = subprocess.check_output(
                shlex.split(f'whois -h {config.WHOIS_ADDRESS} -T route6 {ipv6}'), timeout=3
            ).decode("utf-8")
            asn = set()
            for i in whois4.splitlines() + whois6.splitlines():
                if i.startswith('origin:'):
                    asn.add(i.split(':')[1].strip())
                elif i.startswith('mnt-by:'):
                    mnt = i.split(':')[1].strip()
            if asn:
                asn = ', '.join(asn)
            else:
                raise RuntimeError
        except BaseException:
            dn42 = False
            asn = None
    if not dn42:
        clearnet4 = False
        clearnet6 = False
        if ipv4 and all(ipv4 not in i for i in IPv4_Bogon):
            clearnet4 = True
        if ipv6 and all(ipv6 not in i for i in IPv6_Bogon):
            clearnet6 = True
        if not (clearnet4 or clearnet6):
            clearnet = False
        else:
            clearnet = True
            if clearnet4 and not clearnet6:
                ipv6 = None
            elif clearnet6 and not clearnet4:
                ipv4 = None
    return return_tuple(raw, ipv4, ipv6, domain, asn, mnt, dn42, clearnet)


def gen_peer_me_markup(message):
    if message.chat.id in db_privilege:
        return None
    if message.chat.type == "private" and message.chat.id in db:
        if get_info(db[message.chat.id]):
            return None
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("Peer with me | 与我 Peer", url=f"https://t.me/{bot.get_me().username}"))
    return markup


def get_from_agent(type, data, server=None, *, timeout=10, backoff_factor=0.1):
    api_result = namedtuple('api_result', ['text', 'status'])
    if not server:
        server = base.servers.keys()
    session = FuturesSession()
    session.mount(
        'http://',
        HTTPAdapter(
            max_retries=Retry(
                total=5,
                backoff_factor=backoff_factor,
                allowed_methods=('GET', 'POST'),
            )
        ),
    )
    futures = []
    for region in server:
        future = session.post(
            f"http://{region}.{config.ENDPOINT}:{config.API_PORT}/{type}",
            data=data,
            headers={"X-DN42-Bot-Api-Secret-Token": config.API_TOKEN},
            timeout=timeout,
        )
        future.region = region
        futures.append(future)

    result = {}
    for future in futures:
        try:
            resp = future.result()
            result[future.region] = api_result(resp.text, resp.status_code)
        except requests.exceptions.Timeout:
            result[future.region] = api_result('', 408)
        except BaseException:
            result[future.region] = api_result('', 500)
    return result


def get_info(asn):
    data = {}
    for k, v in get_from_agent("info", str(asn)).items():
        if v.status == 200:
            try:
                data[k] = json.loads(v.text)
            except BaseException:
                data[k] = 'Error'
        elif v.status == 500:
            data[k] = v.text
    return data

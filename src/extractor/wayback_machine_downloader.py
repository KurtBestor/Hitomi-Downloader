# coding: utf8
# title: Wayback Machine Downloader
# comment: https://archive.org
# author: bog_4t

import downloader
from utils import Downloader, Session, get_print, update_url_query
from ratelimit import limits, sleep_and_retry
import ree as re
import json
import datetime
import errors
from error_printer import print_error


@Downloader.register
class Downloader_wayback_machine(Downloader):
    type = 'waybackmachine'
    URLS = ['archive.org', 'web.archive.org']
    icon = 'https://archive.org/services/img/publicsafetycode'
    display_name = 'Wayback Machine'

    def init(self):
        self.session = Session()

    def read(self):
        query = WaybackMachineAPI.get_query(self.url)
        self.urls.extend(get_imgs(query, self.session, cw=self.cw))
        self.title = '{:%Y%m%d%H%M%S}'.format(datetime.datetime.now())


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
        return re.findall(r'archive.org\/(?:(?:web/)?)(?:(?:[0-9]{4})?(?:\*/)?)(.*)', url)[0]

    def snapshots(self, url_for_query):
        snapshots = set()
        data = self.call(url_for_query)
        if not data:
            raise Exception('No archive found')
        for snapshot in data[1:]:
            snapshots.add('https://web.archive.org/web/{}/{}'.format(snapshot[1], snapshot[2]))
        return snapshots


def default(img):
    if img.has_attr('src'):
        return True
    return False


def twitter(img):
    if default(img) and '/media/' in img['src']:
        return True
    return False


filter_ = [
    default,
    twitter,
]


def get_filter_code(query):
    if 'twitter.com' in query.lower():
        return 1
    return 0


def get_imgs(query, session, cw):
    imgs = []
    img_elements = None
    snapshots = WaybackMachineAPI(session, cw).snapshots(query)
    filter_code = get_filter_code(query)
    for url in snapshots:
        soup = downloader.read_soup(url)
        img_elements = soup.find_all('img')
        for img in img_elements:
            if filter_[filter_code](img):
                imgs.append(img['src'])
    return imgs



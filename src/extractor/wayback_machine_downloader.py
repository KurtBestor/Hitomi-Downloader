# coding: utf8
# title: Wayback Machine Downloader
# comment: https://archive.org
# author: bog_4t

import downloader
from utils import Downloader, Soup, Session, get_print
from ratelimit import limits, sleep_and_retry
import ree as re
import json
import errors
from error_printer import print_error


@Downloader.register
class Downloader_wayback_machine(Downloader):
    type = 'waybackmachine'
    URLS = ['archive.org', 'web.archive.org']
    icon = 'https://archive.org/services/img/publicsafetycode'
    display_name = 'Wayback Machine'

    def read(self):
        self.urls.extend(get_imgs(self.url, Session(), cw=self.cw))
        self.title = 'placeholder'


class WaybackMachineAPI(object):
    def __init__(self, session, cw=None):
        self.url_api = 'https://web.archive.org/cdx/search/cdx'
        self.session = session
        self.cw = cw
        self.params = {
            'status code': '200',
            'filter': 'mimetype:text/html',
            'output': 'json'
        }

    @sleep_and_retry
    @limits(1, 2)
    def call(self, url_for_query):
        params = self.params
        params['url'] = url_for_query
        response = self.session.get(self.url_api, params=params)
        if response.status_code != 200:
            response.raise_for_status()
        return response.json()

    def snapshots(self, url_for_query):
        snapshots = set()
        data = self.call(url_for_query)
        if not data:
            raise Exception('No archive found')
        for snapshot in data[1:]:
            snapshots.add('https://web.archive.org/web/{}/{}'.format(snapshot[1], snapshot[2]))
        return snapshots


def get_imgs(url, session, cw):
    print_ = get_print(cw)
    imgs = []
    url_for_query = re.findall(r'archive.org\/(?:(?:web/)?)(?:(?:[0-9]{4})?(?:\*/)?)(.*)', url)
    for snapshot in WaybackMachineAPI(session, cw).snapshots(url_for_query):
        #html = downloader.read_html(url, session=session)
        html = session.get(snapshot).text
        print_(html)
        soup = Soup(html)
        for image in soup.find_all('img'):
            if image.has_attr('src'):
                imgs.append(image['src'])
    return imgs

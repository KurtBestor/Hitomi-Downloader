#coding:utf8
from utils import Downloader, clean_title, Session, Soup, urljoin
import clf2
from mastodon import get_info
import ree as re



def get_id(url):
    return re.find('pawoo.net/([^/]+)', url.lower())



class Downloader_pawoo(Downloader):
    type = 'pawoo'
    URLS = ['pawoo.net']
    ACCEPT_COOKIES = [r'(.*\.)?pawoo\.net']

    def init(self):
        self.session = Session()
        if get_id(self.url) == 'web': #6123
            soup = Soup(clf2.solve(self.url)['html'])
            name = soup.find('div', class_='account__header__tabs__name')
            id_ = name.find('small').text.strip()
            self.url = urljoin(self.url, f'/{id_}')

    @classmethod
    def fix_url(cls, url):
        if url.endswith('/media'):
            url = url[:-len('/media')]
        id_ = get_id(url) or url
        if id_ == 'web':
            return url
        return f'https://pawoo.net/{id_}'

    def read(self):
        id_ = get_id(self.url)
        info = get_info('pawoo.net', id_, f'pawoo_{id_}', self.session, self.cw)

        self.urls += info['files']

        self.title = clean_title('{} (pawoo_{})'.format(info['title'], id_))

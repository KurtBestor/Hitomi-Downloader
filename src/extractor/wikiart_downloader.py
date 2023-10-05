#coding:utf8
import downloader
import json
from utils import LazyUrl, Downloader, Session, get_print, clean_title, check_alive
import os
from timee import sleep
from translator import tr_



class Image:
    def __init__(self, url, referer, title, id):
        self.url = LazyUrl(referer, lambda _: url, self)
        ext = os.path.splitext(url.split('?')[0])[1]
        n = len(id) + len(ext) + 3
        title = clean_title(title, n=-n)
        self.filename = '{} - {}{}'.format(id, title, ext)



class Downloader_wikiart(Downloader):
    type = 'wikiart'
    URLS = ['wikiart.org']
    display_name = 'WikiArt'
    ACCEPT_COOKIES = [r'(.*\.)?wikiart\.org']

    def init(self):
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        url = 'https://www.wikiart.org/en/{}'.format(get_id(url))
        return url

    def read(self):
        artist = get_artist(get_id(self.url), self.session)
        self.artist = artist

        for img in get_imgs(self.url, artist, self.session, cw=self.cw):
            self.urls.append(img.url)

        self.title = clean_title(artist)



def get_id(url):
    userid = url.split('?')[0].split('#')[0].split('wikiart.org/')[1].split('/')[1]
    return userid


def get_imgs(url, artist, session, cw=None):
    print_ = get_print(cw)
    userid = get_id(url)
    print(userid)

    imgs = []
    ids = set()
    for p in range(1, 100):
        check_alive(cw)
        url_api = 'https://www.wikiart.org/en/{}/mode/all-paintings?json=2&layout=new&page={}&resultType=masonry'.format(userid, p)
        print(url_api)
        data_raw = downloader.read_html(url_api, url, session=session)
        data = json.loads(data_raw)

        _imgs = data['Paintings']
        n = data['AllPaintingsCount']

        if not _imgs:
            print_('???')
            break

        for p in _imgs:
            img = p['image']
            id = p['id']
            referer = p['paintingUrl']
            title = p['title']
            if id in ids:
                print('duplicate: {}'.format(id))
                continue
            ids.add(id)
            img = Image(img, referer, title, id)
            imgs.append(img)

        s = '{}  {} - {} / {}'.format(tr_('읽는 중...'), artist, len(imgs), n)
        if cw:
            cw.setTitle(s)
        else:
            print(s)

        if len(imgs) == n:
            print_('full')
            break

    return imgs


def get_artist(userid, session):
    url = 'https://www.wikiart.org/en/{}'.format(userid)
    soup = downloader.read_soup(url, session=session)

    return soup.find('h3').text.strip()

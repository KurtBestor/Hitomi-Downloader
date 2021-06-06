#coding:utf8
import downloader
import ree as re
from timee import sleep, clock, time
from constants import clean_url
from utils import Downloader, urljoin, try_n, Session, get_print, clean_title, Soup, fix_protocol, domain
import os
from translator import tr_
import json
from datetime import datetime
import constants
import clf2
import errors


def suitable(url):
    if domain(url.lower(), 2) not in ['weibo.com', 'weibo.cn']:
        return False
    if '/tv/' in url.lower():
        return False
    return True


@Downloader.register
class Downloader_weibo(Downloader):
    type = 'weibo'
    URLS = [suitable]

    def init(self):
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        url = url.replace('weibo.cn', 'weibo.com').split('?')[0]
        if 'weibo.com/p/' in url:
            id = re.findall('weibo.com/p/([^/]+)', url)[0]
            url = 'https://weibo.com/p/{}'.format(id)
        elif 'weibo.com/u/' in url:
            id = re.findall('weibo.com/u/([^/]+)', url)[0]
            url = 'https://weibo.com/u/{}'.format(id)
        elif 'weibo.com/' in url:
            id = re.findall('weibo.com/([^/]+)', url)[0]
            url = 'https://weibo.com/{}'.format(id)
        else:
            id = url
            url = 'https://weibo.com/u/{}'.format(id)
        url = fix_protocol(url)
        return url

    def read(self):
        checkLogin(self.session)
        
        uid, oid, name = get_id(self.url, self.cw)
        title = clean_title('{} (weibo_{})'.format(name, uid))
        
        for img in get_imgs(uid, oid, title, self.session, cw=self.cw, d=self, parent=self.mainWindow):
            self.urls.append(img.url)
            self.filenames[img.url] = img.filename

        self.title = title


def checkLogin(session):
    c = session.cookies._cookies.get('.weibo.com', {}).get('/',{}).get('SUBP')
    if not c or c.is_expired():
        raise errors.LoginRequired()
    

class Album(object):

    def __init__(self, id, type):
        self.id = id
        self.type = type


class Image(object):

    def __init__(self, url, filename=None, timestamp=0):
        self.url = url
        if filename is None:
            filename = os.path.basename(url)
        self.filename = filename
        self.timestamp = timestamp


def _get_page_id(html):
    m = re.search("CONFIG\\['page_id'\\]='([0-9]+?)'", html)
    return m


def get_id(url, cw=None):
    for try_ in range(2):
        try:
            res = clf2.solve(url, cw=cw, f=_get_page_id)
            html = res['html']
            soup = Soup(html)
            if soup.find('div', class_='gn_login'):
                raise errors.LoginRequired()
            m = _get_page_id(html)
            if not m:
                raise Exception('no page_id')
            oid = m.groups()[0]
            uids = re.findall('uid=([0-9]+)', html)
            uid = max(set(uids), key=uids.count)
            name = re.findall("CONFIG\\['onick'\\]='(.+?)'", html)[0]
            break
        except errors.LoginRequired as e:
            raise
        except Exception as e:
            e_ = e
            print(e)
    else:
        raise e_
    return uid, oid, name



def get_imgs(uid, oid, title, session, cw=None, d=None, parent=None):
    print_ = get_print(cw)
    print_('uid: {}, oid:{}'.format(uid, oid))

    @try_n(4)
    def get_album_imgs(album, page):
        url = 'https://photo.weibo.com/photos/get_all?uid={}&album_id={}&count=30&page={}&type={}&__rnd={}'.format(uid, album.id, page, album.type, int(time()*1000))
        referer = 'https://photo.weibo.com/{}/talbum/index'.format(uid)
        html = downloader.read_html(url, referer, session=session, timeout=30)
        j = json.loads(html)
        data = j['data']
        imgs = []
        for photo in data['photo_list']:
            host = photo['pic_host']
            name = photo['pic_name']
            id = photo['photo_id']
            timestamp = photo['timestamp']
            date = datetime.fromtimestamp(timestamp)
            t = '{:02}-{:02}-{:02}'.format(date.year % 100, date.month, date.day)
            url = '{}/large/{}'.format(host, name)
            ext = os.path.splitext(name)[1]
            filename = '[{}] {}{}'.format(t, id, ext)
            img = Image(url, filename, timestamp)
            imgs.append(img)

        return imgs

    def get_albums(page):
        url = 'https://photo.weibo.com/albums/get_all?uid={}&page={}&count=20&__rnd={}'.format(uid, page, int(time()*1000))
        referer = 'https://photo.weibo.com/{}/albums?rd=1'.format(uid)
        html = downloader.read_html(url, referer, session=session)
        j = json.loads(html)
        data = j['data']
        albums = []
        for album in data['album_list']:
            id = album['album_id']
            type = album['type']
            album = Album(id, type)
            albums.append(album)

        return albums

    albums = []
    for p in range(1, 101):
        albums_new = get_albums(p)
        albums += albums_new
        print_('p:{}, albums:{}'.format(p, len(albums)))
        if not albums_new:
            break

    imgs = []
    for album in albums:
        print('Album:', album.id, album.type)
        for p in range(1, 101):
            imgs_new = get_album_imgs(album, p)
            imgs += imgs_new
            s = u'{} {}  -  {}'.format(tr_(u'읽는 중...'), title, len(imgs))
            if cw:
                if not cw.alive:
                    return []
                cw.setTitle(s)
            else:
                print(s)
            if not imgs_new:
                break
            sleep(1)

    imgs = sorted(imgs, key=lambda img: img.timestamp, reverse=True)
    return imgs



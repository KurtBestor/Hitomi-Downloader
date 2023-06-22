#coding:utf8
import downloader
import ree as re
from timee import sleep, clock, time
from constants import clean_url
from utils import Downloader, urljoin, try_n, Session, get_print, clean_title, Soup, fix_protocol, domain, get_max_range
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



class Downloader_weibo(Downloader):
    type = 'weibo'
    URLS = [suitable]
    ACCEPT_COOKIES = [r'(.*\.)?(weibo\.com|sina\.com\.cn)']

    def init(self):
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        url = url.replace('weibo.cn', 'weibo.com').split('?')[0]
        if 'weibo.com/p/' in url:
            id = re.find(r'weibo.com/p/([^/]+)', url, err='no id')
            url = 'https://weibo.com/p/{}'.format(id)
        elif 'weibo.com/u/' in url:
            id = re.find(r'weibo.com/u/([^/]+)', url, err='no id')
            url = 'https://weibo.com/u/{}'.format(id)
        elif 'weibo.com/' in url:
            id = re.find(r'weibo.com/([^/]+)', url, err='no id')
            url = 'https://weibo.com/{}'.format(id)
        else:
            id = url
            url = 'https://weibo.com/u/{}'.format(id)
        return fix_protocol(url)

    def read(self):
        checkLogin(self.session)

        uid, oid, name = get_id(self.url, self.cw)
        title = clean_title('{} (weibo_{})'.format(name, uid))

        for img in get_imgs(uid, oid, title, self.session, cw=self.cw, d=self, parent=self.mainWindow):
            self.urls.append(img.url)
            self.filenames[img.url] = img.filename

        self.title = title
        self.referer = self.url


def checkLogin(session):
    c = session.cookies._cookies.get('.weibo.com', {}).get('/',{}).get('SUBP')
    if not c or c.is_expired():
        raise errors.LoginRequired()


class Album:

    def __init__(self, id, type):
        self.id = id
        self.type = type


class Image:

    def __init__(self, url, filename=None, timestamp=0):
        self.url = url
        if filename is None:
            filename = os.path.basename(url)
        self.filename = filename
        self.timestamp = timestamp


def _get_page_id(html):
    return re.find(r"CONFIG\['page_id'\]='([0-9]+)'", html) or re.find(r'/u/page/follow/([0-9]+)', html)


def get_id(url, cw=None):
    for try_ in range(2):
        try:
            res = clf2.solve(url, cw=cw, f=_get_page_id)
            html = res['html']
            soup = Soup(html)
            if soup.find('div', class_='gn_login') or soup.find('a', class_=lambda c: c and c.startswith('LoginBtn')):
                raise errors.LoginRequired()
            oid = _get_page_id(html)
            if not oid:
                raise Exception('no page_id')
            uids = re.findall(r'uid=([0-9]+)', html)
            uid = max(set(uids), key=uids.count)
            name = re.find(r"CONFIG\['onick'\]='(.+?)'", html) or soup.find('div', class_=lambda c:c and c.startswith('ProfileHeader_name')).text.strip()
            if not name:
                raise Exception('no name')
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

    max_pid = get_max_range(cw)

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

    @try_n(2)
    def get_albums(page):
        url = 'https://photo.weibo.com/albums/get_all?uid={}&page={}&count=20&__rnd={}'.format(uid, page, int(time()*1000))
        referer = 'https://photo.weibo.com/{}/albums?rd=1'.format(uid)
        html = downloader.read_html(url, referer, session=session)
        if '<title>新浪通行证</title>' in html:
            raise errors.LoginRequired()
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
        imgs_album = []
        for p in range(1, 101):
            imgs_new = get_album_imgs(album, p)
            imgs_album += imgs_new
            s = '{} {}  -  {}'.format(tr_('읽는 중...'), title, len(imgs))
            if cw:
                cw.setTitle(s)
            else:
                print(s)
            if len(imgs_album) >= max_pid:
                break
            if not imgs_new:
                break
            sleep(1, cw)
        imgs += imgs_album

    imgs = sorted(imgs, key=lambda img: img.timestamp, reverse=True)
    return imgs[:max_pid]

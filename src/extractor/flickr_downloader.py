#coding: utf-8
import downloader
import flickr_api
from timee import sleep
from utils import Downloader, LazyUrl, query_url, clean_title
import os
from translator import tr_
import ree as re
from datetime import datetime
import flickr_auth


alphabet = '123456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ'
base = len(alphabet)
def b58encode(div, s=''):
    if div >= base:
        div, mod = divmod(div, base)
        return b58encode(div, alphabet[mod] + s)
    return alphabet[div] + s
def b58decode(s):
    return sum(alphabet.index(c) * pow(base, i) for i, c in enumerate(reversed(s)))



class Image:
    def __init__(self, photo):
        self.photo = photo
        self.id = photo.id
        self.filename = None

        def f(_=None):
            url = photo.getPhotoFile()
            #url = 'https://flic.kr/p/{}'.format(b58encode(int(photo.id)))
            ext = os.path.splitext(url)[1]
            date = datetime.fromtimestamp(int(photo.dateuploaded))
            date = u'{:02}-{:02}-{:02}'.format(date.year%100, date.month, date.day)
            self.filename = u'[{}] {}{}'.format(date, self.id, ext)
            return url
        self.url = LazyUrl(u'flickr_{}'.format(self.id), f, self)


def find_ps(url):
    user = flickr_api.Person.findByUrl(url)
    id = re.search('/albums/([0-9]+)', url).groups()[0]
    pss = user.getPhotosets()
    for ps in pss:
        if ps.id == id:
            break
    else:
        raise Exception('Not found photoset id')
    return user, ps



class Downloader_flickr(Downloader):
    type = 'flickr'
    URLS = ['flickr.com']
    _name = None

    def init(self):
        if 'flickr.com' in self.url.lower():
            self.url = self.url.replace('http://', 'https://')
        else:
            self.url = 'https://www.flickr.com/people/{}'.format(self.url)

    @property
    def name(self):
        global pss
        if self._name is None:
            url = self.url
            flickr_auth.get_api(url, self.cw)
            if '/albums/' in url:
                user, ps = find_ps(url)
                self._name = u'{} (flickr_album_{}_{})'.format(ps.title, user.id, ps.id)
            else:
                user = flickr_api.Person.findByUrl(url)
                self._name = u'{} (flickr_{})'.format(user.username, user.id)
        return clean_title(self._name)


    def read(self):
        self.title = self.name

        imgs = get_imgs(self.url, self.title, cw=self.cw)

        for img in imgs:
            self.urls.append(img.url)

        self.title = self.name


def get_imgs(url, title=None, cw=None):
    flickr_auth.get_api(title, cw)
    if not flickr_auth.isAuth:
        raise Exception('No Auth')


    if '/albums/' in url:
        user, ps = find_ps(url)
        handle = ps
    else:
        user = flickr_api.Person.findByUrl(url)
        handle = user

    photos = []

    per_page = 500
    for page in range(1, 200):
        photos_new = handle.getPhotos(per_page=per_page, page=page)
        photos += photos_new
        if len(photos_new) < per_page:
            break

        msg = u'{}  {} - {}'.format(tr_(u'읽는 중...'), title, len(photos))
        if cw:
            if not cw.alive:
                break
            cw.setTitle(msg)
        else:
            print(msg)

    imgs = []
    for photo in photos:
        img = Image(photo)
        imgs.append(img)

    return imgs

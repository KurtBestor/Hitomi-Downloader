#coding:utf8
from __future__ import division, print_function, unicode_literals
import downloader, json, os
from fucking_encoding import clean_title
from error_printer import print_error
from translator import tr_
from timee import sleep
from utils import Downloader, Soup, get_print, lazy, Session, try_n, LazyUrl


class Image(object):

    def __init__(self, post_url, date, url, page):
        self.post_url = post_url
        self.date = date
        self.url = LazyUrl(post_url, lambda _: url, self)
        self.page = page
        name = post_url.split('/')[(-1)]
        ext = os.path.splitext(url.split('?')[0])[1]
        self.filename = '[{}] {}_p{}{}'.format(date, name, page, ext)

    def __repr__(self):
        return 'Image({})'.format(self.filename)


@Downloader.register
class Downloader_artstation(Downloader):
    type = 'artstation'
    URLS = ['artstation.com']

    def init(self):
        self.url_main = 'https://www.artstation.com/{}'.format(self.id.replace('artstation_', '').replace('／', '/'))
        
        if '/artwork/' in self.url:
            pass#raise NotImplementedError('Single post')
        else:
            self.url = self.url_main
        
        self.session = Session()

    @lazy
    def id(self):
        id = get_id(self.url, self.customWidget)
        return 'artstation_{}'.format(clean_title(id))

    @lazy
    def name(self):
        html = downloader.read_html(self.url_main, session=self.session)
        soup = Soup(html)
        name = soup.find('meta', {'property': 'og:title'}).attrs['content']
        return clean_title('{} ({})'.format(name, self.id))

    def read(self):
        cw = self.customWidget
        self.title = self.name
        id = self.id.replace('artstation_', '').replace('／', '/')
        if '/' in id:
            type = id.split('/')[1]
            id = id.split('/')[0]
        else:
            type = None
        if '/artwork/' in self.url:
            id_art = get_id_art(self.url)
            imgs = get_imgs_page(id_art, self.session, cw=cw)
        else:
            imgs = get_imgs(id, self.title, self.session, type=type, cw=cw)
            
        for img in imgs:
            self.urls.append(img.url)

        self.title = self.name


@try_n(2)
def get_imgs(id, title, session, type=None, cw=None):
    print_ = get_print(cw)
    if type is None:
        type = 'projects'
    referer = 'https://www.artstation.com/{}'.format(id)
    html = downloader.read_html(referer, session=session)
    print(session.cookies.keys())
    datas = []
    p = 1
    while p < 1000:
        url = 'https://www.artstation.com/users/{}/{}.json?page={}'.format(id, type, p)
        print(url)
        for try_ in range(4):
            try:
                html = downloader.read_html(url, session=session, referer=referer)
                break
            except Exception as e:
                print(e)

        else:
            raise

        j = json.loads(html)
        data = j['data']
        if not data:
            break
        datas += data
        if cw:
            if not cw.alive:
                return []
            cw.setTitle(('{}  {} - {}').format(tr_('페이지 읽는 중...'), title, len(datas)))
        else:
            print(len(datas))
        p += 1

    imgs = []
    i = 0
    while i < len(datas):
        data = datas[i]
        date = data['created_at'][2:10]
        post_url = data['permalink']
        print('post_url', post_url)
        id_art = get_id_art(post_url)
        imgs += get_imgs_page(id_art, session, date=date, cw=cw)
        if cw:
            if not cw.alive:
                return []
            cw.setTitle(('{}  {} - {}').format(tr_('이미지 읽는 중...'), title, len(imgs)))
        else:
            print(len(imgs))
        i += 1

    return imgs


def get_id_art(post_url):
    return post_url.split('/artwork/')[1].split('/')[0]


def get_id(url, cw=None):
    print_ = get_print(cw)        

    url = url.split('?')[0].split('#')[0]

    if '/artwork/' in url:
        id_art = get_id_art(url)
        imgs = get_imgs_page(id_art, session=Session(), cw=cw)
        return imgs[0].data['user']['username']
    
    if '.artstation.' in url and 'www.artstation.' not in url:
        id = url.split('.artstation')[0].split('//')[-1]
        type = None
    elif 'artstation.com' in url:
        paths = url.split('artstation.com/')[1].split('/')
        id = paths[0]
        type = paths[1] if len(paths) > 1 else None
    else:
        id = url.replace('artstation_', '').replace('／', '/')
        type = None

    if type not in [None, 'likes']:
        type = None

    print_('type: {}, id: {}'.format(type, id))

    if type:
        return '{}/{}'.format(id, type)
    return id


def get_imgs_page(id_art, session, date=None, cw=None):
    print_ = get_print(cw)
    url_json = 'https://www.artstation.com/projects/{}.json'.format(id_art)
    post_url = 'https://www.artstation.com/artwork/{}'.format(id_art)
    try:
        html = downloader.read_html(url_json, session=session, referer=post_url)
        data = json.loads(html)
        imgs_ = data['assets']
    except Exception as e:
        print_(print_error(e)[(-1)])
        return []

    if date is None:
        date = data['created_at'][2:10]

    imgs = []
    for page, img in enumerate(imgs_):
        if not img['has_image']:
            print('no img')
            continue
        url = None
        video = None
        embed = img.get('player_embedded')
        if embed:
            soup = Soup(embed)
            url_embed = soup.find('iframe').attrs['src']
            print_('embed: {}'.format(url_embed))
            try:
                html = downloader.read_html(url_embed, session=session, referer=post_url)
                soup = Soup(html)
                url = soup.find('video').find('source').attrs['src']
            except Exception as e:
                print(e)
            if not url:
                try:
                    url = soup.find('link', {'rel': 'canonical'}).attrs['href']
                    print_('YouTube: {}'.format(url))
                    raise Exception('YouTube')
##                    from extractor import youtube_downloader
##                    video = youtube_downloader.Video(url, cw=cw)
                except Exception as e:
                    print(e)
                    url = None
        if not url:
            url = img['image_url']
        if video:
            img = video
        else:
            img = Image(post_url, date, url, page)
            
        img.data = data#
        imgs.append(img)

    return imgs



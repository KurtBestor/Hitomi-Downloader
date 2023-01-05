#coding:utf8
import os
import json
import downloader
from error_printer import print_error
from translator import tr_
from utils import Downloader, Soup, get_print, lazy, Session, try_n, LazyUrl, clean_title, check_alive


class Image:

    def __init__(self, post_url, date, url, page, name, data):
        self.post_url = post_url
        self.url = LazyUrl(post_url, lambda _: url.replace('/large/', '/4k/'), self, url)
        self.page = page
        self.data = data
        ext = os.path.splitext(url.split('?')[0])[1]
        self.filename = f'[{date}] {name}_p{page}{ext}'

    def __repr__(self):
        return f'Image({self.filename})'



class Downloader_artstation(Downloader):
    type = 'artstation'
    URLS = ['artstation.com']
    display_name = 'ArtStation'
    ACCEPT_COOKIES = [r'(.*\.)?artstation\.(com|co)']
    url_main = None

    def init(self):
        _ = self._id.replace('artstation_', '', 1)
        self.url_main = f'https://www.artstation.com/{_}'

        if '/artwork/' in self.url or '/projects/' in self.url:
            pass
        else:
            self.url = self.url_main
        self.print_(self.url)

        # 3849
        self.session = Session('chrome')

    @lazy
    def _id(self):
        _id = get_id(self.url, self.cw)
        return f'artstation_{_id}'

    @lazy
    @try_n(2)
    def name(self):
        html = downloader.read_html(self.url_main, session=self.session)
        soup = Soup(html)
        name = soup.find('meta', {'property': 'og:title'}).attrs['content']
        return clean_title(f'{name} ({self._id})')

    def read(self):
        self.title = self.name
        id_ = self._id.replace('artstation_', '', 1)
        if '/' in id_:
            id_ = id_.split('/')[0]

        if '/artwork/' in self.url or '/projects/' in self.url:
            id_art = get_id_art(self.url)
            imgs = get_imgs_page(id_art, self.session, cw=self.cw)
        else:
            imgs = get_imgs(id_, self.title, self.session, cw=self.cw)

        for img in imgs:
            self.urls.append(img.url)

        self.title = self.name


@try_n(2)
def get_imgs(id_, title, session, cw=None):
    print_ = get_print(cw)
    referer = f'https://www.artstation.com/{id_}'
    downloader.read_html(referer, session=session)
    #print(session.cookies.keys())

    url = f'https://www.artstation.com/users/{id_}/quick.json'
    j = downloader.read_json(url, referer, session=session)
    uid = j['id']
    aids = [a['id'] for a in j['albums_with_community_projects']]
    print_(f'albums: {aids}')

    datas = []
    ids = set()
    for aid in aids:
        p = 1
        while p < 1000:
            check_alive(cw)
            url = f'https://www.artstation.com/users/{id_}/projects.json?album_id={aid}&page={p}&user_id={uid}'
            print(url)
            _e = None
            for i in range(4):
                try:
                    j = downloader.read_json(url, referer, session=session)
                    break
                except Exception as e:
                    _e = e
                    print(e)
            else:
                if _e is not None:
                    raise _e

            data = j['data']
            if not data:
                break
            for d in data:
                if d['id'] not in ids:
                    ids.add(d['id'])
                    datas.append(d)
            if cw:
                cw.setTitle(f'{tr_("페이지 읽는 중...")}  {title} - {len(datas)}')
            else:
                print(len(datas))
            p += 1

    datas = sorted(datas, key=lambda data: int(data['id']), reverse=True)

    imgs = []
    i = 0
    names = set()
    while i < len(datas):
        check_alive(cw)
        data = datas[i]
        date = data['created_at'][2:10]
        post_url = data['permalink']
        #print('post_url', post_url)
        id_art = get_id_art(post_url)
        imgs += get_imgs_page(id_art, session, date=date, cw=cw, names=names)
        if cw:
            cw.setTitle(f'{tr_("이미지 읽는 중...")}  {title} - {i+1} / {len(datas)}  ({len(imgs)})')
        else:
            print(len(imgs))
        i += 1

    return imgs


def get_id_art(post_url):
    return post_url.split('/artwork/')[-1].split('/projects/')[-1].split('/')[0].split('?')[0].split('#')[0]


def get_id(url, cw=None):
    print_ = get_print(cw)

    url = url.split('?')[0].split('#')[0]

    if '/artwork/' in url:
        id_art = get_id_art(url)
        imgs = get_imgs_page(id_art, session=Session(), cw=cw)
        return imgs[0].data['user']['username']

    if '.artstation.' in url and 'www.artstation.' not in url:
        id_ = url.split('.artstation')[0].split('//')[-1]
        type_ = None
    elif 'artstation.com' in url:
        paths = url.split('artstation.com/')[1].split('/')
        id_ = paths[0]
        type_ = paths[1] if len(paths) > 1 else None
    else:
        id_ = url.replace('artstation_', '').replace('／', '/')
        type_ = None

    if type_ not in [None, 'likes']:
        type_ = None

    print_(f'type: {type_}, id: {id_}')

    if type_:
        return f'{id_}/{type_}'
    return id_


def get_imgs_page(id_art, session, date=None, cw=None, names=None):
    print_ = get_print(cw)
    url_json = f'https://www.artstation.com/projects/{id_art}.json'
    post_url = f'https://www.artstation.com/artwork/{id_art}'

    name = post_url.strip('/').split('/')[-1]
    if names is not None:
        while name.lower() in names:
            name += '_'
        names.add(name.lower())

    try:
        html = downloader.read_html(url_json, session=session, referer=post_url)
        data = json.loads(html)
        imgs_ = data['assets']
    except Exception as e:
        print_(print_error(e))
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
            print_(f'embed: {url_embed}')
            try:
                html = downloader.read_html(url_embed, session=session, referer=post_url)
                soup = Soup(html)
                v = soup.find('video')
                if v:
                    url = v.find('source').attrs['src']
            except Exception as e:
                print_(print_error(e))
            if not url:
                try:
                    url = soup.find('link', {'rel': 'canonical'}).attrs['href']
                    print_(f'YouTube: {url}')
                    raise Exception('YouTube')
##                    from extractor import youtube_downloader
##                    video = youtube_downloader.Video(url, cw=cw)
##                    video.data = data
                except Exception as e:
                    print(e)
                    url = None
        if not url:
            url = img['image_url']

        if video:
            img = video
        else:
            img = Image(post_url, date, url, page, name, data)

        imgs.append(img)

    return imgs

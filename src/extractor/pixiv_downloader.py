import downloader
from utils import Downloader, Session, urljoin, clean_title, LazyUrl, get_ext, get_print, try_n, compatstr, get_max_range, check_alive, query_url, get_outdir
import ffmpeg
import utils
import os
import ree as re
import errors
from translator import tr_
from error_printer import print_error
try:
    from urllib import quote, unquote # python2
except ImportError:
    from urllib.parse import quote, unquote # python3
import constants
from datetime import datetime
import requests
from timee import sleep
from collections import deque
from locker import lock
import threading
from ratelimit import limits, sleep_and_retry
##import asyncio
FORCE_LOGIN = True
LIMIT = 48
for header in ['pixiv_illust', 'pixiv_bmk', 'pixiv_search', 'pixiv_following', 'pixiv_following_r18']:
    if header not in constants.available_extra:
        constants.available_extra.append(header)



@Downloader.register
class Downloader_pixiv(Downloader):
    type = 'pixiv'
    MAX_CORE = 16
    keep_date = True
    STEP = 8, 32

    @classmethod
    def fix_url(cls, url):
        if url.startswith('illust_'):
            url = 'https://www.pixiv.net/en/artworks/{}'.format(url[len('illust_'):])
        elif url.startswith('bmk_'):
            url = 'https://www.pixiv.net/en/users/{}/bookmarks/artworks'.format(url[len('bmk_'):])
        elif url.startswith('search_'):
            url = 'https://www.pixiv.net/en/tags/{}/artworks'.format(quote(url[len('search_'):].replace('+', ' ')))
        elif url.startswith('following_r18_'):
            url = 'https://www.pixiv.net/bookmark_new_illust_r18.php'
        elif url.startswith('following_'):
            url = 'https://www.pixiv.net/bookmark_new_illust.php'
        elif not re.find(r'^https?://', url) and '.' not in url:
            url = 'https://www.pixiv.net/en/users/{}'.format(url)
            
        #3474
        url = re.sub(r'(users/[0-9]+)/artworks$', r'\1', url)
        
        url = re.sub(r'[?&]p=[0-9]+$', '', url)
        return url.strip('/')

    @classmethod
    def key_id(cls, url):
        return url.replace('://www.', '://').replace('/en/', '/')

    def read(self):
##        loop = asyncio.new_event_loop()
##        asyncio.set_event_loop(loop)
        try:
            info = get_info(self.url, self.cw)
            for img in info['imgs']:
                self.urls.append(img.url)
            self.title = clean_title(info['title'])
        finally:
##            loop.close()
            pass


class PixivAPIError(errors.LoginRequired): pass
class HTTPError(Exception): pass


class PixivAPI():

    def __init__(self):
        self.session = None#Session()

    def illust_id(self, url):
        return re.find('/artworks/([0-9]+)', url) or re.find('[?&]illust_id=([0-9]+)', url)

    def user_id(self, url):
        return re.find('/users/([0-9]+)', url) or re.find('[?&]id=([0-9]+)', url)

    @try_n(8)
    @sleep_and_retry
    @limits(30, 1) #3355
    def call(self, url):
        url = urljoin('https://www.pixiv.net/ajax/', url)
        e_ = None
        try:
            info = downloader.read_json(url, session=self.session)
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code in (403, 404):
                e_ = HTTPError('{} Client Error'.format(code))
            else:
                raise e
        if e_:
            raise e_
        err = info['error']
        if err:
            raise PixivAPIError(info.get('message'))
        return info['body']
    
    def illust(self, id_):
        return self.call('illust/{}'.format(id_))
        
    
    def pages(self, id_):
        return self.call('illust/{}/pages'.format(id_))
        
    
    def ugoira_meta(self, id_):
        return self.call('illust/{}/ugoira_meta'.format(id_))

    def user(self, id_):
        return self.call('user/{}'.format(id_))

    def profile(self, id_):
        return self.call('user/{}/profile/all?lang=en'.format(id_))

    def bookmarks(self, id_, offset=0, limit=None, rest='show'):
        if limit is None:
            limit = LIMIT
        return self.call('user/{}/illusts/bookmarks?tag=&offset={}&limit={}&rest={}&lang=en'.format(id_, offset, limit, rest))

    def search(self, q, order='date_d', mode='all', p=1, s_mode='s_tag_full', type_='all', scd=None, ecd=None, wlt=None, wgt=None, hlt=None, hgt=None, blt=None, bgt=None, ratio=None, tool=None):
        url = 'search/artworks/{0}?word={0}&order={1}&mode={2}&p={3}&s_mode={4}&type={5}&lang=en'.format(quote(q), order, mode, p, s_mode, type_)
        if scd:
            url += '&scd={}'.format(scd)
        if ecd:
            url += '&ecd={}'.format(ecd)
        if wlt:
            url += '&wlt={}'.format(wlt)
        if wgt:
            url += '&wgt={}'.format(wgt)
        if hlt:
            url += '&hlt={}'.format(hlt)
        if hgt:
            url += '&hgt={}'.format(hgt)
        if blt:
            url += '&blt={}'.format(blt)
        if bgt:
            url += '&bgt={}'.format(bgt)
        if ratio:
            url += '&ratio={}'.format(ratio)
        if tool:
            url += '&tool={}'.format(tool)
        return self.call(url)

    @try_n(8)
    def following(self, p, r18=False):
        url = 'https://www.pixiv.net/bookmark_new_illust_r18.php' if r18 else 'https://www.pixiv.net/bookmark_new_illust.php'
        if p > 1:
            url += '?p={}'.format(p)
        html = downloader.read_html(url, session=self.session)
        ids = []
        ids_set = set()
        for id_ in re.findall('([0-9]+)_p0_master1200', html):
            if id_ in ids_set:
                continue
            ids_set.add(id_)
            ids.append(id_)
        return ids


class Image():
    local = False
    def __init__(self, url, referer, id_, p, format_, info, cw, ugoira=None):
        self._url = url
        self.id_ = id_
        self.p = p
        self.format_ = format_
        self.artist = info['artist']
        self.artistid = info['artist_id'] #3636
        self.title = info['raw_title']
        self.utime = info['create_date']
        self.cw = cw
        self.ugoira = ugoira
        self.url = LazyUrl(referer, self.get, self, pp=self.pp, detect_local=not ugoira)

    def get(self, referer):
        ext = get_ext(self._url)
        d ={
            'id': self.id_,
            'page': self.p,
            'artist': self.artist,
            'artistid': self.artistid,
            'title': self.title,
            }
        name = utils.format(self.format_, d)
        self.filename = clean_title(name.strip(), allow_dot=True, n=-len(ext)) + ext
        if self.ugoira and self.ugoira['ext']: #3355
            filename_local = os.path.join(self.cw.dir, self.filename)
            filename_local = '{}{}'.format(os.path.splitext(filename_local)[0], self.ugoira['ext'])
            if os.path.exists(filename_local):
                self.filename = os.path.basename(filename_local)
                self.local = True
        return self._url

    def pp(self, filename):
        if self.ugoira and self.ugoira['ext'] and not self.local:
            with self.cw.convert(self):
                if utils.ui_setting:
                    dither = utils.ui_setting.checkDither.isChecked()
                    quality = utils.ui_setting.ugoira_quality.value()
                else:
                    dither = True
                    quality = 90
                filename_new = '{}{}'.format(os.path.splitext(filename)[0], self.ugoira['ext'])
                ffmpeg.gif(filename, filename_new, self.ugoira['delay'], dither=dither, quality=quality, cw=self.cw)
                utils.removeDirList.append((filename, False))
                return filename_new


def pretty_tag(tag):
    return tag.replace(' ', '').lower()


@lock
def tags_matched(tags_illust, tags_add, cw=None):
    print_ = get_print(cw)

    cache = cw.get_extra('pixiv_tag_cache') if cw else None
    init = True
    if cache is not None:
        init = False
        tags = set(cache['tags'])
        tags_ex = set(cache['tags_ex'])
    else:
        if utils.ui_setting and utils.ui_setting.groupBox_tag.isChecked():
            tags_ = [compatstr(utils.ui_setting.tagList.item(i).text()) for i in range(utils.ui_setting.tagList.count())]
        else:
            tags_ = []
        tags = set()
        tags_ex = set()
        for tag in tags_:
            tag = pretty_tag(tag)
            if tag.startswith('-'):
                tags_ex.add(tag[1:].strip())
            else:
                tags.add(tag)

    if init:
        if cw:
            cache = {}
            cache['tags'] = list(tags)
            cache['tags_ex'] = list(tags_ex)
            cw.set_extra('pixiv_tag_cache', cache)
        print_('tags: [{}]'.format(', '.join(tags)))
        print_('tags_ex: [{}]'.format(', '.join(tags_ex)))

    if tags_add:
        tags.update((pretty_tag(tag) for tag in tags_add))
        if init:
            print_('tags_add: {}'.format(tags_add))
    
    tags_illust = set(pretty_tag(tag) for tag in tags_illust)
    return (not tags or tags & tags_illust) and tags_ex.isdisjoint(tags_illust)


def get_info(url, cw=None, depth=0, tags_add=None):
    print_ = get_print(cw)
    api = PixivAPI()
    info = {}
    imgs = []
    
    ugoira_ext = [None, '.gif', '.webp', '.png'][utils.ui_setting.ugoira_convert.currentIndex()] if utils.ui_setting else None
    format_ = compatstr(utils.ui_setting.pixivFormat.currentText()) if utils.ui_setting else 'id_ppage'
            
    max_pid = get_max_range(cw)
    
    if api.illust_id(url): # Single post
        id_ = api.illust_id(url)
        data = api.illust(id_)
        login = 'noLoginData' not in data
        if FORCE_LOGIN and not login:#
            raise errors.LoginRequired()
        if data['xRestrict'] and not login:
            raise errors.LoginRequired('R-18')
        info['artist'] = data['userName']
        info['artist_id'] = data['userId']
        info['raw_title'] = data['illustTitle']
        info['title'] = '{} (pixiv_illust_{})'.format(info['raw_title'], id_)
        info['create_date'] = parse_time(data['createDate'])
        tags_illust = set(tag['tag'] for tag in data['tags']['tags'])
        
        if tags_matched(tags_illust, tags_add, cw):
            if data['illustType'] == 2: # ugoira
                data = api.ugoira_meta(id_)
                ugoira = {
                    'ext': ugoira_ext,
                    'delay': [frame['delay'] for frame in data['frames']],
                    }
                img = Image(data['originalSrc'], url, id_, 0, format_, info, cw, ugoira=ugoira)
                imgs.append(img)
            else:
                data = api.pages(id_)
                for img in data:
                    img = Image(img['urls']['original'], url, id_, len(imgs), format_, info, cw)
                    imgs.append(img)
        else:
            print('tags mismatched')
    elif '/bookmarks/' in url or 'bookmark.php' in url: # User bookmarks
        id_ = api.user_id(url)
        if id_ is None: #
            id_ = my_id()
        if id_ == my_id():
            rests = ['show', 'hide']
        else:
            rests = ['show']
        process_user(id_, info, api)
        info['title'] = '{} (pixiv_bmk_{})'.format(info['artist'], info['artist_id'])
        ids = []
        ids_set = set()
        for rest in rests:
            offset = 0
            while len(ids) < max_pid:
                data = api.bookmarks(id_, offset, rest=rest)
                c = 0
                for id in [work['id'] for work in data['works']]:
                    if id in ids_set:
                        continue
                    ids_set.add(id)
                    ids.append(id)
                    c += 1
                if not c:
                    break
                offset += LIMIT
                if depth == 0:
                    check_alive(cw)
        process_ids(ids, info, imgs, cw, depth)
    elif '/tags/' in url or 'search.php' in url: # Search
        q = unquote(re.find(r'/tags/([^/]+)', url) or re.find('[?&]word=([^&]*)', url, err='no tags'))
        info['title'] = '{} (pixiv_search_{})'.format(q, q.replace(' ', '+'))
        qs = query_url(url)
        order = qs.get('order', ['date_d'])[0]
        mode = qs.get('mode', ['all'])[0]
        s_mode = qs.get('s_mode', ['s_tag_full'])[0]
        scd = qs.get('scd', [None])[0]
        ecd = qs.get('ecd', [None])[0]
        type_ = qs.get('type', ['all'])[0]
        wlt = qs.get('wlt', [None])[0]
        wgt = qs.get('wgt', [None])[0]
        hlt = qs.get('hlt', [None])[0]
        hgt = qs.get('hgt', [None])[0]
        blt = qs.get('blt', [None])[0]
        bgt = qs.get('bgt', [None])[0]
        ratio = qs.get('ratio', [None])[0]
        tool = qs.get('tool', [None])[0]
        logs = [
            'order: {}'.format(order),
            'mode: {}'.format(mode),
            's_mode: {}'.format(s_mode),
            'scd / ecd: {} / {}'.format(scd, ecd),
            'type: {}'.format(type_),
            'wlt /  wgt: {} / {}'.format(wlt, wgt),
            'hlt / hgt: {} / {}'.format(hlt, hgt),
            'blt / bgt: {} / {}'.format(blt, bgt),
            'ratio: {}'.format(ratio),
            'tool: {}'.format(tool),
                ]
        print_('\n'.join(logs))
        ids = []
        ids_set = set()
        p = 1
        while len(ids) < max_pid:
            data = api.search(q, order, mode, p=p, s_mode=s_mode, scd=scd, ecd=ecd, type_=type_, wlt=wlt, wgt=wgt, hlt=hlt, hgt=hgt, blt=blt, bgt=bgt, ratio=ratio, tool=tool)
            c = 0
            for id in [illust['id'] for illust in data['illustManga']['data'] if 'id' in illust]:
                if id in ids_set:
                    continue
                ids_set.add(id)
                ids.append(id)
                c += 1
            if not c:
                break
            p += 1
        process_ids(ids, info, imgs, cw, depth)
    elif 'bookmark_new_illust.php' in url or 'bookmark_new_illust_r18.php' in url: # Newest works: Following
        r18 = 'bookmark_new_illust_r18.php' in url
        id_ = my_id()
        process_user(id_, info, api)
        info['title'] = '{} (pixiv_following_{}{})'.format(info['artist'], 'r18_' if r18 else '', info['artist_id'])
        ids = []
        ids_set = set()
        p = 1
        while len(ids) < max_pid:
            c = 0
            for id in api.following(p, r18=r18):
                if id in ids_set:
                    continue
                ids_set.add(id)
                ids.append(id)
                c += 1
            if not c:
                break
            p += 1
        process_ids(ids, info, imgs, cw, depth)
    elif api.user_id(url): # User illusts
        m = re.search(r'/users/[0-9]+/([\w]+)/?([^\?#/]*)', url)
        type_ = {'illustrations': 'illusts', 'manga': 'manga'}.get(m and m.groups()[0])
        if type_:
            types = [type_]
        else:
            types = ['illusts', 'manga']
        if m:
            tag = unquote(m.groups()[1]) or None
        else:
            tag = None
        print_('types: {}, tag: {}'.format(types, tag))
        
        id_ = api.user_id(url)
        process_user(id_, info, api)
        data = api.profile(id_)
        info['title'] = '{} (pixiv_{})'.format(info['artist'], info['artist_id'])
        
        ids = []
        for type_ in types:
            illusts = data[type_]
            if not illusts:
                continue
            ids += list(illusts.keys())
        ids = sorted(ids, key=int, reverse=True)
        if not ids:
            raise Exception('no imgs')
        process_ids(ids, info, imgs, cw, depth, tags_add=[tag] if tag else None)
    else:
        raise NotImplementedError()
    info['imgs'] = imgs[:max_pid]

    return info


def parse_time(ds):
    ds, z = ds[:-6], ds[-6:]
    dt = int(z[:3]) * 3600 + int(z[4:]) * 60
    time = datetime.strptime(ds.replace('  ', ' '), '%Y-%m-%dT%H:%M:%S')
    time = (time-datetime(1970,1,1)).total_seconds()
    return time - dt


def my_id():
    sid = Session().cookies.get('PHPSESSID', domain='.pixiv.net')
    if not sid:
        raise errors.LoginRequired()
    return re.find(r'^([0-9]+)', sid, err='no userid')


def process_user(id_, info, api):
    info['artist_id'] = id_
    data_user = api.user(id_)
    info['artist'] = data_user['name']


def process_ids(ids, info, imgs, cw, depth=0, tags_add=None):
    print_ = get_print(cw)
    max_pid = get_max_range(cw)
    class Thread(threading.Thread):
        alive = True
        rem = 0

        def __init__(self, queue):
            super().__init__(daemon=True)
            self.queue = queue

        @classmethod
        @lock
        def add_rem(cls, x):
            cls.rem += x
            
        def run(self):
            while self.alive:
                try:
                    id_, res, i = self.queue.popleft()
                except Exception as e:
                    sleep(.1)
                    continue
                try:
                    info_illust = get_info('https://www.pixiv.net/en/artworks/{}'.format(id_), cw, depth=depth+1, tags_add=tags_add)
                    res[i] = info_illust['imgs']
                except Exception as e:
                    if depth == 0 and (e.args and e.args[0] == '不明なエラーが発生しました' or type(e) == errors.LoginRequired): # logout during extraction
                        res[i] = e
                    print_('process_ids error (id: {}, d:{}):\n{}'.format(id_, depth, print_error(e)[0]))
                finally:
                    Thread.add_rem(-1)
    queue = deque()
    n, step = Downloader_pixiv.STEP
    print_('{} / {}'.format(n, step))
    ts = []
    for i in range(n):
        t = Thread(queue)
        t.start()
        ts.append(t)
    for i in range(0, len(ids), step):
        res = [[]]*step
        for j, id_illust in enumerate(ids[i:i+step]):
            queue.append((id_illust, res, j))
            Thread.add_rem(1)
        while Thread.rem:
            sleep(.001, cw)
        for imgs_ in res:
            if isinstance(imgs_, Exception):
                raise imgs_
            imgs += imgs_
        s = '{} {} - {}'.format(tr_('읽는 중...'), info['title'], len(imgs))
        if cw:
            cw.setTitle(s)
        else:
            print(s)
        if len(imgs) >= max_pid:
            break
        if depth == 0:
            check_alive(cw)
    for t in ts:
        t.alive = False

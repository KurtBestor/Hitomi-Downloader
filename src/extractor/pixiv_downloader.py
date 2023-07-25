import downloader
from utils import Downloader, Session, urljoin, clean_title, LazyUrl, get_ext, get_print, try_n, compatstr, get_max_range, check_alive, query_url, get_outdir, Soup
import ffmpeg
import utils
import os
import ree as re
import errors
from translator import tr_
from error_printer import print_error
from urllib.parse import quote, unquote
import constants
from datetime import datetime
import requests
from timee import sleep
from collections import deque
from locker import lock
import threading
from ratelimit import limits, sleep_and_retry
import clf2
from PIL import Image as Image_
##import asyncio
LIMIT = 48
for header in ['pixiv_illust', 'pixiv_bmk', 'pixiv_search', 'pixiv_following', 'pixiv_following_r18']:
    if header not in constants.available_extra:
        constants.available_extra.append(header)


class LoginRequired(errors.LoginRequired):
    def __init__(self, *args):
        super().__init__(*args, method='browser', url='https://accounts.pixiv.net/login', w=560, h=920)



class Downloader_pixiv(Downloader):
    type = 'pixiv'
    MAX_CORE = 4
    MAX_PARALLEL = 2
    keep_date = True
    STEP = 4, 16
    URLS = ['pixiv.me', 'pixiv.net']
    ACCEPT_COOKIES = [r'(.*\.)?pixiv\.(com|co|net|me)']

    def init(self):
        setattr(self.cw, 'sid?', None)
        res = clf2.solve(self.url, cw=self.cw)
        self.session = res['session'] #5105

        soup = Soup(res['html'])

        if soup.find('a', href=lambda h: h and '/login.php' in h):
            self.print_('yee')
            def f(html, browser=None):
                soup = Soup(html)
                for div in soup.findAll('div'):
                    if div.get('data-page-name') == 'LoginPage':
                        browser.show()
                        return False
                browser.hide()
                return True
            try:
                res = clf2.solve('https://accounts.pixiv.net/login', session=self.session, cw=self.cw, f=f, delay=3, w=560, h=920, timeout=120)
            except clf2.Timeout:
                raise LoginRequired()
            self.print_('yeee')
            res = clf2.solve(self.url, session=self.session, cw=self.cw)
            soup = Soup(res['html'])

        err = soup.find('p', class_='error-message')
        if err: #5223
            raise errors.Invalid('{}: {}'.format(err.text.strip(), self.url))

    @classmethod
    def fix_url(cls, url):
        rt = utils.query_url(url).get('return_to')
        if rt:
            url = urljoin(url, rt[0])

        if '/search_user.php?' in url:
            url = 'https://pixiv.me/{}'.format(utils.query_url(url).get('nick')[0])

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

        if '://' not in url: #6082
            url = 'https://' + url
        return url.strip('/')

    @classmethod
    def key_id(cls, url):
        return url.replace('://www.', '://').replace('/en/', '/').replace('http://', 'https://').lower()

    def read(self):
##        loop = asyncio.new_event_loop()
##        asyncio.set_event_loop(loop)
        try:
            info = get_info(self.url, self.session, self.cw)
            self.artist = info.get('artist') #4897
            for img in info['imgs']:
                if isinstance(img, str): # local
                    self.urls.append(img)
                    continue
                self.urls.append(img.url)
            self.title = clean_title(info['title'])
        finally:
##            loop.close()
            pass


class PixivAPIError(LoginRequired): pass
class HTTPError(Exception): pass


class PixivAPI:

    def __init__(self, session, cw):
        self.session = session
        hdr = {
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9,ko-KR;q=0.8,ko;q=0.7,ja;q=0.6',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Referer': 'https://www.pixiv.net/',
            'X-User-Id': my_id(session, cw),
            }
        self.session.headers.update(hdr)

    def illust_id(self, url):
        return re.find('/artworks/([0-9]+)', url) or re.find('[?&]illust_id=([0-9]+)', url)

    def user_id(self, url):
        return re.find('/users/([0-9]+)', url) or re.find('[?&]id=([0-9]+)', url)

    @try_n(8, sleep=5)
    @sleep_and_retry
    @limits(2, 3) #3355, #5105
    def call(self, url):
        #print('call:', url)
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

    def profile(self, id_):
        return self.call('user/{}/profile/all'.format(id_))

    def top(self, id_):
        return self.call('user/{}/profile/top'.format(id_))

    def bookmarks(self, id_, offset=0, limit=None, rest='show'):
        if limit is None:
            limit = LIMIT
        return self.call('user/{}/illusts/bookmarks?tag=&offset={}&limit={}&rest={}'.format(id_, offset, limit, rest))

    def search(self, q, order='date_d', mode='all', p=1, s_mode='s_tag_full', type_='all', scd=None, ecd=None, wlt=None, wgt=None, hlt=None, hgt=None, blt=None, bgt=None, ratio=None, tool=None):
        url = 'search/artworks/{0}?word={0}&order={1}&mode={2}&p={3}&s_mode={4}&type={5}'.format(quote(q), order, mode, p, s_mode, type_)
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

    def following(self, p, r18=False): #4077
        mode = 'r18' if r18 else 'all'
        url = f'follow_latest/illust?p={p}&mode={mode}'
        return self.call(url)



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
            if os.path.realpath(filename_local) in self.cw.names_old or os.path.exists(filename_local): #4534
                self.filename = os.path.basename(filename_local)
                self.local = True
        return self._url

    def pp(self, filename):
        if self.ugoira and self.ugoira['ext'] and not self.local:
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


def get_info(url, session, cw=None, depth=0, tags_add=None):
    print_ = get_print(cw)
    api = PixivAPI(session, cw)
    info = {}
    imgs = []

    ugoira_ext = [None, '.gif', '.webp', '.png'][utils.ui_setting.ugoira_convert.currentIndex()] if utils.ui_setting else None
    format_ = compatstr(utils.ui_setting.pixivFormat.currentText()) if utils.ui_setting else 'id_ppage'

    max_pid = get_max_range(cw)

    if api.illust_id(url): # Single post
        id_ = api.illust_id(url)
        data = api.illust(id_)
        login = 'noLoginData' not in data
        if not login:#
            raise LoginRequired()
        if data['xRestrict'] and not login:
            raise LoginRequired('R-18')
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
            id_ = my_id(session, cw)
        if id_ == my_id(session, cw):
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
        process_ids(ids, info, imgs, session, cw, depth)
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
        process_ids(ids, info, imgs, session, cw, depth)
    elif 'bookmark_new_illust.php' in url or 'bookmark_new_illust_r18.php' in url: # Newest works: Following
        r18 = 'bookmark_new_illust_r18.php' in url
        id_ = my_id(session, cw)
        process_user(id_, info, api)
        info['title'] = '{} (pixiv_following_{}{})'.format(info['artist'], 'r18_' if r18 else '', info['artist_id'])
        ids = []
        ids_set = set()
        p = 1
        while len(ids) < max_pid:
            data = api.following(p, r18=r18)
            c = 0
            for id in data['page']['ids']:
                if id in ids_set:
                    continue
                ids_set.add(id)
                ids.append(id)
                c += 1
            if not c:
                break
            p += 1
        process_ids(ids, info, imgs, session, cw, depth)
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
        print_(f'ids: {len(ids)}')
        if not ids:
            raise Exception('no imgs')
        process_ids(ids, info, imgs, session, cw, depth, tags_add=[tag] if tag else None)
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


@try_n(4, sleep=.5) #5469
def my_id(session, cw):
    print_ = get_print(cw)
    sid = session.cookies.get('PHPSESSID', domain='.pixiv.net', path='/')
    if not sid:
        raise LoginRequired()
    if cw is not None:
        _ = getattr(cw, 'sid?', None)
        if _ is None:
            setattr(cw, 'sid?', sid)
            print_(f'sid: {sid}')
    userid = re.find(r'^([0-9]+)', sid)
    if userid is None:
        raise LoginRequired()
    return userid


def process_user(id_, info, api):
    info['artist_id'] = id_
    data_user = api.top(id_)
    info['artist'] = data_user['extraData']['meta']['ogp']['title']


def process_ids(ids, info, imgs, session, cw, depth=0, tags_add=None):
    print_ = get_print(cw)
    max_pid = get_max_range(cw)

    names = cw.names_old
    table = {}
    for name in names:
        id = re.find(r'([0-9]+)_p[0-9]+.*\.(jpg|jpeg|png|apng|bmp|webp|gif)$', os.path.basename(name)) #5541
        if id is None:
            continue
        ext = os.path.splitext(name)[1]
        if ext.lower() in ['.gif', '.webp']: #5541
            try:
                img = Image_.open(name)
                n_frames = getattr(img, 'n_frames', 1)
            except Exception as e:
                print_(print_error(e))
                n_frames = 1
            if n_frames > 1:
                print_(f'ugoira: {name}')
                continue
        id = id[0]
        if id in table:
            table[id].append(name)
        else:
            table[id] = [name]

    c_old = 0

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
            nonlocal c_old
            while self.alive:
                try:
                    id_, res, i = self.queue.popleft()
                except Exception as e:
                    sleep(.1)
                    continue
                try:
                    names = table.get(str(id_))
                    if names is not None:
                        res[i] = utils.natural_sort(names)
                        c_old += 1
                    else:
                        info_illust = get_info('https://www.pixiv.net/en/artworks/{}'.format(id_), session, cw, depth=depth+1, tags_add=tags_add)
                        res[i] = info_illust['imgs']
                except Exception as e:
                    if depth == 0 and (e.args and e.args[0] == '不明なエラーが発生しました' or type(e) == errors.LoginRequired): # logout during extraction
                        res[i] = e
                    print_('process_ids error (id: {}, d:{}):\n{}'.format(id_, depth, print_error(e)))
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
            sleep(.01, cw)
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

    print_(f'c_old: {c_old}')

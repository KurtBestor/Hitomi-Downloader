#coding:utf8
from __future__ import division, print_function, unicode_literals
import requests
from pixivpy_async.sync import *
import downloader
from random import shuffle, random
from timee import sleep
from error_printer import print_error
from utils import Downloader, query_url, get_max_range, clean_url, get_outdir, get_print, compatstr, clean_title, LazyUrl
from translator import tr_
import os
import ffmpeg
import constants
import ree as re
import asyncio
from datetime import datetime
try:
    from urllib import unquote # python2
except ImportError:
    from urllib.parse import unquote # python3
import pixiv_auth
N_TRY = 12
SLEEP = 60
print_ = None
headers = {
    'user': 'pixiv_',
    'illust': 'pixiv_illust_',
    'bookmark': 'pixiv_bmk_',
    'search': 'pixiv_search_',
    'following': 'pixiv_following_',
    }


class PixivError(Exception):

    def __init__(self, *args):
        self.api = pixiv_auth.get_api(force=True)
        super(PixivError, self).__init__(*args)


@Downloader.register
class Downloader_pixiv(Downloader):
    type = 'pixiv'
    MAX_CORE = 16
    info = None
    _id = None
    keep_date = True
    atts = ['_format', '_format_name', 'imgs']

    def init(self):
        asyncio.set_event_loop(asyncio.new_event_loop())###
        self.url = clean_url(self.url)
        url = self.url

        # Determine the type
        if 'bookmark.php?type=user' in url or headers['following'] in url:
            type = 'following'
        elif 'bookmark.php' in url or headers['bookmark'] in url or '/bookmarks/' in url:
            type = 'bookmark'
        elif 'illust_id=' in url or headers['illust'] in url or '/artworks/' in url:
            type = 'illust'
        elif 'search.php' in url or headers['search'] in url:
            type = 'search'
            order = query_url(url).get('order', ['date_d'])[0] # data_d, date, popular_d, popular_male_d, popular_female_d
            scd = query_url(url).get('scd', [None])[0] # 2019-09-27
            ecd = query_url(url).get('ecd', [None])[0] # 2019-09-28
            blt = query_url(url).get('blt', [None])[0] # 5000
            bgt = query_url(url).get('bgt', [None])[0] # 9999
            type_ = query_url(url).get('type', [None])[0] # None (all), illust, manga, ugoira
            self.info = {'order': order, 
               'scd': scd, 
               'ecd': ecd, 
               'blt': blt, 
               'bgt': bgt, 
               'type': type_}
        elif '/tags/' in url:
            type = 'search'
            order = query_url(url).get('order', ['date_d'])[0]
            scd = query_url(url).get('scd', [None])[0]
            ecd = query_url(url).get('ecd', [None])[0]
            blt = query_url(url).get('blt', [None])[0]
            bgt = query_url(url).get('bgt', [None])[0]
            type_ = query_url(url).get('type', [None])[0] # None (all), illust, manga, ugoira
            if type_ is None:
                try:
                    type_ = url.split('/tags/')[1].split('/')[1]
                except IndexError:
                    type_ = None
                type_ = {'illustrations': 'illust'}.get(type_, type_)
            self.info = {'order': order, 
               'scd': scd, 
               'ecd': ecd, 
               'blt': blt, 
               'bgt': bgt, 
               'type': type_}
        elif 'id=' in url and 'mode=' not in url or headers['user'] in url or 'pixiv.me' in url or '/users/' in url:
            type = 'user'
        else:
            self.Invalid((u'[pixiv] Can not determine type: {}').format(url))
            return 'stop'
        header = headers[type]
        if 'pixiv.net' in url or 'pixiv.me' in url:
            if not url.startswith('http://') and not url.startswith('https://'):
                url = u'https://' + url
            self.url = url
        else:
            url = url.replace('bmk_', '').replace('illust_', '').replace('pixiv_', '').replace('search_', '')
            if type == 'user':
                url = 'https://www.pixiv.net/member_illust.php?id={}'.format(url)
            elif type == 'bookmark':
                url = 'https://www.pixiv.net/bookmark.php?id={}'.format(url)
            elif type == 'illust':
                url = 'https://www.pixiv.net/member_illust.php?mode=medium&illust_id={}'.format(url)
            elif type == 'search':
                url = 'https://www.pixiv.net/search.php?s_mode=s_tag&word={}'.format(url)
                url = clean_url(url)
            else:
                self.Invalid('{}{}: ???'.format(header, url))
                return 'stop'
            self.url = url
        self.print_('PIXIV_TYPE: {}'.format(type))
        self.pixiv_type = type
        try:
            self.api = pixiv_auth.get_api()
            if 'error' in self.api.user_detail(11):
                self.api = pixiv_auth.get_api(force=True)
        except Exception as e:
            self.print_(print_error(e)[0])
            self.Invalid(tr_('로그인 실패: {}{}\n[옵션 - 설정 - 픽시브 설정 - 로그인] 에서 설정해주세요.').format(header, url))
            return 'stop'

    @property
    def id(self):
        if self._id is None:
            id = get_id(self.url, d=self)
            self._id = id
        return self._id

    @classmethod
    def key_id(cls, url): #2302
        return get_id(url, False)

    def get_types(self):
        return set() # legacy; #2653
        types = set()
        for t in query_url(self.url).get('type', []):
            t = t.lower()
            types.add(t)
        return types

    def read(self):
        type = self.pixiv_type
        cw = self.customWidget
        print_ = cw.print_
        ui_setting = self.ui_setting

        if type == 'following':
            raise NotImplementedError('following')
        
        self._format = [None, 'gif', 'webp', 'png'][ui_setting.ugoira_convert.currentIndex()]
        self._format_name = compatstr(ui_setting.pixivFormat.currentText())
        types = self.get_types()
        if types:
            s = ', '.join(sorted(types))
        else:
            s = 'all'
            types = None
        print_((u'Type: {}').format(s))
        print_((u'info: {}').format(self.info))
        api = self.api
        query = self.id.replace('_bmk', '').replace('_illust', '').replace('pixiv_', '').replace('search_', '')
        if type != 'search':
            query = int(query)
        print('pixiv_query:', query)
        try:
            if type in ('user', 'bookmark', 'search'):
                max_pid = get_max_range(cw, 2000)
                if ui_setting.groupBox_tag.isChecked():
                    tags = [ compatstr(ui_setting.tagList.item(i).text()) for i in range(ui_setting.tagList.count()) ]
                else:
                    tags = []
                if type == 'search':
                    query = query.replace('+', ' ')
                    name = query
                else:
                    id = self.id.replace('_bmk', '').replace('pixiv_', '').replace('search_', '')
                    print('name', id)
                    name = get_name(id, self.api, cw=cw)
                    self.artist = name
                title = u'{} ({})'.format(name, self.id)
                print_(title)
                dir = os.path.join(get_outdir('pixiv'), clean_title(title))
                imgs = get_imgs(query, type=type, api=api, n=max_pid, tags=tags, types=types, format=self._format, format_name=self._format_name, dir=dir, cw=cw, title=title, info=self.info)
            elif type == 'illust':
                for try_ in range(N_TRY):
                    try:
                        detail = api.illust_detail(query, req_auth=True)
                        error = detail.get('error')
                        if error:
                            raise PixivError(error)
                        break
                    except PixivError as e:
                        api = e.api
                        print_(e)
                        if try_ < N_TRY - 1:
                            print_('retry...')
                        sleep(SLEEP)
                else:
                    raise

                illust = detail.illust
                name = illust.title
                title = (u'{} ({})').format(name, self.id)
                dir = os.path.join(get_outdir('pixiv'), clean_title(title))
                imgs = get_imgs_from_illust(illust, api=api, format=self._format, dir=dir, cw=cw, format_name=self._format_name)
        except PixivError as e:
            msg = (u'PixivError: {}').format(e.message)
            return self.Invalid(msg)

        self.imgs = []
        for img in imgs:
            d = {'type': img.type, 'url': img.url()}
            if img.type == 'ugoira':
                d['filename'] = img.filename
                d['frames'] = img.ugoira_data.frames
            self.imgs.append(d)
        for img in imgs:
            self.urls.append(img.url)

        self.title = clean_title(title) # 1390

    def post_processing(self):
        cw = self.customWidget
        ui_setting = self.ui_setting
        format = self._format
        if cw is not None and format is not None:
            try:
                dither = ui_setting.checkDither.isChecked()
                quality = ui_setting.ugoira_quality.value()
            except Exception as e:
                print(e)
                dither = True
                quality = 90

            imgs_ugoira = []
            for img in self.imgs:
##                if img.url not in cw.urls:
##                    continue
                if img['type'] == 'ugoira':
                    if os.path.splitext(img['url'])[1].lower() == '.zip':
                        imgs_ugoira.append(img)

            for j, img in enumerate(imgs_ugoira):
                if not cw.valid or not cw.alive:
                    return
                self.exec_queue.put((cw, (u'customWidget.pbar.setFormat(u"[%v/%m]  {} [{}/{}]")').format(tr_(u'움짤 변환...'), j, len(imgs_ugoira))))
                filename = os.path.join(self.dir, img['filename'])
                out = os.path.splitext(filename)[0] + '.' + format
                cw.print_((u'convert ugoira: {} --> {}').format(filename, out))
                try:
                    duration = [ frame.delay for frame in img['frames'] ]
                    self.print_((u'Duration: {}').format(duration))
                    ffmpeg.gif(filename, out, duration=duration, dither=dither, quality=quality, cw=cw)
                except Exception as e:
                    self.print_(print_error(e)[0])
                    continue
                if not cw.valid or not cw.alive:
                    return
                try:
                    self.removeDirList.append((filename, False))
                    cw.dones.add(out)
                    i = self.imgs.index(img)
                    cw.setNameAt(i, out)
                    if i == 0:
                        cw.setIcon(out)
                except Exception as e:
                    return self.Invalid(e=e)

            self.exec_queue.put((cw, u'customWidget.pbar.setFormat("[%v/%m]")'))


def get_time(illust):
    ds = illust.create_date
    ds, z = ds[:-6], ds[-6:]
    dt = int(z[:3]) * 3600 + int(z[4:]) * 60
    time = datetime.strptime(ds.replace('  ', ' '), '%Y-%m-%dT%H:%M:%S')
    time = (time-datetime(1970,1,1)).total_seconds()
    return time - dt


class Img(object):

    def __init__(self, illust, url, ugoira_data=None, format_name=None):
        self.illust = illust
        self.id = illust.id
        self.type = illust.type
        self.title = illust.title
        self.artist = illust.user.name
        self.url = LazyUrl('https://app-api.pixiv.net/', lambda _: url, self)
        ps = re.findall('_p([0-9]+)', url)
        p = ps[(-1)] if ps else 0
        self.p = p
        self.ext = os.path.splitext(url.split('?')[0].split('#')[0])[1]
        if self.type == 'ugoira':
            self.ugoira_data = ugoira_data
        if format_name:
            name = format_name.replace('id', '###id*').replace('page', '###page*').replace('artist', '###artist*').replace('title', '###title*')
            name = name.replace('###id*', str(self.id)).replace('###page*', str(self.p)).replace('###artist*', self.artist).replace('###title*', self.title)
            self.filename = clean_title(name.strip(), allow_dot=True, n=-len(self.ext)) + self.ext
        else:
            self.filename = os.path.basename(url.split('?')[0].split('#')[0])
        self.utime = get_time(illust)


def get_imgs(user_id, type='user', n=None, api=None, tags=[], types={'illust', 'manga', 'ugoira'}, format=None, format_name=None, dir='', cw=None, title=None, info=None):
    print('get_imgs', user_id, type, dir)
    if api is None:
        api = pixiv_auth.get_api()
    print_ = get_print(cw)
    imgs = []
    offset = 0
    bad = 0
    error = None
    tags_ = tags
    tags = set()
    tags_ex = set()
    for tag in tags_:
        tag = tag.strip().replace(' ', '').lower()
        if tag.startswith('-'):
            tags_ex.add(tag[1:].strip())
        else:
            tags.add(tag)

    print_((u'tags: [{}]').format((u', ').join(tags)))
    print_((u'tags_ex: [{}]').format((u', ').join(tags_ex)))
    max_id = None
    while True:
        if bad >= N_TRY:
            raise PixivError(error)
        if type == 'user':
            json_result = api.user_illusts(user_id, type=None, req_auth=True, filter=None, offset=offset)
        elif type == 'search':
            order = info['order']
            sorts = {
                'date_d': 'date_desc',
                'date': 'date_asc',
                'popular_d': 'popular_desc',
                'popular': 'popular_asc',
                'popular_female_d': 'popular_female_desc',
                'popular_female': 'popular_female_asc',
                'popular_male_d': 'popular_male_desc',
                'popular_male': 'popular_male_asc',
                }
            sort = sorts.get(order, 'date_desc')
            params = {'word': user_id, 
               'search_target': 'partial_match_for_tags', 
               'sort': sort, 
               'filter': 'for_ios'}
            if offset:
                params['offset'] = offset
            if info.get('blt') is not None:
                params['bookmark_num_min'] = info['blt']
            if info.get('bgt') is not None:
                params['bookmark_num_max'] = info['bgt']
            if info.get('scd') is not None:
                params['start_date'] = info['scd']
            if info.get('ecd') is not None:
                params['end_date'] = info['ecd']
            print(params)
            #r = api.no_auth_requests_call('GET', '%s/v1/search/illust' % api.hosts, params=params, req_auth=True)
            #json_result = api.parse_result(r)
            method, url = api.api.search_illust
            r = api.requests_(method, url, params=params, auth=True)
            json_result = api.parse_json(r)
        elif type == 'bookmark':
            print('max_id:', max_id)
            json_result = api.user_bookmarks_illust(user_id, filter=None, max_bookmark_id=max_id, req_auth=True)
        else:
            raise Exception(('type "{}" is not supported').format(type))
        error = json_result.get('error')
        if error:
            print_(error)
            message = error.get('message', '')
            if 'Offset must be no more than' in message:
                break
            print_('retry...')
            sleep(SLEEP)
            bad += 1
            continue
        bad = 0
        illusts = json_result.illusts
        if len(illusts) == 0:
            break
        for p, illust in enumerate(illusts):
            print('illust: {}'.format(illust.id))
            tags_illust = set(tag['name'].strip().replace(' ', '').lower() for tag in illust.tags)
            if not tags or tags & tags_illust:
                if tags_ex.isdisjoint(tags_illust):
                    imgs += get_imgs_from_illust(illust, api=api, types=types, format=format, format_name=format_name, dir=dir, cw=cw)
            if cw is not None and (illust.type == 'ugoira' or p == len(illusts) - 1):
                cw.setTitle((u'{} {} ({})').format(tr_(u'\uc77d\ub294 \uc911...'), title, len(imgs)))
            offset += 1
            if n is not None and len(imgs) >= n:
                break

        if type == 'bookmark':
            if json_result.next_url is None:
                break
            else:
                max_id = api.parse_qs(json_result.next_url)['max_bookmark_id']
        if n is not None and len(imgs) >= n:
            break
        if cw is not None and not cw.alive:
            break

    if not imgs:
        raise Exception('no imgs')
    return imgs[:n]


def get_id(url, dynamic=True, d=None):
    for header in headers.values():
        if url.startswith(header):
            return url
    if dynamic:
        api = pixiv_auth.get_api()
    else:
        api = None
    if 'search.php' in url or '/tags/' in url:
        if 'word=' in url:
            word = re.find('[?&]word=([^&]*)', url)
        else:
            word = url.split('/tags/')[1].split('/')[0]
        word = unquote(word).replace(' ', '+')
        return 'pixiv_search_' + word
    if 'pixiv.me' in url:
        if not dynamic:
            raise Exception('not dynamic')
        html = downloader.read_html(url)
        if 'member.php?id=' in html:
            id = int(html.split('member.php?id=')[1].split('"')[0])
        elif re.find('/users/([0-9]+)', html):
            id = re.find('/users/([0-9]+)', html)
        else:
            raise Exception('User not found')
        return u'pixiv_{}'.format(id)
    if 'member_illust.php?id=' in url or 'member.php?id=' in url or '/users/' in url:
        header = u'pixiv_'
        id = re.find('[?&]id=([0-9]+)', url) or re.find('/users/([0-9]+)', url)
    elif 'illust_id=' in url:
        header = u'pixiv_illust_'
        id = re.find('[?&]illust_id=([0-9]+)', url)
    elif '/artworks/' in url:
        header = u'pixiv_illust_'
        id = re.find('/artworks/([0-9]+)', url)
    elif 'bookmark.php' in url or '/bookmarks/' in url:
        header = u'pixiv_bmk_'
        id = re.find('[?&]id=([0-9]+)', url) or re.find('([0-9]+)/bookmarks/', url)
        if id is None:
            id = api.user_id
            if d:
                d.url = 'https://www.pixiv.net/bookmark.php?id={}'.format(id)
    else:
        raise Exception(u'????: {}'.format(url))
    return '{}{}'.format(header, id)
    

def get_imgs_from_illust(illust, api=None, types={'illust', 'manga', 'ugoira'}, format=None, format_name=None, dir='', print_=None, cw=None):
    print('get_imgs_from_illust', api, types, format, format_name, dir)
    print_ = get_print(cw)
    if api is None:
        api = pixiv_auth.get_api()
    if types is not None and illust.get('type', 'illust') not in types:
        return []
    imgs = []
    if illust.type == 'ugoira':
        sleep(0.2)
        for try_ in range(N_TRY):
            print_(('read ugoira... {}').format(illust.id))
            try:
                ugoira_data = api.ugoira_metadata(illust.id, req_auth=True)
                error = ugoira_data.get('error')
                if error:
                    raise PixivError(error)
                break
            except PixivError as e:
                api = e.api
                print_(e)
                msg = error.get('user_message', '')
                if u'公開制限エラー' in msg:
                    print_('invalid ugoira; ignore')
                    return []
                if u'該当作品の公開レベルにより閲覧できません' in msg:
                    print_('invalid ugoira (2); ignore')
                    return []
                if try_ < N_TRY - 1:
                    print_('retry...')
                sleep(SLEEP)
        else:
            raise

        ugoira_data = ugoira_data.ugoira_metadata
        url = ugoira_data.zip_urls.medium.replace('600x600', '1920x1080')
        img = Img(illust, url, ugoira_data=ugoira_data, format_name=format_name)
        if format is not None:
            filename = os.path.join(dir, img.filename)
            filename = os.path.splitext(filename)[0] + '.' + format
            filename_old = os.path.join(dir, ('{}_ugoira1920x1080.{}').format(img.id, format))
            if os.path.isfile(filename_old) and not os.path.isfile(filename):
                print_((u'rename: {} -> {}').format(os.path.basename(filename), os.path.basename(filename)))
                os.rename(filename_old, filename)
            if os.path.isfile(filename):
                print_((u'skip ugoira: {}').format(filename))
                img = Img(illust, filename, ugoira_data=ugoira_data, format_name=format_name)
        imgs.append(img)
    elif illust.page_count == 1:
        img = Img(illust, illust.meta_single_page.original_image_url, format_name=format_name)
        imgs.append(img)
    else:
        pages = illust.meta_pages
        for page in pages:
            img = Img(illust, page.image_urls.original, format_name=format_name)
            imgs.append(img)

    return imgs


def get_name(user_id, api=None, cw=None):
    print_ = get_print(cw)
    
    for try_ in range(N_TRY): # 1450
        try:
            info = api.user_detail(user_id)
            error = info.get('error')
            if error:
                if u'存在しない作品IDです' in error['user_message']:
                    raise Exception(u'ID does not exist')
                raise PixivError(error)
            break
        except PixivError as e:
            api = e.api
            print_(e)
            if try_ < N_TRY - 1:
                print_('retry...')
            sleep(SLEEP)
    else:
        raise
    
    name = info.user.name
    name = clean_title(name)
    return name


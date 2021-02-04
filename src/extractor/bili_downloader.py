# uncompyle6 version 3.5.0
# Python bytecode 2.7 (62211)
# Decompiled from: Python 2.7.16 (v2.7.16:413a49145e, Mar  4 2019, 01:30:55) [MSC v.1500 32 bit (Intel)]
# Embedded file name: bili_downloader2.pyo
# Compiled at: 2019-10-07 03:49:44
import downloader
from utils import Soup, LazyUrl, Downloader, query_url, get_outdir, get_print, cut_pair, format_filename, clean_title, get_resolution, try_n
import hashlib, json
import os
from io import BytesIO
import ffmpeg
from translator import tr_
import math
import ree as re
import utils
from collections import OrderedDict
_VALID_URL = 'https?://(?:www\\.|bangumi\\.|)bilibili\\.(?:tv|com)/(?:video/av|anime/(?P<anime_id>\\d+)/play#)(?P<id>\\d+)'
_APP_KEY = 'iVGUTjsxvpLeuDCf'
_BILIBILI_KEY = 'aHRmhWMLkdeMuILqORnYZocwMBpMEOdt'
RESOLS = OrderedDict()
RESOLS[116] = '1080p 60'
RESOLS[80] = '1080p'
RESOLS[64] = '720p'
RESOLS[32] = '480p'
RESOLS[16] = '360p'
    

class Video(object):

    def __init__(self, url, referer, id, p):
        ext = os.path.splitext(url.split('?')[0])[1]
        self.filename = (u'{}_{}{}').format(id, p, ext)

        def f(_):
            return url

        self.url = LazyUrl(referer, f, self)


# 1804
@try_n(2)
def fix_url(url, cw=None):
    print_ = get_print(cw)
    if '?' in url:
        tail = url.split('?')[1]
    else:
        tail = None
    html = downloader.read_html(url, methods={'requests'})
    soup = Soup(html)
    meta = soup.find('meta', {'itemprop': 'url'})
    if meta:
        url_new = meta.attrs['content']
        if tail:
            url_new = u'{}?{}'.format(url_new, tail)
        print_(u'redirect: {} -> {}'.format(url, url_new))
    else:
        url_new = url
        print_(u'no redirect')
    return url_new


@Downloader.register
class Downloader_bili(Downloader):
    type = 'bili'
    URLS = ['bilibili.com', 'bilibili.tv']
    lock = True
    detect_removed = False
    display_name = 'bilibili'

    def init(self):
        self.url = fix_url(self.url, self.cw)
        if 'bilibili.com' not in self.url.lower():
            self.url = 'https://www.bilibili.com/video/{}'.format(self.url)
        self.url = self.url.replace('m.bilibili', 'bilibili')

    @property
    def id_(self):
        mobj = re.match(_VALID_URL, self.url)
        video_id = mobj.group('id')
        anime_id = mobj.group('anime_id')
        return video_id

    def read(self):
        page = get_page(self.url)
        videos, info = get_videos(self.url, self.cw)
        if not videos:
            raise Exception('No videos')
        for video in videos:
            self.urls.append(video.url)

        thumb = BytesIO()
        downloader.download(info['url_thumb'], buffer=thumb)
        self.setIcon(thumb)
        title = info['title']
        if page is not None:
            title += (u'_p{}').format(page)
        title = format_filename(title, self.id_, '.mp4')[:-4]
        n = int(math.ceil(8.0 / len(videos)))
        self.print_(('n_threads: {}').format(n))
        self.enableSegment(n_threads=n)
        self.title = title

    def post_processing(self):
        cw = self.cw
        with cw.convert(self):
            outdir = get_outdir(self.type)
            out = os.path.join(outdir, self.title + '.mp4')
            ffmpeg.join(cw.names, out, cw)
            utils.remove(self.dir)
            self.single = True
            cw.setNameAt(0, out)
            del cw.imgs[1:]
            cw.dones.add(os.path.realpath(out))
            cw.dir = outdir


def get_page(url):
    qs = query_url(url)
    page = qs.get('p')
    if page:
        page = int(page[0])
    else:
        page = re.findall('_p([0-9]+)', url)
        if page:
            page = int(page[0])
        else:
            page = None
    if page == 1:
        page = None
    return page


def int_or_none(s):
    try:
        return int(s)
    except:
        return

    return


def float_or_none(s, default=None):
    try:
        return float(s)
    except:
        return default


def get_resolution_(quality):
    return RESOLS[quality]


def get_videos(url, cw=None, depth=0):
    print_ = get_print(cw)
    res = get_resolution()
    
    mobj = re.match(_VALID_URL, url)
    video_id = mobj.group('id')
    anime_id = mobj.group('anime_id')
    print(video_id, anime_id)
    print_ = get_print(cw)
    html = downloader.read_html(url, methods={'requests'})
    soup = Soup(html)
    title = soup.find('h1').attrs['title'].strip()
    url_thumb = soup.find('meta', {'property': 'og:image'}).attrs['content']
    p = get_page(url)
    if p is None:
        p = 1
    print('page:', p)
    if p > 1:
        pages = get_pages(html)
        cid = pages[(p - 1)]['cid']
    else:
        cid = re.findall('\\bcid(?:["\\\']:|=)(\\d+)', html)[0]
    print_('cid: {}'.format(cid))
    headers = {'Referer': url}
    entries = []
    
    RENDITIONS = ['qn={}&quality={}&type='.format(qlt, qlt) for qlt in RESOLS.keys()]# + ['quality=2&type=mp4']
    
    for num, rendition in enumerate(RENDITIONS, start=1):
        print('####', num, rendition)
        payload = 'appkey=%s&cid=%s&otype=json&%s' % (_APP_KEY, cid, rendition)
        sign = hashlib.md5((payload + _BILIBILI_KEY).encode('utf-8')).hexdigest()
        url_json = 'http://interface.bilibili.com/v2/playurl?%s&sign=%s' % (payload, sign)
        s_json = downloader.read_html(url_json)
        print(s_json[:1000])
        video_info = json.loads(s_json)
        if not video_info:
            continue
        if 'durl' not in video_info:
            print('#### error', num)
            if num < len(RENDITIONS):
                continue
            msg = video_info.get('message')
            if msg:
                raise Exception(msg)
        quality = video_info['quality']
        resolution = get_resolution_(quality)
        s = (u'resolution: {}').format(resolution)
        print_(s)

        # 2184
        if int(re.find('([0-9]+)p', resolution)) > res:
            print_('skip resolution')
            continue
        
        for idx, durl in enumerate(video_info['durl']):
            # 1343
            if idx == 0:
                size = downloader.get_size(durl['url'], referer=url)
                if size < 1024 * 1024 and depth == 0:
                    print_('size is too small')
                    return get_videos(url, cw, depth+1)
            
            formats = [
             {'url': durl['url'], 
                'filesize': int_or_none(durl['size'])}]
            for backup_url in durl.get('backup_url', []):
                formats.append({'url': backup_url, 
                   'preference': -2 if 'hd.mp4' in backup_url else -3})

            for a_format in formats:
                a_format.setdefault('http_headers', {}).update({'Referer': url})

            entries.append({'id': '%s_part%s' % (video_id, idx), 
               'duration': float_or_none(durl.get('length'), 1000), 
               'formats': formats})

        break

    videos = []
    for entry in entries:
        url_video = entry['formats'][0]['url']
        video = Video(url_video, url, video_id, len(videos))
        videos.append(video)

    info = {'title': clean_title(title), 
       'url_thumb': url_thumb}
    return (
     videos, info)


def get_pages(html):
    s = re.find(r'__INITIAL_STATE__=(.+)', html)
    data_raw = cut_pair(s)
    data = json.loads(data_raw)
    pages = data['videoData']['pages']
    return pages


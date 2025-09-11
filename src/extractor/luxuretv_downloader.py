# luxuretv_downloader.py
# LuxureTV Downloader plugin for Hitomi Downloader
# Created with ChatGPT help
# This is just a beta version!
# If you can improve it in any way, feel free to do so!
# Note: I'm not sure how much download load their servers can be, 
# and we don't want them to add additional protection that would prevent downloads.
# In my opinion, if we want to download a large number of videos at once, 
# it's safest to set the "Maximum concurrent tasks" and "Maximum connections per task" values ​​to a maximum of 1, maybe 2.
# That will be enough. Let's respect their servers ;)

import downloader
import re
from io import BytesIO
import ytdl

from utils import (
    Downloader,
    Session,
    LazyUrl,
    get_print,
    get_ext,
    try_n,
    format_filename,
    clean_title,
    get_resolution
)


class Downloader_luxuretv(Downloader):
    type = 'luxuretv'
    __name = r'([^/]*\.)?(luxuretv)([0-9]*)'
    URLS = [rf'regex:{__name}\.[a-z0-9]+/videos/']
    single = True
    display_name = 'LuxureTV'
    ACCEPT_COOKIES = __name

    def init(self):
        self.session = Session('chrome')

    @classmethod
    def fix_url(cls, url):
        return url.rstrip('/')

    @classmethod
    def key_id(cls, url):
        return re.sub(cls.__name + r'\.[^/]+', 'domain', url, 1).replace('http://', 'https://')

    def read(self):
        cw = self.cw
        self.enableSegment(1024 * 1024 // 2)
        thumb = BytesIO()

        video = Video(self.url, session=self.session, page_url=self.url, cw=cw)
        video.url()

        self.urls.append(video.url)
        self.title = video.title

        thumb_url = video.info.get('thumbnail') if getattr(video, 'info', None) else None
        if thumb_url:
            try:
                downloader.download(thumb_url, buffer=thumb, session=self.session)
                self.setIcon(thumb)
            except Exception:
                pass


class Video:
    _url = None

    def __init__(self, url, session=None, page_url=None, cw=None):
        self.page_url = page_url or url
        self.session = session or Session('chrome')
        self.cw = cw
        self.url = LazyUrl(url, self.get, self)

    @try_n(2)
    def get(self, url):
        """
        Zwraca (download_url, referer)
        oraz ustawia: self._url, self._referer, self.filename, self.title, self.info
        """
        if self._url is not None:
            return self._url, getattr(self, '_referer', self.page_url)

        info = get_info(self.page_url, session=self.session, cw=self.cw)

        title = info.get('title') or 'luxuretv'
        vid_id = info.get('id') or ''
        formats = info.get('formats') or []

        if not formats:
            raise Exception('No video formats found on page or via ytdl')

        try:
            res = max(get_resolution(), min((f.get('height') or 0) for f in formats))
            formats = [f for f in formats if (f.get('height') or 0) <= res]
        except Exception:
            pass

        video_best = formats[-1]
        self._url = video_best['url']
        ext = get_ext(self._url) or '.mp4'
        self.filename = format_filename(title, vid_id, ext)
        self.title = title
        if isinstance(self._url, str) and 'referer=force' in self._url.lower():
            self._referer = self._url
        else:
            self._referer = self.page_url

        self.info = info

        return self._url, self._referer


def get_info(page_url, session=None, cw=None):
    """
    Parsuje stronę i (ew. przez ytdl) zwraca:
    {
      'title': str,
      'id': str,
      'thumbnail': str,
      'formats': [ {'url': str, 'height': int}, ... ]
    }
    """
    session = session or Session('chrome')
    print_ = get_print(cw)
    info = {}

    try:
        soup = downloader.read_soup(page_url, session=session)
    except Exception as e:
        raise Exception('Failed to fetch page: {}'.format(e))

    title = None
    ttag = soup.find('title')
    if ttag and ttag.text:
        title = ttag.text.strip()
    if not title:
        h1 = soup.find('h1') or soup.find('div', class_='title-right')
        if h1:
            title = h1.text.strip()
    info['title'] = clean_title(title) if title else 'luxuretv'

    m = re.search(r'-([0-9]{3,})\.html$', page_url)
    if m:
        info['id'] = m.group(1)
    else:
        parts = page_url.rstrip('/').split('-')
        last = parts[-1] if parts else ''
        info['id'] = re.sub(r'\D', '', last) or ''

    thumb = None
    video_tag = soup.find('video')
    if video_tag:
        poster = video_tag.get('poster')
        if poster:
            thumb = poster
    if not thumb:
        meta = soup.find('meta', {'name': 'twitter:image'}) or soup.find('meta', {'property': 'og:image'})
        if meta and meta.get('content'):
            thumb = meta.get('content')
    if not thumb:
        link_img = soup.find('link', {'rel': 'image_src'})
        if link_img and link_img.get('href'):
            thumb = link_img.get('href')
    info['thumbnail'] = thumb or ''

    formats = []

    def _valid_src(u):
        if not u:
            return False
        return re.search(r'https?://[^/]*luxuretv\.com/videos/', u) is not None

    if video_tag:
        v_src = video_tag.get('src')
        if v_src and _valid_src(v_src):
            formats.append({'url': v_src, 'height': 0})

    for s in soup.find_all('source'):
        src = s.get('src') or s.get('data-src')
        if src:
            if _valid_src(src):
                h = 0
                if s.has_attr('data-res'):
                    try:
                        h = int(s['data-res'])
                    except Exception:
                        h = 0
                formats.append({'url': src, 'height': h})

    seen = set()
    unique = []
    for f in formats:
        u = f.get('url')
        if u and u not in seen:
            seen.add(u)
            unique.append(f)
    formats = unique

    if not formats:
        print_('No direct <source> found, trying ytdl fallback...')
        try:
            ydl = ytdl.YoutubeDL()
            d = ydl.extract_info(page_url)
            if not info.get('title') and d.get('title'):
                info['title'] = clean_title(d.get('title'))
            if not info.get('id') and d.get('id'):
                info['id'] = d.get('id')
            if not info.get('thumbnail') and d.get('thumbnail'):
                info['thumbnail'] = d.get('thumbnail')

            f_list = []
            for f in d.get('formats', []):
                f_url = f.get('url')
                if not f_url:
                    continue
                if _valid_src(f_url):
                    f_list.append({'url': f_url, 'height': f.get('height') or 0})
            formats = sorted(f_list, key=lambda x: x.get('height') or 0)
        except Exception as e:
            print_('ytdl fallback failed: {}'.format(e))

    info['formats'] = formats

    return info

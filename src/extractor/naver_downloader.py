#coding:utf-8
import downloader
import ree as re
from utils import urljoin, Downloader, Soup, LazyUrl, clean_title, get_ext
import json
from timee import sleep
import collections
import errors
PATTERNS = ['.*blog.naver.com/(?P<username>.+)/(?P<pid>[0-9]+)',
            '.*blog.naver.com/.+?blogId=(?P<username>[^&]+).+?logNo=(?P<pid>[0-9]+)',
            '.*?(?P<username>[0-9a-zA-Z_-]+)\.blog\.me/(?P<pid>[0-9]+)']
HDR = {
    'Accept': 'text/html, application/xhtml+xml, image/jxr, */*',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'ko, en-US; q=0.7, en; q=0.3',
    'Connection': 'Keep-Alive',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.79 Safari/537.36 Edge/14.14393',
    }

def get_id(url):
    for pattern in PATTERNS:
        m = re.match(pattern, url)
        if m is None:
            continue
        username = m.group('username')
        pid = m.group('pid')
        break
    else:
        username, pid = None, None
    return username, pid



class Downloader_naver(Downloader):
    type = 'naver'
    URLS = ['blog.naver.', '.blog.me']
    display_name = 'Naver Blog'

    def init(self):
        username, pid = get_id(self.url)
        if username is None:
            raise errors.Invalid('Invalid format: {}'.format(self.url))
        self.url = 'https://blog.naver.com/{}/{}'.format(username, pid)
        self.headers = {'User-Agent': downloader.hdr['User-Agent']}

    @property
    def name(self):
        username, pid = get_id(self.url)
        return clean_title(u'{}/{}'.format(username, pid))

    def read(self):
        self.title = u'읽는 중... {}'.format(self.name)

        imgs = get_imgs(self.url)

        filenames = {}
        for img in imgs:
            self.urls.append(img.url)

        self.title = self.name


class Image(object):
    def __init__(self, url, referer, p):
        self.url = LazyUrl(referer, lambda _: url, self)
        #3788, #3817
        ext = get_ext(url)
        self.filename = '{:04}{}'.format(p, ext)


class Video(object):
    def __init__(self, url, referer, p):
        self.url = LazyUrl(referer, lambda _: url, self)
        self.filename = 'video_{}.mp4'.format(p)


def read_page(url, depth=0):
    print('read_page', url, depth)
    if depth > 10:
        raise Exception('Too deep')
    html = downloader.read_html(url, header=HDR)

    if len(html) < 5000:
        id = re.find('logNo=([0-9]+)', html, err='no id')
        username = re.find('blog.naver.com/([0-9a-zA-Z]+)', url) or re.find('blogId=([0-9a-zA-Z]+)', url, err='no username')
        url = 'https://m.blog.naver.com/PostView.nhn?blogId={}&logNo={}&proxyReferer='.format(username, id)
        print('###', username, id, url)

    soup = Soup(html)
    if soup.find('div', {'id': 'viewTypeSelector'}):
        return url, soup
    frame = soup.find('frame')
    if frame is None:
        print('frame is None')
        return read_page(url, depth+1)
    return read_page(urljoin('https://blog.naver.com', frame.attrs['src']), depth+1)



def get_imgs(url):
    url = url.replace('blog.naver', 'm.blog.naver')
    referer = url
    url_frame, soup = read_page(url)

    imgs = []
    urls = set()
    view = soup.find('div', {'id': 'viewTypeSelector'})
    print('view', view is not None)

    imgs_ = view.findAll('span', class_='_img') + view.findAll('img')

    for img in imgs_:
        url = img.attrs.get('src', None)
        if url is None:
            url = img.attrs.get('thumburl', None)
        if url is None:
            print(u'invalid img: {}'.format(url))
            continue

        if 'ssl.pstatic.net' in url: #
            continue

        if 'blogpfthumb-phinf.pstatic.net' in url: # profile
            continue

        if 'dthumb-phinf.pstatic.net' in url: # link
            continue

        if 'storep-phinf.pstatic.net' in url: # emoticon
            continue

        url =  url.replace('mblogthumb-phinf', 'blogfiles')
        #url = re.sub('\?type=[a-zA-Z0-9]*', '?type=w1@2x', url)
        #url = re.sub('\?type=[a-zA-Z0-9]*', '', url)
        url = url.split('?')[0]

        if url in urls:
            print('### Duplicate:', url)
            continue

        urls.add(url)
        #url = url.split('?type=')[0]
        img = Image(url, referer, len(imgs))
        imgs.append(img)

    pairs = []

    for video in soup.findAll('span', class_='_naverVideo'):
        vid = video.attrs['vid']
        key = video.attrs['key']
        pairs.append((vid, key))

    for script in soup.findAll('script', class_='__se_module_data'):
        data_raw = script['data-module']
        data = json.loads(data_raw)['data']
        vid = data.get('vid')
        if not vid:
            continue
        key = data['inkey']
        pairs.append((vid, key))

    videos = []
    for vid, key in pairs:
        url_api = 'https://apis.naver.com/rmcnmv/rmcnmv/vod/play/v2.0/{}?key={}'.format(vid, key)
        data_raw = downloader.read_html(url_api)
        data = json.loads(data_raw)
        fs = data['videos']['list']
        fs = sorted(fs, key=lambda f: f['size'], reverse=True)
        video = Video(fs[0]['source'], url_frame, len(videos))
        videos.append(video)

    return imgs + videos

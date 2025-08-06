#coding:utf-8
import downloader
import ree as re
from utils import urljoin, Downloader, Soup, LazyUrl, clean_title, get_ext, get_print, Session, json
import errors
PATTERNS = ['.*blog.naver.com/(?P<username>.+)/(?P<pid>[0-9]+)',
            '.*blog.naver.com/.+?blogId=(?P<username>[^&]+).+?logNo=(?P<pid>[0-9]+)',
            '.*?(?P<username>[0-9a-zA-Z_-]+)\.blog\.me/(?P<pid>[0-9]+)']

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
    ACCEPT_COOKIES = [r'(.*\.)?naver\.com', r'(.*\.)?blog\.me']

    def init(self):
        self.session = Session()
        username, pid = get_id(self.url)
        if username is None:
            raise errors.Invalid(f'Invalid format: {self.url}')
        self.url = f'https://blog.naver.com/{username}/{pid}'

    def read(self):
        info = get_imgs(self.url, self.session, self.cw)

        for img in info['imgs']:
            self.urls.append(img.url)

        username, pid = get_id(self.url)
        self.title = clean_title(f'[{username}] {info["title"]} ({pid})')


class Image:
    def __init__(self, url, referer, p):
        self.url = LazyUrl(referer, lambda _: url, self)
        #3788, #3817
        ext = get_ext(url)
        self.filename = f'{p:04}{ext}'


class Video:
    def __init__(self, url, referer, p):
        self.url = LazyUrl(referer, lambda _: url, self)
        self.filename = f'video_{p}.mp4'


def read_page(url, session, depth=0):
    print('read_page', url, depth)
    if depth > 10:
        raise Exception('Too deep')
    html = downloader.read_html(url, session=session)

    if len(html) < 5000:
        id = re.find('logNo=([0-9]+)', html, err='no id')
        username = re.find('blog.naver.com/([0-9a-zA-Z]+)', url) or re.find('blogId=([0-9a-zA-Z]+)', url, err='no username')
        url = f'https://m.blog.naver.com/PostView.nhn?blogId={username}&logNo={id}&proxyReferer='

    soup = Soup(html)
    if soup.find('div', {'id': 'viewTypeSelector'}):
        return url, soup
    frame = soup.find('frame')
    if frame is None:
        print('frame is None')
        return read_page(url, session, depth+1)
    return read_page(urljoin('https://blog.naver.com', frame['src']), session, depth+1)



def get_imgs(url, session, cw):
    print_ = get_print(cw)
    info = {}
    url = url.replace('blog.naver', 'm.blog.naver')
    referer = url
    url_frame, soup = read_page(url, session)

    info['title'] = soup.find('meta', {'property': 'og:title'})['content'].strip()

    imgs = []
    urls = set()
    view = soup.find('div', {'id': 'viewTypeSelector'})

    imgs_ = view.findAll('span', class_='_img') + view.findAll(['img', 'video']) #7062

    for img in imgs_:
        url = img.get('data-gif-url') or img.get('src')
        if not url:
            url = img.get('thumburl')
        if not url:
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

    for video in soup.findAll(class_='_naverVideo'):
        vid = video['vid']
        key = video['key']
        pairs.append((vid, key))
    print_(f'pairs: {pairs}')

    for script in soup.findAll('script', class_='__se_module_data'):
        data_raw = script.get('data-module') or script.get('data-module-v2')
        data = json.loads(data_raw)['data']
        vid = data.get('vid')
        if not vid:
            continue
        key = data['inkey']
        pairs.append((vid, key))

    videos = []
    for vid, key in pairs:
        url_api = f'https://apis.naver.com/rmcnmv/rmcnmv/vod/play/v2.0/{vid}?key={key}'
        data_raw = downloader.read_html(url_api, session=session)
        data = json.loads(data_raw)
        fs = data['videos']['list']
        fs = sorted(fs, key=lambda f: f['size'], reverse=True)
        video = Video(fs[0]['source'], url_frame, len(videos))
        videos.append(video)

    info['imgs'] = imgs + videos

    return info

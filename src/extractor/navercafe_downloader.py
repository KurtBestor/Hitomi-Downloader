#coding:utf8
from utils import Downloader, get_print, urljoin, Soup, get_ext, LazyUrl, clean_title, downloader, re, try_n, errors, json


class LoginRequired(errors.LoginRequired):
    def __init__(self, *args):
        super().__init__(*args, method='browser', url='https://nid.naver.com/nidlogin.login')


class Downloader_navercafe(Downloader):
    type = 'navercafe'
    URLS = ['cafe.naver.com']

    @classmethod
    def fix_url(cls, url):
        m = re.find(r'cafe\.naver\.com/([^/?#]+).+?articleid%3D([0-9]+)', url)
        if m:
            url = 'https://cafe.naver.com/{}/{}'.format(*m)
        return url

    def read(self):
        info = get_info(self.url, self.cw)
        for img in info['imgs']:
            self.urls.append(img.url)
        tail = f' ({info["cafename"]}_{info["id"]})'
        self.title = clean_title(info['title'], n=-len(tail)) + tail


@try_n(4)
def get_info(url, cw=None):
    print_ = get_print(cw)
    info = {}

    html = downloader.read_html(url)
    if '"cafe_cautionpage"' in html:
        raise LoginRequired()
    if re.find(r'''onclick=['"]toLoginPage\(\)['"]''', html): #6358
        raise LoginRequired()
    url_article = re.find(r'''//cafe\.naver\.com/ArticleRead\.nhn\?articleid=[0-9]+&clubid=[0-9]+''', html, err='no iframe')
    url_article = urljoin(url, url_article)

    print_(url_article)

    articleid = re.find(r'articleid=([0-9]+)', url_article)
    clubid = re.find(r'clubid=([0-9]+)', url_article)
    url_api = f'https://apis.naver.com/cafe-web/cafe-articleapi/v2/cafes/{clubid}/articles/{articleid}?query=&useCafeId=true&requestFrom=A'

    j = downloader.read_json(url_api, url)

    info['title'] = j['result']['article']['subject']
    info['cafename'] = j['result']['cafe']['url']
    info['cafeid'] = clubid
    info['id'] = articleid

    html_content = j['result']['article']['contentHtml']
    soup = Soup(html_content)

    imgs = []

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

    for vid, key in pairs:
        url_api = f'https://apis.naver.com/rmcnmv/rmcnmv/vod/play/v2.0/{vid}?key={key}'
        data_raw = downloader.read_html(url_api)
        data = json.loads(data_raw)
        fs = data['videos']['list']
        fs = sorted(fs, key=lambda f: f['size'], reverse=True)
        video = Image(fs[0]['source'], url_article, len(imgs))
        imgs.append(video)

    for img in soup.findAll('img'):
        img = Image(urljoin(url_article, img['src']), url, len(imgs))
        imgs.append(img)

    info['imgs'] = imgs

    return info


class Image:
    def __init__(self, url, referer, p):
        self.url = LazyUrl(referer, lambda _: url, self)
        ext = get_ext(url)
        self.filename = f'{p:04}{ext}'

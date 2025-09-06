# coding:utf8
from utils import Downloader, get_print, urljoin, Soup, get_ext, File, clean_title, downloader, re, try_n, errors, json, Session
import utils


class LoginRequired(errors.LoginRequired):
    def __init__(self, *args):
        super().__init__(*args, method='browser', url='https://nid.naver.com/nidlogin.login')


class Downloader_navercafe(Downloader):
    type = 'navercafe'
    URLS = ['cafe.naver.com']
    display_name = 'Naver Cafes'
    ACCEPT_COOKIES = [r'(.*\.)?naver\.com']

    def init(self):
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        print('origin_url', url)

        # 신형 우선 처리 (성능 최적화)
        patterns = [
            # REST API 스타일
            (r'cafe\.naver\.com/[^/]+/cafes/([0-9]+)/articles/([0-9]+)',
             lambda m: f'https://cafe.naver.com/ArticleRead.nhn?articleid={m[1]}&clubid={m[0]}'),

            # 구형 스타일
            (r'cafe\.naver\.com/([^/?#]+).+?articleid%3D([0-9]+)',
             lambda m: f'https://cafe.naver.com/{m[0]}/{m[1]}'),
        ]

        for pattern, formatter in patterns:
            m = re.search(pattern, url)
            if m:
                fixed_url = formatter(m.groups())
                print('fixed_url', fixed_url)
                return fixed_url

        print('no_fix_needed', url)
        return url

    def read(self):
        info = get_info(self.url, self.session, self.cw)
        for img in info['imgs']:
            self.urls.append(img)
        tail = f' ({info["cafename"]}_{info["id"]})'
        self.title = clean_title(info['title'], n=-len(tail)) + tail


@try_n(4)
def get_info(url, session, cw=None):
    print_ = get_print(cw)
    info = {}

    html = downloader.read_html(
        url, 'http://search.naver.com', session=session)
    soup = Soup(html)
    if '"cafe_cautionpage"' in html:
        raise LoginRequired()
    PATTERN = r"//cafe\.naver\.com/ArticleRead\.nhn\?[^'\"]*articleid=[0-9]+[^'\"]*"
    matches = [match.group()
               for src in [html, url]
               for match in [re.search(PATTERN, src)]
               if match]

    url_article = matches[0] if matches else "no articleid"
    url_article = urljoin(url, url_article)

    print_(url_article)

    articleid = re.find(r'articleid=([0-9]+)', url_article)
    clubid = re.find(r'clubid(=|%3D)([0-9]+)', url_article)[1]
    art = re.find(r'art=(.+?)&', url_article)
    if art:
        url_api = f'https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{clubid}/articles/{articleid}?art={art}&useCafeId=true&requestFrom=A'
    else:
        url_api = f'https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{clubid}/articles/{articleid}?query=&useCafeId=true&requestFrom=A'

    j = downloader.read_json(url_api, url_article, session=session)

    if j['result'].get('errorCode'):  # 6358
        raise LoginRequired(j['result'].get('reason'))

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
        data_raw = script.get('data-module') or script.get('data-module-v2')
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
        video = Image(
            {'url': fs[0]['source'], 'referer': url_article, 'p': len(imgs)})
        imgs.append(video)

    for img in soup.findAll('img'):
        img = Image(
            {'url': urljoin(url_article, img['src']), 'referer': url, 'p': len(imgs)})
        imgs.append(img)

    info['imgs'] = imgs

    return info


class Image(File):
    type = 'navercafe'
    format = 'page:04;'

    def __init__(self, info):
        self._url = info['url']
        info['url'] = re.sub(r'[?&]type=[wh0-9]+', '', self._url)  # 6460
        ext = get_ext(info['url'])
        d = {
            'page': info['p'],
        }
        info['name'] = utils.format('navercafe', d, ext)
        super().__init__(info)

    def alter(self):
        return self._url

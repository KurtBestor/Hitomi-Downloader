import downloader
from utils import Soup, urljoin, Downloader, LazyUrl, get_print, clean_url, clean_title, check_alive, Session, try_n, format_filename, tr_, get_ext, print_error, get_max_range
import ree as re
import errors
import clf2
import hashlib
import urllib
from io import BytesIO
from timee import time
TIMEOUT = 300
PATTERN_ID = r'(image|video)/([0-9a-zA-Z_-]+)'



class Downloader_iwara(Downloader):
    type = 'iwara'
    URLS = ['iwara.tv']
    MAX_CORE = 16#
    single = True
    display_name = 'Iwara'
    ACCEPT_COOKIES = [r'(.*\.)?iwara\.tv']

    @classmethod
    def fix_url(cls, url):
        url = clean_url(url)
        return url.split('?')[0]

    def init(self):
        self.session = Session()
        self.setTimeout(TIMEOUT)

    def read(self):
        info = get_info(self.url, self.session, self.cw)
        if info is None:
            return # embeded
        self.title = clean_title(info['title'])

        videos = info['files']
        self.single = len(videos) < 2

        # first video must be valid
        while videos:
            video = videos[0]
            try:
                video.url()
                break
            except Exception as e:
                e_ = e
                self.print_(print_error(e))
                videos.remove(video)
        else:
            raise e_

        if info.get('playlist', False):
            video = self.process_playlist(info['title'], videos)
        else: #6031
            self.urls += [file.url for file in videos]

        self.enableSegment()

        url_thumb = video.url_thumb
        self.print_(f'url_thumb: {url_thumb}')
        if url_thumb:
            f = BytesIO()
            downloader.download(url_thumb, buffer=f, session=self.session, customWidget=self.cw)
            f.seek(0)
            self.setIcon(f)

        username = info.get('username')
        if username:
            self.artist = username



class File:
    def __init__(self, type, url, referer, info, session, multi_post=False):
        title = info['title']
        p = len(info['files'])
        self.url = LazyUrl(referer, lambda _: url, self)
        ext = get_ext(url) or downloader.get_ext(url, session=session)
        if type == 'video':
            id_ = re.find(PATTERN_ID, referer, err='no video id')[1]
            self.filename = format_filename(title, id_, ext) #4287
        else:
            name = '{}_p{}'.format(clean_title(title), p) if multi_post else p
            self.filename = '{}{}'.format(name, ext)
        self.url_thumb = info.get('url_thumb')


class LazyFile:
    def __init__(self, url, session, cw):
        self.session = session
        self.cw = cw
        self.url = LazyUrl(url, self.get, self)

    def get(self, url):
        info = get_info(url, self.session, self.cw)
        file = info['files'][0]
        self.filename = file.filename
        self.url_thumb = file.url_thumb
        return file.url()


def get_token(session, cw=None):
    token = None
    def f(html, browser=None):
        def callback(r):
            nonlocal token
            token = r
        browser.runJavaScript('window.localStorage.getItem("token")', callback=callback)
        return bool(token)
    clf2.solve('https://iwara.tv', session=session, cw=cw, f=f, timeout=15)
    #print_(f'token: {token}')
    r = session.post('https://api.iwara.tv/user/token', headers={'Authorization': f'Bearer {token}'})
    d = r.json()
    token = d['accessToken']
    #print_(f'token2: {token}')
    return token


@try_n(2)
def get_info(url, session, cw, multi_post=False):
    print_ = get_print(cw)
    t0 = None
    def f(html, browser=None):
        nonlocal t0
        soup = Soup(html)
        if t0 is None:
            t0 = time()
        if time() - t0 > 10 or '/profile/' in url.lower():
            for a in soup.findAll('a'):
                if urljoin(url, a.get('href', '')) == urljoin(url, '/login'):
                    raise errors.LoginRequired(method='browser', url='https://www.iwara.tv/login', cookie=False, w=1460) #5794
        buttons = soup.findAll(class_='button--primary')
        if buttons:
            for i, button in enumerate(buttons):
                button_text = button.text
                if not button_text:
                    continue
                print_(f'button: {button_text}')
                if button_text.lower() in ['i am over 18', 'continue']:
                    browser.runJavaScript(f'btns=document.getElementsByClassName("button--primary");btns[{i}].click();') #5794#issuecomment-1517879513
        if '/profile/' in url.lower():
            return soup.find('div', class_='page-profile__header') is not None
        else:
            details = soup.find('div', class_='page-video__details')
            if details and not soup.find('div', class_='vjs-poster') and not soup.find(class_='embedPlayer__youtube'): #6737, #6836
                print_('no poster')
                return False
            details = details or soup.find('div', class_='page-image__details')
            return details is not None and details.find('div', class_='text--h1') is not None

    html = clf2.solve(url, session=session, f=f, cw=cw, timeout=30)['html'] #5794
    soup = Soup(html)

    info = {}
    info['files'] = []

    type = url.split('/')[3]
    if type == 'profile':
        max_pid = get_max_range(cw)
        ids = set()
        sub = (url+'/').split('/')[5]
        if not sub:
            sub = 'videos'
        uid = url.split('/')[4]
        url_api = f'https://api.iwara.tv/profile/{uid}'
        j = downloader.read_json(url_api, session=session)
        info['username'] = username = j['user']['name']
        info['id'] = id = j['user']['username']
        info['title'] = f'[Channel] [{sub.capitalize()}] {username} ({id})'
        id = j['user']['id']
        if sub == 'videos':
            info['playlist'] = True
            for p in range(100):
                url_api = f'https://api.iwara.tv/videos?page={p}&sort=date&user={id}'
                j = downloader.read_json(url_api, session=session)
                for post in j['results']:
                    id_ = post['id']
                    if id_ in ids:
                        continue
                    ids.add(id_)
                    slug = post['slug']
                    url_post = f'https://www.iwara.tv/video/{id_}/{slug}'
                    file = LazyFile(url_post, session, cw)
                    info['files'].append(file)
                if cw: cw.setTitle(tr_('읽는 중... {} ({} / {})').format(info['title'], len(ids), j['count']))
                if len(info['files']) >= max_pid:
                    break
                if j['limit']*(p+1) >= j['count']: break
        elif sub == 'images':
            for p in range(100):
                url_api = f'https://api.iwara.tv/images?page={p}&sort=date&user={id}'
                j = downloader.read_json(url_api, session=session)
                for post in j['results']:
                    check_alive(cw)
                    id_ = post['id']
                    if id_ in ids:
                        continue
                    ids.add(id_)
                    slug = post['slug']
                    url_post = f'https://www.iwara.tv/image/{id_}/{slug}'
                    info_post = get_info(url_post, session, cw, True)
                    info['files'] += info_post['files']
                    print_(f'imgs: {len(info["files"])}')
                    if cw: cw.setTitle(tr_('읽는 중... {} ({} / {})').format(info['title'], len(ids), j['count']))
                    if len(info['files']) >= max_pid:
                        break
                if len(info['files']) >= max_pid:
                        break
                if j['limit']*(p+1) >= j['count']: break
        else:
            raise NotImplementedError(f'profile: {sub}')
        return info

    details = soup.find('div', class_='page-video__details') or soup.find('div', class_='page-image__details')
    info['title'] = details.find('div', class_='text--h1').text.strip()
    info['username'] = soup.find('a', class_='username')['title']

    soup.find('div', class_='videoPlayer') or soup.find('div', class_='page-image__slideshow')

    id = re.find(PATTERN_ID, url, err='no id')[1]

    try:
        token = get_token(session, cw=cw)
    except Exception as e:
        print_(print_error(e))
        token = None

    url_api = f'https://api.iwara.tv/{type}/{id}'
    hdr = {}
    if token:
        hdr['authorization'] = f'Bearer {token}'
    data = downloader.read_json(url_api, url, session=session, headers=hdr)

    if data.get('embedUrl'):
        if cw and not cw.downloader.single:
            raise errors.Invalid('[iwara] Embeded: {}'.format(data['embedUrl']))
        #5869
        cw.downloader.pass_()
        cw.gal_num = cw.url = data['embedUrl']
        d = Downloader.get('youtube')(data['embedUrl'], cw, cw.downloader.thread, 1)
        d.start()
        return

    if not data.get('files'):
        data['files'] = [data['file']]

    for file in data['files']:
        id_ = file['id']
        if type == 'video':
            fileurl = data['fileUrl']
            up = urllib.parse.urlparse(fileurl)
            q = urllib.parse.parse_qs(up.query)
            paths = up.path.rstrip('/').split('/')
            x_version = hashlib.sha1('_'.join((paths[-1], q['expires'][0], '5nFp9kmbNnHdAFhaqMvt')).encode()).hexdigest() # https://github.com/yt-dlp/yt-dlp/issues/6549#issuecomment-1473771047
            j = downloader.read_json(fileurl, url, session=session, headers={'X-Version': x_version})
            def key(x):
                if x['name'].lower() == 'source':
                    return float('inf')
                try:
                    return float(x['name'])
                except:
                    return -1
            x = sorted(j, key=key)[-1]
            print_(f'name: {x["name"]}')
            url_file = urljoin(url, x['src']['view'])
            poster = soup.find('div', class_='vjs-poster')['style']
            info['url_thumb'] = urljoin(url, re.find(r'url\("(.+?)"', poster, err='no poster'))
        else:
            name = file['name']
            url_file = f'https://i.iwara.tv/image/original/{id_}/{name}'
        if len(data['files']) == 1:
            multi_post = True#
        file = File(type, url_file, url, info, session, multi_post)
        info['files'].append(file)

    return info

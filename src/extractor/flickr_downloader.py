from utils import Downloader, File, Session, urljoin, get_ext, clean_title, Soup, limits
import utils
import ree as re
import downloader
import clf2
from timee import time
TIMEOUT = 10


class File_flickr(File):
    type = 'flickr'
    format = '[date] id'

    @limits(1)
    def get(self):
        url = self['referer']
        soup = downloader.read_soup(url, session=self.session)
        img = soup.find('meta', {'property': 'og:image'})['content']
        date = re.find(r'"dateCreated":{"data":"([0-9]+)"', soup.html, err='no date')
        ext = get_ext(img)
        d = {
            'date': int(date),
            'id': re.find(r'/photos/[^/]+/([0-9]+)', url, err='no id'),
            }
        return {'url': img, 'name': utils.format('flickr', d, ext)}


class Downloader_flickr(Downloader):
    type = 'flickr'
    URLS = ['flickr.com']
    MAX_CORE = 4
    ACCEPT_COOKIES = [r'(.*\.)?flickr\.com']

    def init(self):
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        url = url.replace('flickr.com/people/', 'flickr.com/photos/')
        uid = re.find(r'flickr.com/photos/([^/]+)', url)
        if uid:
            url = f'https://www.flickr.com/photos/{uid}'
        return url

    def read(self):
        tab = ''.join(self.url.split('/')[3:4])
        if tab == 'photos':
            uid = self.url.split('/')[4]
            title = None
            ids = set()
            c = 0
            ct = None
            p_max = 1
            def f(html, browser=None):
                nonlocal title, c, ct, p_max
                soup = Soup(html)
                browser.runJavaScript('window.scrollTo(0,document.body.scrollHeight);')

                for a in soup.findAll('a'):
                    href = a.get('href') or ''
                    href = urljoin(self.url, href)
                    p_max = max(p_max, int(re.find(rf'flickr.com/photos/{uid}/page([0-9]+)', href) or 0))
                    id_ = re.find(rf'/photos/{uid}/([0-9]+)', href)
                    if not id_:
                        continue
                    if id_ in ids:
                        continue
                    ids.add(id_)
                    file = File_flickr({'referer': href})
                    self.urls.append(file)

                if ids:
                    uname = soup.h1.text.strip()
                    title = f'{clean_title(uname)} (flickr_{uid})'
                    self.cw.setTitle(f'{title} - {len(ids)}')
                    if c == len(ids):
                        if not ct:
                            ct = time()
                        dt = time() - ct
                        if dt > TIMEOUT:
                            return True
                    else:
                        ct = None
                    c = len(ids)

            p = 1
            while p <= p_max:
                url = f'https://www.flickr.com/photos/{uid}/page{p}'
                self.print_(url)
                clf2.solve(url, session=self.session, f=f)
                p += 1
            self.title = title
        else:
            raise NotImplementedError(tab)

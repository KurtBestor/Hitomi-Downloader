import downloader
from utils import Downloader, LazyUrl, clean_title, urljoin, get_ext
from ratelimit import limits, sleep_and_retry


class Image:
    def __init__(self, url, ref, n):
        self._url = url
        self.url = LazyUrl(ref, self.get, self)
        self.filename = '{:04}{}'.format(n, get_ext(url))

    @sleep_and_retry
    @limits(2, 1)
    def get(self, _):
        return self._url



class Downloader_4chan(Downloader):
    type = '4chan'
    URLS = [r'regex:boards.(4chan|4channel).org']
    MAX_CORE = 4
    display_name = '4chan'

    @classmethod
    def fix_url(cls, url):
        return url.split('#')[0]

    def read(self):
        soup = downloader.read_soup(self.url)
        for div in soup.findAll('div', class_='fileText'):
            href = urljoin(self.url, div.a['href'])
            img = Image(href, self.url, len(self.urls))
            self.urls.append(img.url)

        board = self.url.split('/')[3]
        title = soup.find('span', class_='subject').text
        id_ = int(self.url.split('/thread/')[1].split('/')[0])
        self.title = clean_title(f'[{board}] {title} ({id_})')

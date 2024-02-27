from utils import Downloader, urljoin, clean_title, try_n, check_alive, LazyUrl, get_ext, get_max_range, limits
from translator import tr_
import ree as re
import downloader
from urllib.parse import unquote


@try_n(4)
@limits(.25)
def read_soup(url):
    return downloader.read_soup(url)



class Downloader_yandere(Downloader):
    type = 'yande.re'
    URLS = ['yande.re']
    MAX_CORE = 4
    ACCEPT_COOKIES = [r'(.*\.)?yande\.re']

    @classmethod
    def fix_url(cls, url):
        url = re.sub(r'([?&])page=[0-9]+&?', r'\1', url).rstrip('?&')
        pool = re.find('/pool/show/([0-9]+)', url)
        if pool is not None:
            url = urljoin(url, '/post?tags=pool%3A{}'.format(pool))
        return url

    def read(self):
        title = self.get_title(self.url)

        url = self.url
        n = get_max_range(self.cw)
        ids = set()
        while True:
            check_alive(self.cw)
            soup = read_soup(url)
            for a in soup.find_all('a', class_='thumb'):
                id_ = re.find(r'/show/([0-9]+)', a['href'], err='no id')
                if id_ in ids:
                    self.print_(f'dup: {id_}')
                    continue
                ids.add(id_)
                img = Image(urljoin(url, a['href']), id_)
                self.urls.append(img.url)
            if len(self.urls) >= n:
                del self.urls[n:]
                break

            self.cw.setTitle('{}  {} - {}'.format(tr_('읽는 중...'), title, len(self.urls)))

            next_page = soup.find('a', attrs={'rel':'next'}, href=True)
            if not next_page:
                break
            else:
                url = urljoin(self.url, next_page['href'])

        self.title = title

    def get_id(self, url:str) -> str:
        id_ = url.split('yande.re%20')[1].split('%20')[0]
        return int(id_)

    def get_title(self, url:str) -> str:
        if "tags=" not in url:
            raise NotImplementedError('no tags')

        url_tags = url.split("tags=")[-1].split('+')

        return clean_title(unquote(" ".join(url_tags)))


class Image:

    def __init__(self, url, id_):
        self._id = id_
        self.url = LazyUrl(url, self.get, self)

    def get(self, url):
        soup = read_soup(url)
        img = soup.find('a', class_='original-file-unchanged') or soup.find('a', class_='original-file-changed')
        img = urljoin(url, img['href'])
        ext = get_ext(img)
        self.filename = clean_title(self._id, n=-len(ext)) + ext
        return img

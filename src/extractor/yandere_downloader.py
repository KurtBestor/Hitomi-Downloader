from urllib.parse import unquote
from utils import Downloader, urljoin, clean_title, try_n
from translator import tr_
import ree as re
import os
import downloader


@try_n(4)
def read_soup(url):
    return downloader.read_soup(url)


@Downloader.register
class Downloader_yandere(Downloader):
    type = 'yande.re'
    URLS = ['yande.re']
    MAX_CORE = 4

    @classmethod
    def fix_url(cls, url):
        url = re.sub(r'\?page=[0-9]+&', '?', url)
        url = re.sub(r'&page=[0-9]+', '', url)
        pool = re.find('/pool/show/([0-9]+)', url)
        if pool is not None:
            url = urljoin(url, '/post?tags=pool%3A{}'.format(pool))
        return url

    def read(self):
        cw = self.cw

        title = self.get_title(self.url)

        ids = set()
        url = self.url
        while True:
            soup = read_soup(url)
            tmp = soup.find_all(attrs={'class':'directlink'}, href=True)
            for image_html in tmp:
                image_url = image_html['href']
                id_ = self.get_id(image_url)
                if id_ in ids:
                    self.print_('duplicate: {}'.format(id_))
                    continue
                ids.add(id_)
                self.urls.append(image_url)
                self.filenames[image_url] = self.get_filename(image_url)

            if not cw.alive:
                break
            cw.setTitle('{}  {} - {}'.format(tr_('읽는 중...'), title, len(self.urls)))

            next_page = soup.find('a', attrs={'rel':'next'}, href=True)
            if not next_page:
                break
            else:
                url = urljoin(self.url, next_page['href'])

        self.title = title

    def get_id(self, url:str) -> str:
        id_ = url.split('yande.re%20')[1].split('%20')[0]
        return int(id_)

    def get_filename(self, url:str) -> str:
        url_unquote = unquote(url)
        id_tags_extension = url_unquote.split("yande.re")[-1].split(" ")[1:]
        filename = "_".join(id_tags_extension)
        name, ext = os.path.splitext(filename)
        name = str(self.get_id(url))#
        return clean_title(name, n=-len(ext)) + ext

    def get_title(self, url:str) -> str:
        if "tags=" not in url:
            raise NotImplementedError('no tags')

        url_tags = url.split("tags=")[-1].split('+')

        return clean_title(" ".join(url_tags))

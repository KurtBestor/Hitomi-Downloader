import downloader
from utils import Downloader, File, clean_title, urljoin, get_ext, limits
import utils



class File_4chan(File):
    type = '4chan'
    format = 'page:04;'

    @limits(.5)
    def get(self):
        return {}



class Downloader_4chan(Downloader):
    type = '4chan'
    URLS = [r'regex:boards.(4chan|4channel).org']
    MAX_CORE = 4
    display_name = '4chan'
    ACCEPT_COOKIES = [r'(.*\.)?(4chan|4channel)\.org']

    @classmethod
    def fix_url(cls, url):
        return url.split('#')[0]

    def read(self):
        soup = downloader.read_soup(self.url)
        for div in soup.findAll('div', class_='fileText'):
            href = urljoin(self.url, div.a['href'])
            d = {
                'page': len(self.urls),
                }
            file = File_4chan({'url': href, 'referer': self.url, 'name': utils.format('4chan', d, get_ext(href))})
            self.urls.append(file)

        board = self.url.split('/')[3]
        title = soup.find('span', class_='subject').text
        id_ = int(self.url.split('/thread/')[1].split('/')[0])
        self.title = clean_title(f'[{board}] {title} ({id_})')

# coding: cp1252
# title: Wayback Machine Downloader
# author: bog_4t
import concurrent.futures

import downloader, json, os
from utils import Downloader, Session, clean_title, get_print, update_url_query, print_error
import ree as re
from hashlib import md5
from ratelimit import limits, sleep_and_retry


@Downloader.register
class Downloader_wayback_machine(Downloader):
    type = 'waybackmachine'
    URLS = ['archive.org', 'web.archive.org']
    icon = 'https://archive.org/offshoot_assets/favicon.ico'
    display_name = 'Wayback Machine'

    def init(self):
        self.print = get_print(self.cw)

    def read(self):
        e = Extractor(self.url, self.cw)
        self.url = f'https://web.archive.org/cdx/search/cdx?url={e.url}'

        self.title = e.title
        self.urls.extend(get_imgs(self.url, e, self.dir, self.session, self.cw))
        self.title = e.title


class WaybackMachineAPI(object):
    def __init__(self, session, cw=None):
        self.session = session
        self.cw = cw
        self.params = {
            'output': 'json',
            'fl': 'timestamp,original',
            'filter': 'mimetype:text/html',
            'statuscode': '200',
            'collapse': 'urlkey',
            'limit': '5'
        }

    @sleep_and_retry
    @limits(5, 1)
    def call(self, url):
        get_print(self.cw)(url)
        url = update_url_query(url, self.params)
        return downloader.read_json(url, session=self.session)

    def snapshots(self, url):
        data = self.call(url)
        return data[1:] or None


class Extractor(object):
    domains = [
        'twitter.com'
    ]

    def __init__(self, url, cw=None):
        self.cw = cw
        self.print = get_print(cw)
        self.url = re.findall(r'archive.[^/]+/(?:cdx/search/cdx\?url=|(?:web/)?(?:[^/]+/))([^&]+)', url.lower())[0].split('&')[0]
        self.md5 = md5(self.url.encode('utf8')).hexdigest()[:8]
        self.mode = self.__get_mode()
        self.title = self.__get_title()

    def __get_mode(self):
        for mode in [mode for mode, domain in enumerate(self.domains, start=1) if domain in self.url]:
            return mode
        return 0

    def __get_title(self):
        def default():
            tail = f' ({self.md5})'
            return clean_title(os.path.basename(self.url.strip('*').strip('/')), n=-len(tail)) + tail

        def twitter():
            return re.findall('twitter.[^/]+/([^/?]+)', self.url)[0]

        return [
            default,
            twitter
        ][self.mode]()

    def get_imgs_soup(self, soup, snapshot):
        base_url = 'https://web.archive.org/web/{}im_/{}'

        if not soup:
            return []

        def default():
            return [base_url.format(snapshot[0], img['src']) for img in soup.find_all('img', src=True)]

        def twitter():
            return [base_url.format(snapshot[0], div['data-image-url']) for div in soup.find_all('div', {'data-image-url': True})]

        return [
            default,
            twitter
        ][self.mode]()


class Bitmap(object):
    bitmask = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80]

    def __init__(self, size=0, cw=None):
        self.cw = cw
        self.bitmap = bytearray([False] * ((size + 7) // 8))

    def set(self, index):
        self.bitmap[index // 8] |= self.bitmask[index % 8]

    def unset(self, index):
        self.bitmap[index // 8] &= ~self.bitmask[index % 8]

    def get(self, index):
        return (self.bitmap[index // 8] & (self.bitmask[index % 8])) != 0

    def save(self, path):
        with open(path, 'wb') as file:
            file.seek(0)
            file.write(self.bitmap)

    def load(self, size, path):
        with open(path, 'rb') as file:
            self.bitmap = bytearray(file.read((size + 7)//8))
        return self

    def update(self, id_, path):
        self.set(id_)
        self.save(path)

    def print(self, size):
        get_print(self.cw)([str(1) if self.get(i) else str(0) for i in range(0, size)])


def get_imgs(url, extractor, directory, session=Session(), cw=None):
    e = extractor
    print_ = get_print(cw)

    if not os.path.exists(directory):
        os.makedirs(directory)

    urls_path = os.path.join(directory, '{}.urls'.format(e.md5))
    bitmap_path = os.path.join(directory, '{}.bitmap'.format(e.md5))
    count_path = os.path.join(directory, '{}.count'.format(e.md5))

    for path in [urls_path, bitmap_path, count_path]:
        if not os.path.exists(path):
            open(path, 'x').close()

    with open(count_path) as file:
        num_complete = (lambda x: int(x) if x else 0)(file.read())

    snapshots = WaybackMachineAPI(session, cw).snapshots(url)
    bitmap = Bitmap(cw=cw).load(len(snapshots), bitmap_path) if num_complete else Bitmap(len(snapshots), cw=cw)

    def get_imgs_snapshot(id_, snapshot):
        @sleep_and_retry
        @limits(5, 1)
        def get_soup():
            try:
                return downloader.read_soup(f'https://web.archive.org/web/{snapshot[0]}id_/{snapshot[1]}')
            except Exception as exception:
                print_(print_error(exception)[0])
                return None

        return id_, e.get_imgs_soup(get_soup(), snapshot)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(get_imgs_snapshot, id_, snapshot) for id_, snapshot in enumerate(snapshots) if not bitmap.get(id_)]

    with open(urls_path, 'a') as urls_file:
        for future in concurrent.futures.as_completed(futures):
            id_, urls = future.result()
            urls_file.writelines([f'{url}\n' for url in urls])
            bitmap.update(id_, bitmap_path)
            num_complete += 1
            str_num_complete = str(num_complete)
            with open(count_path, 'w') as count_file:
                count_file.write(str_num_complete)
            cw.setTitle('{} - {}'.format(e.title, str_num_complete))

    with open(urls_path) as file:
        urls = [re.findall(r'^\S+$', lines)[0] for lines in file.readlines()]

    os.remove(urls_path)
    os.remove(bitmap_path)
    os.remove(count_path)

    return urls

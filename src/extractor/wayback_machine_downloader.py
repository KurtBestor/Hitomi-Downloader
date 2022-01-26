# coding: utf8
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
    display_name = 'Wayback Machine'

    def read(self):
        filter_ = Filter(self.url, self.cw)
        self.url = f'https://web.archive.org/cdx/search/cdx?url={filter_.url}'
        self.title = filter_.title
        self.urls.extend(get_imgs(self.url, filter_, self.dir, self.session, self.cw))
        self.title = filter_.title


class WaybackMachineAPI(object):
    def __init__(self, session, cw=None):
        self.session = session
        self.cw = cw
        self.params = {
            'output': 'json',
            'fl': 'timestamp,original',
            'filter': 'mimetype:text/html',
            'statuscode': '200',
            'collapse': 'urlkey'
        }

    @sleep_and_retry
    @limits(1, 5)
    def call(self, url):
        url = update_url_query(url, self.params)
        return downloader.read_json(url, session=self.session)

    def snapshots(self, url):
        data = self.call(url)
        return data[1:] or None


class Filter(object):
    domains = [
        'twitter.com'
    ]

    def __init__(self, url, cw=None):
        self.cw = cw
        self.url = re.findall(r'archive.[^/]+/(?:cdx/search/cdx\?url=|(?:web/)?(?:[^/]+/))(.+)', url.lower())[0].strip(
            '/')
        self.base_url = self.url.split('&')[0].strip('*').strip('/')
        self.md5 = md5(self.url.encode('utf8')).hexdigest()[:8]
        self.mode = self.__get_mode()
        self.title = self.__get_title()

    def __get_mode(self):
        for mode in [mode for mode, domain in enumerate(self.domains, start=1) if domain in self.url]:
            return mode
        return 0

    def __get_title(self):
        def default():
            tail = f" ({md5(self.base_url.encode('utf8')).hexdigest()[:8]})"
            return clean_title(os.path.basename(self.base_url), n=-len(tail)) + tail

        def twitter():
            return '@' + re.findall('twitter.[^/]+/([^/?]+)', self.url)[0]

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
            self.bitmap = bytearray(file.read((size + 7) // 8))
        return self

    def update(self, id_, path):
        self.set(id_)
        self.save(path)


def get_imgs(url, filter_, directory, session=Session(), cw=None):
    print_ = get_print(cw)

    if not os.path.exists(directory):
        os.makedirs(directory)

    urls_path = os.path.join(directory, '{}.urls'.format(filter_.md5))
    bitmap_path = os.path.join(directory, '{}.bitmap'.format(filter_.md5))
    count_path = os.path.join(directory, '{}.count'.format(filter_.md5))

    for path in [urls_path, bitmap_path, count_path]:
        if not os.path.exists(path):
            open(path, 'x').close()

    with open(count_path) as file:
        num_complete = (lambda x: int(x) if x else 0)(file.read())

    snapshots = WaybackMachineAPI(session, cw).snapshots(url)
    bitmap = Bitmap(cw=cw).load(len(snapshots), bitmap_path) if num_complete else Bitmap(len(snapshots), cw=cw)

    base_url = 'https://web.archive.org/web/{}im_/{}'

    def get_imgs_snapshot(id_, snapshot):

        @sleep_and_retry
        @limits(1, 5)
        def get_soup():
            try:
                return downloader.read_soup(f'https://web.archive.org/web/{snapshot[0]}id_/{snapshot[1]}')
            except Exception as exception:
                print_(print_error(exception)[0])
                return None

        def get_imgs_soup(soup):
            if not soup:
                return []

            def default():
                return [base_url.format(snapshot[0], img['src']) for img in soup.find_all('img', src=True)]

            def twitter():
                return [base_url.format(snapshot[0], img['src']) for img in soup.find_all('img', {'src': True}) if 'twimg.com/media/' in img['src']]

            return [
                default,
                twitter
            ][filter_.mode]()

        return id_, get_imgs_soup(get_soup())

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(get_imgs_snapshot, id_, snapshot) for id_, snapshot in enumerate(snapshots) if not bitmap.get(id_)]

    with open(urls_path, 'a') as urls_file:
        for future in concurrent.futures.as_completed(futures):
            id_, urls = future.result()
            urls_file.writelines([f'{url}\n' for url in urls])
            bitmap.update(id_, bitmap_path)
            num_complete += 1
            with open(count_path, 'w') as count_file:
                count_file.write(str(num_complete))
            msg = f'{filter_.title} - {num_complete}'
            cw.setTitle(msg) if cw else print_(msg)

    with open(urls_path) as file:
        urls = set()
        for url in file.readlines():
            urls.add(re.findall(r'^\S+$', url)[0])

    os.remove(urls_path)
    os.remove(bitmap_path)
    os.remove(count_path)

    return urls

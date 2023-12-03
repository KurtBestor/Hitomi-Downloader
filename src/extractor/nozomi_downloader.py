import downloader
from urllib.parse import quote
from io import BytesIO
from utils import Downloader, query_url, get_ext, clean_title, check_alive, lock, get_print, get_max_range, File
import errors
from translator import tr_
from ratelimit import limits, sleep_and_retry
import utils
import os



class File_nozomi(File):
    type = 'nozomi'
    format = 'idpage?'

    def get(self):
        infos = []
        for p, img in enumerate(read_post(self['id'], self['referer'], self.cw)):
            url = img['url']
            d = {
                'id': img['id'],
                'page?': f'_p{p}' if p else '',
                }
            filename = utils.format('nozomi', d, get_ext(url))
            info = {'url': url, 'name': filename, 'referer': img['referer']}
            infos.append(info)
        return infos


@sleep_and_retry
@limits(4, 1)
def read_post(id, referer, cw):
    print_ = get_print(cw)
    check_alive(cw)
    # https://j.nozomi.la/nozomi.js
    s_id = str(id)
    url_post = 'https://j.nozomi.la/post/{}/{}/{}.json'.format(s_id[-1], s_id[-3:-1], s_id)
    try:
        j = downloader.read_json(url_post, referer)
    except Exception as e:
        print_(f'{id}: {e}')
        return [] #5989
    imgs = []
    for url in j['imageurls']:
        did = url['dataid']
        if j.get('is_video'): #5754
            cdn = 'v'
            ext = url['type']
        else:
            cdn = 'g' if j.get('type') == 'gif' else 'w'
            ext = 'gif' if url.get('type') == 'gif' else 'webp'
        url = 'https://{}.nozomi.la/{}/{}/{}.{}'.format(cdn, did[-1], did[-3:-1], did, ext) #5340
        img = {'id': id, 'url': url, 'referer': f'https://nozomi.la/post/{id}.html'}
        imgs.append(img)
    return imgs


class Downloader_nozomi(Downloader):
    type = 'nozomi'
    URLS = ['nozomi.la']
    display_name = 'Nozomi.la'
    MAX_CORE = 15
    ACC_MTIME = True
    ACCEPT_COOKIES = [r'(.*\.)?nozomi\.la']

    @classmethod
    def fix_url(cls, url):
        return url.split('#')[0]

    @property
    def name(self):
        qs = query_url(self.url)
        name = qs['q'][0]
        if self._popular:
            name += ' - Popular'
        return clean_title(name)

    def read(self):
        if '/post/' in self.url:
            raise errors.Invalid(tr_('개별 다운로드는 지원하지 않습니다: {}').format(self.url))
        self._popular = 'search-Popular.' in self.url
        self.title = '{} {}'.format(tr_('읽는 중...'), self.name)
        qs = query_url(self.url)
        q = qs['q'][0]
        ids = get_ids_multi(q, self._popular, self.cw)
        self.print_(f'ids: {len(ids)}')
        max_pid = get_max_range(self.cw)

        def foo(id, p):
            d = {
                'id': id,
                'page?': f'_p{p}' if p else '',
                }
            filename_guess_base = utils.format('nozomi', d, '.webp')
            return os.path.join(utils.dir(self.type, self.name, self.cw), filename_guess_base)

        for id in ids:
            if os.path.isfile(foo(id, 0)):
                p = 0
                while True:
                    filename_guess = foo(id, p)
                    if not os.path.isfile(filename_guess):
                        break
                    self.urls.append(filename_guess)
                    p += 1
            else:
                file = File_nozomi({'id': id, 'url': f'https://nozomi.la/post/{id}.html', 'referer': self.url})
                self.urls.append(file)
            if len(self.urls) >= max_pid:
                break
        self.title = self.name


@lock
def get_ids(q, popular, cw):
    check_alive(cw)
    if q is None:
        if popular:
            url_api = 'https://j.nozomi.la/index-Popular.nozomi'
        else:
            url_api = 'https://j.nozomi.la/index.nozomi'
    else:
        q = q.replace('/', '') #5146
        if popular:
            url_api = 'https://j.nozomi.la/nozomi/popular/{}-Popular.nozomi'.format(quote(q))
        else:
            url_api = 'https://j.nozomi.la/nozomi/{}.nozomi'.format(quote(q))
    #print_(url_api)
    f = BytesIO()
    downloader.download(url_api, referer='https://nozomi.la/', buffer=f)
    data = f.read()
    ids = []
    for i in range(0, len(data), 4):
        crop = data[i:i+4]
        id = crop[0]*16777216 + crop[1]*65536 + crop[2]*256 + crop[3]
        ids.append(id)
    return ids


def get_ids_multi(q, popular, cw=None):
    print_ = get_print(cw)
    max_pid = get_max_range(cw)
    qs = q.split(' ')
    qs_pos = [q for q in qs if not q.startswith('-')]
    qs_neg = [q[1:] for q in qs if q.startswith('-')]
    q = qs_pos[0] if qs_pos else None
    ids = get_ids(q, popular, cw)
    print_('{}: {}'.format(q, len(ids)))

    # Positive
    for q in qs_pos[1:]:
        ids_ = get_ids(q, popular, cw)
        set_ids_ = set(ids_)
        ids_old = ids
        ids = []
        for id in ids_old:
            if id in set_ids_:
                ids.append(id)
        print_('{}: {} ({})'.format(q, len(ids_), len(ids)))

    # Negative
    for q in qs_neg:
        ids_ = get_ids(q, popular, cw)
        set_ids_ = set(ids_)
        ids_old = ids
        ids = []
        for id in ids_old:
            if id not in set_ids_:
                ids.append(id)
        print_('-{}: {} ({})'.format(q, len(ids_), len(ids)))
    return ids[:max_pid]

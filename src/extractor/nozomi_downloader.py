import downloader
from urllib.parse import quote
from io import BytesIO
from utils import Downloader, query_url, LazyUrl, get_ext, urljoin, clean_title, check_alive, lock, get_print, get_max_range
import errors
from translator import tr_


class Image:

    def __init__(self, id, referer):
        self._id = id
        self.url = LazyUrl(referer, self.get, self)

    def get(self, referer):
        # https://j.nozomi.la/nozomi.js
        s_id = str(self._id)
        url_post = 'https://j.nozomi.la/post/{}/{}/{}.json'.format(s_id[-1], s_id[-3:-1], self._id)
        j = downloader.read_json(url_post, referer)
        url = urljoin(referer, j['imageurl'])
        ext = get_ext(url)
        self.filename = '{}{}'.format(self._id, ext)
        return url



class Downloader_nozomi(Downloader):
    type = 'nozomi'
    URLS = ['nozomi.la']
    display_name = 'Nozomi.la'
    MAX_CORE = 15
    ACC_MTIME = True

    @classmethod
    def fix_url(cls, url):
        return url.split('#')[0]

    @property
    def name(self):
        qs = query_url(self.url)
        name = qs['q'][0]
        if self._popular:
            name += ' - Popular'
        return name

    def read(self):
        if '/post/' in self.url:
            raise errors.Invalid(tr_('개별 다운로드는 지원하지 않습니다: {}').format(self.url))
        self._popular = 'search-Popular.' in self.url
        self.title = clean_title(self.name)
        qs = query_url(self.url)
        q = qs['q'][0]
        for id in get_ids_multi(q, self._popular, self.cw):
            img = Image(id, self.url)
            self.urls.append(img.url)


@lock
def get_ids(q, popular, cw):
    check_alive(cw)
    if q is None:
        if popular:
            url_api = 'https://j.nozomi.la/index-Popular.nozomi'
        else:
            url_api = 'https://j.nozomi.la/index.nozomi'
    else:
        if popular:
            url_api = 'https://j.nozomi.la/nozomi/popular/{}-Popular.nozomi'.format(quote(q))
        else:
            url_api = 'https://j.nozomi.la/nozomi/{}.nozomi'.format(quote(q))
    print(url_api)
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

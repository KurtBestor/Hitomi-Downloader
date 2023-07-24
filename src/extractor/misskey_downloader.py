from utils import Downloader, Session, clean_title, get_ext, errors, check_alive, tr_, try_n, File
import downloader
import ree as re
from ratelimit import limits, sleep_and_retry
from datetime import datetime
import utils
DOMAIN = 'misskey.io'
SUBFOLDER = True
if not utils.SD.get('misskey', {}).get('format'):
    utils.SD.setdefault('misskey', {})
    utils.SD['misskey']['format'] = '[date] id_ppage'


def get_file(nid, url, referer, session, p, time):
    ext = get_ext(url) or downloader.get_ext(url, session, referer)
    date = datetime.fromtimestamp(float(time))
    date = date.strftime('%y-%m-%d') # local time
    filename = utils.SD['misskey']['format'].replace('date', date).replace('id', str(nid)).replace('page', str(p)) + ext
    info = {'name': filename, 'url': url, 'referer': referer}
    return File(info)


def get_time(note):
    ds = note['createdAt']
    time = datetime.strptime(ds.split('.')[0], '%Y-%m-%dT%H:%M:%S')
    time = (time-datetime(1970,1,1)).total_seconds()
    return time


class Downloader_misskey(Downloader):
    type = 'misskey'
    URLS = [f'{DOMAIN}/notes/', f'{DOMAIN}/@']
    display_name = 'Misskey'
    ACCEPT_COOKIES = [rf'(.*\.)?{DOMAIN}']
    MAX_CORE = 8

    @classmethod
    def fix_url(cls, url):
        if DOMAIN.lower() in url.lower() and '://' not in url:
            url = 'https://' + url
        if url.startswith('@'):
            url = f'https://{DOMAIN}/{url}'
        return url

    def init(self):
        self.session = Session()

    @try_n(4, sleep=5)
    @sleep_and_retry
    @limits(1, 2)
    def call(self, path, payload):
        token = self.session.cookies.get('token', domain=DOMAIN)
        url_api = f'https://{DOMAIN}/api/{path}'
        if token:
            payload['i'] = token
        r = self.session.post(url_api, json=payload)
        d = r.json()
        if isinstance(d, dict):
            err = d.get('error')
            if err:
                raise errors.Invalid(err['message'])
        return d

    def read(self):
        nid = re.find(rf'{DOMAIN}/notes/([^/]+)', self.url)
        if nid:
            self.single = True
            data = {'noteId':nid,
                    }
            note = self.call('notes/show', data)
            username = note['user']['username']
            self.artist = note['user']['name'] or username
            host = note['user']['host']
            if host:
                username += f'@{host}'
            self.title = f'{clean_title(self.artist)} (misskey_@{username})'
            time = get_time(note)
            for file in note['files']:
                file = get_file(note['id'], file['url'], self.url, self.session, len(self.urls), time)
                if SUBFOLDER:
                    file['name'] = self.title + '/' + file['name']
                self.urls.append(file)
        else:
            username = re.find(rf'{DOMAIN}/@([a-zA-Z0-9_@\.]+)', self.url, err='no username')
            if '@' in username:
                username, host = username.split('@')
            else:
                host = None
            data = {"username":username,
                    "host":host,
                    }
            d = self.call('users/show', data)
            username = d['username']
            self.artist = d['name'] or username
            host = d['host'] or None
            if host:
                username += f'@{host}'
            uid = d['id']
            self.title = title = f'{clean_title(self.artist)} (misskey_@{username})'
            untilId = None
            nids = set()
            while check_alive(self.cw):
                data = {"userId":uid,
                        "limit":30,
                        }
                if untilId:
                    data["untilId"] = untilId
                d = self.call('users/notes', data)
                if not d:
                    break
                for note in d:
                    nid = note['id']
                    if nid in nids:
                        continue
                    nids.add(nid)
                    time = get_time(note)
                    url_note = f'https://{DOMAIN}/notes/{nid}'
                    for p, file in enumerate(note['files']):
                        file = get_file(note['id'], file['url'], url_note, self.session, p, time)
                        self.urls.append(file)
                    untilId = nid
                self.cw.setTitle(f'{tr_("읽는 중...")}  {title} - {len(self.urls)}')
            self.title = title

#coding:utf8
import downloader
from translator import tr_
from utils import Soup, Session, query_url, get_max_range, Downloader, clean_title, update_url_query, get_print, get_ext, LazyUrl
import ree as re
import errors
from ratelimit import limits, sleep_and_retry
from error_printer import print_error


class Image(object):

    def __init__(self, url, id, referer, p, cw=None):
        self._url = url
        self.id_ = id
        self.p = p
        self.cw = cw
        self.url = LazyUrl(referer, self.get, self)

    @sleep_and_retry
    @limits(4, 1)
    def get(self, _):
        print_ = get_print(self.cw)
        url = self._url
        ext = get_ext(url)
        if ext.lower()[1:] not in ['jpg', 'png', 'mp4']: #4645
            print_('get_ext: {}, {}'.format(self.id_, url))
            try:
                ext = downloader.get_ext(url, referer=_)
            except Exception as e: #3235
                print_('Err: {}, {}\n'.format(self.id_, url)+print_error(e)[0])
        self.filename = '{}_p{}{}'.format(self.id_, self.p, ext)
        return url


@Downloader.register
class Downloader_tumblr(Downloader):
    type = 'tumblr'
    URLS = ['tumblr.com']
    MAX_CORE = 4

    def init(self):
        if u'tumblr.com/post/' in self.url:
            raise errors.Invalid(tr_(u'개별 다운로드는 지원하지 않습니다: {}').format(self.url))        
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        id = get_id(url)
        return 'https://{}.tumblr.com'.format(id)

    def read(self):
        username = get_id(self.url)
        name = get_name(username, self.session)
        
        for img in get_imgs(username, self.session, cw=self.cw):
            self.urls.append(img.url)

        self.title = clean_title('{} (tumblr_{})'.format(name, username))



class TumblrAPI(object):
    _url_base = 'https://www.tumblr.com/api'
    _hdr = {
        'referer': 'https://www.tumblr.com',
        'authorization': 'Bearer aIcXSOoTtqrzR8L8YEIOmBeW94c3FmbSNSWAUbxsny9KKx5VFh',
        }
    _qs = {
    'fields[blogs]': 'name,avatar,title,url,is_adult,?is_member,description_npf,uuid,can_be_followed,?followed,?advertiser_name,is_paywall_on,theme,subscription_plan,?primary,share_likes,share_following,can_subscribe,subscribed,ask,?can_submit,?is_blocked_from_primary,?tweet,?admin,can_message,?analytics_url,?top_tags,paywall_access',
    'npf': 'true',
    'reblog_info': 'false',
    'include_pinned_posts': 'false',
    #'page_number': None,
    }

    def __init__(self, session, cw=None):
        self.session = session
        self.cw = cw

    def print_(self, s):
        get_print(self.cw)(s)

    @sleep_and_retry
    @limits(1, 1)
    def call(self, path, qs, default_qs=True):
        if default_qs:
            qs_new = qs
            qs = self._qs.copy()
            qs.update(qs_new)
        url = self._url_base + path
        url = update_url_query(url, qs)
        r = self.session.get(url, headers=self._hdr)
        data = r.json()
        errs = data.get('errors', [])
        if errs:
            code = int(errs[0]['code'])
            if code == 0:
                raise Exception('Not found')
            elif code == 4012:
                raise errors.LoginRequired(errs[0]['detail'])
        r.raise_for_status()
        return data['response']

    def name(self, username):
        path = '/v2/blog/{}/posts'.format(username)
        data = self.call(path, {})
        return data['blog']['title'] or data['blog']['name']

    def posts(self, username):
        path = '/v2/blog/{}/posts'.format(username)
        qs = {}
        ids = set()
        default_qs = True
        while True:
            if self.cw and not self.cw.alive:
                break
            data = self.call(path, qs, default_qs=default_qs)
            for post in (post for post in data['posts'] if post['object_type'] != 'backfill_ad'):
                id_ = post['id']
                if id_ in ids:
                    self.print_('duplicate: {}'.format(id_))
                    continue
                ids.add(id_)
                url = 'https://{}.tumblr.com/post/{}'.format(username, id_)
                yield Post(post, url, self.cw)
            try:
                links = data.get('links') or data['_links']
                path_next = links['next']['href']
            except:
                path_next = None
            if path_next:
                path = path_next
                default_qs = False
            else:
                break


class Post(object):

    def __init__(self, data, url, cw=None):
        id_ = data['id']
        self.imgs = []
        
        cs = data['content']
        for trail in data['trail']:
            cs += trail['content']
            
        for c in cs:
            if c['type'] in ['image', 'video']:
                media = c.get('media')
                if not media: #2859
                    continue
                if isinstance(media, list):
                    media = media[0]
                img = media['url']
                self.imgs.append(Image(img, id_, url, len(self.imgs), cw))
            elif c['type'] in ['text', 'link', 'audio']:
                continue
            else:
                raise NotImplementedError(id_, c)
            


def get_name(username, session):
    return TumblrAPI(session).name(username)


def get_imgs(username, session, cw=None):
    print_ = get_print(cw)
    artist = get_name(username, session)
    imgs = []
    error_count = 0
    max_pid = get_max_range(cw)
    api = TumblrAPI(session, cw)
    for post in api.posts(username):
        imgs += post.imgs

        s = '{}  {} (tumblr_{}) - {}'.format(tr_(u'\uc77d\ub294 \uc911...'), artist, username, len(imgs))
        if cw:
            if not cw.alive:
                return
            cw.setTitle(s)
        else:
            print(s)
            
        if len(imgs) > max_pid:
            break

    return imgs[:max_pid]


def get_id(url):
    if '/dashboard/blog/' in url:
        url = re.find('/dashboard/blog/([0-9a-zA-Z_-]+)', url)
    if '/login_required/' in url:
        url = url.split('/login_required/')[1].split('?')[0].split('/')[0]
    if 'tumblr.com/blog/view/' in url:
        url = url.split('tumblr.com/blog/view/')[1]
    if 'tumblr.com' in url:
        if 'www.tumblr.com' in url:
            qs = query_url(url)
            url = qs.get('url', [url])[0]
        url = url.split('.tumblr.com')[0].split('/')[(-1)]
    if url == 'www':
        raise Exception('no id')
    return url
    

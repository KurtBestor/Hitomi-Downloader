#coding:utf8
import downloader
from timee import sleep, clock
from constants import clean_url
from utils import Downloader, LazyUrl, urljoin, get_max_range, Soup, Session, update_url_query, get_print, cut_pair, get_ext, clean_title, lazy, try_n, generate_csrf_token, check_alive
import urllib
from error_printer import print_error
import os, requests
from translator import tr_
import json
from datetime import datetime
import hashlib
import ree as re
from ratelimit import limits, sleep_and_retry
import clf2
import errors
FORMAT_PIN = r'/p/([0-9a-zA-Z-_]+)'


def get_session(url, cw=None):
    #res = clf2.solve(url, cw=cw)
    #return res['session']
    session = Session()
    sessionid = session.cookies._cookies.get('.instagram.com', {}).get('/',{}).get('sessionid')
    if sessionid is None or sessionid.is_expired():
        raise errors.LoginRequired()
    session.headers['User-Agent'] = downloader.hdr['User-Agent']
    if not session.cookies.get('csrftoken', domain='.instagram.com'):
        csrf_token = generate_csrf_token()
        print('csrf:', csrf_token)
        session.cookies.set("csrftoken", csrf_token, domain='.instagram.com')
    return session


@Downloader.register
class Downloader_insta(Downloader):
    type = 'insta'
    URLS = ['instagram.com']
    MAX_CORE = 8
    display_name = 'Instagram'

    def init(self):
        self.session = get_session(self.url, self.cw)
        if '/p/' in self.url:
            self.print_('single post')
        elif '/stories/' in self.url:
            self.print_('stories')
        elif 'instagram.com' in self.url:
            self.url = u'https://www.instagram.com/{}'.format(self.username)

    @lazy
    def username(self):
        return get_username(self.url)

    @classmethod
    def fix_url(cls, url):
        if 'instagram.com' not in url:
            url = u'https://www.instagram.com/{}'.format(url)
        return url.split('?')[0].split('#')[0].strip('/')

    @classmethod
    def key_id(cls, url):
        return url.replace('://www.', '://')

    @lazy
    def name(self):
        return get_name(self.url)

    @property
    def id_(self):
        return u'{} (insta_{})'.format(clean_title(self.name), self.username)

    def read(self):
        cw = self.cw
        title = self.id_
        self.title = title
        self.artist = self.name
        ui_setting = self.ui_setting

        if '/p/' in self.url:
            self.print_('single')
            iter = get_imgs_single(self.url, self.session, cw=cw)
        elif '/stories/highlights/' in self.url:
            iter = get_stories_single(self.url, session=self.session, cw=cw)
        else:
            s = ui_setting.instaStories.isChecked()
            self.print_('stories: {}'.format(s))
            iter = get_imgs_all(self.url, title, session=self.session, cw=cw, d=self, stories=s)

        imgs = []
        for img in iter:
            if cw and not cw.alive:
                return
            self.urls.append(img.url)

        self.title = title


def get_j(script):
    s = script.string
    if not s:
        return

    try:
        s = s.replace('window._sharedData', '').strip()[1:-1].strip()
        j = json.loads(s)
        return j
    except ValueError as e:
        pass


def read_html(url, session, cw):
    #res = clf2.solve(url, session=session, cw=cw)#
    #return res['html']
    return downloader.read_html(url, session=session)


def check_error(soup, cw, wait):
    print_ = get_print(cw)
    
    err = soup.find('div', class_='error-container')
    if err:
        err = err.text.strip()
        if wait:
            print_('err: {}'.format(err))
            sleep(60*30, cw)
        else:
            raise Exception(err)
        

def get_sd(url, session=None, html=None, cw=None, wait=True):
    print_ = get_print(cw)

    if html:
        soup = Soup(html)
        check_error(soup, cw, wait)
        for script in soup.findAll('script'):
            j = get_j(script)
            if j:
                break
        else:
            raise Exception('no _sharedData!!')
    else:
        for try_ in range(4):
            _wait(cw)
            html = read_html(url, session, cw)
            soup = Soup(html)
            check_error(soup, cw, wait)
            for script in soup.findAll('script'):
                j = get_j(script)
                if j:
                    break
            else:
                continue
            break
        else:
            raise Exception('no _sharedData')
    for script in soup.findAll('script'):
        s = script.string
        if s and 'window.__additionalDataLoaded('  in s:
            s = cut_pair(s)
            j_add = json.loads(s)
            try:
                j['entry_data']['PostPage'][0].update(j_add)
            except:
                j['entry_data']['ProfilePage'][0].update(j_add) #2900

    # Challenge
    challenge = j['entry_data'].get('Challenge')
    if challenge:
        for cont in challenge[0]['extraData']['content']:
            title = cont.get('title')
            if title:
                break
        else:
            title = 'Err'
        raise errors.LoginRequired(title)

    # LoginAndSignupPage
    login = j['entry_data'].get('LoginAndSignupPage')
    if login:
        raise errors.LoginRequired()
    
    return j


def get_id(url):
    j = get_sd(url)
    if '/p/' in url:
        id = j['entry_data']['PostPage'][0]['graphql']['shortcode_media']['owner']['id']
    elif '/stories/' in url:
        id = j['entry_data']['StoriesPage'][0]['user']['username'] # ???
    else:
        id = j['entry_data']['ProfilePage'][0]['graphql']['user']['id']
    return id



def get_username(url):
    j = get_sd(url, wait=False)
    if '/p/' in url:
        id = j['entry_data']['PostPage'][0]['graphql']['shortcode_media']['owner']['username']
    elif '/stories/' in url:
        id = j['entry_data']['StoriesPage'][0]['user']['username']
    else:
        id = j['entry_data']['ProfilePage'][0]['graphql']['user']['username']
    return id


def get_name(url):
    j = get_sd(url)
    if '/p/' in url:
        name = j['entry_data']['PostPage'][0]['graphql']['shortcode_media']['owner']['full_name']
    elif '/stories/' in url:
        id = get_id(url)
        url = 'https://www.instagram.com/{}/'.format(id)
        return get_name(url)
    else:
        name = j['entry_data']['ProfilePage'][0]['graphql']['user']['full_name']
    return name


class Image(object):

    def __init__(self, url, referer, filename, id=None):
        self._url = url
        self.url = LazyUrl(referer, self.get, self)
        self.filename = filename
        self.id = id

    def get(self, referer):
        wait_download()
        return self._url


class Image_lazy(object):

    def __init__(self, url, session=None, cw=None):
        self.url = url
        self.session = session
        self.cw = cw

        self.url = LazyUrl(url, self.get, self)

    @try_n(4)
    def get(self, url):
        cw = self.cw
        if cw and not cw.alive:
            raise Exception('cw is dead')
        node = Node(url, session=self.session, cw=cw)
        img = node.imgs[0]
        ext = os.path.splitext(url)[1]
        wait_download()
        url_img = img.url()
        self.filename = img.filename
        return url_img


@sleep_and_retry
@limits(1, 10)
def _wait(cw=None):
    if cw and not cw.alive:
        raise Exception('cw is dead while waiting')


##@sleep_and_retry
##@limits(1, 1)
def wait_download():
    pass


@try_n(2)
def get_query(query_hash, variables, session, cw=None):
    _wait(cw)
    print_ = get_print(cw)
    csrf_token = session.cookies.get('csrftoken', domain='.instagram.com')
    if not csrf_token:
        raise Exception('no csrftoken')
    hdr = {
            "X-CSRFToken"     : csrf_token, #2849
            "X-IG-App-ID"     : "936619743392459",
            "X-IG-WWW-Claim"  : "0",
            "X-Requested-With": "XMLHttpRequest",
        }
    url_ = update_url_query('https://www.instagram.com/graphql/query/', {'query_hash': query_hash, 'variables': json.dumps(variables)})
    #print(len(edges), url_)
    r = session.get(url_, headers=hdr)
    try:
        j = json.loads(r.text)
    except Exception as e:
        print(e)
        j = {}
    if not j or j.get('status') == 'fail':
        msg = 'Fail: {} {}'.format(j.get('message') or 'Please wait a few minutes before you try again.', variables)
        print_(msg)
        sleep(60*30, cw)
        raise Exception(msg)
    return j


def get_imgs(url, n_max=2000, title=None, cw=None, session=None):
    print_ = get_print(cw)

    for try_ in range(4):
        try:
            html = read_html(url, session, cw)
            m = re.search('"edge_owner_to_timeline_media":{"count":([0-9]+)', html)
            if m is None:
                raise Exception('Invalid page')
            break
        except Exception as e:
            e_ = e
            print_(print_error(e)[0])
    else:
        raise e_
    n = int(m.groups()[0])
    n = min(n, n_max)

    data = get_sd(url, html=html, cw=cw)

    uploader_id = data['entry_data']['ProfilePage'][0]['graphql']['user']['id']
    csrf_token = data['config']['csrf_token']#
    session.cookies.set(name='ig_pr', value='1', path='/', domain='.instagram.com')

    cursor = ''
    edges = []
    bad = 0
    while True:
        check_alive(cw)

        variables = {
                    'id': uploader_id,
                    'first': 12,
                }
        if cursor:
            variables['after'] = cursor
        #print_(variables)#

        media = None
        try:
            j = get_query('003056d32c2554def87228bc3fd9668a', variables, session, cw)
            media = j['data']['user']['edge_owner_to_timeline_media']
            sleep(2)#
        except Exception as e:
            if bad > 10:
                raise Exception('no media')
            else:
                print_(u'no media.. retry... ({}) {}'.format(bad+1, print_error(e)[0]))
                sleep(12*bad, cw)
                bad += 1
                continue
        bad = 0

        edges_new = media.get('edges')
        if not edges_new or not isinstance(edges_new, list):
            print('no edges_new')
            break

        edges += edges_new

        s = u'{} {}  ({}/{})'.format(tr_(u'읽는 중...'), title, len(edges), n)
        if cw is not None:
            cw.setTitle(s)
            if not cw.alive:
                return []
        else:
            print(s)

        if len(edges) >= n:
            break

        page_info = media.get('page_info')
        if not page_info:
            break
        if not page_info.get('has_next_page'):
            break
        cursor = page_info.get('end_cursor')
        if not cursor:
            break

    if len(edges) <= n/2:
        raise Exception(u'Too short: {} / {}'.format(len(edges), n))

    imgs = []
    for edge in edges:
        node = edge['node']
        type = node['__typename']
        id = node['shortcode']
        url = u'https://www.instagram.com/p/{}/'.format(id)
##        if type in ['GraphVideo', 'GraphImage']:
##            single = True
##        else:
##            single = False
        for img in Node(url, session=session, cw=cw, media=node).imgs:
            imgs.append(img)
        if len(imgs) >= n_max:
            break

    return imgs


class Node(object):

    def __init__(self, url, format=u'[%y-%m-%d] id_ppage', session=None, cw=None, media=None):
        print('Node', url)
        print_ = get_print(cw)
        self.id = re.search(FORMAT_PIN, url).groups()[0]
        self.imgs = []
        self.session = session

        if not media:
            if False: # Original
                j = get_sd(url, self.session, cw=cw)
                data = j['entry_data']['PostPage'][0]['graphql']
            else:
                variables = {
                    "shortcode"            : self.id,
                    "child_comment_count"  : 3,
                    "fetch_comment_count"  : 40,
                    "parent_comment_count" : 24,
                    "has_threaded_comments": True,
                    }
                j = get_query('a9441f24ac73000fa17fe6e6da11d59d', variables, session, cw)
                data = j['data']
            media = data['shortcode_media']

        if 'video_url' in media:
            urls = [
             media['video_url']]
        elif 'edge_sidecar_to_children' in media:
            edges = media['edge_sidecar_to_children']['edges']
            urls = []
            for edge in edges:
                node = edge['node']
                if 'video_url' in node:
                    url_ = node['video_url']
                else:
                    url_ = node['display_resources'][(-1)]['src']
                urls.append(url_)
        else:
            urls = [media['display_resources'][(-1)]['src']]
        time = media['taken_at_timestamp']

        self.date = datetime.fromtimestamp(time)
        self.timeStamp = self.date.strftime(format).replace(':', u'\uff1a')
        for p, img in enumerate(urls):
            ext = os.path.splitext(img.split('?')[0].split('#')[0])[1]
            filename = ('{}{}').format(self.timeStamp, ext).replace('id', str(self.id)).replace('page', str(p))
            img = Image(img, url, filename)
            self.imgs.append(img)


def get_imgs_all(url, title=None, cw=None, d=None, session=None, stories=True):
    max_pid = get_max_range(cw)
    url = clean_url(url)
    if stories:
        imgs_str = get_stories(url, title, cw=cw, session=session)
    else:
        imgs_str = []
    max_pid = max(0, max_pid - len(imgs_str))
    imgs = get_imgs(url, max_pid, title=title, cw=cw, session=session)

    return imgs_str + imgs[:max_pid]


def get_imgs_single(url, session=None, cw=None):
    node = Node(url, session=session, cw=cw)
    return node.imgs


def get_stories(url, title=None, cw=None, session=None):
    print_ = get_print(cw)

    html = downloader.read_html(url, session=session)

    data = get_sd(url, html=html, cw=cw)

    uploader_id = data['entry_data']['ProfilePage'][0]['graphql']['user']['id']
    csrf_token = data['config']['csrf_token']#
    session.cookies.set(name='ig_pr', value='1', path='/', domain='.instagram.com')

    print('uploader_id:', uploader_id)
    variables = {
        'user_id': uploader_id,
        'include_chaining': True,
        'include_reel': True,
        'include_suggested_users': False,
        'include_logged_out_extras': False,
        'include_highlight_reels': True,
        'include_live_status': True,
        }
    j = get_query('d4d88dc1500312af6f937f7b804c68c3', variables, session, cw) 

    imgs = []
    ids = set()

    data = j['data']
    hs = data['user']['edge_highlight_reels']
    edges = hs['edges']
    edges.insert(0, str(uploader_id))
    for i, edge in enumerate(edges):
        if isinstance(edge, str):
            id = edge
            hid = None
            url_str = url
        else:
            id = None
            hid = edge['node']['id']
            url_str = 'https://www.instagram.com/stories/highlights/{}/'.format(hid)
        try:
            imgs_new = get_stories_single(url_str, id=id, cw=cw, session=session)
            for img in imgs_new:
                if img.id in ids:
                    print('duplicate: {}'.format(img.id))
                    continue
                ids.add(img.id)
                imgs.append(img)
            print_('stories: {}'.format(hid))
        except Exception as e:
            print_(u'Failed to get stories: {}'.format(hid))
            print(e)
        msg = u'{} {}  ({}/{})'.format(tr_(u'스토리 읽는 중...'), title, i+1, len(edges))
        if cw:
            if not cw.alive:
                return
            cw.setTitle(msg)
        else:
            print(msg)
    imgs = sort_str(imgs)
    return imgs


def sort_str(imgs):
    imgs = sorted(imgs, key=lambda img: int(img.id), reverse=True)
    return imgs


def get_stories_single(url, id=None, cw=None, session=None):
    j = get_sd(url, session=session, cw=cw)
    hid = re.find('/stories/highlights/([0-9]+)', url)
    reel_ids = []
    highlight_reel_ids = []
    if hid is None:
        if id is None:
            id = get_id(url) # ???
        reel_ids.append(str(id))
    else:
        highlight_reel_ids.append(str(hid))
    print(id, hid)
    variables = {
        "reel_ids":reel_ids,
        "tag_names":[],
        "location_ids":[],
        "highlight_reel_ids":highlight_reel_ids,
        "precomposed_overlay":False,
        "show_story_viewer_list":True,
        "story_viewer_fetch_count":50,
        "story_viewer_cursor":"",
        "stories_video_dash_manifest":False
        }
    print(variables)
    j = get_query('f5dc1457da7a4d3f88762dae127e0238', variables, session, cw)
    data = j['data']
    m = data['reels_media'][0]
    items = m['items']
    if not items:
        raise Exception('no items')
    imgs = []
    for item in items:
        id = item['id']
        rs = item.get('video_resources') or item['display_resources']
        r = rs[-1]
        src = r['src']
        ext = get_ext(src)
        filename = u'stories_{}{}'.format(id, ext)
        img = Image(src, url, filename, id=id)
        imgs.append(img)
    imgs = sort_str(imgs)
    return imgs

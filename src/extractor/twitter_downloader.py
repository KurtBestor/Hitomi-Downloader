#coding:utf8
from __future__ import division, print_function, unicode_literals
import downloader
from utils import Downloader, Session, LazyUrl, get_ext, try_n, Soup, get_print, update_url_query, urljoin, try_n, get_max_range, get_outdir, clean_title, lock, check_alive, check_alive_iter, SkipCounter
from timee import time, sleep
import json
import ree as re
from datetime import datetime, timedelta
from translator import tr_
from error_printer import print_error
import os
import ytdl
import ffmpeg
from ratelimit import limits, sleep_and_retry
import options
AUTH = "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
UA = "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko"
#UA = downloader.hdr['User-Agent']#
RETRY_PAGINATION = 21
RETRY_MORE = 3
RETRY_MORE_IMGS = 16
TIMEOUT_GUEST_TOKEN = 3600
CACHE_GUEST_TOKEN = None


def change_ua(session):
    session.headers['User-Agent'] = downloader.ua.random


def get_session():
    session = Session()
    session.headers['User-Agent'] = UA
    session.cookies['app_shell_visited'] = '1'
    return session


def suitable(url):
    if 'twitter.com' not in url.lower():
        return False
    if '/i/broadcasts/' in  url: # Etc
        return False
    return True


@Downloader.register
class Downloader_twitter(Downloader):
    type = 'twitter'
    URLS = [suitable]
    MAX_CORE = 8
    #MAX_SPEED = 4.0

    def init(self):
        self.session = get_session()
        #self.url = fix_url(self.url)
        self.artist, self.username = get_artist_username(self.url, self.session, self.cw)
        if self.username == 'home':
            raise Exception('No username: home')

    @classmethod
    def fix_url(cls, url):
        username = re.find(r'twitter.com/([^/]+)/media', url)
        if username:
            url = username
        if 'twitter.com/' in url and not re.find('^https?://', url): #3165; legacy
            url = 'https://' + url
        if not re.find('^https?://', url):
            url = 'https://twitter.com/{}'.format(url.lstrip('@'))
        return url.split('?')[0].split('#')[0].strip('/')

    @classmethod
    def key_id(cls, url):
        return url.lower()

    def read(self):
        ui_setting = self.ui_setting

        title = '{} (@{})'.format(clean_title(self.artist), self.username)

        types = {'img', 'video'}
        if ui_setting.exFile.isChecked():
            if ui_setting.exFileImg.isChecked():
                types.remove('img')
            if ui_setting.exFileVideo.isChecked():
                types.remove('video')

        if '/status/' in self.url:
            self.print_('single tweet')
            imgs = get_imgs_single(self.url, self.session, types, cw=self.cw)
        else:
            self.print_('multiple tweets')
            imgs = get_imgs(self.username, self.session, title, types, cw=self.cw)
        for img in imgs:
            if isinstance(img, Image):
                self.urls.append(img.url)
            else:
                self.urls.append(img)

        self.title = title
        #self.session = None#


@lock
def _guest_token(session, headers, cache=True, cw=None):
    global CACHE_GUEST_TOKEN
    print_ = get_print(cw)
    token = None
    if cache:
        if CACHE_GUEST_TOKEN and time() - CACHE_GUEST_TOKEN[1] < TIMEOUT_GUEST_TOKEN:
            token = CACHE_GUEST_TOKEN[0]
    if token is None:
        print('!!! get guest_token')
        name = 'x-guest-token'
        if name in headers:
            del headers[name]
        r = session.post('https://api.twitter.com/1.1/guest/activate.json', headers=headers)
        data = json.loads(r.text)
        token = data['guest_token']
        print_('token type: {}'.format(type(token)))
        if isinstance(token, int): #3525
            token = str(token)
        CACHE_GUEST_TOKEN = token, time()
    return token


class TwitterAPI(object):
    def __init__(self, session, cw=None, cache_guest_token=True):
        self.session = session
        self.cw = cw
        hdr = {
            "authorization": AUTH,
            "x-twitter-client-language": "en",
            "x-twitter-active-user": "yes",
            "Origin": "https://twitter.com",
            }
        session.headers.update(hdr)

        auth_token = session.cookies.get("auth_token", domain=".twitter.com")
        if auth_token:
            session.headers["x-twitter-auth-type"] = "OAuth2Session"
            print('auth_token:', auth_token)
        else:
            # guest token
            guest_token = _guest_token(session, session.headers, cache=cache_guest_token, cw=cw)
            session.headers["x-guest-token"] = guest_token
            session.cookies.set("gt", guest_token, domain=".twitter.com")
            print('guest_token:', guest_token)

        self.params = {
            "include_profile_interstitial_type": "1",
            "include_blocking": "1",
            "include_blocked_by": "1",
            "include_followed_by": "1",
            "include_want_retweets": "1",
            "include_mute_edge": "1",
            "include_can_dm": "1",
            "include_can_media_tag": "1",
            "skip_status": "1",
            "cards_platform": "Web-12",
            "include_cards": "1",
            "include_composer_source": "true",
            "include_ext_alt_text": "true",
            "include_reply_count": "1",
            "tweet_mode": "extended",
            "include_entities": "true",
            "include_user_entities": "true",
            "include_ext_media_color": "true",
            "include_ext_media_availability": "true",
            "send_error_codes": "true",
            "simple_quoted_tweet": "true",
            #  "count": "20",
            "count": "100",
            #"cursor": None,
            "ext": "mediaStats%2ChighlightedLabel%2CcameraMoment",
            "include_quote_count": "true",
        }

    @sleep_and_retry
    @limits(1, 2)
    def _call(self, url_api, referer='https://twitter.com', params=None):
        url_api = urljoin('https://api.twitter.com', url_api)
        if params:
            url_api = update_url_query(url_api, params)
        #print('call:', url_api)
        r = self.session.get(url_api, headers={'Referer': referer})
        csrf = r.cookies.get('ct0')
        if csrf:
            self.session.headers['x-csrf-token'] = csrf
        data = json.loads(r.text)
        return data

##    @sleep_and_retry
##    @limits(1, 36)
    def search(self, query, f='live'):
        endpoint = "2/search/adaptive.json"
        params = self.params.copy()
        params["q"] = query
        params["tweet_search_mode"] = f
        params["query_source"] = "typed_query"
        params["pc"] = "1"
        params["spelling_corrections"] = "1"
        return self._pagination(endpoint, params, "sq-I-t-", "sq-cursor-bottom")

    def user_by_screen_name(self, screen_name):
        url_api = "graphql/-xfUfZsnR_zqjFd-IfrN5A/UserByScreenName"
        params = {
            "variables": '{"screen_name":"' + screen_name + '"'
                         ',"withHighlightedLabel":true}'
        }
        return self._call(url_api, params=params)['data']['user']

    def tweet(self, id, referer):
        url_api = '/2/timeline/conversation/{}.json'.format(id)
        url_api += '?tweet_mode=extended'#
        return self._call(url_api, referer)

    def timeline_media(self, screen_name):
        user = self.user_by_screen_name(screen_name)
        url_api = "2/timeline/media/{}.json".format(user["rest_id"])
        url_api += '?tweet_mode=extended'#
        return self._pagination(url_api)

    def print_(self, s):
        get_print(self.cw)(s)

    def _pagination(self, url_api, params=None, entry_tweet="tweet-", entry_cursor="cursor-bottom-"):
        if params is None:
            params = self.params.copy()

        while True:
            cursor = None
            if params.get("cursor"):
                self.print_('cursor: {}'.format(params.get("cursor")))

            # 2303
            n_try = RETRY_PAGINATION
            for try_ in range(n_try):
                try:
                    data = self._call(url_api, params=params)
                    if 'globalObjects' not in data:
                        try_ = n_try
                        raise Exception(str(data['errors']))
                    tweets = data["globalObjects"]["tweets"]
                    break
                except Exception as e:
                    e_ = e
                    e_msg = print_error(e)[0]
                    if try_ < n_try - 1 :
                        self.print_('retry... _pagination ({})\n{}'.format(try_+1, e_msg))
                        sleep(30, self.cw)
            else:
                break#raise e_ #3392

            users = data["globalObjects"]["users"]
            for instr in data["timeline"]["instructions"]:
                for entry in instr.get("addEntries", {}).get("entries", []):
                    if entry["entryId"].startswith(entry_tweet):
                        tid = entry["content"]["item"]["content"]["tweet"]["id"]
                        if tid not in tweets:
                            self.print_("Skipping unavailable Tweet {}".format(tid))
                            continue
                        #print('tid:', tid)#
                        tweet = tweets[tid]
                        tweet["user"] = users[tweet["user_id_str"]]

                        yield tweet

                    elif entry["entryId"].startswith(entry_cursor):
                        cursor = entry["content"]["operation"]["cursor"]["value"]

                if not cursor or params.get('cursor') == cursor:
                    print('same cursor')
                    return
                params["cursor"] = cursor
            if params.get("cursor") is None: # nothing
                self.print_('no cursor')
                break


def get_imgs_single(url, session, types, format='[%y-%m-%d] id_ppage', cw=None):
    print_ = get_print(cw)
    id = re.find('/status/([0-9]+)', url)
    if id is None:
        raise Exception('no id')

    data = TwitterAPI(session, cw).tweet(id, url)

    tweets = data["globalObjects"]["tweets"]
    id = tweets[id].get('retweeted_status_id_str') or id
    tweet = tweets[id]

    time = get_time(tweet)

    img = Image(url, url, id, time, 0, format, cw, True, try_n=1, n_thread=4)
    try:
        img.url()
        return [img]
    except Exception as e:
        print(print_error(e)[-1])
        return get_imgs_from_tweet(tweet, session, types, format, cw)


def get_imgs(username, session, title, types, n=0, format='[%y-%m-%d] id_ppage', cw=None):
    print_ = get_print(cw)

    # Range
    n = max(n, get_max_range(cw))

    # 2303
    ids = set()
    names = dict()
    dir_ = os.path.join(get_outdir('twitter'), title)
    if os.path.isdir(dir_) and cw:
        for name in cw.names_old:
            name = os.path.basename(name)
            id_ = re.find('([0-9]+)_p', name)
            if id_ is None:
                continue
            if get_ext(name).lower() == '.mp4':
                type_ = 'video'
            else:
                type_ = 'img'
            if type_ not in types:
                continue
            id_ = int(id_)
            ids.add(id_)
            if id_ in names:
                names[id_].append(name)
            else:
                names[id_] = [name]
    ids_sure = sorted(ids)[:-100]
    max_id = max(ids_sure) if ids_sure else 0 #3201

    # 2303
    imgs_old = []
    for id_ in sorted(ids, reverse=True):
        for p, file in enumerate(sorted(os.path.join(dir_, name) for name in names[id_])):
            img = Image(file, '', id_, 0, p, format, cw, False)
            img.url = LazyUrl_twitter(None, lambda _: file, img)
            img.filename = os.path.basename(file)
            imgs_old.append(img)

    imgs_new = []
    enough = False
    c_old = 0
    counter = SkipCounter(1)
    msg = None
    for tweet in check_alive_iter(cw, TwitterAPI(session, cw).timeline_media(username)):
        id_ = int(tweet['id_str'])
        if id_ < max_id:
            print_('enough')
            enough = True
            break

        if id_ in ids:
            print_('duplicate: {}'.format(id_))
            c_old += 1
            continue
        ids.add(id_)

        imgs_new += get_imgs_from_tweet(tweet, session, types, format, cw)

        if len(imgs_new) + c_old >= n: #3201
            break

        if counter.next():
            msg = '{}  {} - {}'.format(tr_('읽는 중...'), title, len(imgs_new))
            if cw:
                cw.setTitle(msg)
            else:
                print(msg)
    if msg:
        if cw:
            cw.setTitle(msg)
        else:
            print(msg)

    if not enough and not imgs_new and c_old == 0:
        raise Exception('no imgs')

    imgs = sorted(imgs_old + imgs_new, key=lambda img: img.id, reverse=True)

    if len(imgs) < n:
        imgs = get_imgs_more(username, session, title, types, n, format, cw, imgs=imgs)

    return imgs[:n]


def get_imgs_more(username, session, title, types, n=None, format='[%y-%m-%d] id_ppage', cw=None, mode='media', method='tab', imgs=None):
    print_ = get_print(cw)
    imgs = imgs or []
    print_('imgs: {}, types: {}'.format(len(imgs), ', '.join(types)))

    artist, username = get_artist_username(username, session, cw)#

    # Range
    n = max(n or 0, get_max_range(cw))

    ids_set = set(img.id for img in imgs)

    count_no_tweets = 0
    count_no_imgs = 0

    while check_alive(cw) or len(imgs) < n:
        if options.get('experimental') or count_no_tweets: #2687, #3392
            filter_ = ''
        else:
            filter_ = ' filter:media'
        cache_guest_token = bool(count_no_tweets)

        if ids_set:
            max_id = min(ids_set) - 1
            q = 'from:{} max_id:{} exclude:retweets{} -filter:periscope'.format(username, max_id, filter_)
        else:
            q = 'from:{} exclude:retweets{} -filter:periscope'.format(username, filter_)
        print(q)

        tweets = []
        for tweet in list(TwitterAPI(session, cw, cache_guest_token).search(q)):
            id = int(tweet['id'])
            if id in ids_set:
                print_('duplicate: {}'.format(id))
                continue
            ids_set.add(id)
            tweets.append(tweet)

        if tweets:
            exists_more_imgs = False
            for tweet in tweets:
                imgs_tweet = get_imgs_from_tweet(tweet, session, types, format, cw)
                if imgs_tweet:
                    imgs += imgs_tweet
                    exists_more_imgs = True
            if exists_more_imgs:
                count_no_imgs = 0
            else:
                count_no_imgs += 1
                if count_no_imgs >= RETRY_MORE_IMGS: #4130
                    break
            count_no_tweets = 0
        else:
            count_no_tweets += 1
            change_ua(session)
            if count_no_tweets >= RETRY_MORE:
                break
            print_('retry... {}'.format(count_no_tweets))
            continue

        msg = '{}  {} (@{}) - {}'.format(tr_('읽는 중...'), artist, username, len(imgs))
        if cw:
            cw.setTitle(msg)
        else:
            print(msg)

    return imgs


def get_time(tweet):
    ds = tweet['created_at']
    z = re.find(r'[\+\-][0-9]+', ds)
    ds = re.sub(r'[\+\-][0-9]+', '', ds)
    time = datetime.strptime(ds.replace('  ', ' '), '%a %b %d %H:%M:%S %Y')
    time = (time-datetime(1970,1,1)).total_seconds()
    if z:
        time -= 3600*int(z)
    return time


def get_imgs_from_tweet(tweet, session, types, format, cw=None):
    print_ = get_print(cw)
    id = tweet['id_str']

    if 'extended_entities' not in tweet:
        tweet['extended_entities'] = {'media': []}

    media = tweet['extended_entities']['media']

    for url_ in tweet['entities'].get('urls', []):
        url_ = url_['expanded_url']
        if '//twitpic.com/' in url_:
            print_('twitpic: {}'.format(url_))
            try:
                url_ = get_twitpic(url_, session)
                media.append({'type': 'photo', 'media_url': url_, 'expanded_url': 'https://twitter.com'})
            except Exception as e:
                print_('Invalid twitpic')
                print_(print_error(e)[-1])

    time = get_time(tweet)

    imgs = []
    for m in media:
        type_ = m['type']
        if type_ == 'photo':
            type_ = 'img'
        elif type_ == 'animated_gif':
            type_ = 'video'
        if type_ not in types:
            continue
        if type_ == 'video':
            url_media = sorted(m['video_info']['variants'], key=lambda x: x.get('bitrate', 0))[-1]['url']
        elif type_ == 'img':
            url_media = m['media_url']
            if ':' not in os.path.basename(url_media):
                url_media += ':orig'
        else:
            raise NotImplementedError('unknown type')
        url = m['expanded_url']
        img = Image(url_media, url, id, time, len(imgs), format, cw, type_=='video')
        imgs.append(img)

    return imgs


@try_n(4)
def get_twitpic(url, session):
    html = downloader.read_html(url, session=session)
    soup = Soup(html)
    url = soup.find('img')['src']
    return url


@LazyUrl.register
class LazyUrl_twitter(LazyUrl):
    type = 'twitter'

    def dump(self):
        return {
            'url': self.image._url,
            'referer': self._url,
            'id': self.image.id,
            'time': self.image.time,
            'p': self.image.p,
            'format': self.image.format,
            'cw': LazyUrl.CW,
            'isVideo': self.image.isVideo,
                }

    @classmethod
    def load(cls, data):
        img = Image(data['url'], data['referer'], data['id'], data['time'], data['p'], data['format'], data['cw'], data['isVideo'])
        return img.url


class Url_alter(object):
    count = 0

    def __init__(self, url):
        urls = [url]
        if ':' in os.path.basename(url):
            urls.append(':'.join(url.split(':')[:-1]))
        base, _, fmt = url.rpartition('.')
        base += '?format=' + fmt.split(':')[0] + '&name='
        for name in ['orig', 'large']:
            urls.append(base + name)
        self.urls = urls

    def __call__(self):
        self.count += 1
        return self.urls[self.count%len(self.urls)]


class Image(object):
    _url_cache = None

    def __init__(self, url, referer, id, time, p, format, cw=None, isVideo=False, try_n=4, n_thread=1):
        self._url = url
        self.referer = referer
        self.id = int(id)
        self.time = time
        self.p = p
        self.n_thread = n_thread
        if isVideo:
            url_alter = self.get #4185
        else:
            url_alter = Url_alter(url)
        if isVideo and get_ext(url).lower() not in ['.mp4', '.m3u8']:
            get = self.get
        else:
            get = lambda _: self._url
        self.url = LazyUrl_twitter(referer, get, self, url_alter)
        self.format = format
        self.cw = cw
        self.isVideo = isVideo
        self.try_n = try_n
##        time_ms = (int(id) >> 22) + 1288834974657
##        time = time_ms / 1000 # GMT+0
        date = datetime.fromtimestamp(float(time))
        timeStamp = date.strftime(format).replace(':', '\uff1a') # local time
        ext = '.mp4' if isVideo else get_ext(url)
        self.filename = timeStamp.replace('id', str(id)).replace('page', str(p)) + ext

    @sleep_and_retry
    @limits(1, 5)
    def get(self, _=None):
        if self._url_cache:
            return self._url_cache
        print_ = get_print(self.cw)
        for try_ in range(self.try_n):
            try:
                d = ytdl.YoutubeDL(cw=self.cw)
                info = d.extract_info(self.referer)

                fs = info['formats']
                for f in fs:
                    print_('{} {} - {}'.format(f.get('height'), f['protocol'], f['url']))
                def key(f):
                    h = f.get('height', 0)
                    if not f['protocol'].startswith('http'):
                        h -= .1
                    return h
                for f in sorted(fs, key=key, reverse=True):
                    if downloader.ok_url(f['url'], self.referer): #4185
                        break
                    else:
                        print_('invalid video: {}'.format(f['url']))
                else:
                    raise Exception('no valid videos')
                url = f['url']
                ext = get_ext(url)
                self.ext = ext
                print_('get_video: {} {}'.format(url, ext))
                if ext.lower() == '.m3u8':
                    url = ffmpeg.Stream(url)
                    url._live = False
                self._url_cache = url
                return url
            except Exception as e:
                e_ = e
                msg = print_error(e)[0]
                print_('\nTwitter video Error:\n{}'.format(msg))
                if try_ < self.try_n - 1:
                    sleep(10, self.cw)
        else:
            raise e_


@try_n(4)
def get_artist_username(url, session, cw=None):
    if 'twitter.' not in url:
        username = url.strip('@')
    else:
        id = re.find('/status/([0-9]+)', url)
        if id:
            tweet = TwitterAPI(session, cw).tweet(id, url)
            user_id = tweet['globalObjects']['tweets'][id]['user_id_str']
            username = tweet['globalObjects']['users'][user_id]['screen_name']
            print('username fixed:', username)
        else:
            username = re.find('twitter.[^/]+/([^/?]+)', url)
    if not username:
        raise Exception('no username')
    data = TwitterAPI(session, cw).user_by_screen_name(username)
    artist = data['legacy']['name']
    username = data['legacy']['screen_name']
    return artist, username

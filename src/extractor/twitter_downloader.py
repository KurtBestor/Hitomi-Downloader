#coding:utf8
from __future__ import division, print_function, unicode_literals
import downloader
from utils import Downloader, Session, cache, LazyUrl, get_ext, try_n, Soup, get_print, update_url_query, urljoin, try_n, get_max_range, get_outdir, clean_title
from timee import time, sleep
import hashlib
import json
import ree as re
from datetime import datetime, timedelta
from translator import tr_
from error_printer import print_error
import os
import youtube_dl
import ffmpeg
import random
from m3u8_tools import M3u8_stream
import youtube_dl_test
import urllib
from ratelimit import limits, sleep_and_retry
try:
    from urllib import quote # python2
except:
    from urllib.parse import quote # python3
AUTH = "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
UA = "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko"
#UA = downloader.hdr['User-Agent']#
UAS = [
    'Opera/9.80 (Windows NT 6.1; U; en-US) Presto/2.7.62 Version/11.01',
    'Opera/9.80 (Windows NT 6.1; WOW64; U; pt) Presto/2.10.229 Version/11.62',
    'Opera/12.0(Windows NT 5.1;U;en)Presto/22.9.168 Version/12.00',
    'Opera/9.80 (Windows NT 5.1; U; en) Presto/2.9.168 Version/11.51',
    'Opera/9.80 (X11; Linux x86_64; U; fr) Presto/2.9.168 Version/11.50',
    'Opera/9.80 (X11; Linux x86_64; U; pl) Presto/2.7.62 Version/11.00',
    'Opera/9.80 (Windows NT 6.1 x64; U; en) Presto/2.7.62 Version/11.00',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1',
    'Opera/9.80 (Windows NT 6.1; U; zh-cn) Presto/2.6.37 Version/11.00',
    'Opera/9.80 (X11; Linux i686; U; ru) Presto/2.8.131 Version/11.11',
    'Opera/9.80 (Windows NT 6.1; Opera Tablet/15165; U; en) Presto/2.8.149 Version/11.1',
    'Opera/9.80 (Macintosh; Intel Mac OS X 10.6.8; U; de) Presto/2.9.168 Version/11.52',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.75.14 (KHTML, like Gecko) Version/7.0.3 Safari/7046A194A',
    'Opera/9.80 (Windows NT 5.1; U; zh-tw) Presto/2.8.131 Version/11.10',
    'Opera/9.80 (Windows NT 6.0) Presto/2.12.388 Version/12.14',
    'Opera/9.80 (X11; Linux i686; U; hu) Presto/2.9.168 Version/11.50',
    'Opera/9.80 (Windows NT 6.0; U; en) Presto/2.8.99 Version/11.10',
    'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36',
    'Opera/9.80 (X11; Linux x86_64; U; bg) Presto/2.8.131 Version/11.10',
    ]

def change_ua(session):
    i = random.randrange(len(UAS))
    session.headers['User-Agent'] = UAS[i]

    
from youtube_dl.utils import ExtractorError
from youtube_dl.compat import compat_HTTPError
def _call_api(self, path, video_id, query={}):
    headers = {
        'Authorization': AUTH,
    }
    if 'auth_token' in self._downloader.cookiejar.get_dict('.twitter.com'):
        print('auth_token')
        ct0 = self._downloader.cookiejar._cookies.get('.twitter.com', {}).get('/',{}).get('ct0')
        if ct0 is None or ct0.is_expired():
            print('Expired cookies')
            self._downloader.cookiejar.clear()
            return self._call_api(path, video_id, query)
        headers["x-twitter-auth-type"] = "OAuth2Session"
        headers["x-csrf-token"] = ct0.value
    else:
        if not self._GUEST_TOKEN:
            self._GUEST_TOKEN = self._download_json(
                self._API_BASE + 'guest/activate.json', video_id,
                'Downloading guest token', data=b'',
                headers=headers)['guest_token']
        headers['x-guest-token'] = self._GUEST_TOKEN
        
    try:
        return self._download_json(
            self._API_BASE + path, video_id, headers=headers, query=query)
    except ExtractorError as e:
        if isinstance(e.cause, compat_HTTPError) and e.cause.code == 403:
            raise ExtractorError(self._parse_json(
                e.cause.read().decode(),
                video_id)['errors'][0]['message'], expected=True)
        raise
youtube_dl.extractor.twitter.TwitterBaseIE._call_api = _call_api


def get_session():
    session = Session()
    session.headers['User-Agent'] = UA
    session.cookies['app_shell_visited'] = '1'
    return session


@Downloader.register
class Downloader_twitter(Downloader):
    type = 'twitter'
    URLS = ['twitter.com']
    MAX_CORE = 12

    def init(self):
        self.session = get_session()
        self.url = self.url.replace('twitter_', '')
        #self.url = fix_url(self.url)
        if 'twitter.com/home' in self.url:
            raise Exception('No username: home')
        self.artist, self.username = get_artist_username(self.url, self.session)
        if '/status/' not in self.url:
            self.url = 'https://twitter.com/{}'.format(self.username)

    @classmethod
    def fix_url(cls, url):
        if url.startswith('@'):
            url = 'https://twitter.com/{}'.format(url.lstrip('@'))
        return url.split('?')[0].split('#')[0].strip('/')

    def read(self):
        cw = self.customWidget
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
            imgs = get_imgs_single(self.url, self.session, types, cw=cw)
        else:
            self.print_('multiple tweets')
            imgs = get_imgs(self.username, self.session, title, types, cw=cw)
        for img in imgs:
            if isinstance(img, Image):
                self.urls.append(img.url)
            else:
                self.urls.append(img)

        self.title = title

        
@cache(3600)
def _guest_token(headers):
    session = Session()
    r = session.post('https://api.twitter.com/1.1/guest/activate.json', headers=headers)
    data = json.loads(r.text)
    return data['guest_token']


class TwitterAPI(object):
    def __init__(self, session, cw=None):
        self.session = session
        self.cw = cw
        csrf = hashlib.md5(str(time()).encode()).hexdigest()
        hdr = {
            "authorization": AUTH,
            "x-twitter-client-language": "en",
            "x-twitter-active-user": "yes",
            "x-csrf-token": csrf,
            "Origin": "https://twitter.com",
            }
        session.headers.update(hdr)
        session.cookies.set('ct0', csrf, domain='.twitter.com')
            

        if session.cookies.get("auth_token", domain=".twitter.com"):
            session.headers["x-twitter-auth-type"] = "OAuth2Session"
        else:
            # guest token
            guest_token = _guest_token(session.headers)
            session.headers["x-guest-token"] = guest_token
            session.cookies.set("gt", guest_token, domain=".twitter.com")

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
        data = downloader.read_json(url_api, referer, session=self.session)
        return data
    
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
            self.print_('cursor: {}'.format(params.get("cursor")))
            
            # 2303
            n_try = 20
            for try_ in range(n_try):
                try:
                    data = self._call(url_api, params=params)
                    tweets = data["globalObjects"]["tweets"]
                    break
                except Exception as e:
                    e_ = e
                    e_msg = print_error(e)[0]
                    if try_ < n_try - 1 :
                        self.print_('retry... _pagination ({})\n{}'.format(try_+1, e_msg))
                        sleep(30)
            else:
                raise e_
            
            users = data["globalObjects"]["users"]
            for instr in data["timeline"]["instructions"]:
                for entry in instr.get("addEntries", {}).get("entries", []):
                    if entry["entryId"].startswith(entry_tweet):
                        tid = entry["content"]["item"]["content"]["tweet"]["id"]
                        if tid not in tweets:
                            self.print_("Skipping unavailable Tweet {}".format(tid))
                            continue
                        tweet = tweets[tid]
                        tweet["user"] = users[tweet["user_id_str"]]

##                        if "quoted_status_id_str" in tweet:
##                            quoted = tweets[tweet["quoted_status_id_str"]]
##                            tweet["author"] = tweet["user"]
##                            if "extended_entities" in quoted:
##                                tweet["extended_entities"] = \
##                                    quoted["extended_entities"]
##                        elif "retweeted_status_id_str" in tweet:
##                            retweet = tweets[tweet["retweeted_status_id_str"]]
##                            tweet["author"] = users[retweet["user_id_str"]]
##                        else:
##                            tweet["author"] = tweet["user"]

                        yield tweet

                    elif entry["entryId"].startswith(entry_cursor):
                        cursor = entry["content"]["operation"]["cursor"]["value"]

                if not cursor or params.get('cursor') == cursor:
                    print('same cursor')
                    return
                params["cursor"] = cursor
            if params.get("cursor") is None: # nothing
                break
    

def get_imgs_single(url, session, types, format='[%y-%m-%d] id_ppage', cw=None):
    print_ = get_print(cw)
    id = re.find('/status/([0-9]+)', url)
    if id is None:
        raise Exception('no id')

    data = TwitterAPI(session, cw).tweet(id, url)

    tweets = data["globalObjects"]["tweets"]
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
##    try:
##        return get_imgs_legacy(username, session, title, types, n, format, cw)
##    except Exception as e:
##        print_(print_error(e)[-1])
        
    # Range
    n = max(n, get_max_range(cw))

    # 2303
    ids = set()
    names = dict()
    dir_ = os.path.join(get_outdir('twitter'), title)
    if os.path.isdir(dir_):
        for name in os.listdir(dir_):
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
    max_id = max(ids) if ids else 0

    
    imgs = []
    enough = False
    for tweet in TwitterAPI(session, cw).timeline_media(username):
        imgs += get_imgs_from_tweet(tweet, session, types, format, cw)
        if n is not None and len(imgs) >= n:
            break

        id_ = int(tweet['id_str'])
        if id_ < max_id:
            print_('enough')
            enough = True
            break

        msg = '{}  {} - {}'.format(tr_('읽는 중...'), title, len(imgs))
        if cw:
            if not cw.alive:
                break
            cw.setTitle(msg)
        else:
            print(msg)

    if not imgs:
        raise Exception('no imgs')

    if not enough and len(imgs) < n:
        imgs = get_imgs_legacy(username, session, title, types, n, format, cw, method='search', imgs=imgs)

    # 2303
    ids_new = set()
    for img in imgs:
        ids_new.add(img.id)
    for id_ in sorted(ids, reverse=True):
        if id_ in ids_new:
            continue
        imgs += sorted(os.path.join(dir_, name) for name in names[id_])

    return imgs


def get_imgs_legacy(username, session, title, types, n=None, format='[%y-%m-%d] id_ppage', cw=None, mode='media', method='tab', imgs=None):
    print_ = get_print(cw)
    print_('types: {}'.format(', '.join(types)))

    artist, username = get_artist_username(username, session)#
    
    # Range
    n = max(n, get_max_range(cw))

    max_pos = None
    ids_set = set()
    if imgs:
        for img in imgs:
            ids_set.add(img.id)
    else:
        imgs = []
    fuck = 0
    min_position = None
    while len(imgs) < n:
        if mode == 'media':
            if method == 'tab':
                foo = '&max_position={}'.format(max_pos) if max_pos is not None else ''
                url = 'https://twitter.com/i/profiles/show/{}/media_timeline?include_available_features=1&include_entities=1{}&reset_error_state=false'.format(username, foo)
                print_('max_pos={},  imgs={}'.format(max_pos, len(imgs)))
            elif method == 'search':  # 1028
                max_id = min(ids_set) - 1 if ids_set else None
                if ids_set:
                    q = 'from:{} max_id:{} exclude:retweets filter:media -filter:periscope'.format(username, max_id)
                else:
                    q = 'from:{} exclude:retweets filter:media -filter:periscope'.format(username)
                q = quote(q, '')
                url = 'https://twitter.com/i/search/timeline?f=tweets&vertical=default&q={}&src=typd&include_available_features=1&include_entities=1&reset_error_state=false'.format(q)
                print_('max_id={},  imgs={}'.format(max_id, len(imgs)))
            elif method == 'search2':  # 1028
                max_id = min(ids_set) - 1 if ids_set else None
                if ids_set:
                    q = 'from:{} max_id:{} exclude:retweets filter:media -filter:periscope'.format(username, max_id)
                else:
                    q = 'from:{} exclude:retweets filter:media -filter:periscope'.format(username)
                q = quote(q, '')
                foo = '&max_position={}'.format(max_pos) if max_pos is not None else ''
                url = 'https://twitter.com/i/search/timeline?f=tweets&vertical=default&q={}&src=typd&include_available_features=1&include_entities=1{}&reset_error_state=false'.format(q, foo)
                print_('max_pos={},  max_id={},  imgs={}'.format(max_pos, max_id, len(imgs)))
            else:
                raise Exception('Invalid method: {}'.format(method))
        elif mode == 'likes':
            foo = '&max_position={}'.format(max_pos) if max_pos is not None else ''
            url = 'https://twitter.com/{}/likes/timeline?include_available_features=1&include_entities=1{}&reset_error_state=false'.format(username, foo)
        print(url)
        
        hdr = {
            "X-Requested-With": "XMLHttpRequest",
            "X-Twitter-Active-User": "yes",
            }

        for try_ in range(16):
            if cw and not cw.alive:
                return
            try:
                html = downloader.read_html(url, session=session, referer='https://twitter.com/{}'.format(username), headers=hdr) #err
            except Exception as e:
                e_msg = print_error(e)[-1]
                print_('retry... ({}) {}\n{}'.format(try_, url, e_msg))
                change_ua(session)
                continue
            try:
                data = json.loads(html)
            except Exception as e:
                change_ua(session)
                soup = Soup(html)
                login = soup.find('div', class_='LoginForm-input')
                if login and method == 'tab':
                    raise Exception('Login required!')
                print_('can not load json: {}'.format(e))
                sleep(1)
                continue
            break
        else:
            print_('over try')
            if not imgs:
                raise Exception('No imgs')
            break

        if 'items_html' in data:
            html = data['items_html']
        else:
            print_('no items_html')
            session.cookies.clear() # ???
            #break

        soup = Soup(html)
        tweets = soup.findAll('div', class_='tweet') + soup.findAll('span', class_='grid-tweet')

        ids = []
        for tweet in tweets:
            id = int(tweet.attrs['data-tweet-id'])
            if id in ids_set:
                print('duplicate')
                continue
            ids.append(id)
            ids_set.add(id)
            tweet = Tweet(tweet, format, types, session, cw)
            for img in tweet.imgs:
                imgs.append(img)
        
        if n is not None and len(imgs) >= n:
            break

        if not ids:
            foo = 4 if method != 'search2' else 16
            if len(imgs) == 0:
                raise Exception('No Image')
            elif fuck > foo:
                if method == 'tab': ### search
                    method = 'search'
                    fuck = 0
                    continue
                elif method == 'search' and not ids and min_position is not None: ### search2
                    method = 'search2'
                    max_pos = min_position
                    #min_position = None
                    fuck = 0
                    continue
                else:
                    print('too much fuck')
                    break
            else:
                print('fuck!!!!!')
                change_ua(session)
                fuck += 1
        elif fuck:
            print('reset fuck')
            fuck = 0
            
        max_pos_new = data.get('min_position') # 1028
        if max_pos_new is None:
            if ids:
                max_pos_new = min(ids)
            else:
                max_pos_new = max_pos#
        max_pos = max_pos_new

        if data.get('min_position'):
            min_position = data['min_position']
            print('min_position:', min_position)

        try:
            if cw is not None:
                if not cw.alive:
                    break
                cw.setTitle('{}  {} (@{}) - {}'.format(tr_('읽는 중...'), artist, username, len(imgs)))
        except Exception as e:
            print(e)
            raise

    return imgs


def get_filename(tweet, page, format):
    id = int(tweet.attrs['data-tweet-id'])
    for span in tweet.findAll('span'):
        time = span.attrs.get('data-time')
        if time:
            break
    else:
        time_ms = (id >> 22) + 1288834974657
        time = time_ms / 1000

    date = datetime.fromtimestamp(float(time))
    timeStamp = date.strftime(format).replace(':', '\uff1a')
    return timeStamp.replace('id', str(id)).replace('page', str(page))


class Tweet(object):
    isVideo = False

    def __init__(self, tweet, format, types, session, cw):
        print_ = get_print(cw)
        self.tweet = tweet
        self.session = session
        self.username = tweet.attrs['data-screen-name']
        self.id = int(tweet.attrs['data-tweet-id'])
        for span in tweet.findAll('span'):
            time = span.attrs.get('data-time')
            if time:
                break
        else:
            time_ms = (id >> 22) + 1288834974657
            time = time_ms / 1000
        self.time = time
        self.url = urljoin('https://twitter.com', tweet.attrs['data-permalink-path'])
        self.withheld = 'withheld-tweet' in tweet.attrs
        if self.withheld:
            print_(('    withheld: {}').format(self.id))
        urls = []
        if 'img' in types:
            for div in tweet.findAll('div'):
                url = div.attrs.get('data-image-url')
                if not url:
                    continue
                if ':' not in os.path.basename(url):
                    url += ':orig'
                urls.append(url)

        if 'img' in types:
            for a in tweet.findAll('a'):
                url = a.attrs.get('data-expanded-url', '')
                if '//twitpic.com/' not in url:
                    continue
                print_(('twitpic: {}, {}').format(self.id, url))
                try:
                    url = get_twitpic(url, session)
                    if url in urls:
                        print('duplicate twitpic')
                        continue
                    urls.append(url)
                except Exception as e:
                    print_(('Failed to read twitpic:\n{}').format(print_error(e)[(-1)]))

        if 'grid-tweet' in tweet.attrs['class']:
            url = tweet.attrs['data-url'] + ':large'
            urls.append(url)
        self.imgs = []
        for page, url in enumerate(urls):
            img = Image(url, self.url, self.id, self.time, page, format, cw)
            self.imgs.append(img)

        if 'PlayableMedia-container' in str(tweet):
            self.isVideo = True
            if 'video' in types:
                img = Image(self.url, self.url, self.id, self.time, 0, format, cw, True)
                self.imgs.append(img)


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

    for url_ in tweet['entities'].get('urls', []):
        url_ = url_['expanded_url']
        if '//twitpic.com/' in url_:
            print_('twitpic: {}'.format(url_))
            try:
                url_ = get_twitpic(url_, session)
                tweet['extended_entities']['media'].append({'type': 'photo', 'media_url': url_, 'expanded_url': 'https://twitter.com'})
            except Exception as e:
                print_('Invalid twitpic')
                print_(print_error(e)[-1])
            
    media = tweet['extended_entities']['media']

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
    url = soup.find('img').attrs['src']
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

    
class Image(object):
    _url_cache = None
    
    def __init__(self, url, referer, id, time, p, format, cw=None, isVideo=False, try_n=4, n_thread=1):
        self._url = url
        self.referer = referer
        self.id = int(id)
        self.time = time
        self.p = p
        self.n_thread = n_thread
        if not isVideo and ':' in os.path.basename(url):
            url_alter = ':'.join(url.split(':')[:-1])
        else:
            url_alter = None
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
    def get(self, _):
        if self._url_cache:
            return self._url_cache
        print_ = get_print(self.cw)
        for try_ in range(self.try_n):
            try:
                d = youtube_dl.YoutubeDL()
                info = d.extract_info(self._url)
                
                url = info['url']
                ext = os.path.splitext(url.split('?')[0].split('#')[0])[1]
                self.ext = ext
                print_('get_video: {} {}'.format(url, ext))
                if ext.lower() == '.m3u8':
                    url = M3u8_stream(url, n_thread=self.n_thread, post_processing=True)
                self._url_cache = url
                return url
            except Exception as e:
                e_ = e
                msg = print_error(e)[(-1)]
                print_('\nTwitter video Error:\n{}'.format(msg))
                if try_ < self.try_n - 1:
                    sleep(10)
        else:
            raise e_


@try_n(4)
def get_artist_username(url, session):
    if 'twitter.' not in url:
        username = url.strip('@')
    else:
        id = re.find('/status/([0-9]+)', url)
        if id:
            tweet = TwitterAPI(session).tweet(id, url)
            user_id = tweet['globalObjects']['tweets'][id]['user_id_str']
            username = tweet['globalObjects']['users'][user_id]['screen_name']
            print('username fixed:', username)
        else:
            username = re.find('twitter.[^/]+/([^/?]+)', url)
    if not username:
        raise Exception('no username')
    data = TwitterAPI(session).user_by_screen_name(username)
    artist = data['legacy']['name']
    username = data['legacy']['screen_name']
    return artist, username


import downloader
from utils import Session, Downloader, LazyUrl, clean_url, try_n, Soup, clean_title, get_ext, get_max_range, get_print, check_alive
import json, os, ree as re
from timee import sleep
from translator import tr_
import urllib
import constants
from ratelimit import limits, sleep_and_retry
from m3u8_tools import playlist2stream, M3u8_stream
BASE_URL = 'https://www.pinterest.com'



class Downloader_pinter(Downloader):
    type = 'pinter'
    URLS = ['pinterest.']
    type_pinter = 'board'
    display_name = 'Pinterest'
    ACCEPT_COOKIES = [r'(.*\.)?(pinterest)\.']

    @try_n(4)
    def init(self):
        self.session = Session('chrome')
        self.api = PinterestAPI(self.session)
        self._pin_id = re.find(r'https?://.*pinterest\.[^/]+/pin/([0-9]+)', self.url)
        if self._pin_id is not None:
            self.type_pinter = 'pin'
        else:
            username, board = get_username_board(self.url)
            if '/' in board:
                self.type_pinter = 'section'
            if board == '_created':
                self.type_pinter = 'created'
        self.print_('type: {}'.format(self.type_pinter))
        if self.type_pinter in ['board', 'section', 'created']:
            self.info = get_info(username, board, self.api)
        elif self.type_pinter == 'pin':
            pass #5132
        else:
            raise NotImplementedError(self.type_pinter)

    @classmethod
    def fix_url(cls, url):
        if 'pinterest.' not in url:
            url = 'https://www.pinterest.com/{}'.format(url)
        return url

    @property
    def name(self):
        if self.type_pinter == 'pin':
            return self._pin_id
        username = ''
        name = ''
        if self.type_pinter == 'created':
            username = self.info['native_creator']['username']
            name = '_created'
        else:
            username = self.info['owner']['username']
            name = self.info['name']
        return clean_title('{}/{}'.format(username, name))

    def read(self):
        if self.type_pinter == 'pin':
            self.single = True
            id = self._pin_id
        else:
            id = self.info['id']
        self.title = self.name
        imgs = get_imgs(id, self.api, cw=self.cw, title=self.name, type=self.type_pinter)
        for img in imgs:
            self.urls.append(img.url)
        self.title = self.name


def get_info(username, board, api):
    if '/' in board:
        section = '/'.join(board.split('/')[1:])
        board = board.split('/')[0]
        info = api.board(username, board)
        for s in api.board_sections(info['id']):
            print(s['slug'].lower(), section)
            if s['slug'].lower() == section.lower():
                break
        else:
            raise Exception('Invalid section')

        title = s['title']
        info.update(s)
        info['name'] = '{}/{}'.format(info['name'], title)
        print('section_id:', info['id'])
    elif board == '_created':
        info = api.board_created(username)[0]
    else:
        info = api.board(username, board)
    return info


class PinterestAPI:
    HEADERS = {
        'Accept': 'application/json, text/javascript, */*, q=0.01',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': BASE_URL + '/',
        'X-Requested-With': 'XMLHttpRequest',
        'X-APP-VERSION' : '31461e0',
        'X-Pinterest-AppState': 'active',
        'Origin': BASE_URL,
        }

    def __init__(self, session):
        self.session = session
        self.session.headers.update(self.HEADERS)

    def pin(self, pin_id):
        options = {'id': pin_id, 'field_set_key': 'detailed'}
        return self._call('Pin', options)['resource_response']['data']

    def pin_related(self, pin_id):
        options = {'pin': pin_id, 'add_vase': True, 'pins_only': True}
        return self._pagination('RelatedPinFeed', options)

    def board(self, user, board):
        options = {'slug': board, 'username': user, 'field_set_key': 'detailed'}
        return self._call('Board', options)['resource_response']['data']

    def board_pins(self, board_id):
        options = {'board_id': board_id}
        return self._pagination('BoardFeed', options)

    def board_related(self, board_id):
        options = {'board_id': board_id, 'add_vase': True}
        return self._pagination('BoardRelatedPixieFeed', options)

    def board_sections(self, board_id):
        options = {'board_id': board_id}
        return self._pagination('BoardSections', options)

    def board_section_pins(self, section_id):
        options = {'section_id': section_id}
        return self._pagination('BoardSectionPins', options)

    def board_created(self, user):
        options = {'data': {}, 'username': user, 'field_set_key': 'grid_item'}
        return self._call('UserActivityPins', options)['resource_response']['data']

    def board_created_pins(self, user):
        options = {'data': {}, 'username': user, 'field_set_key': 'grid_item'}
        return self._pagination('UserActivityPins', options)

    @try_n(4)
    @sleep_and_retry
    @limits(1, 4) # 1000 calls per hour
    def _call(self, resource, options):
        url = '{}/resource/{}Resource/get/'.format(BASE_URL, resource)
        params = {'data': json.dumps({'options': options}), 'source_url': ''}
        #print('_call: {}, {}'.format(url, params))
        r = self.session.get(url, params=params)
        s = r.text
        status_code = r.status_code
        try:
            data = json.loads(s)
        except ValueError:
            data = {}

        if status_code < 400 and not r.history:
            return data

        if status_code == 404 or r.history:
            raise Exception('Not Found')
        raise Exception('API request failed: {}'.format(status_code))

    def _pagination(self, resource, options):
        while True:
            data = self._call(resource, options)
            if resource == 'UserActivityPins' and len(data['resource_response']['data']) == 0:
                return
            for x in data['resource_response']['data']:
                yield x

            try:
                bookmarks = data['resource']['options']['bookmarks']
                if not bookmarks or bookmarks[0] == '-end-' or bookmarks[0].startswith('Y2JOb25lO'):
                    return
                options['bookmarks'] = bookmarks
            except KeyError:
                return


class Image:

    def __init__(self, img):
        self.id = img['id']
        print(self.id)
        videos = img.get('videos')
        if videos and 'video_list' in videos:
            src = list(videos['video_list'].values())[0]['url']
        else:
            src = img['images']['orig']['url']

        ext = get_ext(src)
        if ext.lower() == '.m3u8':
            try:
                src = playlist2stream(src)
            except:
                src = M3u8_stream(src)
            ext = '.mp4'

        self.url = LazyUrl('{}/pin/{}/'.format(BASE_URL, self.id), lambda _: src, self)
        self.filename = f'{self.id}{ext}'



def get_imgs(id, api, cw=None, title=None, type='board'):
    print_ = get_print(cw)
    n = get_max_range(cw)
    imgs = []
    ids = set()
    print('get_imgs: type={}'.format(type))
    if type == 'board':
        gen = api.board_pins(id)
    elif type == 'section':
        gen = api.board_section_pins(id)
    elif type == 'pin':
        gen = [api.pin(id)]
    elif type == 'created':
        gen = api.board_created_pins(title.split('／')[0])
    else:
        raise Exception('Type "{}" is not supported'.format(type))
    for img in gen:
        check_alive(cw)
        if 'images' not in img:
            print('skip img:', img['id'])
            continue
        img = Image(img)
        if type == 'pin' and img.id != id:
            raise AssertionError('id mismatch')
        if img.id in ids:
            print('duplicate:', img.id)
            continue
        ids.add(img.id)
        print(img.url)
        print(img.filename)
        print()
        imgs.append(img)
        if len(imgs) >= n:
            break
        if cw is not None:
            cw.setTitle('{} {}  ({})'.format(tr_('읽는 중...'), title, len(imgs)))

    return imgs


def get_username_board(url):
    url = clean_url(url)
    m = re.search('pinterest.[a-zA-Z.]+?/([^/]+)/([^#\\?]+)', url)
    username, board = m.groups()
    board = urllib.parse.unquote(board).strip()
    while board.endswith('/'):
        board = board[:-1].strip()

    return (username, board)

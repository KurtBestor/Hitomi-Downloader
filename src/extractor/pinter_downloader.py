# uncompyle6 version 3.5.0
# Python bytecode 2.7 (62211)
# Decompiled from: Python 2.7.16 (v2.7.16:413a49145e, Mar  4 2019, 01:30:55) [MSC v.1500 32 bit (Intel)]
# Embedded file name: pinter_downloader.pyo
# Compiled at: 2019-10-21 07:44:55
import downloader
from utils import Session, Downloader, LazyUrl, clean_url, try_n, Soup, clean_title
import json, os, ree as re
from timee import sleep
from translator import tr_
import urllib
import constants
from ratelimit import limits, sleep_and_retry
BASE_URL = 'https://www.pinterest.com'

def get_info(username, board, api):
    if '/' in board:
        section = (u'/').join(board.split('/')[1:])
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
        info['name'] = (u'{}/{}').format(info['name'], title)
        print('section_id:', info['id'])
    else:
        info = api.board(username, board)
        #info = board_info(username, board)
    return info


def board_info(username, board):
    url = u'https://www.pinterest.com/{}/{}/'.format(username, board)
    html = downloader.read_html(url)
    soup = Soup(html)
    data = soup.find('script', id='initial-state').text
    data = json.loads(data)['resourceResponses']
    info = data[0]['response']['data']
    return info


@Downloader.register
class Downloader_pinter(Downloader):
    type = 'pinter'
    URLS = ['pinterest.']
    type_pinter = 'board'
    display_name = 'Pinterest'

    @try_n(4)
    def init(self):
        if 'pinterest.' not in self.url:
            self.url = u'https://www.pinterest.com/{}'.format(self.url)
        self.api = PinterestAPI()
        username, board = get_username_board(self.url)
        if '/' in board:
            self.type_pinter = 'section'
        self.print_(('type: {}').format(self.type_pinter))
        self.info = get_info(username, board, self.api)

    @property
    def name(self):
        username = self.info['owner']['username']
        name = self.info['name']
        return clean_title((u'{}/{}').format(username, name))

    def read(self):
        self.title = self.name
        id = self.info['id']
        imgs = get_imgs(id, self.api, cw=self.cw, title=self.name, type=self.type_pinter)
        for img in imgs:
            self.urls.append(img.url)

        self.title = self.name


class PinterestAPI:
    HEADERS = {'Accept': 'application/json, text/javascript, */*, q=0.01', 
       'Accept-Language': 'en-US,en;q=0.5', 
       'X-Pinterest-AppState': 'active', 
       'X-APP-VERSION': 'cb1c7f9', 
       'X-Requested-With': 'XMLHttpRequest', 
       'Origin': BASE_URL + '/'}

    def __init__(self):
        self.session = Session()
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

    @try_n(4)
    @sleep_and_retry
    @limits(1, 4) # 1000 calls per hour
    def _call(self, resource, options):
        url = ('{}/resource/{}Resource/get/').format(BASE_URL, resource)
        params = {'data': json.dumps({'options': options}), 'source_url': ''}
        print('_call: {}, {}'.format(url, params))
        r = self.session.get(url, params=params)
        print(r)
        s = r.text
        status_code = r.status_code
        try:
            data = json.loads(s)
        except ValueError:
            data = {}
        else:
            if status_code < 400 and not r.history:
                return data

        if status_code == 404 or r.history:
            raise Exception('Not Found')
        raise Exception('API request failed: {}'.format(status_code))

    def _pagination(self, resource, options):
        while True:
            data = self._call(resource, options)
            for x in data['resource_response']['data']:
                yield x

            try:
                bookmarks = data['resource']['options']['bookmarks']
                if not bookmarks or bookmarks[0] == '-end-' or bookmarks[0].startswith('Y2JOb25lO'):
                    return
                options['bookmarks'] = bookmarks
            except KeyError:
                return


class Image(object):

    def __init__(self, img):
        self.id = img['id']
        print(self.id)
        self.url0 = img['images']['orig']['url']

        def f(_):
            return self.url0

        self.url = LazyUrl(('{}/pin/{}/').format(BASE_URL, self.id), f, self)
        ext = os.path.splitext(self.url0.split('?')[0].split('#')[0])[1]
        self.filename = ('{}{}').format(self.id, ext)



def get_imgs(id, api, cw=None, title=None, type='board'):
    imgs = []
    ids = set()
    print('get_imgs: type={}'.format(type))
    if type == 'board':
        gen = api.board_pins(id)
    elif type == 'section':
        gen = api.board_section_pins(id)
    else:
        raise Exception((u'Type "{}" is not supported').format(type))
    for img in gen:
        if 'images' not in img:
            print('skip img:', img['id'])
            continue
        img = Image(img)
        if img.id in ids:
            print('duplicate:', img.id)
            continue
        ids.add(img.id)
        print(img.url)
        print(img.filename)
        print
        imgs.append(img)
        if cw is not None:
            if not cw.alive:
                return []
            cw.setTitle((u'{} {}  ({})').format(tr_(u'\uc77d\ub294 \uc911...'), title, len(imgs)))

    return imgs


def get_username_board(url):
    url = clean_url(url)
    m = re.search('pinterest.[a-zA-Z.]+?/([^/]+)/([^#\\?]+)', url)
    username, board = m.groups()
    board = urllib.parse.unquote(board).strip()
    while board.endswith('/'):
        board = board[:-1].strip()

    return (username, board)


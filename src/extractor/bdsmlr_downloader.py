#coding:utf8
import downloader
from utils import Session, Soup, LazyUrl, Downloader, get_max_range, try_n, get_print, clean_title, check_alive
from datetime import datetime
import ree as re
import os
from translator import tr_
from error_printer import print_error
import clf2
import errors



class Downloader_bdsmlr(Downloader):
    type = 'bdsmlr'
    URLS = ['bdsmlr.com']
    display_name = 'BDSMlr'
    ACCEPT_COOKIES = [r'(.*\.)?bdsmlr\.com']

    def init(self):
        if 'bdsmlr.com/post/' in self.url:
            raise errors.Invalid(tr_('개별 다운로드는 지원하지 않습니다: {}').format(self.url))

        self.url = 'https://{}.bdsmlr.com'.format(self.id_)
        self.session = Session()
        clf2.solve(self.url, session=self.session,  cw=self.cw)

    @property
    def id_(self):
        url = self.url
        if 'bdsmlr.com' in url:
            if 'www.bdsmlr.com' in url:
                raise Exception('www.bdsmlr.com')
            gal_num = url.split('.bdsmlr.com')[0].split('/')[(-1)]
        else:
            gal_num = url
        return gal_num

    def read(self):
        info = get_imgs(self.id_, session=self.session, cw=self.cw)

        for post in info['posts']:
            self.urls.append(post.url)

        self.title = '{} (bdsmlr_{})'.format(clean_title(info['username']), self.id_)


class Post:
    def __init__(self, url, referer, id, p):
        self.id = id
        self.url = LazyUrl(referer, lambda x: url, self)
        ext = os.path.splitext(url)[1]
        self.filename = '{}_p{}{}'.format(id, p, ext)


def foo(url, soup, info, reblog=False):
    #print('foo', info['c'], len(info['ids']))
    for post in soup.findAll('div', class_='wrap-post'):
        try:
            id = int(re.find('[0-9]+', post.attrs['class'][1]))
        except Exception as e:
            print(print_error(e))
            continue
        if id in info['ids']:
            continue
        info['ids'].add(id)
        info['last'] = id
        if not reblog and post.find('div', class_='ogname'):
            continue
        for p, mag in enumerate(post.findAll(['a', 'div'], class_='magnify')):
            post = Post(mag.attrs['href'], url, id, p)
            info['posts'].append(post)
    info['c'] += 20 if info['c'] else 5


@try_n(2)
def get_imgs(user_id, session, cw=None):
    print_ = get_print(cw)
    url = 'https://{}.bdsmlr.com/'.format(user_id)
    info = {'c': 0, 'posts': [], 'ids': set()}

    html = downloader.read_html(url, session=session)
    soup = Soup(html)

    sorry = soup.find('div', class_='sorry')
    if sorry:
        raise Exception(sorry.text.strip())

    username = soup.find('title').text.strip()###
    print('username:', username)
    info['username'] = username

    token = soup.find('meta', {'name': 'csrf-token'}).attrs['content']
    print_('token: {}'.format(token))

    max_pid = get_max_range(cw)

    n = len(info['ids'])
    for p in range(1000):
        check_alive(cw)
        if p == 0:
            url_api = 'https://{}.bdsmlr.com/loadfirst'.format(user_id)
        else:
            url_api = 'https://{}.bdsmlr.com/infinitepb2/{}'.format(user_id, user_id)
        data = {
            'scroll': str(info['c']),
            'timenow': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
        if 'last' in info:
            data['last'] = str(info['last'])
        print_('n:{}, scroll:{}, last:{}'.format(len(info['posts']), data['scroll'], data.get('last')))
        headers = {
            'Referer': url,
            'X-CSRF-TOKEN': token,
            }
        _e = None
        for try_ in range(4):
            try:
                r = session.post(url_api, data=data, headers=headers)
                if p == 0:
                    r.raise_for_status()
                break
            except Exception as e:
                _e = e
                print(e)
        else:
            if _e is not None:
                raise _e
        soup = Soup(r.text)
        foo(url, soup, info)
        if len(info['ids']) == n:
            print('same; break')
            break
        n = len(info['ids'])

        s = '{}  {} (tumblr_{}) - {}'.format(tr_('읽는 중...'), username, user_id, len(info['posts']))
        if cw is not None:
            cw.setTitle(s)
        else:
            print(s)

        if len(info['posts']) > max_pid:
            break

    return info

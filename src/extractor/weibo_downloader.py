#coding:utf8
import downloader
import ree as re
from utils import Downloader, Session, get_print, clean_title, Soup, fix_protocol, domain, get_max_range, get_ext, File, check_alive, limits
from translator import tr_
import clf2
import errors
import utils
import dateutil.parser


def suitable(url):
    if domain(url.lower(), 2) not in ['weibo.com', 'weibo.cn']:
        return False
    if '/tv/' in url.lower():
        return False
    return True


class LoginRequired(errors.LoginRequired):
    def __init__(self, *args):
        super().__init__(*args, method='browser', url='https://weibo.com/login.php', w=1180)



class Downloader_weibo(Downloader):
    type = 'weibo'
    URLS = [suitable]
    MAX_PARALLEL = 2 #6739
    ACCEPT_COOKIES = [r'(.*\.)?(weibo\.com|sina\.com\.cn|weibo\.cn)']

    def init(self):
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        url = url.replace('weibo.cn', 'weibo.com').split('?')[0]
        if 'weibo.com/p/' in url:
            id = re.find(r'weibo.com/p/([^/]+)', url, err='no id')
            url = f'https://weibo.com/p/{id}'
        elif 'weibo.com/u/' in url:
            id = re.find(r'weibo.com/u/([^/]+)', url, err='no id')
            url = f'https://weibo.com/u/{id}'
        elif 'weibo.com/' in url:
            id = re.find(r'weibo.com/([^/]+)', url, err='no id')
            url = f'https://weibo.com/{id}'
        else:
            id = url
            url = f'https://weibo.com/u/{id}'
        return fix_protocol(url)

    def read(self):
        checkLogin(self.session)

        uid, oid, name = get_id(self.url, self.cw)
        title = clean_title(f'{name} (weibo_{uid})')

        self.urls += get_imgs(uid, title, self.session, cw=self.cw)

        self.title = title


def checkLogin(session):
    c = session.cookies._cookies.get('.weibo.com', {}).get('/',{}).get('SUBP')
    if not c or c.is_expired():
        raise LoginRequired()


class Album:

    def __init__(self, id, type):
        self.id = id
        self.type = type


@limits(1)
def wait():
    pass


class Image(File):

    type = 'weibo'
    format = '[date] id_ppage'


def _get_page_id(html):
    return re.find(r"CONFIG\['page_id'\]='([0-9]+)'", html) or re.find(r'/u/page/follow/([0-9]+)', html)


def get_id(url, cw=None):
    for try_ in range(2):
        try:
            res = clf2.solve(url, cw=cw, f=_get_page_id)
            html = res['html']
            soup = Soup(html)
            if soup.find('div', class_='gn_login') or soup.find('a', class_=lambda c: c and c.startswith('LoginBtn')):
                raise LoginRequired()
            oid = _get_page_id(html)
            if not oid:
                raise Exception('no page_id')
            uids = re.findall(r'uid=([0-9]+)', html)
            uid = max(set(uids), key=uids.count)
            name = re.find(r"CONFIG\['onick'\]='(.+?)'", html) or soup.find('div', class_=lambda c:c and c.startswith('ProfileHeader_name')).text.strip()
            if not name:
                raise Exception('no name')
            break
        except errors.LoginRequired as e:
            raise e
        except Exception as e:
            e_ = e
            print(e)
    else:
        raise e_
    return uid, oid, name


def extract_video(d):
    return d.get('stream_url_hd') or d['stream_url']


def get_imgs(uid, title, session, cw=None): #6739
    print_ = get_print(cw)
    print_(f'uid: {uid}')

    olds = utils.process_olds(Image, title, r'([0-9]+)_p', cw)
    mids = olds['ids']
    imgs_old = olds['imgs']

    referer = f'https://weibo.com/u/{uid}?tabtype=album'
    imgs = []
    sinceid = None

    while check_alive(cw):
        if sinceid:
            url_api = f'https://weibo.com/ajax/profile/getImageWall?uid={uid}&sinceid={sinceid}'
        else:
            url_api = f'https://weibo.com/ajax/profile/getImageWall?uid={uid}&sinceid=0&has_album=true'
        wait()
        d = downloader.read_json(url_api, referer, session=session)
        sinceid = d['data']['since_id']
        for item in d['data']['list']:
            mid = int(item['mid'])
            if mid in mids:
                #print_(f'dup: {mid}')
                continue
            mids.add(mid)
            url_api = f'https://weibo.com/ajax/statuses/show?id={mid}'
            wait()
            d = downloader.read_json(url_api, referer, session=session)
            if d.get('ok') != 1:
                print_(f'skip: {mid}')
                continue
            date = dateutil.parser.parse(d['created_at'])
            structs = [d] + (d.get('url_struct') or [])
            for struct in structs:
                media_info = struct.get('mix_media_info', {}).get('items') or (struct.get('pic_infos').values() if 'pic_infos' in struct else None) #6739
                if media_info:
                    break
            else:
                print_(f'no media: {mid}') #6739
                continue
            for p, item in enumerate(media_info):
                if data := item.get('data'):
                    type = item.get('type')
                    if type == 'video':
                        img = extract_video(data['media_info'])
                    elif type == 'pic':
                        img = data['largest']['url']
                    else:
                        raise Exception(f'media type: {type}')
                else:
                    img = item['largest']['url']
                ext = get_ext(img)
                d = {
                    'date': date,
                    'id': mid,
                    'page': p,
                    }
                filename = utils.format('weibo', d, ext)
                img = Image({'referer': referer, 'url': img, 'name': filename})
                imgs.append(img)

            cw.setTitle(f'{tr_("읽는 중...")}  {title} - {len(imgs)}')

        if not sinceid:
            break

        if len(imgs) >= get_max_range(cw):
            break

    return imgs + imgs_old

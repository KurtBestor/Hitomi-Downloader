#coding:utf8
'''
Pornhub Downloader
'''
from io import BytesIO
import downloader
import ree as re
from utils import (Downloader, Soup, try_n, LazyUrl, urljoin, get_print,
                   Session, get_max_range, filter_range, get_ext,
                   format_filename, clean_title, get_resolution, check_alive)
import clf2
import utils
from m3u8_tools import playlist2stream, M3u8_stream
import errors
from error_printer import print_error
import ytdl



class File:
    '''
    File
    '''
    _thumb = None

    def __init__(self, id_, title, url, url_thumb, artist=''):
        self.id_ = id_
        self.title = clean_title(f'{title}')
        self.url = url

        ext = get_ext(self.url)
        if ext.lower() == '.m3u8':
            try:
                self.url = playlist2stream(self.url, n_thread=4)
            except:
                self.url = M3u8_stream(self.url, n_thread=4)

        self.url_thumb = url_thumb

        if ext.lower() == '.m3u8':
            ext = '.mp4'
        self.filename = format_filename(self.title, self.id_, ext, artist=artist)

    def thumb(self):
        if self._thumb is None:
            f = BytesIO()
            downloader.download(self.url_thumb, buffer=f)
            self._thumb = f
        else:
            f = self._thumb
        f.seek(0)
        return f


class Video:
    '''
    Video
    '''
    _url = None
    filename = None
    thumb = None

    def __init__(self, url, cw, session):
        url = Downloader_pornhub.fix_url(url)
        self.url = LazyUrl(url, self.get, self)
        self.cw = cw
        self.session = session

    @try_n(2)
    def get(self, url):
        '''
        get
        '''
        cw = self.cw
        session = self.session
        print_ = get_print(cw)
        if self._url:
            return self._url

        id_ = re.find(r'viewkey=(\w+)', url, re.I) or \
              re.find(r'/embed/(\w+)', url, re.I)
        print_('id: {}'.format(id_))
        if 'viewkey=' not in url.lower() and '/gif/' not in url.lower():
            if id_ is None:
                raise Exception('no id')
            url = urljoin(url, '/view_video.php?viewkey={}'.format(id_))

        url_test = url.replace('pornhubpremium.com', 'pornhub.com')
        try:
            html = downloader.read_html(url_test, session=session)
            soup = Soup(html)
            if soup.find('div', id='lockedPlayer'):
                print_('Locked player')
                raise Exception('Locked player')
            url = url_test
        except Exception as e: #3511
            print_(print_error(e))
            url = url.replace('pornhub.com', 'pornhubpremium.com')
            html = downloader.read_html(url, session=session)

        soup = Soup(html)
        soup = fix_soup(soup, url, session, cw)
        html = soup.html

        # removed
        if soup.find('div', class_='removed'):
            raise Exception('removed')

        gif = soup.find('div', {'id': 'gifImageSection'})
        if gif:
            print_('GIF')
            id_ = url.split('/gif/')[1]
            id_ = re.findall('[0-9a-zA-Z]+', id_)[0]

            jss = list(gif.children)
            for js in jss:
                if 'data-mp4' in getattr(js, 'attrs', {}):
                    break
            else:
                raise Exception('gif mp4 url not found')

            title = js['data-gif-title']
            url = js['data-mp4']
            url_thumb = re.find(r'https?://.+?.phncdn.com/pics/gifs/.+?\.jpg', html, err='no thumb')
            file = File('gif_{}'.format(id_), title, url, url_thumb)
        else:
            if id_ is None:
                raise Exception('no id')

            print_('Video')

            # 1968
            title = soup.find('h1', class_='title')
            for item in title.findAll(class_='phpFree'):
                item.decompose()
            title = title.text.strip()

            #4940
            artist = soup.find('div', class_='userInfo').find('div', class_='usernameWrap').text.strip()

            ydl = ytdl.YoutubeDL(cw=cw)
            info = ydl.extract_info(url)
            session.headers.update(info.get('http_headers', {}))

            fs = []
            for f in info['formats']:
                f['quality'] = f.get('height') or 0
                if f['protocol'].startswith('m3u8'):
                    f['quality'] -= 1
                if 'dash' in f['protocol'].lower(): #5554
                    continue
                print_('[{}p] {} {}'.format(f['height'], f['protocol'], f['url']))
                fs.append(f)

            if not fs:
                raise Exception('No formats')

            fs = sorted(fs, key=lambda f: f['quality'])

            res = get_resolution()

            fs_good = [f for f in fs if f['quality'] <= res]
            if fs_good:
                f = fs_good[-1]
            else:
                f = fs[0]
            print_('\n[{}p] {} {}'.format(f['height'], f['protocol'], f['url']))

            file = File(id_, title, f['url'], info['thumbnail'], artist)

        self._url = file.url
        self.title = file.title
        self.filename = file.filename
        self.thumb = file.thumb
        return self._url


def is_login(session, cw=None, n=2):
    '''
    is_login
    '''
    print_ = get_print(cw)
    print_('is_login {}'.format(n))
    if n <= 0:
        return False
    url = 'https://www.pornhubpremium.com'
    soup = downloader.read_soup(url, session=session)
    soup = fix_soup(soup, url, session, cw)
    if soup.find('ul', id='profileMenuDropdown'):
        return True
    return is_login(session, cw, n-1)



class Downloader_pornhub(Downloader):
    '''
    Downloader
    '''
    type = 'pornhub'
    single = True
    strip_header = False
    URLS = ['pornhub.com', 'pornhubpremium.com', 'pornhubthbh7ap3u.onion']
    ACCEPT_COOKIES = [r'.*(pornhub|phncdn|pornhubpremium).*'] #6181

    @classmethod
    def fix_url(cls, url):
        if 'pornhub_gif_' in url:
            url = 'https://www.pornhub.com/gif/{}'.format(
                url.replace('pornhub_gif_', ''))
        elif 'pornhub_album_' in url:
            url = 'https://www.pornhub.com/album/{}'.format(
                url.replace('pornhub_album_', ''))
        elif 'pornhub_' in url:
            url = 'https://www.pornhub.com/view_video.php?viewkey={}'\
                       .format(url.replace('pornhub_', ''))
        if '/authenticate/goToLoggedIn' in url:
            qs = utils.query_url(url)
            url = urljoin(url, qs['url'][0])
        url = url.replace('pornhubthbh7ap3u.onion', 'pornhub.com')
        return url

    @classmethod
    def key_id(cls, url):
        for domain in cls.URLS:
            if domain in url:
                id_ = domain + url.split(domain)[1]
                break
        else:
            raise Exception('no id')
        return id_.split('#')[0]

    @try_n(2)
    def read(self):
        cw = self.cw

        session = self.session = Session() # 1791
        self.purge_cookies()
        session.cookies.update({
            'age_verified': '1',
            'accessAgeDisclaimerPH': '1',
            'accessPH': '1',
            }) #6124
        if 'pornhubpremium.com' in self.url.lower() and\
           not is_login(session, cw):
            raise errors.LoginRequired(method='browser', url='https://www.pornhubpremium.com/premium/login')

        videos = []
        tab = ''.join(self.url.replace('pornhubpremium.com', 'pornhub.com', 1).split('?')[0].split('#')[0].split('pornhub.com/')[-1].split('/')[2:3])

        if '/album/' in self.url:
            self.print_('Album')
            info = read_album(self.url, session=session)
            self.single = False
            for photo in info['photos']:
                self.urls.append(photo.url)

            self.title = clean_title(info['title'])
        elif '/photo/' in self.url:
            self.print_('Photo')
            info = read_photo(self.url, session=session)
            self.urls.append(info['photo'].url)

            self.title = info['title']
        elif tab not in ['', 'videos']:
            raise NotImplementedError(tab)
        elif 'viewkey=' not in self.url.lower() and\
             '/embed/' not in self.url.lower() and\
             '/gif/' not in self.url.lower():
            self.print_('videos')
            info = get_videos(self.url, session, cw)
            hrefs = info['hrefs']
            self.print_('videos: {}'.format(len(hrefs)))

            if not hrefs:
                raise Exception('no hrefs')

            videos = [Video(href, cw, session) for href in hrefs]
            video = self.process_playlist(info['title'], videos)
            self.setIcon(video.thumb())
            self.enableSegment()
        else:
            video = Video(self.url, cw, session)
            video.url()
            self.urls.append(video.url)
            self.setIcon(video.thumb())
            self.title = video.title
            self.enableSegment()



def fix_soup(soup, url, session=None, cw=None):
    '''
    fix_soup
    '''
    print_ = get_print(cw)
    if soup.find('div', class_='logo'):
        return soup
    print_('invalid soup: {}'.format(url))

    res = clf2.solve(url, session=session, cw=cw)
    session.purge(Downloader_pornhub.ACCEPT_COOKIES)

    return Soup(res['html'])



class Photo_lazy:
    '''
    Photo_lazy
    '''

    def __init__(self, url, session):
        self._session = session
        self.url = LazyUrl(url, self.get, self)

    def get(self, url):
        info = read_photo(url, self._session)
        photo = info['photo']
        url = photo.url()
        self.filename = photo.filename
        return url



class Photo:
    '''
    Photo
    '''

    def __init__(self, url, referer, id_, session):
        self._session = session
        ext = get_ext(url)
        self.filename = f'{id_}{ext}'
        self.url = LazyUrl(referer, lambda _: url, self)


@try_n(8)
def read_album(url, session=None):
    '''
    read_album
    '''
    photos = []
    soup = downloader.read_soup(url, session=session)
    id_album = re.find('/album/([0-9]+)', url, err='no album id')
    for block in soup.findAll('div', class_='photoAlbumListBlock'):
        href = block.a.attrs['href']
        href = urljoin(url, href)
        photo = Photo_lazy(href, session)
        photos.append(photo)

    info = {}
    title = soup.find('h1', class_='photoAlbumTitleV2').text
    info['title'] = format_filename(title, f'album_{id_album}')
    info['photos'] = photos
    return info


@try_n(8)
def read_photo(url, session=None):
    '''
    read_photo
    '''
    id_ = re.find('/photo/([0-9]+)', url, err='no photo id')
    soup = downloader.read_soup(url, session=session)
    section = soup.find('div', id='photoImageSection')
    photo = section.find('img')['src']

    info = {}
    info['photo'] = Photo(photo, url, id_, session)
    title = soup.find('h1').text
    info['title'] = format_filename(title, f'photo_{id_}')
    return info


@try_n(4)
def get_videos(url, session, cw=None):
    '''
    get_videos
    '''
    print_ = get_print(cw)

    if '/users/' in url:
        mode = 'users'
        username = url.split('/users/')[1].split('/')[0]
    elif '/pornstar/' in url:
        mode = 'pornstar'
        username = url.split('/pornstar/')[1].split('/')[0]
    elif '/model/' in url:
        mode = 'model'
        username = url.split('/model/')[1].split('/')[0]
    elif '/channels/' in url:
        mode = 'channels'
        username = url.split('/channels/')[1].split('/')[0]
    elif '/playlist/' in url:
        mode = 'playlist'
        username = url.split('/playlist/')[1].split('/')[0]
    else:
        raise Exception('Not supported url')
    username = username.split('?')[0].split('#')[0]

    domain = utils.domain(url)

    if mode in ['pornstar']:
        url_main = 'https://{}/{}/{}'.format(domain, mode, username)
        html = downloader.read_html(url_main, session=session)
        soup = Soup(html)
        soup = fix_soup(soup, url_main, session, cw)
        for a in soup.findAll('a'):
            if '/{}/{}/videos/upload'.format(mode, username) in a.attrs.get('href', ''):
                free = True
                break
        else:
            free = False
        print_('free: {}'.format(free))

    # Range
    max_pid = get_max_range(cw)

    html = downloader.read_html(url, session=session)
    soup = fix_soup(Soup(html), url, session, cw)

    info = {}

    # get title
    h1 = soup.find('h1')
    if h1:
        header = 'Playlist'
        title = h1.parent.find(id='watchPlaylist')
    else:
        title = None
    if not title:
        header = 'Channel'
        profile = soup.find('div', class_='profileUserName')
        wrapper = soup.find('div', class_='titleWrapper')
        bio = soup.find('div', class_='withBio')
        title = soup.find('h1', {'itemprop':'name'})
        if not title and profile:
            title = profile.a
        if not title and wrapper:
            title = wrapper.h1
        if not title and bio:
            title = bio.h1
    if not title:
        raise Exception('No title')
    #print(title)
    info['title'] = '[{}] {}'.format(header, title.text.strip())
    token = re.find('''token *= *['"](.*?)['"]''', html)
    print_('token: {}'.format(token))

    # get links
    hrefs = []
    fail = 0
    for p in range(1, 1+100):
        check_alive(cw)
        try:
            if mode in ['users', 'model']:
                if mode == 'users':
                    url_api = 'https://{}/users/{}/videos/public/'\
                              'ajax?o=mr&page={}'.format(domain, username, p)
                elif mode == 'model':
                    url_api = 'https://{}/model/{}/videos/upload/'\
                              'ajax?o=mr&page={}'.format(domain, username, p)
                r = session.post(url_api)
                soup = Soup(r.text)
                if soup.find('h1'):
                    print('break: h1')
                    break
            elif mode in ['pornstar']:
                if free:
                    url_api = 'https://{}/{}/{}/videos/upload'\
                              '?page={}'.format(domain, mode, username, p)
                    soup = downloader.read_soup(url_api, session=session)
                    soup = fix_soup(soup, url_api, session, cw)
                    soup = soup.find('div', class_='videoUList')
                else:
                    url_api = 'https://{}/{}/{}?page={}'.format(domain, mode, username, p)
                    soup = downloader.read_soup(url_api, session=session)
                    soup = fix_soup(soup, url_api, session, cw)
                    soup = soup.find('ul', class_='pornstarsVideos')
            elif mode in ['channels']:
                url_api = 'https://{}/{}/{}/videos?page={}'.format(domain, mode, username, p)
                soup = downloader.read_soup(url_api, session=session)
                soup = fix_soup(soup, url_api, session, cw)
                try:
                    soup = soup.find('div', {'id': 'channelsBody'}).find('div', class_='rightSide')
                except:
                    break
            elif mode in ['playlist']:
                #url_api = 'https://{}/playlist/viewChunked?id={}&offset={}&itemsPerPage=40'.format(domain, username, len(hrefs))
                if token is None:
                    raise Exception('no token')
                url_api = 'https://{}/playlist/viewChunked?id={}&token={}&page={}'.format(domain, username, token, p)
                soup = downloader.read_soup(url_api, session=session)
            else:
                raise NotImplementedError(mode)
            fail = 0
        except Exception as e:
            print_(e)
            fail += 1
            if fail < 2:
                continue
            else:
                break
        finally:
            print_('{}  ({})'.format(url_api, len(hrefs)))

        lis = soup.findAll('li', class_='videoblock')
        if not lis:
            print_('break: no lis')
            break

        if getattr(soup.find('title'), 'text', '').strip() == 'Page Not Found':
            print_('Page Not Found')
            break

        c = 0
        for li in lis:
            a = li.find('a')
            href = a.attrs['href']
            href = urljoin(url, href)
            if href in hrefs:
                continue
            c += 1
            if href.startswith('javascript:'): # Remove Pornhub Premium
                print(href)
                continue
            hrefs.append(href)
        if c == 0:
            print('c==0')
            break
        print(c) # 1320

        if len(hrefs) >= max_pid:
            break

    if cw:
        hrefs = filter_range(hrefs, cw.range)
        cw.fped = True

    info['hrefs'] = hrefs[:max_pid]

    return info

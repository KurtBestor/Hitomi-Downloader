#coding:utf8
'''
Pornhub Downloader
'''
from __future__ import division, print_function, unicode_literals
from io import BytesIO
import os
import js2py
import downloader
import ree as re
from utils import (Downloader, Soup, try_n, LazyUrl, urljoin, get_print,
                   Session, get_max_range, filter_range, get_ext,
                   lock, format_filename, clean_title, get_resolution)
import clf2
import utils
from m3u8_tools import playlist2stream, M3u8_stream



class File(object):
    '''
    File
    '''

    def __init__(self, id_, title, url, url_thumb):
        self.id_ = id_
        self.title = clean_title('{}'.format(title))
        self.url = url
        
        ext = get_ext(self.url)
        if ext.lower() == '.m3u8':
            try:
                self.url = playlist2stream(self.url, n_thread=4)
            except:
                self.url = M3u8_stream(self.url, n_thread=4)
            
        self.url_thumb = url_thumb
        self.thumb = BytesIO()
        downloader.download(self.url_thumb, buffer=self.thumb)
        
        if ext.lower() == '.m3u8':
            ext = '.mp4'
        self.filename = format_filename(self.title, self.id_, ext)
        print('filename:', self.filename)


class Video(object):
    '''
    Video
    '''
    _url = None
    filename = None
    thumb = None

    def __init__(self, url, cw, session):
        self.url = LazyUrl(url, self.get, self)
        self.cw = cw
        self.session = session

    def get(self, url):
        '''
        get
        '''
        cw = self.cw
        session = self.session
        print_ = get_print(cw)
        if self._url:
            return self._url

        id_ = re.find(r'viewkey=(\w+)', url, re.IGNORECASE) or \
              re.find(r'/embed/(\w+)', url, re.IGNORECASE)
        print('id: {}'.format(id_))
        if 'viewkey=' not in url.lower() and '/gif/' not in url.lower():
            url = urljoin(url, '/view_video.php?viewkey={}'.format(id_))
        html = downloader.read_html(url, session=session)
            
        soup = Soup(html)
        soup = fix_soup(soup, url, session, cw)
        html = str(soup)

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
            j = decode(html, cw)

            # 1968
            #title = j['video_title']
            title = soup.find('h1', class_='title').text.strip()

            url_thumb = j['image_url']
            videos = []
            for video in j['mediaDefinitions']:
                url_ = video.get('videoUrl').strip()
                ext = get_ext(url_)
                if ext.lower() not in ['.mp4', '.m3u8']:
                    print('not mp4: {}'.format(ext))
                    continue
                quality = video.get('quality', 0)
                if isinstance(quality, list):
                    quality = quality[0]
                video['quality'] = int(quality)
                print_('[{}p] {}'.format(quality, url_))
                videos.append(video)

            if not videos:
                raise Exception('No videos')

            videos = sorted(videos, key=lambda video: video['quality'])

            res = get_resolution()

            videos_good = [video for video in videos if video['quality'] <= res]
            if videos_good:
                video = videos_good[-1]
            else:
                video = videos[0]
            print_('\n[{}p] {}'.format(video['quality'], video['videoUrl']))

            file = File(id_, title, video['videoUrl'].strip(), url_thumb)
        
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
    html = str(soup)
    if soup.find('ul', id='profileMenuDropdown'):
        return True
    return is_login(session, cw, n-1)



@Downloader.register
class Downloader_pornhub(Downloader):
    '''
    Downloader
    '''
    type = 'pornhub'
    single = True
    strip_header = False
    URLS = ['pornhub.com', 'pornhubpremium.com']

    def init(self):
        self.session = Session() # 1791
        if 'pornhub_gif_' in self.url:
            self.url = 'https://www.pornhub.com/gif/{}'.format(
                self.url.replace('pornhub_gif_', ''))
        elif 'pornhub_album_' in self.url:
            self.url = 'https://www.pornhub.com/album/{}'.format(
                self.url.replace('pornhub_album_', ''))
        elif 'pornhub_' in self.url:
            self.url = 'https://www.pornhub.com/view_video.php?viewkey={}'\
                       .format(self.url.replace('pornhub_', ''))
        if 'pornhubpremium.com' in self.url.lower() and\
           not is_login(self.session, self.cw):
            return self.Invalid('[Pornhub] Login cookies required')

    @classmethod
    def key_id(cls, url):
        for domain in cls.URLS:
            if domain in url:
                id_ = domain + url.split(domain)[1]
                break
        else:
            raise Exception('no id')
        return id_.split('#')[0]

    def read(self):
        cw = self.cw
        session = self.session

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
            for photo in info['photos']:
                self.urls.append(photo.url)

            self.title = info['title']
        elif tab not in ['', 'videos']:
            raise NotImplementedError(tab)
        elif 'viewkey=' not in self.url.lower() and\
             '/embed/' not in self.url.lower() and\
             '/gif/' not in self.url.lower():
            self.print_('videos')
            info = get_videos(self.url, cw)
            hrefs = info['hrefs']
            self.print_('videos: {}'.format(len(hrefs)))

            if not hrefs:
                raise Exception('no hrefs')

            videos = [Video(href, cw, session) for href in hrefs]
            video = self.process_playlist(info['title'], videos)
            self.setIcon(video.thumb)
            self.enableSegment()
        else:
            video = Video(self.url, cw, session)
            video.url()
            self.urls.append(video.url)
            self.setIcon(video.thumb)
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

    return Soup(res['html'])



class Photo(object):
    '''
    Photo
    '''

    def __init__(self, id_, url, referer):
        self.id_ = id_
        self.url = LazyUrl(referer, lambda x: url, self)
        ext = os.path.splitext(url.split('?')[0])[1]
        self.filename = '{}{}'.format(id_, ext)


@try_n(8)
def read_album(url, session=None):
    '''
    read_album
    '''
    soup = downloader.read_soup(url, session=session)
    id_album = re.find('/album/([0-9]+)', url, err='no album id')
    url_json = 'https://www.pornhub.com/album/show_album_json?album={}'.format(id_album)
    data = downloader.read_json(url_json, url, session=session)
    block = soup.find('div', class_='photoAlbumListBlock')
    href = block.a.attrs['href']
    id_ = re.find('/photo/([0-9]+)', href, err='no photo id')
    ids = [id_]
    while True:
        item = data[id_]
        id_ = item['next']
        if id_ in ids:
            break
        ids.append(id_)

    photos = []
    for id_ in ids:
        item = data[id_]
        img = item['img_large']
        referer = 'https://www.pornhub.com/photo/{}'.format(id_)
        photo = Photo(id_, img, referer)
        photos.append(photo)

    info = {}
    title = clean_title(soup.find('h1', class_='photoAlbumTitleV2').text)
    info['title'] = format_filename(title, 'album_{}'.format(id_album))
    info['photos'] = photos
    return info


@try_n(8)
def read_photo(url, session=None):
    '''
    read_photo
    '''
    id_ = re.find('/photo/([0-9]+)', url, err='no photo id')
    soup = downloader.read_soup(url, session=session)
    div = soup.find('div', id='thumbSlider')
    href = urljoin(url, div.find('a').attrs['href'])
    info = read_album(href)
    photos = []
    for photo in info['photos']:
        if str(photo.id_) == id_:
            photos.append(photo)

    info['photos'] = photos
    info['title'] = '{} - {}'.format(info['title'], photos[0].filename)
    return info


@try_n(4)
def get_videos(url, cw=None):
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

    session = Session()

    if mode in ['pornstar']:
        url_main = 'https://www.pornhub.com/{}/{}'.format(mode, username)
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
    max_pid = get_max_range(cw, 500)
    max_pid = min(max_pid, 2000)#

    html = downloader.read_html(url, session=session)
    soup = fix_soup(Soup(html), url, session, cw)

    info = {}

    # get title
    h1 = soup.find('h1')
    if h1:
        header = 'Playlist'
        title = h1.find(id='watchPlaylist')
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
        try:
            if mode in ['users', 'model']:
                if mode == 'users':
                    url_api = 'https://www.pornhub.com/users/{}/videos/public/'\
                              'ajax?o=mr&page={}'.format(username, p)
                elif mode == 'model':
                    url_api = 'https://www.pornhub.com/model/{}/videos/upload/'\
                              'ajax?o=mr&page={}'.format(username, p)
                r = session.post(url_api)
                soup = Soup(r.text)
                if soup.find('h1'):
                    print('break: h1')
                    break
            elif mode in ['pornstar']:
                if free:
                    url_api = 'https://www.pornhub.com/{}/{}/videos/upload'\
                              '?page={}'.format(mode, username, p)
                    soup = downloader.read_soup(url_api, session=session)
                    soup = fix_soup(soup, url_api, session, cw)
                    soup = soup.find('div', class_='videoUList')
                else:
                    url_api = 'https://www.pornhub.com/{}/{}?page={}'.format(mode, username, p)
                    soup = downloader.read_soup(url_api, session=session)
                    soup = fix_soup(soup, url_api, session, cw)
                    soup = soup.find('ul', class_='pornstarsVideos')
            elif mode in ['channels']:
                url_api = 'https://www.pornhub.com/{}/{}/videos?page={}'.format(mode, username, p)
                soup = downloader.read_soup(url_api, session=session)
                soup = fix_soup(soup, url_api, session, cw)
                try:
                    soup = soup.find('div', {'id': 'channelsBody'}).find('div', class_='rightSide')
                except:
                    break
            elif mode in ['playlist']:
                #url_api = 'https://www.pornhub.com/playlist/viewChunked?id={}&offset={}&itemsPerPage=40'.format(username, len(hrefs))
                if token is None:
                    raise Exception('no token')
                url_api = 'https://www.pornhub.com/playlist/viewChunked?id={}&token={}&page={}'.format(username, token, p)
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

        if cw and not cw.alive:
            return

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

    info['hrefs'] = hrefs

    return info


@lock
def decode(html, cw=None):
    '''
    decode
    '''
    print_ = get_print(cw)
    print_('decode')
    soup = Soup(html)

    for script in soup.findAll('script'):
        script = script.text or script.string or ''
        script = script.strip()
        if 'videoUrl' in script:
            break
    else:
        raise Exception('No script')

    flashvars = script.split()[1]
    script = 'playerObjList={};' + script

    context = js2py.EvalJs()
    context.execute(script)

    return context.eval(flashvars).to_dict()

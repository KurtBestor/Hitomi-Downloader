#coding:utf8
import downloader
import nndownload
from io import BytesIO
import ree as re
from utils import Downloader, get_print, compatstr, format_filename, clean_title, try_n
from nico_login import login, logout


def get_id(url):
    if '/watch/' in url:
        id = re.findall('/watch/([a-zA-Z0-9]+)', url)[0]
    else:
        id = url
    return id


class Video(object):
    def __init__(self, session, info):
        self.session = session
        self.info = info
        self.url = info['url']
        self.title = info['title']
        self.ext = info['ext']
        self.id = info['id']
        
        self.fileName = format_filename(self.title, self.id, self.ext)
        
        self.url_thumb = info['thumbnail_url']
        print('thumb:', self.url_thumb)
        self.thumb = BytesIO()
        downloader.download(self.url_thumb, buffer=self.thumb)

    def __repr__(self):
        return u'Video({})'.format(self.id)


@Downloader.register
class Downloader_nico(Downloader):
    type = 'nico'
    single = True
    URLS = ['nicovideo.jp']
    display_name = 'Niconico'
    
    def init(self):
        if not re.match('https?://.+', self.url, re.IGNORECASE):
            self.url = 'https://www.nicovideo.jp/watch/{}'.format(self.url)

    @property
    def id_(self):
        return get_id(self.url)

    def read(self):
        ui_setting = self.ui_setting

        if ui_setting.nicoBox.isChecked():
            username = compatstr(ui_setting.nico_id.text())
            password = compatstr(ui_setting.nico_pw.text())
        else:
            username = ''
            password = ''
            
        try:
            session = login(username, password)
        except Exception as e:
            logout()
            return self.Invalid(u'Failed to login: {}'.format(self.url), fail=True)

        self.session = session
        try:
            video = get_video(session, self.id_, cw=self.cw)
        except Exception as e:
            logout()
            raise

        self.urls.append(video.url)
        self.filenames[video.url] = video.fileName
        self.setIcon(video.thumb)

        self.enableSegment()

        self.title = video.title


@try_n(2)
def get_video(session, id, cw=None):
    print_ = get_print(cw)

    try:
        info = nndownload.request_video(session, id)
    except:
        raise Exception('Err')
    video = Video(session, info)

    return video



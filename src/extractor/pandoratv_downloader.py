import downloader
from utils import Session, Soup, LazyUrl, get_print, Downloader, get_ext, try_n, format_filename, clean_title
import ree as re
import json
from io import BytesIO
import errors



class EmbedUrlError(Exception): pass



class Downloader_pandoratv(Downloader):
    type = 'pandoratv'
    URLS = ['pandora.tv']
    single = True
    display_name = 'Pandora TV'

    @classmethod
    def fix_url(cls, url):
        return url.split('#')[0]

    def read(self):
        video = Video(self.url, format, cw=self.cw)
        try:
            video.url()#
        except EmbedUrlError as e:
            raise errors.Invalid(e.args[0])

        self.urls.append(video.url)
        self.setIcon(video.thumb)

        self.enableSegment()

        self.title = video.title



def extract(name, html, cw=None):
    print_ = get_print(cw)
    value = re.find(r'''{} *= *['"](.*?)['"]'''.format(name), html)
    if value is None:
        value = json.loads(re.find(r'''{} *= *(\[.*?\])'''.format(name), html))
    print_('{}: {}'.format(name, value))
    if value is None:
        raise Exception('No {}'.format(name))
    return value


class Video(object):
    _url_video = None

    def __init__(self, url, format='title', cw=None):
        self.url = LazyUrl(url, self.get, self)
        self.format = format
        self.cw = cw

    @try_n(2)
    def get(self, url):
        if self._url_video:
            return self._url_video
        cw = self.cw
        print_ = get_print(cw)
        html = downloader.read_html(url)
        soup = Soup(html)

        embedUrl = extract('embedUrl', html, cw)
        if embedUrl:
            raise EmbedUrlError('[pandoratv] EmbedUrl: {}'.format(embedUrl))

        uid = extract('strLocalChUserId', html, cw)
        pid = extract('nLocalPrgId', html, cw)
        fid = extract('strFid', html, cw)
        resolType = extract('strResolType', html, cw)
        resolArr = extract('strResolArr', html, cw)
        vodSvr = extract('nVodSvr', html, cw)
        resols = extract('nInfo', html, cw)
        runtime = extract('runtime', html, cw)

        url_api = 'http://www.pandora.tv/external/getExternalApi/getVodUrl/'
        data = {
            'userId': uid,
            'prgId': pid,
            'fid': fid,
            'resolType': resolType,
            'resolArr': ','.join(map(str, resolArr)),
            'vodSvr': vodSvr,
            'resol': max(resols),
            'runtime': runtime,
            'tvbox': 'false',
            'defResol': 'true',
            'embed': 'false',
            }
        session = Session()
        r = session.post(url_api, headers={'Referer': url}, data=data)
        data = json.loads(r.text)
        self._url_video = data['src']

        self.title = soup.find('meta', {'property': 'og:description'})['content']

        ext = get_ext(self._url_video)
        self.filename = format_filename(self.title, pid, ext)

        self.url_thumb = soup.find('meta', {'property': 'og:image'})['content']
        self.thumb = BytesIO()
        downloader.download(self.url_thumb, buffer=self.thumb)

        return self._url_video

import downloader
from utils import Downloader, Soup, get_print, json_loads, compatstr, LazyUrl, format_filename, clean_title
import devtools
import js2py
import ree as re
from m3u8_tools import playlist2stream
from io import BytesIO



@Downloader.register
class Downloader_javfinder(Downloader):
    type = 'javfinder'
    URLS = ['javfinder.la']
    single = True
    display_name = 'JavFinder'

    def read(self):
        video = Video(self.url, cw=self.cw)

        self.urls.append(video.url)
        self.setIcon(video.thumb)

        self.title = video.title


class Video(object):

    def __init__(self, url, cw=None):
        info = solve(url, cw=cw)
        url_video = info['file']
        stream = playlist2stream(url_video, n_thread=4)
        self.url = LazyUrl(url, lambda x: stream, self)
        self.title = info['title']
        id = info['id']
        self.filename = format_filename(self.title, id, '.mp4')
        self.thumb = BytesIO()
        downloader.download(info['url_thumb'], buffer=self.thumb)

        
def solve(url, cw=None):
    print_ = get_print(cw)
    info = {}
    res = devtools.watch_network(url, cw=cw)

    #html = res['html']
    html = downloader.read_html(url) # ???
    
    soup = Soup(html)
    info['title'] = soup.find('h1').text.strip()

    info['url_thumb'] = soup.find('meta', {'property': 'og:image'})['content'].strip()
    
    for r in res['rs']:
        url_player = r.url()
        if 'streamsb.net/embed-' in url_player:
            break
    else:
        raise Exception('no player')
    print_('player: {}'.format(url_player))

    info['id'] = ''#
    
    html = downloader.read_html(url_player, url)
    soup = Soup(html)
    for script in soup.findAll('script'):
        script = script.string or ''
        if 'function(p,a,c,k,e,d)' in script:
            break
    else:
        raise Exception('no function(p,a,c,k,e,d)')
    js = script.strip()[5:-1].replace('function(p,a,c,k,e,d)', 'function hack(p,a,c,k,e,d)').replace('return p}', 'return p};hack')
    context = js2py.EvalJs()
    t = context.eval(js)
    sources = re.find(r'sources *: *(\[\{.+?\}\])', t, err='no sources')
    sources = json_loads(sources)
    info['file'] = sources[0]['file']
    return info


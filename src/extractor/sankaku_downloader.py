#coding: utf-8
#https://chan.sankakucomplex.com/
#https://idol.sankakucomplex.com/
#https://beta.sankakucomplex.com/
#https://sankaku.app/
#http://white.sankakucomplex.com/
#https://www.sankakucomplex.com/
import downloader
import ree as re
from utils import Downloader, urljoin, query_url, get_max_range, get_print, Soup, lazy, Session, clean_title, check_alive, File, get_ext, limits, clean_url
from translator import tr_
import os
from timee import sleep
from error_printer import print_error
from urllib.parse import quote
import errors
import utils


class File_sankaku(File):
    type = 'sankaku'
    format = 'id'

    def get(self):
        print_ = get_print(self.cw)
        referer = self['referer']

        for try_ in range(4):
            wait(self.cw)
            html = ''
            try:
                html = downloader.read_html(referer, session=self.session)
                soup = Soup(html)
                highres = soup.find(id='highres')
                url = urljoin(referer, highres['href'] if highres else soup.find(id='image')['src'])
                break
            except Exception as e:
                e_msg = print_error(e)
                if '429 Too many requests'.lower() in html.lower():
                    t_sleep = 120 * min(try_ + 1, 2)
                    e = '429 Too many requests... wait {} secs'.format(t_sleep)
                elif 'post-content-notification' in html: # sankaku plus
                    print_('Sankaku plus: {}'.format(self['id']))
                    return ''
                else:
                    t_sleep = 5
                s = '[Sankaku] failed to read image (id:{}): {}'.format(self['id'], e)
                print_(s)
                sleep(t_sleep, self.cw)
        else:
            raise Exception('can not find image (id:{})\n{}'.format(self['id'], e_msg))
        soup = Soup('<p>{}</p>'.format(url))
        url = soup.string
        d = {
            'id': self['id'],
            }
        return {'url': url, 'name': utils.format('sankaku', d, get_ext(url))}



class Downloader_sankaku(Downloader):
    type = 'sankaku'
    URLS = ['chan.sankakucomplex.com', 'idol.sankakucomplex.com', 'www.sankakucomplex.com']
    MAX_CORE = 4
    display_name = 'Sankaku Complex'
    ACCEPT_COOKIES = [r'(.*\.)?(sankakucomplex\.com|sankaku\.app)']

    def init(self):
        type = self.url.split('sankakucomplex.com')[0].split('//')[-1].strip('.').split('.')[-1]
        if type == '':
            type = 'www'
        if type not in ['chan', 'idol', 'www']:
            raise Exception('Not supported subdomain')
        self.type_sankaku = type
        self.url = self.url.replace('&commit=Search', '')
        self.url = clean_url(self.url)
        self.session = Session()

    @lazy
    def soup(self):
        html = downloader.read_html(self.url, session=self.session)
        return Soup(html)

    @classmethod
    def fix_url(cls, url):
        if 'sankakucomplex.com' not in url:
            url = url.replace(' ', '+')
            while '++' in url:
                url = url.replace('++', '+')
            url = quote(url)
            url = url.replace('%2B', '+')
            url = url.replace('%20', '+')#
            if url.startswith('[chan]'):
                type = 'chan'
                url = url.replace('[chan]', '', 1).strip()
            elif url.startswith('[idol]'):
                type = 'idol'
                url = url.replace('[idol]', '', 1).strip()
            elif url.startswith('[www]'):
                type = 'www'
                url = url.replace('[www]', '', 1).strip()
            else:
                raise Exception('Not supported subdomain')
            url = 'https://{}.sankakucomplex.com/?tags={}'.format(type, url)
        return url.replace('http://', 'https://')

    @lazy
    def id(self):
        if self.type_sankaku == 'www':
            id = '[www] ' + self.soup.find('h1', class_='entry-title').text.strip()
        else:
            if '/post/show/' in self.url or '/posts/' in self.url: #6718
                id = get_id(self.url, self.soup)
            else:
                qs = query_url(self.url)
                tags = qs.get('tags', [])
                tags.sort()
                id = ' '.join(tags)
                if not id:
                    id = 'N/A'
            id = '[{}] {}'.format(self.type_sankaku, id)
        return clean_title(id)

    @property
    def name(self):
        return self.id

    def read(self):
        ui_setting = self.ui_setting
        self.title = self.name

        types = ['img', 'gif', 'video']
        if ui_setting.exFile.isChecked():
            if ui_setting.exFileImg.isChecked():
                types.remove('img')
            if ui_setting.exFileGif.isChecked():
                types.remove('gif')
            if ui_setting.exFileVideo.isChecked():
                types.remove('video')

        if self.type_sankaku == 'www':
            imgs = get_imgs_www(self.url, self.soup)
        else:
            info = get_imgs(self.url, self.name, cw=self.cw, types=types, session=self.session)
            self.single = info['single']
            imgs = info['imgs']

        self.urls += imgs

        self.title = self.name


def get_imgs_www(url, soup):
    imgs = []
    view = soup.find('div', class_='entry-content')
    for img in view.findAll('img'):
        img = img.get('data-lazy-src')
        if not img: # no script
            continue
        img = urljoin(url, img)
        if img in imgs:
            print('duplicate', img)
            continue
        imgs.append(img)
    return imgs


def setPage(url, page):
    # Always use HTTPS
    url = url.replace('http://', 'https://')

    # Change the page
    if 'page=' in url:
        url = re.sub(r'page=[0-9]*', 'page={}'.format(page), url)
    else:
        url += '&page={}'.format(page)

    return url


@limits(6)
def wait(cw):
    check_alive(cw)


def get_imgs(url, title=None, cw=None, types=['img', 'gif', 'video'], session=None):
    print_ = get_print(cw)
    print_('types: {}'.format(', '.join(types)))
    if 'chan.sankakucomplex' in url:
        type = 'chan'
    elif 'idol.sankakucomplex' in url:
        type = 'idol'
    else:
        raise Exception('Not supported subdomain')

    info = {}
    info['single'] = False

    if '/post/show/' in url or '/posts/' in url: #6718
        info['single'] = True
        id = get_id(url)
        info['imgs'] = [File_sankaku({'type': type, 'id': id, 'referer': url})]
        return info

    # Range
    max_pid = get_max_range(cw)

    local_ids = {}
    if cw is not None:
        dir = cw.downloader.dir
        try:
            names = os.listdir(dir)
        except Exception as e:
            print(e)
            names = []
        for name in names:
            id = os.path.splitext(name)[0]
            local_ids[id] = os.path.join(dir, name)

    imgs = []
    page = 1
    ids = set()
    url_old = 'https://{}.sankakucomplex.com'.format(type)
    if cw is not None:
        cw.setTitle('{}  {}'.format(tr_('읽는 중...'), title))
    while len(imgs) < max_pid:
        #if page > 25: # Anonymous users can only view 25 pages of results
        #    break
        wait(cw)
        #url = setPage(url, page)
        print_(url)
        try:
            html = downloader.read_html(url, referer=url_old, session=session)
        except Exception as e: #3366
            print_(print_error(e))
            break
        if '429 Too many requests'.lower() in html.lower():
            print_('429 Too many requests... wait 120 secs')
            sleep(120, cw)
            continue
        page += 1
        url_old = url
        soup = Soup(html)
        for banner in soup.findAll('div', class_='has-mail'): #5861
            banner.decompose()
        banner = soup.find('div', class_='popular-previews')
        if banner: #6171
            banner.decompose()
        err = soup.find('div', class_='post-premium-browsing_error')
        if err and not imgs:
            raise errors.LoginRequired(err.text.strip())
        articles = soup.findAll('span', {'class': 'thumb'})

        if not articles:
            if soup.find(class_='post-premium-browsing_error'): #6418
                print_('premium error')
                tags = utils.query_url(url)['tags'][0]
                tags = re.sub(r'id_range:<[0-9]+', '', tags).strip()
                tags += f' id_range:<{min(ids)}'
                url = utils.update_url_query(url, {'tags': tags})
                url = re.sub(r'&page=[0-9]+', '', url)
                url = re.sub(r'&next=[0-9]+', '', url)
                continue
            print_('no articles')
            break

        for article in articles:
            # 1183
            tags = article.find('img', class_='preview')['data-auto_page'].split() #6718
            if 'animated_gif' in tags:
                type_ = 'gif'
            elif 'animated' in tags or 'webm' in tags or 'video' in tags or 'mp4' in tags: # 1697
                type_ = 'video'
            else:
                type_ = 'img'
            if type_ not in types:
                continue

            url_img = article.a['href']
            if not url_img.startswith('http'):
                url_img = urljoin('https://{}.sankakucomplex.com'.format(type), url_img)
            if 'get.sankaku.plus' in url_img: # sankaku plus
                continue
            id = int(re.find(r'p([0-9]+)', article['id'], err='no id')) #5892
            #print_(article)
            if str(id) in local_ids:
                #print('skip', id)
                local = True
            else:
                local = False
            #print(url_img)
            if id not in ids:
                ids.add(id)
                if local:
                    img = local_ids[str(id)]
                else:
                    img = File_sankaku({'type':type, 'id':id, 'referer':url_img})
                imgs.append(img)
                if len(imgs) >= max_pid:
                    break

        try:
            # For page > 50
            pagination = soup.find('div', class_='pagination')
            url = urljoin('https://{}.sankakucomplex.com'.format(type), utils.html.unescape(pagination['next-page-url'])) #6326
##            #3366
##            p = int(re.find(r'[?&]page=([0-9]+)', url, default=1))
##            if p > 100:
##                break
        except Exception as e:
            print_(print_error(e))
            #url = setPage(url, page)
            break

        if cw is not None:
            cw.setTitle('{}  {} - {}'.format(tr_('읽는 중...'), title, len(imgs)))
        else:
            print(len(imgs), 'imgs')

    if not imgs:
        raise Exception('no images')

    info['imgs'] = imgs

    return info


def get_id(url, soup=None):
    if soup is None:
        html = downloader.read_html(url)
        soup = Soup(html)
    if x := soup.find('input', id='post_id'):
        return x['value']
    return soup.find('p', id='hidden_post_id').string

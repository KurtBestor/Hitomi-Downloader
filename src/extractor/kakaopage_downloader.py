import downloader
import ree as re
from utils import Session, LazyUrl, Soup, Downloader, try_n, get_print, clean_title, print_error, urljoin, get_imgs_already
from timee import sleep
from translator import tr_
import page_selector
import json
import clf2
from ratelimit import limits, sleep_and_retry


class Page:

    def __init__(self, sid, pid, title):
        self.sid = sid
        self.pid = pid
        self.title = title
        self.url = f'https://page.kakao.com/content/{sid}/viewer/{pid}'


class Image:

    def __init__(self, url, page, p):
        self._url = url
        self.url = LazyUrl('https://page.kakao.com/', self.get, self)
        ext = '.jpg'
        self.filename = '{}/{:04}{}'.format(clean_title(page.title), p, ext)

    @sleep_and_retry
    @limits(5, 1)
    def get(self, _):
        return self._url



class Downloader_kakaopage(Downloader):
    type = 'kakaopage'
    URLS = ['page.kakao.com/home', 'page.kakao.com/content/']
    MAX_PARALLEL = 2
    MAX_CORE = 4
    MAX_SPEED = 4.0
    display_name = 'KakaoPage'
    ACCEPT_COOKIES = [r'(.*\.)?kakao\.com']

    @classmethod
    def fix_url(cls, url):
        # legacy
        id = re.find(r'\?seriesId=([0-9]+)', url)
        if id is not None:
            url = f'https://page.kakao.com/content/{id}'

        id = re.find('/content/([0-9]+)', url)
        if id is not None:
            url = id
        if url.isdecimal():
            url = f'https://page.kakao.com/content/{url}'
        return url

    def read(self):
        self.session = Session()
        info = get_info(self.url, self.session, cw=self.cw)
        self.purge_cookies()

        for img in info['imgs']:
            if isinstance(img, Image):
                img = img.url
            self.urls.append(img)

        self.artist = info['artist']

        self.title = info['title']



def get_id(url):
    id_ = re.find('/content/([0-9]+)', url, err='No seriesId')
    return id_



def get_pages(url, session, cw=None):
    read_html(url, session=session)
    id_ = get_id(url)

    pages = []
    ids = set()
    for p in range(500): #2966
        url_api = 'https://page.kakao.com/graphql'
        q = r'''query contentHomeProductList($after: String, $before: String, $first: Int, $last: Int, $seriesId: Long!, $boughtOnly: Boolean, $sortType: String) {
 contentHomeProductList(
 seriesId: $seriesId
 after: $after
 before: $before
 first: $first
 last: $last
 boughtOnly: $boughtOnly
 sortType: $sortType
 ) {
 totalCount
 pageInfo {
 hasNextPage
 endCursor
 hasPreviousPage
 startCursor
 __typename
 }
 selectedSortOption {
 id
 name
 param
 __typename
 }
 sortOptionList {
 id
 name
 param
 __typename
 }
 edges {
 cursor
 node {
 ...SingleListViewItem
 __typename
 }
 __typename
 }
 __typename
 }
}

fragment SingleListViewItem on SingleListViewItem {
 id
 type
 thumbnail
 showPlayerIcon
 isCheckMode
 isChecked
 scheme
 row1 {
 badgeList
 title
 __typename
 }
 row2
 row3
 single {
 productId
 ageGrade
 id
 isFree
 thumbnail
 title
 slideType
 operatorProperty {
 isTextViewer
 __typename
 }
 __typename
 }
 isViewed
 purchaseInfoText
 eventLog {
 ...EventLogFragment
 __typename
 }
}

fragment EventLogFragment on EventLog {
 click {
 layer1
 layer2
 setnum
 ordnum
 copy
 imp_id
 imp_provider
 __typename
 }
 eventMeta {
 id
 name
 subcategory
 category
 series
 provider
 series_id
 type
 __typename
 }
 viewimp_contents {
 type
 name
 id
 imp_area_ordnum
 imp_id
 imp_provider
 imp_type
 layer1
 layer2
 __typename
 }
 customProps {
 landing_path
 view_type
 toros_imp_id
 toros_file_hash_key
 toros_event_meta_id
 content_cnt
 event_series_id
 event_ticket_type
 play_url
 banner_uid
 __typename
 }
}
'''
        data = {
            'query': q,
            'operationName': 'contentHomeProductList',
            'variables': {
                "seriesId": int(id_),
                "after": str(len(pages)),
                "boughtOnly": False,
                "sortType":"asc",
                }
            }
        r = session.post(url_api, json=data, headers={'Referer': url})
        print(p, r)
        data = r.json()['data']
        edges = data['contentHomeProductList']['edges']
        if not edges:
            break

        for edge in edges:
            single = edge['node']['single']
            title_page = single['title']
            id_page = single['productId']
            if id_page in ids:
                print('dup id')
                continue
            ids.add(id_page)
            page = Page(id_, id_page, title_page)
            pages.append(page)
        sleep(1, cw)
    return pages


def read_html(url, session):
    res = clf2.solve(url, session=session)
    return res['html']


def get_imgs_page(page, session):
    html = read_html(page.url, session=session)
    url_api = 'https://page.kakao.com/graphql'
    q = r'''query viewerInfo($seriesId: Long!, $productId: Long!) {
 viewerInfo(seriesId: $seriesId, productId: $productId) {
 item {
 ...SingleFragment
 __typename
 }
 seriesItem {
 ...SeriesFragment
 __typename
 }
 prevItem {
 ...NearItemFragment
 __typename
 }
 nextItem {
 ...NearItemFragment
 __typename
 }
 viewerData {
 ...TextViewerData
 ...TalkViewerData
 ...ImageViewerData
 ...VodViewerData
 __typename
 }
 displayAd {
 ...DisplayAd
 __typename
 }
 __typename
 }
}

fragment SingleFragment on Single {
 id
 productId
 seriesId
 title
 thumbnail
 badge
 isFree
 ageGrade
 state
 slideType
 lastReleasedDate
 size
 pageCount
 isHidden
 freeChangeDate
 isWaitfreeBlocked
 saleState
 series {
 ...SeriesFragment
 __typename
 }
 serviceProperty {
 ...ServicePropertyFragment
 __typename
 }
 operatorProperty {
 ...OperatorPropertyFragment
 __typename
 }
 assetProperty {
 ...AssetPropertyFragment
 __typename
 }
}

fragment SeriesFragment on Series {
 id
 seriesId
 title
 thumbnail
 categoryUid
 category
 subcategoryUid
 subcategory
 badge
 isAllFree
 isWaitfree
 isWaitfreePlus
 is3HoursWaitfree
 ageGrade
 state
 onIssue
 seriesType
 businessModel
 authors
 pubPeriod
 freeSlideCount
 lastSlideAddedDate
 waitfreeBlockCount
 waitfreePeriodByMinute
 bm
 saleState
 serviceProperty {
 ...ServicePropertyFragment
 __typename
 }
 operatorProperty {
 ...OperatorPropertyFragment
 __typename
 }
 assetProperty {
 ...AssetPropertyFragment
 __typename
 }
}

fragment ServicePropertyFragment on ServiceProperty {
 viewCount
 readCount
 ratingCount
 ratingSum
 commentCount
 pageContinue {
 ...ContinueInfoFragment
 __typename
 }
 todayGift {
 ...TodayGift
 __typename
 }
 waitfreeTicket {
 ...WaitfreeTicketFragment
 __typename
 }
 isAlarmOn
 isLikeOn
 ticketCount
 purchasedDate
 lastViewInfo {
 ...LastViewInfoFragment
 __typename
 }
 purchaseInfo {
 ...PurchaseInfoFragment
 __typename
 }
}

fragment ContinueInfoFragment on ContinueInfo {
 title
 isFree
 productId
 lastReadProductId
 scheme
 continueProductType
 hasNewSingle
 hasUnreadSingle
}

fragment TodayGift on TodayGift {
 id
 uid
 ticketType
 ticketKind
 ticketCount
 ticketExpireAt
 isReceived
}

fragment WaitfreeTicketFragment on WaitfreeTicket {
 chargedPeriod
 chargedCount
 chargedAt
}

fragment LastViewInfoFragment on LastViewInfo {
 isDone
 lastViewDate
 rate
 spineIndex
}

fragment PurchaseInfoFragment on PurchaseInfo {
 purchaseType
 rentExpireDate
}

fragment OperatorPropertyFragment on OperatorProperty {
 thumbnail
 copy
 torosImpId
 torosFileHashKey
 isTextViewer
}

fragment AssetPropertyFragment on AssetProperty {
 bannerImage
 cardImage
 cardTextImage
 cleanImage
 ipxVideo
}

fragment NearItemFragment on NearItem {
 productId
 slideType
 ageGrade
 isFree
 title
 thumbnail
}

fragment TextViewerData on TextViewerData {
 type
 atsServerUrl
 metaSecureUrl
 contentsList {
 chapterId
 contentId
 secureUrl
 __typename
 }
}

fragment TalkViewerData on TalkViewerData {
 type
 talkDownloadData {
 dec
 host
 path
 talkViewerType
 __typename
 }
}

fragment ImageViewerData on ImageViewerData {
 type
 imageDownloadData {
 ...ImageDownloadData
 __typename
 }
}

fragment ImageDownloadData on ImageDownloadData {
 files {
 ...ImageDownloadFile
 __typename
 }
 totalCount
 totalSize
 viewDirection
 gapBetweenImages
 readType
}

fragment ImageDownloadFile on ImageDownloadFile {
 no
 size
 secureUrl
 width
 height
}

fragment VodViewerData on VodViewerData {
 type
 vodDownloadData {
 contentId
 drmType
 endpointUrl
 width
 height
 duration
 __typename
 }
}

fragment DisplayAd on DisplayAd {
 sectionUid
 bannerUid
 treviUid
 momentUid
}
'''
    data = {
        'query': q,
        'operationName': 'viewerInfo',
        'variables': {
            "seriesId": page.sid,
            "productId": page.pid,
            }
        }
    r = session.post(url_api, json=data, headers={'Referer': page.url})
    j = r.json()
    errs = j.get('errors')
    if errs:
        raise KakaopageException(errs[0]['message'])

    data = j['data']

    imgs = []
    for file in data['viewerInfo']['viewerData']['imageDownloadData']['files']:
        url = file['secureUrl']
        if not url.startswith('http'):
            url = 'https://page-edge.kakao.com/sdownload/resource?kid=' + url #5176
        img = Image(url, page, len(imgs))
        imgs.append(img)
    return imgs


class KakaopageException(Exception): pass


def get_info(url, session, cw=None):
    print_ = get_print(cw)

    info = {}

    html = read_html(url, session=session)
    soup = Soup(html)

    pages = get_pages(url, session, cw)
    pages = page_selector.filter(pages, cw)
    if not pages:
        raise Exception('no pages')

    title = soup.find('meta', {'property':"og:title"})['content']
    artist = soup.find('meta', {'name':"author"})['content']
    for x in [' ,', ', ']:
        while x in artist:
            artist = artist.replace(x, ',')
    artist = artist.replace(',', ', ')
    info['artist'] = artist
    info['title_raw'] = title
    info['title'] = clean_title('[{}] {}'.format(artist, title))

    imgs = []

    for i, page in enumerate(pages):
        if cw is not None:
            cw.setTitle('{} {} / {}  ({} / {})'.format(tr_('읽는 중...'), info['title'], page.title, i + 1, len(pages)))

        #3463
        imgs_already = get_imgs_already('kakaopage', info['title'], page, cw)
        if imgs_already:
            imgs += imgs_already
            continue

        _imgs = []
        e_msg = None
        for _ in range(2):
            try:
                _imgs = get_imgs_page(page, session)
                break
            except KakaopageException as e:
                e_msg = e.args[0]
                break
            except Exception as e:
                e_msg = print_error(e)
        print_('{} {}'.format(page.title, len(_imgs)))
        if e_msg:
            print_(e_msg)

        imgs += _imgs
        sleep(1, cw)

    if not imgs:
        raise Exception('no imgs')

    info['imgs'] = imgs

    return info


@page_selector.register('kakaopage')
@try_n(4)
def f(url):
    if '/viewer/' in url:
        raise Exception(tr_('목록 주소를 입력해주세요'))
    pages = get_pages(url, Session())
    return pages

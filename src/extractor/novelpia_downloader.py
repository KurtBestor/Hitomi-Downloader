import re
from io import BytesIO
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import requests
import page_selector
from errors import LoginRequired
from utils import Downloader, Session, Soup, clean_title, tr_, urljoin


class SoupInfo:
    def __init__(self, soup: Soup, number: int) -> None:
        self.soup: Soup = soup
        self.number: int = number


class Page:
    def __init__(self, title: str, number: int):
        self.title = title
        self.number = number
        self.url = f"https://novelpia.com/viewer/{number}"


class NovelpiaParser:
    cache: List[Page] = []

    def __init__(
        self, url: str, downloader: Optional["Downloader_novelpia"] = None
    ) -> None:
        self.parsed_url = urlparse(url.replace("test_novelpia_", ""))
        self.downloader = downloader
        self.session = self.get_session_with_set_cookies()

    @property
    def is_novel(self):
        return "novel" in self.parsed_url[2]

    @property
    def number(self) -> str:
        path = self.parsed_url[2]
        if self.is_novel:
            return path.replace("/novel/", "")
        return path.replace("/viewer/", "")

    @property
    def proc_episode_list_url(self) -> str:
        return urljoin(self.parsed_url.geturl(), "/proc/episode_list")

    def get_session_with_set_cookies(self) -> Session:
        session = requests.Session()
        user_key = Session().cookies.get("USERKEY", domain=".novelpia.com")
        login_key = Session().cookies.get("LOGINKEY", domain=".novelpia.com")

        if user_key and login_key:
            session.cookies.set("USERKEY", user_key, domain=".novelpia.com")
            session.cookies.set("LOGINKEY", login_key, domain=".novelpia.com")
        return session

    def proc_episode_list_url_request(self, page: int):
        r = self.session.post(
            self.proc_episode_list_url,
            data={"novel_no": self.number, "page": page},
        )
        return r.text

    def get_total_episode_list(self) -> Tuple[int, str]:
        regex = re.compile(
            rf"localStorage\['novel_page_{self.number}'\] = '(.+?)'; episode_list\(\);"
        )
        html = self.proc_episode_list_url_request(0)
        soup = Soup(html, "lxml")
        page_link_element = soup.find_all("div", {"class": "page-link"})
        last_episode = page_link_element[::-1][0]["onclick"]
        matched = regex.match(last_episode)
        assert matched
        total_episode_page = matched.group(1)
        if self.downloader:
            self.downloader.title = tr_("{} 개 찾음").format(total_episode_page)
        return int(total_episode_page), html

    def get_all_viewer_numbers(self):
        htmls: List[str] = []
        novel_numbers: List[int] = []
        total_episode_page, html = self.get_total_episode_list()
        htmls.append(html)

        for i in range(1, total_episode_page + 1):
            html = self.proc_episode_list_url_request(i)
            if self.downloader:
                self.downloader.title = (
                    f"{tr_('페이지 읽는 중...')} {i + 1}/{total_episode_page+ 1}"
                )
            htmls.append(html)

        for html in htmls:
            soup = Soup(html)
            for element in soup.find_all("i", {"class": "icon ion-bookmark"}):
                novel_numbers.append(int(element["id"].replace("bookmark_", "")))

        if self.downloader:
            self.downloader.title = tr_("{} 개 찾음").format(len(novel_numbers))
        return novel_numbers

    def parse(self) -> List[Page]:
        viewer_numbers: List[int] = []

        if self.is_novel:
            viewer_numbers.extend(self.get_all_viewer_numbers())
        else:
            viewer_numbers.append(int(self.number))

        soups: List[SoupInfo] = []
        for i, viewer_number in enumerate(viewer_numbers, 0):
            if self.downloader:
                self.downloader.title = f"{tr_('읽는 중...')} {i} / {len(viewer_numbers)}"
            r = self.session.get(
                urljoin(self.parsed_url.geturl(), f"/viewer/{viewer_number}")
            )
            soup = Soup(r.text)
            soups.append(SoupInfo(soup, viewer_number))

        parsed_info: List[Page] = []
        for soup_info in soups:
            soup = soup_info.soup

            title_element = soup.find("b", {"class": "cut_line_one"})
            if not title_element:
                if self.is_novel:
                    if self.downloader:
                        self.downloader.print_(
                            f"Ignored because the next item could not be fetched because there was no logged in cookie: {soup_info.number}"
                        )
                    continue
                raise LoginRequired

            if self.downloader:
                self.downloader.title = title_element.text

            # css selecter is not working :(
            ep_num = soup.find(
                "span",
                {
                    "style": "background-color:rgba(155,155,155,0.5);padding: 1px 6px;border-radius: 3px;font-size: 11px; margin-right: 3px;"
                },
            )

            ep_name = soup.find("span", {"class": "cut_line_one"})

            # Dirty but for clean filename
            ep_name.text.replace(ep_num.text, "")

            parsed_info.append(
                Page(
                    clean_title(f"{ep_num.text}: {ep_name.text}.txt", "safe"),
                    soup_info.number,
                )
            )
        return parsed_info


@page_selector.register("test_novelpia")
def _(url: str):
    novelpia_parser = NovelpiaParser(url)
    if not novelpia_parser.is_novel:
        raise Exception(tr_("목록 주소를 입력해주세요"))
    parsed = novelpia_parser.parse()
    NovelpiaParser.cache = parsed
    return parsed


@Downloader.register
class Downloader_novelpia(Downloader):
    type = "test_novelpia"
    URLS = ["novelpia.com"]

    def init(self) -> None:
        self.novelpia_parser = NovelpiaParser(self.url, self)

    def read(self):
        if NovelpiaParser.cache:
            pages = page_selector.filter(NovelpiaParser.cache, self.cw)
            NovelpiaParser.cache.clear()
        else:
            pages = self.novelpia_parser.parse()

        for page in pages:
            # Get real contents
            # https://novelpia.com/proc/viewer_data/:number:
            # {"s": [{"text": ""}]}
            f = BytesIO()
            self.filenames[f] = page.title
            response = self.novelpia_parser.session.get(
                f"https://novelpia.com/proc/viewer_data/{page.number}"
            )
            if response.text:
                response = response.json()
                for text_dict in response["s"]:
                    text = text_dict["text"]
                    if "img" in text:
                        soup = Soup(text)
                        img = soup.find("img")
                        src = img.attrs["src"]
                        filename = img.get("data-filename") or "cover.jpg"
                        f.write(f"[{filename}]".encode("UTF-8"))
                        self.urls.append(f"https:{src}")
                        self.filenames[f"https:{src}"] = filename
                    else:
                        f.write(
                            text_dict["text"].replace("&nbsp;", "\n").encode("UTF-8")
                        )
                f.seek(0)
                self.urls.append(f)
            else:
                raise LoginRequired

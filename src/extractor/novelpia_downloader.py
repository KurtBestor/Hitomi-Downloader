import re
from io import BytesIO
from typing import List, Tuple, cast
from urllib.parse import urlparse

import requests
from bs4.element import Tag
from errors import LoginRequired
from requests.sessions import session
from utils import Downloader, Session, Soup, clean_title, tr_, urljoin


class SoupInfo:
    def __init__(self, soup: Soup, number: int) -> None:
        self.soup: Soup = soup
        self.number: int = number


@Downloader.register
class Downloader_novelpia(Downloader):
    type = "test_novelpia"
    URLS = ["novelpia.com"]

    def init(self) -> None:
        self.parsed_url = urlparse(self.url)  # url 나눔

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
        return urljoin(self.url, "/proc/episode_list")

    def __get_session_with_set_cookies(self) -> Session:
        session = requests.Session()
        user_key = Session().cookies.get("USERKEY", domain=".novelpia.com")
        login_key = Session().cookies.get("LOGINKEY", domain=".novelpia.com")

        if user_key and login_key:
            session.cookies.set("USERKEY", user_key, domain=".novelpia.com")
            session.cookies.set("LOGINKEY", login_key, domain=".novelpia.com")
        return session

    def __proc_episoe_list_url_request(self, session: Session, page: int):
        r = session.post(
            self.proc_episode_list_url,
            data={"novel_no": self.number, "page": page},
        )
        return r.text

    def __get_total_episode_list(self, session: Session) -> Tuple[int, str]:
        regex = re.compile(
            rf"localStorage\['novel_page_{self.number}'\] = '(.+?)'; episode_list\(\);"
        )
        html = self.__proc_episoe_list_url_request(session, 0)
        soup = Soup(html, "lxml")
        page_link_element = soup.find_all("div", {"class": "page-link"})
        last_episode = page_link_element[::-1][0]["onclick"]
        matched = regex.match(last_episode)
        assert matched
        total_episode_page = matched.group(1)
        self.title = tr_("{} 개 찾음".format(total_episode_page))
        return int(total_episode_page), html

    def __get_all_viewer_numbers(self):
        htmls: List[str] = []
        novel_numbers: List[int] = []
        session = self.__get_session_with_set_cookies()
        total_episode_page, html = self.__get_total_episode_list(session)
        htmls.append(html)

        for i in range(1, total_episode_page - 1):
            html = self.__proc_episoe_list_url_request(session, i)
            self.title = f"{tr_('페이지 읽는 중...')} {i + 1}/{total_episode_page}"
            htmls.append(html)

        for html in htmls:
            soup = Soup(html)
            for element in soup.find_all("i", {"class": "icon ion-bookmark"}):
                novel_numbers.append(int(element["id"].replace("bookmark_", "")))

        self.title = tr_("{} 개 찾음").format(len(novel_numbers))
        return novel_numbers

    def read(self):
        viewer_numbers: list[int] = []
        session = self.__get_session_with_set_cookies()

        if self.is_novel:
            viewer_numbers.extend(self.__get_all_viewer_numbers())
        else:
            viewer_numbers.append(int(self.number))

        i = 0
        soups: List[SoupInfo] = []
        for viewer_number in viewer_numbers:
            i += 1
            self.title = f"{tr_('읽는 중...')} {i} / {len(viewer_numbers)}"
            r = session.get(urljoin(self.url, f"/viewer/{viewer_number}"))
            soup = Soup(r.text)
            soups.append(SoupInfo(soup, viewer_number))

        for soup_info in soups:
            soup = soup_info.soup
            f = BytesIO()

            title_element = soup.find("b", {"class": "cut_line_one"})
            if not title_element:
                if self.is_novel:
                    self.print_(
                        f"Ignored because the next item could not be fetched because there was no logged in cookie: {soup_info.number}"
                    )
                    continue
                raise LoginRequired

            self.title = title_element.text
            # Maybe NavigableString?
            assert isinstance(title_element, Tag)

            # css selecter is not working :(
            ep_num = soup.find(
                "span",
                {
                    "style": "background-color:rgba(155,155,155,0.5);padding: 1px 6px;border-radius: 3px;font-size: 11px; margin-right: 3px;"
                },
            )
            assert isinstance(ep_num, Tag)

            ep_name = soup.find("span", {"class": "cut_line_one"})
            assert isinstance(ep_name, Tag)

            # Dirty but for clean filename
            self.print_(ep_name.text)
            ep_name.text.replace(ep_num.text, "")
            self.print_(ep_name.text)
            self.print_(ep_num.text)

            self.filenames[f] = clean_title(
                f"{ep_num.text}: {ep_name.text}.txt", "safe"
            )

            # Get real contents
            # https://novelpia.com/proc/viewer_data/:number:
            # {"s": [{"text": ""}]}

            response = session.get(
                f"https://novelpia.com/proc/viewer_data/{soup_info.number}"
            )
            if response.text:
                response = response.json()
                for text_dict in response["s"]:
                    text = text_dict["text"]
                    if "img" in text:
                        soup = Soup(text)
                        img = soup.find("img")
                        # Maybe NavigableString here too?
                        assert isinstance(img, Tag)
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

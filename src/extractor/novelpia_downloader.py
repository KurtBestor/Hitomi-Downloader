from io import BytesIO
from urllib.parse import urlparse
from typing import List, cast

from requests.sessions import session

from errors import LoginRequired
from utils import Downloader, Soup, Session, clean_title

from bs4.element import Tag
import requests


@Downloader.register
class Downloader_novelpia(Downloader):
    type = "novelpia"
    URLS = ["novelpia.com"]

    def init(self) -> None:
        self.parsed_url = urlparse(self.url)  # url 나눔

    @property
    def is_novel(self) -> bool:
        return "novel" in self.url

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

    def __proc_episoe_list_url_request(self, session: Session, page_no: int):
        r = session.post(
            self.proc_episode_list_url,
            data={"novel_no": self.number, "page_no": page_no},
        )
        return r.text

    def __get_total_episode_list(self, session: Session) -> Tuple[int, str]:
        regex = re.compile(
            rf"localStorage\['novel_page_{self.number}'\] = '(1)'; episode_list\(\);"
        )
        html = self.__proc_episoe_list_url_request(session, 0)
        soup = Soup(html, "lxml")
        page_link_element = soup.find_all("div", {"class": "page-link"})
        last_episode = page_link_element[::-1][0]["onclick"]
        matched = regex.match(last_episode)
        assert matched
        total_episode_page = matched.group(1)
        return int(total_episode_page), html

    def __get_all_viewer_numbers(self):
        htmls: List[str] = []
        viewer_numbers: List[int] = []
        session = self.__get_session_with_set_cookies()
        total_episode_page, html = self.__get_total_episode_list(session)
        htmls.append(html)

        for i in range(1, total_episode_page - 1):
            html = self.__proc_episoe_list_url_request(session, i)
            htmls.append(html)

        for html in htmls:
            soup = Soup(html)
            for element in soup.find_all("i", {"class": "icon ion-bookmark"}):
                viewer_numbers.append(int(element["id"]))

        return viewer_numbers

    def read(self):
        session = self.__get_cookie()
        f = BytesIO()

        title_element = self.soup.find("b", {"class": "cut_line_one"})

        if not title_element:
            raise LoginRequired

        # Maybe NavigableString?
        assert isinstance(title_element, Tag)
        self.title = title_element.text

        # css selecter is not working :(
        ep_num = self.soup.find(
            "span",
            {
                "style": "background-color:rgba(155,155,155,0.5);padding: 1px 6px;border-radius: 3px;font-size: 11px; margin-right: 3px;"
            },
        )
        assert isinstance(ep_num, Tag)

        ep_name = self.soup.find("span", {"class": "cut_line_one"})
        assert isinstance(ep_name, Tag)

        # Dirty but for clean filename
        self.print_(ep_name.text)
        ep_name.text.replace(ep_num.text, "")
        self.print_(ep_name.text)
        self.print_(ep_num.text)

        self.filenames[f] = clean_title(f"{ep_num.text}: {ep_name.text}.txt", "safe")

        # https://novelpia.com/viewer/:number:
        numbers: List[str] = []
        numbers.append(self.__get_number(self.parsed_url[2]))

        # Get real contents
        # https://novelpia.com/proc/viewer_data/:number:
        # {"s": [{"text": ""}]}
        viewer_datas = map(
            lambda number: f"https://novelpia.com/proc/viewer_data/{number}", numbers
        )
        for viewer_data in viewer_datas:
            response = session.get(viewer_data)
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
                    else:
                        f.write(text_dict["text"].encode("UTF-8"))
                f.seek(0)
                self.urls.append(f)
            else:
                raise LoginRequired

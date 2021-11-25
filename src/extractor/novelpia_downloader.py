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

    def __get_number(self, url: str) -> str:
        return url.replace("/viewer/", "")

    def __get_cookie(self) -> Session:
        session = requests.Session()
        user_key = Session().cookies.get("USERKEY", domain=".novelpia.com")
        login_key = Session().cookies.get("LOGINKEY", domain=".novelpia.com")

        if user_key and login_key:
            session.cookies.set("USERKEY", user_key, domain=".novelpia.com")
            session.cookies.set("LOGINKEY", login_key, domain=".novelpia.com")
        return session

    def init(self) -> None:
        self.parsed_url = urlparse(self.url)  # url 나눔
        self.soup = Soup(requests.get(self.url).text)

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
                        filename = img.attrs["data-filename"]
                        f.write(f"[{filename}]".encode("UTF-8"))
                        self.urls.append(f"https:{src}")
                    else:
                        f.write(text_dict["text"].encode("UTF-8"))
                f.seek(0)
                self.urls.append(f)
            else:
                raise LoginRequired

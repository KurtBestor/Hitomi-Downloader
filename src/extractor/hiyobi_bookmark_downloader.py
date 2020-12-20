# coding: UTF-8
# title: Hiyobi.me 북마크 다운로드 스크립트
# comment: Hiyobi.me 북마크를 다운로드합니다
# author: SaidBySolo

"""
MIT License

Copyright (c) 2020 Saebasol

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import asyncio
from io import BytesIO

import aiohttp

from utils import Downloader
from translator import tr_


@Downloader.register
class DownloaderHiyobiBookmark(Downloader):
    type = "hiyobibookmark"

    def init(self) -> None:
        self.url: str = self.url.replace("hiyobibookmark_", "")
        self.bookmark_info_list: list = []
        self.username: str = "User"

    def read(self) -> None:
        account_info: list = self.url.split("/")

        if not len(account_info) == 2:
            return self.Invalid("이메일/비밀번호 형식으로 작성해주세요.")

        email = account_info[0]
        password = account_info[1]

        result = asyncio.run(self.main(email, password))

        if result:
            return result

        f = BytesIO()
        f.write("\n".join(self.bookmark_info_list).encode("UTF-8"))
        f.seek(0)
        self.title = self.username
        self.urls.append(f)
        self.filenames[f] = "bookmark.txt"

    async def main(self, email: str, password: str):
        token_or_errorMsg = await self.post_account_info(email, password)

        if isinstance(token_or_errorMsg, str):
            return token_or_errorMsg

        bookmark_info = await self.post_hiyobi_bookmark(token_or_errorMsg)

        bookmark_total_count: int = bookmark_info["count"]

        if bookmark_total_count == 0:
            return self.Invalid("북마크된 정보가 없는거같아요.")

        count = (
            round(bookmark_total_count / 15) + 1
            if not (bookmark_total_count / 15).is_integer()
            else round(bookmark_total_count / 15)
        ) + 1

        await self.add_in_bookmark_info_list(count, token_or_errorMsg)

    async def add_in_bookmark_info_list(self, count: int, token: str) -> None:
        for paging in range(1, count):
            self.title = tr_("총 {}페이지 중 {}번 페이지 읽는 중...").format(count - 1, paging)
            paged_bookmark_info = await self.post_hiyobi_bookmark(token, paging)
            self.parsing_bookmark(paged_bookmark_info["list"])

    def parsing_bookmark(self, bookmark_list: list) -> None:
        for bookmark_element in bookmark_list:
            search = bookmark_element["search"]
            number = bookmark_element["number"]
            if search:
                self.bookmark_info_list.append(search)
            elif number:
                self.bookmark_info_list.append(str(number))
            else:
                # 추후 디버깅
                raise Exception(bookmark_element)

    async def post(self, url: str, **kwargs) -> dict:
        async with aiohttp.ClientSession() as cs:
            async with cs.post(url, **kwargs) as r:
                return await r.json()

    async def post_hiyobi_bookmark(self, token: str, paging: int = 1) -> dict:
        await asyncio.sleep(1)
        response = await self.post(
            f"https://api.hiyobi.me/bookmark/{paging}",
            headers={
                "referrer": "https://hiyobi.me/",
                "authorization": f"Bearer {token}",
            },
            json={"paging": paging},
        )
        return response

    async def post_account_info(self, email: str, password: str):
        response = await self.post(
            "https://api.hiyobi.me/user/login",
            headers={
                "referrer": "https://hiyobi.me/",
            },
            json={"email": email, "password": password, "remember": True},
        )

        if response.get("errorMsg"):
            return self.Invalid(response["errorMsg"])

        self.username = response["data"]["name"]
        return response["data"]["token"]

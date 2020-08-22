from bs4 import BeautifulSoup
from urllib.request import urlopen
from urllib.parse import unquote
@Downloader.register
class Downloader_yandere(Downloader):
    type = 'yande.re'
    URLS = ['yande.re']
    
    def init(self):
        self.single = False

    @property
    def id(self):
        if 'page' in self.url:
            self.url= "https://yande.re/post?" + self.url.split("&")[-1]
        return self.url

    def read(self):
        while True:
            html = urlopen(self.url)
            soup = BeautifulSoup(html, "html.parser")
            tmp = soup.find_all(attrs={'class':'directlink'}, href=True)
            for image_html in tmp:
                image_url = image_html['href']
                self.urls.append(image_url)
                self.filenames[image_url] = self.get_filename(image_url)
                
            self.title = self.get_title(self.url)

            next_page = soup.find('a', attrs={'rel':'next'}, href=True)
            if not next_page:
                break
            else:
                self.url = u"https://yande.re" +next_page['href']

    
    def get_id(self, url:str) -> str:
        id_begin = url.find("yande.re%20") + 11
        id_end = url[id_begin:].find("%20")
        return url[id_begin:][:id_end]

    def get_filename(self, url:str) -> str:
        url_unquote = unquote(url)
        id_tags_extension = url_unquote.split("yande.re")[-1].split(" ")[1:]
        return "_".join(id_tags_extension)
        
        

    def get_title(self, url:str) -> str:
        if "tags=" not in url:
            return '[N/A]' + url.split('yande.re/')[-1]
            
        url_tags = url.split("tags=")[-1].split('+')

        return " ".join(url_tags)


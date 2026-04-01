import os
import re
import asyncio
import random
import aiohttp
import cloudscraper
import pikepdf
import shutil
import sys
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm
from functools import wraps
from PIL import Image

# --- RETRY DECORATOR ---
def retry_on_failure(max_retries=3, base_delay=1):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    if attempt == max_retries - 1: return None
                    await asyncio.sleep((base_delay * (2 ** attempt)) + random.uniform(0, 1))
            return None
        return wrapper
    return decorator

class Nhentai2PDF:
    def __init__(self, concurrency_limit=5):
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        # Your Luxurious GDrive Path
        self.output_dir = r"G:\My Drive\Luxurious Chest\Doujin Archives"
        os.makedirs(self.output_dir, exist_ok=True)

    def _sanitize(self, text):
        return re.sub(r'[\\/*?:"<>|]', "", text).strip().replace(" ", "_")

    def fetch_metadata(self, code):
        url = f"https://nhentai.net/g/{code}/"
        resp = self.scraper.get(url)
        if resp.status_code != 200: 
            raise Exception(f"HTTP {resp.status_code}: Access Denied or Invalid Code")
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        cover_img = soup.find('div', id='cover').find('img')
        img_src = cover_img.get('data-src') or cover_img.get('src')
        media_id = re.search(r'galleries/(\d+)/', img_src).group(1)
        
        title = soup.find('span', class_='pretty').text
        total_pages = len(soup.find_all('div', class_='thumb-container'))
        
        artist_tag = soup.find('a', href=re.compile(r'/artist/'))
        artist_name = artist_tag.find('span', class_='name').text if artist_tag else "Unknown"
        
        # Comprehensive Tag and Language Extraction
        tags = [t.find('span', class_='name').text for t in soup.find_all('a', href=re.compile(r'/tag/'))]
        
        # Specifically target the language category
        lang_tags = [t.find('span', class_='name').text for t in soup.find_all('a', href=re.compile(r'/language/'))]
        # Filter out 'translated' to find the actual language (English, Japanese, etc.)
        detected_lang = "Unknown"
        for l in lang_tags:
            if l.lower() != "translated":
                detected_lang = l.capitalize()
                break

        return {
            "title": title,
            "safe_title": self._sanitize(title),
            "media_id": media_id,
            "total_pages": total_pages,
            "artist": artist_name,
            "tags": tags,
            "language": detected_lang,
            "url": url
        }

    async def download_page(self, session, media_id, page_num, temp_path):
        extensions = ['jpg', 'png', 'webp', 'gif']
        async with self.semaphore:
            for ext in extensions:
                url = f"https://i.nhentai.net/galleries/{media_id}/{page_num}.{ext}"
                try:
                    async with session.get(url, timeout=12) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            file_path = os.path.join(temp_path, f"{page_num:03d}.{ext}")
                            with open(file_path, "wb") as f:
                                f.write(content)
                            return True
                except: continue
            return False

    async def execute(self, code):
        print(f"\n[*] Querying Archive ID: {code}...")
        data = self.fetch_metadata(code)
        
        print("=" * 60)
        print(f"  TARGET   : {data['title']}")
        print(f"  ARTIST   : {data['artist']}")
        print(f"  LANGUAGE : {data['language']}")
        print(f"  VOLUME   : {data['total_pages']} Pages")
        print("=" * 60)
        
        confirm = input(f"Compile this entry? (y/n): ").lower()
        if confirm != 'y':
            print("[!] Operation scrubbed.")
            return

        temp_path = f"temp_{code}"
        os.makedirs(temp_path, exist_ok=True)
        cookies = self.scraper.cookies.get_dict()
        headers = {"User-Agent": self.scraper.headers['User-Agent'], "Referer": "https://nhentai.net/"}

        async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
            tasks = [self.download_page(session, data['media_id'], i, temp_path) for i in range(1, data['total_pages'] + 1)]
            results = await tqdm.gather(*tasks, desc=f"Progress [{code}]", unit="pg")

        if not all(results):
            print(f"\n[!] ERROR: Integrity check failed.")
            shutil.rmtree(temp_path)
            return

        # Filename now includes Language for quick OS-level sorting
        final_filename = os.path.join(self.output_dir, f"{code}_[{data['artist']}]_{data['safe_title']}.pdf")
        
        img_files = [os.path.join(temp_path, f) for f in sorted(os.listdir(temp_path)) 
                     if f.lower().endswith(('.jpg', '.png', '.webp', '.gif'))]

        print(f"[*] Normalizing aspect ratios (1600x2260)...")
        processed_pages = []
        TARGET_W, TARGET_H = 1600, 2260 

        for img_path in img_files:
            img = Image.open(img_path).convert('RGB')
            ratio = min(TARGET_W / img.width, TARGET_H / img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            canvas = Image.new('RGB', (TARGET_W, TARGET_H), (255, 255, 255))
            canvas.paste(img, ((TARGET_W - new_size[0]) // 2, (TARGET_H - new_size[1]) // 2))
            processed_pages.append(canvas)

        print(f"[*] Compiling & Linearizing (Quality: 90)...")
        processed_pages[0].save(
            final_filename, 
            save_all=True, 
            append_images=processed_pages[1:], 
            resolution=100.0, 
            quality=90
        )
        
        # Refined Metadata Injection with pikepdf
        with pikepdf.open(final_filename, allow_overwriting_input=True) as pdf:
            with pdf.open_metadata() as meta:
                # Displays Language in the PDF Viewer Title Bar
                meta['dc:title'] = f"{data['title']} [{data['language']}]"
                meta['dc:creator'] = [data['artist']]
                meta['dc:subject'] = data['tags']
                # Standard XMP field for language-based filtering
                meta['dc:language'] = [data['language'].lower()]
            
            # Linearize enables Fast Web View (FIFO loading)
            pdf.save`(final_filename, linearize=True)
        
        shutil.rmtree(temp_path)
        print("=" * 60)
        print(f"  TARGET   : {data['title']}")
        print(f"  ARTIST   : {data['artist']}")
        print(f"  LANGUAGE : {data['language']}")
        print(f"  VOLUME   : {data['total_pages']} Pages")
        print("=" * 60)
        print(f"  [!] Compile success. [{data['title']}]")
        print(f"      in [{data['language']}] Archive completed. 😏")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py nh2pdf.py <code_here>")
    else:
        try:
            asyncio.run(Nhentai2PDF().execute(sys.argv[1]))
        except KeyboardInterrupt: print("\n[!] Emergency Stop.")
        except Exception as e: print(f"\n[!] Critical System Error: {e}")
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
    def __init__(self, output_dir=r"G:\My Drive\Luxurious Chest\Doujin Archives", concurrency_limit=5):
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        
        # Determine output directory
        base_path = os.path.abspath(output_dir)
        drive = os.path.splitdrive(base_path)[0]
        
        if drive and not os.path.exists(drive + os.sep):
            print(f"[*] Drive {drive} not found. Falling back to 'outputs'.")
            self.output_dir = "outputs"
        else:
            self.output_dir = output_dir

        try:
            os.makedirs(self.output_dir, exist_ok=True)
        except Exception as e:
            print(f"[!] Could not create {self.output_dir}: {e}. Falling back to 'outputs'.")
            self.output_dir = "outputs"
            os.makedirs(self.output_dir, exist_ok=True)

    def _sanitize(self, text):
        return re.sub(r'[\\/*?:"<>|]', "", text).strip().replace(" ", "_")

    def fetch_metadata(self, code):
        """Fetch metadata using the v2 API."""
        api_url = f"https://nhentai.net/api/v2/galleries/{code}"
        resp = self.scraper.get(api_url)
        
        if resp.status_code == 403:
            raise Exception("Access Denied (Cloudflare). Try updating cloudscraper or using a VPN.")
        if resp.status_code == 404:
            raise Exception(f"Gallery {code} not found (might have been removed).")
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}: Error fetching metadata.")

        try:
            data = resp.json()
        except Exception:
            raise Exception("Failed to parse API response.")

        # Mapping API fields to our structure
        title = data.get('title', {}).get('pretty') or data.get('title', {}).get('english', 'Untitled')
        media_id = data.get('media_id')
        total_pages = data.get('num_pages')
        
        # Tags processing
        tags = []
        artist = "Unknown"
        language = "Unknown"
        
        for t in data.get('tags', []):
            t_type = t.get('type')
            t_name = t.get('name', '')
            if t_type == 'tag':
                tags.append(t_name)
            elif t_type == 'artist':
                artist = t_name
            elif t_type == 'language' and t_name.lower() != 'translated':
                language = t_name.capitalize()

        # Image extensions mapping
        # API uses: 'j' -> jpg, 'p' -> png, 'w' -> webp
        ext_map = {'j': 'jpg', 'p': 'png', 'w': 'webp'}
        pages_ext = [ext_map.get(p.get('t'), 'jpg') for p in data.get('images', {}).get('pages', [])]

        return {
            "title": title,
            "safe_title": self._sanitize(title),
            "media_id": media_id,
            "total_pages": total_pages,
            "artist": artist,
            "tags": tags,
            "language": language,
            "pages_ext": pages_ext
        }

    @retry_on_failure(max_retries=3, base_delay=1)
    async def _fetch_image(self, session, url, path):
        async with session.get(url, timeout=12) as resp:
            if resp.status == 200:
                content = await resp.read()
                with open(path, "wb") as f:
                    f.write(content)
                return True
            return False

    async def download_page(self, session, media_id, page_num, ext, temp_path):
        async with self.semaphore:
            url = f"https://i.nhentai.net/galleries/{media_id}/{page_num}.{ext}"
            file_path = os.path.join(temp_path, f"{page_num:04d}.{ext}")
            try:
                return await self._fetch_image(session, url, file_path)
            except Exception:
                return False

    async def execute(self, code):
        print(f"\n[*] Querying Archive ID: {code}...")
        try:
            data = self.fetch_metadata(code)
        except Exception as e:
            print(f"[!] Metadata Fetch Error: {e}")
            return

        print("=" * 60)
        print(f"  TARGET   : {data['title']}")
        print(f"  ARTIST   : {data['artist']}")
        print(f"  LANGUAGE : {data['language']}")
        print(f"  VOLUME   : {data['total_pages']} Pages")
        print("=" * 60)
        
        confirm = input(f"Compile this entry? [Enter to Continue / n to Cancel]: ").lower()
        if confirm == 'n':
            print("[!] Operation scrubbed.")
            return

        temp_path = f"temp_{code}"
        os.makedirs(temp_path, exist_ok=True)
        
        # Sync cookies and UA from cloudscraper to aiohttp
        cookies = self.scraper.cookies.get_dict()
        headers = {
            "User-Agent": self.scraper.headers.get('User-Agent'),
            "Referer": "https://nhentai.net/"
        }

        async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
            tasks = []
            for i, ext in enumerate(data['pages_ext'], 1):
                tasks.append(self.download_page(session, data['media_id'], i, ext, temp_path))
            
            results = await tqdm.gather(*tasks, desc=f"Progress [{code}]", unit="pg")

        if not all(results):
            failed = len([r for r in results if not r])
            print(f"\n[!] ERROR: Integrity check failed. {failed} page(s) failed to download.")
            # We don't delete temp_path immediately so user can see what failed? 
            # Actually, the original code deleted it.
            shutil.rmtree(temp_path)
            return

        # Prepare final filename
        final_filename = os.path.join(self.output_dir, f"{code}_[{data['artist']}]_{data['safe_title']}.pdf")
        
        img_files = []
        for f in sorted(os.listdir(temp_path)):
            if f.lower().endswith(('.jpg', '.png', '.webp', '.gif')):
                img_files.append(os.path.join(temp_path, f))

        print(f"[*] Normalizing and Compiling (1600x2260)...")
        TARGET_W, TARGET_H = 1600, 2260 
        processed_img_files = []

        for img_path in img_files:
            try:
                with Image.open(img_path) as img:
                    img = img.convert('RGB')
                    ratio = min(TARGET_W / img.width, TARGET_H / img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
                    canvas = Image.new('RGB', (TARGET_W, TARGET_H), (255, 255, 255))
                    canvas.paste(resized_img, ((TARGET_W - new_size[0]) // 2, (TARGET_H - new_size[1]) // 2))
                    
                    proc_path = img_path + ".jpg"
                    canvas.save(proc_path, "JPEG", quality=90)
                    processed_img_files.append(proc_path)
            except Exception as e:
                print(f"[!] Error processing {img_path}: {e}")

        if processed_img_files:
            # We use img2pdf if available for faster joining, but since we already resized...
            # Pillow's save_all is fine since we are re-opening them via a generator.
            first_img = Image.open(processed_img_files[0])
            first_img.save(
                final_filename, 
                save_all=True, 
                append_images=(Image.open(p) for p in processed_img_files[1:]), 
                resolution=100.0, 
                quality=90
            )
            first_img.close()
        
        # Inject Metadata
        try:
            with pikepdf.open(final_filename, allow_overwriting_input=True) as pdf:
                with pdf.open_metadata() as meta:
                    meta['dc:title'] = f"{data['title']} [{data['language']}]"
                    meta['dc:creator'] = [data['artist']]
                    meta['dc:subject'] = data['tags']
                    meta['dc:language'] = [data['language'].lower()]
                pdf.save(final_filename, linearize=True)
        except Exception as e:
            print(f"[!] Warning: Failed to inject metadata: {e}")
        
        shutil.rmtree(temp_path)
        print("=" * 60)
        print(f"   -> Success: [{data['title']}]")
        print(f"      Archive completed: {final_filename}")
        print("=" * 60)

def main():
    if len(sys.argv) < 2:
        print("Usage: nh2pdf <code_here>")
    else:
        code = sys.argv[1]
        try:
            asyncio.run(Nhentai2PDF().execute(code))
        except KeyboardInterrupt:
            print("\n[!] Emergency Stop.")
        except Exception as e:
            print(f"\n[!] Critical System Error: {e}")

if __name__ == "__main__":
    main()
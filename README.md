# 🏛️ nhentai2pdf: Luxurious Archive Architect

A high-performance, asynchronous Python utility designed to fetch, normalize, and archive galleries into a structured PDF format. Optimized for local Google Drive synchronization, high-fidelity viewing, and memory efficiency across extremely large multi-hundred page archives.

## ✨ Key Features
* **Asynchronous Downloads:** Utilizes `aiohttp` and `asyncio` for high-speed concurrent fetching.
* **Resilient Connectivity:** Automatically catches and retries failed downloads caused by intermittent timeouts or client drops.
* **Universal Extension Hunter:** Automatically detects and resolves mixed-format galleries (JPG, PNG, WebP, GIF).
* **Aspect Ratio Normalization:** Every page is centered on a uniform 1600x2260 canvas to prevent "jumping" during reading.
* **Memory-Efficient PDF Compilation:** Leverages on-disk buffering and generator consumption to compile massive archives without encountering out-of-memory errors on system RAM.
* **Metadata Injection:** Bakes Artist, Title, Language, and Tags directly into the PDF metadata via `pikepdf`.
* **Configurable Outputs:** Defaults storage directly to a designated Google Drive path, but is configured to cleanly accept any custom directory.
* **Strict Integrity Check:** Aborts compilation if a page critically fails to download, ensuring 100% complete archives.

## 🛠️ Prerequisites

Ensure you have Python 3.9+ installed. You will need the following libraries:

```powershell
pip install aiohttp cloudscraper beautifulsoup4 tqdm pikepdf Pillow
```

## 🚀 Usage

Run the script using the Python launcher or standard `python` command:

```powershell
py nh2pdf.py <6-digit-code>
```

### Execution Flow:
1. **Metadata Fetch:** The script connects and displays the Title, Artist, Language, and Page Count.
2. **Handshake:** You will be prompted to confirm the download (`[Enter to Continue / n to Cancel]`).
3. **Download:** Pages are fetched asynchronously into a temporary directory using automatic retry failsafes.
4. **Processing & Export:** Images are individually resized to a uniform `1600x2260` canvas, streamed sequentially into a multi-page PDF object, and cleanly saved to your output directory. The output filename neatly incorporates the Language tag.

## 📁 Project Structure
* `nh2pdf.py`: The core architect script.
* `temp_XXXXXX/`: Temporary storage for raw images during the fetch and conversion process (auto-cleaned after success/failure).
* **Outputs:** Defaults to `G:\My Drive\Luxurious Chest\Doujin Archives`.

## ⚠️ Requirements & Limitations
* **Cloudflare:** Uses `cloudscraper` to bypass basic bot detection. If HTTP connectivity issues persist during the handshake phase, ensure your proxy/VPN/WARP is active.
* **Drive Path:** Ensure your G: drive is securely mounted before execution if you are saving straight to your Google Drive ecosystem.

---
*Created for the Luxurious Chest Collection. 😏*

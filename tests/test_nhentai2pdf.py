import os
import pytest
import aiohttp
from unittest.mock import patch, MagicMock, AsyncMock
from nhentai2pdf import Nhentai2PDF

@pytest.fixture
def mock_scraper():
    with patch('nhentai2pdf.cloudscraper.create_scraper') as mock:
        yield mock

def test_init_creates_output_dir(tmp_path, mock_scraper):
    output_dir = tmp_path / "custom_outputs"
    nh2pdf = Nhentai2PDF(output_dir=str(output_dir))
    assert os.path.exists(output_dir)
    assert nh2pdf.output_dir == str(output_dir)

def test_init_fallback_dir(mock_scraper):
    with patch('os.makedirs', side_effect=[Exception("Mock Error"), None]):
        nh2pdf = Nhentai2PDF(output_dir="/invalid/dir")
        assert nh2pdf.output_dir == "outputs"

def test_sanitize(mock_scraper):
    nh2pdf = Nhentai2PDF()
    assert nh2pdf._sanitize("A Title? *With: <Invalid> Characters|") == "A_Title_With_Invalid_Characters"

def test_fetch_metadata_success(mock_scraper):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "title": {"english": "Test Gallery"},
        "media_id": "12345",
        "num_pages": 2,
        "tags": [
            {"type": "tag", "name": "tag1"},
            {"type": "artist", "name": "artist1"},
            {"type": "language", "name": "translated"}
        ],
        "images": {
            "pages": [
                {"t": "j"},
                {"t": "p"}
            ]
        }
    }
    mock_scraper.return_value.get.return_value = mock_resp

    nh2pdf = Nhentai2PDF()
    data = nh2pdf.fetch_metadata("123456")

    assert data["title"] == "Test Gallery"
    assert data["media_id"] == "12345"
    assert data["total_pages"] == 2
    assert data["artist"] == "artist1"
    assert "tag1" in data["tags"]
    assert data["pages_ext"] == ["jpg", "png"]

def test_fetch_metadata_403(mock_scraper):
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_scraper.return_value.get.return_value = mock_resp

    nh2pdf = Nhentai2PDF()
    with pytest.raises(Exception, match="Access Denied"):
        nh2pdf.fetch_metadata("123456")

@pytest.mark.asyncio
async def test_fetch_image_success(mock_scraper, tmp_path):
    nh2pdf = Nhentai2PDF()
    temp_file = tmp_path / "test.jpg"

    mock_session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b"fake_image_data"

    # Mocking async context manager
    mock_session.get.return_value.__aenter__.return_value = mock_resp
    mock_session.get.return_value.__aexit__.return_value = None

    result = await nh2pdf._fetch_image(mock_session, "http://fake.url", str(temp_file))

    assert result is True
    assert os.path.exists(temp_file)
    with open(temp_file, "rb") as f:
        assert f.read() == b"fake_image_data"

@pytest.mark.asyncio
async def test_fetch_image_failure(mock_scraper):
    nh2pdf = Nhentai2PDF()

    mock_session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 404

    # Mocking async context manager
    mock_session.get.return_value.__aenter__.return_value = mock_resp
    mock_session.get.return_value.__aexit__.return_value = None

    result = await nh2pdf._fetch_image(mock_session, "http://fake.url", "fake.jpg")

    assert result is False

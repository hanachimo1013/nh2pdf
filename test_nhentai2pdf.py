import os
import pytest
from unittest.mock import AsyncMock
from nhentai2pdf import Nhentai2PDF

@pytest.fixture
def instance():
    # Pass a specific output dir to avoid cluttering or hitting real dirs
    return Nhentai2PDF(output_dir="test_outputs", concurrency_limit=2)

@pytest.mark.asyncio
async def test_download_page_success(instance):
    instance._fetch_image = AsyncMock(return_value=True)
    session_mock = "mock_session"

    media_id = "12345"
    page_num = 1
    ext = "jpg"
    temp_path = "temp"

    result = await instance.download_page(session_mock, media_id, page_num, ext, temp_path)

    assert result is True
    expected_url = f"https://i.nhentai.net/galleries/12345/1.jpg"
    expected_file_path = os.path.join("temp", "0001.jpg")
    instance._fetch_image.assert_called_once_with("mock_session", expected_url, expected_file_path)

@pytest.mark.asyncio
async def test_download_page_failure(instance):
    instance._fetch_image = AsyncMock(return_value=False)

    result = await instance.download_page("mock_session", "54321", 2, "png", "temp")

    assert result is False
    expected_url = f"https://i.nhentai.net/galleries/54321/2.png"
    expected_file_path = os.path.join("temp", "0002.png")
    instance._fetch_image.assert_called_once_with("mock_session", expected_url, expected_file_path)

@pytest.mark.asyncio
async def test_download_page_exception(instance):
    instance._fetch_image = AsyncMock(side_effect=Exception("Test Error"))

    result = await instance.download_page("mock_session", "999", 3, "webp", "temp")

    assert result is False
    expected_url = f"https://i.nhentai.net/galleries/999/3.webp"
    expected_file_path = os.path.join("temp", "0003.webp")
    instance._fetch_image.assert_called_once_with("mock_session", expected_url, expected_file_path)

import pytest
import os
import shutil
from unittest.mock import patch, MagicMock
from nhentai2pdf import Nhentai2PDF
from PIL import Image

@pytest.fixture
def temp_output_dir(tmp_path):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    return str(output_dir)

@pytest.fixture
def mock_metadata():
    return {
        "title": "Test Title",
        "safe_title": "Test_Title",
        "media_id": "123456",
        "total_pages": 2,
        "artist": "Test Artist",
        "tags": ["tag1", "tag2"],
        "language": "English",
        "pages_ext": ["jpg", "png"]
    }

@pytest.mark.asyncio
@patch('nhentai2pdf.Nhentai2PDF.fetch_metadata')
@patch('builtins.input')
async def test_execute_metadata_fetch_error(mock_input, mock_fetch_metadata, temp_output_dir):
    nh2pdf = Nhentai2PDF(output_dir=temp_output_dir)
    mock_fetch_metadata.side_effect = Exception("Test Exception")

    result = await nh2pdf.execute("123456")

    assert result is False
    mock_input.assert_not_called()

@pytest.mark.asyncio
@patch('nhentai2pdf.Nhentai2PDF.fetch_metadata')
@patch('builtins.input')
async def test_execute_user_cancel(mock_input, mock_fetch_metadata, mock_metadata, temp_output_dir):
    nh2pdf = Nhentai2PDF(output_dir=temp_output_dir)
    mock_fetch_metadata.return_value = mock_metadata
    mock_input.return_value = 'n'

    result = await nh2pdf.execute("123456")

    assert result is False
    mock_input.assert_called_once()

@pytest.mark.asyncio
@patch('nhentai2pdf.Nhentai2PDF.fetch_metadata')
@patch('builtins.input')
@patch('nhentai2pdf.Nhentai2PDF._fetch_image')
async def test_execute_download_failure(mock_fetch_image, mock_input, mock_fetch_metadata, mock_metadata, temp_output_dir):
    nh2pdf = Nhentai2PDF(output_dir=temp_output_dir)
    mock_fetch_metadata.return_value = mock_metadata
    mock_input.return_value = ''

    # Simulate first page success, second page failure
    async def mock_fetch_image_side_effect(session, url, path):
        if "2.png" in url:
            return False
        # Create a dummy image for the successful one
        img = Image.new('RGB', (10, 10), color='red')
        img.save(path)
        return True

    mock_fetch_image.side_effect = mock_fetch_image_side_effect

    result = await nh2pdf.execute("123456")

    assert result is False
    assert not os.path.exists(f"temp_123456")

@pytest.mark.asyncio
@patch('nhentai2pdf.Nhentai2PDF.fetch_metadata')
@patch('builtins.input')
@patch('nhentai2pdf.Nhentai2PDF._fetch_image')
async def test_execute_success(mock_fetch_image, mock_input, mock_fetch_metadata, mock_metadata, temp_output_dir):
    nh2pdf = Nhentai2PDF(output_dir=temp_output_dir)
    mock_fetch_metadata.return_value = mock_metadata
    mock_input.return_value = ''

    async def mock_fetch_image_side_effect(session, url, path):
        # Need to create valid image files for pikepdf and pillow to read
        img = Image.new('RGB', (100, 100), color='white')
        img.save(path)
        return True

    mock_fetch_image.side_effect = mock_fetch_image_side_effect

    result = await nh2pdf.execute("123456")

    assert result is True
    # Verify the output PDF was created
    expected_pdf_path = os.path.join(temp_output_dir, "123456_[Test Artist]_Test_Title.pdf")
    assert os.path.exists(expected_pdf_path)

    # Verify temp directory is cleaned up
    assert not os.path.exists("temp_123456")

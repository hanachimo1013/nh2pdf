import pytest
from nhentai2pdf import Nhentai2PDF

def test_sanitize_removes_invalid_characters():
    assert Nhentai2PDF._sanitize(None, 'a\\b/c*d?e:f"g<h>i|j') == 'abcdefghij'

def test_sanitize_strips_whitespace():
    assert Nhentai2PDF._sanitize(None, '  hello  ') == 'hello'

def test_sanitize_replaces_spaces_with_underscores():
    assert Nhentai2PDF._sanitize(None, 'hello world') == 'hello_world'

def test_sanitize_combined():
    assert Nhentai2PDF._sanitize(None, '  [Artist] Title: Volume 1?  ') == '[Artist]_Title_Volume_1'

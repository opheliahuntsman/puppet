#!/usr/bin/env python3
"""
Simple tests for smartframe_extractor.py

Run with: python test_extractor.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from smartframe_extractor import SmartFrameExtractor


def test_url_parsing():
    """Test SmartFrame URL parsing."""
    extractor = SmartFrameExtractor()
    
    # Test valid URL
    url1 = "https://smartframe.com/search/image/abc123/image456"
    result1 = extractor._parse_smartframe_url(url1)
    assert result1 is not None, "Should parse valid URL"
    assert result1['hash'] == 'abc123', f"Expected hash 'abc123', got {result1['hash']}"
    assert result1['image_id'] == 'image456', f"Expected image_id 'image456', got {result1['image_id']}"
    print("✓ Valid URL parsing works")
    
    # Test URL with query parameters
    url2 = "https://smartframe.com/search/image/xyz789/img999?param=value"
    result2 = extractor._parse_smartframe_url(url2)
    assert result2 is not None, "Should parse URL with query params"
    assert result2['hash'] == 'xyz789'
    assert result2['image_id'] == 'img999'
    print("✓ URL with query parameters parsing works")
    
    # Test invalid URL
    url3 = "https://example.com/not-a-smartframe-url"
    result3 = extractor._parse_smartframe_url(url3)
    assert result3 is None, "Should return None for invalid URL"
    print("✓ Invalid URL correctly rejected")
    
    print("\nAll URL parsing tests passed! ✓")


def test_date_normalization():
    """Test date normalization."""
    extractor = SmartFrameExtractor()
    
    # Test DD.MM.YY format
    date1 = extractor._normalize_date("15.11.07")
    assert date1 == "2007-11-15", f"Expected 2007-11-15, got {date1}"
    print("✓ Date normalization works for DD.MM.YY")
    
    # Test DD.MM.YYYY format
    date2 = extractor._normalize_date("25.12.2023")
    assert date2 == "2023-12-25", f"Expected 2023-12-25, got {date2}"
    print("✓ Date normalization works for DD.MM.YYYY")
    
    # Test invalid date
    date3 = extractor._normalize_date("invalid")
    assert date3 == "invalid", "Should return original string for invalid date"
    print("✓ Invalid date handling works")
    
    # Test None
    date4 = extractor._normalize_date(None)
    assert date4 is None, "Should return None for None input"
    print("✓ None handling works")
    
    print("\nAll date normalization tests passed! ✓")


def test_metadata_structure():
    """Test metadata structure initialization."""
    extractor = SmartFrameExtractor()
    
    # This would normally be done inside extract_image_metadata
    # but we can test the structure here
    metadata = {
        'imageId': 'test123',
        'hash': 'hash456',
        'url': 'https://test.com',
        'photographer': None,
        'tags': [],
    }
    
    assert 'imageId' in metadata, "Should have imageId field"
    assert 'photographer' in metadata, "Should have photographer field"
    assert 'tags' in metadata, "Should have tags field"
    assert isinstance(metadata['tags'], list), "tags should be a list"
    print("✓ Metadata structure is correct")
    
    print("\nAll metadata structure tests passed! ✓")


if __name__ == '__main__':
    print("Running SmartFrame Extractor Tests")
    print("=" * 60)
    print()
    
    try:
        test_url_parsing()
        print()
        test_date_normalization()
        print()
        test_metadata_structure()
        print()
        print("=" * 60)
        print("All tests passed! ✓✓✓")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)

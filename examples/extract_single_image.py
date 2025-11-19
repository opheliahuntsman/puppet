#!/usr/bin/env python3
"""
Example: Extract metadata from a single SmartFrame image

This script demonstrates basic usage of the SmartFrame extractor.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import smartframe_extractor
sys.path.insert(0, str(Path(__file__).parent.parent))

from smartframe_extractor import SmartFrameExtractor


async def main():
    """Extract and display metadata from a SmartFrame image."""
    
    # Example URL - replace with actual SmartFrame URL
    example_url = "https://smartframe.com/search/image/CUSTOMER_ID/IMAGE_ID"
    
    print("SmartFrame Extractor - Single Image Example")
    print("=" * 60)
    
    # Check if URL was provided as argument
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input(f"Enter SmartFrame image URL (or press Enter for example): ").strip()
        if not url:
            print(f"\nUsing example URL: {example_url}")
            print("Note: Replace with a real URL for actual extraction\n")
            url = example_url
    
    # Create extractor instance
    extractor = SmartFrameExtractor(headless=True, timeout=30000)
    
    try:
        # Extract metadata
        print(f"\nExtracting metadata from: {url}\n")
        metadata = await extractor.extract_image_metadata(url)
        
        # Display results
        print("\n" + "=" * 60)
        print("EXTRACTED METADATA")
        print("=" * 60 + "\n")
        
        # Display key fields
        fields = [
            ('Image ID', 'imageId'),
            ('Title', 'title'),
            ('Photographer', 'photographer'),
            ('Date Taken', 'dateTaken'),
            ('Location', None),  # Custom field
            ('Image Size', 'imageSize'),
            ('File Size', 'fileSize'),
            ('Featuring', 'featuring'),
            ('Copyright', 'copyright'),
            ('Content Partner', 'contentPartner'),
            ('Tags', 'tags'),
        ]
        
        for label, key in fields:
            if key is None and label == 'Location':
                # Combine city and country
                city = metadata.get('city')
                country = metadata.get('country')
                if city or country:
                    location = f"{city}, {country}" if city and country else city or country
                    print(f"{label:20} {location}")
            elif key:
                value = metadata.get(key)
                if value:
                    if isinstance(value, list):
                        value = ', '.join(str(v) for v in value)
                    print(f"{label:20} {value}")
        
        # Display caption
        if metadata.get('caption'):
            print(f"\n{'Caption':20}")
            print("-" * 60)
            print(metadata['caption'])
        
        # Check for errors
        if metadata.get('error'):
            print(f"\n⚠️  Warning: {metadata['error']}")
        
        # Ask to save
        print("\n" + "=" * 60)
        save = input("Save to file? (y/n): ").strip().lower()
        if save == 'y':
            filename = input("Enter filename (default: metadata.json): ").strip()
            if not filename:
                filename = "metadata.json"
            
            extractor.export_to_json(metadata, filename)
            print(f"✓ Saved to {filename}")
        
        print("\n✓ Extraction complete!")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())

#!/usr/bin/env python3
"""
Example: Batch process multiple SmartFrame URLs

This script demonstrates processing multiple URLs and exporting to CSV.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from smartframe_extractor import SmartFrameExtractor


async def main():
    """Batch process multiple SmartFrame URLs."""
    
    print("SmartFrame Extractor - Batch Processing Example")
    print("=" * 60)
    
    # Example URLs - replace with actual SmartFrame URLs
    urls = [
        "https://smartframe.com/search/image/CUSTOMER_ID/IMAGE_ID_1",
        "https://smartframe.com/search/image/CUSTOMER_ID/IMAGE_ID_2",
        "https://smartframe.com/search/image/CUSTOMER_ID/IMAGE_ID_3",
    ]
    
    # Check if URLs file was provided
    if len(sys.argv) > 1:
        urls_file = sys.argv[1]
        print(f"\nReading URLs from: {urls_file}")
        with open(urls_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
    else:
        print("\nUsing example URLs (replace with real URLs)")
        print("Or run: python batch_extract.py urls.txt\n")
    
    print(f"Processing {len(urls)} URLs...\n")
    
    # Create extractor
    extractor = SmartFrameExtractor(headless=True)
    
    # Process each URL
    results = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] Processing: {url}")
        try:
            metadata = await extractor.extract_image_metadata(url)
            results.append(metadata)
            
            # Show brief info
            title = metadata.get('title', 'No title')
            photographer = metadata.get('photographer', 'Unknown')
            print(f"  ✓ {title} by {photographer}")
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            results.append({'url': url, 'error': str(e)})
    
    # Export results
    print("\n" + "=" * 60)
    print("EXPORT RESULTS")
    print("=" * 60)
    
    output_file = input("Enter output filename (default: results.csv): ").strip()
    if not output_file:
        output_file = "results.csv"
    
    format_choice = input("Format (json/csv, default: csv): ").strip().lower()
    if not format_choice:
        format_choice = "csv"
    
    if format_choice == 'csv':
        extractor.export_to_csv(results, output_file)
    else:
        extractor.export_to_json(results, output_file)
    
    print(f"\n✓ Successfully processed {len(results)} URLs")


if __name__ == '__main__':
    asyncio.run(main())

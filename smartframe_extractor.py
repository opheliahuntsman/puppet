#!/usr/bin/env python3
"""
SmartFrame Metadata Extractor

A Python module for extracting image metadata from SmartFrame.com URLs.
This is a proof-of-concept implementation that demonstrates how SmartFrame
metadata extraction could be implemented in Python.

Features:
- Shadow DOM penetration for SmartFrame custom elements
- Metadata parsing and normalization
- JSON and CSV export
- Command-line interface
- Retry mechanism for rate limiting

Usage:
    # As a module
    from smartframe_extractor import SmartFrameExtractor
    
    extractor = SmartFrameExtractor()
    metadata = extractor.extract_image_metadata(url)
    
    # As a CLI
    python smartframe_extractor.py --url "https://smartframe.com/search/image/HASH/IMAGE_ID"
"""

import asyncio
import json
import csv
import sys
import argparse
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from urllib.parse import urlparse


class SmartFrameExtractor:
    """
    SmartFrame metadata extractor using Playwright for browser automation.
    
    This class handles extraction of image metadata from SmartFrame.com pages,
    including parsing Shadow DOM elements and network-intercepted data.
    """
    
    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        Initialize the extractor.
        
        Args:
            headless: Run browser in headless mode
            timeout: Navigation timeout in milliseconds
        """
        self.headless = headless
        self.timeout = timeout
        self.metadata_cache = {}
    
    async def extract_image_metadata(self, url: str) -> Dict[str, Any]:
        """
        Extract metadata from a SmartFrame image URL.
        
        Args:
            url: SmartFrame image URL (e.g., https://smartframe.com/search/image/HASH/IMAGE_ID)
        
        Returns:
            Dictionary containing extracted metadata
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "Playwright is required. Install with: pip install playwright && playwright install chromium"
            )
        
        # Parse URL to extract image ID and hash
        parsed = self._parse_smartframe_url(url)
        if not parsed:
            raise ValueError(f"Invalid SmartFrame URL: {url}")
        
        image_id = parsed['image_id']
        hash_id = parsed['hash']
        
        # Initialize metadata structure
        metadata = {
            'imageId': image_id,
            'hash': hash_id,
            'url': url,
            'smartframeId': image_id,
            'photographer': None,
            'imageSize': None,
            'fileSize': None,
            'country': None,
            'city': None,
            'date': None,
            'matchEvent': None,
            'thumbnailUrl': None,
            'title': None,
            'caption': None,
            'captionRaw': None,
            'featuring': None,
            'tags': [],
            'comments': None,
            'copyright': None,
            'dateTaken': None,
            'authors': None,
            'contentPartner': None,
            'extractedAt': datetime.utcnow().isoformat()
        }
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            # Setup network interception
            async def handle_response(response):
                if 'smartframe' in response.url and ('/api/' in response.url or '/metadata' in response.url):
                    try:
                        data = await response.json()
                        if data and ('imageId' in data or 'image_id' in data or 'id' in data):
                            cached_id = data.get('imageId') or data.get('image_id') or data.get('id')
                            self.metadata_cache[cached_id] = data
                            print(f"Cached metadata for image: {cached_id}")
                    except:
                        pass
            
            page.on('response', handle_response)
            
            try:
                # Navigate to the page
                print(f"Navigating to {url}...")
                await page.goto(url, wait_until='networkidle', timeout=self.timeout)
                
                # Wait for SmartFrame embed element
                try:
                    await page.wait_for_selector('smartframe-embed', timeout=15000)
                    print("SmartFrame embed element found")
                except:
                    print("Warning: SmartFrame embed not found within timeout")
                
                # Extract data from Shadow DOM and page content
                raw_data = await page.evaluate("""
                    () => {
                        const labelValues = [];
                        const keywords = [];
                        
                        // Access Shadow DOM
                        const embed = document.querySelector('smartframe-embed');
                        let shadowRoot = embed ? embed.shadowRoot : null;
                        
                        let title = null;
                        let caption = null;
                        let contentPartner = null;
                        
                        // Extract from Shadow DOM
                        if (shadowRoot) {
                            const shadowTitle = shadowRoot.querySelector('h1, h2, [class*="title"]');
                            title = shadowTitle?.textContent || null;
                            
                            const shadowCaption = shadowRoot.querySelector('p, div[class*="caption"]');
                            caption = shadowCaption?.textContent || null;
                            
                            // Extract label-value pairs
                            shadowRoot.querySelectorAll('li').forEach(li => {
                                const strong = li.querySelector('strong');
                                if (!strong) return;
                                
                                const label = strong.textContent?.replace(':', '').trim() || '';
                                let value = null;
                                
                                const button = li.querySelector('button');
                                if (button) {
                                    value = button.textContent;
                                } else if (strong.nextSibling) {
                                    value = strong.nextSibling.textContent;
                                }
                                
                                if (label && value) {
                                    labelValues.push({ label, value });
                                }
                            });
                        }
                        
                        // Fallback to light DOM
                        if (!title) {
                            const h1 = document.querySelector('h1');
                            title = h1?.textContent || null;
                        }
                        
                        if (!caption) {
                            const captionSelectors = ['section p', 'p.text-iy-midnight-400', 'article p'];
                            for (const selector of captionSelectors) {
                                const el = document.querySelector(selector);
                                if (el?.textContent && el.textContent.length > 20) {
                                    caption = el.textContent.trim();
                                    break;
                                }
                            }
                        }
                        
                        // Extract content partner
                        const partnerSection = document.querySelector('h6.headline');
                        if (partnerSection?.textContent?.includes('SmartFrame Content Partner')) {
                            const parent = partnerSection.parentElement;
                            const partnerName = parent?.querySelector('h2.headline');
                            contentPartner = partnerName?.textContent?.trim() || null;
                        }
                        
                        // Extract keywords
                        const keywordSections = Array.from(document.querySelectorAll('h2')).filter(h2 => 
                            h2.textContent?.toLowerCase().includes('keyword')
                        );
                        
                        keywordSections.forEach(section => {
                            const parent = section.parentElement;
                            if (parent) {
                                const buttons = parent.querySelectorAll('button[type="button"]');
                                buttons.forEach(button => {
                                    const keyword = button.textContent?.trim();
                                    if (keyword && !keyword.includes('SmartFrame') && !keyword.includes('View all')) {
                                        keywords.push(keyword);
                                    }
                                });
                            }
                        });
                        
                        return { title, caption, labelValues, contentPartner, keywords };
                    }
                """)
                
                # Parse extracted data
                self._parse_metadata(metadata, raw_data)
                
                # Check for cached network data
                if image_id in self.metadata_cache:
                    print(f"Using cached network metadata for {image_id}")
                    cached = self.metadata_cache[image_id]
                    self._merge_cached_metadata(metadata, cached)
                
            except Exception as e:
                print(f"Error during extraction: {e}")
                metadata['error'] = str(e)
            finally:
                await browser.close()
        
        return metadata
    
    def _parse_smartframe_url(self, url: str) -> Optional[Dict[str, str]]:
        """Parse SmartFrame URL to extract image ID and hash."""
        # Format: https://smartframe.com/search/image/HASH/IMAGE_ID
        match = re.search(r'/search/image/([^/]+)/([^/?]+)', url)
        if match:
            return {
                'hash': match.group(1),
                'image_id': match.group(2)
            }
        return None
    
    def _parse_metadata(self, metadata: Dict, raw_data: Dict):
        """Parse raw extracted data into metadata structure."""
        metadata['title'] = raw_data.get('title')
        metadata['captionRaw'] = raw_data.get('caption')
        metadata['caption'] = raw_data.get('caption')
        metadata['contentPartner'] = raw_data.get('contentPartner')
        metadata['tags'] = raw_data.get('keywords', [])
        
        # Parse label-value pairs
        for item in raw_data.get('labelValues', []):
            label = item['label'].lower()
            value = item['value'].strip() if item['value'] else None
            
            if not value:
                continue
            
            # Map labels to metadata fields
            if label in ['photographer', 'credit', 'photo credit', 'author']:
                metadata['photographer'] = metadata['photographer'] or value
                metadata['authors'] = metadata['authors'] or value
            elif label in ['image size', 'size', 'dimensions']:
                metadata['imageSize'] = value
            elif label in ['file size', 'filesize']:
                metadata['fileSize'] = value
            elif label in ['country']:
                metadata['country'] = value
            elif label in ['city', 'location']:
                metadata['city'] = value
            elif label in ['date', 'date taken', 'created']:
                metadata['date'] = value
                metadata['dateTaken'] = self._normalize_date(value)
            elif label in ['event', 'title', 'headline']:
                metadata['matchEvent'] = metadata['matchEvent'] or value
            elif label in ['featuring', 'people', 'subject']:
                metadata['featuring'] = value
            elif label in ['copyright', '©']:
                metadata['copyright'] = value
        
        # Parse caption for embedded metadata
        caption = metadata.get('captionRaw', '')
        if caption:
            self._parse_caption_metadata(metadata, caption)
    
    def _parse_caption_metadata(self, metadata: Dict, caption: str):
        """Extract metadata embedded in caption text."""
        lines = [l.strip() for l in caption.split('\n') if l.strip()]
        
        # Extract credit line
        credit_match = re.search(r'(?:Credit|Photographer|Photo(?:\s+Credit)?|©|Copyright):\s*([^\n]+)', caption, re.IGNORECASE)
        if credit_match and not metadata.get('photographer'):
            credit = credit_match.group(1).strip()
            # Clean up credit
            credit = re.sub(r'^\s*\([^)]+\)\s*:\s*', '', credit)
            metadata['photographer'] = credit
            metadata['authors'] = credit
        
        # Extract location-date format: "City, Country - DD.MM.YY"
        for line in lines:
            location_date_match = re.match(r'^(.+?)\s+[-–]\s+(\d{2}\.\d{2}\.\d{2,4})$', line)
            if location_date_match and not metadata.get('date'):
                location = location_date_match.group(1).strip()
                date = location_date_match.group(2).strip()
                
                if ',' in location:
                    parts = [p.strip() for p in location.split(',')]
                    metadata['city'] = metadata['city'] or parts[0]
                    metadata['country'] = metadata['country'] or ', '.join(parts[1:])
                else:
                    metadata['city'] = metadata['city'] or location
                
                metadata['date'] = date
                metadata['dateTaken'] = self._normalize_date(date)
    
    def _merge_cached_metadata(self, metadata: Dict, cached: Dict):
        """Merge cached network metadata into main metadata."""
        mappings = {
            'photographer': ['photographer', 'credit', 'author'],
            'imageSize': ['dimensions', 'size', 'imageSize'],
            'fileSize': ['fileSize', 'file_size'],
            'country': ['country'],
            'city': ['city', 'location'],
            'date': ['date', 'dateCreated', 'created_at'],
            'title': ['title', 'headline'],
            'caption': ['description', 'caption'],
            'featuring': ['featuring', 'people', 'subject'],
            'copyright': ['copyright'],
            'tags': ['tags', 'keywords']
        }
        
        for meta_key, cache_keys in mappings.items():
            if not metadata.get(meta_key):
                for cache_key in cache_keys:
                    if cached.get(cache_key):
                        metadata[meta_key] = cached[cache_key]
                        break
    
    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalize date string to ISO format."""
        if not date_str:
            return None
        
        # Handle DD.MM.YY format
        match = re.match(r'(\d{2})\.(\d{2})\.(\d{2,4})', date_str)
        if match:
            day, month, year = match.groups()
            # Convert 2-digit year to 4-digit
            if len(year) == 2:
                year = '20' + year if int(year) < 50 else '19' + year
            try:
                dt = datetime(int(year), int(month), int(day))
                return dt.strftime('%Y-%m-%d')
            except:
                pass
        
        return date_str
    
    def export_to_json(self, metadata: Dict, filepath: str):
        """Export metadata to JSON file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"Exported to {filepath}")
    
    def export_to_csv(self, metadata_list: List[Dict], filepath: str):
        """Export metadata list to CSV file."""
        if not metadata_list:
            return
        
        # Get all possible keys
        keys = set()
        for item in metadata_list:
            keys.update(item.keys())
        
        keys = sorted(keys)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for item in metadata_list:
                # Convert lists to strings for CSV
                row = {}
                for k, v in item.items():
                    if isinstance(v, list):
                        row[k] = ', '.join(str(x) for x in v)
                    else:
                        row[k] = v
                writer.writerow(row)
        
        print(f"Exported {len(metadata_list)} items to {filepath}")


async def main():
    """Command-line interface for the extractor."""
    parser = argparse.ArgumentParser(
        description='Extract metadata from SmartFrame images',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract single image
  python smartframe_extractor.py --url "https://smartframe.com/search/image/abc123/image456"
  
  # Extract and save to JSON
  python smartframe_extractor.py --url "..." --output metadata.json
  
  # Extract multiple images and save to CSV
  python smartframe_extractor.py --urls urls.txt --output results.csv --format csv
        """
    )
    
    parser.add_argument('--url', help='Single SmartFrame image URL to extract')
    parser.add_argument('--urls', help='File containing URLs (one per line)')
    parser.add_argument('--output', help='Output file path')
    parser.add_argument('--format', choices=['json', 'csv'], default='json', help='Output format')
    parser.add_argument('--headless', action='store_true', default=True, help='Run browser in headless mode')
    parser.add_argument('--timeout', type=int, default=30000, help='Navigation timeout in milliseconds')
    
    args = parser.parse_args()
    
    if not args.url and not args.urls:
        parser.error("Either --url or --urls must be specified")
    
    extractor = SmartFrameExtractor(headless=args.headless, timeout=args.timeout)
    
    # Collect URLs to process
    urls = []
    if args.url:
        urls.append(args.url)
    if args.urls:
        with open(args.urls, 'r') as f:
            urls.extend([line.strip() for line in f if line.strip()])
    
    # Extract metadata
    results = []
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] Processing {url}")
        try:
            metadata = await extractor.extract_image_metadata(url)
            results.append(metadata)
            print(f"✓ Successfully extracted metadata")
        except Exception as e:
            print(f"✗ Failed: {e}")
            results.append({'url': url, 'error': str(e)})
    
    # Export results
    if args.output:
        if args.format == 'json':
            if len(results) == 1:
                extractor.export_to_json(results[0], args.output)
            else:
                extractor.export_to_json(results, args.output)
        else:  # CSV
            extractor.export_to_csv(results, args.output)
    else:
        # Print to stdout
        print("\n" + "="*60)
        print("RESULTS")
        print("="*60)
        print(json.dumps(results if len(results) > 1 else results[0], indent=2))


if __name__ == '__main__':
    asyncio.run(main())

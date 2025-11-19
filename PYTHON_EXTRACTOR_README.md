# SmartFrame Extractor - Python Implementation

## Overview

`smartframe_extractor.py` is a proof-of-concept Python module for extracting image metadata from SmartFrame.com URLs. This provides an alternative implementation to the existing TypeScript scraper and demonstrates the feasibility of Python-based extraction.

## Features

✅ **Shadow DOM Access** - Penetrates SmartFrame's custom elements  
✅ **Network Interception** - Caches API responses for metadata  
✅ **Metadata Parsing** - Extracts EXIF, IPTC, and custom fields  
✅ **Multiple Formats** - Export to JSON or CSV  
✅ **CLI Interface** - Easy command-line usage  
✅ **Programmatic API** - Use as a Python module  

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install chromium
```

## Usage

### Command Line Interface

#### Extract Single Image

```bash
python smartframe_extractor.py --url "https://smartframe.com/search/image/HASH/IMAGE_ID"
```

#### Extract and Save to JSON

```bash
python smartframe_extractor.py \
  --url "https://smartframe.com/search/image/abc123/image456" \
  --output metadata.json
```

#### Extract Multiple Images from File

Create a text file with URLs (one per line):

```
https://smartframe.com/search/image/hash1/id1
https://smartframe.com/search/image/hash2/id2
https://smartframe.com/search/image/hash3/id3
```

Then extract:

```bash
python smartframe_extractor.py \
  --urls urls.txt \
  --output results.csv \
  --format csv
```

#### Show Browser Window (Non-headless)

```bash
python smartframe_extractor.py \
  --url "..." \
  --headless false
```

### Programmatic Usage

```python
import asyncio
from smartframe_extractor import SmartFrameExtractor

async def extract_example():
    extractor = SmartFrameExtractor(headless=True)
    
    # Extract single image
    metadata = await extractor.extract_image_metadata(
        "https://smartframe.com/search/image/abc123/image456"
    )
    
    print(f"Title: {metadata['title']}")
    print(f"Photographer: {metadata['photographer']}")
    print(f"Tags: {', '.join(metadata['tags'])}")
    
    # Export to JSON
    extractor.export_to_json(metadata, 'output.json')

# Run
asyncio.run(extract_example())
```

## Extracted Metadata Fields

The extractor retrieves the following metadata:

| Field | Description | Example |
|-------|-------------|---------|
| `imageId` | SmartFrame image identifier | `"abc123def456"` |
| `hash` | SmartFrame customer/collection hash | `"xyz789"` |
| `url` | Full SmartFrame URL | `"https://smartframe.com/..."` |
| `photographer` | Image photographer/credit | `"John Smith/Getty Images"` |
| `imageSize` | Image dimensions | `"3000x2000"` |
| `fileSize` | File size | `"2.5 MB"` |
| `country` | Country where taken | `"United Kingdom"` |
| `city` | City/location where taken | `"London"` |
| `date` | Original date string | `"15.11.07"` |
| `dateTaken` | Normalized date (ISO) | `"2007-11-15"` |
| `title` | Image title/headline | `"Royal Wedding Ceremony"` |
| `caption` | Generated caption | Combined metadata |
| `captionRaw` | Original caption text | Raw caption from page |
| `featuring` | People featured | `"Queen Elizabeth II"` |
| `tags` | Keywords/tags | `["royal", "ceremony", "UK"]` |
| `copyright` | Copyright notice | `"© 2007 John Smith"` |
| `contentPartner` | SmartFrame content partner | `"WENN"` |
| `matchEvent` | Associated event | `"Royal Wedding 2007"` |

## Integration with TypeScript Scraper

### Option 1: Post-Processing Pipeline

Use Python extractor to enhance data from the TypeScript scraper:

```bash
# 1. Run TypeScript scraper and export
npm run dev
# (Use web UI to scrape and export to CSV)

# 2. Post-process with Python
python scripts/enhance_metadata.py \
  --input exported-data.csv \
  --output enhanced-data.csv
```

### Option 2: Hybrid Processing

Use Python for specific tasks:

```javascript
// In TypeScript scraper
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

async function enhanceWithPython(imageUrl: string) {
  const { stdout } = await execAsync(
    `python smartframe_extractor.py --url "${imageUrl}"`
  );
  return JSON.parse(stdout);
}
```

### Option 3: Standalone Mode

Use Python extractor independently:

```bash
# Extract images directly with Python
python smartframe_extractor.py \
  --urls smartframe-urls.txt \
  --output python-results.csv \
  --format csv
```

## Performance Comparison

| Metric | TypeScript (Puppeteer) | Python (Playwright) |
|--------|------------------------|---------------------|
| Single image extraction | ~3-5s | ~3-5s |
| Parallel processing | ✅ Supported (5-10 tabs) | ✅ Supported (configurable) |
| Memory usage | ~200-300 MB | ~200-300 MB |
| Startup time | ~2s | ~2s |
| Shadow DOM access | ✅ Yes | ✅ Yes |
| Network interception | ✅ Yes | ✅ Yes |

## Limitations

⚠️ **Current Limitations:**
- No retry mechanism (TypeScript version has advanced retry)
- No pagination handling (extract single images only)
- No job queue management
- No database integration
- No parallel batch processing in CLI (use programmatically)

## Future Enhancements

Potential additions for full feature parity:

1. **Retry Logic** - Add exponential backoff for rate limiting
2. **Parallel Processing** - Batch processing with configurable concurrency
3. **Pagination** - Handle SmartFrame search pages
4. **Database Integration** - Direct database storage
5. **REST API** - Flask/FastAPI wrapper for HTTP endpoints
6. **Image Analysis** - OCR, AI captioning, quality detection
7. **Caching** - Redis/file-based caching for repeated URLs

## Troubleshooting

### Playwright Not Found

```bash
# Install Playwright browsers
playwright install chromium
```

### Timeout Errors

Increase timeout:

```bash
python smartframe_extractor.py --url "..." --timeout 60000
```

### No Metadata Extracted

1. Check if URL is valid SmartFrame image URL
2. Run with `--headless false` to see browser
3. SmartFrame may be rate-limiting (wait and retry)

## Testing

Test with a sample SmartFrame URL:

```bash
# Replace with actual SmartFrame URL
python smartframe_extractor.py \
  --url "https://smartframe.com/search/image/CUSTOMER_ID/IMAGE_ID" \
  --output test.json
```

Expected output:
```
Navigating to https://smartframe.com/search/image/...
SmartFrame embed element found
✓ Successfully extracted metadata
Exported to test.json
```

## Contributing

This is a proof-of-concept implementation. Contributions welcome:

1. Add retry mechanism
2. Implement parallel processing
3. Add comprehensive tests
4. Improve error handling
5. Add more export formats

## License

MIT License - Same as parent project

## See Also

- [SMARTFRAME_EXTRACTOR_REVIEW.md](./SMARTFRAME_EXTRACTOR_REVIEW.md) - Detailed analysis and recommendations
- [server/scraper.ts](./server/scraper.ts) - TypeScript implementation
- [README.md](./README.md) - Main project README

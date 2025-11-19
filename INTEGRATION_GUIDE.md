# Integration Guide: Python Extractor with TypeScript Scraper

## Overview

This guide explains how to integrate the Python SmartFrame extractor (`smartframe_extractor.py`) with the existing TypeScript-based scraper.

## Architecture Options

### Option 1: Standalone Operation (Recommended for Testing)

Use Python extractor independently without affecting the TypeScript implementation.

**When to use:**
- Testing Python implementation
- Processing small batches of images
- One-off metadata extraction tasks
- Validating metadata quality

**Setup:**
```bash
# Install Python dependencies
pip install -r requirements.txt
playwright install chromium

# Run extraction
python smartframe_extractor.py --url "https://smartframe.com/search/image/..."
```

### Option 2: Post-Processing Pipeline

Use Python to enhance or validate data exported from the TypeScript scraper.

**Workflow:**
1. Run TypeScript scraper through web UI
2. Export data to CSV/JSON
3. Process with Python for enhancement
4. Re-import or use enhanced data

**Example Script:**

```python
# scripts/enhance_exported_data.py
import pandas as pd
import asyncio
from smartframe_extractor import SmartFrameExtractor

async def enhance_csv(input_file, output_file):
    """Re-extract metadata for validation or enhancement."""
    df = pd.read_csv(input_file)
    extractor = SmartFrameExtractor()
    
    enhanced_rows = []
    for _, row in df.iterrows():
        url = row['url']
        print(f"Re-extracting: {url}")
        
        try:
            metadata = await extractor.extract_image_metadata(url)
            # Merge with original data
            enhanced = {**row.to_dict(), **metadata}
            enhanced_rows.append(enhanced)
        except Exception as e:
            print(f"Error: {e}")
            enhanced_rows.append(row.to_dict())
    
    pd.DataFrame(enhanced_rows).to_csv(output_file, index=False)

# Usage: python scripts/enhance_exported_data.py
```

### Option 3: Hybrid Processing via Child Process

Call Python extractor from TypeScript code for specific tasks.

**Use Cases:**
- Image analysis with Python libraries (Pillow, OpenCV)
- Advanced metadata validation
- ML-based caption generation
- OCR for text in images

**TypeScript Integration:**

```typescript
// server/utils/python-extractor.ts
import { exec } from 'child_process';
import { promisify } from 'util';
import { writeFileSync, unlinkSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

const execAsync = promisify(exec);

export async function extractWithPython(url: string): Promise<any> {
  const outputFile = join(tmpdir(), `extract-${Date.now()}.json`);
  
  try {
    const cmd = `python3 smartframe_extractor.py --url "${url}" --output ${outputFile}`;
    await execAsync(cmd, { timeout: 60000 });
    
    const result = JSON.parse(readFileSync(outputFile, 'utf-8'));
    unlinkSync(outputFile);
    
    return result;
  } catch (error) {
    if (existsSync(outputFile)) unlinkSync(outputFile);
    throw error;
  }
}

// Usage in scraper
import { extractWithPython } from './utils/python-extractor';

// Fallback to Python if TypeScript extraction fails
if (!metadata.photographer && !metadata.title) {
  console.log('Trying Python extractor as fallback...');
  const pythonResult = await extractWithPython(url);
  metadata = { ...metadata, ...pythonResult };
}
```

### Option 4: REST API Wrapper

Create a Flask/FastAPI service for the Python extractor.

**Benefits:**
- Language-agnostic integration
- Scalable across multiple servers
- Can be containerized independently
- Easy to version and deploy separately

**Basic Flask Implementation:**

```python
# api/extractor_service.py
from flask import Flask, request, jsonify
import asyncio
from smartframe_extractor import SmartFrameExtractor

app = Flask(__name__)
extractor = SmartFrameExtractor()

@app.route('/extract', methods=['POST'])
def extract():
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'URL required'}), 400
    
    try:
        # Run async extraction
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        metadata = loop.run_until_complete(
            extractor.extract_image_metadata(url)
        )
        loop.close()
        
        return jsonify(metadata)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(port=5001)
```

**TypeScript Client:**

```typescript
// Call Python API from TypeScript
async function extractViaPythonAPI(url: string): Promise<any> {
  const response = await fetch('http://localhost:5001/extract', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url })
  });
  
  if (!response.ok) {
    throw new Error(`Python API error: ${response.statusText}`);
  }
  
  return response.json();
}
```

## Deployment Considerations

### Development Environment

```bash
# Terminal 1: Run TypeScript scraper
npm run dev

# Terminal 2: Run Python API (if using Option 4)
cd api
python extractor_service.py
```

### Production Environment

**Option A: Containerized Services**

```yaml
# docker-compose.yml
version: '3.8'
services:
  typescript-scraper:
    build: .
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
  
  python-extractor:
    build: ./python
    ports:
      - "5001:5001"
    depends_on:
      - typescript-scraper
```

**Option B: Shared Server**

```bash
# Install both Node and Python
apt-get install nodejs python3 python3-pip

# Install dependencies
npm install
pip install -r requirements.txt

# Run with process manager
pm2 start npm --name "scraper" -- run start
pm2 start "python api/extractor_service.py" --name "python-api"
```

## Performance Comparison

| Metric | TypeScript | Python | Recommended |
|--------|-----------|---------|-------------|
| Single image extraction | 3-5s | 3-5s | Either |
| Batch processing (100 images) | 2-3 min | 3-4 min | TypeScript |
| Parallel processing | ✅ 5-10 tabs | ✅ Configurable | TypeScript |
| Memory usage | ~300 MB | ~300 MB | Similar |
| Startup overhead | ~2s | ~2s | Similar |
| Code maintainability | Medium | High | Python |
| Integration complexity | None | Medium | TypeScript |

## Migration Strategy

### Phase 1: Validation (Week 1)
1. Run both extractors on same URLs
2. Compare results for accuracy
3. Identify discrepancies
4. Fix bugs in either implementation

### Phase 2: Selective Use (Week 2-3)
1. Use Python for specific tasks:
   - Image analysis
   - Advanced validation
   - Data enrichment
2. Keep TypeScript for core scraping

### Phase 3: Decision (Week 4)
Based on results:
- **Option A:** Keep both (hybrid approach)
- **Option B:** Migrate fully to Python
- **Option C:** Keep TypeScript, use Python for utilities

## Monitoring and Logging

### Unified Logging

```typescript
// Shared logger that works with both
import { createLogger } from './logger';

const logger = createLogger('scraper');

// TypeScript
logger.info('TypeScript: Scraped image', { imageId, source: 'typescript' });

// Python (via API)
logger.info('Python: Extracted metadata', { imageId, source: 'python' });
```

### Metrics Collection

```typescript
// Track performance of both extractors
interface ExtractionMetrics {
  source: 'typescript' | 'python';
  duration: number;
  success: boolean;
  imageId: string;
}

const metrics: ExtractionMetrics[] = [];

// Compare performance
function compareExtractors(metrics: ExtractionMetrics[]) {
  const typescript = metrics.filter(m => m.source === 'typescript');
  const python = metrics.filter(m => m.source === 'python');
  
  return {
    typescript: {
      avgDuration: avg(typescript.map(m => m.duration)),
      successRate: typescript.filter(m => m.success).length / typescript.length
    },
    python: {
      avgDuration: avg(python.map(m => m.duration)),
      successRate: python.filter(m => m.success).length / python.length
    }
  };
}
```

## Troubleshooting

### Python Not Available

```typescript
// Gracefully fallback if Python isn't installed
async function extractWithPythonSafe(url: string) {
  try {
    return await extractWithPython(url);
  } catch (error) {
    console.warn('Python extractor not available, using TypeScript fallback');
    return extractWithTypeScript(url);
  }
}
```

### Version Conflicts

```bash
# Use virtual environment for Python
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### Playwright Browser Issues

```bash
# Ensure browsers are installed
playwright install chromium

# Check installation
playwright show-traces
```

## Best Practices

1. **Start Small:** Begin with Option 1 (standalone) for testing
2. **Validate:** Compare results with TypeScript scraper
3. **Document:** Keep track of what each implementation does better
4. **Monitor:** Track performance and error rates
5. **Iterate:** Gradually increase Python usage based on results
6. **Backup:** Always keep TypeScript scraper operational

## Conclusion

The Python extractor provides a flexible alternative to the TypeScript implementation. Start with standalone testing, then gradually integrate based on your specific needs and the performance characteristics you observe.

For questions or issues, refer to:
- [PYTHON_EXTRACTOR_README.md](./PYTHON_EXTRACTOR_README.md) - Python usage guide
- [SMARTFRAME_EXTRACTOR_REVIEW.md](./SMARTFRAME_EXTRACTOR_REVIEW.md) - Implementation analysis
- [server/scraper.ts](./server/scraper.ts) - TypeScript implementation

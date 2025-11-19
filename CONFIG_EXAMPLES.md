# SmartFrame Canvas Extraction - Configuration Examples

This document provides ready-to-use configuration examples for different use cases.

## Example 1: Full Resolution Canvas Extraction (9999x9999)

**Use case:** Extract highest quality images for archival or professional use

```json
{
  "vpn": {
    "enabled": false,
    "command": "manual",
    "connectionVerifyUrl": "https://www.google.com",
    "connectionVerifyTimeout": 5000,
    "maxRetries": 10,
    "retryDelay": 2000,
    "changeAfterFailures": 5
  },
  "waitTimes": {
    "scrollDelay": 1000,
    "minVariance": 2000,
    "maxVariance": 5000
  },
  "scraping": {
    "concurrency": 1,
    "maxRetryRounds": 2,
    "retryDelay": 5000,
    "detectEmptyResults": true
  },
  "metadata": {
    "metadataTimeout": 15000,
    "cookieBannerSelector": ".cky-btn.cky-btn-accept"
  },
  "navigation": {
    "timeout": 60000,
    "waitUntil": "domcontentloaded",
    "maxConcurrentJobs": 1
  },
  "smartframe": {
    "extractFullImages": true,
    "viewportMode": "full",
    "headless": false,
    "renderTimeout": 8000,
    "viewportSizes": {
      "full": {
        "width": 9999,
        "height": 9999
      },
      "thumbnail": {
        "width": 600,
        "height": 600
      }
    }
  }
}
```

**Notes:**
- `concurrency: 1` - Reduce to 1 for full resolution to avoid memory issues
- `maxConcurrentJobs: 1` - Process one job at a time
- `renderTimeout: 8000` - Increased timeout for large canvas rendering
- `headless: false` - **REQUIRED** for canvas rendering

## Example 2: Thumbnail Canvas Extraction (600x600)

**Use case:** Extract preview images for faster processing

```json
{
  "vpn": {
    "enabled": false,
    "command": "manual",
    "connectionVerifyUrl": "https://www.google.com",
    "connectionVerifyTimeout": 5000,
    "maxRetries": 10,
    "retryDelay": 2000,
    "changeAfterFailures": 5
  },
  "waitTimes": {
    "scrollDelay": 1000,
    "minVariance": 2000,
    "maxVariance": 5000
  },
  "scraping": {
    "concurrency": 2,
    "maxRetryRounds": 2,
    "retryDelay": 5000,
    "detectEmptyResults": true
  },
  "metadata": {
    "metadataTimeout": 15000,
    "cookieBannerSelector": ".cky-btn.cky-btn-accept"
  },
  "navigation": {
    "timeout": 60000,
    "waitUntil": "domcontentloaded",
    "maxConcurrentJobs": 2
  },
  "smartframe": {
    "extractFullImages": true,
    "viewportMode": "thumbnail",
    "headless": false,
    "renderTimeout": 5000,
    "viewportSizes": {
      "full": {
        "width": 9999,
        "height": 9999
      },
      "thumbnail": {
        "width": 600,
        "height": 600
      }
    }
  }
}
```

**Notes:**
- `concurrency: 2` - Can increase for thumbnails (smaller file size)
- `maxConcurrentJobs: 2` - Process multiple jobs in parallel
- `renderTimeout: 5000` - Standard timeout for smaller canvas
- `headless: false` - **REQUIRED** for canvas rendering

## Example 3: Metadata Only (No Canvas Extraction)

**Use case:** Extract metadata without canvas images (default behavior)

```json
{
  "vpn": {
    "enabled": false,
    "command": "manual",
    "connectionVerifyUrl": "https://www.google.com",
    "connectionVerifyTimeout": 5000,
    "maxRetries": 10,
    "retryDelay": 2000,
    "changeAfterFailures": 5
  },
  "waitTimes": {
    "scrollDelay": 1000,
    "minVariance": 2000,
    "maxVariance": 5000
  },
  "scraping": {
    "concurrency": 5,
    "maxRetryRounds": 2,
    "retryDelay": 5000,
    "detectEmptyResults": true
  },
  "metadata": {
    "metadataTimeout": 15000,
    "cookieBannerSelector": ".cky-btn.cky-btn-accept"
  },
  "navigation": {
    "timeout": 60000,
    "waitUntil": "domcontentloaded",
    "maxConcurrentJobs": 3
  },
  "smartframe": {
    "extractFullImages": false,
    "viewportMode": "thumbnail",
    "headless": false,
    "renderTimeout": 5000,
    "viewportSizes": {
      "full": {
        "width": 9999,
        "height": 9999
      },
      "thumbnail": {
        "width": 600,
        "height": 600
      }
    }
  }
}
```

**Notes:**
- `extractFullImages: false` - Canvas extraction disabled
- `concurrency: 5` - Higher concurrency for faster metadata extraction
- `maxConcurrentJobs: 3` - Process multiple jobs in parallel
- Browser can run in headless mode when canvas extraction is disabled

## Example 4: Custom Viewport Sizes

**Use case:** Custom viewport dimensions for specific requirements

```json
{
  "vpn": {
    "enabled": false,
    "command": "manual",
    "connectionVerifyUrl": "https://www.google.com",
    "connectionVerifyTimeout": 5000,
    "maxRetries": 10,
    "retryDelay": 2000,
    "changeAfterFailures": 5
  },
  "waitTimes": {
    "scrollDelay": 1000,
    "minVariance": 2000,
    "maxVariance": 5000
  },
  "scraping": {
    "concurrency": 2,
    "maxRetryRounds": 2,
    "retryDelay": 5000,
    "detectEmptyResults": true
  },
  "metadata": {
    "metadataTimeout": 15000,
    "cookieBannerSelector": ".cky-btn.cky-btn-accept"
  },
  "navigation": {
    "timeout": 60000,
    "waitUntil": "domcontentloaded",
    "maxConcurrentJobs": 2
  },
  "smartframe": {
    "extractFullImages": true,
    "viewportMode": "full",
    "headless": false,
    "renderTimeout": 6000,
    "viewportSizes": {
      "full": {
        "width": 5000,
        "height": 5000
      },
      "thumbnail": {
        "width": 800,
        "height": 800
      }
    }
  }
}
```

**Notes:**
- Custom `viewportSizes` for specific dimensions
- `full`: 5000x5000 - Medium-high resolution
- `thumbnail`: 800x800 - Larger thumbnail size
- Adjust `renderTimeout` based on viewport size

## Performance Comparison

| Configuration | Speed | Image Quality | Memory Usage | Recommended For |
|--------------|-------|---------------|--------------|-----------------|
| Full (9999x9999) | Slow | Highest | High | Archival, professional use |
| Thumbnail (600x600) | Fast | Medium | Low | Preview, faster scraping |
| Metadata Only | Fastest | N/A | Lowest | Metadata collection only |
| Custom (5000x5000) | Medium | High | Medium | Balanced quality/speed |

## Testing Your Configuration

After updating `scraper.config.json`, validate your setup:

```bash
node validate-smartframe-config.mjs
```

The validator will check:
- ✓ Configuration file is valid JSON
- ✓ SmartFrame section exists and is properly configured
- ✓ Extension files are present
- ✓ Settings are compatible (headless mode warning)

## Switching Between Modes

To switch from metadata-only to canvas extraction:

1. Set `extractFullImages: true`
2. Choose `viewportMode`: `"full"` or `"thumbnail"`
3. Ensure `headless: false`
4. Restart the scraper

To switch back to metadata-only:

1. Set `extractFullImages: false`
2. Restart the scraper

## Common Issues and Solutions

### Issue: Canvas images not extracted

**Solution:** Ensure `headless: false` in configuration

### Issue: Low quality images

**Solution:** Use `viewportMode: "full"` for maximum quality

### Issue: Slow performance

**Solution:** 
- Use `viewportMode: "thumbnail"` for faster extraction
- Reduce `concurrency` to 1 for full resolution
- Increase `renderTimeout` if images are incomplete

### Issue: Out of memory errors

**Solution:**
- Reduce `concurrency` to 1
- Set `maxConcurrentJobs` to 1
- Use `viewportMode: "thumbnail"` instead of `"full"`

## See Also

- [SMARTFRAME_CANVAS_EXTRACTION.md](SMARTFRAME_CANVAS_EXTRACTION.md) - Complete documentation
- [README.md](README.md) - Main documentation
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Technical details

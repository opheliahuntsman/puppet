# SmartFrame Canvas Image Extraction

## Overview

The scraper now supports extracting full-resolution canvas images from SmartFrame embeds. Users can select canvas extraction mode directly from the web interface without editing any code.

## Quick Start

1. **Open the scraper web interface**
2. **Click "Show Advanced Options"**
3. **Select canvas extraction mode:**
   - **No Canvas Images** - Metadata only (default, fastest)
   - **Thumbnail (600x600)** - Extract thumbnail-sized canvas images
   - **High Resolution (9999x9999)** - Extract full-resolution canvas images
4. **Start scraping** - Canvas images will be automatically extracted

No configuration files or code editing required!

## Features

- 🎨 **Full Canvas Extraction**: Extract full-resolution canvas images from SmartFrame embeds
- 📐 **Three Modes**: Choose between no images, thumbnail (600x600), or full resolution (9999x9999)
- 🖱️ **UI Control**: Select mode from dropdown - no code editing needed
- 🔧 **Per-Job Configuration**: Each scrape job can have different settings
- 💾 **Automatic Storage**: Extracted images are saved alongside metadata
- 🖼️ **PNG Output**: Canvas images are saved as high-quality PNG files

## Image Filenames

Canvas images are saved with the SmartFrame imageId as the filename:

**Format:** `{imageId}_canvas_{mode}.png`

**Examples:**
- `abc123_canvas_full.png` - Full resolution image (9999x9999)
- `abc123_canvas_thumbnail.png` - Thumbnail image (600x600)

The imageId matches the SmartFrame image identifier, making it easy to correlate canvas images with metadata.

## Configuration

### Web Interface (Recommended)

The easiest way to configure canvas extraction is through the web interface:

1. Open the scraper web application
2. Click **"Show Advanced Options"**
3. Find the **"Canvas Image Extraction"** dropdown
4. Select your preferred mode:
   - **No Canvas Images** - Metadata only (fastest)
   - **Thumbnail (600x600)** - Extract preview images
   - **High Resolution (9999x9999)** - Extract full quality images

### Configuration File (Optional)

For advanced users, canvas extraction can also be configured via `scraper.config.json`:

```json
{
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

**Note:** The web interface settings override the config file for individual scrape jobs.

## Usage

### Using the Web Interface

1. **Access the scraper** - Open the web application in your browser
2. **Enter SmartFrame URLs** - Add one or more SmartFrame search URLs
3. **Show Advanced Options** - Click the "Show Advanced Options" button
4. **Select Canvas Mode:**
   - **No Canvas Images** - Fastest, metadata only
   - **Thumbnail (600x600)** - Good balance of quality and speed
   - **High Resolution (9999x9999)** - Highest quality, slower
5. **Start Scraping** - Click "Start Scraping"
6. **View Results** - Canvas images are saved to `downloaded_images/` directory

### Using the Configuration File

To enable canvas extraction globally for all scrape jobs, update your `scraper.config.json`:

**For Full Resolution:**

```json
{
  "smartframe": {
    "extractFullImages": true,
    "viewportMode": "full",
    "headless": false
  }
}
```

### Enable Thumbnail Extraction

To extract thumbnail-sized images (600x600):

```json
{
  "smartframe": {
    "extractFullImages": true,
    "viewportMode": "thumbnail",
    "headless": false
  }
}
```

### Run the Scraper

**Via Web Interface (Recommended):**
The scraper will automatically:
1. Initialize the Chrome extension when a job requires canvas extraction
2. Configure the viewport based on your selected mode
3. Extract canvas images during the scraping process
4. Save images to the `downloaded_images` directory
5. Clean up the extension on shutdown

**Via Command Line:**
If running the scraper programmatically, canvas extraction settings are passed through the API automatically.

## Output

Canvas images are saved with the following naming convention:

```
{imageId}_canvas_{mode}.png
```

**Examples:**
- `abc123_canvas_full.png` - Full resolution image (imageId: abc123)
- `xyz789_canvas_thumbnail.png` - Thumbnail image (imageId: xyz789)

The imageId is the SmartFrame image identifier, making it easy to match canvas images with their metadata.

The canvas image path is also stored in the scraped image metadata as `canvasImagePath`.

## How It Works

### 1. Chrome Extension Setup

When canvas extraction is enabled, the scraper:
- Creates a temporary directory for the Chrome extension
- Writes the extension files (manifest.json, background.js, content_script.js)
- Launches Puppeteer with the extension loaded

### 2. JavaScript Injection

For each SmartFrame embed, the scraper:
- Injects JavaScript to intercept shadow DOM creation
- Captures references to the shadow root and canvas element
- Sets the viewport size to match the configured mode
- Dispatches resize events to trigger canvas re-rendering

### 3. Canvas Extraction

The Chrome extension:
- Monitors for canvas extraction requests via window.postMessage
- Locates the canvas element in the shadow DOM
- Uses the original `toDataURL` method to extract image data
- Returns the data URL to the page

### 4. Image Storage

The scraper:
- Receives the data URL from the extension
- Decodes the base64 PNG data
- Saves the image to the `downloaded_images` directory
- Stores the file path in the scraped image metadata

## Important Notes

### Browser Visibility Requirement

⚠️ **The browser MUST run in non-headless mode for canvas images to render properly.**

SmartFrame embeds only render their canvas when visible in the viewport. Set `headless: false` in the configuration.

### Performance Considerations

- Full resolution (9999x9999) extraction is slower due to rendering time
- Each canvas extraction adds 3-5 seconds per image
- Consider using thumbnail mode for faster scraping
- Reduce concurrency when using full resolution mode

### Memory Usage

Large canvas extraction (9999x9999) requires significant memory:
- Each full-resolution PNG can be 5-20 MB
- Consider the `downloaded_images` directory size
- Monitor system memory usage during bulk scraping

## Troubleshooting

### Canvas Extraction Fails

**Problem**: Canvas images are not extracted

**Solutions**:
1. Ensure `headless: false` in configuration
2. Check that the browser window is visible
3. Increase `renderTimeout` for slow-loading pages
4. Check browser console logs for errors

### Extension Errors

**Problem**: Chrome extension fails to load

**Solutions**:
1. Check that Puppeteer is properly installed
2. Verify write permissions to temp directory
3. Check for Chrome/Chromium compatibility
4. Review extension manager logs

### Image Quality Issues

**Problem**: Extracted images are low quality or incomplete

**Solutions**:
1. Use `viewportMode: "full"` for maximum quality
2. Increase `renderTimeout` to allow full rendering
3. Check network connection for slow-loading images
4. Verify SmartFrame embed is rendering correctly

## Technical Details

### Extension Architecture

The canvas extractor uses a Manifest V3 Chrome extension with three components:

1. **manifest.json**: Defines extension permissions and components
2. **background.js**: Service worker that executes privileged scripts
3. **content_script.js**: Monitors page messages and communicates with background

### Injected JavaScript

The injected JavaScript:
- Intercepts `Element.prototype.attachShadow` to capture shadow roots
- Stores references to SmartFrame embed elements
- Applies viewport dimensions via CSS
- Dispatches window resize events
- Sends extraction requests to the extension

### Security

The extension:
- Only runs on pages explicitly navigated to by the scraper
- Uses message passing for secure communication
- Validates all message origins and sources
- Cleans up temporary files after execution
- Does not persist any data

## Migration from Python Script

If you're migrating from `smartframe_extractor.py`:

1. **Configuration**: The Python script's command-line arguments map to `scraper.config.json` settings
2. **Viewport**: The Python `--viewport` flag is now `viewportMode` in config
3. **Output**: Images are saved to `downloaded_images/` instead of script directory
4. **Integration**: No need to run separately - canvas extraction happens during scraping

## Future Enhancements

Potential improvements for future releases:

- [ ] JPG conversion (requires adding sharp or similar library)
- [ ] Custom viewport dimensions (not just full/thumbnail presets)
- [ ] Batch canvas extraction optimization
- [ ] Metadata embedding in extracted images
- [ ] Configurable output directory
- [ ] Progress tracking for canvas extraction

## See Also

- [README.md](README.md) - Main documentation
- [scraper.config.json](scraper.config.json) - Configuration file
- [smartframe_extractor.py](smartframe_extractor.py) - Original Python implementation

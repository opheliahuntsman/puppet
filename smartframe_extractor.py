# --- Standard Library Imports ---
import os
import shutil
import json
import re
import subprocess
import sys
import time
import logging
import logging.handlers
import multiprocessing
import tempfile
import threading
import base64
import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Any
from urllib.parse import urlparse, urljoin

# --- Third-Party Imports ---
missing_dependencies: List[str] = []

try:
    from playwright.async_api import async_playwright
except ImportError:
    missing_dependencies.append(
        "playwright (pip install playwright && python -m playwright install chromium)"
    )

try:
    from PIL import Image
except ImportError:
    missing_dependencies.append("Pillow (pip install Pillow)")

try:
    import requests
except ImportError:
    missing_dependencies.append("requests (pip install requests)")

try:
    from tabulate import tabulate
except ImportError:
    missing_dependencies.append("tabulate (pip install tabulate)")

try:
    from dateutil import parser as date_parser
except ImportError:
    missing_dependencies.append("python-dateutil (pip install python-dateutil)")

if missing_dependencies:
    sys.stderr.write("The following dependencies are missing:\n")
    for package in missing_dependencies:
        sys.stderr.write(f"  - {package}\n")
    sys.stderr.write(
        "\nInstall the packages listed above and rerun this script.\n"
    )
    sys.exit(1)

# --- Configuration Constants ---
TEMP_DIR_PREFIX = "smartframe_extractor_"
LOG_FILE = "smartframe_extractor.log"
MAX_RETRIES = 5
RETRY_DELAY_SECONDS = 5
THUMBNAIL_DOWNLOAD_TIMEOUT = 10
MIN_CAPTION_LENGTH = 3
METADATA_SEPARATOR_LENGTH = 50
FAILED_DOWNLOADS_FILE = "failed_downloads.txt"

# --- Logging Setup ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

fh = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=10*1024*1024, backupCount=5
)
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)
logger.addHandler(fh)

# --- Chrome Extension Files Content (MANIFEST V3) ---
MANIFEST_JSON_CONTENT = """
{
  "manifest_version": 3,
  "name": "Canvas Data Extractor",
  "version": "2.0",
  "description": "Extracts data from a canvas, bypassing taint restrictions (Manifest V3).",
  "permissions": [
    "scripting"
  ],
  "host_permissions": [
    "<all_urls>"
  ],
  "background": {
    "service_worker": "background.js"
  },
  "content_scripts": [
    {
      "matches": ["<all_urls>"],
      "js": ["content_script.js"],
      "run_at": "document_start"
    }
  ],
  "web_accessible_resources": [
    {
      "resources": ["*"],
      "matches": ["<all_urls>"]
    }
  ]
}
"""

# background.js content - MANIFEST V3 SERVICE WORKER
BACKGROUND_JS_CONTENT = """
console.log("Canvas Extractor V3: Service Worker loaded.");

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log("Canvas Extractor V3: Message received in service worker.", request);
  
  if (request.action === "getCanvasDataURL") {
    console.log(`Canvas Extractor V3: Executing script in tab ${sender.tab.id} to get canvas data.`);
    
    // Manifest V3: Use chrome.scripting.executeScript instead of chrome.tabs.executeScript
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id },
      world: 'MAIN', // CRITICAL: Run in MAIN world to access window.__smartFrameShadowRoot
      func: (selector) => {
        console.log('Canvas Extractor [Privileged]: Script started in page context.');
          const selectorsToTry = [];
          if (selector) {
            selectorsToTry.push(selector);
          }
          if (window.__SMARTFRAME_TARGET_IMAGE_ID) {
            selectorsToTry.push(`smartframe-embed[image-id=\"${window.__SMARTFRAME_TARGET_IMAGE_ID}\"]`);
          }
          selectorsToTry.push('smartframe-embed:not([thumbnail-mode])');
          selectorsToTry.push('smartframe-embed');

          let smartframeEmbed = null;
          for (const candidateSelector of selectorsToTry) {
            try {
              const candidate = document.querySelector(candidateSelector);
              if (candidate) {
                smartframeEmbed = candidate;
                console.log(`Canvas Extractor [Privileged]: smartframe-embed resolved via selector '${candidateSelector}'.`);
                break;
              }
            } catch (err) {
              console.warn(`Canvas Extractor [Privileged]: Selector '${candidateSelector}' threw an error:`, err);
            }
          }

          if (!smartframeEmbed) {
            console.error('Canvas Extractor [Privileged]: smartframe-embed not found.');
            return { error: 'smartframe-embed element not found' };
          }
        console.log('Canvas Extractor [Privileged]: smartframe-embed found.');
        
        // Function to search for canvas with retry logic
        // Increased from 10 to 15 attempts and delay from 500ms to 1000ms for large canvas dimensions (9999x9999)
        function findCanvas(maxAttempts = 15, delay = 1000) {
          return new Promise((resolve) => {
            let attempts = 0;
            
            function tryFind() {
              attempts++;
              console.log(`Canvas Extractor [Privileged]: Search attempt ${attempts}/${maxAttempts}`);
              
              let canvas = null;
              
              // First, try to use the captured shadow root from window object
              if (window.__smartFrameShadowRoot) {
                console.log('Canvas Extractor [Privileged]: Checking captured shadow root...');
                const allCanvases = window.__smartFrameShadowRoot.querySelectorAll('canvas');
                console.log(`Canvas Extractor [Privileged]: Found ${allCanvases.length} canvas element(s) in captured shadowRoot`);
                
                canvas = window.__smartFrameShadowRoot.querySelector('canvas.stage');
                if (!canvas) {
                  canvas = window.__smartFrameShadowRoot.querySelector('canvas');
                }
                if (canvas) {
                  console.log('Canvas Extractor [Privileged]: Canvas found in captured shadowRoot');
                }
              } else {
                console.log('Canvas Extractor [Privileged]: window.__smartFrameShadowRoot is null/undefined');
              }
              
              // If not found via captured reference, try direct shadowRoot access
              if (!canvas) {
                const shadowRoot = smartframeEmbed.shadowRoot;
                if (shadowRoot) {
                  console.log('Canvas Extractor [Privileged]: Checking direct shadowRoot access...');
                  const allCanvases = shadowRoot.querySelectorAll('canvas');
                  console.log(`Canvas Extractor [Privileged]: Found ${allCanvases.length} canvas element(s) in direct shadowRoot`);
                  
                  canvas = shadowRoot.querySelector('canvas.stage');
                  if (!canvas) {
                    canvas = shadowRoot.querySelector('canvas');
                  }
                  if (canvas) {
                    console.log('Canvas Extractor [Privileged]: Canvas found in shadowRoot via direct access');
                  }
                } else {
                  console.log('Canvas Extractor [Privileged]: smartframeEmbed.shadowRoot is null');
                }
              }
              
              // Fallback to searching the entire document if not found in shadow DOM
              if (!canvas) {
                console.log('Canvas Extractor [Privileged]: Searching in document...');
                const allCanvases = document.querySelectorAll('canvas');
                console.log(`Canvas Extractor [Privileged]: Found ${allCanvases.length} canvas element(s) in document`);
                
                canvas = document.querySelector('canvas.stage');
                if (!canvas) {
                  canvas = document.querySelector('canvas[width][height]');
                  if (!canvas) {
                    canvas = document.querySelector('canvas');
                  }
                }
                if (canvas) {
                  console.log('Canvas Extractor [Privileged]: Canvas found in document');
                }
              }
              
              if (canvas) {
                console.log(`Canvas Extractor [Privileged]: Canvas found on attempt ${attempts}. Width: ${canvas.width}, Height: ${canvas.height}`);
                resolve(canvas);
              } else if (attempts < maxAttempts) {
                console.log(`Canvas Extractor [Privileged]: Canvas not found, retrying in ${delay}ms...`);
                setTimeout(tryFind, delay);
              } else {
                console.error('Canvas Extractor [Privileged]: Canvas element not found after all attempts.');
                resolve(null);
              }
            }
            
            tryFind();
          });
        }
        
        // Return a promise that resolves with the result
        return findCanvas().then(canvas => {
          if (!canvas) {
            return { error: 'Canvas element not found after all retry attempts' };
          }

          console.log('Canvas Extractor [Privileged]: Canvas found. Attempting to get data URL.');
          try {
            // CRITICAL FIX: Use original toDataURL and apply to current canvas
            const tempCanvas = document.createElement("canvas");
            tempCanvas.width = canvas.width || 1920; 
            tempCanvas.height = canvas.height || 1080;

            const dataUrl = tempCanvas.toDataURL.call(canvas, 'image/png');
            console.log('Canvas Extractor [Privileged]: Successfully generated data URL length:', dataUrl ? dataUrl.length : 'null');
            return { dataUrl: dataUrl };
          } catch (e) {
            console.error('Canvas Extractor [Privileged]: Error calling toDataURL:', e);
            return { error: 'Error calling toDataURL: ' + e.message };
          }
        });
      },
      args: [request.selector]
    }).then(results => {
      console.log("Canvas Extractor V3: Script execution finished.");
      const result = results && results[0] && results[0].result;
      console.log("Canvas Extractor V3: Sending response:", result);
      sendResponse(result || { error: 'No result from script execution' });
    }).catch(error => {
      console.error("Canvas Extractor V3: Error executing script in tab:", error);
      sendResponse({ error: error.toString() });
    });
    
    // Return true to indicate asynchronous response
    return true;
  }
});
"""

# content_script.js content - MANIFEST V3
CONTENT_SCRIPT_JS_CONTENT = """
console.log("Canvas Extractor V3: Content script loaded.");

// Listen for messages from the page context via window.postMessage
window.addEventListener('message', function(event) {
  // Verify origin matches current page (security check)
  if (event.origin !== window.location.origin) {
    return;
  }
  
  // Only accept messages from the same window (not from iframes)
  if (event.source !== window) {
    return;
  }
  
  // Check if this is our custom message
  if (event.data && event.data.type === 'GET_CANVAS_DATA') {
    console.log("Canvas Extractor V3 [Content]: 'GET_CANVAS_DATA' message received by content script.");
    const selector = event.data.selector;

    console.log(`Canvas Extractor V3 [Content]: Sending message to service worker for selector: ${selector}`);
    
    // Send a message to the service worker, requesting the data URL
    chrome.runtime.sendMessage({
      action: "getCanvasDataURL",
      selector: selector
    }).then(response => {
      console.log("Canvas Extractor V3 [Content]: Received response from service worker.", response);
      
      // Create a temporary element in the DOM to hold the response data
      const responseDiv = document.createElement('div');
      responseDiv.id = 'extension-response-data';
      responseDiv.style.display = 'none';
      
      if (response && response.dataUrl) {
        console.log("Canvas Extractor V3 [Content]: Data URL received, creating response div with data-url.");
        responseDiv.setAttribute('data-url', response.dataUrl);
      } else {
        const errorMsg = (response && response.error) || "Unknown error: No data URL returned.";
        console.error(`Canvas Extractor V3 [Content]: Error received from service worker: ${errorMsg}`);
        responseDiv.setAttribute('data-error', errorMsg);
      }
      document.body.appendChild(responseDiv);
      console.log("Canvas Extractor V3 [Content]: Appended responseDiv to body.");
    }).catch(error => {
      console.error("Canvas Extractor V3 [Content]: Error sending message or receiving response from service worker:", error);
      
      // Still try to append a div to indicate failure
      const responseDiv = document.createElement('div');
      responseDiv.id = 'extension-response-data';
      responseDiv.style.display = 'none';
      responseDiv.setAttribute('data-error', 'Communication error: ' + error.toString());
      document.body.appendChild(responseDiv);
      console.log("Canvas Extractor V3 [Content]: Appended error responseDiv to body after communication error.");
    });
  }
});
"""

# INJECTED_JAVASCRIPT_FOR_EXTENSION
INJECTED_JAVASCRIPT_FOR_EXTENSION = """
    (function() {
      // Store reference to smartframe-embed shadow root on window object for extension access
      // Only initialize if not already set by another script
      if (window.__smartFrameShadowRoot === undefined) {
          window.__smartFrameShadowRoot = null;
      }
      if (window.__smartFrameHostElement === undefined) {
          window.__smartFrameHostElement = null;
      }
      if (window.__SMARTFRAME_EMBED_SELECTOR === undefined) {
          window.__SMARTFRAME_EMBED_SELECTOR = null;
      }
      if (window.__SMARTFRAME_TARGET_IMAGE_ID === undefined) {
          window.__SMARTFRAME_TARGET_IMAGE_ID = null;
      }
      const nativeAttachShadow = Element.prototype.attachShadow;
      Element.prototype.attachShadow = function(init) {
          const shadowRoot = nativeAttachShadow.call(this, init);
          if (this.tagName.toLowerCase() === 'smartframe-embed') {
              const targetSelector = window.__SMARTFRAME_EMBED_SELECTOR;
              const targetImageId = window.__SMARTFRAME_TARGET_IMAGE_ID;
              const imageId = this.getAttribute('image-id');
              
              const matchesImageId = Boolean(targetImageId && imageId === targetImageId);
              const matchesSelector = Boolean(targetSelector && typeof this.matches === 'function' && this.matches(targetSelector));
              const shouldCapture = matchesImageId || matchesSelector || window.__smartFrameShadowRoot === null;
              
              if (shouldCapture) {
                  window.__smartFrameShadowRoot = shadowRoot;
                  window.__smartFrameHostElement = this;
                  console.log('Injected JavaScript (Main Page): Captured smartframe-embed shadow root reference.');
                  
                  // Log initial canvas count in shadow root
                  setTimeout(() => {
                      const canvases = shadowRoot.querySelectorAll('canvas');
                      console.log(`Injected JavaScript (Main Page): Shadow root has ${canvases.length} canvas element(s) initially.`);
                  }, 100);
              }
          }
          return shadowRoot;
      };

    console.log('Injected JavaScript (Main Page): Shadow root capture hook applied.');

      const smartframeEmbedSelector = window.__SMARTFRAME_EMBED_SELECTOR || 'smartframe-embed';
      const smartframeTargetImageId = window.__SMARTFRAME_TARGET_IMAGE_ID || null;
      
      function resolveSmartFrameElement() {
          const selectorsToTry = [];
          
          if (smartframeTargetImageId) {
              selectorsToTry.push(`smartframe-embed[image-id="${smartframeTargetImageId}"]`);
          }
          
          if (smartframeEmbedSelector && !selectorsToTry.includes(smartframeEmbedSelector)) {
              selectorsToTry.push(smartframeEmbedSelector);
          }
          
          selectorsToTry.push('smartframe-embed:not([thumbnail-mode])');
          selectorsToTry.push('smartframe-embed');
          
          for (const selector of selectorsToTry) {
              if (!selector) {
                  continue;
              }
              
              try {
                  const candidate = document.querySelector(selector);
                  if (candidate) {
                      console.log(`Injected JavaScript (Main Page): SmartFrame candidate found via selector '${selector}'.`);
                      return { element: candidate, selector };
                  }
              } catch (err) {
                  console.warn(`Injected JavaScript (Main Page): Selector '${selector}' threw an error:`, err);
              }
          }
          
          return { element: null, selector: smartframeEmbedSelector };
      }
    
    // Guard to prevent multiple executions
    let extractionInitialized = false;

    // Use event-based initialization instead of polling
    function initSmartFrameExtraction() {
        // Prevent multiple executions
        if (extractionInitialized) {
            return;
        }
        
      const { element: smartFrame, selector: resolvedSelector } = resolveSmartFrameElement();
      if (smartFrame) {
            extractionInitialized = true;
            console.log('Injected JavaScript (Main Page): smartframe-embed found.');
          window.__SMARTFRAME_ACTIVE_SELECTOR = resolvedSelector;
          window.__smartFrameHostElement = smartFrame;
          
          if (!window.__smartFrameShadowRoot && smartFrame.shadowRoot) {
              window.__smartFrameShadowRoot = smartFrame.shadowRoot;
          }

            // Retrieve original image dimensions from custom CSS properties
            const width = smartFrame.style.getPropertyValue('--sf-original-width');
            const height = smartFrame.style.getPropertyValue('--sf-original-height');

            // Apply correct dimensions to the smartframe-embed element's CSS
            // getPropertyValue returns an empty string if property doesn't exist
            if (width && height && width.trim() !== '' && height.trim() !== '' && width !== '0' && width !== '0px' && height !== '0' && height !== '0px') {
                // Add 'px' suffix if not already present (convert to string to be safe)
                const widthStr = String(width).trim();
                const heightStr = String(height).trim();
                const widthValue = widthStr.endsWith('px') ? widthStr : widthStr + 'px';
                const heightValue = heightStr.endsWith('px') ? heightStr : heightStr + 'px';
                
                smartFrame.style.width = widthValue;
                smartFrame.style.maxWidth = widthValue;
                smartFrame.style.height = heightValue;
                smartFrame.style.maxHeight = heightValue;
                console.log(`Injected JavaScript (Main Page): SmartFrame container dimensions set to ${widthValue} x ${heightValue} from CSS vars.`);
            } else {
                console.warn('Injected JavaScript (Main Page): Could not retrieve valid --sf-original-width/height. Attempting to set large fixed size.');
                smartFrame.style.width = '9999px';
                smartFrame.style.maxWidth = '9999px';
                smartFrame.style.height = '9999px';
                smartFrame.style.maxHeight = '9999px';
                console.log('Injected JavaScript (Main Page): SmartFrame container dimensions set to 9999px x 9999px (fixed fallback).');
            }
            
            // Dispatch a window resize event to encourage SmartFrame to re-render its canvas
            window.dispatchEvent(new Event('resize'));
            console.log('Injected JavaScript (Main Page): Dispatched window resize event.');

            // Wait for rendering before dispatching to extension
            // Timeout history: 15s (initial) → 2s (v2 optimization) → 1s (v3, matches TamperMonkey script) → 3s (current fix for large dimension rendering)
            // Increased to 3 seconds to allow SmartFrame sufficient time to detect resize event
            // and re-render canvas at the new large dimensions (9999x9999)
            setTimeout(() => {
                console.log('Injected JavaScript (Main Page): Attempting to send message to content script via window.postMessage.');
                window.postMessage({
                    type: 'GET_CANVAS_DATA',
                      selector: resolvedSelector || smartframeEmbedSelector
                }, window.location.origin);
                console.log('Injected JavaScript (Main Page): Message sent to content script.');
            }, 3000);
        } else {
            console.warn('Injected JavaScript (Main Page): smartframe-embed not found on page.');
        }
    }

    // Wait for the page to fully load (matching TamperMonkey script behavior)
    window.addEventListener('load', initSmartFrameExtraction);
    
    // Also try on DOMContentLoaded as a fallback for faster loading
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSmartFrameExtraction);
    } else {
        // DOM already loaded, try now
        initSmartFrameExtraction();
    }
    
    // Add a delayed retry in case the element loads after initial events
    setTimeout(initSmartFrameExtraction, 1000);
    setTimeout(initSmartFrameExtraction, 2000);
})();
"""

# --- Helper Functions ---
def sanitize_filename(url_or_id):
    """
    Generates a sanitized filename from a URL or image ID.
    """
    if url_or_id:
        filename = re.sub(r'[^a-zA-Z0-9.\-_]', '-', url_or_id)
        filename = re.sub(r'-+', '-', filename).strip('-')
        return filename
    return "unknown_image"

def download_thumbnail(url: str, output_path: Path):
    """
    Downloads a thumbnail image using the requests library.
    Returns True on success, False on failure.
    """
    logger.info(f"Attempting to download thumbnail from: {url}")
    try:
        response = requests.get(url, timeout=THUMBNAIL_DOWNLOAD_TIMEOUT, stream=True)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"Thumbnail downloaded successfully to: {output_path}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download thumbnail from {url}: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during thumbnail download: {e}", exc_info=True)
        return False

def transfer_metadata_with_exiftool(source_image: Path, target_image: Path):
    """
    Transfers metadata from a source image to a target image using ExifTool.
    Returns True on success, False on failure.
    """
    logger.info(f"Transferring metadata from '{source_image}' to '{target_image}' using ExifTool.")
    try:
        command = ['exiftool', '-tagsFromFile', str(source_image), '-overwrite_original', str(target_image)]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        logger.info(f"ExifTool stdout:\n{result.stdout.strip()}")
        if result.stderr:
            logger.warning(f"ExifTool stderr:\n{result.stderr.strip()}")
        logger.info("Metadata transfer complete.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"ExifTool failed with error code {e.returncode}. Stderr:\n{e.stderr.strip()}")
        return False
    except FileNotFoundError:
        logger.error("ExifTool command not found. Please ensure ExifTool is installed and in your system's PATH.")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during ExifTool operation: {e}", exc_info=True)
        return False

def convert_png_to_jpg(png_path: Path, jpg_path: Path):
    """
    Converts a PNG image to JPG format using Pillow.
    Returns True on success, False on failure.
    """
    logger.info(f"Converting '{png_path}' to JPG: '{jpg_path}'")
    try:
        with Image.open(png_path) as img:
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            img.save(jpg_path, 'jpeg', quality=95)
        logger.info("Image conversion successful.")
        return True
    except Exception as e:
        logger.error(f"Error converting image from PNG to JPG: {e}", exc_info=True)
        return False

def setup_extension_files(extension_dir: Path):
    """Creates the extension directory and writes the necessary files."""
    if extension_dir.exists():
        shutil.rmtree(extension_dir)
    extension_dir.mkdir(parents=True, exist_ok=True)

    (extension_dir / "manifest.json").write_text(MANIFEST_JSON_CONTENT)
    (extension_dir / "background.js").write_text(BACKGROUND_JS_CONTENT)
    (extension_dir / "content_script.js").write_text(CONTENT_SCRIPT_JS_CONTENT)
    logger.info(f"Chrome extension V3 files created in: {extension_dir.absolute()}")

def cleanup_temp_dirs(user_data_dir: Path, extension_dir: Path):
    """Cleans up the temporary user data and extension directories."""
    if user_data_dir.exists():
        shutil.rmtree(user_data_dir)
        logger.info(f"Cleaned up user data directory: {user_data_dir.absolute()}")
    if extension_dir.exists():
        shutil.rmtree(extension_dir)
        logger.info(f"Cleaned up extension directory: {extension_dir.absolute()}")

async def get_thumbnail_url_from_page(page, page_url):
    """
    Attempts to extract the thumbnail URL from the page.
    Returns the URL if found, None otherwise.
    """
    logger.info("Attempting to extract thumbnail URL from page metadata.")
    try:
        og_image = page.locator('meta[property="og:image"]')
        if await og_image.count() > 0:
            thumbnail_url = await og_image.get_attribute('content')
            if thumbnail_url:
                thumbnail_url = urljoin(page_url, thumbnail_url)
                logger.info(f"Found thumbnail URL from og:image: {thumbnail_url}")
                return thumbnail_url
        
        twitter_image = page.locator('meta[name="twitter:image"]')
        if await twitter_image.count() > 0:
            thumbnail_url = await twitter_image.get_attribute('content')
            if thumbnail_url:
                thumbnail_url = urljoin(page_url, thumbnail_url)
                logger.info(f"Found thumbnail URL from twitter:image: {thumbnail_url}")
                return thumbnail_url
        
        logger.warning("No thumbnail URL found in page metadata.")
        return None
    except Exception as e:
        logger.error(f"Error extracting thumbnail URL: {e}", exc_info=True)
        return None

async def extract_smartframe_metadata(page, page_url):
    """
    Extracts metadata from SmartFrame.com pages specifically.
    Returns a dictionary with Caption, Date, Credit, and other metadata.
    """
    metadata = {
        "caption": None,
        "date": None,
        "credit": None,
        "image_id": None,
        "image_size": None,
        "provider": None,
        "location": None,
        "city": None,
        "country": None,
        "photographer": None,
        "featuring": None,
        "title": None,
        "subject": None
    }
    
    if "smartframe.com" not in page_url:
        logger.info("URL is not from smartframe.com, skipping SmartFrame-specific metadata extraction.")
        return metadata
    
    logger.info("Extracting SmartFrame.com metadata from page...")
    try:
        # Attempt structured extraction using observed SmartFrame layout
        metadata_container = page.locator("div.flex.flex-col.gap-4x").first
        if await metadata_container.count() > 0:
            logger.info("Structured metadata container found.")
            
            try:
                provider_locator = metadata_container.locator("section").nth(0).locator("h2").first
                provider_text = await provider_locator.text_content(timeout=3000)
                if provider_text:
                    provider_text = provider_text.strip()
                    if provider_text:
                        metadata["provider"] = provider_text
                        logger.info(f"Found provider: {metadata['provider']}")
            except Exception as e:
                logger.debug(f"Structured provider extraction failed: {e}")
            
            try:
                caption_locator = metadata_container.locator("section").nth(1).locator("h1").first
                caption_text = await caption_locator.text_content(timeout=3000)
                if caption_text:
                    caption_text = caption_text.strip()
                    if caption_text:
                        metadata["caption"] = caption_text
                        logger.info(f"Found caption: {metadata['caption']}")
            except Exception as e:
                logger.debug(f"Structured caption extraction failed: {e}")
            
            try:
                details_paragraph = metadata_container.locator("section").nth(1).locator("p").first
                details_text = await details_paragraph.inner_text(timeout=3000)
                if details_text:
                    normalized_text = details_text.replace('\xa0', ' ')
                    markers = ("Featuring:", "Where:", "When:", "Credit:", "SmartFrame image ID:", "Image size:")
                    for marker in markers:
                        normalized_text = normalized_text.replace(f" {marker}", f"\n{marker}")
                    # Collect any narrative sentences that appear before the structured
                    # metadata markers (e.g. "When:", "Credit:"). These are typically the
                    # descriptive sentences SmartFrame shows on the page and should flow
                    # into the caption, title, and subject fields.
                    preface_lines: List[str] = []
                    metadata_section_started = False
                    for raw_line in normalized_text.splitlines():
                        line = raw_line.strip()
                        if not line:
                            continue

                        line_starts_with_marker = any(line.startswith(marker) for marker in markers)
                        if not metadata_section_started and not line_starts_with_marker:
                            preface_lines.append(line)
                            continue

                        if line_starts_with_marker:
                            metadata_section_started = True

                        if line.startswith("When:") and not metadata["date"]:
                            metadata["date"] = line.replace("When:", "").strip()
                            logger.info(f"Found date: {metadata['date']}")
                        elif line.startswith("Credit:") and not metadata["credit"]:
                            metadata["credit"] = line.replace("Credit:", "").strip()
                            logger.info(f"Found credit: {metadata['credit']}")
                        elif line.startswith("Featuring:") and not metadata["featuring"]:
                            metadata["featuring"] = line.replace("Featuring:", "").strip()
                            logger.info(f"Found featuring: {metadata['featuring']}")
                        elif line.startswith("Where:") and not metadata["location"]:
                            location_value = line.replace("Where:", "").strip()
                            metadata["location"] = location_value
                            logger.info(f"Found location: {metadata['location']}")
                            if not metadata["city"] or not metadata["country"]:
                                parts = [part.strip() for part in location_value.split(",") if part.strip()]
                                if parts:
                                    if len(parts) == 1:
                                        metadata["city"] = metadata["city"] or parts[0]
                                    else:
                                        metadata["city"] = metadata["city"] or parts[0]
                                        metadata["country"] = metadata["country"] or parts[-1]
                                        logger.info(f"Derived city/country: {metadata['city']}, {metadata['country']}")
                        elif line.startswith("SmartFrame image ID:") and not metadata["image_id"]:
                            metadata["image_id"] = line.replace("SmartFrame image ID:", "").strip()
                            logger.info(f"Found image ID from paragraph: {metadata['image_id']}")
                        elif line.startswith("Image size:") and not metadata["image_size"]:
                            metadata["image_size"] = line.replace("Image size:", "").strip()
                            logger.info(f"Found image size: {metadata['image_size']}")

                    if preface_lines:
                        preface_text = " | ".join(preface_lines)
                        if metadata["caption"]:
                            if preface_text not in metadata["caption"]:
                                metadata["caption"] = f"{preface_text} | {metadata['caption']}"
                        else:
                            metadata["caption"] = preface_text

                        # Ensure the more descriptive preface is also surfaced in title and
                        # subject so downstream metadata consumers have consistent values.
                        metadata["title"] = metadata["title"] or preface_text
                        metadata["subject"] = metadata["subject"] or preface_text
                        logger.info(f"Derived preface summary for title/subject: {preface_text}")
            except Exception as e:
                logger.debug(f"Structured detail extraction failed: {e}")
            
            try:
                info_items = await metadata_container.locator("section.bg-iy-neutral-100 li").all_text_contents()
                for item in info_items:
                    if not item:
                        continue
                    text = item.strip()
                    if not text:
                        continue
                    normalized = " ".join(text.split())
                    if ":" in normalized:
                        label, value = normalized.split(":", 1)
                        label = label.strip().lower()
                        value = value.strip()
                        if label == "smartframe image id" and not metadata["image_id"]:
                            metadata["image_id"] = value
                            logger.info(f"Found image ID from list: {metadata['image_id']}")
                        elif label == "image size" and not metadata["image_size"]:
                            metadata["image_size"] = value
                            logger.info(f"Found image size from list: {metadata['image_size']}")
                        elif label == "credit" and not metadata["credit"]:
                            metadata["credit"] = value
                            logger.info(f"Found credit from list: {metadata['credit']}")
                        elif label == "photographer" and not metadata["photographer"]:
                            metadata["photographer"] = value
                            logger.info(f"Found photographer: {metadata['photographer']}")
                        elif label == "country" and not metadata["country"]:
                            metadata["country"] = value
                            logger.info(f"Found country: {metadata['country']}")
                        elif label == "city" and not metadata["city"]:
                            metadata["city"] = value
                            logger.info(f"Found city: {metadata['city']}")
            except Exception as e:
                logger.debug(f"Structured list extraction failed: {e}")
        
    except Exception as e:
        logger.warning(f"Error extracting SmartFrame metadata: {e}")
    
    # Fallback: legacy text parsing to fill missing fields
    missing_fields = [key for key in ("provider", "caption", "date", "credit", "image_id", "image_size") if not metadata.get(key)]
    if missing_fields:
        logger.info(f"Attempting fallback metadata extraction for missing fields: {missing_fields}")
        try:
            full_text = await page.inner_text("body", timeout=5000)
            lines = full_text.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if not metadata["date"] and line.startswith("When:"):
                    metadata["date"] = line.replace("When:", "").strip()
                    logger.info(f"Fallback found date: {metadata['date']}")
                elif not metadata["credit"] and line.startswith("Credit:"):
                    metadata["credit"] = line.replace("Credit:", "").strip()
                    logger.info(f"Fallback found credit: {metadata['credit']}")
                elif not metadata["featuring"] and line.startswith("Featuring:"):
                    metadata["featuring"] = line.replace("Featuring:", "").strip()
                    logger.info(f"Fallback found featuring: {metadata['featuring']}")
                elif not metadata["location"] and line.startswith("Where:"):
                    location_value = line.replace("Where:", "").strip()
                    metadata["location"] = location_value
                    logger.info(f"Fallback found location: {metadata['location']}")
                    parts = [part.strip() for part in location_value.split(",") if part.strip()]
                    if parts:
                        if len(parts) == 1 and not metadata["city"]:
                            metadata["city"] = parts[0]
                        else:
                            if not metadata["city"]:
                                metadata["city"] = parts[0]
                            if not metadata["country"]:
                                metadata["country"] = parts[-1]
                            logger.info(f"Fallback derived city/country: {metadata['city']}, {metadata['country']}")
                elif not metadata["image_id"] and "SmartFrame image ID:" in line:
                    metadata["image_id"] = line.split("SmartFrame image ID:")[-1].strip()
                    logger.info(f"Fallback found image ID: {metadata['image_id']}")
                elif not metadata["image_size"] and "Image size:" in line:
                    metadata["image_size"] = line.split("Image size:")[-1].strip()
                    logger.info(f"Fallback found image size: {metadata['image_size']}")
                elif not metadata["photographer"] and line.startswith("Photographer:"):
                    metadata["photographer"] = line.replace("Photographer:", "").strip()
                    logger.info(f"Fallback found photographer: {metadata['photographer']}")
                elif not metadata["country"] and line.startswith("Country:"):
                    metadata["country"] = line.replace("Country:", "").strip()
                    logger.info(f"Fallback found country: {metadata['country']}")
                elif not metadata["city"] and line.startswith("City:"):
                    metadata["city"] = line.replace("City:", "").strip()
                    logger.info(f"Fallback found city: {metadata['city']}")
            
            if not metadata["caption"] and metadata["provider"]:
                for i, line in enumerate(lines):
                    if line.strip() == metadata["provider"]:
                        if i + 1 < len(lines):
                            potential_caption = lines[i + 1].strip()
                            if potential_caption and not potential_caption.startswith("When:") and not potential_caption.startswith("Credit:") and len(potential_caption) > MIN_CAPTION_LENGTH:
                                metadata["caption"] = potential_caption
                                logger.info(f"Fallback found caption: {metadata['caption']}")
                                break
            if metadata["caption"]:
                if not metadata["title"]:
                    metadata["title"] = metadata["caption"]
                if not metadata["subject"]:
                    metadata["subject"] = metadata["caption"]
        except Exception as e:
            logger.warning(f"Error during fallback metadata extraction: {e}")
    
    return metadata

def save_metadata_to_file(metadata: Dict[str, Any], output_path: Path):
    """
    Saves extracted metadata to a text file alongside the image.
    Excludes image_size from the output as it's not needed in metadata.
    """
    metadata_path = output_path.with_suffix('.txt')
    try:
        with open(metadata_path, 'w', encoding='utf-8') as f:
            f.write("SmartFrame Image Metadata\n")
            f.write("=" * METADATA_SEPARATOR_LENGTH + "\n\n")
            for key, value in metadata.items():
                # Skip image_size as requested by user
                if value and key != 'image_size':
                    f.write(f"{key.replace('_', ' ').title()}: {value}\n")
        logger.info(f"Metadata saved to: {metadata_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving metadata to file: {e}")
        return False

def write_failed_download_report(results: List[Dict[str, Any]], output_path: Path) -> bool:
    """
    Persist a summary of failed downloads so the user can retry manually.
    """
    try:
        output_path = output_path.resolve()
        with open(output_path, 'w', encoding='utf-8') as report:
            if not results:
                report.write("The extractor did not attempt any downloads.\n")
                logger.info(f"Failed download report written to: {output_path}")
                return True

            failed = [res for res in results if res.get("Status") != "Success"]
            if not failed:
                report.write("All downloads succeeded.\n")
            else:
                report.write("Failed SmartFrame downloads:\n")
                for item in failed:
                    original_url = item.get("Original URL", "Unknown URL")
                    error_message = item.get("Error Message") or "No additional error details."
                    report.write(f"- {original_url}\n    Reason: {error_message}\n")

        logger.info(f"Failed download report written to: {output_path}")
        return True
    except Exception as exc:
        logger.error(f"Unable to write failed download report to {output_path}: {exc}", exc_info=True)
        return False

def parse_date_components(date_str: str) -> Optional[Dict[str, str]]:
    """
    Parse various date formats and convert them into structured components suitable for
    EXIF, IPTC, and XMP metadata fields.
    
    Returns a dictionary with the following keys:
      - exif_datetime: YYYY:MM:DD HH:MM:SS
      - iptc_date: YYYY:MM:DD
      - iptc_time: HH:MM:SS+/-HH:MM
      - xmp_datetime: YYYY-MM-DDTHH:MM:SS(+/-HH:MM or Z)
    """
    if not date_str:
        return None
    
    try:
        parsed_date = date_parser.parse(date_str, fuzzy=True)
    except Exception as e:
        logger.warning(f"Could not parse date '{date_str}' into structured components: {e}")
        return None
    
    tzinfo = parsed_date.tzinfo
    offset_for_iptc = "+00:00"
    if tzinfo is not None and parsed_date.utcoffset() is not None:
        offset_seconds = int(parsed_date.utcoffset().total_seconds())
        sign = "+" if offset_seconds >= 0 else "-"
        offset_seconds = abs(offset_seconds)
        offset_hours, remainder = divmod(offset_seconds, 3600)
        offset_minutes = remainder // 60
        offset_for_iptc = f"{sign}{offset_hours:02d}:{offset_minutes:02d}"
    
    naive_date = parsed_date.replace(tzinfo=None)
    exif_datetime = naive_date.strftime("%Y:%m:%d %H:%M:%S")
    iptc_date = naive_date.strftime("%Y:%m:%d")
    iptc_time = naive_date.strftime("%H:%M:%S") + offset_for_iptc
    xmp_offset = "Z" if offset_for_iptc == "+00:00" else offset_for_iptc
    xmp_datetime = naive_date.strftime("%Y-%m-%dT%H:%M:%S") + xmp_offset
    
    logger.info(
        "Parsed date '%s' into exif_datetime='%s', iptc_date='%s', iptc_time='%s', xmp_datetime='%s'",
        date_str,
        exif_datetime,
        iptc_date,
        iptc_time,
        xmp_datetime
    )
    
    return {
        "exif_datetime": exif_datetime,
        "iptc_date": iptc_date,
        "iptc_time": iptc_time,
        "xmp_datetime": xmp_datetime
    }

def write_metadata_to_image(metadata: Dict[str, Any], image_path: Path):
    """
    Writes SmartFrame metadata into the image EXIF/IPTC fields using ExifTool.
    Maps extracted metadata to appropriate EXIF/IPTC/XMP fields.
    Returns True on success, False on failure.
    """
    if not metadata or not any(metadata.values()):
        logger.info("No metadata to write to image.")
        return True
    
    logger.info(f"Writing SmartFrame metadata to image: {image_path}")
    try:
        # Build ExifTool command with metadata mappings
        command = ['exiftool', '-overwrite_original']
        
        # Map SmartFrame metadata to EXIF/IPTC/XMP fields
        # IPTC fields are widely supported and recommended for editorial images
        
        if metadata.get('caption'):
            # Caption/Description fields
            command.extend([
                f'-IPTC:Caption-Abstract={metadata["caption"]}',
                f'-XMP:Description={metadata["caption"]}',
                f'-EXIF:ImageDescription={metadata["caption"]}'
            ])
        
        if metadata.get('title'):
            # Headline/Title fields (IPTC ObjectName & Headline, plus XMP/EXIF equivalents)
            command.extend([
                f'-IPTC:ObjectName={metadata["title"]}',
                f'-IPTC:Headline={metadata["title"]}',
                f'-XMP:Title={metadata["title"]}',
                f'-XMP-photoshop:Headline={metadata["title"]}',
                f'-EXIF:XPTitle={metadata["title"]}'
            ])
        
        if metadata.get('subject'):
            # Store the subject as both XMP subject and IPTC keyword for wider compatibility
            command.extend([
                f'-XMP:Subject={metadata["subject"]}',
                f'-IPTC:Keywords={metadata["subject"]}'
            ])
        
        if metadata.get('credit'):
            # Credit/Source fields and Author field
            command.extend([
                f'-IPTC:Credit={metadata["credit"]}',
                f'-IPTC:By-line={metadata["credit"]}',
                f'-XMP:Credit={metadata["credit"]}',
                f'-EXIF:Artist={metadata["credit"]}',
                f'-XMP:Creator={metadata["credit"]}'
            ])
        
        if metadata.get('provider'):
            # Source/Provider fields
            command.extend([
                f'-IPTC:Source={metadata["provider"]}',
                f'-XMP:Source={metadata["provider"]}'
            ])
        
        if metadata.get('date'):
            parsed_components = parse_date_components(metadata["date"])
            if parsed_components:
                exif_dt = parsed_components["exif_datetime"]
                iptc_date = parsed_components["iptc_date"]
                iptc_time = parsed_components["iptc_time"]
                xmp_dt = parsed_components["xmp_datetime"]
                
                command.extend([
                    f'-EXIF:DateTimeOriginal={exif_dt}',
                    f'-EXIF:CreateDate={exif_dt}',
                    f'-EXIF:DateTimeDigitized={exif_dt}',
                    f'-IPTC:DateCreated={iptc_date}',
                    f'-IPTC:TimeCreated={iptc_time}',
                    f'-XMP:DateCreated={xmp_dt}',
                    f'-XMP:DateTimeOriginal={xmp_dt}',
                    f'-XMP:CreateDate={xmp_dt}',
                    f'-XMP:MetadataDate={xmp_dt}',
                    f'-XMP:ModifyDate={xmp_dt}'
                ])
            else:
                cleaned_date = metadata["date"].strip()
                if cleaned_date:
                    command.extend([
                        f'-IPTC:DateCreated={cleaned_date}',
                        f'-XMP:DateCreated={cleaned_date}'
                    ])
        
        if metadata.get('city'):
            command.extend([
                f'-IPTC:City={metadata["city"]}',
                f'-XMP-photoshop:City={metadata["city"]}'
            ])
        
        if metadata.get('country'):
            command.extend([
                f'-IPTC:Country-PrimaryLocationName={metadata["country"]}',
                f'-XMP-photoshop:Country={metadata["country"]}'
            ])
        
        if metadata.get('location'):
            command.extend([
                f'-IPTC:Sub-location={metadata["location"]}',
                f'-XMP-photoshop:Location={metadata["location"]}'
            ])
        
        if metadata.get('photographer'):
            command.extend([
                f'-XMP:Contributor={metadata["photographer"]}'
            ])
        
        if metadata.get('featuring'):
            participants = [name.strip() for name in re.split(r',| and ', metadata["featuring"]) if name.strip()]
            if not participants:
                participants = [metadata["featuring"].strip()]
            for person in participants:
                command.append(f'-XMP:PersonInImage+={person}')
        
        if metadata.get('image_id'):
            # Image ID in custom fields
            command.extend([
                f'-XMP:Identifier={metadata["image_id"]}',
                f'-IPTC:OriginalTransmissionReference={metadata["image_id"]}'
            ])
        
        # Create comprehensive Comments field with all metadata except image_size
        comments_parts = []
        if metadata.get('caption'):
            comments_parts.append(f"Caption: {metadata['caption']}")
        if metadata.get('date'):
            comments_parts.append(f"Date: {metadata['date']}")
        if metadata.get('credit'):
            comments_parts.append(f"Credit: {metadata['credit']}")
        if metadata.get('photographer') and metadata.get('photographer') != metadata.get('credit'):
            comments_parts.append(f"Photographer: {metadata['photographer']}")
        if metadata.get('image_id'):
            comments_parts.append(f"Image ID: {metadata['image_id']}")
        if metadata.get('provider'):
            comments_parts.append(f"Provider: {metadata['provider']}")
        location_components = []
        if metadata.get('city'):
            location_components.append(metadata['city'])
        if metadata.get('country'):
            location_components.append(metadata['country'])
        if location_components:
            comments_parts.append(f"Location: {', '.join(location_components)}")
        elif metadata.get('location'):
            comments_parts.append(f"Location: {metadata['location']}")
        if metadata.get('featuring'):
            comments_parts.append(f"Featuring: {metadata['featuring']}")
        # Avoid duplicating the caption text in the comments; only append when distinct.
        if metadata.get('subject') and metadata['subject'] != metadata.get('caption'):
            comments_parts.append(f"Subject: {metadata['subject']}")
        if metadata.get('title') and metadata['title'] not in (metadata.get('caption'), metadata.get('subject')):
            comments_parts.append(f"Title: {metadata['title']}")
        
        if comments_parts:
            comments_text = " | ".join(comments_parts)
            command.extend([
                f'-EXIF:UserComment={comments_text}',
                f'-XMP:UserComment={comments_text}'
            ])
        
        # Add the target image path
        command.append(str(image_path))
        
        # Execute ExifTool
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        logger.info(f"ExifTool stdout:\n{result.stdout.strip()}")
        if result.stderr:
            logger.warning(f"ExifTool stderr:\n{result.stderr.strip()}")
        logger.info("SmartFrame metadata successfully written to image.")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"ExifTool failed with error code {e.returncode}. Stderr:\n{e.stderr.strip()}")
        return False
    except FileNotFoundError:
        logger.error("ExifTool command not found. Please ensure ExifTool is installed and in your system's PATH.")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred while writing metadata to image: {e}", exc_info=True)
        return False

# --- Main Automation Logic ---
async def process_url(
    target_url: str,
    output_dir_path: Path,
    extension_dir: Path,
    user_data_dir: Path,
    temp_root_dir: Path,
    thumbnail_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Automates the download of high-resolution images protected by SmartFrame for a single URL.
    """
    page_result = {
        "Original URL": target_url,
        "Image ID": "N/A",
        "Status": "Failed",
        "Output Filename": "N/A",
        "Error Message": ""
    }
    
    parsed_target_url = urlparse(target_url)
    netloc_lower = parsed_target_url.netloc.lower()
    is_smartframe_url = netloc_lower == 'smartframe.com' or netloc_lower.endswith('.smartframe.com')
    
    smartframe_target_image_id: Optional[str] = None
    smartframe_embed_selector = 'smartframe-embed'
    if is_smartframe_url:
        path_segments = [segment for segment in parsed_target_url.path.split('/') if segment]
        if path_segments:
            potential_image_id = path_segments[-1]
            if potential_image_id:
                smartframe_target_image_id = potential_image_id
                smartframe_embed_selector = f'smartframe-embed[image-id="{potential_image_id}"]'
        if smartframe_target_image_id is None:
            smartframe_embed_selector = 'smartframe-embed:not([thumbnail-mode])'
    
    try:
        async with async_playwright() as p:
            # CRITICAL: Large viewport (9999x9999) is required for SmartFrame to render
            # the canvas at full resolution. The SmartFrame embed renders its canvas
            # based on the actual viewport/display size, not just CSS dimensions.
            browser_context = await p.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=False,
                args=[
                    f'--disable-extensions-except={extension_dir.absolute()}',
                    f'--load-extension={extension_dir.absolute()}',
                    "--start-maximized"
                ],
                viewport={"width": 9999, "height": 9999},
                ignore_https_errors=True
            )
            
            try:
                init_selector_script = (
                    f"window.__SMARTFRAME_EMBED_SELECTOR = {json.dumps(smartframe_embed_selector)};"
                    f"window.__SMARTFRAME_TARGET_IMAGE_ID = {json.dumps(smartframe_target_image_id)};"
                )
                await browser_context.add_init_script(init_selector_script)
                await browser_context.add_init_script(INJECTED_JAVASCRIPT_FOR_EXTENSION)
                logger.info("INJECTED_JAVASCRIPT_FOR_EXTENSION injected as an init script.")

                page = await browser_context.new_page()
                
                page.on("console", lambda msg: logger.info(f"Browser Console [{msg.type.upper()}]: {msg.text}"))
                
                logger.info(f"Navigating to URL: {target_url}")
                await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                logger.info(f"Page loaded: {target_url} (DOM content loaded)")
                
                # Extract SmartFrame metadata from page
                smartframe_metadata = await extract_smartframe_metadata(page, target_url)

                response_selector = '#extension-response-data'
                logger.info(f"Waiting for extension response element: {response_selector}")
                
                await page.wait_for_selector(
                    f'{response_selector}[data-url], {response_selector}[data-error]', 
                    state='attached', 
                    timeout=120000
                )
                logger.info("Extension response element found.")

                image_data_url = await page.locator(response_selector).get_attribute('data-url')
                error_from_extension = await page.locator(response_selector).get_attribute('data-error')
                
                image_id = None
                try:
                    candidate_selectors = [
                        smartframe_embed_selector,
                        'smartframe-embed:not([thumbnail-mode])',
                        'smartframe-embed'
                    ]
                    smartframe_element = None
                    for selector in candidate_selectors:
                        if not selector:
                            continue
                        locator = page.locator(selector)
                        if await locator.count() > 0:
                            smartframe_element = locator.nth(0)
                            logger.info(f"Selected smartframe element using selector '{selector}'.")
                            break
                    
                    if smartframe_element:
                        image_id_attr = await smartframe_element.get_attribute('image-id')
                        if image_id_attr:
                            image_id = image_id_attr.split('_').pop().replace(" ", "-")
                            logger.info(f"Extracted image ID from smartframe-embed: {image_id}")
                            page_result["Image ID"] = image_id
                except Exception as e:
                    logger.warning(f"Could not get image-id from smartframe-embed: {e}")
                
                if error_from_extension:
                    error_msg = f"Extension reported error: {error_from_extension}"
                    logger.error(f"Error: {error_msg}")
                    page_result["Error Message"] = error_msg
                elif image_data_url and image_data_url.startswith("data:image/png;base64,"):
                    _, base64_data = image_data_url.split(",", 1)
                    file_extension = ".png"

                    final_filename = sanitize_filename(image_id if image_id else urlparse(target_url).path.split('/')[-1]) + file_extension
                    output_path = output_dir_path / final_filename

                    with open(output_path, "wb") as f:
                        f.write(base64.b64decode(base64_data))

                    logger.info(f"Successfully downloaded raw PNG: {output_path}")
                    
                    output_jpg_path = output_path.with_suffix(".jpg")
                    if convert_png_to_jpg(output_path, output_jpg_path):
                        logger.info(f"Converted PNG to JPG: {output_jpg_path}")
                    else:
                        logger.warning("Failed to convert PNG to JPG. Keeping PNG.")
                        output_jpg_path = output_path

                    # Handle thumbnail extraction and metadata transfer
                    # Skip thumbnail for smartframe.com as these pages don't have thumbnails
                    if is_smartframe_url:
                        logger.info("Skipping thumbnail extraction for smartframe.com (no thumbnails available).")
                    else:
                        if not thumbnail_url:
                            thumbnail_url = await get_thumbnail_url_from_page(page, page.url)
                        
                        if thumbnail_url:
                            temp_thumbnail_path = temp_root_dir / "thumbnail.jpg"
                            if download_thumbnail(thumbnail_url, temp_thumbnail_path):
                                if not transfer_metadata_with_exiftool(temp_thumbnail_path, output_jpg_path):
                                    logger.warning("Metadata transfer failed. Image saved without original metadata.")
                            else:
                                logger.warning("Thumbnail download failed. Skipping metadata transfer.")
                        else:
                            logger.info("No thumbnail URL available. Skipping metadata transfer.")

                    logger.info(f"High-resolution image saved to: {output_jpg_path.resolve()}")
                    
                    # Save metadata to TXT file and write to image EXIF/IPTC fields if any metadata was extracted
                    if smartframe_metadata and any(smartframe_metadata.values()):
                        save_metadata_to_file(smartframe_metadata, output_jpg_path)
                        write_metadata_to_image(smartframe_metadata, output_jpg_path)
                    
                    page_result.update({
                        "Status": "Success",
                        "Output Filename": output_jpg_path.name,
                        "Error Message": "N/A"
                    })
                else:
                    error_msg = "No valid image data URL received from extension."
                    logger.error(f"Error: {error_msg}")
                    page_result["Error Message"] = error_msg
            finally:
                # Close browser_context before exiting the async_playwright context
                if browser_context:
                    await browser_context.close()

    except Exception as e:
        error_msg = f"An unrecoverable error occurred during the main execution for URL {target_url}: {e}"
        logger.critical(error_msg, exc_info=True)
        page_result["Error Message"] = error_msg
    
    return page_result

# --- Entry point for the script ---
async def run_main_script():
    OUTPUT_DIR_PATH = Path("downloaded_images")
    os.makedirs(OUTPUT_DIR_PATH, exist_ok=True)

    EXTENSION_DIR = Path("./chrome_extension_bypass")
    USER_DATA_DIR = Path("./playwright_user_data")
    TEMP_ROOT_DIR = Path(tempfile.mkdtemp(prefix=TEMP_DIR_PREFIX))
    FAILED_DOWNLOADS_PATH = Path(FAILED_DOWNLOADS_FILE)
    
    logger.info(f"Created temporary directory: {TEMP_ROOT_DIR.absolute()}")

    all_results: List[Dict[str, Any]] = []
    failed_report_written = False

    try:
        if USER_DATA_DIR.exists():
            shutil.rmtree(USER_DATA_DIR)
            logger.info(f"Removed old user data directory: {USER_DATA_DIR.absolute()}")
        
        setup_extension_files(EXTENSION_DIR)

        urls = []
        URLS_FILE = "urls.txt"
        try:
            with open(URLS_FILE, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
            if not urls:
                logger.warning(f"No URLs found in {URLS_FILE}. Using hardcoded example URL.")
                urls = ["https://archive.newsimages.co.uk/id/00333991"]
        except FileNotFoundError:
            logger.warning(f"Error: {URLS_FILE} not found. Using hardcoded example URL.")
            urls = ["https://archive.newsimages.co.uk/id/00333991"]
        except Exception as e:
            logger.error(f"Error reading {URLS_FILE}: {e}. Using hardcoded example URL.", exc_info=True)
            urls = ["https://archive.newsimages.co.uk/id/00333991"]

        for url in urls:
            result = await process_url(
                target_url=url,
                output_dir_path=OUTPUT_DIR_PATH,
                extension_dir=EXTENSION_DIR,
                user_data_dir=USER_DATA_DIR,
                temp_root_dir=TEMP_ROOT_DIR,
                thumbnail_url=None
            )
            all_results.append(result)

        print("\n--- SmartFrame Image Download Summary ---")
        headers = ["Original URL", "Image ID", "Status", "Output Filename", "Error Message"]
        table_data = []
        for res in all_results:
            table_data.append([
                res.get("Original URL", "N/A"),
                res.get("Image ID", "N/A"),
                res.get("Status", "N/A"),
                res.get("Output Filename", "N/A"),
                res.get("Error Message", "N/A")
            ])
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        print(f"\nDownloaded images saved to: {os.path.abspath(OUTPUT_DIR_PATH)}")

        failed_report_written = write_failed_download_report(all_results, FAILED_DOWNLOADS_PATH)
        if failed_report_written:
            print(f"Failed download report: {FAILED_DOWNLOADS_PATH.resolve()}")
    except Exception as exc:
        logger.critical(f"Unrecoverable error in main execution: {exc}", exc_info=True)
        if not failed_report_written:
            failed_report_written = write_failed_download_report(all_results, FAILED_DOWNLOADS_PATH)
        raise
    finally:
        cleanup_temp_dirs(USER_DATA_DIR, EXTENSION_DIR)
        
        if TEMP_ROOT_DIR.exists():
            shutil.rmtree(TEMP_ROOT_DIR)
            logger.info(f"Cleaned up temporary directory: {TEMP_ROOT_DIR.absolute()}")

        if not failed_report_written and not FAILED_DOWNLOADS_PATH.exists():
            write_failed_download_report(all_results, FAILED_DOWNLOADS_PATH)

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_main_script())

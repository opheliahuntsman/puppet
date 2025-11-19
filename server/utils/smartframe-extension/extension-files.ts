/**
 * SmartFrame Canvas Extractor Chrome Extension
 * Ported from Python smartframe_extractor.py
 * 
 * This module contains the Chrome extension files (manifest.json, background.js, content_script.js)
 * and injected JavaScript needed to extract canvas images from SmartFrame embeds.
 */

export const MANIFEST_JSON = {
  manifest_version: 3,
  name: "Canvas Data Extractor",
  version: "2.0",
  description: "Extracts data from a canvas, bypassing taint restrictions (Manifest V3).",
  permissions: ["scripting"],
  host_permissions: ["<all_urls>"],
  background: {
    service_worker: "background.js"
  },
  content_scripts: [
    {
      matches: ["<all_urls>"],
      js: ["content_script.js"],
      run_at: "document_start"
    }
  ],
  web_accessible_resources: [
    {
      resources: ["*"],
      matches: ["<all_urls>"]
    }
  ]
};

export const BACKGROUND_JS = `
console.log("Canvas Extractor V3: Service Worker loaded.");

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log("Canvas Extractor V3: Message received in service worker.", request);
  
  if (request.action === "getCanvasDataURL") {
    console.log(\`Canvas Extractor V3: Executing script in tab \${sender.tab.id} to get canvas data.\`);
    
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
            selectorsToTry.push(\`smartframe-embed[image-id="\${window.__SMARTFRAME_TARGET_IMAGE_ID}"]\`);
          }
          selectorsToTry.push('smartframe-embed:not([thumbnail-mode])');
          selectorsToTry.push('smartframe-embed');

          let smartframeEmbed = null;
          for (const candidateSelector of selectorsToTry) {
            try {
              const candidate = document.querySelector(candidateSelector);
              if (candidate) {
                smartframeEmbed = candidate;
                console.log(\`Canvas Extractor [Privileged]: smartframe-embed resolved via selector '\${candidateSelector}'.\`);
                break;
              }
            } catch (err) {
              console.warn(\`Canvas Extractor [Privileged]: Selector '\${candidateSelector}' threw an error:\`, err);
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
              console.log(\`Canvas Extractor [Privileged]: Search attempt \${attempts}/\${maxAttempts}\`);
              
              let canvas = null;
              
              // First, try to use the captured shadow root from window object
              if (window.__smartFrameShadowRoot) {
                console.log('Canvas Extractor [Privileged]: Checking captured shadow root...');
                const allCanvases = window.__smartFrameShadowRoot.querySelectorAll('canvas');
                console.log(\`Canvas Extractor [Privileged]: Found \${allCanvases.length} canvas element(s) in captured shadowRoot\`);
                
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
                  console.log(\`Canvas Extractor [Privileged]: Found \${allCanvases.length} canvas element(s) in direct shadowRoot\`);
                  
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
                console.log(\`Canvas Extractor [Privileged]: Found \${allCanvases.length} canvas element(s) in document\`);
                
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
                console.log(\`Canvas Extractor [Privileged]: Canvas found on attempt \${attempts}. Width: \${canvas.width}, Height: \${canvas.height}\`);
                resolve(canvas);
              } else if (attempts < maxAttempts) {
                console.log(\`Canvas Extractor [Privileged]: Canvas not found, retrying in \${delay}ms...\`);
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
`;

export const CONTENT_SCRIPT_JS = `
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

    console.log(\`Canvas Extractor V3 [Content]: Sending message to service worker for selector: \${selector}\`);
    
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
        console.error(\`Canvas Extractor V3 [Content]: Error received from service worker: \${errorMsg}\`);
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
`;

export const INJECTED_JAVASCRIPT = `
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
                      console.log(\`Injected JavaScript (Main Page): Shadow root has \${canvases.length} canvas element(s) initially.\`);
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
              selectorsToTry.push(\`smartframe-embed[image-id="\${smartframeTargetImageId}"]\`);
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
                      console.log(\`Injected JavaScript (Main Page): SmartFrame candidate found via selector '\${selector}'.\`);
                      return { element: candidate, selector };
                  }
              } catch (err) {
                  console.warn(\`Injected JavaScript (Main Page): Selector '\${selector}' threw an error:\`, err);
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
                console.log(\`Injected JavaScript (Main Page): SmartFrame container dimensions set to \${widthValue} x \${heightValue} from CSS vars.\`);
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
`;

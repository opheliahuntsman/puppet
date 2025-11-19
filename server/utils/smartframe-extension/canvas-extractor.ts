import { Page } from 'puppeteer';
import fs from 'fs';
import path from 'path';
import { INJECTED_JAVASCRIPT } from './extension-files';

/**
 * SmartFrame Canvas Image Extractor
 * Handles extraction of full-resolution canvas images from SmartFrame embeds
 */
export class SmartFrameCanvasExtractor {
  /**
   * Extract canvas image from SmartFrame embed
   * @param page - Puppeteer page instance
   * @param imageId - SmartFrame image ID
   * @param outputDir - Directory to save extracted images
   * @param viewportMode - Viewport mode: "full" (9999x9999) or "thumbnail" (600x600)
   * @returns Path to extracted image file, or null if extraction failed
   */
  async extractCanvasImage(
    page: Page,
    imageId: string,
    outputDir: string,
    viewportMode: 'full' | 'thumbnail' = 'thumbnail'
  ): Promise<string | null> {
    console.log(`[SmartFrame Canvas] Extracting canvas image for ${imageId} in ${viewportMode} mode`);

    try {
      // Inject the SmartFrame extraction JavaScript
      const smartframeEmbedSelector = `smartframe-embed[image-id="${imageId}"]`;
      const initScript = `
        window.__SMARTFRAME_EMBED_SELECTOR = ${JSON.stringify(smartframeEmbedSelector)};
        window.__SMARTFRAME_TARGET_IMAGE_ID = ${JSON.stringify(imageId)};
      `;
      
      await page.evaluate(initScript);
      await page.evaluate(INJECTED_JAVASCRIPT);
      console.log('[SmartFrame Canvas] Injected extraction JavaScript');

      // Wait for the extension response
      const responseSelector = '#extension-response-data';
      console.log('[SmartFrame Canvas] Waiting for canvas extraction...');

      await page.waitForSelector(
        `${responseSelector}[data-url], ${responseSelector}[data-error]`,
        { timeout: 120000 } // 2 minutes timeout for large canvas rendering
      );

      // Get the data URL or error
      const imageDataUrl = await page.$eval(
        responseSelector,
        (el) => el.getAttribute('data-url')
      );
      const errorFromExtension = await page.$eval(
        responseSelector,
        (el) => el.getAttribute('data-error')
      );

      if (errorFromExtension) {
        console.error(`[SmartFrame Canvas] Extension error: ${errorFromExtension}`);
        return null;
      }

      if (!imageDataUrl || !imageDataUrl.startsWith('data:image/png;base64,')) {
        console.error('[SmartFrame Canvas] No valid canvas data URL received');
        return null;
      }

      // Extract base64 data
      const base64Data = imageDataUrl.split(',')[1];
      const imageBuffer = Buffer.from(base64Data, 'base64');

      // Save as PNG
      const sanitizedId = imageId.replace(/[^a-zA-Z0-9.\-_]/g, '-');
      const pngFilename = `${sanitizedId}_canvas_${viewportMode}.png`;
      const pngPath = path.join(outputDir, pngFilename);

      fs.writeFileSync(pngPath, imageBuffer);
      console.log(`[SmartFrame Canvas] Saved canvas image: ${pngPath}`);

      return pngPath;
    } catch (error) {
      console.error(`[SmartFrame Canvas] Error extracting canvas:`, error);
      return null;
    }
  }

  /**
   * Convert PNG to JPG (optional, for compatibility)
   * Note: This would require an image processing library like sharp
   * For now, we'll just return the PNG path
   */
  async convertToJpg(pngPath: string): Promise<string | null> {
    // TODO: Implement PNG to JPG conversion using sharp or similar library
    // For now, return the PNG path as-is
    console.log('[SmartFrame Canvas] PNG to JPG conversion not yet implemented, returning PNG');
    return pngPath;
  }
}

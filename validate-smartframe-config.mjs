#!/usr/bin/env node
/**
 * SmartFrame Canvas Extraction - Validation Script
 * 
 * This script validates that the SmartFrame canvas extraction integration
 * is properly configured and ready to use.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('🔍 SmartFrame Canvas Extraction - Configuration Validator\n');

// Check if scraper.config.json exists
const configPath = path.join(process.cwd(), 'scraper.config.json');
if (!fs.existsSync(configPath)) {
  console.error('❌ Error: scraper.config.json not found');
  process.exit(1);
}

console.log('✓ Configuration file found');

// Load configuration
let config;
try {
  const configData = fs.readFileSync(configPath, 'utf-8');
  config = JSON.parse(configData);
  console.log('✓ Configuration loaded successfully');
} catch (error) {
  console.error('❌ Error parsing scraper.config.json:', error.message);
  process.exit(1);
}

// Validate SmartFrame configuration
console.log('\n📋 SmartFrame Configuration:');

if (!config.smartframe) {
  console.log('⚠️  Warning: "smartframe" section not found in config');
  console.log('   Canvas extraction is disabled by default');
} else {
  const sf = config.smartframe;
  
  console.log(`  extractFullImages: ${sf.extractFullImages || false}`);
  console.log(`  viewportMode: ${sf.viewportMode || 'thumbnail'}`);
  console.log(`  headless: ${sf.headless !== undefined ? sf.headless : false}`);
  console.log(`  renderTimeout: ${sf.renderTimeout || 5000}ms`);
  
  if (sf.viewportSizes) {
    console.log(`  Viewport Sizes:`);
    if (sf.viewportSizes.full) {
      console.log(`    full: ${sf.viewportSizes.full.width}x${sf.viewportSizes.full.height}`);
    }
    if (sf.viewportSizes.thumbnail) {
      console.log(`    thumbnail: ${sf.viewportSizes.thumbnail.width}x${sf.viewportSizes.thumbnail.height}`);
    }
  }
  
  // Validate configuration
  console.log('\n🔧 Validation Results:');
  
  if (sf.extractFullImages) {
    if (sf.headless !== false) {
      console.log('  ⚠️  Warning: Canvas extraction requires headless=false');
      console.log('     The browser must be visible for canvas rendering');
    } else {
      console.log('  ✓ Browser will run in non-headless mode (required)');
    }
    
    const mode = sf.viewportMode || 'thumbnail';
    if (mode !== 'full' && mode !== 'thumbnail') {
      console.log(`  ⚠️  Warning: Invalid viewportMode "${mode}"`);
      console.log('     Valid options: "full" or "thumbnail"');
    } else {
      console.log(`  ✓ Viewport mode: ${mode}`);
    }
    
    console.log('  ✓ Canvas extraction is enabled');
  } else {
    console.log('  ℹ️  Canvas extraction is disabled');
    console.log('     Set extractFullImages: true to enable');
  }
}

// Check if output directory will be created
console.log('\n📁 Output Configuration:');
const outputDir = path.join(process.cwd(), 'downloaded_images');
if (fs.existsSync(outputDir)) {
  console.log(`  ✓ Output directory exists: ${outputDir}`);
} else {
  console.log(`  ℹ️  Output directory will be created: ${outputDir}`);
}

// Check extension files
console.log('\n🔌 Extension Files:');
const extensionPath = path.join(
  process.cwd(),
  'server/utils/smartframe-extension'
);

const extensionFiles = [
  'extension-files.ts',
  'extension-manager.ts',
  'canvas-extractor.ts',
  'index.ts'
];

let allFilesExist = true;
for (const file of extensionFiles) {
  const filePath = path.join(extensionPath, file);
  if (fs.existsSync(filePath)) {
    console.log(`  ✓ ${file}`);
  } else {
    console.log(`  ❌ ${file} - NOT FOUND`);
    allFilesExist = false;
  }
}

// Final summary
console.log('\n' + '='.repeat(60));
if (allFilesExist) {
  console.log('✅ SmartFrame canvas extraction is properly installed');
  
  if (config.smartframe?.extractFullImages) {
    console.log('\n🎨 Canvas extraction is ENABLED');
    console.log(`   Mode: ${config.smartframe.viewportMode || 'thumbnail'}`);
    console.log(`   Browser visibility: ${config.smartframe.headless === false ? 'VISIBLE (required)' : 'HEADLESS (will not work!)'}`);
  } else {
    console.log('\nℹ️  Canvas extraction is currently DISABLED');
    console.log('   To enable, update scraper.config.json:');
    console.log('   {');
    console.log('     "smartframe": {');
    console.log('       "extractFullImages": true,');
    console.log('       "viewportMode": "full",');
    console.log('       "headless": false');
    console.log('     }');
    console.log('   }');
  }
} else {
  console.log('❌ Some extension files are missing');
  console.log('   Please ensure the installation is complete');
}
console.log('='.repeat(60));

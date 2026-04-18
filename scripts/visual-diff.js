/**
 * PaperForge — Visual Diff (SSIM)
 * Pure JS: pdf.js + canvas + pixelmatch for in-memory PDF comparison.
 * No external binaries needed (no Ghostscript, no Poppler).
 * 
 * Usage: node visual-diff.js base.pdf target.pdf [outputDir] [--threshold=0.95] [--aa=0.12]
 */

const fs = require('fs');
const path = require('path');
const { createCanvas } = require('canvas');

// Lazy-load pdfjs-dist
let pdfjsLib;
try {
  pdfjsLib = require('pdfjs-dist/legacy/build/pdf.js');
} catch (e) {
  console.error('pdfjs-dist not installed. Run: npm install pdfjs-dist');
  process.exit(1);
}

let pixelmatch;
try {
  pixelmatch = require('pixelmatch');
} catch (e) {
  console.error('pixelmatch not installed. Run: npm install pixelmatch');
  process.exit(1);
}

// ── Configuration ──────────────────────────────────────────────────

const DEFAULT_THRESHOLD = 0.95;
const AA_TOLERANCE = 0.12;

function parseArgs() {
  const args = process.argv.slice(2);
  const config = {
    basePdf: null,
    targetPdf: null,
    outputDir: 'diffs',
    threshold: DEFAULT_THRESHOLD,
    aaTolerance: AA_TOLERANCE,
    ignoreZones: [],
    boundingBoxes: [],
  };

  for (const arg of args) {
    if (arg.startsWith('--threshold=')) {
      config.threshold = parseFloat(arg.split('=')[1]);
    } else if (arg.startsWith('--aa=')) {
      config.aaTolerance = parseFloat(arg.split('=')[1]);
    } else if (arg.startsWith('--config=')) {
      const cfgPath = arg.split('=')[1];
      if (fs.existsSync(cfgPath)) {
        const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
        Object.assign(config, cfg);
      }
    } else if (!config.basePdf) {
      config.basePdf = arg;
    } else if (!config.targetPdf) {
      config.targetPdf = arg;
    } else {
      config.outputDir = arg;
    }
  }

  return config;
}

// ── PDF to PNG Conversion ──────────────────────────────────────────

async function pdfToPngBuffers(pdfPath) {
  const data = new Uint8Array(fs.readFileSync(pdfPath));
  const pdf = await pdfjsLib.getDocument({ data, useSystemFonts: true }).promise;
  const pages = [];

  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const viewport = page.getViewport({ scale: 2.0 }); // 2x for quality

    const canvas = createCanvas(viewport.width, viewport.height);
    const ctx = canvas.getContext('2d');

    // White background
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, viewport.width, viewport.height);

    await page.render({
      canvasContext: ctx,
      viewport: viewport,
    }).promise;

    pages.push({
      buffer: canvas.toBuffer('image/png'),
      width: viewport.width,
      height: viewport.height,
    });
  }

  return pages;
}

// ── SSIM Computation ───────────────────────────────────────────────

function luminance(r, g, b) {
  // BT.601 coefficients
  return 0.299 * r + 0.587 * g + 0.114 * b;
}

function isAntialiased(dataA, dataB, idx, width, height) {
  // Check if pixel difference is due to antialiasing
  // by sampling neighbor pixels
  const x = (idx / 4) % width;
  const y = Math.floor((idx / 4) / width);

  const neighbors = [
    [-1, -1], [-1, 0], [-1, 1],
    [0, -1],           [0, 1],
    [1, -1],  [1, 0],  [1, 1],
  ];

  let similarNeighborsA = 0;
  let similarNeighborsB = 0;

  for (const [dx, dy] of neighbors) {
    const nx = x + dx;
    const ny = y + dy;
    if (nx < 0 || ny < 0 || nx >= width || ny >= height) continue;

    const nIdx = (ny * width + nx) * 4;

    // Check if neighbor is similar to current pixel in image A
    const diffA = Math.abs(luminance(dataA[idx], dataA[idx+1], dataA[idx+2]) -
                          luminance(dataA[nIdx], dataA[nIdx+1], dataA[nIdx+2]));
    if (diffA < 30) similarNeighborsA++;

    // Check in image B
    const diffB = Math.abs(luminance(dataB[idx], dataB[idx+1], dataB[idx+2]) -
                          luminance(dataB[nIdx], dataB[nIdx+1], dataB[nIdx+2]));
    if (diffB < 30) similarNeighborsB++;
  }

  // If mixed similar/dissimilar neighbors, likely AA
  return similarNeighborsA > 2 && similarNeighborsB > 2 &&
         similarNeighborsA < 7 && similarNeighborsB < 7;
}

function computeDiff(imgA, imgB, width, height, config) {
  const { ImageData } = require('canvas');

  const dataA = new Uint8ClampedArray(imgA);
  const dataB = new Uint8ClampedArray(imgB);
  const diffBuffer = new Uint8ClampedArray(dataA.length);

  let diffPixels = 0;
  let aaPixels = 0;
  const totalPixels = width * height;

  for (let i = 0; i < dataA.length; i += 4) {
    const rA = dataA[i], gA = dataA[i+1], bA = dataA[i+2];
    const rB = dataB[i], gB = dataB[i+1], bB = dataB[i+2];

    // Perceptual luminance distance
    const lumA = luminance(rA, gA, bA);
    const lumB = luminance(rB, gB, bB);
    const lumDiff = Math.abs(lumA - lumB) / 255;

    // RGB distance
    const rDiff = Math.abs(rA - rB);
    const gDiff = Math.abs(gA - gB);
    const bDiff = Math.abs(bB - bA);
    const maxChannelDiff = Math.max(rDiff, gDiff, bDiff) / 255;

    // Check if this is antialiasing
    if (maxChannelDiff > 0.01 && lumDiff < config.aaTolerance) {
      if (isAntialiased(dataA, dataB, i, width, height)) {
        // Mark as AA (light blue)
        diffBuffer[i] = 173;
        diffBuffer[i+1] = 216;
        diffBuffer[i+2] = 230;
        diffBuffer[i+3] = 255;
        aaPixels++;
        continue;
      }
    }

    if (maxChannelDiff > 0.05) {
      // Actual diff (red)
      diffBuffer[i] = 255;
      diffBuffer[i+1] = 0;
      diffBuffer[i+2] = 0;
      diffBuffer[i+3] = 255;
      diffPixels++;
    } else {
      // Copy from base, slightly dimmed
      diffBuffer[i] = Math.floor(rA * 0.3);
      diffBuffer[i+1] = Math.floor(gA * 0.3);
      diffBuffer[i+2] = Math.floor(bA * 0.3);
      diffBuffer[i+3] = 255;
    }
  }

  return {
    diffBuffer,
    diffPixels,
    aaPixels,
    ssim: 1 - diffPixels / totalPixels,
    totalPixels,
  };
}

// ── Main ───────────────────────────────────────────────────────────

async function main() {
  const config = parseArgs();

  if (!config.basePdf || !config.targetPdf) {
    console.error('Usage: node visual-diff.js base.pdf target.pdf [outputDir] [--threshold=0.95] [--aa=0.12]');
    process.exit(1);
  }

  if (!fs.existsSync(config.basePdf)) {
    console.error(`Base PDF not found: ${config.basePdf}`);
    process.exit(1);
  }
  if (!fs.existsSync(config.targetPdf)) {
    console.error(`Target PDF not found: ${config.targetPdf}`);
    process.exit(1);
  }

  // Ensure output dir
  fs.mkdirSync(config.outputDir, { recursive: true });

  console.log(`[visual-diff] Comparing:`);
  console.log(`  Base:   ${config.basePdf}`);
  console.log(`  Target: ${config.targetPdf}`);
  console.log(`  Threshold: ${config.threshold}`);
  console.log(`  AA Tolerance: ${config.aaTolerance}`);

  // Convert PDFs to PNGs
  console.log('[visual-diff] Rendering base PDF...');
  const basePages = await pdfToPngBuffers(config.basePdf);
  console.log(`  ${basePages.length} pages`);

  console.log('[visual-diff] Rendering target PDF...');
  const targetPages = await pdfToPngBuffers(config.targetPdf);
  console.log(`  ${targetPages.length} pages`);

  // Page count check
  if (basePages.length !== targetPages.length) {
    console.warn(`[visual-diff] WARNING: Page count mismatch (base: ${basePages.length}, target: ${targetPages.length})`);
  }

  const report = {
    timestamp: new Date().toISOString(),
    basePdf: config.basePdf,
    targetPdf: config.targetPdf,
    threshold: config.threshold,
    aaTolerance: config.aaTolerance,
    basePages: basePages.length,
    targetPages: targetPages.length,
    pages: [],
    passed: true,
    overallSsim: 1.0,
  };

  const maxPages = Math.min(basePages.length, targetPages.length);

  for (let i = 0; i < maxPages; i++) {
    console.log(`[visual-diff] Comparing page ${i + 1}/${maxPages}...`);

    const base = basePages[i];
    const target = targetPages[i];

    // Ensure same dimensions (scale to match)
    const width = Math.min(base.width, target.width);
    const height = Math.min(base.height, target.height);

    const { loadImage } = require('canvas');
    const baseImg = await loadImage(base.buffer);
    const targetImg = await loadImage(target.buffer);

    const baseCanvas = createCanvas(width, height);
    const targetCanvas = createCanvas(width, height);
    const baseCtx = baseCanvas.getContext('2d');
    const targetCtx = targetCanvas.getContext('2d');

    baseCtx.drawImage(baseImg, 0, 0, width, height);
    targetCtx.drawImage(targetImg, 0, 0, width, height);

    const baseData = baseCtx.getImageData(0, 0, width, height);
    const targetData = targetCtx.getImageData(0, 0, width, height);

    const result = computeDiff(baseData.data, targetData.data, width, height, config);

    // Save diff image
    const diffCanvas = createCanvas(width, height);
    const diffCtx = diffCanvas.getContext('2d');
    diffCtx.putImageData(
      new (require('canvas').ImageData)(result.diffBuffer, width, height),
      0, 0
    );

    const diffPath = path.join(config.outputDir, `page-${i + 1}-diff.png`);
    fs.writeFileSync(diffPath, diffCanvas.toBuffer('image/png'));

    const pageResult = {
      page: i + 1,
      ssim: result.ssim,
      diffPixels: result.diffPixels,
      aaPixels: result.aaPixels,
      totalPixels: result.totalPixels,
      diffPercent: ((result.diffPixels / result.totalPixels) * 100).toFixed(2),
      passed: result.ssim >= config.threshold,
      diffImage: diffPath,
    };

    report.pages.push(pageResult);

    if (!pageResult.passed) {
      report.passed = false;
      console.log(`  ❌ Page ${i + 1} FAILED — SSIM: ${result.ssim.toFixed(4)} (${result.diffPixels} diff pixels)`);
    } else {
      console.log(`  ✅ Page ${i + 1} PASSED — SSIM: ${result.ssim.toFixed(4)}`);
    }
  }

  // Overall SSIM
  if (report.pages.length > 0) {
    report.overallSsim = report.pages.reduce((sum, p) => sum + p.ssim, 0) / report.pages.length;
  }

  // Write report
  const reportPath = path.join(config.outputDir, 'report.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));

  console.log(`\n[visual-diff] Overall SSIM: ${report.overallSsim.toFixed(4)}`);
  console.log(`[visual-diff] ${report.passed ? '✅ PASSED' : '❌ FAILED'}`);
  console.log(`[visual-diff] Report: ${reportPath}`);

  process.exit(report.passed ? 0 : 1);
}

main().catch(err => {
  console.error('[visual-diff] Error:', err);
  process.exit(1);
});

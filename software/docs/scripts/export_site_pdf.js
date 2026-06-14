#!/usr/bin/env node
/**
 * Render a Sphinx singlehtml build to a print-ready PDF via headless Chromium.
 *
 * Usage:
 *   node scripts/export_site_pdf.js <input.html> <output.pdf>
 *
 * Requires: npm ci in software/docs (puppeteer via @mermaid-js/mermaid-cli).
 */
'use strict';

const fs = require('fs');
const path = require('path');

async function resolvePuppeteer(docsDir) {
  try {
    return require('puppeteer');
  } catch (_) {
    /* mermaid-cli bundles puppeteer; fall back to that install tree. */
    const nested = path.join(
      docsDir,
      'node_modules',
      '@mermaid-js',
      'mermaid-cli',
      'node_modules',
      'puppeteer',
    );
    return require(nested);
  }
}

async function waitForMermaid(page, timeoutMs) {
  await page.waitForFunction(
    () => {
      const blocks = document.querySelectorAll('.mermaid, pre.mermaid');
      if (blocks.length === 0) {
        return true;
      }
      return [...blocks].every((el) => {
        if (el.getAttribute('data-processed') === 'true') {
          return true;
        }
        return el.querySelector('svg') !== null;
      });
    },
    { timeout: timeoutMs },
  );
}

async function main() {
  const htmlArg = process.argv[2];
  const pdfArg = process.argv[3];
  if (!htmlArg || !pdfArg) {
    console.error('Usage: node export_site_pdf.js <input.html> <output.pdf>');
    process.exit(1);
  }

  const htmlPath = path.resolve(htmlArg);
  const pdfPath = path.resolve(pdfArg);
  const docsDir = path.resolve(__dirname, '..');
  const puppeteerCfg = path.join(docsDir, 'puppeteer-config.json');

  if (!fs.existsSync(htmlPath)) {
    console.error(`[export_site_pdf] HTML not found: ${htmlPath}`);
    process.exit(1);
  }

  const puppeteer = await resolvePuppeteer(docsDir);
  const launchOpts = { headless: true };
  if (fs.existsSync(puppeteerCfg)) {
    launchOpts.args = JSON.parse(fs.readFileSync(puppeteerCfg, 'utf8')).args;
  }

  fs.mkdirSync(path.dirname(pdfPath), { recursive: true });

  const browser = await puppeteer.launch(launchOpts);
  try {
    const page = await browser.newPage();
    await page.emulateMediaType('print');
    await page.goto(`file://${htmlPath}`, { waitUntil: 'networkidle0', timeout: 120_000 });
    await waitForMermaid(page, 60_000);

    await page.pdf({
      path: pdfPath,
      format: 'Letter',
      printBackground: true,
      margin: { top: '0.65in', right: '0.65in', bottom: '0.75in', left: '0.65in' },
      displayHeaderFooter: true,
      headerTemplate: '<span></span>',
      footerTemplate:
        '<div style="width:100%;font-size:8px;color:#666;text-align:center;padding:0 0.5in;">'
        + '<span>Fishing Robot ROS 2 Codebase</span>'
        + ' · <span class="pageNumber"></span> / <span class="totalPages"></span>'
        + '</div>',
    });

    const stat = fs.statSync(pdfPath);
    console.log(
      `[export_site_pdf] Wrote ${pdfPath} (${(stat.size / 1024 / 1024).toFixed(2)} MiB)`,
    );
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error('[export_site_pdf] Failed:', err.message);
  process.exit(1);
});

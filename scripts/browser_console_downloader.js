/**
 * ═══════════════════════════════════════════════════════════════════
 *  TARANG PHARMA — RECEIPT BULK DOWNLOADER  v4  (Final)
 *  File : browser_console_downloader.js
 *
 *  HOW TO RUN
 *  ──────────
 *  1. Open the task page on atslite.interviewgod.ai.
 *  2. Expand the "467 photos" section so photo buttons are visible.
 *  3. Press F12 → Console tab.
 *  4. Paste this entire script → press Enter.
 *  5. Answer the confirmation prompt → all 467 downloads begin.
 *
 *  ROOT CAUSE (v1–v3 bug)
 *  ──────────────────────
 *  All 467 buttons ARE in the DOM (no virtualisation).
 *  Previous versions used regex /IMG[-_]\d{8}[-_]WA\d{4,}/i which
 *  required "WA" in the filename — only matching the 130 WhatsApp
 *  photos (IMG-YYYYMMDD-WAxxxx.jpg).
 *  The other 337 are camera photos (IMG_YYYYMMDD_xxxxxx.jpg) with
 *  no "WA" — silently skipped every time.
 *  Fix: match any button inside the photo UL whose text contains
 *  "images/" — covers BOTH filename formats.
 * ═══════════════════════════════════════════════════════════════════
 */

(async () => {
  'use strict';

  // ── Config ────────────────────────────────────────────────────────
  const CFG = {
    EXPECTED_TOTAL  : 467,
    CLICK_DELAY_MS  : 800,   // gap between button clicks
    BATCH_SIZE      : 25,    // clicks before a longer pause
    BATCH_PAUSE_MS  : 1500,  // longer pause every BATCH_SIZE clicks
  };

  const sleep = ms => new Promise(r => setTimeout(r, ms));

  const log = {
    ok   : m => console.log(`%c✅ ${m}`, 'color:#22c55e'),
    warn : m => console.warn(`⚠️  ${m}`),
    err  : m => console.error(`❌ ${m}`),
    info : m => console.log(`▸  ${m}`),
    head : m => console.log(`%c${m}`, 'font-weight:bold;font-size:13px;color:#60a5fa'),
  };

  // ── Safety check ──────────────────────────────────────────────────
  log.head('═══════════════════════════════════════════════════════');
  log.head('  Tarang Pharma Distribution — Receipt Bulk Downloader ');
  log.head('              v4 — Final                               ');
  log.head('═══════════════════════════════════════════════════════');

  if (!location.hostname.includes('atslite.interviewgod.ai')) {
    log.err(`Wrong page. Expected atslite.interviewgod.ai, got: ${location.hostname}`);
    return;
  }

  // ── Find the photo list UL ─────────────────────────────────────────
  // Confirmed by diagnostic: <UL class="...overflow-y-auto...max-h-96...">
  // with 467 direct <li> children, all already in the DOM.
  const photoUL = Array.from(document.querySelectorAll('ul'))
    .filter(ul => {
      const cs = getComputedStyle(ul);
      return (
        (cs.overflowY === 'auto' || cs.overflow === 'auto') &&
        ul.scrollHeight > 1000 &&
        ul.querySelectorAll('button').length > 10
      );
    })
    .reduce((best, el) => el.scrollHeight > (best?.scrollHeight ?? 0) ? el : best, null);

  if (!photoUL) {
    log.err(
      'Could not find the photo list container.\n' +
      '• Is the "467 photos" section expanded?\n' +
      '• Is the page fully loaded?'
    );
    return;
  }

  // ── Collect ALL buttons — both filename formats ────────────────────
  //
  //  Format A (WhatsApp) : images/IMG-20260610-WA0001.jpg   ← 130 files
  //  Format B (Camera)   : images/IMG_20260807_213207.jpg   ← 337 files
  //
  //  Match: any button whose trimmed text starts with "images/"
  //  or ends with a common image extension.
  //
  function getAllReceiptButtons() {
    return Array.from(photoUL.querySelectorAll('button')).filter(btn => {
      const text = btn.textContent.trim();
      return (
        text.startsWith('images/') ||
        /\.(jpg|jpeg|png|gif|webp|bmp)$/i.test(text)
      );
    });
  }

  // Extract clean filename (strip leading "images/" folder prefix)
  function getFilename(btn) {
    const text = btn.textContent.trim();
    // Remove path prefix if present (e.g. "images/IMG_..." → "IMG_...")
    return text.replace(/^[^/]+\//, '').trim() || text;
  }

  const allButtons   = getAllReceiptButtons();
  const uniqueCount  = allButtons.length;

  log.info(`Photo list UL: ${photoUL.querySelectorAll('button').length} total buttons`);
  log.info(`Matching receipt buttons: ${uniqueCount}`);

  if (uniqueCount === 0) {
    log.err(
      'No receipt buttons found.\n' +
      '• Expand the "467 photos" section first.\n' +
      '• Make sure the page is fully loaded.'
    );
    return;
  }

  // Preview
  log.info(`First : ${getFilename(allButtons[0])}`);
  log.info(`Last  : ${getFilename(allButtons[allButtons.length - 1])}`);

  // ── Confirm ───────────────────────────────────────────────────────
  const confirmed = confirm(
    `Tarang Pharma Receipt Downloader  (v4)\n` +
    `${'─'.repeat(42)}\n` +
    `Receipt buttons found : ${uniqueCount} / ${CFG.EXPECTED_TOTAL}\n\n` +
    `Format A (WhatsApp)  : IMG-YYYYMMDD-WAxxxx.jpg\n` +
    `Format B (Camera)    : IMG_YYYYMMDD_xxxxxx.jpg\n` +
    `Both formats included ✓\n\n` +
    `Files save to your Downloads folder.\n` +
    `No data is submitted or modified.\n\n` +
    `Click OK to begin, or Cancel to abort.`
  );

  if (!confirmed) {
    log.info('Cancelled. Nothing was downloaded.');
    return;
  }

  // ── Click all buttons sequentially ───────────────────────────────
  log.head(`\n── Downloading ${uniqueCount} receipts ──`);

  const processed = new Set();
  let success     = 0;
  let failed      = 0;
  let batchCount  = 0;

  for (let i = 0; i < allButtons.length; i++) {
    const btn      = allButtons[i];
    const filename = getFilename(btn);

    // Skip exact duplicate filenames (safety guard)
    if (processed.has(filename)) {
      log.warn(`[${i+1}/${uniqueCount}] Duplicate skipped: ${filename}`);
      continue;
    }
    processed.add(filename);

    try {
      btn.click();
      success++;
      batchCount++;
      log.ok(`[${success}/${uniqueCount}] ${filename}`);
    } catch (err) {
      failed++;
      log.err(`[${i+1}/${uniqueCount}] ${filename} — ${err.message}`);
    }

    await sleep(CFG.CLICK_DELAY_MS);

    // Longer pause every BATCH_SIZE downloads (lets browser & server breathe)
    if (batchCount > 0 && batchCount % CFG.BATCH_SIZE === 0) {
      log.info(`── Batch of ${CFG.BATCH_SIZE} done. Pausing ${CFG.BATCH_PAUSE_MS}ms... ──`);
      await sleep(CFG.BATCH_PAUSE_MS);
    }
  }

  // ── Final report ──────────────────────────────────────────────────
  const divider = '═'.repeat(57);
  console.log(`\n${divider}`);
  console.log('  FINAL REPORT — Tarang Pharma Receipt Downloader v4');
  console.log(divider);
  console.log(`  Buttons found             : ${uniqueCount} / ${CFG.EXPECTED_TOTAL}`);
  console.log(`  ✅ Successfully clicked   : ${success}`);
  console.log(`  ❌ Errors                 : ${failed}`);
  console.log(`  ⏭  Duplicates skipped    : ${uniqueCount - success - failed}`);

  if (uniqueCount < CFG.EXPECTED_TOTAL) {
    console.log(
      `\n  ⚠  ${CFG.EXPECTED_TOTAL - uniqueCount} receipts were not found in the DOM.\n` +
      `     Make sure the "467 photos" section is fully expanded and try again.`
    );
  } else {
    console.log(`\n  🎉 All ${CFG.EXPECTED_TOTAL} receipts downloaded!`);
  }

  console.log(`\n  📁 Check your Downloads folder.`);
  console.log(divider);

})();

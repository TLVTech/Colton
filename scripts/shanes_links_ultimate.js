const puppeteer = require("puppeteer-core");
const fs = require("fs");

// ---------- CONFIG ----------
const BROWSER_WS =
  "wss://brd-customer-hl_7e560da0-zone-scraping_browser1:mq12dr9w27zb@brd.superproxy.io:9222";
const TARGET_URL =
  "https://www.shanesequipment.com/inventory/?/listings/search?ScopeCategoryIDs=27&Category=16013%7C16045&AccountCRMID=8589249&dlr=1&settingscrmid=5114963&lo=2";
const HOMEPAGE = "https://www.shanesequipment.com/";
const COOKIES_FILE = "scripts/shane_cookies.json"; // Only if you want to try cookie injection

// --- Helper: Load cookies from local export (from Chrome extension or DevTools) ---
async function maybeInjectCookies(page) {
  if (fs.existsSync(COOKIES_FILE)) {
    const cookies = JSON.parse(fs.readFileSync(COOKIES_FILE, "utf8"));
    try {
      await page.setCookie(...cookies);
      console.log(`[🍪] Injected ${cookies.length} cookies!`);
    } catch (e) {
      console.log(`[⚠️] Cookie injection error:`, e);
    }
  }
}

// --- Helper: Simulate more human activity ---
async function simulateHuman(page) {
  for (let i = 0; i < 6; i++) {
    await page.mouse.move(
      100 + Math.random() * 500,
      100 + Math.random() * 300,
      { steps: 5 }
    );
    await new Promise((r) => setTimeout(r, 700 + Math.random() * 1300));
    if (i % 2 === 0) {
      await page.mouse.click(
        150 + Math.random() * 300,
        120 + Math.random() * 150
      );
      await new Promise((r) => setTimeout(r, 500 + Math.random() * 1000));
    }
  }
  await page.keyboard.press("Tab");
  await new Promise((r) => setTimeout(r, 800));
  await page.keyboard.press("Tab");
  await new Promise((r) => setTimeout(r, 900));
  await page.evaluate(() => window.scrollBy(0, 400 + Math.random() * 600));
  await new Promise((r) => setTimeout(r, 1100 + Math.random() * 1200));
}

(async () => {
  console.log("[🌐] Connecting to Bright Data browser...");
  const browser = await puppeteer.connect({ browserWSEndpoint: BROWSER_WS });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  // 1. Go to homepage first to "build trust"
  await page.goto(HOMEPAGE, { waitUntil: "domcontentloaded", timeout: 60000 });
  console.log("[🏠] On homepage. Simulating human activity...");
  await simulateHuman(page);
  await maybeInjectCookies(page); // Only runs if you have cookies

  // 2. Now navigate to inventory/search page
  console.log("[➡️] Navigating to inventory page...");
  await page.goto(TARGET_URL, {
    waitUntil: "domcontentloaded",
    timeout: 120000,
  });

  // 3. Simulate more human activity on inventory page
  console.log("[🕹️] Simulating more human actions...");
  await simulateHuman(page);

  // 4. Wait for up to 2 minutes for the listContainer to appear
  console.log("[⏳] Waiting (up to 2min) for #listContainer...");
  let foundContainer = false;
  try {
    await page.waitForSelector("#listContainer", { timeout: 120000 });
    foundContainer = true;
  } catch (e) {
    console.log("[⚠️] #listContainer did not appear after 2min.");
  }

  // 5. Try to extract links (even if not found, in case of wrong timing)
  let links = [];
  if (foundContainer) {
    links = await page.$$eval('#listContainer a[href^="/inventory/"]', (as) =>
      Array.from(
        new Set(
          as.map(
            (a) => "https://www.shanesequipment.com" + a.getAttribute("href")
          )
        )
      )
    );
    console.log(`[✅] Found ${links.length} vehicle URLs!`);
    console.log(links);
  } else {
    console.log("[❌] No links extracted—dumping HTML for analysis...");
    const html = await page.content();
    fs.writeFileSync("shane_debug_blocked.html", html);
    console.log("[📄] Wrote debug HTML to shane_debug_blocked.html");
  }

  await browser.close();
})();

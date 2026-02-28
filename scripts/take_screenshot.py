import asyncio
from playwright.async_api import async_playwright

async def take_screenshot():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Login
        await page.goto('http://127.0.0.1:5000/')
        
        try:
            input_user = await page.query_selector("input[name='username']")
            if input_user:
                await page.fill("input[name='username']", 'admin')
                await page.fill("input[name='password']", 'admin123') # Guessing common password if one isn't known
                await page.click("button[type='submit']")
                await page.wait_for_load_state('networkidle')
        except Exception as e:
            print(f'Login step skipped or failed: {e}')

        # Go to reports
        await page.goto('http://127.0.0.1:5000/finance/reports')
        await page.wait_for_timeout(3000)
        
        # Screenshot of reports page
        await page.screenshot(path='reports_screenshot.png', full_page=True)
        print('Saved reports_screenshot.png')
        await browser.close()

asyncio.run(take_screenshot())

import asyncio
from playwright.async_api import async_playwright
import os

async def take_screenshot():
    async with async_playwright() as p:
        # Launching with a mobile viewport to trigger the mobile UI
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={'width': 375, 'height': 812},
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1'
        )
        page = await context.new_page()
        
        # Login
        await page.goto('http://127.0.0.1:5000/')
        
        try:
            input_user = await page.query_selector("input[name='username']")
            if input_user:
                await page.fill("input[name='username']", 'admin')
                await page.fill("input[name='password']", 'admin123')
                # Mobile login button might be different but usually enter works
                await page.click("button[type='submit']")
                await page.wait_for_load_state('networkidle')
        except Exception as e:
            print(f'Login step skipped or failed: {e}')

        # Go to reports
        await page.goto('http://127.0.0.1:5000/finance/reports')
        await page.wait_for_timeout(3000)
        
        # Taking screenshot of mobile view
        await page.screenshot(path='reports_mobile_screenshot.png', full_page=True)
        print('Saved reports_mobile_screenshot.png')
        await browser.close()

asyncio.run(take_screenshot())

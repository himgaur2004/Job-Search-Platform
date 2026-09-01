from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    
    page.goto("https://wellfound.com/jobs?q=software+engineer")
    with open("wellfound.html", "w") as f:
        f.write(page.content())
        
    browser.close()

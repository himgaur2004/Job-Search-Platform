from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    print("Fetching Indeed...")
    page.goto("https://www.indeed.com/jobs?q=software+engineer&l=remote&sort=date")
    print("Indeed Title:", page.title())
    print("Indeed Length:", len(page.content()))
    
    print("Fetching Glassdoor...")
    page.goto("https://www.glassdoor.com/Job/jobs.htm?sc.keyword=software%20engineer&locT=N&locId=0&jobType=all")
    print("Glassdoor Title:", page.title())
    print("Glassdoor Length:", len(page.content()))
    
    browser.close()

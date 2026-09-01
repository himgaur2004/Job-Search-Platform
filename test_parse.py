from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    
    page.goto("https://www.indeed.com/jobs?q=software+engineer&l=remote&sort=date")
    with open("indeed.html", "w") as f:
        f.write(page.content())
        
    page.goto("https://www.glassdoor.com/Job/jobs.htm?sc.keyword=software%20engineer&locT=N&locId=0&jobType=all")
    with open("glassdoor.html", "w") as f:
        f.write(page.content())
        
    browser.close()

from bs4 import BeautifulSoup

def parse_indeed():
    with open('indeed.html', 'r') as f:
        soup = BeautifulSoup(f.read(), 'lxml')
    cards = soup.select(".resultContent")
    for card in cards[:2]:
        title_tag = card.select_one("[id^='jobTitle'], .jobTitle")
        company_tag = card.select_one("[data-testid='company-name']")
        location_tag = card.select_one("[data-testid='text-location']")
        jk_node = card.select_one("[data-jk]")
        job_key = jk_node.get("data-jk", "") if jk_node else ""

        title = title_tag.get_text(strip=True) if title_tag else ""
        company = company_tag.get_text(strip=True) if company_tag else ""
        loc = location_tag.get_text(strip=True) if location_tag else ""
        job_url = f"https://www.indeed.com/viewjob?jk={job_key}" if job_key else ""
        
        print(f"title: {title!r}")
        print(f"company: {company!r}")
        print(f"url: {job_url!r}")

parse_indeed()

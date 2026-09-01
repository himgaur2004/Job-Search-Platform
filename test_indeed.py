from services.job_sources import _fetch_indeed, _get_html
from bs4 import BeautifulSoup

def test():
    url = "https://www.indeed.com/jobs?q=software+engineer&l=remote&sort=date"
    soup = _get_html(url)
    with open("indeed_fetch.html", "w") as f:
        f.write(soup.prettify())
    print("Cards:", len(soup.select(".resultContent")))
    res = _fetch_indeed("software engineer", "remote", 25)
    print("Jobs:", len(res.jobs))

test()

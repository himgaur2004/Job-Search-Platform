from bs4 import BeautifulSoup
import json

def parse_indeed():
    with open('indeed.html', 'r') as f:
        soup = BeautifulSoup(f.read(), 'lxml')
    cards = soup.select(".resultContent")
    print(f"Indeed cards: {len(cards)}")
    for card in cards[:2]:
        title = card.select_one("[id^='jobTitle'], .jobTitle").get_text(strip=True) if card.select_one("[id^='jobTitle'], .jobTitle") else ""
        company = card.select_one("[data-testid='company-name']").get_text(strip=True) if card.select_one("[data-testid='company-name']") else ""
        jk = card.select_one("[data-jk]").get("data-jk") if card.select_one("[data-jk]") else ""
        print(f" - {title} @ {company} (jk: {jk})")

parse_indeed()

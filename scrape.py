# scrape.py
import requests
from bs4 import BeautifulSoup
import re

URL = "https://tradelinesupply.com/pricing/"

def scrape_and_group_by_limit():
    resp = requests.get(URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.find_all("tr")

    buckets = {"0-2500": [], "2501-5000": [], "5001-10000": [], "10001+": []}

    for row in rows:
        try:
            product_td = row.find("td", class_="product_data")
            price_td = row.find("td", class_="product_price")
            if not product_td or not price_td:
                continue

            bank_name = (product_td.get("data-bankname") or "").strip()
            credit_limit_raw = (product_td.get("data-creditlimit") or "").strip().replace("$", "").replace(",", "")
            credit_limit = int(credit_limit_raw) if credit_limit_raw.isdigit() else 0
            date_opened = (product_td.get("data-dateopened") or "").strip()
            purchase_by = (product_td.get("data-purchasebydate") or "").strip()
            reporting_period = (product_td.get("data-reportingperiod") or "").strip()
            availability = (product_td.get("data-availability") or "").strip()

            price_text = price_td.get_text(strip=True)
            m = re.search(r"\$\s?(\d+(?:,\d{3})*(?:\.\d{2})?)", price_text)
            if not m:
                continue
            base_price = float(m.group(1).replace(",", ""))

            if base_price < 500:
                final_price = base_price + 100
            elif base_price <= 1000:
                final_price = base_price + 200
            else:
                final_price = base_price + 300

            item = {
                "buy_link": f"/buy?bank={bank_name}&price={final_price}",
                "bank": bank_name,
                "text": (
                    f"🏦 Bank: {bank_name}\n"
                    f"💳 Credit Limit: ${credit_limit:,}\n"
                    f"📅 Date Opened: {date_opened}\n"
                    f"🛒 Purchase Deadline: {purchase_by}\n"
                    f"📈 Reporting Period: {reporting_period}\n"
                    f"📦 Availability: {availability}\n"
                    f"💰 Price: ${final_price:,.2f}"
                ),
                "price": round(final_price, 2),
                "limit": credit_limit,
                "opened": date_opened,
                "deadline": purchase_by,
                "reporting": reporting_period,
                "availability": availability,
            }

            if credit_limit <= 2500:
                buckets["0-2500"].append(item)
            elif credit_limit <= 5000:
                buckets["2501-5000"].append(item)
            elif credit_limit <= 10000:
                buckets["5001-10000"].append(item)
            else:
                buckets["10001+"].append(item)

        except Exception:
            continue

    unique_banks = sorted({t["bank"] for b in buckets.values() for t in b if t["bank"]})
    years = sorted(
        {
            int(t["opened"].split()[0])
            for b in buckets.values()
            for t in b
            if t["opened"] and t["opened"].split()[0].isdigit()
        },
        reverse=True,
    )

    return buckets, unique_banks, years

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import pandas as pd
import requests

TELEGRAM_TOKEN = 'your token'
TELEGRAM_CHAT_ID = 'your id'

def calculate_avg_goals(results, team=1):
    goals = []
    for entry in results.split(" | "):
        try:
            score = entry.split("—")[1].strip().replace('\xa0', ' ')
            # Исправлено: используем ":" вместо "-" для разделения счета
            goals_pair = score.split(":")
            if len(goals_pair) == 2 and goals_pair[team - 1].strip().isdigit():
                goals.append(int(goals_pair[team - 1].strip()))
        except:
            continue
    return sum(goals) / len(goals) if goals else 0

options = Options()
options.add_argument('--headless')
options.add_argument('--start-maximized')
service = Service("I:/Downloads/bot 2.0/chromedriver.exe")
driver = webdriver.Chrome(service=service, options=options)

driver.get("https://www.betexplorer.com/soccer/")
time.sleep(3)

try:
    show_all = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Show all"))
    )
    show_all.click()
    time.sleep(5)
except Exception as e:
    print("Ошибка при клике 'Show all':", e)

try:
    upcoming = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "a#sCurrent"))
    )
    upcoming.click()
    time.sleep(4)
except Exception as e:
    print("Ошибка при открытии 'Upcoming':", e)

soup = BeautifulSoup(driver.page_source, 'html.parser')
match_urls = []
match_blocks = soup.select("li.table-main__tournamentLiContent[data-fro='0']")

for block in match_blocks:
    link_tag = block.select_one("a[href*='/football/']")
    if link_tag:
        href = link_tag.get("href")
        if href and href.startswith("/football/"):
            full_url = "https://www.betexplorer.com" + href
            match_urls.append(full_url)

all_data = []

total = len(match_urls)
for i, url in enumerate(match_urls, start=1):
    print(f"🔄 Обработка {i}/{total} ({(i/total)*100:.2f}%) — {url}")
    driver.get(url)
    time.sleep(3)
    match_soup = BeautifulSoup(driver.page_source, "html.parser")

    try:
        teams = [team.text.strip() for team in match_soup.select("ul.list-details .teamsLink")]
        h2h_matches = []
        for row in match_soup.select("div#mutual_div div.head-to-head__row")[:5]:
            date = row.select_one("div.head-to-head__date span").text.strip()
            score = row.select_one("div.mainResult").text.strip().replace('\xa0', ' ')
            h2h_matches.append(f"{date} — {score}")

        team1_results = []
        for row in match_soup.select("div#match-results-home div.head-to-head__row")[:5]:
            date = row.select_one("div.head-to-head__date span").text.strip()
            score = row.select_one("div.mainResult").text.strip().replace('\xa0', ' ')
            team1_results.append(f"{date} — {score}")

        team2_results = []
        for row in match_soup.select("div#match-results-away div.head-to-head__row")[:5]:
            date = row.select_one("div.head-to-head__date span").text.strip()
            score = row.select_one("div.mainResult").text.strip().replace('\xa0', ' ')
            team2_results.append(f"{date} — {score}")

        all_data.append({
            "Match URL": url,
            "Team 1": teams[0] if len(teams) > 0 else "",
            "Team 2": teams[1] if len(teams) > 1 else "",
            "H2H Last 5": " | ".join(h2h_matches),
            "Team 1 Last 5": " | ".join(team1_results),
            "Team 2 Last 5": " | ".join(team2_results),
        })
    except Exception as e:
        print(f"Ошибка при обработке матча {url}: {e}")

driver.quit()

df = pd.DataFrame(all_data)
df.to_csv("btts_combined_output.csv", index=False, encoding="utf-8-sig")

def calculate_btts_and_avg_goals(h2h_results):
    btts_count, total_goals, valid_matches = 0, 0, 0
    for result in h2h_results.split(" | "):
        parts = result.split("—")
        if len(parts) > 1:
            score = parts[1].strip()
            goals = score.replace(" ", "").split(":")
            if len(goals) == 2 and goals[0].isdigit() and goals[1].isdigit():
                g1, g2 = int(goals[0]), int(goals[1])
                total_goals += g1 + g2
                valid_matches += 1
                if g1 > 0 and g2 > 0:
                    btts_count += 1
    btts_percent = (btts_count / valid_matches * 100) if valid_matches else 0
    avg_goals = (total_goals / valid_matches) if valid_matches else 0
    return btts_percent, avg_goals

df["BTTS % (H2H)"], df["Avg Goals (H2H)"] = zip(*df["H2H Last 5"].apply(lambda x: calculate_btts_and_avg_goals(x)))

df["Team 1 Avg Goals"] = df["Team 1 Last 5"].apply(lambda results: calculate_avg_goals(results, team=1))
df["Team 2 Avg Goals"] = df["Team 2 Last 5"].apply(lambda results: calculate_avg_goals(results, team=2))

df["BTTS Score"] = (
    0.5 * df["BTTS % (H2H)"] +
    0.25 * df["Team 1 Avg Goals"] +
    0.25 * df["Team 2 Avg Goals"]
)

df["BTTS Rating"] = df["BTTS Score"].apply(lambda x: min(100, round(x * 10)))

top_5 = df.sort_values("BTTS Score", ascending=False).head(5)

message = "🔥 Топ 5 матчей на 'Обе забьют – Да':\n\n"
for i, row in top_5.iterrows():
    message += (
        f"⚽️ {row['Team 1']} vs {row['Team 2']}\n"
        f"📈 Рейтинг BTTS: {row['BTTS Rating']}/100\n"
        f"📊 BTTS в H2H: {row['BTTS % (H2H)']:.0f}% (ср. {row['Avg Goals (H2H)']:.2f} гола)\n"
        f"📉 Средние голы по последним матчам: {row['Team 1 Avg Goals']:.2f} / {row['Team 2 Avg Goals']:.2f}\n"
        f"🔗 Ссылка: {row['Match URL']}\n\n"
    )

try:
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    response = requests.post(send_url, data=payload)
    if response.status_code == 200:
        print("📩 Сообщение успешно отправлено в Telegram!")
    else:
        print("❌ Ошибка при отправке:", response.text)
except Exception as e:
    print("❌ Исключение при отправке:", e)

print(f"✅ Сохранено {len(all_data)} матчей в файл 'btts_combined_output.csv'")

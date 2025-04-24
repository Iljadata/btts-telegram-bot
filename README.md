# ⚽ BTTS Telegram Bot

A Python bot that analyzes football match statistics to find the best opportunities for **BTTS (Both Teams To Score – Yes)** bets. It collects data from [BetExplorer](https://www.betexplorer.com), processes recent games and head-to-head stats, and sends the top 5 matches with the highest BTTS potential directly to your Telegram channel.

---

## 🔍 Features

- Scrapes **all today's football matches** using Selenium + BeautifulSoup
- Analyzes:
  - Last 5 **head-to-head** (H2H) matches
  - Last 5 matches of **each team**
  - Goal stats and BTTS percentage
- Ranks matches by BTTS probability (custom score 1–100)
- Sends **daily summary** with links to BetExplorer in Telegram

---

## 💻 Installation

### 1. Clone the repo
bash
git clone https://github.com/Iljadata/btts-telegram-bot.git
cd btts-telegram-bot
2. Install dependencies
bash
Copy
Edit
pip install selenium beautifulsoup4 pandas requests python-dotenv
3. Download ChromeDriver
Ensure ChromeDriver version matches your Chrome browser:
👉 https://chromedriver.chromium.org/downloads

⚙️ Configuration
Create a .env file based on the example:

change in main telegram ID and token
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id
Donwload chromedriver.exe

🚀 Run the Bot
bash
Copy
Edit
python main.py
🧪 Telegram Output Example
java
Copy
Edit
🔥 Top 5 BTTS Matches Today:

⚽ Leganes vs Girona  
📊 BTTS %: 80%  
⚔️ Avg Goals (H2H): 3.2  
🔢 Avg Team Goals: 1.8 & 2.1  
🔗 https://www.betexplorer.com/...

...
🧑‍💻 Author
Created by Ilja Lomovcevs
Feel free to star ⭐ the project or contribute!

📄 License
This project is licensed under the MIT License.

yaml
Copy
Edit

---


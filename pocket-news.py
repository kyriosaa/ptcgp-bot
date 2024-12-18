import logging
from logging.handlers import RotatingFileHandler
import discord
from discord.ext import tasks, commands
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")  # Bot token
CHANNEL_ID = 1303516169810083850  # Discord channel ID
URL = "https://www.pokemon-zone.com/articles/"

# --- Logging Setup ---
log_file = "bot_activity.log"

# Create logger
logger = logging.getLogger("pocket-news")
logger.setLevel(logging.INFO)

# Log file configuration
handler = RotatingFileHandler(log_file, maxBytes=100*1024*1024, backupCount=100)  # 100MB per file, 100 backups
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Add handler to the logger
logger.addHandler(handler)

# --- Track Posted Articles ---
posted_articles = set()

# --- Discord Intents Setup ---
intents = discord.Intents.default()
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Fetch Articles ---
def fetch_articles():
    try:
        response = requests.get(URL)
        if response.status_code != 200:
            logger.error(f"Error fetching the webpage. Status code: {response.status_code}")
            return []
    except requests.RequestException as e:
        logger.error(f"Request error: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    articles = soup.find_all('article', class_='article-preview')
    fetched_articles = []

    for article in articles:
        title_tag = article.find('h3')
        link_tag = article.find('a')
        image_tag = article.find('img')

        if title_tag and link_tag and image_tag:
            title = title_tag.text.strip()
            link = link_tag['href']
            full_link = f"https://www.pokemon-zone.com{link}" if link.startswith("/") else link
            image_url = image_tag['src']
            fetched_articles.append((title, full_link, image_url))

    logger.info(f"Fetched {len(fetched_articles)} articles from the website.")
    return fetched_articles

def fetch_first_paragraph(article_url):
    try:
        response = requests.get(article_url)
        if response.status_code != 200:
            logger.error(f"Error fetching the article {article_url}. Status code: {response.status_code}")
            return ""
    except requests.RequestException as e:
        logger.error(f"Request error while fetching {article_url}: {e}")
        return ""

    soup = BeautifulSoup(response.content, 'html.parser')
    first_paragraph = soup.find('p')
    if first_paragraph:
        return first_paragraph.text.strip()
    return ""

# --- Post Articles ---
async def post_articles(channel, articles):
    for title, link, image_url in articles:
        first_paragraph = fetch_first_paragraph(link)
        description = f"{first_paragraph}\n\nRead more at {link}"

        embed = discord.Embed(title=title, url=link, description=description)
        embed.set_image(url=image_url)
        await channel.send(embed=embed)
        logger.info(f"Posted article: {title} - {link}")

# --- Background Task ---
@tasks.loop(hours=1)
async def check_and_post_articles():
    logger.info("Checking for new articles...")
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        logger.error("Channel not found. Check your CHANNEL_ID.")
        return

    new_articles = []
    all_articles = fetch_articles()

    for title, link, image_url in all_articles:
        if link not in posted_articles:
            new_articles.append((title, link, image_url))
            posted_articles.add(link)

    if new_articles:
        logger.info(f"Found {len(new_articles)} new articles. Posting now...")
        await post_articles(channel, new_articles)
    else:
        logger.info("No new articles found.")

# --- Slash Command to Trigger Website Check ---
@bot.tree.command(name="pocketnews", description="Check for updates on Pokemon TCG Pocket.")
async def pocketnews(interaction: discord.Interaction):
    logger.info("Slash command /pocketnews triggered.")
    await interaction.response.send_message("Checking for new articles... ⏳", ephemeral=True)

    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        await interaction.followup.send("Channel not found. Check your CHANNEL_ID.", ephemeral=True)
        logger.error("Channel not found during slash command.")
        return

    new_articles = []
    all_articles = fetch_articles()

    for title, link, image_url in all_articles:
        if link not in posted_articles:
            new_articles.append((title, link, image_url))
            posted_articles.add(link)

    if new_articles:
        await post_articles(channel, new_articles)
        await interaction.followup.send(f"Posted {len(new_articles)} new article(s). ✅", ephemeral=True)
        logger.info(f"Slash command posted {len(new_articles)} articles.")
    else:
        await interaction.followup.send("No new articles found. ✅", ephemeral=True)
        logger.info("No new articles found via slash command.")

# --- Event: Bot Ready ---
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    await bot.tree.sync()  # Sync slash commands
    logger.info("Slash commands synced.")
    logger.info("Initializing posted articles...")

    all_articles = fetch_articles()
    for _, link, _ in all_articles:
        posted_articles.add(link)

    logger.info("Startup complete. Background task starting...")
    check_and_post_articles.start()

# --- Run the Bot ---
bot.run(TOKEN)

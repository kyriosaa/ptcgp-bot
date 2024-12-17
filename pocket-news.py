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

# Track posted articles
posted_articles = set()

# Intents setup
intents = discord.Intents.default()
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Fetch all articles from the website
def fetch_articles():
    try:
        response = requests.get(URL)
        if response.status_code != 200:
            print("Error fetching the webpage.")
            return []
    except requests.RequestException as e:
        print(f"Request error: {e}")
        return []

    # Parse the webpage content
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find all articles
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

    return fetched_articles

# Fetch the first paragraph from the article
def fetch_first_paragraph(article_url):
    try:
        response = requests.get(article_url)
        if response.status_code != 200:
            print(f"Error fetching the article {article_url}.")
            return ""
    except requests.RequestException as e:
        print(f"Request error: {e}")
        return ""

    # Parse the article page
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find the first paragraph
    first_paragraph = soup.find('p')
    if first_paragraph:
        return first_paragraph.text.strip()
    return ""  # If no paragraph, return an empty string

# Post articles to the Discord channel
async def post_articles(channel, articles):
    # Reverse the articles list to post from oldest to newest (bottom to top)
    articles = articles[::-1]
    
    for title, link, image_url in articles:
        # Fetch the first paragraph for the article
        first_paragraph = fetch_first_paragraph(link)
        
        # Add the "Read more at {link}" text at the end of the first paragraph
        description = f"{first_paragraph}\n\nRead more at {link}"

        embed = discord.Embed(title=title, url=link, description=description)
        
        # Add image to the embed
        embed.set_image(url=image_url)
        
        # Send the embed to the channel
        await channel.send(embed=embed)

# Task to check for new articles every hour
@tasks.loop(hours=1)
async def check_and_post_articles():
    print("Checking for new articles...")
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("Channel not found. Check your CHANNEL_ID.")
        return

    new_articles = []
    all_articles = fetch_articles()

    # Check if articles are new
    for title, link, image_url in all_articles:  # Expecting all three values
        if link not in posted_articles:  # Check if already posted
            new_articles.append((title, link, image_url))  # Add all three values
            posted_articles.add(link)  # Mark as posted

    # Post new articles
    if new_articles:
        print(f"Posting {len(new_articles)} new articles.")
        await post_articles(channel, new_articles)
    else:
        print("No new articles found.")


# Event when the bot is ready
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    channel = bot.get_channel(CHANNEL_ID)

    if not channel:
        print("Channel not found. Check your CHANNEL_ID.")
        return

    # Initialize the posted articles set to avoid reposting
    print("Initializing posted articles...")
    current_articles = fetch_articles()
    for _, link, _ in current_articles:
        posted_articles.add(link)

    print("Startup complete. Background task starting...")
    check_and_post_articles.start()

bot.run(TOKEN)

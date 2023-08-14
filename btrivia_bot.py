# This is a sample Python script.
import discord
import sqlite3
import os
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime

# load .env file, and obtain token
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Creates connection to sqlite3 database bd.db (birthdays)
con = sqlite3.connect('bd.db')
cur = con.cursor()

# Declare
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='$', intents=intents)


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    res = cur.execute("SELECT name FROM sqlite_master")
    if res.fetchone() is None:
        print("No \'bd.db\' detected, creating...")
        try:
            cur.execute("CREATE TABLE birthdate(id, date, score)")
            print("Successfully created \'bd.db\'!")
        except:
            print("Error in creating \'bd.db\'.")


# @bot.event
# async def on_message(message):
#     if message.author == bot.user:
#         return
#
#     if message.content.startswith('$hello'):
#         await message.channel.send('Hola guey!')


@bot.command()
async def test(ctx):
    await ctx.send("HOLA GUEY")

@bot.command()
async def opt(ctx, date=None):
    #newdate = datetime.strptime(date, '%m-%d-%Y')
    #print(int(newdate.strftime("%j")))
    embed = discord.Embed(
        title="Welcome {fname}!".format(fname = ctx.author),
        description="""Command: $opt \"MM-DD-YYY\"\n Description: You have the option to store your birthday in our system! Simply share your birthdate using the format MM-DD-YYYY (for example, \"08-08-2001\"). Once confirmed, your birthdate will be linked with your Discord ID, so we can add your special day to our set of trivia questions!""",
        colour=discord.Colour.blurple()
    )
    await ctx.send(embed=embed)

bot.run(TOKEN)

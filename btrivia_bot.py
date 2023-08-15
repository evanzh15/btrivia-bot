# This is a sample Python script.
import discord
import sqlite3
import os
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime, timezone

# load .env file, and obtain token
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Creates connection to sqlite3 database bd.db (birthdays)
con = sqlite3.connect('bd.db')
cur = con.cursor()

# Declare
intents = discord.Intents.default()
intents.message_content = True

# Sets delimiter to '$', and declares default intents
bot = commands.Bot(command_prefix='$', intents=intents)


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    res = cur.execute("SELECT name FROM sqlite_master")
    if res.fetchone() is None:
        print("No \'bd.db\' detected, creating...")
        try:
            cur.execute("CREATE TABLE birthdate(id INTEGER PRIMARY KEY, date INTEGER NOT NULL, score INTEGER NOT NULL)")
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
    res = cur.execute("SELECT * FROM birthdate")
    await ctx.send(res.fetchall())


@bot.command()
async def opt(ctx, date=None):
    # If first parameter remains not present
    if date is None:
        embed = discord.Embed(
            title="Welcome {fname}!".format(fname=ctx.author),
            description="""Command: $opt \"MM-DD-YYY\"\n Description: You have the option to store your birthday in our system! Simply share your birthdate using the format MM-DD-YYYY (for example, \"08-08-2001\"). Once confirmed, your birthdate will be linked with your Discord ID, so we can add your special day to our set of trivia questions!""",
            colour=discord.Colour.blurple()
        )
        await ctx.send(embed=embed)
        return

    res = cur.execute("SELECT date FROM birthdate WHERE id = ?", (ctx.author.id,))
    user_bd = res.fetchone()
    # If user is already in db, output embed message
    if user_bd is not None:
        dt_ts = datetime.fromtimestamp(user_bd[0], tz=timezone.utc)
        embed = discord.Embed(
            title="Rut-roh!".format(fname=ctx.author),
            description="""You're already in the database! Your given birthdate is: {birthdate}. So, just sit back, relax, and wait for the trivia :). If you want to opt-out, please use $deopt.""".format(birthdate=datetime.strftime(dt_ts, "%B %d, %Y")),
            colour=discord.Colour.blurple()
        )
        await ctx.send(embed=embed)
    # Check if user is in db, if not in db, insert (ID, Birthdate, Score: 0)
    else:
        try:
            dt_date = datetime.strptime(date,
                                        '%m-%d-%Y')  # Try to convert string to datetime object, else throw ValueError
            f_date = datetime.strftime(dt_date, '%B %d, %Y')  # Format datetime object into string
            embed = discord.Embed(
                title="Welcome {fname}!".format(fname=ctx.author),
                description="Thank you for opting in! You entered your date of birth as: {dob}".format(dob=f_date),
                colour=discord.Colour.blurple()
            )
            cur.execute("INSERT INTO birthdate (id, date, score) VALUES(?,?,?)",
                        (ctx.author.id, dt_date.replace(tzinfo=timezone.utc).timestamp(), 0))
            con.commit()
            await ctx.send(embed=embed)
        except ValueError:  # User did not enter a valid date, e.g. 02-30-2000, 2-30-200
            embed = discord.Embed(
                title="Rut-roh!".format(fname=ctx.author),
                description="Please enter your birthdate using the format MM-DD-YYYY!",
                colour=discord.Colour.blurple()
            )
            await ctx.send(embed=embed)
        return


@bot.command()
async def deopt(ctx):
    res = cur.execute("SELECT EXISTS(SELECT * FROM birthdate WHERE id = ?)", (ctx.author.id,))
    if res.fetchone()[0]:
        cur.execute("DELETE FROM birthdate WHERE id = ?", (ctx.author.id,))
        con.commit()
        embed = discord.Embed(
            title=":(".format(fname=ctx.author),
            description="Sorry to see you go, {author}! I hope you had a fun time with our trivia!".format(author=ctx.author.name),
            colour=discord.Colour.blurple()
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Rut-roh!".format(fname=ctx.author),
            description="Sorry, I don't know who you are! You're not in our systems, but if you would want to opt-in, please use $opt {MM-DD-YYYY} where MM-DD-YYYY is your birthday.",
            colour=discord.Colour.blurple()
        )
        await ctx.send(embed=embed)

bot.run(TOKEN)

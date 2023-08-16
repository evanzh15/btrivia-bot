import asyncio
import discord
import sqlite3
import os
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timezone

# load .env file, and obtain token
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD = os.getenv("GUILD_ID")

# Creates connection to sqlite3 database bd.db (birthdays)
con = sqlite3.connect('bd.db')
cur = con.cursor()

# Declare
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

# Sets delimiter to '$', and declares default intents
bot = commands.Bot(command_prefix='$', intents=intents)

desired_time = datetime.today().replace(hour=19, minute=46, second=0, microsecond=0)
trivia_questions = ["Whose birthday is on {birthdate}?",
                    "Who celebrates their birthday on {birthdate}?"]


@bot.event
async def on_ready():
    background_loop.start()

    print(f'We have logged in as {bot.user}')
    res = cur.execute("SELECT name FROM sqlite_master")
    if res.fetchone() is None:
        print("No \'bd.db\' detected, creating...")
        try:
            cur.execute("CREATE TABLE birthdate(id INTEGER PRIMARY KEY, date INTEGER NOT NULL, score INTEGER NOT NULL)")
            print("Successfully created \'bd.db\'!")
        except:
            print("Error in creating \'bd.db\'.")


@bot.event
async def on_guild_join(guild):
    # ***** Create a check to see if the channel already exists or not. *****
    await guild.create_text_channel('birthday-trivia')


@bot.command()
async def test(ctx, id):
    res = cur.execute("SELECT * FROM birthdate ORDER BY RANDOM() LIMIT 1")
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
            description="""You're already in the database! Your given birthdate is: {birthdate}. So, just sit back, relax, and wait for the trivia :). If you want to opt-out, please use $deopt.""".format(
                birthdate=datetime.strftime(dt_ts, "%B %d, %Y")),
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
            description="Sorry to see you go, {author}! I hope you had a fun time with our trivia!".format(
                author=ctx.author.name),
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


@tasks.loop(minutes=1)
async def background_loop():
    curr_time = datetime.today().replace(second=0, microsecond=0)
    if curr_time.time() == desired_time.time():
        await birthdate()


async def birthdate():
    res = cur.execute("SELECT * FROM birthdate ORDER BY RANDOM() LIMIT 1")
    subject = res.fetchall()[0]

    user = bot.get_user(subject[0])
    u_bd = datetime.fromtimestamp(subject[1], tz=timezone.utc)

    #print("BIRTHDATE: ", user, u_bd)
    guild = bot.get_guild(int(GUILD))
    channel = discord.utils.get(guild.channels, name="birthday-trivia", type=discord.ChannelType.text)
    await channel.send(trivia_questions[0].format(birthdate=datetime.strftime(u_bd, '%B %d, %Y')))

    def check(response):
        return response.channel == channel and len(response.mentions) == 1 and response.author != bot.user

    try:
        mentioned_users = {}
        for _ in range(10):
            message = await bot.wait_for("message", check=check, timeout=10)
            if message.author.id not in mentioned_users:
                #print(message.author, "not in dict.")
                mentioned_users[message.author.id] = message.mentions[0]
                await message.add_reaction('\N{THUMBS UP SIGN}')
            else:
                await channel.send("You've already submitted a response!")
    except asyncio.TimeoutError:
        await channel.send("Time's up!")

    if len(mentioned_users) == 0:
        await channel.send("No responses :(. The correct answer was <@{user}>!".format(user=user.id))
        return

    embed_info = []

    for author in mentioned_users:
        if mentioned_users[author].id == user.id:
            embed_info += [author]

    desc = ""

    for i, author in enumerate(embed_info):
        res = cur.execute("SELECT score FROM birthdate WHERE id = {identity}".format(identity=author))
        user_score = res.fetchone()[0]
        if i == 0:
            desc += "1st Place: <@" + str(author) + "> \N{Party Popper} \N{Heavy Plus Sign}\U00000035 \n"
            user_score += 5
        elif i == 1:
            desc += "2nd Place: <@" + str(author) + "> \N{Party Popper} \N{Heavy Plus Sign}\U00000033 \n"
            user_score += 3
        elif i == 2:
            user_score += 1
            desc += "3rd Place+: <@" + str(author) + "> "
        else:
            user_score += 1
            desc += "<@" + str(author) + "> "
            if i == len(embed_info) - 1:
                desc += "\N{Party Popper} \N{Heavy Plus Sign}\U00000031"

        cur.execute("UPDATE birthdate SET score = {score} WHERE id = {id}".format(score=user_score, id=author))
        con.commit()

    embed = discord.Embed(
        title="Results! \N{Grinning Face with Smiling Eyes}",
        description=desc,
        color=discord.Colour.dark_magenta()
    )
    await channel.send(embed=embed)

@bot.command()
async def text_channel(ctx):
    if ctx.channel.name == "birthday-trivia":
        # guild = ctx.guild
        # channel = discord.utils.get(guild.channels, name="birthday-trivia", type=discord.ChannelType.text)
        await ctx.send("hola :)")


bot.run(TOKEN)

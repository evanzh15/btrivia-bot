import asyncio
import discord
import sqlite3
import os
from discord.ext import commands, tasks
from dotenv import load_dotenv
import datetime as dt
from datetime import datetime, timezone
import random
import math

# load .env file, and obtain token
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD = os.getenv("GUILD_ID1")

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

trivia_questions = ["Whose birthday is on {birthdate}?",
                    "Who celebrates their birthday on {birthdate}?"]


@bot.event
async def on_ready():
    if "Birthday_Loop" not in bot.cogs:
        await bot.add_cog(Birthday_Loop(bot))

    print(f'We have logged in as {bot.user}')
    res = cur.execute("SELECT name FROM sqlite_master")
    if res.fetchone() is None:
        print("No \'bd.db\' detected, creating...")
        try:
            cur.execute("CREATE TABLE birthdate(id INTEGER PRIMARY KEY, date INTEGER NOT NULL, score INTEGER NOT NULL)")
            cur.execute("CREATE TABLE calendar(date INTEGER PRIMARY KEY, done INTEGER NOT NULL)")
            print("Successfully created \'bd.db\'!")
        except sqlite3.OperationalError:
            print("Error in creating \'bd.db\'.")


@bot.event
async def on_guild_join(guild):
    if discord.utils.get(guild.channels, name="birthday-trivia", type=discord.ChannelType.text) is None:
        await guild.create_text_channel('birthday-trivia')
    if discord.utils.get(guild.roles, name="trivia-heads", type=discord.ChannelType.text) is None:
        await guild.create_role(name='trivia-heads', mentionable=True)


@bot.command()
async def opt(ctx, date=None):
    # If first parameter remains not present
    if date is None:
        embed = discord.Embed(
            title=f"Welcome {ctx.author}!",
            description="""Command: $opt \"MM-DD-YYY\"\n Description: You have the option to store your birthday in our 
            system! Simply share your birthdate using the format MM-DD-YYYY (for example, \"08-08-2001\"). Once 
            confirmed, your birthdate will be linked with your Discord ID, so we can add your special day to our set of 
            trivia questions!""",
            colour=discord.Colour.blurple()
        )
        await ctx.send(embed=embed)
        return

    # Check if id exists in DB
    res = cur.execute("SELECT date FROM birthdate WHERE id = ?", (ctx.author.id,))
    user_bd = res.fetchone()

    # If user is already in DB, output embed message
    if user_bd is not None:
        dt_ts = datetime.fromtimestamp(user_bd[0], tz=timezone.utc)
        embed = discord.Embed(
            title="Rut-roh!",
            description="""You're already in the database! Your given birthdate is: {birthdate}. So, just sit back, 
            relax, and wait for the trivia :). If you want to opt-out, please use $deopt.""".format(
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
                title=f"Welcome {ctx.author}!",
                description="Thank you for opting in! You entered your date of birth as: {dob}".format(dob=f_date),
                colour=discord.Colour.blurple()
            )
            cur.execute("INSERT INTO birthdate (id, date, score) VALUES(?,?,?)",
                        (ctx.author.id, dt_date.replace(tzinfo=timezone.utc).timestamp(), 0))
            con.commit()
            role = discord.utils.get(ctx.guild.roles, name="trivia-heads")
            await ctx.author.add_roles(role)
            await ctx.send(embed=embed)
        except ValueError:  # User did not enter a valid date, e.g. 02-30-2000, 2-30-200
            embed = discord.Embed(
                title="Rut-roh!",
                description="Please enter your birthdate using the format MM-DD-YYYY!",
                colour=discord.Colour.blurple()
            )
            await ctx.send(embed=embed)
        return


@bot.command()
async def deopt(ctx):
    # Check if id exists in DB
    res = cur.execute("SELECT EXISTS(SELECT * FROM birthdate WHERE id = ?)", (ctx.author.id,))

    # If id exists, then delete row from table - send goodbye message
    if res.fetchone()[0]:
        cur.execute("DELETE FROM birthdate WHERE id = ?", (ctx.author.id,))
        con.commit()
        embed = discord.Embed(
            title=":(".format(fname=ctx.author),
            description="Sorry to see you go, {author}! I hope you had a fun time with our trivia!".format(
                author=ctx.author.name),
            colour=discord.Colour.blurple()
        )
        role = discord.utils.get(ctx.guild.roles, name="trivia-heads")
        await ctx.author.remove_roles(role)
        await ctx.send(embed=embed)
    # If id does not exist, deny and offer $opt
    else:
        embed = discord.Embed(
            title="Rut-roh!",
            description="""Sorry, I don't know who you are! You're not in our systems, but if you would want to opt-in, 
                        please use $opt {MM-DD-YYYY} where MM-DD-YYYY is your birthday.""",
            colour=discord.Colour.blurple()
        )
        await ctx.send(embed=embed)


async def birthdate():
    # Obtain guild information since there is no ctx for this function, and search for "birthday-trivia" channel
    # Send random trivia_question
    guild = bot.get_guild(int(GUILD))
    channel = discord.utils.get(guild.channels, name="birthday-trivia", type=discord.ChannelType.text)

    # Obtain a random birthdate from DB and fetch it.
    res = cur.execute("SELECT * FROM birthdate ORDER BY RANDOM() LIMIT 1")
    subject = res.fetchone()

    if subject is None:
        warn_embed = discord.Embed(
            title="Rut-roh!",
            description="There are no birthdays in our database... You should fix that :)",
            colour=discord.Colour.blurple()
        )
        await channel.send(embed=warn_embed)
        return

    # Obtain User and datetime object pertaining to subject
    user = bot.get_user(subject[0])
    user_bd = datetime.fromtimestamp(subject[1], tz=timezone.utc)

    # Obtain list of all users who share the same birthdate
    res = cur.execute(f"SELECT id FROM birthdate WHERE date = {subject[1]}")
    shared_bdays = list(res.fetchall())

    # Create text-channel in case of deletion or on_guild_join() malfunctions
    if channel is None:
        await guild.create_text_channel("birthday-trivia")
    q_embed = discord.Embed(
        title="Attention trivia-heads!",
        description=trivia_questions[random.randint(0, 1)].format(birthdate=datetime.strftime(user_bd, '%B %d, %Y'))
    )
    role = discord.utils.get(guild.roles, name="trivia-heads")
    await channel.send(role.mention)
    await channel.send(embed=q_embed)

    # Check function to determine what message is allowed as input: Must be in "birthday-trivia", messages cannot be
    # from Birthday Bot, and there can only be one mention within responses.
    def check(response):
        return response.channel == channel and len(response.mentions) == 1 and response.author != bot.user

    mentioned_users = {}
    try:
        for _ in range(10):
            message = await bot.wait_for("message", check=check, timeout=20)

            # Only allows for one response per member, and a maximum of 10 responses.
            if message.author.id not in mentioned_users:
                mentioned_users[message.author.id] = message.mentions[0]
                await message.add_reaction('\N{THUMBS UP SIGN}')
            else:
                await message.reply(embed=discord.Embed(title="Rut-roh!",
                                                        description="You've already submitted a response!",
                                                        colour=discord.Colour.dark_red()))
    except asyncio.TimeoutError:
        if len(mentioned_users) == 0:
            if len(shared_bdays) == 1:
                await channel.send("No responses :(. The correct answer was <@{user}>!".format(user=user.id))
            else:
                all_results = ""
                for user in shared_bdays:
                    if user == shared_bdays[-1]:
                        all_results += "and <@" + str(user) + ">"
                    else:
                        all_results += "<@" + str(user) + ">, "
                await channel.send("No responses :(. The correct answers were " + all_results)
            return
        await channel.send("Time's up!")

    embed_info = []

    # Only correct responses are put into consideration
    for author_id in mentioned_users:
        if mentioned_users[author_id].id in shared_bdays:
            embed_info += [str(author_id)]

    desc = "The correct answer was <@{user}>!\n".format(user=user.id)

    # Responses are awarded 5 points for 1st place, 3 points for 2nd place, and 1 point for all subsequent ranks.
    for i, author_id in enumerate(embed_info):
        res = cur.execute("SELECT score FROM birthdate WHERE id = {identity}".format(identity=author_id))
        user_score = res.fetchone()[0]
        if i == 0:
            desc += ("1st Place: <@" + author_id +
                     "> \N{Face with Party Horn and Party Hat} \N{Heavy Plus Sign}\U00000035 \n")
            user_score += 5
        elif i == 1:
            desc += "2nd Place: <@" + author_id + "> \N{Party Popper} \N{Heavy Plus Sign}\U00000033 \n"
            user_score += 3
        elif i == 2:
            user_score += 1
            desc += "3rd Place+: <@" + author_id + "> "
        else:
            user_score += 1
            desc += "<@" + author_id + "> "
            if i == len(embed_info) - 1:
                desc += "\N{Confetti Ball} \N{Heavy Plus Sign}\U00000031"

        cur.execute("UPDATE birthdate SET score = {score} WHERE id = {id}".format(score=user_score, id=author_id))
        con.commit()

    embed = discord.Embed(
        title="Results! \N{Grinning Face with Smiling Eyes}",
        description=desc,
        color=discord.Colour.dark_magenta()
    )
    await channel.send(embed=embed)


async def get_page_score(page):
    offset = page * 10
    result = cur.execute(
        "SELECT id, score FROM birthdate ORDER BY score DESC LIMIT 10 OFFSET {offset}".format(offset=offset))
    score_board = result.fetchall()

    page_desc = ""
    for i, tup in enumerate(score_board):
        if bot.get_user(tup[0]) is None:
            page_desc += str(i) + ". " + "None" + " - " + str(tup[1]) + "\n"
        else:
            page_desc += str(i) + ". " + bot.get_user(tup[0]).name + " - " + str(tup[1]) + "\n"
    p_embed = discord.Embed(
        title="Scoreboard!",
        description=page_desc,
        colour=discord.Colour.blurple()
    )
    return p_embed


async def get_page_birthday(page):
    offset = page * 10
    result = cur.execute(
        "SELECT id, date FROM birthdate ORDER BY date ASC LIMIT 10 OFFSET {offset}".format(offset=offset))
    bd_list = result.fetchall()
    page_desc = ""
    for i, tup in enumerate(bd_list):
        if bot.get_user(tup[0]) is None:
            page_desc += (str(i) + ". " + "None" + " - " +
                          datetime.strftime(datetime.utcfromtimestamp(tup[1]), "%B %d, %Y") + "\n")
        else:
            page_desc += (str(i) + ". " + bot.get_user(tup[0]).name + " - " +
                          datetime.strftime(datetime.utcfromtimestamp(tup[1]), "%B %d, %Y") + "\n")
    p_embed = discord.Embed(
        title="Birthdays!",
        description=page_desc,
        colour=discord.Colour.blurple()
    )
    return p_embed


@bot.command()
async def scoreboard(ctx):
    res = cur.execute("SELECT COUNT(*) FROM birthdate")
    max_pages = int(math.ceil(res.fetchone()[0] / 10.0)) - 1
    print(max_pages)
    if max_pages < 0:
        max_pages = 0
    pagination_view = Button(get_page_score, max_pages)
    await pagination_view.send(ctx)


@bot.command()
async def birthdays(ctx):
    res = cur.execute("SELECT COUNT(*) FROM birthdate")
    max_pages = int(math.ceil(res.fetchone()[0] / 10.0)) - 1
    print(max_pages)
    if max_pages < 0:
        max_pages = 0
    pagination_view = Button(get_page_birthday, max_pages)
    await pagination_view.send(ctx)


async def daily(today_date: int):
    cur.execute("INSERT INTO calendar (date, done) VALUES (?, ?)", (today_date, 0,))
    con.commit()


async def update(today_date: int):
    cur.execute(f"UPDATE calendar SET done = 1 WHERE date = {today_date}")
    con.commit()


class Birthday_Loop(commands.Cog):
    __INIT_TIME = dt.time(hour=10)
    __MIDNIGHT_TIME = dt.time()

    def __init__(self, b):
        self.bot = b
        self.has_run_today = False
        self.time = Birthday_Loop.__INIT_TIME
        self.begin_check = False
        self.loop.start()

    @tasks.loop(minutes=1)
    async def loop(self):
        # print(datetime.now().time().hour, datetime.now().time().minute,
        #       Birthday_Loop.__MIDNIGHT_TIME.hour, Birthday_Loop.__MIDNIGHT_TIME.minute)
        date = datetime.now().strftime("%m-%d-%Y")
        dt_obj = datetime.strptime(date, "%m-%d-%Y").replace(tzinfo=timezone.utc).timestamp()

        res = cur.execute("SELECT done FROM calendar WHERE date = {date}".format(date=dt_obj))
        done = res.fetchone()[0]
        # print(done, date, dt_obj)

        if done is None:
            print("done is None")
            await daily(int(dt_obj))

        if done == 0 and datetime.now().time() >= self.time:
            await birthdate()
            print("done is 0, and now() is > time")
            await update(int(dt_obj))
        if (done == 1 and datetime.now().time().hour == Birthday_Loop.__MIDNIGHT_TIME.hour
                and datetime.now().time().minute == Birthday_Loop.__MIDNIGHT_TIME.minute):
            print("done is 1, and now() is == midnight")
            await self.generate_times()

    async def generate_times(self):
        lower_cutoff, upper_cutoff = 12, 21
        self.time = dt.time(hour=random.randint(lower_cutoff, upper_cutoff))
        print(self.time)


class Button(discord.ui.View):
    def __init__(self, page_f, max_page, timeout=30):
        super().__init__(timeout=timeout)
        self.message = None
        self.get_page = page_f
        self.max_page = max_page
        self.curr_page = 0

    async def send(self, ctx):
        self.message = await ctx.send(view=self)
        await self.update_message()

    async def update_message(self):
        emb = await self.get_page(self.curr_page)
        self.update_buttons()
        await self.message.edit(embed=emb, view=self)

    def update_buttons(self):
        if self.curr_page == 0:
            self.previous_button.disabled = True
        else:
            self.previous_button.disabled = False

        if self.curr_page == self.max_page:
            self.next_button.disabled = True
        else:
            self.next_button.disabled = False

    # noinspection PyUnresolvedReferences
    @discord.ui.button(label="◀️", style=discord.ButtonStyle.green)
    async def previous_button(self, interaction: discord.Interaction, button: discord.Button):
        if self.curr_page <= 0:
            print("left arrow disabled")
            button.disabled = True
        else:
            print("left arrow enabled")
            button.disabled = False

        await interaction.response.defer()
        self.curr_page -= 1
        await self.update_message()

    # noinspection PyUnresolvedReferences
    @discord.ui.button(label="▶️", style=discord.ButtonStyle.green)
    async def next_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.defer()
        self.curr_page += 1

        await self.update_message()

    async def on_timeout(self):
        await self.message.edit(view=None)


bot.run(TOKEN)

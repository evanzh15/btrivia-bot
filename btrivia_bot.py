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

# Set desired time to run birthdate()
desired_time = datetime.today().replace(hour=18, minute=29, second=0, microsecond=0)
trivia_questions = ["Whose birthday is on {birthdate}?",
                    "Who celebrates their birthday on {birthdate}?"]


@bot.event
async def on_ready():
    if not background_loop.is_running():
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
    if discord.utils.get(guild.channels, name="birthday-trivia", type=discord.ChannelType.text) is None:
        await guild.create_text_channel('birthday-trivia')
    if discord.utils.get(guild.roles, name="trivia-heads", type=discord.ChannelType.text) is None:
        await guild.create_role(name='trivia-heads', mentionable=True)


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

    # Check if id exists in DB
    res = cur.execute("SELECT date FROM birthdate WHERE id = ?", (ctx.author.id,))
    user_bd = res.fetchone()

    # If user is already in DB, output embed message
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
            role = discord.utils.get(ctx.guild.roles, name="trivia-heads")
            await ctx.author.add_roles(role)
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
    # Obtain a random birthdate from DB and fetch it.
    res = cur.execute("SELECT * FROM birthdate ORDER BY RANDOM() LIMIT 1")
    subject = res.fetchall()[0]

    # Obtain User and datetime object pertaining to subject
    user = bot.get_user(subject[0])
    user_bd = datetime.fromtimestamp(subject[1], tz=timezone.utc)

    # Obtain guild information since there is no ctx for this function, and search for "birthday-trivia" channel
    # Send random trivia_question
    guild = bot.get_guild(int(GUILD))
    channel = discord.utils.get(guild.channels, name="birthday-trivia", type=discord.ChannelType.text)

    # Create text-channel in case of deletion or on_guild_join() malfunctions
    if channel is None:
        await guild.create_text_channel("birthday-trivia")

    q_embed = discord.Embed(
        title="Attention trivia-heads!",
        description=trivia_questions[0].format(birthdate=datetime.strftime(user_bd, '%B %d, %Y'))
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
            message = await bot.wait_for("message", check=check, timeout=10)

            # Only allows for one response per member, and a maximum of 10 responses.
            if message.author.id not in mentioned_users:
                # print(message.author, "not in dict.")
                mentioned_users[message.author.id] = message.mentions[0]
                await message.add_reaction('\N{THUMBS UP SIGN}')
            else:
                await message.reply(embed=discord.Embed(title="Rut-roh!",
                                                        description="You've already submitted a response!",
                                                        colour=discord.Colour.dark_red()))
    except asyncio.TimeoutError:
        if len(mentioned_users) == 0:
            await channel.send("No responses :(. The correct answer was <@{user}>!".format(user=user.id))
            return
        await channel.send("Time's up!")

    embed_info = []

    # Only correct responses are put into consideration
    for author_id in mentioned_users:
        if mentioned_users[author_id].id == user.id:
            embed_info += [str(author_id)]

    desc = "The correct answer was <@{user}>!\n".format(user=user.id)

    # Responses are awarded 5 points for 1st place, 3 points for 2nd place, and 1 point for all subsequent ranks.
    for i, author_id in enumerate(embed_info):
        res = cur.execute("SELECT score FROM birthdate WHERE id = {identity}".format(identity=author_id))
        user_score = res.fetchone()[0]
        if i == 0:
            desc += "1st Place: <@" + author_id + "> \N{Face with Party Horn and Party Hat} \N{Heavy Plus Sign}\U00000035 \n"
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

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.green)
    async def next_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.defer()
        self.curr_page += 1

        await self.update_message()

    async def on_timeout(self):
        await self.message.edit(view=None)


async def get_page(page):
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


@bot.command()
async def scoreboard(ctx):
    res = cur.execute("SELECT COUNT(*) FROM birthdate")
    max_pages = int(res.fetchone()[0]/10.0)
    pagination_view = Button(get_page, max_pages)
    await pagination_view.send(ctx)


bot.run(TOKEN)

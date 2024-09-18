import asyncio
import builtins
import copy
import logging
import time
import yaml

import discord
from discord.ext import commands

import env
import scrapper

settings_file = "settings.yaml"
dump_file = "data.yaml"

# Suppress only the discord.gateway heartbeat warning
discord_gateway_logger = logging.getLogger('discord.gateway')
discord_gateway_logger.setLevel(logging.ERROR)  # Set level higher to suppress the warning

# Alternatively, to suppress the traceback while keeping the warning message:
discord_gateway_logger.propagate = False
handler = logging.StreamHandler()
handler.setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
discord_gateway_logger.addHandler(handler)

class Bot:

    def __init__(self, settings_file:str, token:str):
        self.logger = copy.copy(logging.getLogger('discord'))
        self.logger.name = "bga-bot"
        self.logger.setLevel(logging.INFO)
        self.logger.info(f"{'*'*50}")

        intents = discord.Intents.default()
        intents.message_content = True

        self.bot = commands.Bot(command_prefix='--', intents=intents)

        @self.bot.event
        async def on_guild_join(guild):
            self.logger.info(f"Joined guild: {guild.name}.")

        @self.bot.command(help="url, friendly name - adds a game to monitor", aliases=['f'])
        async def follow(ctx, url, friendly_name=None):
            self.logger.info("Received follow command.")
            await self.follow(ctx, url, friendly_name)

        @self.bot.command(help="game_id - stop following game.")
        async def unfollow(ctx, game_id):
            await self.unfollow(ctx, game_id)

        @self.bot.command(help="clear games list")
        async def reset(ctx):
            await self.reset(ctx)

        @self.bot.command(help="shows currently monitored games")
        async def games(ctx):
            await self.show_games_list(ctx)

        @self.bot.command(help="bga handle - get pinged when it's your turn")
        async def register(ctx, bga_handle):
            await self.register(ctx, bga_handle)

        @self.bot.command(help="unregisters your discord handle for @'ing when it's your turn")
        async def unregister(ctx):
            await self.unregister(ctx)
        
        @self.bot.command(help="lists players registered on this server")
        async def players(ctx):
            await self.list_players(ctx)

        @self.bot.command(help="passive agressively remind players who is up.")
        async def poke(ctx):
            await self.poke(ctx)

        @self.bot.command(help="mute notifications for 1 hour")
        async def mute(ctx):
            await self.mute(ctx)

        @self.bot.command(help="unmute notifications")
        async def unmute(ctx):
            await self.unmute(ctx)

        with open(settings_file) as stream:
            self.settings = yaml.safe_load(stream)

        @self.bot.event
        async def on_ready():
            self.logger.info(msg="Bot is ready.")
            for guild in self.bot.guilds:
                self.logger.info("Joined {}".format(guild.name))
                with open(dump_file, 'r') as stream:
                    data = None
                    try:
                        data = yaml.safe_load(stream)
                    except EOFError:
                        pass
                if data is None:
                    data = {}
                self.all_games_dict = data
                if guild.name not in builtins.list(self.all_games_dict.keys()):
                    self.logger.info(f"Adding new guild to local record: {guild.name}")
                    self.all_games_dict[guild.name] = {}
                    self.all_games_dict[guild.name]["games"] = {}
                    self.all_games_dict[guild.name]["next_game_id"] = 0
                    self.all_games_dict[guild.name]["players"] = {}

            for guild_name in list(self.all_games_dict.keys()):
                for game_id in builtins.list(self.all_games_dict[guild_name]["games"].keys()):
                    asyncio.create_task(self.monitor_game(game_id, guild_name))
        
        self.refresh_time = self.settings["refresh_time"]
        self.page_reread_attempts = self.settings["page_reread_attempts"]
        self.page_reread_pause = self.settings["page_reread_pause"]
        self.page_reload_attempts = self.settings["page_reload_attempts"]

    
    def run(self):
        self.bot.run(token, reconnect=True)

    
    async def on_ready(self):
        self.logger.info(f'We have logged in as {self.client.user}.')


    async def poke(self, ctx):
        guild_dict = self.get_guild_dict(ctx.guild.name)
        self.logger.info(f"Poke command received for channel {ctx.guild.name}")
        for game_id in list(guild_dict["games"].keys()):
            game_dict = guild_dict["games"][game_id]
            player_up = game_dict["last_player_up"]
            if player_up != "":
                info_str = f"{player_up} is up in game {game_id}: [{game_dict["friendly_name"]}]({game_dict["url"]})."
                if player_up in list(guild_dict["players"].keys()):
                    info_str = info_str + f" <@{guild_dict["players"][player_up]["id"]}>"
                channel = self.bot.get_channel(game_dict["channel_id"])
                if channel is not None and isinstance(channel, discord.TextChannel):
                    await channel.send(info_str)
                else:
                    self.logger.warning(f'Poke command failed in guild {ctx.guild.name}.')
    async def mute(self,ctx):
        guild_dict = self.get_guild_dict(ctx.guild.name)
        self.logger.info(f"Mute command received for channel {ctx.guild.name}")
        self.update_mute_start_time(guild_dict)
        await ctx.send("Notifications muted for one hour.")


    async def unmute(self,ctx):
        guild_dict = self.get_guild_dict(ctx.guild.name)
        self.logger.info(f"Unmute command received for channel {ctx.guild.name}")
        self.update_mute_start_time(guild_dict, 0)
        await ctx.send("Notifications unmuted.")


    def update_mute_start_time(self, guild_dict, start_time:int=None):
        if time is not None:
            guild_dict["mute_time_start"] = start_time
        else:
            guild_dict["mute_time_start"] = int(time.time())

            
    def get_mute_start_time(self, guild_dict):
        if "mute_time_start" in list(guild_dict.keys()):
            return guild_dict["mute_time_start"]
        else:
            return None

    
    async def follow(self, ctx, url, friendly_name):
        guild_dict = self.get_guild_dict(ctx.guild.name)
        game_id = guild_dict["next_game_id"]
        guild_dict["next_game_id"] += 1
        if friendly_name is None:
            friendly_name = f"game {game_id}"
        guild_dict["games"][game_id] = {
            "id": game_id,
            "url": url,
            "channel_id": ctx.channel.id,
            "friendly_name": friendly_name,
            "last_player_up": ""
        }
        game_dict = guild_dict["games"][game_id]
        info_str = f"Now following game {game_id}: [{game_dict["friendly_name"]}]({game_dict["url"]})."
        self.logger.info(info_str)
        await ctx.send(info_str)
        self.write_data_to_file()
        asyncio.create_task(self.monitor_game(game_id, ctx.guild.name))


    def get_guild_dict(self, guild_name):
        if guild_name not in list(self.all_games_dict.keys()):
            self.all_games_dict[guild_name] = {}
            self.all_games_dict[guild_name]["games"] = {}
            self.all_games_dict[guild_name]["next_game_id"] = 0
            self.all_games_dict[guild_name]["players"] = {}
        return self.all_games_dict[guild_name]


    async def monitor_game(self, game_id, guild_name):
        game_dict = self.all_games_dict[guild_name]["games"][game_id]
        self.logger.info(f"Now monitoring game id {game_id} in guild {guild_name}.")
        guild_dict = self.get_guild_dict(guild_name)
        url = game_dict["url"]
        page_reload_counter = 0
        try:
            while game_id in list(guild_dict["games"].keys()):
                if not self.get_mute_start_time(guild_dict):
                    self.update_mute_start_time(guild_dict, 0)
                # self.logger.info(f"{'$'*50}\nTasks:\n{asyncio.all_tasks()}")
                if int(time.time()) - guild_dict["mute_time_start"] > 60*60:
                    try:
                        page_reload_counter += 1
                        page_listener = scrapper.BGA_Page(url, self.logger)
                        try:
                            get_page_return = page_listener.get_page()
                            #page loaded
                            for i in range(1, self.page_reread_attempts):
                                #try reading page
                                await asyncio.sleep(self.page_reread_pause)
                                player_up = page_listener.check_whos_up()
                                if player_up is None or player_up == 1:
                                    #player up not found
                                    self.logger.info(f"Player up not found for game id {game_id}. Waiting {self.page_reread_pause} seconds and checking page again (attempt {i}/{self.page_reread_attempts}).")
                                    continue
                                else:
                                    #player up found, move on
                                    break
                        except:
                            #error
                            info_str = f"Loading page for game {game_id} failed: {str(get_page_return)}."
                            self.logger.info(info_str)
                            player_up = None
                                
                        if player_up is None or player_up == 1:
                            #player up not found after multiple reread attempts
                            if page_reload_counter < self.page_reload_attempts:
                                #reload attempts remaining
                                info_str = f"Player up not found for game id {game_id}. Ignoring for now. Reload counter {page_reload_counter}/{self.page_reload_attempts}."
                                self.logger.info(info_str)
                            else:
                                #no reload attempts remaining
                                info_str = f"[Game {game_id} \"{game_dict["friendly_name"]}]({game_dict["url"]})\" appears to be over. Removing it from the game list."
                                self.logger.info(info_str)
                                channel = self.bot.get_channel(game_dict["channel_id"])
                                if channel is not None and isinstance(channel, discord.TextChannel):
                                    await channel.send(info_str)
                                self.delete_game(guild_name=guild_name, game_id=game_id)
                        else:
                            if player_up != game_dict["last_player_up"] and player_up.strip() != "":
                                self.write_data_to_file()
                                info_str = f"{player_up} is up in game {game_id}: [{game_dict["friendly_name"]}]({game_dict["url"]})."
                                if player_up in list(guild_dict["players"].keys()):
                                    info_str = info_str + f" <@{guild_dict["players"][player_up]["id"]}>"
                                self.logger.info(info_str)
                                channel = self.bot.get_channel(game_dict["channel_id"])
                                if channel is not None and isinstance(channel, discord.TextChannel):
                                    try:
                                        await channel.send(info_str)
                                        game_dict["last_player_up"] = player_up
                                    finally:
                                        page_listener.close()
                                        self.write_data_to_file()
                                        self.logger.info(f"Finished new player up sequence {player_up}/{game_id}/{guild_name}.")
                            else:
                                self.logger.info(f"Player up found for game {game_id} in {guild_name} ({player_up}). No change. Took {page_reload_counter} page load attempts.")
                            page_reload_counter=0
                    except Exception as e:
                        self.logger.info(f"Exception encountered while monitoring game {game_id} in {guild_name}: {e}")
                    finally:
                        try:
                            page_listener.close()
                        except:
                            pass
                await asyncio.sleep(self.refresh_time)
        finally:
            self.write_data_to_file()

    def delete_game(self, guild_name, game_id:int):
        guild_dict = self.get_guild_dict(guild_name)
        if game_id in list(guild_dict["games"].keys()):
            game_dict:dict = guild_dict["games"][game_id]
            del guild_dict["games"][game_id]
            self.logger.info(f"Game {game_dict["friendly_name"]} was deleted.")
        
    async def unfollow(self, ctx, game_id:str):
        error_str = f"\"{game_id}\" is not a valid game id. Use the \"list\" command and lookup the game's integer id."
        try:
            game_id = int(game_id)
        except:
            await ctx.send(error_str)
            return
        if game_id not in list(self.all_games_dict[ctx.guild.name]["games"].keys()):
            await ctx.send(error_str)
            return
        guild_dict = self.get_guild_dict(ctx.guild.name)
        game_dict:dict = guild_dict["games"][game_id]
        self.delete_game(ctx.guild.name, game_id)
        await ctx.send(f"Game {game_id}: [{game_dict["friendly_name"]}]({game_dict["url"]}) unfollowed.")
        self.write_data_to_file()

    async def show_games_list(self, ctx):
        info_str = []
        guild_dict = self.get_guild_dict(ctx.guild.name)
        self.logger.info(f"Game list request command received from channel {ctx.guild.name}")
        if guild_dict["games"] == {}:
            await ctx.send("No games currently being monitored.")
            return
        for game_id in list(guild_dict["games"].keys()):
            game_dict:dict = guild_dict["games"][game_id]
            info_str.append(f"{game_id}: [{game_dict["friendly_name"]}]({game_dict["url"]}) --> {game_dict["last_player_up"]} is up")
        await ctx.send("\n".join(info_str))

    async def reset(self, ctx):
        self.logger.info(f"Reset command received for channel {ctx.guild.name}")
        for game_id in list(self.all_games_dict[ctx.guild.name]["games"].keys()):
            await self.unfollow(ctx, game_id)
        guild_dict = self.get_guild_dict(ctx.guild.name)
        guild_dict["next_game_id"] = 1
        self.write_data_to_file()

    def write_data_to_file(self):
        with open(dump_file, 'w') as stream:
            yaml.safe_dump(self.all_games_dict, stream)
        
    async def register(self, ctx, bga_handle:str):
        discord_id = ctx.author.id
        guild_dict = self.get_guild_dict(ctx.guild.name)
        guild_dict["players"][bga_handle] = {}
        guild_dict["players"][bga_handle]["id"] = discord_id
        guild_dict["players"][bga_handle]["name"] = ctx.author.name
        info_str = f"Registed BGA user \"{bga_handle}\" as discord user \"{ctx.author}\"."
        await ctx.send(info_str)
        self.logger.info(info_str)
        self.write_data_to_file()

    async def unregister(self, ctx):
        discord_id = ctx.author.id
        guild_dict = self.get_guild_dict(ctx.guild.name)
        players_list = guild_dict["players"].copy()
        for handle in players_list:
            if guild_dict["players"][handle]["id"] == discord_id:
                del guild_dict["players"][handle]
                info_str = f"Unregistered BGA user \"{handle}\"."
                await ctx.send(info_str)
                self.logger.info(info_str)
        self.write_data_to_file()
    
    async def list_players(self, ctx):
        self.logger.info(f"List players command received for channel {ctx.guild.name}")
        guild_dict = self.get_guild_dict(ctx.guild.name)
        info_str = ["BGA handle - Discord handle"]
        info_str.append("=========================")
        if list(guild_dict["players"].keys()) == []:
            await ctx.send("No BGA handles registered on this server.")
            return
        for bga_handle in list(guild_dict["players"].keys()):
            discord_handle = guild_dict["players"][bga_handle]["name"]
            info_str.append(f"{bga_handle} - {discord_handle}")
        await ctx.send("\n".join(info_str))
        self.write_data_to_file()

if __name__ == "__main__":

    token = env.token
    bot = Bot(settings_file, token)
    bot.run()

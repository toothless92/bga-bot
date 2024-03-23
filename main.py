import asyncio
import copy
import logging
import yaml

import discord
from discord.ext import commands

import env
import scrapper

settings_file = "settings.yaml"
# logger = logging.root()

class Bot:

    def __init__(self, settings_file:str, token:str):
        self.logger = copy.copy(logging.getLogger('discord'))
        self.logger.name = "bga-bot"
        self.logger.setLevel(logging.INFO)

        intents = discord.Intents.default()
        intents.message_content = True

        self.bot = commands.Bot(command_prefix='--', intents=intents)

        @self.bot.event
        async def on_ready():
            self.logger.info(msg="Bot is ready.")
            self.all_games_dict = {}
            for guild in self.bot.guilds:
                self.logger.info("Joined {}".format(guild.name))
                self.all_games_dict[guild.name] = {}
                self.all_games_dict[guild.name]["next_game_id"] = 0

        @self.bot.event
        async def on_guild_join(guild):
            self.logger.info(f"Joined guild: {guild.name}.")

        @self.bot.command(help="url, friendly name - adds a game to monitor")
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
        async def list(ctx):
            await self.show_list(ctx)

        with open(settings_file) as stream:
            self.settings = yaml.safe_load(stream)
        
        self.refresh_time = self.settings["refresh_time"]
    
    def run(self):
        self.bot.run(token, reconnect=True)
    
    async def on_ready(self):
        self.logger.info(f'We have logged in as {self.client.user}.')

    async def follow(self, ctx, url, friendly_name):
        page_listener = scrapper.BGA_Page(url, self.logger)
        guild_games_dict = self.all_games_dict[ctx.guild.name]
        game_id = guild_games_dict["next_game_id"]
        guild_games_dict["next_game_id"] += 1
        guild_games_dict[game_id] = self.Game(
            id = game_id,
            url = url,
            ctx = ctx,
            friendly_name = friendly_name,
            page_listener = page_listener
        )
        game:self.Game = guild_games_dict[game_id]
        info_str = f"Now following [{game.friendly_name}]({game.url})."
        self.logger.info(info_str)
        await game.ctx.send(info_str)
        while game_id in list(guild_games_dict.keys()):
            player_up = page_listener.check_whos_up()
            if player_up is None:
                info_str = f"[Game \"{game.friendly_name}]({game.url})\" appears to be over. Removing it from the game list."
                self.logger.info(info_str)
                await game.ctx.send(info_str)
                self.delete_game(guild_games_dict=guild_games_dict, game_id=game_id)
            else:
                if player_up != game.last_player_up and player_up.strip() != "":
                    game.last_player_up = player_up
                    info_str = f"{player_up} is up in [{game.friendly_name}]({game.url})\""
                    self.logger.info(info_str)
                    await game.ctx.send(info_str)
            await asyncio.sleep(self.refresh_time)

    def delete_game(self, guild_games_dict, game_id:int):
        game = guild_games_dict[game_id]
        game.page_listener.close()
        del guild_games_dict[game_id]
        self.logger.info(f"Game {game.friendly_name} was deleted.")
        
    async def unfollow(self, ctx, game_id:str):
        error_str = f"\"{game_id}\" is not a valid game id. Use the \"list\" command and lookup the game's integer id."
        try:
            game_id = int(game_id)
        except:
            await ctx.send(error_str)
            return
        if game_id not in list(self.all_games_dict[ctx.guild.name].keys()):
            await ctx.send(error_str)
            return
        guild_games_dict = self.all_games_dict[ctx.guild.name]
        game = guild_games_dict[game_id]
        self.delete_game(guild_games_dict, game_id)
        await ctx.send(f"[{game.friendly_name}]({game.url}) unfollowed.")

    async def show_list(self, ctx):
        info_str = []
        guild_games_dict = self.all_games_dict[ctx.guild.name]
        if guild_games_dict == {}:
            await ctx.send("No games currently being monitored.")
            return
        for game_id in list(guild_games_dict.keys()):
            game:self.Game = guild_games_dict[game_id]
            info_str.append(f"{game_id}: [{game.friendly_name}]({game.url}) --> {game.last_player_up} is up")
            await ctx.send("\n".join(info_str))

    async def reset(self, ctx):
        for game_id in list(self.all_games_dict[ctx.guild.name].keys()):
            await self.unfollow(ctx, game_id)

    class Game():
        def __init__(self, id:int, url:str="", ctx=None, last_player_up:str="", friendly_name=None, page_listener=None):
            self.id = id
            self.url = url
            self.ctx = ctx
            self.last_player_up = last_player_up
            self.friendly_name = friendly_name
            if friendly_name is None:
                self.friendly_name = f"game {self.id}"
            self.page_listener = page_listener

if __name__ == "__main__":
    token = env.token
    bot = Bot(settings_file, token)
    bot.run()
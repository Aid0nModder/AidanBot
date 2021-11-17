import discord
from discord.ext import commands
from discord.utils import find

import asyncio

from functions import getEmbed, addField, Error, userHasPermission

import json
with open('./desc.json') as file:
    DESC = json.load(file)

async def getCommand(ctx, client, commandparam):
	com = None
	for command in client.commands:
		if command.name.lower() == commandparam.lower():
			com = command
	if not com:
		return "NotWork"

	if com.hidden: # check command can run
		return "NotWork"
	try:
		succ = await com.can_run(ctx)
		if not succ:
			return "NotWork"
	except commands.CommandError:
		return "NotWork"
	return com

class ImportantCog(commands.Cog):
	def __init__(self, client):
		self.client = client

	@commands.cooldown(1, 10, commands.BucketType.channel)
	@commands.command(description=DESC["help"])
	async def help(self, ctx, name:str=None):
		prefix = self.client.PREFIX

		if name: 
			command = await getCommand(ctx, self.client, name)
			if command != "NotWork":   # Get help on a spesific command
				name = f"{prefix}{command.name}"
				if command.aliases:
					name += f" (or {prefix}{command.aliases[0]})"

				emb = getEmbed(ctx, f"Help > {prefix}{command.name}", f"{name} - {command.signature}", command.description.format(prefix=prefix))
				await ctx.reply(embed=emb, mention_author=False)

			else:   # Get all commands in a category
				category, categoryname = False, False
				for order in DESC["_order_"]:
					nicename = order
					if order in DESC["_ordernicenames_"]:
						nicename = DESC["_ordernicenames_"][order][0]
						
					if name.lower() == order.lower():
						category, categoryname = DESC["_order_"][order], nicename
					if order in DESC["_ordernicenames_"]:
						for nname in DESC["_ordernicenames_"][order]:
							if name.lower() == nname.lower():
								category, categoryname = DESC["_order_"][order], nicename

				if not category:
					await ctx.send("Couldn't find command or category with that name :/")
					return

				txt = ""
				for commandname in category:
					command = await getCommand(ctx, self.client, commandname)
					if command == "NotWork":
						continue
					desc = command.description.format(prefix=prefix) or "No description."
					if "\n" in desc:
						desc = desc.splitlines()[0]
					txt = txt + f"`{prefix}{command.name}`: {desc}\n"

				emb = getEmbed(ctx, f"Help > {name}", f"All commands in {name}:", f"Run {prefix}help <command> to get more help on a command!")
				emb = addField(emb, categoryname, txt, False)
				await ctx.reply(embed=emb, mention_author=False)

		else:   # Get all commands
			categories = []
			for order in DESC["_order_"]:
				txt, lenn = "", 0
				for commandname in DESC["_order_"][order]:
					command = await getCommand(ctx, self.client, commandname)
					if command == "NotWork":
						continue
					desc = command.description.format(prefix=prefix) or "No description."
					if "\n" in desc:
						desc = desc.splitlines()[0]
					txt = txt + f"`{prefix}{command.name}`: {desc}\n"
					lenn += 1
				if txt != "":
					nicename = order
					if order in DESC["_ordernicenames_"]:
						nicename = DESC["_ordernicenames_"][order][0]
					categories.append([nicename, txt, lenn])

			pagesi = [[]]
			page, maxpages, pagelen, minlen = 0, 0, 0, 9
			for i in range(0, len(categories)):
				pagesi[maxpages].append(i)
				pagelen += categories[i][2]
				if pagelen >= minlen and i != len(categories)-1:
					maxpages += 1
					pagelen = 0
					pagesi.append([])

			def getHelpEmbed(typ=None):
				title, timeout = "Help", False
				if typ == "load":
					title = "Help (loading...)"
				elif typ == "timeout":
					title, timeout = "Help (timeout)", True
				else:
					title = f"Help (page {page+1} of {maxpages+1})"

				buttons = discord.ui.View(
					discord.ui.Button(label="<<<", style=discord.ButtonStyle.blurple, custom_id="left", disabled=timeout),
					discord.ui.Button(label=">>>", style=discord.ButtonStyle.blurple, custom_id="right", disabled=timeout),
					discord.ui.Button(emoji="✖️", style=discord.ButtonStyle.grey, custom_id="exit", disabled=timeout)
				)

				emb = getEmbed(ctx, title, "All commands you can use:", f"Run {prefix}help <command> to get more help on a command!\nRun {prefix}help <category> to get all commands in a category.")
				for i in pagesi[page]:
					emb = addField(emb, categories[i][0], categories[i][1], False)

				return emb, buttons

			emb, buttons = getHelpEmbed("load")
			MSG = await ctx.reply(embed=emb, mention_author=False, view=buttons)

			def check(interaction):
				return (interaction.user.id == ctx.author.id and interaction.message.id == MSG.id)

			while True:
				emb, buttons = getHelpEmbed()
				await MSG.edit(embed=emb, view=buttons)

				try:
					interaction = await self.client.wait_for("interaction", timeout=60, check=check)
					if interaction.data["custom_id"] == "left" and page > 0:
						page -= 1
					elif interaction.data["custom_id"] == "right" and page < maxpages:
						page += 1
					elif interaction.data["custom_id"] == "exit":
						emb, buttons = getHelpEmbed("timeout")
						await MSG.edit(embed=emb, view=buttons)
						return
				except asyncio.TimeoutError:
					emb, buttons = getHelpEmbed("timeout")
					await MSG.edit(embed=emb, view=buttons)
					return

	@commands.command(description=DESC["info"])
	@commands.cooldown(1, 10, commands.BucketType.channel)
	async def info(self, ctx):
		emb = getEmbed(ctx, "Info", f"Hey, I am {self.client.NAME}!", self.client.DESC)

		emb = addField(emb, "Version:", self.client.VERSION)
		await ctx.reply(embed=emb, mention_author=False)

	@commands.command(description=DESC["invite"])
	@commands.cooldown(1, 10, commands.BucketType.channel)
	async def invite(self, ctx):
		if self.client.ISBETA:
			if ctx.author.id == 384439774972215296:
				await ctx.reply("Sent to your DM's aidan, gotta keep me safe :3", mention_author=False)
				await ctx.author.send("https://discord.com/api/oauth2/authorize?client_id=861571290132643850&permissions=8&scope=bot%20applications.commands")
			else:
				await ctx.reply("I'm a test bot so you can't add me sorry, my brother would love to join your server tho! https://discord.com/api/oauth2/authorize?client_id=804319602292949013&permissions=8&scope=bot", mention_author=False)
		else:
			await ctx.reply("Y- you want me on your server??? I'd love too!!! https://discord.com/api/oauth2/authorize?client_id=804319602292949013&permissions=8&scope=bot", mention_author=False)

	@commands.command(description=DESC["role"])
	@commands.cooldown(3, 30, commands.BucketType.user)
	async def role(self, ctx, *, name=None):
		if name == None:
			await Error(ctx, self.client, "Missing un-optional argument for command.")
			return

		r = find(lambda m: name.lower() in m.name.lower(), ctx.guild.roles)
		if r == None:
			await ctx.reply("Try again, i couldn't find this role.", mention_author=False)
			return

		if userHasPermission(ctx.author, "manage_roles") or r.name.startswith("[r]"):
			if r == ctx.author.top_role:
				await ctx.reply(f"You can't remove your top role", mention_author=False)
				return
			if r in ctx.author.roles:
				await ctx.author.remove_roles(r)
				await ctx.reply(f"Removed {r.name}", mention_author=False)
			else:
				await ctx.author.add_roles(r)
				await ctx.reply(f"Added {r.name}", mention_author=False)
		else:
			await ctx.reply(f"{r.name} is not a role that can be added by anyone", mention_author=False)

def setup(client):
	client.add_cog(ImportantCog(client))
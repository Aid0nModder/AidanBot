from discord import Option, InputTextStyle
from discord.ui import Modal, InputText
from discord.ext import commands
from discord.commands import SlashCommandGroup

import io, contextlib, textwrap
from traceback import format_exception
from functions import getComEmbed

def tobool(val):
	if val.lower() == "true":
		return True
	return False
	
class OwnerCog(commands.Cog):
	def __init__(self, client):
		self.client = client

	class EvalModal(Modal):
		def __init__(self, client, template):
			self.client = client
			super().__init__(title="Eval", custom_id="eval")

			txt = ""
			if template == "utils.get":
				txt = 'from discord.utils import get\nguild = get(client.guilds, name="name_here")'
			if template == "embed":
				txt = 'from functions import getComEmbed\nemb = getComEmbed(ctx, client, "Amgous", "Sussy")\nawait ctx.send(embed=emb)'
			self.add_item(InputText(style=InputTextStyle.long, label="Code:", placeholder="print('Hello World!')", value=txt, required=True))
		async def callback(self, interaction):
			await interaction.response.send_message("Working...")

	ownergroup = SlashCommandGroup("owner", "Owner commands.")

	@ownergroup.command(name="eval", description="For running python code in discord.")
	async def eval(self, ctx,
		template:Option(str, "Template code", choices=["None","utils.get","embed"], default="None"),
		respond:Option(str, "If it responds after the code has finished running.", choices=["True","False"], default="True"),
		ephemeral:Option(str, "If the code can be seen by just you or not.", choices=["True","False"], default="False")
	):
		if not await self.client.is_owner(ctx.author):
			return await ctx.respond("**No.**")
		respond, ephemeral = tobool(respond), tobool(ephemeral)
		await ctx.send_modal(self.EvalModal(self.client, template))
		
		interaction = await self.client.wait_for("interaction")
		try:
			code = interaction.data["components"][0]["components"][0]["value"]
			await interaction.delete_original_message()

			local_variables = {
				"client": self.client,
				"ctx": ctx,
				"author": ctx.author,
				"channel": ctx.channel,
				"guild": ctx.guild
			}
			stdout = io.StringIO()
			iserror = False
			try:
				with contextlib.redirect_stdout(stdout):
					exec(f"import discord\n\nasync def func():\n{textwrap.indent(code, '    ')}", local_variables)
					await local_variables["func"]()
					result = f"{stdout.getvalue()}"
			except Exception as e:
				result = "".join(format_exception(e, e, e.__traceback__))
				iserror = True
			
			if iserror or respond:
				embed = False
				if result == "":
					embed = getComEmbed(ctx, self.client, content=f"Code: ```py\n{code}\n```")
				else:
					embed = getComEmbed(ctx, self.client, content=f"Code: ```py\n{code}\n```\nResults: ```\n{str(result)}\n```")
				await ctx.respond(embed=embed, ephemeral=ephemeral)
		except:
			return

def setup(client):
	client.add_cog(OwnerCog(client))
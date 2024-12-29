import discord
from discord.ext import commands
import aiohttp
import os
import asyncio

# Bot Configuration

TOKEN = ''

# Intents Setup
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='§', intents=intents)

# Remove the default help command
bot.remove_command('help')

# Temporary folder for attachments
TEMP_DIR = 'attachments'
os.makedirs(TEMP_DIR, exist_ok=True)

# Per-server configurations
server_config = {}


# ✅ Event: Bot Ready
@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user.name}')


# ✅ Admin Role Check Decorator
def is_admin():
    async def predicate(ctx):
        admin_role = discord.utils.get(ctx.guild.roles, name='Musk')
        if admin_role in ctx.author.roles:
            return True
        await ctx.send("❌ You need the **Admin** role to use this command.")
        return False
    return commands.check(predicate)


# ✅ Custom Help Command (Admin Only, Embed)
@bot.command(name='help', help='Displays a list of available commands and their descriptions.')
@is_admin()
async def custom_help(ctx):
    """Custom Help Command Restricted to Admins."""
    embed = discord.Embed(
        title="🛠️ **Bot Command List**",
        description="Here are the available commands categorized by functionality:",
        color=discord.Color.blue()
    )

    # Admin Commands
    embed.add_field(
        name="🛡️ **Admin Commands**",
        value=(
            "`§set_log_channel #channel` → Set the logging channel.\n"
            "`§set_forward_channels #source #destination` → Set source and destination forwarding channels.\n"
            "`§toggle_invites` → Enable/disable invite removal.\n"
            "`§remove_invites` → Remove all invites from the server.\n"
        ),
        inline=False
    )

    # General Commands
    embed.add_field(
        name="📦 **General Commands**",
        value="`§help` → Show this help message.",
        inline=False
    )

    # Footer
    embed.set_footer(text="Use §help <command> for detailed information about a specific command.")

    await ctx.send(embed=embed)


# ✅ Command: Set Log Channel
@bot.command()
@commands.has_permissions(administrator=True)
async def set_log_channel(ctx, channel: discord.TextChannel):
    """Set the log channel for this server."""
    guild_id = ctx.guild.id
    if guild_id not in server_config:
        server_config[guild_id] = {}
    server_config[guild_id]['log_channel'] = channel.id
    await ctx.send(f"✅ Log channel set to {channel.mention}")


# ✅ Command: Set Source and Destination Channels for Forwarding
@bot.command()
@commands.has_permissions(administrator=True)
async def set_forward_channels(ctx, source: discord.TextChannel, destination: discord.TextChannel):
    """Set the source and destination channels for message forwarding."""
    guild_id = ctx.guild.id
    if guild_id not in server_config:
        server_config[guild_id] = {}
    server_config[guild_id]['source_channel'] = source.id
    server_config[guild_id]['destination_channel'] = destination.id
    await ctx.send(f"✅ Source channel set to {source.mention}\n✅ Destination channel set to {destination.mention}")


# ✅ Command: Toggle Invite Removal
@bot.command()
@commands.has_permissions(administrator=True)
async def toggle_invites(ctx):
    """Enable or disable invite removal for this server."""
    guild_id = ctx.guild.id
    if guild_id not in server_config:
        server_config[guild_id] = {}
    server_config[guild_id]['invite_removal_enabled'] = not server_config[guild_id].get('invite_removal_enabled', True)
    status = "enabled" if server_config[guild_id]['invite_removal_enabled'] else "disabled"
    await ctx.send(f"🛡️ Invite removal has been **{status}**.")
    
    log_channel_id = server_config[guild_id].get('log_channel')
    if log_channel_id:
        log_channel = bot.get_channel(log_channel_id)
        if log_channel:
            await log_channel.send(f"🔄 **Invite removal has been {status}** by **{ctx.author}**.")


# ✅ Command: Remove All Invites with Logging
@bot.command()
@commands.has_permissions(manage_guild=True)
async def remove_invites(ctx):
    """Remove all invites in the current server."""
    guild_id = ctx.guild.id
    config = server_config.get(guild_id, {})
    if not config.get('invite_removal_enabled', True):
        await ctx.send("❌ Invite removal is currently **disabled**. Use `§toggle_invites` to enable it.")
        return

    guild = ctx.guild
    if not guild:
        await ctx.send("❌ This command can only be used in a server.")
        return

    try:
        invites = await guild.invites()
        invite_count = len(invites)

        if invite_count == 0:
            await ctx.send("✅ No active invites found in this server.")
            return

        log_channel_id = config.get('log_channel')
        log_channel = bot.get_channel(log_channel_id) if log_channel_id else None

        await ctx.send(f"🛡️ **Starting to remove {invite_count} invite(s)...**")
        if log_channel:
            await log_channel.send(f"🛡️ **Starting to remove {invite_count} invite(s) in {guild.name}...**")

        for invite in invites:
            await invite.delete()
            await asyncio.sleep(0.25)

        await ctx.send(f"🎯 **Successfully removed {invite_count} invite(s) from {guild.name}.**")

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to manage invites.")


# ✅ Event: Forward Messages and Attachments Between Channels
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    guild_id = message.guild.id if message.guild else None
    config = server_config.get(guild_id, {})

    source_channel_id = config.get('source_channel')
    destination_channel_id = config.get('destination_channel')

    # ✅ Forward Messages from Source Channel to Destination Channel
    if message.channel.id == source_channel_id:
        destination_channel = bot.get_channel(destination_channel_id)
        
        if destination_channel:
            # Forward text content if available
            if message.content:
                await destination_channel.send(
                    f"**Message from {message.author.name} in {message.channel.name}:** {message.content}"
                )
            
            # ✅ Handle Attachments
            if message.attachments:
                for attachment in message.attachments:
                    file_path = os.path.join(TEMP_DIR, attachment.filename)
                    
                    try:
                        # Download the attachment
                        async with aiohttp.ClientSession() as session:
                            async with session.get(attachment.url) as resp:
                                if resp.status == 200:
                                    with open(file_path, 'wb') as f:
                                        f.write(await resp.read())
                                    print(f"✅ Attachment downloaded: {file_path}")
                    
                        # Upload the attachment to the destination channel
                        with open(file_path, 'rb') as f:
                            discord_file = discord.File(f, filename=attachment.filename)
                            await destination_channel.send(
                                f"**Attachment from {message.author.name}:**", 
                                file=discord_file
                            )
                        print(f"✅ Attachment forwarded: {attachment.filename}")
                    
                    except Exception as e:
                        print(f"❌ Error handling attachment: {e}")
                        await message.channel.send(f"❌ Failed to process attachment: {attachment.filename}")
                    
                    finally:
                        # Clean up local file
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            print(f"🗑️ Temporary file removed: {file_path}")
        else:
            print("❌ Destination channel not found!")

    await bot.process_commands(message)


# ✅ Run the Bot
bot.run(TOKEN)

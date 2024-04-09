from typing import Final
import os
from dotenv import load_dotenv
from discord.ext import commands
import discord
from netmiko import ConnectHandler
from ospf import ospf, remove_ospf_nw, disable_ospf
from rip import rip, remove_rip_nw, disable_rip
from bgp import bgp, remove_bgp_nw, remove_bgp_neighbor, disable_bgp
from eigrp import eigrp, remove_eigrp_nw, disable_eigrp
from help_pages import get_help_page


load_dotenv()
TOKEN: Final[str] = os.getenv("DISCORD_TOKEN")
CHANNEL_ID: Final[int] = int(os.getenv("CHANNEL_ID"))

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())
net_connect = None

connections = {}

def no_index_exists():
    embed = discord.Embed(title="Error", color=0xff0000)
    embed.add_field(name="", value="No device at the index provided.", inline=False)
    embed.add_field(name="", value="Use !show_connection to show all connected device with index.", inline=False)
    embed.add_field(name="", value="Use !create_connection <ip_addr> <username> <password> to connect to a device.", inline=False)
    return embed

@bot.event
async def on_ready():
    print('Bot is ready!')
    channel = bot.get_channel(CHANNEL_ID)
    embed = discord.Embed(title="Bot is ready!", color=0x00ff00)
    await channel.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Invalid command. Type **!help** to see the list of available commands.", inline=False)
        await ctx.send(embed=embed)
    else:
        raise error


@bot.command()
async def create_connection(ctx, ip, username, password):
    discord_username = str(ctx.author)

    user_connections = [key for key in connections if key.startswith(f"{discord_username}:")]
    device_index = len(user_connections) + 1

    key = f"{discord_username}:{device_index}"
    if key in connections:
        await ctx.send(f"```Device {device_index} is already connected for {discord_username}.```")
        return

    connections[key] = [ip, username, password]
    await ctx.send(f"```Connection created for {discord_username} with device #{device_index}.```")
    print(connections)

@bot.command()
async def connect(ctx, device_index: int = None):
    global net_connect
    discord_username = str(ctx.author)

    if device_index is None:
        user_connections = [key for key in connections if key.startswith(f"{discord_username}:")]
        if not user_connections:
            embed = discord.Embed(title="Error", color=0xff0000)
            embed.add_field(name="", value="You don't have any devices connected.", inline=False)
            embed.add_field(name="", value="Use !create_connection first.", inline=False)
            await ctx.send(embed=embed)
            return None
        device_index = 1

    key = f"{discord_username}:{device_index}"
    if key not in connections:
        embed = discord.Embed(title="Error", description="Device not found", color=0xff0000)
        embed.add_field(name="", value=f"No device information found for the device at index {device_index}.", inline=False)
        embed.add_field(name="", value="Use !create_connection first.", inline=False)
        await ctx.send(embed=embed)
        #await ctx.send(f"```No device information found for the device at index {device_index}.\n\nUse !create_connection first.```")
        return None

    ip, username, password = connections[key]

    device = {
        'device_type': 'cisco_ios',
        'host': ip,
        'username': username,
        'password': password,
        'port': 22,
    }

    await ctx.send(f'```Connecting to {ip}...```')
    net_connect = ConnectHandler(**device)
    output = net_connect.send_command('show ip int brief')
    if output == '':
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to device.", inline=False)
        await ctx.send(embed=embed)
        return None
    else:
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value=f"Connected to {ip} successfully!", inline=False)
        await ctx.send(embed=embed)
        return net_connect

@bot.command()
async def command_list(ctx):
    mention = ctx.author.mention
    channel = await ctx.author.create_dm()
    message = await channel.send(embed=get_help_page(1))
    await message.add_reaction('⬅️')
    await message.add_reaction('➡️')
    await ctx.send(f'{mention}'+'``` Command lists sent to your DM!```')

@bot.event
async def on_raw_reaction_add(payload):
    message_id = payload.message_id
    message = await bot.get_channel(payload.channel_id).fetch_message(message_id)
    page = 1
    if "Help (1/5)" in message.embeds[0].title:
        page = 1
    elif "Help (2/5)" in message.embeds[0].title:
        page = 2
    elif "Help (3/5)" in message.embeds[0].title:
        page = 3
    elif "Help (4/5)" in message.embeds[0].title:
        page = 4
    elif "Help (5/5)" in message.embeds[0].title:
        page = 5
    if str(payload.emoji) == '⬅️':
        # await message.remove_reaction('⬅️', payload.member)
        if page == 1:
            await message.edit(embed=get_help_page(5))
        else:
            await message.edit(embed=get_help_page(page-1))
    elif str(payload.emoji) == '➡️':
        # await message._remove_reaction('➡️', payload.member)
        if page == 5:
            await message.edit(embed=get_help_page(1))
        else:
            await message.edit(embed=get_help_page(page+1))

@bot.command()
async def show_connection(ctx):
    discord_username = str(ctx.author)
    user_connections = [key for key in connections if key.startswith(f"{discord_username}:")]
    if not user_connections:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You don't have any devices connected.", inline=False)
        embed.add_field(name="", value="Use **!create_connection** first.", inline=False)
        await ctx.send(embed=embed)
        return

    embed = discord.Embed(title="Connected Devices", color=0x00ff00)
    for key in user_connections:
        device_index = key.split(":")[1]
        ip, _, _ = connections[key]
        embed.add_field(name=f"Device #{device_index}", value=f"IP: {ip}", inline=False)
    mention = ctx.author.mention
    await ctx.send(mention + '```List of connected devices has been sent to your DM!```')
    await ctx.author.send(embed=embed)

@bot.command()
async def ping(ctx, index, ip):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    net_connect = await connect(ctx, index)

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        await ctx.send(embed=embed)
    else:
        cmd_list = ['ping ' + ip,
                     '\n']
        await ctx.send(f'```Pinging to {ip}...```')
        output = net_connect.send_multiline_timing(cmd_list)
        count = output.count('!')
        embed = discord.Embed(title="Ping Result", color=0x00ff00)
        embed.add_field(name="Packets sent", value="5", inline=False)
        embed.add_field(name="Packets received", value=str(count), inline=False)
        embed.add_field(name="", value="----------------------", inline=False)
        embed.add_field(name="Packet received", value=f"{count} ({count * 20}% received)", inline=False)
        embed.add_field(name="Packet loss", value=f"{5 - count} ({(5 - count) * 20}% loss)", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()
        
@bot.command()
async def show_int(ctx, index):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    net_connect = await connect(ctx, index)

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        await ctx.send(embed=embed)
        # await ctx.send('```You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.```')
    else:
        output = net_connect.send_command('show ip int brief')
        await ctx.send('```'+output+'```')
        net_connect.disconnect()

@bot.command()
async def show_vlan(ctx, index):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    net_connect = await connect(ctx, index)

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        # await ctx.send('```You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.```')
    else:
        output = net_connect.send_command('show vlan brief')
        if 'Invalid' in output:
            await ctx.send('```This command is not supported on router.```')
        else:
            await ctx.send('```'+output+'```')
            net_connect.disconnect()

@bot.command()
async def show_run(ctx, index):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    net_connect = await connect(ctx, index)

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        # await ctx.send('You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.')
    else:
        output = net_connect.send_command('show run')
        await ctx.send('```'+output+'```')
        net_connect.disconnect() 

@bot.command()
async def show_run_int(ctx, index, interface):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        # await ctx.send('You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.')
    else:
        output = net_connect.send_command('show run int ' + interface)
        await ctx.send('```'+output+'```')
        net_connect.disconnect()

@bot.command()
async def save_config(ctx, index):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        # await ctx.send('You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.')
    else:
        output = net_connect.send_command('wr')
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value="Configuration has been saved!", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()

@bot.command()
async def hostname(ctx, index, hostname):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        # await ctx.send('You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.')
    else:
        command_list = ['hostname ' + hostname]
        output = net_connect.send_config_set(command_list)
        await ctx.send('```Hostname has been set to ' + hostname+'```')
        net_connect.disconnect()
        
@bot.command()
async def show_hostname(ctx, index):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return
    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        output = net_connect.send_command('show run | include hostname')
        output = output.split(' ')[1]
        await ctx.send('```Hostname: '+output+'```')
        net_connect.disconnect()

@bot.command()
async def show_route(ctx, index):
    global net_connect
    discord_username = str(ctx.author)
    key = f'{discord_username}:{index}'
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        # await ctx.send('You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.')
    else:
        output = net_connect.send_command('show ip route')
        await ctx.send('```'+output+'```')
        net_connect.disconnect()
        
@bot.command()
async def create_route(ctx , index, dest_ip, dest_mark, next_hop):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        # await ctx.send('You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.')
    else:
        output = net_connect.send_command(f'ip route {dest_ip} {dest_mark} {next_hop}')
        await ctx.send('```Route has been added!```')
        net_connect.disconnect()

@bot.command()
async def delete_route(ctx, index, dest_ip, dest_mark, next_hop):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        # await ctx.send('You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.')
    else:
        output = net_connect.send_command(f'no ip route {dest_ip} {dest_mark} {next_hop}')
        await ctx.send('```Route has been deleted!```')
        net_connect.disconnect()
        
@bot.command()
async def show_spanning_tree(ctx, index):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        # await ctx.send('You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.')
    else:
        output = net_connect.send_command('show spanning-tree')
        if 'No spanning tree' in output:
            embed = discord.Embed(title="Error", color=0xff0000)
            embed.add_field(name="", value=output, inline=False)
            await ctx.send(embed=embed)
        await ctx.send('```'+output+'```')
        net_connect.disconnect()

@bot.command()
async def banner(ctx, index, str):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        # await ctx.send('You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.')
    else:
        output = net_connect.send_command(f'banner motd # {str} #')
        await ctx.send('```Banner has been set!```')
        net_connect.disconnect()

@bot.command()
async def create_vlan(ctx, index, id):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        # await ctx.send('You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.')
    else:
        configs = ['vlan ' + id]
        net_connect.send_config_set(configs)
        await ctx.send(f'```VLAN {id} created.```')
        net_connect.disconnect()

@bot.command()
async def vlan_ip_add(ctx, index, vlan, ip_addr, netmask):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        # await ctx.send('You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.')
    else:
        configs = ['int ' + vlan,
                   'ip add ' + ip_addr + ' ' + netmask]
        net_connect.send_config_set(configs)
        await ctx.send(f'```IP Address {ip_addr} and Subnet Mask {netmask} has been added to VLAN {vlan}.```')
        net_connect.disconnect()

@bot.command()
async def vlan_no_shut(ctx, index, id):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        # await ctx.send('You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.')
    else:
        configs = ['vlan ' + id,
                   'no sh']
        net_connect.send_config_set(configs)
        await ctx.send(f'```No shutdown VLAN {id} succeed.```')
        net_connect.disconnect()

@bot.command()
async def delete_vlan(ctx, index, id):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        configs = ['no vlan ' + id]
        net_connect.send_config_set(configs)
        await ctx.send(f'```VLAN {id} has been deleted.```')
        net_connect.disconnect()

@bot.command()
async def int_ip_add(ctx, index, interface, ip, mask):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        configs = ['int ' + interface,
                   'no ip add',
                   'ip add ' + ip + ' ' + mask]
        net_connect.send_config_set(configs)
        await ctx.send(f'```IP Address {ip} and Subnet Mask {mask} has been added to Interface {interface}```')
        net_connect.disconnect()

@bot.command()
async def add_gateway(ctx, index, ip_gateway):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        # await ctx.send('You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.')
    else:
        configs = ['ip default-gateway ' + ip_gateway]
        net_connect.send_config_set(configs)
        await ctx.send(f'```IP Default Gateway {ip_gateway} has been set on the device.```')
        net_connect.disconnect()

@bot.command()
async def delete_gateway(ctx, index, ip_gateway):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        configs = ['no ip default-gateway ' + ip_gateway]
        net_connect.send_config_set(configs)
        await ctx.send(f'```IP Default Gateway {ip_gateway} has been deleted.```')
        net_connect.disconnect()

@bot.command()
async def int_switch_mode(ctx, index, interface, mode):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        # await ctx.send('You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.')
    else:
        mode = mode.lower()
        configs = ['int ' + interface,
                       'switchport mode ' + mode]
        net_connect.send_config_set(configs)
        if mode == 'access':
            await ctx.send(f'```Changed {interface} to switchport mode access successfully!```')
        elif mode == 'trunk':
            await ctx.send(f'```Changed {interface} to switchport mode trunk successfully!```')
        net_connect.disconnect()

@bot.command()
async def int_no_shut(ctx,index, interface):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        # await ctx.send('You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.')
    else:
        configs = ['int ' + interface,
                   'no shut']
        net_connect.send_config_set(configs)
        await ctx.send(f'```Interface {interface} is now no shutdown.```')
        net_connect.disconnect()

@bot.command()
async def int_shut(ctx,index, interface):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
        # await ctx.send('You need to connect to a device first!\n\nUse !connect <ip> <username> <password> to connect to a device.')
    else:
        configs = ['int ' + interface,
                   'shut']
        net_connect.send_config_set(configs)
        await ctx.send(f'```Interface {interface} is now shuted down.```')
        net_connect.disconnect()

@bot.command()
async def ospf(ctx, index, networks):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        commands = ospf(networks)
        output = net_connect.send_config_set(commands)
        if 'Invalid' in output:
            embed = discord.Embed(title="Error", color=0xff0000)
            embed.add_field(name="", value="Invalid input!", inline=False)
            embed.add_field(name="", value="Usage: **!ospf <network_ip/netmask(1-32)/area,network_ip2/netmask2(1-32)/area2>**.", inline=False)
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value="OSPF has been configured with the following configuration", inline=False)
        for command in commands:
            if "network" in command:
                ip = command.split(' ')[1]
                wildcard = command.split(' ')[2]
                area = command.split(' ')[4]
                embed.add_field(name="Network", value=ip, inline=False)
                embed.add_field(name="Wildcard", value=wildcard, inline=False)
                embed.add_field(name="Area", value=area, inline=False)
                embed.add_field(name="", value="----------------------", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()

@bot.command()
async def remove_ospf_nw(ctx, index, networks):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        commands = remove_ospf_nw(networks)
        output = net_connect.send_config_set(commands)
        if 'in' in output:
            embed = discord.Embed(title="Error", color=0xff0000)
            embed.add_field(name="", value="Invalid input!", inline=False)
            embed.add_field(name="", value="Usage: **!remove_ospf_nw <network_ip/netmask(1-32)/area,network_ip2/netmask2(1-32)/area2>**.", inline=False)
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value="The following OSPF networks has been removed.", inline=False)
        for command in commands:
            if "network" in command:
                ip = command.split(' ')[1]
                area = command.split(' ')[4]
                embed.add_field(name="Network", value=ip + " Area: " + area, inline=False)
                embed.add_field(name="", value="----------------------", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()

@bot.command()
async def disable_ospf(ctx, index):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return

    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        commands = disable_ospf()
        output = net_connect.send_config_set(commands)
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value="OSPF has been disabled.", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()

@bot.command()
async def show_ospf(ctx, index):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return

    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        output = net_connect.send_command('show ip ospf neighbor')
        await ctx.send('```'+output+'```')
        net_connect.disconnect()

@bot.command()
async def rip(ctx, index, networks):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        commands = rip(networks)
        print(commands)
        output = net_connect.send_config_set(commands)
        if 'Invalid' in output:
            embed = discord.Embed(title="Error", color=0xff0000)
            embed.add_field(name="", value="Invalid input!", inline=False)
            embed.add_field(name="", value="Usage: **!rip <network_ip,network_ip2>**.", inline=False)
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value="RIP has been configured with the following configuration", inline=False)
        for command in commands:
            if "network" in command:
                ip = command.split(' ')[1]
                embed.add_field(name="Network", value=ip, inline=False)
                embed.add_field(name="", value="----------------------", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()

@bot.command()
async def remove_rip_nw(ctx, index, networks):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return

    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        commands = remove_rip_nw(networks)
        output = net_connect.send_config_set(commands)
        if 'in' in output:
            embed = discord.Embed(title="Error", color=0xff0000)
            embed.add_field(name="", value="Invalid input!", inline=False)
            embed.add_field(name="", value="Usage: **!remove_rip_nw <network_ip,network_ip2>**.", inline=False)
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value="The following RIP networks has been removed.", inline=False)
        for command in commands:
            if "network" in command:
                ip = command.split(' ')[1]
                embed.add_field(name="Network", value=ip, inline=False)
                embed.add_field(name="", value="----------------------", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()

@bot.command()
async def disable_rip(ctx, index):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return

    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        commands = disable_rip()
        output = net_connect.send_config_set(commands)
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value="RIP has been disabled.", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()

@bot.command()
async def show_rip(ctx, index):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return

    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        output = net_connect.send_command('show ip route')
        await ctx.send('```'+output+'```')
        net_connect.disconnect()

@bot.command()
async def eigrp(ctx, index, networks, asn):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        commands = eigrp(networks, asn)
        output = net_connect.send_config_set(commands)
        if 'Invalid' in output:
            embed = discord.Embed(title="Error", color=0xff0000)
            embed.add_field(name="", value="Invalid input!", inline=False)
            embed.add_field(name="", value="Usage: **!eigrp <network_ip/netmask(1-32),network_ip2/netmask2(1-32)> <as>**.", inline=False)
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value="EIGRP has been configured with the following configuration", inline=False)
        embed.add_field(name="AS Number", value=asn, inline=False)
        embed.add_field(name="", value="", inline=False)
        for command in commands:
            if "network" in command:
                ip = command.split(' ')[1]
                mask = command.split(' ')[2]
                embed.add_field(name="Network", value=ip, inline=False)
                embed.add_field(name="Subnet Mask", value=mask, inline=False)
                embed.add_field(name="", value="----------------------", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()

@bot.command()
async def remove_eigrp_nw(ctx, index, networks, asn):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return

    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        commands = remove_eigrp_nw(networks, asn)
        output = net_connect.send_config_set(commands)
        if 'Invalid' in output:
            embed = discord.Embed(title="Error", color=0xff0000)
            embed.add_field(name="", value="Invalid input!", inline=False)
            embed.add_field(name="", value="Usage: **!remove_eigrp_nw <network_ip/netmask(1-32),network_ip2/netmask2(1-32)> <as>**.", inline=False)
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value="The following EIGRP networks has been removed.", inline=False)
        for command in commands:
            if "network" in command:
                ip = command.split(' ')[1]
                mask = command.split(' ')[2]
                embed.add_field(name="Network", value=ip, inline=False)
                embed.add_field(name="Subnet Mask", value=mask, inline=False)
                embed.add_field(name="", value="----------------------", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()

@bot.command()
async def disable_eigrp(ctx, index, asn):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return

    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        commands = disable_eigrp(asn)
        output = net_connect.send_config_set(commands)
        if 'Invalid' in output:
            embed = discord.Embed(title="Error", color=0xff0000)
            embed.add_field(name="", value="Invalid input!", inline=False)
            embed.add_field(name="", value="Usage: **!disable_eigrp <as>**.", inline=False)
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value="EIGRP has been disabled.", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()

@bot.command()
async def show_eigrp(ctx, index, asn):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return

    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        output = net_connect.send_command('show ip eigrp neighbor')
        await ctx.send('```'+output+'```')
        net_connect.disconnect()

@bot.command()
async def bgp(ctx, index, networks, neighbors, asn):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return

    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        commands = bgp(networks, neighbors, asn)
        output = net_connect.send_config_set(commands)
        if 'Invalid' in output:
            embed = discord.Embed(title="Error", color=0xff0000)
            embed.add_field(name="", value="Invalid input!", inline=False)
            embed.add_field(name="", value="Usage: **!bgp <network_ip/netmask(1-32),network_ip2/netmask2(1-32)> <neighbor_ip/neighbor_as> <as>**.", inline=False)
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value="BGP has been configured with the following configuration", inline=False)
        embed.add_field(name="AS Number", value=asn, inline=False)
        embed.add_field(name="", value="", inline=False)
        embed.add_field(name="---Networks---", value="", inline=False)
        for command in commands:
            if "network" in command:
                ip = command.split(' ')[1]
                mask = command.split(' ')[2]
                embed.add_field(name="Network", value=ip, inline=False)
                embed.add_field(name="Subnet Mask", value=mask, inline=False)
                embed.add_field(name="", value="----------------------", inline=False)
        embed.add_field(name="---Neighbors---", value="", inline=False)
        for command in commands:
            if "neighbor" in command:
                neighbor = command.split(' ')[1]
                neighbor_asn = command.split(' ')[3]
                embed.add_field(name="Neighbor", value=neighbor, inline=False)
                embed.add_field(name="Neighbor ASN", value=neighbor_asn, inline=False)
                embed.add_field(name="", value="----------------------", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()

@bot.command()
async def remove_bgp_nw(ctx, index, networks, asn):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return

    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        commands = remove_bgp_nw(networks, asn)
        output = net_connect.send_config_set(commands)
        if 'Invalid' in output:
            embed = discord.Embed(title="Error", color=0xff0000)
            embed.add_field(name="", value="Invalid input!", inline=False)
            embed.add_field(name="", value="Usage: **!remove_bgp_nw <network_ip/netmask(1-32),network_ip2/netmask2(1-32)> <as>**.", inline=False)
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value="The following BGP networks has been removed.", inline=False)
        for command in commands:
            if "network" in command:
                ip = command.split(' ')[1]
                mask = command.split(' ')[2]
                embed.add_field(name="Network", value=ip, inline=False)
                embed.add_field(name="Subnet Mask", value=mask, inline=False)
                embed.add_field(name="", value="----------------------", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()

@bot.command()
async def remove_bgp_neighbor(ctx, index, neighbors, asn):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return

    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        commands = remove_bgp_neighbor(neighbors, asn)
        output = net_connect.send_config_set(commands)
        if 'Invalid' in output:
            embed = discord.Embed(title="Error", color=0xff0000)
            embed.add_field(name="", value="Invalid input!", inline=False)
            embed.add_field(name="", value="Usage: **!remove_bgp_neighbor <neighbor_ip/neighbor_as> <as>**.", inline=False)
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value="The following BGP neighbors has been removed.", inline=False)
        for command in commands:
            if "neighbor" in command:
                neighbor = command.split(' ')[1]
                neighbor_asn = command.split(' ')[3]
                embed.add_field(name="Neighbor", value=neighbor, inline=False)
                embed.add_field(name="Neighbor ASN", value=neighbor_asn, inline=False)
                embed.add_field(name="", value="----------------------", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()

@bot.command()
async def disable_bgp(ctx, index, asn):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return

    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        commands = disable_bgp(asn)
        output = net_connect.send_config_set(commands)
        if 'Invalid' in output:
            embed = discord.Embed(title="Error", color=0xff0000)
            embed.add_field(name="", value="Invalid input!", inline=False)
            embed.add_field(name="", value="Usage: **!disable_bgp <as>**.", inline=False)
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value="BGP has been disabled.", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()

@bot.command()
async def show_bgp(ctx, index, asn):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return

    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        output = net_connect.send_command('show ip bgp summary')
        await ctx.send('```'+output+'```')
        net_connect.disconnect()


@bot.command()
async def show_mac_table(ctx, index):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return

    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        output = net_connect.send_command('show mac-address-table')
        await ctx.send('```'+output+'```')
        net_connect.disconnect()
        
@bot.command()
async def show_cdp_neighbors(ctx, index):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return

    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        output = net_connect.send_command('show cdp neighbors')
        await ctx.send('```'+output+'```')
        net_connect.disconnect()

@bot.command()
async def int_ip_delete(ctx, index, interface):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return

    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        command_list = ['int ' + interface,
                        'no ip address']
        output = net_connect.send_config_set(command_list)
        if 'Invalid' in output:
            embed = discord.Embed(title="Error", color=0xff0000)
            embed.add_field(name="", value="Invalid input!", inline=False)
            embed.add_field(name="", value="Usage: **!int_ip_delete <device_index> <interface>**.", inline=False)
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value="The IP Address has been removed from the interface.", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()

@bot.command()
async def vlan_shut(ctx, index, vlan_id):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return

    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return

    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        command_list = ['int vlan ' + vlan_id,
                        'shut']
        output = net_connect.send_config_set(command_list)
        if 'Invalid' in output:
            embed = discord.Embed(title="Error", color=0xff0000)
            embed.add_field(name="", value="Invalid input!", inline=False)
            embed.add_field(name="", value="Usage: **!vlan_shut <device_index> <vlan_id>**.", inline=False)
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value="The VLAN " + vlan_id + " has been shutdown.", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()

@bot.command()
async def router_on_a_stick(ctx, index, interface, vlan_id, ip_address, subnet_mask):
    global net_connect
    discord_username = str(ctx.author)
    key = f"{discord_username}:{index}"
    if key not in connections:
        no_index_exists()
        return
    
    try:
        net_connect = await connect(ctx, index)
    except:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="Failed to connect to the device.", inline=False)
        return
    
    if net_connect == None:
        embed = discord.Embed(title="Error", color=0xff0000)
        embed.add_field(name="", value="You need to connect to a device first!", inline=False)
        embed.add_field(name="", value="Use **!create_connection <ip> <username> <password>** to connect to a device.", inline=False)
    else:
        command_list = ['int ' + interface,
                        'no shut',
                        'exit',
                        'int ' + interface + '.' + vlan_id,
                        'encapsulation dot1Q ' + vlan_id,
                        'ip address ' + ip_address + ' ' + subnet_mask,]
        output = net_connect.send_config_set(command_list)
        if 'Invalid' in output:
            embed = discord.Embed(title="Error", color=0xff0000)
            embed.add_field(name="", value="Invalid input!", inline=False)
            embed.add_field(name="", value="Usage: **!router_on_a_stick <device_index> <interface> <vlan_id> <ip_address> <subnet_mask>**.", inline=False)
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(title="Success", color=0x00ff00)
        embed.add_field(name="", value="Router on a stick has been configured.", inline=False)
        await ctx.send(embed=embed)
        net_connect.disconnect()


    
bot.run(TOKEN)


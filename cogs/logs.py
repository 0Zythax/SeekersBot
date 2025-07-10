import discord, os, pytesseract, json, asyncio, pygsheets, random
from discord.ext import commands
from PIL import Image, ImageOps
from thefuzz import process

validTesseractExtensions = ["png", "jpeg"]

def readJSON(file):
    io = open(file, "r")
    output = json.load(io)
    io.close()
    return output

def extractIndexes(data):
    result = []
    for value in data:
        result.append(value)
    return result

# tesseract check function
def validExtension(attachment : discord.Attachment):
    isValid = False
    for extension in validTesseractExtensions:
        if attachment.filename.endswith(extension):
            print(f"attachment is {extension}")
            isValid = True
    return isValid

class logs(commands.Cog):
    # reads config on cog init and sets variables ig
    def __init__(self, bot):
        self.bot : commands.Bot = bot
        self.itemData = readJSON("./items.json")
        self.items = extractIndexes(self.itemData)
        self.botInitalized = False

        # bot stuff
        self.botLogChannel = None
        self.reactionMessage = None
        self.guild = None
        self.ticketCategory = None
        self.discordCDN = None

        # gsheets
        self.gsheetsClient = None
        self.spreadsheet = None
        self.rostersheet : pygsheets.Worksheet = None

    async def fetchUserFromString(self, string):
        user = None
        try: 
            if string.startswith("<@") and string.endswith(">"): user = self.guild.get_member(int(string[2:-1]))
            else: user = self.guild.get_member(int(string))
        except Exception: return False
        return user

    async def getUserTicket(self, member : discord.Member):
        if self.ticketCategory == None: print("there is literally no ticket channel what do you want to me say");return True
        for channel in self.ticketCategory.channels:
            if int(channel.name) == int(member.id):
                return channel
        return None
    
    async def findCell(self, n):
        cell = None
        cells = self.rostersheet.range("A:F", returnas="cells")
        for cellRow in cells:
            for selectedCell in cellRow:
                if str(n) == selectedCell.value:
                    cell = selectedCell
        return cell
    
    async def makeTicketChannel(self, member):
        # make channel
        nticketChannel : discord.TextChannel = await self.guild.create_text_channel(
            name = str(member.id), 
            category = self.ticketCategory, 
            reason = ""
        );
        overwrite = discord.PermissionOverwrite();
        overwrite.read_messages = True;
        overwrite.send_messages = True;
        overwrite.read_message_history = True;
        overwrite.attach_files = True;
        await nticketChannel.set_permissions(self.guild.default_role, read_messages = False)
        await nticketChannel.set_permissions(member, overwrite = overwrite)
        return nticketChannel
    
    async def formatFields(self, embed, fields, per):
        z = 0
        for name, value in fields.items():
            embed.add_field(name = name, value = value, inline = z%(per+1) == 0)

    # this is a hack
    @commands.Cog.listener()
    async def on_ready(self):
        try:
            await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name='logs & commands'))
            if self.botInitalized: return
            print("validating configuration & setting variables")
            configuration = readJSON("./config.json")
            guild = self.bot.get_guild(int(configuration["guildID"]))
            if guild == None: print("bot is not in guild set in config.json");input();exit()
            self.guild = guild
            category = self.guild.get_channel(int(configuration["ticketCategoryID"]))
            if category == None: print("can't find set ticket category in set guild");input();exit()
            self.ticketCategory = category
            channel = self.bot.get_channel(int(configuration["botLogChannelID"]))
            if channel == None: print("can't find cdn channel");input();exit()
            self.discordCDN = channel
            channel = self.guild.get_channel(int(configuration["botLogChannelID"]))
            if channel == None: print("can't find set manual review channel in set guild");input();exit()
            self.botLogChannel = channel
            self.botInitalized = True
            if configuration["reactionMessageChannelID"] != 0 and configuration["reactionMessageID"] != 0:
                channel = self.guild.get_channel(int(configuration["reactionMessageChannelID"]))
                if channel == None: print("warning: reaction message cfg broken, please rerun the setup command\nconfig partially broken");return
                message = await channel.fetch_message(int(configuration["reactionMessageID"]))
                if message == None: return # i don't know why i made this check if it can't find the message it errors anyways 😂
                self.reactionMessage = message
            print("logging into service account & verifying ownership")
            self.gsheetsClient = pygsheets.authorize(service_account_file = "./serviceaccount.json")
            self.spreadsheet = self.gsheetsClient.open("Seekers Roster v2")
            self.rostersheet = self.spreadsheet.worksheet("title", "Roster")
            print(f"init complete, logged into {self.bot.user} successfully")
        except Exception as error:
            print(error)
            print("an error has occured, the bot cannot start-up");input();exit();
    
    @commands.command()
    @commands.cooldown(1, 30, commands.BucketType.guild)
    @commands.has_role("[SEEKERS COMMAND]")
    async def event(self, interaction : discord.Interaction, globalPoints : float):
        timedOut = False
        caller = interaction.message.author
        pointsToGive = {} 

        logTextFileName = f"./{caller.id}-{random.randint(9,99999999)}.txt"
        logTextFile = open(f"./logs/{logTextFileName}", "a+")

        def check(message):
            return message.author.id == caller.id
        
        async def responce():
            try: responceMessage = await self.bot.wait_for("message", check = check, timeout = 30)
            except asyncio.TimeoutError: return None
            responce = responceMessage.content
            return responce

        if caller.voice == None: await interaction.message.reply("You are not in an voice call."); return
        for member in caller.voice.channel.members:
            pointsToGive[member] = globalPoints

        while True:
            embed = discord.Embed()
            embed.title = "Event Panel"
            embed.description = "The users below will recieve however points was listed.\n Say 'modify' to add or edit an entry, say 'remove' to remove an entry, say 'cancel' to cancel this prompt, say 'done' to confirm this prompt."
            await self.formatFields(embed, pointsToGive, 3)
            await interaction.message.channel.send(embed = embed)

            input = await responce()
            if input == None: timedOut = True; break

            match input:
                case "modify":
                    await interaction.channel.send("Mention or state the userid of the member you want to add/edit.")
                    input = await responce()
                    if input == None: timedOut = True; break
                    user = await self.fetchUserFromString(input)
                    if user == None or False: await interaction.channel.send("Failed to find that user, please try again!"); continue

                    await interaction.channel.send("How many points should they recieve?")
                    input = await responce()
                    if input == None: timedOut = True; break
                    try: float(input) 
                    except Exception: await interaction.channel.send("Failed to convert, please only insert numbers."); continue
                    pointsToGive[user] = float(input)
                    logTextFile.write(f"Modified/added {user.name} {user.id} -> {input} pts")
                case "remove":
                    await interaction.channel.send("Mention or state the userid of the member you want to remove from the list.")
                    input = await responce()
                    if input == None: timedOut = True; break
                    user = await self.fetchUserFromString(input)
                    if user == None or False: await interaction.channel.send("Failed to find that user, please try again!"); continue
                    if pointsToGive[user] == None: await interaction.channel.send("Not on the list."); continue
                    pointsToGive.pop(user)
                    logTextFile.write(f"Removed {user.name} {user.id} from list\n")
                case "cancel":
                    timedOut = True
                    break
                case "done":
                    break
                case _:
                    await interaction.channel.send("Invalid command.")
                    continue
        
        if timedOut:
            await interaction.channel.send("Timed-out. Please try again.")
            return
        
        failed = 0
        for member, points in pointsToGive.items():
            try:
                cell = await self.findCell(member.id)
                cell = self.rostersheet.cell(f"B{cell.row}")
                cell.set_value(f"{float(points) + float(cell.value)}")
                cell = self.rostersheet.cell(f"D{cell.row}")
                cell.set_value(f"{1 + int(cell.value)}")
                logTextFile.write(f"Gave {member.name} {member.id} {points} points\n")
            except Exception as error:
                failed += 1
                logTextFile.write(f"Couldn't give {member.name} {member.id} points {points}, {error}\n")

        await interaction.channel.send(f"Done! Failed: {failed}.")

        logTextFile.close()
        embed = discord.Embed()
        embed.title = f"Audit log from {caller.name} {caller.id}"
        embed.description = f"!event command ran"
        await self.botLogChannel.send(embed = embed, file = discord.File(f"./logs/{logTextFileName}", "auditlog.txt"))

        if os.path.isfile(f"./logs/{logTextFileName}"): 
            os.remove(f"./logs/{logTextFileName}")

    @commands.command()
    @commands.cooldown(1, 8, commands.BucketType.user)
    @commands.has_role("[SEEKERS COMMAND]")
    async def points(self, interaction : discord.Interaction, user, *, points):
        message = interaction.message;

        # get user
        user = await self.fetchUserFromString(user)
        if user == False: return message.reply("Invalid argument.")
        if user == None: return message.reply("Couldn't find user.")
        
        # set
        try:
            cell = await self.findCell(user.id)
            cell = self.rostersheet.cell(f"B{cell.row}")
            oldv = cell.value
            cell.set_value(f"{float(points) + float(cell.value)}")
            await message.reply(f"Gave {user.name} {points} points ({oldv} -> {cell.value})")
        except Exception as error:
            print(error)
            await message.reply(f"An unexpected error has occured with the service account.")

    @commands.command()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def view(self, interaction : discord.Interaction):
        message = interaction.message;
        user = message.author;
        cell = await self.findCell(user.id)
        points = self.rostersheet.cell(f"B{cell.row}")
        eventsAttended = self.rostersheet.cell(f"D{cell.row}")
        embed = discord.Embed()
        embed.title = f"{user.name} {user.id}"
        embed.add_field(name = "Points", value = str(points.value))
        embed.add_field(name = "Events Attended", value = str(eventsAttended.value))
        await message.reply(embed = embed)

    # Never finished this function lol
    # Never finished this function lol
    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_role("[SEEKERS COMMAND]")
    async def adduser(self, interaction : discord.Interaction, *, user):
        message = interaction.message

        user = await self.fetchUserFromString(user)
        if user == False: return message.reply("Invalid argument.")
        if user == None: return message.reply("Couldn't find user.")
        message = await message.reply("Creating entry (this may take a while...) [0]")

        i = 0
        top : pygsheets.Cell = await self.findCell("Trailers | T-LR")
        selrow = top.row + 1
        self.rostersheet.insert_rows(row = top.row + 1, number = 1, values = [[user.name, 0, str(user.id), 0, "FALSE", "FALSE"]])
        todesign = self.rostersheet.range(f"A{selrow}:F{selrow}", returnas = "cells")
        for cell in todesign[0]:
            i+=1
            await asyncio.sleep(1)
            cell : pygsheets.Cell = cell
            cell.set_vertical_alignment(pygsheets.VerticalAlignment.MIDDLE)
            await message.edit(content = f"Creating entry (this may take a while...) [{i} - {len(todesign[0])}]")

    @commands.command()
    @commands.cooldown(1, 60, commands.BucketType.user)
    @commands.has_role("[SEEKERS COMMAND]")
    async def setup(self, interaction : discord.Interaction, *, id = 0):
        message = interaction.message;

        # checks
        if not self.botInitalized: await message.reply("The bot has not initalized successfully so this command cannot be ran, please contact Zythax to resolve this issue.");return
        if id == 0 or id == None: await message.reply("This is not a valid ID.");return
        try:int(id)
        except ValueError: await message.reply("This is not a valid ID.");return
        channel = self.guild.get_channel(int(id))
        if channel == None: await message.reply("This channel does not exist / is not in this guild.");return

        # make message
        embed = discord.Embed()
        embed.color = discord.Color.blue()
        embed.title = "Log Hub"
        embed.description = "📦 -> Item\nOnly open a ticket based on what you are logging, use the legend above to know what reaction to react with."
        embed.footer.text = "Created by 0Zythax/Zythax for the Smugglers sub-faction, Seekers."
        reactMessage = await channel.send(embed = embed)
        await reactMessage.add_reaction("📦")

        # save
        modifiedConfiguration = readJSON("./config.json")
        modifiedConfiguration["reactionMessageChannelID"] = reactMessage.channel.id
        modifiedConfiguration["reactionMessageID"] = reactMessage.id
        self.reactionMessage = reactMessage
        ioSession = open("./config.json", "w")
        json.dump(modifiedConfiguration, ioSession)
        ioSession.close()

        await message.reply("done")

    @commands.command()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def help(self, interaction : discord.Interaction):
        await interaction.message.reply("<#1376303121575313558>")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event : discord.RawReactionActionEvent):
        if self.reactionMessage != None and self.ticketCategory != None and event.message_id == self.reactionMessage.id:
            
            # check for existing ticket, remove reaction
            member = self.guild.get_member(event.user_id)
            await self.reactionMessage.remove_reaction(event.emoji, member)
            existingTicket = await self.getUserTicket(member)
            if existingTicket != None: await member.send("You already have an existing ticket!");return

            try:
                cell = await self.findCell(member.id)
                cell = self.rostersheet.cell(f"B{cell.row}")
            except Exception as error:
                print(error)
                await member.send(f"Cannot find your cell on the spreadsheet. Please contact an HR to resolve this issue. {error}")

            # start new audit log and channel
            logTextFileName = f"./{member.id}-{random.randint(9,99999999)}.txt"
            logTextFile = open(f"./logs/{logTextFileName}", "a+")
            ticketChannel = await self.makeTicketChannel(member)

            # checks defs
            def memberMessageCheck(message : discord.Message):
                return message.author.id == member.id
            def messageIsInTicket(message : discord.Message):
                return message.channel.id == ticketChannel.id and message.author.id == member.id

            # start item log
            if event.emoji.name == "📦":
                timedout = False
                awarded = 0

                # send notification to start making stuf , ,
                await ticketChannel.send(f"{member.mention}\nYou have opened a ticket for logging items. Please begin to post your screenshots.")

                # screenshot loop
                while True:
                    memberMessage = None
                    manualReviewRequired = False
                        
                    # waits for a responce (attachment or a message)
                    try: memberMessage : discord.Message = await self.bot.wait_for("message", check = memberMessageCheck, timeout = 60)
                    except asyncio.TimeoutError: break # we are timed out, break out of the screenshot loop and set state
                    if memberMessage.content.lower() == "done": break # break out of the screenshot loop
                    if len(memberMessage.attachments) != 1: await memberMessage.reply("Please send an attachment (not a link) (one per message) or say 'done' (without the quotation marks) to close/complete this ticket."); continue
                    
                    # get attachment, check attachment
                    attachment = memberMessage.attachments[0]
                    if not validExtension(attachment): await memberMessage.add_reaction("❌"); continue

                    try:
                        # try to save the attachment, edit it, read it and get a result
                        await attachment.save(f"./imgs/{attachment.filename}")
                        oldimage = open(f"./imgs/{attachment.filename}", "rb")
                        imagedata = await self.discordCDN.send(content = f"Image from {member.name} {member.id}", file = discord.File(oldimage))
                        imagedata = imagedata.attachments[0]
                        image = Image.open(f"./imgs/{attachment.filename}")
                        oldSize = image.size
                        dimentions = ( ( oldSize[0] * 70 ) / 100, 20, 10, ( oldSize[1] * 70 ) / 100)    # top, left, right, bottom
                        image = ImageOps.crop(image, dimentions)
                        image.save(f"./imgs/{attachment.filename}")
                        content = pytesseract.image_to_string(image)
                        result = process.extractBests(query = content.lower(), choices = self.items, score_cutoff = 40)
                        logData = None

                        # nothing detected lmfao
                        if len(result) == 0:
                            res = None
                            # add question mark
                            await ticketChannel.send("The bot could not read this image, would you like for this image to be reviewed by a High Ranking? Please say 'review' in chat to confirm or say anything else to dismiss.")
                            try: res = await self.bot.wait_for("message", check = messageIsInTicket, timeout = 60) # wait for responce
                            except asyncio.TimeoutError: await ticketChannel.send(f"{member.mention} Automatically dismissed, if you want to change your mind, resubmit the screenshot."); continue # timed out, ignore
                            if res != None and res.content.lower() == 'review':  # if message sent is 'review'
                                await ticketChannel.send("Sent for review.")
                                manualReviewRequired = True
                            else: continue
                        # more than 1 result
                        elif len(result) >= 2:
                            valid = []
                            responce = None
                            resultEmbed = discord.Embed()
                            resultEmbed.title = "Multiple items detected."
                            resultEmbed.description = "State which item was detected from the results below. If the item is none of the results below then you can say 'review' to get this screenshot reviewed by a High Ranking."
                            # populate embed, set valid options for responce
                            for resultData in result:
                                resultEmbed.add_field(name = resultData[0], value = f"{resultData[1]}%")
                                valid.append(resultData[0])
                            await ticketChannel.send(embed = resultEmbed)
                            # loop for responce, breaks upon valid answer
                            while True:
                                try: responce = await self.bot.wait_for("message", check = messageIsInTicket, timeout = 30)
                                except asyncio.TimeoutError: timedout = True; break # yk the drill, cancel everything
                                if responce.content.lower() in valid: break # break out of this loop
                                elif responce.content.lower() == 'review': manualReviewRequired = True; await memberMessage.add_reaction("🟡"); break # break out of this loop and set state to manual review
                            if timedout: break # break out of the screenshot loop since we got timed out from the previous responce
                            if not manualReviewRequired: # no manual review required? checkmark and set logdata to that
                                logTextFile.write(f"{imagedata.url} -> User said this is {responce.content.lower()} from multi-selection. \n")
                                logData = self.itemData[responce.content.lower()]
                                await memberMessage.add_reaction("✅")
                        elif len(result) == 1:
                            # only 1 responce
                            logData = self.itemData[result[0][0]]
                            logTextFile.write(f"{imagedata.url} -> Detected {logData['name']}. \n")
                            await memberMessage.add_reaction("✅")
                        
                        # add to detected items, screenshot checking done
                        if logData != None:
                            try:
                                cell.set_value(f"{float(logData['value']) + float(cell.value)}")
                                awarded += logData['value']
                            except Exception as e:
                                await ticketChannel.send(f"Failed to award points. {e}")
                                logTextFile.write(f"An error occured with the GService account. - {error}")
                            
                    # if an error has occured when checking, flag an error and redo screenshot loop
                    except Exception as error: 
                        logTextFile.write(f"An error has occured in the screenshot loop. - {error}\n")
                        await memberMessage.add_reaction("❌")
                        await ticketChannel.send(f'An unexpected error has occured. {error}')
                        continue
                    
                    # if the item needed a manual review
                    if manualReviewRequired:
                        try:
                            # try to send a embed to bot log channel
                            embed = discord.Embed()
                            embed.title = "Manual log review required for user."
                            embed.description = f"{member.name} wants to log the following item, but the OCR couldn't detect it."
                            await self.botLogChannel.send(embed = embed, content = imagedata.url)
                        except Exception as error:
                            # if an error occurs log it since we should be able to send there
                            logTextFile.write(f"An error has occured when sending an item for review. - {error}\n")
                            await ticketChannel.send(f"An unexpected error has occured when attempting to send this off for manual review. {error}")
                    
                    # remove the screenshot since we're done with it
                    oldimage.close()
                    if os.path.isfile(f"./imgs/{attachment.filename}"): 
                        os.remove(f"./imgs/{attachment.filename}")

                logTextFile.close()
                embed = discord.Embed()
                embed.title = f"Audit log from {member.name} {member.id}."
                embed.description = f"Awarded {awarded} points."
                embed.color = discord.Color.blue()
                await self.botLogChannel.send(embed = embed, file = discord.File(f"./logs/{logTextFileName}"))
                if os.path.isfile(f"./logs/{logTextFileName}"): 
                    os.remove(f"./logs/{logTextFileName}")

                # if we got timed out then just cancel the ticket, remove it, etc
                if timedout:
                    await ticketChannel.send("Closing due to inactivity...")
                    await member.send(content = "Ticket closed due to inactivity.")
                    asyncio.sleep(5)
                    await ticketChannel.delete(reason = "Timed out.")
                    return
                else:
                    await ticketChannel.send("Closing ticket...")
                    await asyncio.sleep(5)
                    await ticketChannel.delete(reason = "Ticket done.")

def setup(bot : commands.Bot):
    return bot.add_cog(logs(bot))

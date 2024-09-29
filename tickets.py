### Importações necessárias
import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput, Select
from datetime import datetime
import pytz
import asyncio
import uuid
import io

### Declara as intenções do bot
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

### Config de canais, categorias e imagens
IMAGE = ''

CHANNEL_START = 123
TRANSCRIPT_CHANNEL_ID = 123
FEEDBACK_CHANNEL_ID = 123
HTML_CHANNEL_ID = 123

# Politico = Staff 
POLITICO_ROLE_ID = 123

CATEGORY_NAME = "tickets"

CATEGORY_NAMES = {
    "Assuntos Financeiros": "💰・",
    "Assuntos Gerais": "📝・",
    "Suspeita de Hack": "👻・",
    "Denunciar Jogador": "🚫・",
    "Reportar um Bug": "🐞・",
    "Denunciar Staff": "⚠️・",
    "Criador de conteúdo": "📸・",
}

ticket_code = str(uuid.uuid4())[:6].upper()
ticket_info = {}

local_tz = pytz.timezone('America/Sao_Paulo')

### Classes e funções (Tem função de feedback e criação de transcript)
class FeedbackView(View):
    def __init__(self, ticket_code, politician):
        super().__init__(timeout=180.0)
        self.add_item(FeedbackSelect(ticket_code=ticket_code, politician=politician))

class FeedbackCommentModal(Modal):
    def __init__(self, ticket_code, feedback, interaction_user, politician):
        super().__init__(title="Comentário Adicional")
        self.ticket_code = ticket_code
        self.feedback = feedback
        self.interaction_user = interaction_user
        self.politician = politician

        self.add_item(TextInput(label="Alguma sugestão/comentário?", placeholder="Digite sua sugestão/comentário aqui", style=discord.TextStyle.paragraph, required=False))

    async def on_submit(self, interaction: discord.Interaction):
        comment = self.children[0].value.strip()
        feedback_channel = interaction.client.get_channel(FEEDBACK_CHANNEL_ID)

        color_map = {
            "Excelente": discord.Color.green(),
            "Bom": discord.Color.blue(),
            "Regular": discord.Color.orange(),
            "Ruim": discord.Color.red(),
        }
        color = color_map.get(self.feedback, discord.Color.default())

        if feedback_channel:
            embed = discord.Embed(
                title="Nova avaliação de atendimento recebida",
                color=color
            )
            embed.add_field(name="**Usuário**", value=self.interaction_user.mention, inline=True)
            embed.add_field(name="**Staff responsável**", value=self.politician.mention, inline=True)
            embed.add_field(name="", value='', inline=True)
            embed.add_field(name="**Ticket**", value=f'```{self.ticket_code}```', inline=True)
            embed.add_field(name="**Avaliação**", value=f'```{self.feedback}```', inline=True)
            if comment:
                embed.add_field(name="**Comentário**", value=comment, inline=False)

            await feedback_channel.send(embed=embed)
            await interaction.response.send_message("Obrigado pelo seu feedback!", ephemeral=True)
        else:
            await interaction.response.send_message("Não foi possível encontrar o canal de feedback.", ephemeral=True)

class FeedbackSelect(Select):
    def __init__(self, ticket_code, politician):
        self.ticket_code = ticket_code
        self.politician = politician
        options = [
            discord.SelectOption(label="Excelente", emoji="🌟"),
            discord.SelectOption(label="Bom", emoji="👍"),
            discord.SelectOption(label="Regular", emoji="👌"),
            discord.SelectOption(label="Ruim", emoji="👎"),
        ]
        super().__init__(placeholder="Selecione a avaliação do atendimento...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        feedback = self.values[0]

        await interaction.response.send_modal(FeedbackCommentModal(ticket_code=self.ticket_code, feedback=feedback, interaction_user=interaction.user, politician=self.politician))

class AddUserButton(Button):
    def __init__(self):
        super().__init__(label="➕ Adicionar um usuário", style=discord.ButtonStyle.secondary   , custom_id="add_user", row=1)

    async def callback(self, interaction: discord.Interaction):
        if POLITICO_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("Você não tem permissão para usar este botão.", ephemeral=True)
            return
        
        modal = AddUserModal()
        await interaction.response.send_modal(modal)

class AddUserModal(Modal, title="Adicionar Usuário ao Ticket"):
    def __init__(self):
        super().__init__()
        self.add_item(TextInput(label="ID do Usuário", placeholder="Digite o ID do usuário para adicionar", style=discord.TextStyle.short))

    async def on_submit(self, interaction: discord.Interaction):
        user_input = self.children[0].value.strip()
        guild = interaction.guild
        channel = interaction.channel
        member = None

        if user_input.isdigit():
            member_id = int(user_input)
            member = await guild.fetch_member(member_id)
        else:
            await interaction.response.send_message("ID do usuário inválido. Verifique o ID e tente novamente.", ephemeral=True)
            return

        if member:
            await channel.set_permissions(member, read_messages=True, send_messages=True)
            await interaction.response.send_message(f"{member.mention} adicionado ao ticket `{ticket_code}`.", ephemeral=True)

            try:
                await member.send(f"Olá, **{member.name}**, você foi adicionado ao ticket `{ticket_code}` no canal {channel.mention}.")
            except discord.Forbidden:
                await interaction.followup.send("Não foi possível enviar uma mensagem direta ao usuário.", ephemeral=True)
        else:
            await interaction.response.send_message("Usuário não encontrado. Verifique o ID e tente novamente.", ephemeral=True)

class RemoveUserButton(Button):
    def __init__(self):
        super().__init__(label="➖ Remover Usuário", style=discord.ButtonStyle.secondary, custom_id="remove_user", row=1)

    async def callback(self, interaction: discord.Interaction):
        if POLITICO_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("Você não tem permissão para usar este botão.", ephemeral=True)
            return

        modal = RemoveUserModal()
        await interaction.response.send_modal(modal)

class RemoveUserModal(Modal, title="Remover Usuário do Ticket"):
    def __init__(self):
        super().__init__()
        self.add_item(TextInput(label="ID do Usuário", placeholder="Digite o ID do usuário para remover", style=discord.TextStyle.short))

    async def on_submit(self, interaction: discord.Interaction):
        user_input = self.children[0].value.strip()
        guild = interaction.guild
        channel = interaction.channel
        member = None

        if user_input.isdigit():
            member_id = int(user_input)
            try:
                member = await guild.fetch_member(member_id)
            except discord.NotFound:
                print("Member not found by ID.")
            except discord.HTTPException as e:
                print(f"HTTP Exception: {e}")
        else:
            await interaction.response.send_message("ID do usuário inválido. Verifique o ID e tente novamente.", ephemeral=True)
            return

        if member:
            try:
                await channel.set_permissions(member, read_messages=False, send_messages=False)
                await interaction.response.send_message(f"Usuário {member.mention} removido do ticket.", ephemeral=True)
                
                try:
                    await member.send(f"Olá, **{member.name}**, você foi removido do ticket `{ticket_code}`.")
                except discord.Forbidden:
                    await interaction.followup.send("Não foi possível enviar uma mensagem direta ao usuário.", ephemeral=True)
            except Exception as e:
                print(f"Error setting permissions: {e}")
                await interaction.response.send_message("Ocorreu um erro ao remover o usuário do ticket.", ephemeral=True)
        else:
            await interaction.response.send_message("Usuário não encontrado. Verifique o ID e tente novamente.", ephemeral=True)

class NotifyUserButton(Button):
    def __init__(self):
        super().__init__(label="🔔 Notificar Usuário", style=discord.ButtonStyle.secondary, custom_id="notify_user", row=1)

    async def callback(self, interaction: discord.Interaction):
        if POLITICO_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("Você não tem permissão para usar este botão.", ephemeral=True)
            return

        channel = interaction.channel
        ticket_data = ticket_info.get(channel.id, {})
        user_id = ticket_data.get("opened_by_id")
        
        if not user_id:
            await interaction.response.send_message("Não foi possível identificar o usuário que abriu o ticket.", ephemeral=True)
            return
        
        user = interaction.guild.get_member(user_id)
        
        if user is None:
            try:
                user = await interaction.client.fetch_user(user_id)
            except discord.NotFound:
                user = None
        
        if user:
            try:
                await user.send(f"Olá, **{user.name}**, seu ticket foi atualizado. Por favor, verifique o canal {channel.mention} para mais detalhes.")
                await interaction.response.send_message("O usuário foi notificado com sucesso.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("Não foi possível enviar uma mensagem para o usuário. Verifique se ele não está com mensagens privadas desativadas.", ephemeral=True)
        else:
            await interaction.response.send_message("Usuário não encontrado. Verifique se o usuário ainda está no servidor.", ephemeral=True)

class TicketCloseView(View):
    def __init__(self, ticket_code: str, category: str, subject: str, member: discord.Member):
        super().__init__(timeout=180)
        self.ticket_code = ticket_code
        self.category = category
        self.subject = subject
        self.member = member

        self.add_item(CloseTicketButton(ticket_code=self.ticket_code, category=self.category, subject=self.subject, member=self.member))
        self.add_item(AddUserButton())
        self.add_item(RemoveUserButton())
        self.add_item(NotifyUserButton())

class TicketCloseModal(Modal):
    def __init__(self, ticket_code: str, member: discord.Member, requester: discord.User, category: str, subject: str):
        super().__init__(title="Finalização de Ticket")
        self.ticket_code = ticket_code
        self.member = member
        self.requester = requester
        self.category = category
        self.subject = subject
        self.add_item(TextInput(label="Resolução", placeholder="Digite a resolução do ticket", style=discord.TextStyle.paragraph, required=True))

    ### Cria um transcript do ticket
    async def on_submit(self, interaction: discord.Interaction):
        user = self.requester
        resolution = self.children[0].value.strip()

        if user is None:
            await interaction.response.send_message("Solicitante do ticket não encontrado.", ephemeral=True)
            return

        channel_id = interaction.channel.id
        ticket_data = ticket_info.get(channel_id, {})
        subject = ticket_data.get("subject", "Não especificado")
        category = ticket_data.get("category", "Não especificada")

        transcript_html = io.StringIO()
        transcript_html.write("<html><head><style>")
        transcript_html.write("body { background-color: #36393f; color: #dcddde; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; }")
        transcript_html.write("h1, h3 { color: #dcddde; }")
        transcript_html.write("ul { list-style: none; padding: 0; margin: 0; }")
        transcript_html.write("li { padding: 10px; border-bottom: 1px solid #40444b; display: flex; align-items: flex-start; }")
        transcript_html.write(".message-content { margin-left: 10px; }")
        transcript_html.write(".avatar { border-radius: 50%; width: 40px; height: 40px; }")
        transcript_html.write(".timestamp { color: #72767d; font-size: 12px; }")
        transcript_html.write(".label { color: #7289da; font-weight: bold; }")  #Etiquetas
        transcript_html.write(".value { color: #dcddde; }")  #Valores 
        transcript_html.write("</style></head><body>")
        transcript_html.write(f"<h1><span class='label'>Ticket:</span> <span class='value'>{self.ticket_code}</span></h1>")
        transcript_html.write(f"<h3><span class='label'>Categoria:</span> <span class='value'>{self.category}</span></h3>")
        transcript_html.write(f"<h3><span class='label'>Necessidade apontada:</span> <span class='value'>{self.subject}</span></h3>")
        transcript_html.write(f"<h3><span class='label'>Resolução:</span> <span class='value'>{resolution}</span></h3>")
        transcript_html.write("<ul>")
        
        last_author = None
        buffer = []

        async for message in interaction.channel.history(limit=200, oldest_first=True):
            timestamp = message.created_at.replace(tzinfo=pytz.utc).astimezone(pytz.timezone("America/Sao_Paulo")).strftime("[%H:%M:%S - %d/%m/%Y]")
            author = message.author
            author_name = author.display_name if author else "Desconhecido"
            author_avatar = author.display_avatar.url if author and author.display_avatar else "https://example.com/default_avatar.png"
            content = message.content

            if last_author == author:
                buffer.append(f"<div>{content}</div>")
            else:
                if buffer:
                    transcript_html.write(f"<li><img src='{last_author.display_avatar.url}' alt='Avatar' class='avatar'><div class='message-content'>{''.join(buffer)}</div></li>")
                last_author = author
                buffer = [f"<div class='timestamp'>{timestamp}</div><strong>{author_name}:</strong><div>{content}</div>"]

            if message.attachments:
                for attachment in message.attachments:
                    if attachment.url.lower().endswith(('png', 'jpg', 'jpeg', 'gif')):
                        transcript_html.write(f"<br><img src='{attachment.url}' style='max-width: 100%; height: auto; margin-top: 5px;' alt='Anexo'>")
                    elif attachment.url.lower().endswith(('mp4', 'webm', 'mov')):
                        transcript_html.write(f"<br><video controls style='max-width: 100%; height: auto; margin-top: 5px;'><source src='{attachment.url}' type='video/mp4'></video>")
        
        if buffer:
            transcript_html.write(f"<li><img src='{last_author.display_avatar.url}' alt='Avatar' class='avatar'><div class='message-content'>{''.join(buffer)}</div></li>")

        transcript_html.write("</ul>")
        transcript_html.write("</body></html>")
        
        transcript_html.seek(0)

        transcript_channel = bot.get_channel(TRANSCRIPT_CHANNEL_ID)
        html_channel = bot.get_channel(HTML_CHANNEL_ID)
        if transcript_channel:
            transcript_path = f"ticket_{self.ticket_code}_transcript.html"
            with open(transcript_path, 'w', encoding='utf-8') as file:
                file.write(transcript_html.getvalue())

            with open(transcript_path, 'rb') as file:
                message = await html_channel.send(file=discord.File(fp=file, filename=transcript_path))
                transcript_url = message.attachments[0].url

            embed = discord.Embed(
                title=f"Ticket ```{self.ticket_code}``` Finalizado",
                description=f"[Clique aqui para ver a transcrição online]({transcript_url})",
                color=discord.Color.dark_embed()
            )
            embed.add_field(name="**Staff responsável**", value=self.member.mention, inline=True)
            embed.add_field(name="**Usuário atendido**", value=self.requester.mention, inline=True)
            embed.add_field(name="**Categoria**", value=self.category, inline=False)
            embed.add_field(name="**Necessidade Apontada**", value=self.subject, inline=False)
            embed.add_field(name="**Resolução**", value=f'{resolution}', inline=False)

            await transcript_channel.send(embed=embed)
        else:
            await interaction.response.send_message("Não foi possível encontrar o canal de transcrição.", ephemeral=True)

        embed = discord.Embed(
            description=(
                f"Olá, **{user.name}**, seu ticket de código `{self.ticket_code}` foi finalizado. "
                "Segue abaixo a resolução dele.\n\n"
                f"**Staff que finalizou:** {self.member.mention} ({self.member.name})\n"
                f"**Resolução:** `{resolution}`\n\n"
                "Caso deseje, realize agora uma rápida avaliação do seu atendimento selecionando a opção abaixo."
            ),
            color=discord.Color.dark_embed()
        )
        embed.set_author(name="Sistema de Tickets - Sanja City", icon_url=IMAGE)
        
        feedback_view = FeedbackView(ticket_code=self.ticket_code, politician=self.member)

        await user.send(
            embed=embed,
            view=feedback_view
        )

        await interaction.response.send_message(f"{user.mention}, o seu ticket foi finalizado e o canal será fechado em 15 segundos. Uma mensagem de avaliação foi enviada no seu privado.", ephemeral=False)

        await asyncio.sleep(15)
        await interaction.channel.delete(reason=f"Ticket {self.ticket_code} finalizado.")


class CloseTicketButton(Button):
    def __init__(self, ticket_code: str, category: str, subject: str, member: discord.Member):
        super().__init__(style=discord.ButtonStyle.danger, label="🔒 Fechar ticket")
        self.ticket_code = ticket_code
        self.category = category
        self.subject = subject
        self.member = member

    async def callback(self, interaction: discord.Interaction):
        if POLITICO_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("Você não tem permissão para usar este botão.", ephemeral=True)
            return
        
        ticket_data = ticket_info.get(interaction.channel.id)
        if ticket_data is None:
            await interaction.response.send_message("Informações do ticket não encontradas.", ephemeral=True)
            return

        requester_id = ticket_data.get("opened_by_id")
        if not requester_id:
            await interaction.response.send_message("ID do solicitante não encontrado.", ephemeral=True)
            return

        requester = interaction.guild.get_member(requester_id)
        if requester is None:
            requester = await interaction.guild.fetch_member(requester_id)
            if requester is None:
                await interaction.response.send_message("Solicitante não encontrado no servidor. Verifique se o ID está correto ou se o solicitante foi removido.", ephemeral=True)
                return

        modal = TicketCloseModal(
            ticket_code=self.ticket_code,
            member=interaction.user,
            requester=requester,
            category=self.category,
            subject=self.subject
        )
        await interaction.response.send_modal(modal)

class TicketSubjectModal(Modal, title="Abertura de Ticket"):
    def __init__(self, category_emoji, category_name):
        super().__init__()
        self.category_emoji = category_emoji
        self.category_name = category_name
        self.ticket_code = str(uuid.uuid4())[:6].upper()
        self.add_item(TextInput(label="Detalhe sua necessidade", placeholder="Dê mais detalhes sobre sua necessidade aqui", style=discord.TextStyle.paragraph, required=True))

    async def on_submit(self, interaction: discord.Interaction):
        subject = self.children[0].value.strip()
        user = interaction.user
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name=CATEGORY_NAME)

        if category is None:
            category = await guild.create_category(CATEGORY_NAME)

        channel_name = f"{self.category_emoji}・{user.name.lower()}-{self.ticket_code}"

        ticket_channel = await guild.create_text_channel(channel_name, category=category)

        await ticket_channel.set_permissions(guild.default_role, read_messages=False, send_messages=False)
        await ticket_channel.set_permissions(user, read_messages=True, send_messages=True)
        politico_role = guild.get_role(POLITICO_ROLE_ID)
        if politico_role:
            await ticket_channel.set_permissions(politico_role, read_messages=True, send_messages=True)

        ticket_info[ticket_channel.id] = {
            "opened_by": user.mention,
            "opened_by_id": user.id,
            "open_time": datetime.now().strftime("%B %d, %Y %I:%M %p"),
            "subject": subject, 
            "category": self.category_name, 
            "ticket_code": self.ticket_code
        }

        data = datetime.now()
        open_time = data.strftime("`%d/%m/%Y` às `%H:%M`")

        embed = discord.Embed(
            title=f"Ticket `{self.ticket_code}` ({self.category_name})",
            description=f"Olá, **{user.name}**, seja bem-vindo ao suporte da Sanja City. Caso queira dar mais detalhes sobre seu problema, peço que escreva de forma objetiva e clara, para que possamos lhe ajudar da melhor forma possível. Assim que possível, um <@&840793938276909098> virá te atender. Desde já, agradecemos o contato.\n\n**Solicitante:** {user.mention}\n**Aberto em:** {open_time}\n**Assunto do ticket:**\n```{subject}```",
            color=discord.Color.dark_embed()
        )
        #embed.set_thumbnail(url=IMAGE)
        embed.set_author(name="Sistema de atendimento - Sanja City", icon_url=IMAGE)

        politico_role = interaction.guild.get_role(POLITICO_ROLE_ID)

        await ticket_channel.send(
            f"{user.mention} {politico_role.mention}",
            embed=embed,
            view=TicketCloseView(ticket_code=self.ticket_code, category=self.category_name, subject=subject, member=user)
        )

        embed_ticket_opened = discord.Embed(
            title=f"**Ticket aberto ✅**",
            description=f"Clique [aqui](https://discord.com/channels/{guild.id}/{ticket_channel.id}) para ir até ele!",
            color=discord.Color.green()
        )

        try:
            await interaction.response.send_message(embed=embed_ticket_opened, ephemeral=True)
        except discord.errors.NotFound:
            pass

class CategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="📝・Assuntos Gerais", description="Dúvidas ou suporte", value="📝 Assuntos Gerais"),
            discord.SelectOption(label="💰・Assuntos Financeiros", description="Dúvidas financeiras ou doações", value="💰 Assuntos Financeiros"),
            discord.SelectOption(label="👻・Suspeita de Hack", description="Suspeita de uso de hacks ou trapaças", value="👻 Suspeita de Hack"),
            discord.SelectOption(label="🚫・Denunciar Jogador", description="Denunciar comportamento inadequado de um jogador", value="🚫 Denunciar Jogador"),
            discord.SelectOption(label="🐞・Reportar um Bug", description="Relatar um bug encontrado na cidade", value="🐞 Reportar um Bug"),
            discord.SelectOption(label="⚠️・Denunciar Staff", description="Viu algo de errado com a Staff? Denuncie aqui!", value="⚠️ Denunciar Staff"),
            discord.SelectOption(label="📸・Criador de conteúdo", description="Seja um criador de conteúdo", value="📸 Criador de conteúdo"),
        ]
        super().__init__(placeholder="Selecione uma categoria", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        category_data = self.values[0].split(' ', 1)
        category_emoji = category_data[0]
        category_name = category_data[1]
        modal = TicketSubjectModal(category_emoji, category_name)
        await interaction.response.send_modal(modal)

        new_view = CategoryView()
        await interaction.message.edit(view=new_view)

class CategoryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(CategorySelect())


### Inicia o bot
@bot.event
async def on_ready():
    print('O bot está ONLINE')
    print(bot.user.name)
    print(bot.user.id)
    print('------------')
    channel = bot.get_channel(CHANNEL_START)
    
    if channel:
        async for message in channel.history(limit=15):
            if message.author == bot.user:
                await message.delete()

        embed = discord.Embed(
            title="", 
            description="Para dar início ao seu atendimento, clique na bandeja abaixo e selecione o tipo de ticket, conforme necessidade.\n\n> **Observações:**\n- Por favor, tenha em mente que cada tipo de ticket é específico para lidar com o assunto selecionado.\n- Abrir um ticket sem um motivo válido ou com o intuito de brincadeiras pode resultar em punições.",    
            color=discord.Color.dark_embed()
        )
        embed.set_author(name="Sistema de atendimento", icon_url=IMAGE)
        
        #if bot.user.avatar:
        #    embed.set_footer(text=f"{bot.user.display_name}", icon_url=bot.user.avatar.url)
        #else:
        #    embed.set_footer(text=f"{bot.user.display_name}")

        #embed.set_thumbnail(url=IMAGE)
        
        await channel.send(embed=embed, view=CategoryView())

bot.run('TOKEN')
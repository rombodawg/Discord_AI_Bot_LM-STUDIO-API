import nextcord
import aiohttp
from collections import deque
import os

# Load the token from token.txt
def load_token(file_path='token.txt'):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file {file_path} does not exist.")
    with open(file_path, 'r') as file:
        token = file.read().strip()
    if not token:
        raise ValueError("The token file is empty.")
    return token

DISCORD_TOKEN = load_token()
API_URL = "http://localhost:1234/v1/chat/completions"
SYSTEM_MESSAGE = (
    "Put System message here"
)

class ChatBot(nextcord.Client):
    def __init__(self):
        intents = nextcord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.histories = {}  # Stores conversation history per guild (or channel for DMs)

    def get_history(self, guild_id):
        if guild_id not in self.histories:
            self.histories[guild_id] = deque(maxlen=10)  # Stores last 10 exchanges
        return self.histories[guild_id]

    def format_history_for_lm_studio(self, history):
        """
        Converts history into LM Studio's required 'messages' format.
        The system message is always included first.
        """
        messages = [{"role": "system", "content": SYSTEM_MESSAGE}]

        for msg in history:
            if msg["role"] == "user" or msg["role"] == "assistant":  # Treat the bot as a user
                name = msg.get("name", "")
                entry = {
                    "role": "user",
                    "content": f"{name}: {msg['content']}"
                }
                messages.append(entry)

        return messages

    async def get_llm_response(self, history):
        """
        Calls the API with LM Studio-compatible format while keeping our custom prompt structure.
        """
        messages = self.format_history_for_lm_studio(history)

        async with aiohttp.ClientSession() as session:
            payload = {
                "model": "MODEL_NAME_HERE", #Write the name of the LLM here from LM studio
                "messages": messages,
                "temperature": 0.5,
                "max_tokens": -1,
                "stream": False
            }
            headers = {"Content-Type": "application/json"}
            try:
                async with session.post(API_URL, json=payload, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result['choices'][0]['message']['content']
                    else:
                        error_text = await response.text()
                        raise Exception(f"API call failed with status {response.status}: {error_text}")
            except Exception as e:
                print(f"Error calling LM Studio API: {e}")
                raise

    async def on_ready(self):
        print(f'{self.user} has connected to Discord!')

    async def on_message(self, message):
        if message.author == self.user or message.author.bot:  # Ignore bot's own messages and other bots
            return
        if message.content.lstrip().startswith("//"):  # Ignore commands starting with //
            return

        # Check if bot is mentioned or called by name change (tobi) to your bots name
        if self.user.mentioned_in(message) or 'tobi' in message.content.lower():
            async with message.channel.typing():
                user_message = message.content.replace(f'<@{self.user.id}>', '').strip()

                try:
                    guild_id = message.guild.id if message.guild else message.channel.id
                    history = self.get_history(guild_id)

                    # Append user message with optional name
                    username = message.author.display_name or ""
                    history.append({"role": "user", "name": username, "content": user_message})

                    # Get AI response
                    response_text = await self.get_llm_response(list(history))

                    # Append response to history
                    history.append({"role": "user", "name": "Tobi", "content": response_text}) # again change tobi to your bots name

                    # Handle long responses
                    if len(response_text) > 2000:
                        chunks = [response_text[i:i+2000] for i in range(0, len(response_text), 2000)]
                        for chunk in chunks:
                            await message.reply(chunk)
                    else:
                        await message.reply(response_text)

                except Exception as e:
                    print(f"Error: {e}")
                    await message.reply("Error Bot is currently offline.")

# Run the bot
if __name__ == "__main__":
    bot = ChatBot()
    bot.run(DISCORD_TOKEN)

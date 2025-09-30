import os
import discord # type: ignore
from discord.ext import commands # type: ignore
from dotenv import load_dotenv
import asyncio
import json
import sys
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters # type: ignore
from mcp.client.stdio import stdio_client # type: ignore
from openai import OpenAI # type: ignore
from langchain_community.document_loaders import TextLoader # type: ignore
from langchain_community.vectorstores import Chroma # type: ignore
from langchain_huggingface import HuggingFaceEmbeddings # type: ignore
from langchain.text_splitter import RecursiveCharacterTextSplitter # type: ignore
from langchain.prompts import PromptTemplate # type: ignore
from langchain.schema import HumanMessage # type: ignore
from langchain_openai import ChatOpenAI # type: ignore
import json

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MAX_DISCORD_MSG = 2000

loader = TextLoader("myself.txt")
documents = loader.load()

text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
texts = text_splitter.split_documents(documents)
    
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-m3")
retriever = Chroma.from_documents(texts, embeddings).as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={"k": 5, "score_threshold": 0.3}
)

llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=OPENAI_API_KEY)

prompt_template = """Bạn là trợ lý thông minh. Dựa trên thông tin dưới đây, hãy trả lời câu hỏi.
Nếu không biết, hãy nói "Không biết".
Thông tin: 
{context}

Câu hỏi: {question}
Trả lời:"""

PROMPT = PromptTemplate(template=prompt_template, input_variables=["context", "question"])


class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.openai = OpenAI(api_key=OPENAI_API_KEY)

    async def connect_to_server(self, server_script_path: str):
        is_python = server_script_path.endswith(".py")
        command = "python" if is_python else "None"

        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None,
        )
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        response = await self.session.list_tools()
        tools = response.tools
        print("Connected to server with tools: ", [tool.name for tool in tools])

    async def process_query(self, messages: list):
        if not self.session:
            return {"role": "assistant", "content": "Not connected to MCP server."}

        response = await self.session.list_tools()
        available_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            }
            for tool in response.tools
        ]

        # final_text = []

        completion = self.openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=available_tools,
        )

        choice = completion.choices[0].message
        final_text = ""

        if choice.content:
            final_text.append(choice.content)

        if choice.tool_calls:
            messages.append({
                "role": "assistant",
                "content": choice.content or "",
                "tool_calls": choice.tool_calls
            })

            for tool_call in choice.tool_calls:
                tool_name = tool_call.function.name
                try: 
                    tool_args = json.loads(tool_call.function.arguments)
                except:
                    tool_args = {}
                    print(f"Lỗi: Đối số của tool {tool_name} không hợp lệ")
                
                result = await self.session.call_tool(tool_name, tool_args)
                tool_result_text = "".join(c.text for c in result.content if c.type == "text")

                print(f"Calling tool {tool_name} with args {tool_args}")
                print(f"Tool result: {tool_result_text}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result_text,
                })

            completion = self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=available_tools,
            )
            final_text = completion.choices[0].message.content

        return {"role": "assistant", "content": final_text}

    async def cleanup(self):
        await self.exit_stack.aclose()


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
mcp_client = MCPClient()


@bot.event
async def on_ready():
    print(f"Bot is ready! Logged in as {bot.user}")


pending_id_users = set()
@bot.event
async def on_member_join(member):
    try:
        await member.send(f"```Hi {member.name}, vui lòng cho mình biết ID của bạn.```")
        pending_id_users.add(member.id)
        print(f"Sent ID request to {member.name}")
    except Exception as e:
        print(f"Could not send message to {member.name}: {e}")


@bot.command(name="ask")
async def ask_rag(ctx, *, question: str):
    try:
        docs = retriever.invoke(question)
        
        if not docs:
            await ctx.send("```Không tìm thấy thông tin liên quan trong dữ liệu.```")
            return
        
        context = "\n".join([doc.page_content for doc in docs])
        
        print(f"[DEBUG] Found {len(docs)} documents")
        print(f"[DEBUG] Context: {context[:200]}...")
        
        human_msg = HumanMessage(content=PROMPT.format(context=context, question=question))
        llm_response = await llm.agenerate([[human_msg]])
        answer = llm_response.generations[0][0].text

        for i in range(0, len(answer), MAX_DISCORD_MSG):
            await ctx.send(f"```{answer[i:i+MAX_DISCORD_MSG]}```")

    except Exception as e:
        print(f"[ERROR] Processing question: {e}")
        import traceback
        traceback.print_exc()
        await ctx.send("Có lỗi xảy ra khi truy vấn dữ liệu.")

chat_history = {}

MAX_HISTORY = 20  

import json
import traceback


@bot.command(name="tool")
async def crud_book(ctx, *, question: str):
    user_id = str(ctx.author.id)
    print(f"Received question from {ctx.author}: {question}")

    if user_id not in chat_history:
        chat_history[user_id] = []

    new_message = {"role": "user", "content": question}
    
    chat_history[user_id].append(new_message)

    if len(chat_history[user_id]) > MAX_HISTORY:
        chat_history[user_id] = chat_history[user_id][-MAX_HISTORY:]

    try:

        response = await mcp_client.process_query(chat_history[user_id])
        if isinstance(response, dict) and "role" in response and "content" in response:
            chat_history[user_id].append(response)
            msg_to_send = response["content"] 
        else:
            chat_history[user_id].append({"role": "assistant", "content": str(response)})
            msg_to_send = "Lỗi định dạng phản hổi"
            
        if isinstance(msg_to_send, (dict, list)):
            msg = json.dumps(msg_to_send, ensure_ascii=False, indent=2)
        else:
            msg = str(msg_to_send)
        if len(msg) > 1900:
            msg = msg[:1900] + "\n...(truncated)..."

        await ctx.send(f"```{msg}```")

    except Exception as e:
        print(f"Error processing question from {ctx.author}: {e}")
        print(traceback.format_exc())
        await ctx.send("```Xin lỗi, đã có lỗi khi xử lý câu hỏi của bạn.```")
@bot.command(name="clear_history")
async def clear_history(ctx):
    """Xóa lịch sử hội thoại của user."""
    user_id = str(ctx.author.id)
    if user_id in chat_history:
        del chat_history[user_id]
        await ctx.send("```Đã xóa lịch sử hội thoại của bạn.```")
    else:
        await ctx.send("```Bạn chưa có lịch sử để xóa.```")

async def main():
    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_TOKEN is missing in .env file")
    if len(sys.argv) < 2:
        print("Usage: python bot.py <path_to_mcp_server_script>")
        sys.exit(1)

    server_script = sys.argv[1]
    await mcp_client.connect_to_server(server_script)
    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
        asyncio.run(mcp_client.cleanup())
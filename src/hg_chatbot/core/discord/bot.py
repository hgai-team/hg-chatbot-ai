# import os
# import json
# import discord
# import asyncio
# import time
# import requests
# from collections import defaultdict
# import logging
# import concurrent.futures

# from api.schema import UserContext

# from core.config import get_core_settings
# from core.base import Document

# from llama_index.core.node_parser import SentenceSplitter

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger("discord_bot")

# intents = discord.Intents.default()
# intents.message_content = True

# client = discord.Client(intents=intents)

# message_queue = asyncio.Queue()
# user_last_message = defaultdict(float)
# user_message_count = defaultdict(int)

# workers = []

# thread_pool = concurrent.futures.ThreadPoolExecutor(
#     max_workers=get_core_settings().DISCORD_BOT_NUM_WORKERS * 2,
#     thread_name_prefix="discord_bot_worker"
# )

# sentence_splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=0)

# async def run_in_thread(func, *args, **kwargs):
#     """Chạy hàm chặn trong thread riêng biệt để không chặn vòng lặp sự kiện chính"""
#     loop = asyncio.get_event_loop()
#     return await loop.run_in_executor(thread_pool, func, *args, **kwargs)

# async def process_message_queue():
#     while True:
#         try:
#             message, prompt = await message_queue.get()
#             asyncio.create_task(process_single_message(message, prompt))
#             message_queue.task_done()
#         except Exception as e:
#             logger.error(f"Error processing queued message: {e}")

# async def get_user_context(user_id):
#     response = requests.get(f"http://discord-crawl:8200/users/{user_id}")
#     if response.status_code == 200:
#         user_context = response.json()
#         return user_context
#     else:
#         logger.info(f"Failed to fetch user context for {user_id}: {response.status_code}")
#         return ""

# async def chat(query_text, user_id, session_id, user_context):
#     from services.agentic_workflow.vahacha import (
#         get_chat_service,
#         get_evaluation_agent,
#         get_google_genai_llm
#     )
#     from api.routers.vahacha.chatbots import chat_user_stream
#     from services import get_settings_cached
#     if isinstance(query_text, str):
#         query_text = query_text.lower().strip()

#     agent_prompt_path = get_settings_cached().VAHACHA_AGENT_PROMPT_PATH
#     bot_name = "VaHaCha"

#     chat_service = get_chat_service(
#         bot_name=bot_name,
#         agent_prompt_path=agent_prompt_path
#     )

#     evaluation_agent = get_evaluation_agent(
#         agent_prompt_path=agent_prompt_path
#     )

#     google_llm = get_google_genai_llm(
#         model_name=get_settings_cached().GOOGLEAI_MODEL
#     )

#     if user_context.role != "admin":
#         validate_response = await chat_service.validate_chat_request(
#             query_text=query_text,
#             user_id=user_id,
#             session_id=session_id,
#             user_context=user_context
#         )

#         if validate_response.get("status") == "invalid":
#             return validate_response.get("response", "Invalid query.")

#         if not validate_response.get("authorized"):
#             return validate_response.get("reason")

#         elif validate_response.get("question_type") == "user_information":
#             response_text = await evaluation_agent.validate(
#                 query=f"""user_query:\n{query_text.lower()}\n\nuser_context:\n{user_context.model_dump_json().lower()}""",
#                 user_id=user_id,
#                 session_id=session_id,
#                 func=google_llm.arun, agent_name="user_information_answerer"
#             )
#             return response_text.get("answer")

#         elif validate_response.get("question_type") == "chatbot_information":
#             return """
#             Xin chào! Mình là VaHaCha – Chatbot nội bộ hỗ trợ Vận Hành Team được HG AI Team huấn luyện. Dưới đây là những gì mình có thể hỗ trợ bạn:
#             1. Tra cứu quy định: Nhanh chóng tìm và giải thích mọi quy định chung, quy định đặc thù theo network, dự án hoặc phòng ban.
#             2. Tìm kiếm & giải thích file quy định: Xác định thư mục, tên file liên quan đến từng bộ dữ liệu và giải thích mục đích sử dụng của từng tài liệu.
#             3. Liên hệ đúng người phụ trách: Cho bạn biết ai chịu trách nhiệm phản hồi theo từng dự án hoặc phòng ban, giúp rút ngắn thời gian chờ đợi.
#             """

#     response_text = await chat_service.process_chat_request(
#         query_text=query_text,
#         user_id=user_id,
#         session_id=session_id,
#         user_context=user_context
#     )

#     return response_text


# async def process_single_message(message, prompt):
#     try:
#         bot_message = await message.author.send("Đang xử lý...")

#         logger.info(f"Getting response for user {message.author.id}")
#         user_context = await get_user_context(message.author.id)

#         user_context = UserContext(**user_context)

#         if user_context:
#             full_response = await chat(prompt, message.author.id, f"discord-{message.author.id}", user_context)
#         else:
#             full_response = """⚠️  Xin lỗi, hồ sơ của bạn hiện chưa được cập nhật nên bạn tạm thời không thể sử dụng tính năng hỏi – đáp. Vui lòng liên hệ quản trị viên để được cấp quyền"""
#         logger.info(f"Received full response for user {message.author.id}")

#         document = Document(text=full_response)
#         nodes = await run_in_thread(lambda: sentence_splitter.get_nodes_from_documents([document]))
#         segments = [node.text for node in nodes]

#         if full_response.strip() and not segments:
#             segments = [full_response.strip()]

#         current_message = ""
#         buffer = ""
#         buffer_size = 300
#         message_parts = [bot_message]

#         for segment in segments:
#             buffer += segment + " "
#             current_message += segment + " "

#             if len(buffer) >= buffer_size or "\n" in buffer:
#                 if len(current_message) <= 1999:
#                     try:
#                         await message_parts[-1].edit(content=current_message)
#                         await asyncio.sleep(0.3)
#                     except Exception as e:
#                         logger.error(f"Edit error: {e}")
#                 else:
#                     split_pos = min(1900, len(current_message))
#                     for i in range(split_pos, max(0, split_pos-200), -1):
#                         if i < len(current_message):
#                             if current_message[i] == '\n':
#                                 split_pos = i + 1
#                                 break
#                             elif current_message[i] == '.' and i+1 < len(current_message) and current_message[i+1] == ' ':
#                                 split_pos = i + 2
#                                 break
#                             elif current_message[i] == ' ':
#                                 split_pos = i + 1
#                                 break

#                     first_part = current_message[:split_pos]
#                     try:
#                         await message_parts[-1].edit(content=first_part)
#                     except Exception as e:
#                         logger.error(f"Edit error when splitting: {e}")

#                     remaining = current_message[split_pos:]
#                     try:
#                         new_message = await message.author.send("...")
#                         message_parts.append(new_message)
#                         current_message = remaining

#                         await new_message.edit(content=current_message)
#                     except Exception as e:
#                         logger.error(f"Edit error for new message: {e}")

#                 buffer = ""
#                 await asyncio.sleep(0.5)

#         if buffer and current_message != message_parts[-1].content:
#             if len(current_message) <= 1999:
#                 try:
#                     await message_parts[-1].edit(content=current_message)
#                 except Exception as e:
#                     logger.error(f"Final update error: {e}")
#             else:
#                 try:
#                     await message_parts[-1].edit(content=current_message[:1999])

#                     remaining = current_message[1999:]
#                     chunks = [remaining[i:i+1999] for i in range(0, len(remaining), 1999)]

#                     for chunk in chunks:
#                         await message.author.send(chunk)
#                         await asyncio.sleep(0.1)
#                 except Exception as e:
#                     logger.error(f"Error in final chunking: {e}")

#     except Exception as e:
#         logger.error(f"Error processing message: {e}", exc_info=True)
#         await message.author.send(f"Đã xảy ra lỗi: {str(e)}")

# @client.event
# async def on_ready():
#     logger.info(f'We have logged in as {client.user}')
#     global workers
#     for _ in range(get_core_settings().DISCORD_BOT_NUM_WORKERS):
#         worker = asyncio.create_task(process_message_queue())
#         workers.append(worker)
#     logger.info(f'Started {get_core_settings().DISCORD_BOT_NUM_WORKERS} message queue workers')

# @client.event
# async def on_message(message):
#     if message.author == client.user:
#         return

#     if message.content.startswith(get_core_settings().DISCORD_BOT_ID):
#         user_id = message.author.id
#         current_time = time.time()

#         if current_time - user_last_message[user_id] > get_core_settings().DISCORD_BOT_RATE_LIMIT_PERIOD:
#             user_message_count[user_id] = 0

#         if user_message_count[user_id] >= get_core_settings().DISCORD_BOT_MAX_MESSAGES_PER_PERIOD:
#             await message.author.send(get_core_settings().DISCORD_BOT_COOLDOWN_MESSAGE)
#             return

#         user_message_count[user_id] += 1
#         user_last_message[user_id] = current_time

#         prompt = message.content.replace(get_core_settings().DISCORD_BOT_ID, "").strip()

#         await message_queue.put((message, prompt))


import os
import json
import discord
import asyncio
import time
import logging
import concurrent.futures

from collections import defaultdict
from fastapi import Depends
from starlette.responses import StreamingResponse

# import endpoint và schema từ FastAPI
from api.routers.vahacha.chatbots import chat_user_stream, chat_admin_stream
from api.schema import ChatRequest, UserContext

from core.config import get_core_settings
from core.base import Document

from llama_index.core.node_parser import SentenceSplitter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# hàng đợi và rate limit
message_queue = asyncio.Queue()
user_last_message = defaultdict(float)
user_message_count = defaultdict(int)

workers = []
# pool thread để xử lý chặn
thread_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=get_core_settings().DISCORD_BOT_NUM_WORKERS * 2,
    thread_name_prefix="discord_bot_worker"
)

sentence_splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=0)


async def run_in_thread(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(thread_pool, func, *args, **kwargs)


async def process_message_queue():
    while True:
        message, prompt = await message_queue.get()
        asyncio.create_task(process_single_message(message, prompt))
        message_queue.task_done()


async def process_single_message(message: discord.Message, prompt: str):
    """
    Với mỗi message trigger, chúng ta sẽ gọi stream_generator từ FastAPI
    và đọc dần các SSE chunks, rồi đẩy về Discord.
    """
    try:
        # Gửi trước một DM reply để edit dần
        bot_message = await message.author.send("⏳ Đang khởi tạo phiên chat...")
        thinking_content = ""
        response_content = ""
        in_response = False

        user_context = await fetch_user_context_obj(message.author.id)
        
        # Chuẩn bị ChatRequest
        chat_req = ChatRequest(
            bot_name='VaHaCha',
            user_id=str(message.author.id),
            session_id=f"discord-{message.author.id}",
            query_text=prompt,
            user_context=user_context
        )

        # Gọi FastAPI endpoint
        if user_context.role != 'admin':
            streaming_resp: StreamingResponse = await chat_user_stream(
                request=chat_req,
                api_key=get_core_settings().API_KEY
            )
        else:
            streaming_resp: StreamingResponse = await chat_admin_stream(
                request=chat_req,
                api_key=get_core_settings().API_KEY
            )
            
        # Đọc từng SSE chunk từ body_iterator
        async for chunk in streaming_resp.body_iterator:
            # Chuẩn hoá text
            text = chunk if isinstance(chunk, str) else chunk.decode("utf-8")

            for line in text.splitlines():
                if not line.startswith("data:"):
                    continue

                # bóc JSON payload
                payload_str = line[len("data:"):].strip()
                try:
                    payload = json.loads(payload_str)
                except json.JSONDecodeError:
                    logger.warning(f"Cannot parse JSON: {payload_str}")
                    continue

                # lower không cần thiết ở đây, vì chúng ta chỉ dùng payload["type"] và payload["tokens"]
                evt = payload.get("type")
                tokens = payload.get("tokens", [])
                data_str = "".join(tokens)

                # 1) processing thinking
                if evt in ("header_thinking", "thinking") and not in_response:
                    # append lên thinking_content
                    thinking_content += data_str
                    # edit luôn bot_message (lúc này thinking_content chưa có dòng khởi tạo)
                    await bot_message.edit(content=thinking_content)

                # 2) chuyển sang response
                elif evt == "response":
                    # nếu mới vào lần đầu gặp response, xoá thinking_content
                    if not in_response:
                        in_response = True
                        response_content = data_str
                    else:
                        # đã bắt đầu response, tiếp tục append
                        response_content += data_str

                    # edit bot_message để hiển thị response
                    await bot_message.edit(content=response_content)

                # 3) kết thúc stream
                elif evt == "end":
                    # gửi thêm 1 tin nhắn hoàn thành
                    await message.author.send("✅ Hoàn thành!")
                    return

        # bảo đảm kết thúc
        await message.author.send("✅ Hoàn thành!")
    except Exception as e:
        logger.error(f"Error in process_single_message: {e}", exc_info=True)
        await message.author.send(f"❌ Đã xảy ra lỗi: {e}")


async def fetch_user_context_obj(user_id: int) -> UserContext:
    """Hàm helper để fetch và parse UserContext từ service"""
    import requests
    
    resp = requests.get(f"http://discord-crawl:8200/users/{user_id}")
    if resp.status_code == 200:
        resp_json = {} 
        for key, values in resp.json().items():
            if isinstance(values, str):
                resp_json[key] = values.lower()
            if isinstance(values, list):
                resp_json[key] = []
                for value in values:
                    resp_json[key].append(value.lower())
        return UserContext(**resp_json)
    else:
        raise RuntimeError(f"Không fetch được user_context: {resp.status_code}")


@client.event
async def on_ready():
    logger.info(f'We have logged in as {client.user}')
    global workers
    for _ in range(get_core_settings().DISCORD_BOT_NUM_WORKERS):
        worker = asyncio.create_task(process_message_queue())
        workers.append(worker)
    logger.info(f'Started {get_core_settings().DISCORD_BOT_NUM_WORKERS} message queue workers')


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    prefix = get_core_settings().DISCORD_BOT_ID
    if message.content.startswith(prefix):
        uid = message.author.id
        now = time.time()
        # reset period
        if now - user_last_message[uid] > get_core_settings().DISCORD_BOT_RATE_LIMIT_PERIOD:
            user_message_count[uid] = 0
        # check limit
        if user_message_count[uid] >= get_core_settings().DISCORD_BOT_MAX_MESSAGES_PER_PERIOD:
            await message.author.send(get_core_settings().DISCORD_BOT_COOLDOWN_MESSAGE)
            return

        user_message_count[uid] += 1
        user_last_message[uid] = now
        prompt = message.content[len(prefix):].strip()
        await message_queue.put((message, prompt))

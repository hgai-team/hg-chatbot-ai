# HG-ChatBot

## Installation

### 2. Start services

```bash
docker network create hg-chatbot-network

docker compose -f docker-compose.qdrant.yml up -d

docker compose -f docker-compose.mongodb.yml up -d

docker compose -f docker-compose.hg-chatbot.yml up -d
```

## Project Structure
```bash
|hg-chatbot/
├── src/
│   ├── hg_chatbot/
│   │   ├── .env
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── endpoints.py
│   │   │   ├── routers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── files.py
│   │   │   │   ├── operations_chatbot.py
│   │   │   │   ├── query.py
│   │   │   ├── schema/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── files.py
│   │   │   │   ├── operations_chatbot.py
│   │   │   │   ├── query.py
│   │   │   ├── security/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── api_credentials.py
│   │   │   │   ├── env_loader.py
│   │   ├── core/
│   │   │   ├── base/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── schema.py
│   │   │   ├── config/
│   │   │   │   ├── base.yaml
│   │   │   │   ├── agents/
│   │   │   │   │   ├── operations_agent.yaml
│   │   │   │   ├── chatbots/
│   │   │   │   │   ├── operations_chatbot.yaml
│   │   │   ├── discord/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── bot.py
│   │   │   ├── embeddings/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── openai.py
│   │   │   ├── llms/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── openai.py
│   │   │   ├── loaders/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── excel_loader.py
│   │   │   │   ├── utils/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── table.py
│   │   │   ├── parsers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── parser_file.py
│   │   │   ├── security/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── env_loader.py
│   │   │   ├── storages/
│   │   │   │   ├── docstores/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── base.py
│   │   │   │   │   ├── lancedb.py
│   │   │   │   │   ├── mongodb.py
│   │   │   │   ├── vectorstores/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── base.py
│   │   │   │   │   ├── qdrant.py
│   │   │   ├── tools/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── custom_tool.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── agents/
│   │   │   │   ├── operations/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── chat.py
│   │   │   │   │   ├── tools/
│   │   │   │   │   │   ├── query_agent.py.py
│   │   │   │   │   │   ├── validate_agent.py
│   │   │   ├── chatbot/
│   │   │   │   ├── operations/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── chat.py
│   │   │   ├── tools/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── chat.py
│   │   │   │   ├── files.py
│   │   │   │   ├── prompt.py
│   │   │   │   ├── search.py
├── .gitignore
├── README.md
├── requirements.txt
```

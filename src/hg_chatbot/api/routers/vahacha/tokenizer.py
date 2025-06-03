from fastapi import APIRouter, Depends, HTTPException

from api.security import validate_auth

from core.parsers import json_parser

from services import (
    get_settings_cached,
    get_google_genai_llm
)

from services.tools.prompt import (
    load_prompt,
    apply_chat_template,
    prepare_chat_messages
)

DEFAULT_PROMPT_PATH = "api/config/prompts.yaml"
DEFAULT_BASE_PATH = "core/config/base.yaml"

app = APIRouter(
    prefix="/tokenizer",
    tags=["Tokenizer"]
)

async def tiktokenize(text: str) -> list[str]:
    import tiktoken

    encoding = tiktoken.get_encoding("o200k_base")

    token_ids = encoding.encode(text)

    tokens: list[str] = []
    for tid in token_ids:
        try:
            token_str = encoding.decode_single_token_str(tid)
        except AttributeError:
            token_str = encoding.decode([tid])
        tokens.append(token_str)

    return tokens


@app.post(
    "/gemini_tokenizer",
    dependencies=[Depends(validate_auth)]
)
async def gemini_tokenizer(
    text: str
):
    google_llm = get_google_genai_llm(
        model_name=get_settings_cached().GOOGLEAI_MODEL
    )
    try:
        agent_prompt = load_prompt(DEFAULT_PROMPT_PATH)
        prompt_template = load_prompt(DEFAULT_BASE_PATH)
        gemini_tokenizer_prompt = agent_prompt.get("gemini_tokenizer")

        prompt = apply_chat_template(template=prompt_template, **{**gemini_tokenizer_prompt, **{'input': text}})
        messages = prepare_chat_messages(prompt=prompt)

        response = await google_llm.arun(messages)

        return json_parser(response)

    except HTTPException as http_exc:
         raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post(
    "/tiktoken",
    dependencies=[Depends(validate_auth)]
)
async def tiktoken(
    text: str
):
    try:
        return await tiktokenize(text)

    except HTTPException as http_exc:
         raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

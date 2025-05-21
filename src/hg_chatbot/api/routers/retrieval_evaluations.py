from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from api.schema import SearchRequest, SearchResponse
from api.security import get_api_key

app = APIRouter(
    prefix="/retrieval",
    tags=["Retrieval"]
)


from services import (
    get_settings_cached, get_google_genai_llm
)

from services.agentic_workflow.tools import (
    get_query_analyzer_agent,
)

from services.tools import (
    get_search_tool,
)

APIKeyDep = Annotated[str, Depends(get_api_key)]

@app.post(
    "/vector",
)
async def retrieval_vector(
    api_key: APIKeyDep,
    request: SearchRequest,
    bot_name: str,
):
    search_tool = get_search_tool(
        bot_name=bot_name
    )

    try:
        _, _, ids = search_tool.find_similar_documents(
            query_text=request.query_text.lower(),
            top_k=request.top_k,
        )
        docs = search_tool.retrieve_documents(ids)
        return {
            "documents": docs
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post(
    "/keywords",
)
async def retrieval_keywords(
    api_key: APIKeyDep,
    request: SearchRequest,
    bot_name: str,
    agent_prompt_path: str
):
    query_analyzer = get_query_analyzer_agent(
        agent_prompt_path=agent_prompt_path
    )

    search_tool = get_search_tool(
        bot_name=bot_name
    )

    google_llm = get_google_genai_llm(
        model_name=get_settings_cached().GOOGLEAI_MODEL,
        agent_prompt_path=agent_prompt_path
    )

    try:
        keywords_result = await query_analyzer.extract_keyword(
            queries=request.query_text.lower(),
            user_id="demo",
            session_id="demo",
            func=google_llm.arun,
            agent_name="keyword_extractor"
        )

        response = await search_tool.find_documents_by_keywords(
            keywords=keywords_result[0]['keywords'],
            top_k=request.top_k,
        )

        ids = [doc['id'] for doc in response]
        docs = search_tool.retrieve_documents(ids)


        return {
            "keywords": keywords_result[0]['keywords'],
            "documents": docs
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# @app.post(
#     "/bm25",
# )
# async def retrieval_keywords(
#     api_key: APIKeyDep,
#     search_tool: SearchToolDep,
#     request: SearchRequest,
# ):
#     try:
#         docs = await search_tool.find_documents_by_bm25(
#             query=request.query_text.lower(),
#             top_k=request.top_k,
#         )
#         return {
#             "documents": docs
#         }


#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=str(e)
#         )

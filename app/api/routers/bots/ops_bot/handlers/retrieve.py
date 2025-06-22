# from fastapi import APIRouter, Depends, HTTPException

# from api.schema import SearchRequest, BotNames
# from api.security import validate_auth

# app = APIRouter(
#     prefix="/vahacha/retrieval",
#     tags=["Retrieval"]
# )


# from services import (
#     get_settings_cached, get_google_genai_llm
# )

# from services.agentic_workflow.tools import (
#     get_query_analyzer_agent,
# )

# from services.tools import (
#     get_search_tool,
# )

# @app.post(
#     "/vector",
#     dependencies=[Depends(validate_auth)]
# )
# async def retrieval_vector(
#     request: SearchRequest,
#     bot_name: BotNames,
# ):
#     search_tool = get_search_tool(
#         bot_name=bot_name
#     )

#     try:
#         _, _, ids = search_tool.find_similar_documents(
#             query_text=request.query_text.lower(),
#             top_k=request.top_k,
#         )
#         docs = search_tool.retrieve_documents(ids)
#         return {
#             "documents": docs
#         }

#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=str(e)
#         )

# @app.post(
#     "/keywords",
#     dependencies=[Depends(validate_auth)]
# )
# async def retrieval_keywords(
#     request: SearchRequest,
#     agent_prompt_path: str,
#     bot_name: BotNames,
# ):
#     query_analyzer = get_query_analyzer_agent(
#         agent_prompt_path=agent_prompt_path
#     )

#     search_tool = get_search_tool(
#         bot_name=bot_name
#     )

#     google_llm = get_google_genai_llm(
#         model_name=get_settings_cached().GOOGLEAI_MODEL,
#         agent_prompt_path=agent_prompt_path
#     )

#     try:
#         keywords_result = await query_analyzer.extract_keyword(
#             queries=request.query_text.lower(),
#             user_id="demo",
#             session_id="demo",
#             func=google_llm.arun,
#             agent_name="keyword_extractor"
#         )

#         response = await search_tool.find_documents_by_keywords(
#             keywords=keywords_result[0]['keywords'],
#             top_k=request.top_k,
#         )

#         ids = [doc['id'] for doc in response]
#         docs = search_tool.retrieve_documents(ids)


#         return {
#             "keywords": keywords_result[0]['keywords'],
#             "documents": docs
#         }

#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=str(e)
#         )

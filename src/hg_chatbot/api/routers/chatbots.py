import timeit

from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated

from api.schema import ChatRequest, ChatResponse
from api.security import get_api_key

from services import get_settings_cached

app = APIRouter(
    prefix="/chatbots",
    tags=["ChatBots"]
)

APIKeyDep = Annotated[str, Depends(get_api_key)]

@app.post(
    "/vahacha/chat/agent",
    response_model=ChatResponse
)
async def chat(
    request: ChatRequest,
    api_key: APIKeyDep,
):
    from services.agentic_workflow.vahacha import (
        get_chat_service,
        get_evaluation_agent,
        get_google_genai_llm
    )

    agent_prompt_path = get_settings_cached().VAHACHA_AGENT_PROMPT_PATH

    chat_service = get_chat_service(
        bot_name=request.bot_name,
        agent_prompt_path=agent_prompt_path
    )

    evaluation_agent = get_evaluation_agent(
        agent_prompt_path=agent_prompt_path
    )

    google_llm = get_google_genai_llm(
        model_name=get_settings_cached().GOOGLEAI_MODEL
    )

    try:
        start_time = timeit.default_timer()

        if request.user_context.role != "admin":
            validate_response = await chat_service.validate_chat_request(
                query_text=request.query_text.lower(),
                user_id=request.user_id,
                session_id=request.session_id,
                user_context=request.user_context
            )

            if validate_response.get("status") == "invalid":
                end_time = timeit.default_timer()
                return ChatResponse(results=validate_response.get("response", "Invalid query."), status=200, time_taken=end_time - start_time)

            if not validate_response.get("authorized"):
                end_time = timeit.default_timer()
                return ChatResponse(results=validate_response.get("reason"), status=200, time_taken=end_time - start_time)

            elif validate_response.get("question_type") == "user_information":
                response_text = await evaluation_agent.validate(
                    query=f"""user_query:\n{request.query_text.lower()}\n\nuser_context:\n{request.user_context.model_dump_json().lower()}""",
                    user_id=request.user_id,
                    session_id=request.session_id,
                    func=google_llm.arun, agent_name="user_information_answerer"
                )
                end_time = timeit.default_timer()
                return ChatResponse(results=response_text.get("answer"), status=200, time_taken=end_time - start_time)

            elif validate_response.get("question_type") == "chatbot_information":
                end_time = timeit.default_timer()
                return ChatResponse(results=response_text, status=200, time_taken=end_time - start_time)

        response_text = await chat_service.process_chat_request(
            query_text=request.query_text.lower(),
            user_id=request.user_id,
            session_id=request.session_id,
            user_context=request.user_context
        )
        end_time = timeit.default_timer()

        return ChatResponse(results=response_text, status=200, time_taken=end_time - start_time)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

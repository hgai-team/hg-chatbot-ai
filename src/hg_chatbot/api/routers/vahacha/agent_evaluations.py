from fastapi import APIRouter, Depends, HTTPException, Body

from api.security import validate_auth
from api.schema import ChatRequest

from services import (
    get_settings_cached,
)

app = APIRouter(
    prefix="/evaluations/agent",
    tags=["Evaluations"]
)

@app.post(
    "/vahacha/safety_guard",
    dependencies=[Depends(validate_auth)]
)
async def safety_guard(
    request: ChatRequest,
    agent_prompt_path: str = None,
):
    from services.agentic_workflow.vahacha import (
        get_evaluation_agent,
        get_google_genai_llm
    )

    if agent_prompt_path is None:
        agent_prompt_path = get_settings_cached().VAHACHA_AGENT_PROMPT_PATH

    evaluation_agent = get_evaluation_agent(
        agent_prompt_path=agent_prompt_path
    )

    google_llm = get_google_genai_llm(
        model_name=get_settings_cached().GOOGLEAI_MODEL
    )

    try:
        safety_guard_response = await evaluation_agent.validate(
            query=request.query_text.lower(),
            user_id=request.user_id,
            session_id=request.session_id,
            func=google_llm.arun,
            agent_name="safety_guard"
        )

        return safety_guard_response

    except HTTPException as http_exc:
         raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post(
    "/vahacha/query_classifier",
    dependencies=[Depends(validate_auth)]
)
async def query_classifier(
    request: ChatRequest,
    agent_prompt_path: str = None,
):
    from services.agentic_workflow.vahacha import (
        get_evaluation_agent,
        get_google_genai_llm
    )

    if agent_prompt_path is None:
        agent_prompt_path = get_settings_cached().VAHACHA_AGENT_PROMPT_PATH

    evaluation_agent = get_evaluation_agent(
        agent_prompt_path=agent_prompt_path
    )

    google_llm = get_google_genai_llm(
        model_name=get_settings_cached().GOOGLEAI_MODEL
    )

    try:
        query_classifier_response = await evaluation_agent.validate(
            query=f"""user_query:\n{request.query_text.lower()}\n\nuser_context:\n{request.user_context.model_dump_json().lower()}""",
            user_id=request.user_id,
            session_id=request.session_id,
            func=google_llm.arun,
            agent_name="query_classifier"
        )

        return query_classifier_response

    except HTTPException as http_exc:
         raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post(
    "/vahacha/query_preprocessor",
    dependencies=[Depends(validate_auth)]
)
async def query_preprocessor(
    query: str,
    user_id: str,
    session_id: str,
    agent_prompt_path: str = None
):
    from services.agentic_workflow.vahacha import (
        get_evaluation_agent,
        get_google_genai_llm
    )

    if agent_prompt_path is None:
        agent_prompt_path = get_settings_cached().VAHACHA_AGENT_PROMPT_PATH

    evaluation_agent = get_evaluation_agent(
        agent_prompt_path=agent_prompt_path
    )

    google_llm = get_google_genai_llm(
        model_name=get_settings_cached().GOOGLEAI_MODEL
    )

    try:
        query_preprocessor_response = await evaluation_agent.validate(
            query=query.lower().strip(),
            user_id=user_id,
            session_id=session_id,
            func=google_llm.arun,
            agent_name="query_preprocessor"
        )

        return query_preprocessor_response

    except HTTPException as http_exc:
         raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post(
    "/vahacha/keyword_extractor",
    dependencies=[Depends(validate_auth)]
)
async def keyword_extractor(
    queries: list[str],
    user_id: str,
    session_id: str,
    agent_prompt_path: str = None,
):
    from services.agentic_workflow.vahacha import (
        get_evaluation_agent,
        get_google_genai_llm
    )

    if agent_prompt_path is None:
        agent_prompt_path = get_settings_cached().VAHACHA_AGENT_PROMPT_PATH

    evaluation_agent = get_evaluation_agent(
        agent_prompt_path=agent_prompt_path
    )

    google_llm = get_google_genai_llm(
        model_name=get_settings_cached().GOOGLEAI_MODEL
    )

    try:
        keyword_extractor_response = await evaluation_agent.validate(
            queries=queries,
            user_id=user_id,
            session_id=session_id,
            func=google_llm.arun,
            agent_name="keyword_extractor"
        )

        return keyword_extractor_response

    except HTTPException as http_exc:
         raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post(
    "/vahacha/response_permission_editor",
    dependencies=[Depends(validate_auth)]
)
async def response_permission_editor(
    request: ChatRequest,
    response_text: str = Body(...)
):
    from services.agentic_workflow.vahacha import (
        get_evaluation_agent,
        get_google_genai_llm
    )
    agent_prompt_path = get_settings_cached().VAHACHA_AGENT_PROMPT_PATH

    evaluation_agent = get_evaluation_agent(
        agent_prompt_path=agent_prompt_path
    )

    google_llm = get_google_genai_llm(
        model_name=get_settings_cached().GOOGLEAI_MODEL_EDITOR
    )

    try:
        response_permission_editor_response = await evaluation_agent.validate(
            query=f"""question:\n{request.query_text}\nquestion_context:\n{response_text}\n\nuser_context:\n{request.user_context.model_dump_json(exclude='role').lower()}""",
            user_id=request.user_id,
            session_id=request.session_id,
            func=google_llm.arun,
            agent_name="response_permission_editor"
        )

        return response_permission_editor_response

    except HTTPException as http_exc:
         raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

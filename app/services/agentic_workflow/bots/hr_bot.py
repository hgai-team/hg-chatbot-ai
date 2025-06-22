class HrBotService:
    def __init__(
        self,
    ):
        self.bot_name = 'ChaChaCha'
        self._set_up()

    def _set_up(
        self,
    ):
        from services.agentic_workflow.tools import (
            get_query_processing_tool,
            get_context_retrieval_tool,
            get_prompt_processor_tool,
            get_evaluation_agent_tool,
            FileProcessorTool, get_file_processor_tool,
        )

        from services import (
            get_settings_cached,
            get_google_genai_llm,
            get_openai_llm,
            MongoDBMemoryStore, get_mongodb_memory_store,
            get_langfuse_instrumentor_cached
        )

        settings = get_settings_cached()


        database_name = f"{self.bot_name}{settings.MONGODB_BASE_DATABASE_NAME}"
        collection_name = f"{self.bot_name}{settings.MONGODB_BASE_CHAT_HISTORY_COLLECTION_NAME}"

        self.file_processor: FileProcessorTool = get_file_processor_tool(bot_name=self.bot_name)

        self.agent_prompt_path = settings.OPS_AGENT_PROMPT_PATH

        self.query_processor = get_query_processing_tool(
            database_name=database_name,
            collection_name=collection_name,
            agent_prompt_path=self.agent_prompt_path,
            bot_name=self.bot_name

        )
        self.context_retriever = get_context_retrieval_tool(
            bot_name=self.bot_name,
            agent_prompt_path=self.agent_prompt_path
        )
        self.prompt_processor = get_prompt_processor_tool()
        self.eval_agent = get_evaluation_agent_tool(
            agent_prompt_path=self.agent_prompt_path
        )
        self.google_llm = get_google_genai_llm(
            model_name=get_settings_cached().GOOGLEAI_MODEL,
        )
        self.main_llm = get_openai_llm()
        self.memory_store: MongoDBMemoryStore = get_mongodb_memory_store(
            database_name=database_name,
            collection_name=collection_name
        )
        self.instrumentor = get_langfuse_instrumentor_cached()

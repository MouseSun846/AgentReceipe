# All imports at the top
from vanna import Agent
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver, User, RequestContext
from vanna.tools import RunSqlTool, VisualizeDataTool
from vanna.tools.agent_memory import SaveQuestionToolArgsTool, SearchSavedCorrectToolUsesTool, SaveTextMemoryTool
from vanna.servers.fastapi import VannaFastAPIServer
from vanna.integrations.openai import OpenAILlmService
from vanna.integrations.mysql import MySQLRunner
from vanna.integrations.chromadb import ChromaAgentMemory
from vanna.core.agent.config import AgentConfig
from vanna.integrations.local.agent_memory import DemoAgentMemory  
  
# Configure your LLM
llm = OpenAILlmService(
    model="qwen3-coder",
    api_key="sk-...",  # Or use os.getenv("OPENAI_API_KEY")
    base_url="http://10.1.30.1:18080/v1"
)

# Configure your database
db_tool = RunSqlTool(
    sql_runner=MySQLRunner(
        host="10.0.101.76",
        port=3306,
        user="root",
        password="Clypg@1357!!!",
        database="writing_structured_data",
        charset="utf8mb4"
    )
)

# Configure your agent memory
class CustomOpenAIEmbeddingFunction:
    def __init__(self, api_key, base_url, model, dimensions, batch_size=32):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size

    def __call__(self, input: list[str]) -> list[list[float]]:
        embeddings = []
        for i in range(0, len(input), self.batch_size):
            batch = input[i : i + self.batch_size]
            response = self.client.embeddings.create(
                input=batch,
                model=self.model,
                dimensions=self.dimensions
            )
            # Sort by index to ensure order is preserved
            batch_embeddings = [data.embedding for data in sorted(response.data, key=lambda x: x.index)]
            embeddings.extend(batch_embeddings)
        return embeddings

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self(texts)

    def embed_query(self, text: str) -> list[float]:
        return self([text])[0]

embedding_function = CustomOpenAIEmbeddingFunction(
    api_key="sk-9v01fP7eIS6jT8uxxrVr1XaRPDPw1Y3nRvWIYL67vtwCUnLD",
    base_url="http://10.1.19.110:8006/v1",
    model="qwen3-8b-embd",
    dimensions=4096,
    batch_size=32
)

agent_memory = ChromaAgentMemory(
    persist_directory="./chroma_memory",
    collection_name="tool_memories",
    embedding_function=embedding_function
)

# Configure user authentication
class SimpleUserResolver(UserResolver):
    async def resolve_user(self, request_context: RequestContext) -> User:
        user_email = request_context.get_cookie('vanna_email') or 'guest@example.com'
        group = 'admin' if user_email == 'admin@example.com' else 'user'
        return User(id=user_email, email=user_email, group_memberships=[group])

user_resolver = SimpleUserResolver()

# Create your agent
tools = ToolRegistry()
tools.register_local_tool(db_tool, access_groups=['admin', 'user'])
tools.register_local_tool(SaveQuestionToolArgsTool(), access_groups=['admin'])
tools.register_local_tool(SearchSavedCorrectToolUsesTool(), access_groups=['admin', 'user'])
tools.register_local_tool(SaveTextMemoryTool(), access_groups=['admin', 'user'])
tools.register_local_tool(VisualizeDataTool(), access_groups=['admin', 'user'])


agent_memory = DemoAgentMemory(max_items=1000) 

agent = Agent(
    llm_service=llm,
    tool_registry=tools,
    user_resolver=user_resolver,
    agent_memory=agent_memory,
    config = AgentConfig(max_tool_iterations=100)
)

# Run the server
server = VannaFastAPIServer(agent, config={  
    "dev_mode": True,  
    "static_folder": "static"  # 文件系统路径  
})
server.run()  # Access at http://localhost:8000
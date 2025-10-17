import asyncio
import uuid
from typing import Annotated, TypedDict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt, Command
from sse_starlette import EventSourceResponse

from dotenv import load_dotenv

load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the state for the graph
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


llm = ChatOpenAI(model="model_name", temperature=0, base_url="base_url")

# Define the graph builder
builder = StateGraph(State, State)

# Define the node that calls the LLM
def call_llm(state: State):
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

# Define the node that waits for human input
def human_input_node(state: State):
    # The interrupt() function pauses the graph and waits for input
    # The graph will be resumed with the value provided in the Command
    user_input = interrupt(
        {
            "previous_messages": state["messages"],
        }
    )
    return {"messages": [HumanMessage(content=user_input)]}

# Add nodes to the graph
builder.add_node("llm", call_llm)
builder.add_node("human", human_input_node)

# Define the edges of the graph
builder.add_edge("llm", "human")
builder.add_edge("human", "llm")

# Set the entry point of the graph
builder.set_entry_point("human")

# Compile the graph with a memory checkpointer
memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# Store conversation graphs in memory
conversations = {}

@app.post("/start")
async def start_conversation():
    """
    Starts a new conversation and returns a unique thread ID.
    """
    thread_id = str(uuid.uuid4())
    conversations[thread_id] = graph
    print(f"Started new conversation with thread_id: {thread_id}")
    return {"thread_id": thread_id}

@app.post("/chat/{thread_id}")
async def chat(thread_id: str, message: dict):
    """
    Handles a chat message for a given thread_id and streams the response.
    """
    if thread_id not in conversations:
        return {"error": "Invalid thread_id"}, 404

    messages_list = message.get("messages")
    if not messages_list:
        return {"error": "Messages not provided"}, 400

    # The last message is the user's input
    user_message = messages_list[-1]["content"]

    config = {"configurable": {"thread_id": thread_id}}
    
    async def event_stream():
        # Resume the graph with the user's message
        # The graph will run until it hits the next interrupt
        async for chunk in graph.astream(Command(resume=user_message), config=config):
            if "__interrupt__" in chunk:
                # The graph is paused, waiting for the next human input
                break
            
            # Stream the AIMessage content
            for message in chunk.get("llm", {}).get("messages", []):
                if isinstance(message, AIMessage):
                    yield message.content

    return EventSourceResponse(event_stream())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

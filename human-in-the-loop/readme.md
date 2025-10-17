# LangGraph 人机交互实战 (Human-in-the-Loop)

本项目是一个基于 LangGraph 的实战案例，展示了如何利用其“人机交互”（Human-in-the-Loop）功能构建一个带有前端界面的实时聊天应用。

## 核心概念

此应用的核心是利用 LangGraph 的中断（Interrupt）机制来暂停图（Graph）的执行，等待用户的输入，然后再继续运行。这对于构建需要人类参与、审核或输入的复杂工作流至关重要。

关键组件包括：

1.  **`langgraph.types.interrupt`**: 这是 LangGraph 提供的核心函数，用于在图的某个节点上暂停执行。当图执行到包含 `interrupt()` 的节点时，它会保存当前状态并等待外部指令来恢复。
2.  **`langgraph.checkpoint.memory.MemorySaver`**: 中断功能依赖于持久化层来保存图的状态。`MemorySaver` 是一个内存中的 checkpointer，它使得图在暂停后能够被恢复。在生产环境中，可以替换为更持久的存储（如 Redis、PostgreSQL 等）。
3.  **`langgraph.types.Command`**: 当图被中断后，需要使用 `Command(resume=...)` 来传递用户的输入并恢复图的执行。

## 项目结构

```
.
├── backend/
│   ├── main.py         # FastAPI 后端，包含 LangGraph 逻辑
│   └── ...
└── frontend/
    └── index.html      # 纯 HTML/CSS/JS 实现的聊天前端界面
```

-   **`frontend/index.html`**: 提供一个简单的用户界面，用户可以在此输入问题并实时看到 AI 的流式回答。
-   **`backend/main.py`**: 使用 FastAPI 搭建的 Web 服务器。它定义了一个 LangGraph 状态图，该图在 AI 和人类用户之间交替执行，从而实现对话功能。

## 工作原理

### 1. 后端 (`backend/main.py`)

-   **状态图定义**:
    -   创建了一个 `StateGraph`，包含两个主要节点：`llm` 和 `human`。
    -   `llm` 节点：调用大语言模型（LLM）生成回复。
    -   `human` 节点：调用 `interrupt()` 函数，暂停图的执行，等待前端用户的输入。
-   **图的流程**:
    -   图的入口点被设置为 `human` 节点，意味着每次对话总是从等待用户输入开始。
    -   `human` 节点的下一跳是 `llm` 节点，`llm` 节点的下一跳又回到 `human` 节点，形成一个 `human -> llm -> human -> ...` 的循环。
-   **API 接口**:
    -   `/start`: 创建一个新的对话线程（`thread_id`），并初始化一个独立的图实例。
    -   `/chat/{thread_id}`:
        -   接收前端发送的用户消息。
        -   使用 `graph.astream(Command(resume=user_message), config=config)` 来恢复对应 `thread_id` 的图的执行。用户的消息作为 `resume` 的参数被注入图中。
        -   图从 `human` 节点恢复，将用户消息传递给 `llm` 节点。
        -   `llm` 节点生成回复后，图再次运行到 `human` 节点并暂停。
        -   整个过程中的 AI 回复通过 SSE (Server-Sent Events) 以流式方式实时返回给前端。

### 2. 前端 (`frontend/index.html`)

-   **初始化**: 页面加载时，向后端的 `/start` 接口发送请求，获取一个唯一的 `thread_id`，用于标识当前对话。
-   **发送消息**:
    -   当用户点击“Send”按钮或按下回车键时，将输入框中的文本内容和历史消息一并 POST 到后端的 `/chat/{thread_id}` 接口。
-   **接收流式响应**:
    -   前端使用 `fetch` API 和 `TextDecoderStream` 来处理后端返回的 SSE 流。
    -   它会实时读取数据块（chunk），并将 AI 生成的文本动态追加到聊天窗口中，实现了打字机效果。

## 如何运行

1.  **启动后端服务**:
    ```bash
    # 安装依赖
    pip install -r backend/requirements.txt

    # 运行 FastAPI 服务器
    python backend/main.py
    ```
    服务将在 `http://localhost:8000` 上运行。

2.  **打开前端页面**:
    -   在你的网页浏览器中直接打开 `frontend/index.html` 文件。

现在，你就可以在网页上与 LangGraph 驱动的聊天机器人进行交互了。

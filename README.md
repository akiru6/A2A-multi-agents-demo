
---

# Multi-Agent Collaboration with Google's A2A Framework
**[English]** A demonstration of a multi-agent system built with Google's Agent-to-Agent (A2A) communication framework. This project simulates a collaborative team of AI agents to perform market research on GitHub repositories.

**[中文]** 一个基于谷歌 A2A (Agent-to-Agent) 框架构建的多智能体协作系统演示。本项目模拟了一个由 AI 智能体组成的协作团队，对 GitHub 仓库进行市场调研。

---

## 🚀 Architecture / 项目架构

This project features a team of three specialist agents, each running as an independent web service:
本项目包含一个由三名专家智能体组成的团队，每个智能体都作为独立网络服务运行：

1.  **Orchestrator (项目总监):** The main agent that understands the user's high-level goal and delegates tasks to the appropriate specialist.
    *   **[中文]** **编排器 (项目总监):** 主智能体，负责理解用户的宏观目标，并将任务委派给最合适的专家。

2.  **GitHub Scout (信息侦察员):** A specialist responsible for searching GitHub, finding relevant repositories, and saving the findings locally.
    *   **[中文]** **GitHub 侦察员:** 专家智能体，负责搜索 GitHub，寻找相关代码仓库，并将结果保存在本地。

3.  **Business Analyst (商业分析师):** A specialist that reads the scout's findings, conducts further web research for commercial potential, and synthesizes a final marketing report.
    *   **[中文]** **商业分析师:** 专家智能体，负责读取侦察员的发现，通过网络搜索挖掘其商业潜力，并撰写最终的营销分析报告。

### How It Works / 工作流程
`User -> Orchestrator -> Scout -> (Saves File)`
`User -> Orchestrator -> Analyst -> (Reads File, Researches, Saves Report)`

## ✨ Key Features / 核心特性

*   **A2A Framework:** Agents communicate over the network using a standardized protocol.
*   **Agent Card:** Each agent has a "business card" to describe its identity and capabilities, enabling discovery and interoperability.
*   **Microservice Architecture:** Every agent is a decentralized, standalone service that can be deployed and scaled independently.
*   **LLM-Powered Delegation:** The Orchestrator uses an LLM to dynamically route user requests to the correct specialist agent.
*   **Multi-Step Tool Use:** Agents autonomously use a series of tools (GitHub Search, Web Search, File I/O) to accomplish complex tasks.

## 🛠️ Getting Started / 快速开始

### 1. Prerequisites / 环境准备
*   Python 3.9+
*   Docker (for running the GitHub MCP Server)
*   Clone this repository: `git clone [your-repo-url]`
*   Create a `.env` file by copying `.env.example` and fill in your API keys:
    ```env
    GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
    GITHUB_TOKEN="YOUR_GITHUB_PERSONAL_ACCESS_TOKEN"
    TAVILY_API_KEY="YOUR_TAVILY_API_KEY"
    ```

### 2. Installation / 安装依赖```bash
pip install -r requirements.txt
```

### 3. Run the Agents / 运行智能体
This command starts all three agents, each on its own port (10030, 10031, 10032).
该命令会启动所有三个智能体，每个智能体占用一个独立端口。
```bash
python A2A_github_demo_simplified.py
```

## 💬 Usage / 使用方法

Use a separate terminal to interact with the Orchestrator agent using the provided client script. The process is a two-step conversation.
请在另一个终端，使用我们提供的客户端脚本与“项目总监”（Orchestrator）进行交互。这是一个两步对话过程。

**Step 1: Ask the Scout to find repositories.**
**第一步：指令侦察员寻找仓库。**
```bash
# In a new terminal
python client.py "Find the top 5 'ai agent application' repos and save the list."
```
> **Expected Output:** The agent will confirm that the list has been saved to `output/repository_list.md`.
> **[中文] 预期输出:** 智能体将确认列表已保存至 `output/repository_list.md` 文件。

**Step 2: Ask the Analyst to create a report.**
**第二步：指令分析师撰写报告。**
```bash
python client.py "Now, analyze the repositories from the saved list and create the final report."
```
> **Expected Output:** The agent will confirm that the report has been saved to `output/marketing_plan.md`.
> **[中文] 预期输出:** 智能体将确认分析报告已保存至 `output/marketing_plan.md` 文件。

Check the `output/` directory to see the results!
请查看 `output/` 目录下的最终成果！

## 📄 License / 许可证
This project is licensed under the MIT License.
本项目采用 MIT 许可证。
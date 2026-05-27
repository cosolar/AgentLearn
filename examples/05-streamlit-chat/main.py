"""
Streamlit 聊天界面 — 支持流式输出的对话 Agent

用法:
    streamlit run examples/05-streamlit-chat/main.py

依赖:
    pip install streamlit
"""

import streamlit as st
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from agentlearn import DialogAgent, Msg

load_dotenv()

# ---------------------------------------------------------------------------
# 页面配置
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AgentLearn Chat",
    page_icon="🤖",
    layout="centered",
)

st.title("🤖 AgentLearn Chat")
st.caption("基于 DialogAgent 的流式对话演示")


# ---------------------------------------------------------------------------
# 初始化 session state
# ---------------------------------------------------------------------------
def init_agent(model_name: str) -> DialogAgent:
    """创建或重建 DialogAgent"""
    return DialogAgent(
        name="assistant",
        sys_prompt=(
            "你是一个友好、有帮助的 AI 助手。"
            "用中文回答，回答简洁准确，必要时可以详细解释。"
        ),
        llm=ChatOpenAI(model=model_name, temperature=0.7),
        verbose=True,
    )


def init_session():
    if "agent" not in st.session_state:
        st.session_state.agent = init_agent("gpt-4o-mini")
    if "messages" not in st.session_state:
        st.session_state.messages = []  # [{"role": str, "content": str}, ...]
    if "model_changed" not in st.session_state:
        st.session_state.model_changed = False


init_session()


# ---------------------------------------------------------------------------
# 侧边栏
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 设置")

    # 模型选择
    model_options = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
    selected_model = st.selectbox(
        "模型",
        model_options,
        index=model_options.index(
            st.session_state.agent.llm.model_name
            if st.session_state.agent.llm
            else "gpt-4o-mini"
        ),
    )

    # 温度
    temperature = st.slider(
        "温度 (Temperature)",
        min_value=0.0,
        max_value=2.0,
        value=0.7,
        step=0.1,
    )

    st.divider()

    # 系统提示词
    sys_prompt = st.text_area(
        "系统提示词",
        value=st.session_state.agent.sys_prompt,
        height=120,
    )

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 重建 Agent", use_container_width=True):
            st.session_state.agent = DialogAgent(
                name="assistant",
                sys_prompt=sys_prompt,
                llm=ChatOpenAI(model=selected_model, temperature=temperature),
                verbose=True,
            )
            st.session_state.messages = []
            st.rerun()

    with col2:
        if st.button("🗑️ 清空对话", use_container_width=True):
            st.session_state.messages = []
            st.session_state.agent.memory.clear_all()
            st.rerun()

    st.divider()

    # 对话统计
    msg_count = len(st.session_state.messages)
    mem_stats = st.session_state.agent.memory.get_stats()
    st.caption(
        f"消息数: {msg_count} | "
        f"记忆: W{mem_stats['working']} "
        f"S{mem_stats['short_term']} "
        f"L{mem_stats['long_term']}"
    )

    st.caption(f"AgentLearn v1.0.0 | streamlit")


# ---------------------------------------------------------------------------
# 应用实时配置变更
# ---------------------------------------------------------------------------
current_model = st.session_state.agent.llm.model_name if st.session_state.agent.llm else ""
if (selected_model != current_model
        or abs(temperature - (st.session_state.agent.llm.temperature if st.session_state.agent.llm else 0.7)) > 0.01):
    st.session_state.agent.llm = ChatOpenAI(
        model=selected_model, temperature=temperature
    )

if sys_prompt != st.session_state.agent.sys_prompt:
    st.session_state.agent.sys_prompt = sys_prompt


# ---------------------------------------------------------------------------
# 显示聊天消息
# ---------------------------------------------------------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ---------------------------------------------------------------------------
# 聊天输入与流式响应
# ---------------------------------------------------------------------------
if prompt := st.chat_input("请输入你的消息..."):
    # 1. 显示用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. 流式输出 Agent 响应
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""

        # 逐 token 流式输出
        for chunk in st.session_state.agent.stream_reply(Msg.user_msg(prompt)):
            full_response += chunk
            placeholder.markdown(full_response + "▌")

        # 最终显示（去掉光标）
        placeholder.markdown(full_response)

    # 3. 保存完整响应到历史
    st.session_state.messages.append(
        {"role": "assistant", "content": full_response}
    )

    # 4. 手动 rerun 以显示新消息（实际上 streamlit 会自动 rerun）

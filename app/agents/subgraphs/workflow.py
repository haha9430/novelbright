from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.ruunables import RunnableConfig
from app.agents.state import MainState
from app.agents.utils import clean_and_parse_json

# 워크플로우 구현
# Clio 호출
def call_clio(state: MainState, config: RunnableConfig):
    pass

# Story Keeper 호출
def call_story_keeper(state: MainState, config: RunnableConfig):
    pass

# 흐름 제어 로직 구현

# Super Graph 조립 및 컴파일
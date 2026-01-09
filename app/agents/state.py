from dataclasses import Field
from typing import TypedDict, Annotated, List
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

# 각 에이전트의 주고 받는 대화와 데이터를 저장
# 각 하위 에이전트가 사용할 state 정의
class StoryKeeperState(TypedDict):
    message: Annotated[List[BaseMessage], add_messages]

class ClioState(TypedDict):
    message: Annotated[List[BaseMessage], add_messages]

class MainState(TypedDict):
    user_query: str # 사용자의 최초 질문
    build_logs: List[BaseMessage]
    augment_logs: List[BaseMessage]
    extract_logs: List[BaseMessage]
    answer_logs: Annotated[List[BaseMessage], add_messages]
    process_status: str
    loop_count: int

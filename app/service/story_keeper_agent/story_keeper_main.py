from fastapi import FastAPI
from app.service.story_keeper_agent.api import router as story_router

app = FastAPI()
app.include_router(story_router)

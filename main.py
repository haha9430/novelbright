from fastapi import FastAPI
from app.api.route.user_routers import router as user_router
from app.api.route.agent_routers import router as agent_router

app = FastAPI()
app.include_router(user_router)
app.include_router(agent_router)


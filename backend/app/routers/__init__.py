from fastapi import APIRouter

from app.routers import auth, canvas, invites, runs, scores

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(runs.router)
api_router.include_router(canvas.router)
api_router.include_router(invites.router)
api_router.include_router(scores.router)

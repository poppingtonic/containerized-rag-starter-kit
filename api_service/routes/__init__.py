from fastapi import APIRouter
from .query_routes import router as query_router
from .legacy_routes import router as legacy_router
from .memory_routes import router as memory_router
from .feedback_routes import router as feedback_router
from .thread_routes import router as thread_router
from .cache_routes import router as cache_router
from .export_routes import router as export_router
from .health_routes import router as health_router
from .ragas_routes import router as ragas_router
from .document_routes import router as document_router
from .graph_routes import router as graph_router

# Create main router
main_router = APIRouter()

# Include all sub-routers
main_router.include_router(query_router, tags=["Query"])
main_router.include_router(legacy_router, tags=["Legacy"])
main_router.include_router(memory_router, prefix="/memory", tags=["Memory"])
main_router.include_router(feedback_router, tags=["Feedback"])
main_router.include_router(thread_router, prefix="/thread", tags=["Threads"])
main_router.include_router(cache_router, prefix="/cache", tags=["Cache"])
main_router.include_router(export_router, prefix="/export", tags=["Export"])
main_router.include_router(health_router, tags=["Health"])
main_router.include_router(ragas_router, prefix="/ragas", tags=["RAGAS Evaluation"])
main_router.include_router(document_router, prefix="/document", tags=["Document"])
main_router.include_router(graph_router, prefix="/graph", tags=["Knowledge Graph"])
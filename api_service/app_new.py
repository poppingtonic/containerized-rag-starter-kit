from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import main_router

# Initialize FastAPI app
app = FastAPI(
    title="GraphRAG API", 
    description="API for querying documents with GraphRAG-enhanced retrieval",
    version="2.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routes
app.include_router(main_router)

@app.get("/")
async def root():
    return {"message": "GraphRAG API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
import os
import io
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from backend.chat_backend import ChatData

# Get the base directory
BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Excel Chat Assistant")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load ChatData once at startup
chat_engine = ChatData()

# Serve static files (HTML, JS, CSS)
static_dir = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    try:
        index_path = BASE_DIR / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="index.html not found")
        return index_path.read_text()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading index.html: {str(e)}")

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
        
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Only .xlsx files are allowed")
    
    try:
        # Read file content
        file_content = await file.read()
        if not file_content:
            raise HTTPException(status_code=400, detail="Empty file provided")
            
        # Create BytesIO object
        excel_stream = io.BytesIO(file_content)
        
        # Try to validate if it's a valid Excel file
        try:
            chat_engine.ingest_excel(excel_stream)
            return JSONResponse({"message": f"Successfully ingested {file.filename}"})
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing Excel file: {str(e)}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error with file upload: {str(e)}")

@app.post("/ask/")
async def ask_question(question: str = Form(...)):
    if not question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    try:
        answer = chat_engine.ask(question)
        return JSONResponse({"answer": answer})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during answering: {str(e)}")

@app.post("/clear/")
async def clear_data():
    try:
        chat_engine.clear()
        return JSONResponse({"message": "Cleared all ingested data."})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during clearing: {str(e)}")

@app.get("/export/")
async def export_chat():
    try:
        history_text = chat_engine.export_chat_history()
        return StreamingResponse(
            iter([history_text.encode()]),
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=chat_export.txt"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during export: {str(e)}")

# Health check endpoint for Render
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

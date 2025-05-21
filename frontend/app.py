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

# Configure maximum file size (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB in bytes

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
        # Check file size
        file_size = 0
        file_content = bytearray()
        
        # Read file in chunks to handle large files
        while chunk := await file.read(8192):  # 8KB chunks
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size is {MAX_FILE_SIZE/1024/1024}MB"
                )
            file_content.extend(chunk)
        
        if not file_content:
            raise HTTPException(status_code=400, detail="Empty file provided")
            
        # Create BytesIO object and ensure it's at the beginning
        excel_stream = io.BytesIO(file_content)
        excel_stream.seek(0)
        
        # Try to validate and process the Excel file
        try:
            rows_processed = chat_engine.ingest_excel(excel_stream)
            return JSONResponse({
                "message": f"Successfully processed {rows_processed} rows from {file.filename}",
                "status": "success",
                "rows_processed": rows_processed
            })
        except ValueError as ve:
            # Log the error for debugging
            print(f"Excel processing error: {str(ve)}")
            raise HTTPException(status_code=400, detail=str(ve))
        except RuntimeError as re:
            # Handle HuggingFace API errors
            error_msg = str(re)
            if "HuggingFace API key" in error_msg or "Failed to connect to HuggingFace services" in error_msg:
                print(f"HuggingFace API error: {error_msg}")
                raise HTTPException(
                    status_code=503,
                    detail="Failed to connect to AI services. Please check your API key configuration and internet connection."
                )
            raise HTTPException(status_code=500, detail=error_msg)
        except Exception as e:
            # Log the error for debugging
            print(f"Unexpected error during Excel processing: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing Excel file: {str(e)}")
        finally:
            # Clean up
            excel_stream.close()
            await file.close()
            
    except HTTPException:
        raise
    except Exception as e:
        # Log the error for debugging
        print(f"File upload error: {str(e)}")
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

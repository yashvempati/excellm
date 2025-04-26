import os
import io
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from backend.chat_backend import ChatData

app = FastAPI()

# Load ChatData once at startup
chat_engine = ChatData()

# Serve static files (HTML, JS, CSS)
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("frontend/index.html") as f:
        return f.read()

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_content = await file.read()
        excel_stream = io.BytesIO(file_content)
        chat_engine.ingest_excel(excel_stream)
        return JSONResponse({"message": f"Successfully ingested {file.filename}"})
    except Exception as e:
        return JSONResponse({"error": f"Error with file upload: {str(e)}"}, status_code=400)

@app.post("/ask/")
async def ask_question(question: str = Form(...)):
    try:
        answer = chat_engine.ask(question)
        return JSONResponse({"answer": answer})
    except Exception as e:
        return JSONResponse({"error": f"Error during answering: {str(e)}"}, status_code=500)

@app.post("/clear/")
async def clear_data():
    try:
        chat_engine.clear()
        return JSONResponse({"message": "Cleared all ingested data."})
    except Exception as e:
        return JSONResponse({"error": f"Error during clearing: {str(e)}"}, status_code=500)

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
        return JSONResponse({"error": f"Error during export: {str(e)}"}, status_code=500)
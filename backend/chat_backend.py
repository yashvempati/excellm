import os
import stat
import io
import shutil
import threading
import time
import requests
import openpyxl
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

HF_API_KEY = os.environ.get("HF_API_KEY")
if not HF_API_KEY:
    raise RuntimeError(
        "HuggingFace API key not found. Please set the HF_API_KEY environment variable. "
        "You can get an API key from https://huggingface.co/settings/tokens"
    )

HF_LLM_URL = "https://api-inference.huggingface.co/models/google/flan-t5-small"
HF_EMBED_URL = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"

def hf_generate(prompt):
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": prompt}
    try:
        response = requests.post(HF_LLM_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        if isinstance(result, list) and "generated_text" in result[0]:
            return result[0]["generated_text"]
        elif isinstance(result, dict) and "generated_text" in result:
            return result["generated_text"]
        else:
            return str(result)
    except requests.exceptions.RequestException as e:
        if response.status_code == 401:
            raise RuntimeError("Invalid HuggingFace API key. Please check your API key at https://huggingface.co/settings/tokens")
        elif response.status_code == 403:
            raise RuntimeError("Access denied. Please check if your HuggingFace API key has the correct permissions.")
        else:
            raise RuntimeError(f"Error calling HuggingFace API: {str(e)}")

def hf_embed(texts):
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": texts}
    try:
        response = requests.post(HF_EMBED_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        if response.status_code == 401:
            raise RuntimeError("Invalid HuggingFace API key. Please check your API key at https://huggingface.co/settings/tokens")
        elif response.status_code == 403:
            raise RuntimeError("Access denied. Please check if your HuggingFace API key has the correct permissions.")
        else:
            raise RuntimeError(f"Error calling HuggingFace API: {str(e)}")

class ChatData:
    def __init__(self):
        self.persist_directory = "chroma_db"
        os.makedirs(self.persist_directory, exist_ok=True)
        self._ensure_writable(self.persist_directory)

        self.vector_store = None
        self.retriever = None
        self.chain = None
        self.chat_history = []

        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1024, chunk_overlap=100)
        self.prompt = PromptTemplate.from_template(
            """
            You are a helpful assistant focused on analyzing Excel data and generating insights. Stick strictly to the provided context. 
            If the question cannot be answered with the given data, respond: "I cannot perform this analysis or the answer is not in the provided data."
            You can return answers as:
            - Plain text
            - Markdown tables (prefixed with "TABLE:")
            - Python code for Streamlit charts (prefixed with "CODE:" and inside triple backticks).
            Question: {question}
            Context: {context}
            Answer:
            """
        )

        self.ping_url = os.environ.get("RENDER_EXTERNAL_URL")
        self.keep_awake = True
        self._start_self_pinger()

    def _ensure_writable(self, path):
        try:
            os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            for root, dirs, files in os.walk(path):
                for d in dirs:
                    os.chmod(os.path.join(root, d), stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
                for f in files:
                    os.chmod(os.path.join(root, f), stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        except Exception as e:
            raise RuntimeError(f"Failed to set permissions on {path}: {str(e)}")

    def _start_self_pinger(self):
        if not self.ping_url:
            print("Self-ping URL not set. Skipping self-ping setup.")
            return

        def ping():
            while self.keep_awake:
                try:
                    print(f"Pinging {self.ping_url} to prevent Render sleep...")
                    requests.get(self.ping_url, timeout=10)
                except Exception as e:
                    print(f"Self-ping failed: {e}")
                time.sleep(600)  # every 10 minutes

        thread = threading.Thread(target=ping, daemon=True)
        thread.start()

    def _initialize_vector_store(self, documents):
        try:
            # Use HuggingFace embeddings for all documents
            texts = [doc.page_content for doc in documents]
            embeddings = hf_embed(texts)
            for i, doc in enumerate(documents):
                doc.embedding = embeddings[i]
            self.vector_store = Chroma.from_documents(
                documents=documents,
                embedding_function=lambda docs: hf_embed([d.page_content for d in docs]),
                persist_directory=self.persist_directory
            )
            self.vector_store.persist()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize vector store: {str(e)}")

    def _is_excel_file(self, file_obj):
        try:
            current_pos = file_obj.tell()
            try:
                wb = openpyxl.load_workbook(file_obj, read_only=True)
                if not wb.sheetnames:
                    return False
            except Exception:
                return False
            finally:
                file_obj.seek(current_pos)
            return True
        except Exception:
            return False

    def ingest_excel(self, excel_file):
        try:
            if not isinstance(excel_file, io.BytesIO):
                raise TypeError("Uploaded file must be a BytesIO object")
            if not self._is_excel_file(excel_file):
                raise ValueError("The uploaded file is not a valid Excel file or is corrupted.")
            excel_file.seek(0)
            wb = openpyxl.load_workbook(excel_file, data_only=True, read_only=True)
            sheets_to_process = wb.sheetnames
            if not sheets_to_process:
                raise ValueError("The Excel file contains no sheets.")
            docs = []
            for sheet in sheets_to_process:
                ws = wb[sheet]
                rows = list(ws.iter_rows(values_only=True))
                if not rows or not rows[0]:
                    continue
                headers = [str(h) for h in rows[0]]
                if not headers:
                    continue
                for i, row in enumerate(rows[1:], start=2):
                    if all(v is None for v in row):
                        continue
                    row_data = dict(zip(headers, row))
                    content = f"Sheet: {sheet}\nRow {i}\nData:\n{row_data}"
                    docs.append(Document(page_content=content, metadata={"sheet": sheet}))
            if not docs:
                raise ValueError("No valid data found in the Excel file. Please ensure the file contains at least one sheet with headers and data.")
            chunks = self.text_splitter.split_documents(docs)
            chunks = filter_complex_metadata(chunks)
            if self.vector_store is None:
                self._initialize_vector_store(chunks)
            else:
                self.vector_store.add_documents(chunks)
                self.vector_store.persist()
            self._create_retriever_and_chain()
        except Exception as e:
            raise RuntimeError(f"Failed to ingest Excel file: {str(e)}")

    def _create_retriever_and_chain(self):
        if self.vector_store:
            self.retriever = self.vector_store.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={"k": 3, "score_threshold": 0.5}
            )
            self.chain = self._chain

    def _chain(self, question):
        # Retrieve context
        docs = self.retriever.get_relevant_documents(question)
        context = "\n".join([doc.page_content for doc in docs])
        prompt = self.prompt.format(question=question, context=context)
        return hf_generate(prompt)

    def ask(self, query: str):
        if not self.chain:
            return "Please, add an Excel file first."
        try:
            response = self.chain(query).strip()
            self.chat_history.append({"question": query, "answer": response})
            if response.startswith("```python") and response.endswith("````"):
                code = response[9:-3].strip()
                return f"CODE:\n{code}"
            elif response.startswith("|") and "\n|" in response:
                return f"TABLE:{response}"
            else:
                return response
        except Exception as e:
            return f"Error processing your question: {str(e)}"

    def clear(self):
        try:
            if os.path.exists(self.persist_directory):
                shutil.rmtree(self.persist_directory)
            self.vector_store = None
            self.retriever = None
            self.chain = None
            self.chat_history = []
        except Exception as e:
            raise RuntimeError(f"Failed to clear data: {str(e)}")

    def export_chat_history(self):
        if not self.chat_history:
            return "No chat history available."
        try:
            lines = []
            for entry in self.chat_history:
                lines.append(f"Q: {entry['question']}\nA: {entry['answer']}\n")
            return "\n".join(lines)
        except Exception as e:
            raise RuntimeError(f"Failed to export chat history: {str(e)}")

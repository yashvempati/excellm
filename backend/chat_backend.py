import os
import stat
import io
import shutil
import openpyxl
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain.prompts import PromptTemplate
from langchain_community.llms import Ollama
from langchain.schema.runnable import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

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
            <s> [INST] You are a helpful assistant focused on analyzing Excel data and generating insights. Stick strictly to the provided context. 
            If the question cannot be answered with the given data, respond: "I cannot perform this analysis or the answer is not in the provided data."
            You can return answers as:
            - Plain text
            - Markdown tables (prefixed with "TABLE:")
            - Python code for Streamlit charts (prefixed with "CODE:" and inside triple backticks).
            Question: {question}
            Context: {context}
            Answer: [/INST] </s>
            """
        )
        
        # Initialize Ollama
        self.llm = Ollama(model="mistral")
        self.embeddings = OllamaEmbeddings(model="mistral")

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

    def _initialize_vector_store(self, documents):
        try:
            self.vector_store = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                persist_directory=self.persist_directory
            )
            self.vector_store.persist()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize vector store: {str(e)}")

    def ingest_excel(self, excel_file):
        try:
            if not isinstance(excel_file, io.BytesIO):
                raise TypeError(f"Invalid file type: {type(excel_file)}. Expected a BytesIO object.")

            wb = openpyxl.load_workbook(excel_file, data_only=True, read_only=True)
            sheets_to_process = wb.sheetnames
            docs = []

            for sheet in sheets_to_process:
                ws = wb[sheet]
                rows = list(ws.iter_rows(values_only=True))
                if not rows or not rows[0]:
                    continue

                headers = [str(h) for h in rows[0]]

                for i, row in enumerate(rows[1:], start=2):
                    if all(v is None for v in row):
                        continue
                    row_data = dict(zip(headers, row))
                    content = f"Sheet: {sheet}\nRow {i}\nData:\n{row_data}"
                    docs.append(Document(page_content=content, metadata={"sheet": sheet}))

            if not docs:
                raise ValueError("No valid data found in the Excel file")

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
            self.chain = (
                {"context": self.retriever, "question": RunnablePassthrough()}
                | self.prompt
                | self.llm
                | StrOutputParser()
            )

    def ask(self, query: str):
        if not self.chain:
            return "Please, add an Excel file first."

        try:
            response = self.chain.invoke(query).strip()

            # Save to chat history
            self.chat_history.append({"question": query, "answer": response})

            if response.startswith("```python") and response.endswith("```"):
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

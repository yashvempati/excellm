import os
import stat
import io
import shutil
import threading
import time
import requests
import pandas as pd
import traceback
import logging
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from ctransformers import AutoModelForCausalLM
from sentence_transformers import SentenceTransformer

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize models
def initialize_models():
    """Initialize the LLM and embedding models."""
    try:
        # Initialize TinyLlama
        llm = AutoModelForCausalLM.from_pretrained(
            "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
            model_file="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
            model_type="llama",
            gpu_layers=0,  # CPU only for Render free tier
            context_length=2048,  # Set a reasonable context length
            threads=4  # Limit threads to stay within Render's free tier
        )
        
        # Initialize sentence transformer for embeddings
        embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        
        return llm, embedding_model
    except Exception as e:
        logger.error(f"Failed to initialize models: {str(e)}")
        raise RuntimeError(f"Failed to initialize models: {str(e)}")

# Initialize models
try:
    logger.info("Initializing models...")
    llm, embedding_model = initialize_models()
    logger.info("Successfully initialized models")
except Exception as e:
    logger.error(f"Failed to initialize models: {str(e)}")
    raise

def generate_text(prompt):
    """Generate text using TinyLlama."""
    try:
        # Format the prompt properly for chat
        formatted_prompt = f"<|system|>\nYou are a helpful assistant focused on analyzing Excel data and generating insights. Stick strictly to the provided context.\n<|user|>\n{prompt}\n<|assistant|>\n"
        response = llm(
            formatted_prompt,
            max_new_tokens=1024,
            temperature=0.1,
            top_p=0.95,
            repetition_penalty=1.1,
            stop=["<|user|>", "<|system|>"]  # Stop at the next user or system message
        )
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating text: {str(e)}")
        raise RuntimeError(f"Failed to generate response: {str(e)}")

def get_embeddings(texts):
    """Get embeddings using sentence-transformers."""
    try:
        return embedding_model.encode(texts)
    except Exception as e:
        logger.error(f"Error getting embeddings: {str(e)}")
        raise RuntimeError(f"Failed to get embeddings: {str(e)}")

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
            # Use sentence-transformers embeddings for all documents
            texts = [doc.page_content for doc in documents]
            embeddings = get_embeddings(texts)
            for i, doc in enumerate(documents):
                doc.embedding = embeddings[i]
            self.vector_store = Chroma.from_documents(
                documents=documents,
                embedding_function=lambda docs: get_embeddings([d.page_content for d in docs]),
                persist_directory=self.persist_directory
            )
            self.vector_store.persist()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize vector store: {str(e)}")

    def ingest_csv(self, csv_file):
        """Ingest CSV file using pandas for reliable processing."""
        try:
            if not isinstance(csv_file, io.StringIO):
                raise TypeError("Uploaded file must be a StringIO object")

            # Read the CSV file
            csv_file.seek(0)
            logger.info("Attempting to read CSV file...")
            
            try:
                df = pd.read_csv(csv_file)
            except Exception as e:
                logger.error(f"Error reading CSV file: {str(e)}")
                logger.error(traceback.format_exc())
                raise ValueError(f"Failed to read CSV file: {str(e)}")
            
            if df.empty:
                raise ValueError("No data found in the CSV file")

            all_docs = []
            total_rows = 0

            # Process the DataFrame
            for idx, row in df.iterrows():
                try:
                    # Skip rows where all values are empty strings
                    if all(pd.isna(row)):
                        continue
                        
                    # Create row data dictionary
                    row_data = {col: val for col, val in row.items() if pd.notna(val)}
                    
                    if row_data:
                        content = (
                            f"Row {idx + 1}\n"  # +1 because pandas is 0-based
                            f"Data:\n{row_data}"
                        )
                        all_docs.append(Document(
                            page_content=content,
                            metadata={"row": idx + 1}
                        ))
                        total_rows += 1
                except Exception as e:
                    logger.error(f"Error processing row {idx}: {str(e)}")
                    continue

            if not all_docs:
                raise ValueError("No valid data found in the CSV file")

            logger.info(f"Successfully processed {total_rows} rows from the CSV file")

            # Split documents into chunks
            chunks = self.text_splitter.split_documents(all_docs)
            chunks = filter_complex_metadata(chunks)

            # Initialize or update vector store
            if self.vector_store is None:
                logger.info("Initializing new vector store...")
                self._initialize_vector_store(chunks)
            else:
                logger.info("Updating existing vector store...")
                self.vector_store.add_documents(chunks)
                self.vector_store.persist()

            self._create_retriever_and_chain()
            return total_rows

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error in ingest_csv: {error_msg}")
            logger.error(traceback.format_exc())
            
            if "No data found" in error_msg:
                raise ValueError("The CSV file contains no data")
            elif "No valid data" in error_msg:
                raise ValueError("No valid data could be extracted from the CSV file")
            else:
                raise RuntimeError(f"Failed to process CSV file: {error_msg}")

    def _create_retriever_and_chain(self):
        if self.vector_store:
            # We are using a custom embedding function with Chroma, so it expects a list of Document objects
            # or texts, and it will apply the embedding function.
            # The retriever uses this underlying embedding function when performing similarity searches.
            self.retriever = self.vector_store.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={"k": 3, "score_threshold": 0.5}
            )
            self.chain = (
                {"context": self.retriever, "question": RunnablePassthrough()}
                | self.prompt
                | StrOutputParser() # Use StrOutputParser to get the string output from the LLM
            )

    def ask(self, query: str):
        if not self.chain:
            return "Please, add an Excel file first."
        try:
            response = self.chain.invoke(query).strip() # Use .invoke() for the Runnable chain
            self.chat_history.append({"question": query, "answer": response})
            
            # Handling different response formats based on the prompt instructions
            if response.startswith("TABLE:"):
                # Remove "TABLE:" prefix and return as markdown table
                return response[len("TABLE:"):].strip()
            elif response.startswith("CODE:"):
                # Remove "CODE:" prefix and return as a code block
                return f"```python\n{response[len('CODE:'):].strip()}\n```"
            else:
                # Default to plain text
                return response
        except Exception as e:
            logger.error(f"Error in ask: {str(e)}")
            logger.error(traceback.format_exc())
            return f"An error occurred: {str(e)}"

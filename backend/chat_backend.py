import pandas as pd
import io
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain.prompts import PromptTemplate
from langchain_community.llms import Ollama

class ChatData:
    def __init__(self):
        self.dataframes = {}
        self.vectorstore = None
        self.chat_history = []

        # Setup embedding model
        self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

        # Setup LLM
        self.llm = Ollama(model="mistral")

    def ingest_excel(self, excel_stream):
        try:
            xls = pd.ExcelFile(excel_stream)
            for sheet_name in xls.sheet_names:
                self.dataframes[sheet_name] = xls.parse(sheet_name)
            self.create_vectorstore()
        except Exception as e:
            raise ValueError(f"Failed to read Excel file: {str(e)}")

    def create_vectorstore(self):
        texts = []
        for sheet_name, df in self.dataframes.items():
            sheet_text = f"Sheet: {sheet_name}\n{df.to_string(index=False)}"
            texts.append(sheet_text)

        # Split texts into manageable chunks
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        docs = splitter.create_documents(texts)

        # Create FAISS Vectorstore
        self.vectorstore = FAISS.from_documents(docs, self.embeddings)

    def ask(self, question):
        if not self.vectorstore:
            return "Please upload an Excel file first."

        # Find top 3 relevant chunks
        relevant_docs = self.vectorstore.similarity_search(question, k=3)
        context = "\n\n".join(doc.page_content for doc in relevant_docs)

        # Build full prompt
        chat_memory = ""
        for role, content in self.chat_history[-6:]:  # last 3 rounds
            chat_memory += f"{role}: {content}\n"

        final_prompt = f"""
You are an expert at analyzing Excel sheets.
Use the context below to answer the user's question.

Context:
{context}

Chat History:
{chat_memory}

User's New Question: {question}

Answer:
"""

        answer = self.llm.invoke(final_prompt)

        # Save chat history
        self.chat_history.append(("Question", question))
        self.chat_history.append(("Answer", answer))

        return answer

    def clear(self):
        self.dataframes.clear()
        self.vectorstore = None
        self.chat_history.clear()

    def export_chat_history(self):
        if not self.chat_history:
            return "No chat history yet."

        history = []
        for role, content in self.chat_history:
            history.append(f"{role}: {content}")
        return "\n".join(history)

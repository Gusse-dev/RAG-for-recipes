import chromadb
from chromadb.api.types import EmbeddingFunction
from chromadb.utils import embedding_functions
from langchain_chroma import Chroma
from langchain_ollama import ChatOllama
from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.chat_message_histories import ChatMessageHistory
import uuid

class ChromaEmbeddingsAdapter(Embeddings):
    def __init__(self, ef: EmbeddingFunction):
        self.ef = ef

    def embed_documents(self, texts):
        return self.ef(texts)

    def embed_query(self, query):
        return self.ef([query])[0]



class RecipeRecommender:

    def __init__(self, model_name, vector_db_path, vector_db_collection_name):
        model = ChatOllama(model=model_name)
        self.history = {}
        self.chat_id = uuid.uuid4()
        retriever = self.create_vector_db_retriever(vector_db_path, vector_db_collection_name)
        qa_chain = self.create_qa_chain(model)
        history_aware_retriever = self.create_history_retriever(model,retriever)
        rag_chain = create_retrieval_chain(history_aware_retriever, qa_chain)

        self.conversational_rag_chain = RunnableWithMessageHistory(
            rag_chain,
            self.get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer",
        )

    def create_vector_db_retriever(self, vector_db_path, vector_db_collection_name):
        embedding_adapter = ChromaEmbeddingsAdapter(embedding_functions.DefaultEmbeddingFunction())
        persistentClient = chromadb.PersistentClient(path=vector_db_path)
        vector_store = Chroma(client=persistentClient, collection_name=vector_db_collection_name, embedding_function=embedding_adapter)
        retriever = vector_store.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={
                "k": 3,
                "score_threshold": 0.5,
            },
        )
        return retriever
    
    def create_qa_chain(self,model):
        system_prompt = (
            "You are an assistant for question-answering tasks."
            "Your task is to recommend recipes."
            "Use the following pieces of retrieved context to answer the question."
            "If you don't know have a suitable recipe, tell it and give an alternative."
            "Then return the recipe title, the ingredient list and a step-by-step manual."
            "\n\n"
            "{context}"
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )
        qa_chain = create_stuff_documents_chain(llm=model, prompt=prompt)
        return qa_chain
    

    def create_history_retriever(self, model, retriever):
        contextualize_question_system_prompt = (
            "Given a chat history and the latest user question "
            "which might reference context in the chat history, "
            "formulate a standalone question which can be understood "
            "without the chat history. Do NOT answer the question, "
            "just reformulate it if needed and otherwise return it as is."
        )
        contextualize_question_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", contextualize_question_system_prompt),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )
        history_aware_retriever = create_history_aware_retriever(
            model, retriever, contextualize_question_prompt
        )
        return history_aware_retriever


    def handle_query(self, query: str) -> str:
        return self.conversational_rag_chain.invoke(
            {"input": query},
            config={
                "configurable": {"session_id": self.chat_id}
            }
        )
    
    def get_session_history(self, session_id: str) -> BaseChatMessageHistory:
        if session_id not in self.history:
            self.history[session_id] = ChatMessageHistory()
        return self.history[session_id]
    
    def get_session_id(self):
        return self.chat_id
    
    def start_new_session(self):
        self.chat_id = uuid.uuid4()
    
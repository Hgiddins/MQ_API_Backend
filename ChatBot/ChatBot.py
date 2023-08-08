import os

from langchain.chains import ConversationalRetrievalChain
from langchain.chat_models import ChatOpenAI
from langchain.document_loaders import TextLoader
from langchain.embeddings import OpenAIEmbeddings
from langchain.indexes import VectorstoreIndexCreator
from langchain.indexes.vectorstore import VectorStoreIndexWrapper
from langchain.chains import ConversationChain
from langchain.memory import ConversationSummaryMemory
from langchain.llms import OpenAI
from langchain.vectorstores import Chroma
from langchain.memory import ConversationBufferMemory


from ChatBot import ChatBotConstants


def setup_openai_authorization():
    """
    Sets up OpenAI's API authorization using environment variables or constants.
    """
    os.environ["OPENAI_API_KEY"] = ChatBotConstants.APIKEY

def get_index(persist, loader):
    """
    Get or create the vector store index.

    Args:
        persist (bool): Whether to persist the vector store on disk.
        loader (object): Data loader.

    Returns:
        object: Initialized index.
    """
    if persist and os.path.exists("persist"):
        print("Reusing index...\n")
        vectorstore = Chroma(persist_directory="persist", embedding_function=OpenAIEmbeddings())
        return VectorStoreIndexWrapper(vectorstore=vectorstore)
    else:
        if persist:
            return VectorstoreIndexCreator(vectorstore_kwargs={"persist_directory": "persist"}).from_loaders([loader])
        else:
            return VectorstoreIndexCreator().from_loaders([loader])


def instantiate_retrieval_chain(index):
    """
    Instantiates the conversational retrieval chain.
    Args:
        index (object): Vector store index.
    Returns:
        object: Initialized conversational retrieval chain.
    """
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    chain = ConversationalRetrievalChain.from_llm(
        llm=ChatOpenAI(temperature=0, model="gpt-3.5-turbo"),
        retriever=index.vectorstore.as_retriever(search_kwargs={"k": 1}),
        memory=memory
    )
    return chain

def instantiate_conversation_chain():
    """
    Instantiates the conversation chain and its memory.
    Returns:
        tuple: Initialized memory and conversation chain objects.
    """
    memory = ConversationSummaryMemory(llm=OpenAI())
    conversation = ConversationChain(
        llm=ChatOpenAI(temperature=0, model="gpt-3.5-turbo"),
        memory=memory
    )
    return memory, conversation


def boot_chatbot():
    PERSIST = False
    setup_openai_authorization()
    loader = TextLoader("ChatBot/MQ_DOCS_2035.txt")
    index = get_index(PERSIST, loader)
    retrieval_chain = instantiate_retrieval_chain(index)
    memory, conversation_chain = instantiate_conversation_chain()


    return retrieval_chain, conversation_chain


def get_error_message_chatbot_response(retrieval_chain, conversation_chain, error_information):
    # get relevant related information from the documentation
    context_prompt = "Provide relevant information about the causes and possible solutions to this issue: " + error_information

    documentation_context = retrieval_chain({"question": context_prompt})['answer']

    troubleshoot_prompt = """Given the provided context provided give an overview of the problem in my system and how to fix it : 
    *System Event message:\n""" + error_information + "\n\nIBMMQ Documentation reference:\n"+documentation_context

    result = conversation_chain.predict(input=troubleshoot_prompt)

    return result

def get_general_chatbot_response(retrieval_chain, conversation_chain, user_query):
    # get relevant related information from the documentation
    context_prompt = "Provide any relevant information about the following question: " + user_query

    documentation_context = retrieval_chain({"question": context_prompt})['answer']

    troubleshoot_prompt = """Given the provided context provided answer the question. If the provided context is not relevant then you do not have to use it: 
    *Question:\n""" + user_query + "\n\nIBMMQ Documentation reference:\n"+documentation_context

    result = conversation_chain.predict(input=troubleshoot_prompt)
    return result



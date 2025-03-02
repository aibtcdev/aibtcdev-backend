#!/usr/bin/env python
"""
Example of using the Vector React workflow with Supabase Vecs.

This example demonstrates how to initialize the vector store,
add documents, and execute the vector-enabled ReAct workflow.
"""

import asyncio

import dotenv
from langchain_community.document_loaders import WebBaseLoader
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.factory import backend
from services.workflows.vector_react import (
    add_documents_to_vectors,
    execute_vector_langgraph_stream,
)

dotenv.load_dotenv()


async def load_documents_from_url(url):
    """Load documents from a URL using WebBaseLoader and split them with RecursiveCharacterTextSplitter."""
    try:
        print(f"Loading content from {url}...")
        loader = WebBaseLoader(url)
        docs = loader.load()

        # Initialize the text splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=4000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )

        # Split the documents
        split_docs = text_splitter.split_documents(docs)

        # Add metadata to each document
        for doc in split_docs:
            doc.metadata["type"] = "stacks_documentation"
            doc.metadata["url"] = url

        print(
            f"Successfully loaded and split into {len(split_docs)} documents from {url}"
        )
        return split_docs
    except Exception as e:
        print(f"Error loading content from {url}: {str(e)}")
        return []


async def main():
    """Run the Vector React example."""
    # Set your OpenAI API key
    # Create some example documents
    documents = [
        Document(
            page_content="OpenAI was founded in 2015 and released GPT-1, GPT-2, GPT-3, and GPT-4.",
            metadata={"source": "about_openai.txt"},
        ),
        Document(
            page_content="Python is a programming language known for its readability and versatility.",
            metadata={"source": "programming_languages.txt"},
        ),
        Document(
            page_content="Supabase is an open source Firebase alternative with a PostgreSQL database.",
            metadata={"source": "database_services.txt"},
        ),
    ]

    # Add Stacks documentation content
    stacks_urls = [
        "https://docs.stacks.co/reference/functions",
        "https://docs.stacks.co/reference/keywords",
    ]

    for url in stacks_urls:
        print(f"\nProcessing documentation from {url}")
        docs = await load_documents_from_url(url)
        if docs:
            print(f"Adding {len(docs)} documents from {url}")
            documents.extend(docs)
        else:
            print(f"No content was retrieved from {url}")

    # Collection name for the vector store
    collection_name = "example_collection"

    # Initialize embeddings
    embeddings = OpenAIEmbeddings()

    # Ensure the vector collection exists
    try:
        # Try to get the collection first
        collection = backend.get_vector_collection(collection_name)
        print(f"Using existing vector collection: {collection_name}")
    except Exception:
        # Create the collection if it doesn't exist
        embed_dim = 1536  # Default for OpenAI embeddings
        if hasattr(embeddings, "embedding_dim"):
            embed_dim = embeddings.embedding_dim
        collection = backend.create_vector_collection(
            collection_name, dimensions=embed_dim
        )
        print(
            f"Created new vector collection: {collection_name} with dimensions: {embed_dim}"
        )

    # Add documents to the vector store
    print("Adding documents to vector store...")
    await add_documents_to_vectors(
        collection_name=collection_name, documents=documents, embeddings=embeddings
    )
    print("Documents added successfully!")

    # Create an index on the collection for better query performance
    print("Creating index on vector collection...")
    try:
        backend.create_vector_index(collection_name)
        print("Index created successfully!")
    except Exception as e:
        print(f"Error creating index: {str(e)}")

    # Setup example conversation history
    history = [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": "Hello, who are you?"},
        {
            "role": "assistant",
            "content": "I'm an AI assistant here to help you with your questions.",
        },
    ]

    # User query that will leverage the vector store for context
    user_query = "Write a Clarity function that returns the current block height."

    print(f"\nExecuting Vector React workflow with query: '{user_query}'")
    print("Streaming response:")

    # Execute the Vector React workflow and stream the response
    async for chunk in execute_vector_langgraph_stream(
        history=history,
        input_str=user_query,
        collection_name=collection_name,
        embeddings=embeddings,
    ):
        if chunk["type"] == "token":
            print(chunk["content"], end="", flush=True)
        elif chunk["type"] == "end":
            print("\n\nStream completed!")
        elif chunk["type"] == "result":
            print("\n\nFinal result metadata:", chunk)


if __name__ == "__main__":
    asyncio.run(main())

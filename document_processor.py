#!/usr/bin/env python
"""
Document processor for loading texts from URLs and local files, adding them to a vector database.

This utility focuses solely on ingesting documents from specified URLs and local files,
processing them, and storing them in a vector collection for later retrieval.
"""

import asyncio
import os
from pathlib import Path
from typing import List, Optional, Union

import dotenv
from langchain_community.document_loaders import TextLoader, WebBaseLoader
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.factory import backend
from services.workflows.vector_react import add_documents_to_vectors

# Load environment variables
dotenv.load_dotenv()


async def load_documents_from_url(url: str) -> List[Document]:
    """
    Load documents from a URL using WebBaseLoader and split them with RecursiveCharacterTextSplitter.

    Args:
        url: The URL to load documents from

    Returns:
        List of processed Document objects
    """
    try:
        print(f"Loading content from URL: {url}...")
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
            doc.metadata["type"] = "web_documentation"
            doc.metadata["url"] = url
            doc.metadata["source_type"] = "url"

        print(
            f"Successfully loaded and split into {len(split_docs)} documents from {url}"
        )
        return split_docs
    except Exception as e:
        print(f"Error loading content from URL {url}: {str(e)}")
        return []


def load_documents_from_file(
    file_path: str, document_type: str = "local_file"
) -> List[Document]:
    """
    Load documents from a local file and split them with RecursiveCharacterTextSplitter.

    Args:
        file_path: Path to the local file
        document_type: Type to assign in document metadata

    Returns:
        List of processed Document objects
    """
    try:
        print(f"Loading content from file: {file_path}...")
        file_path = Path(file_path)

        # Skip non-text files and hidden files
        if not file_path.is_file() or file_path.name.startswith("."):
            return []

        # Skip files that are likely binary or non-text
        text_extensions = [
            ".txt",
            ".md",
            ".py",
            ".js",
            ".ts",
            ".html",
            ".css",
            ".json",
            ".yaml",
            ".yml",
            ".clar",
        ]
        if file_path.suffix.lower() not in text_extensions:
            print(f"Skipping likely non-text file: {file_path}")
            return []

        loader = TextLoader(str(file_path))
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
            doc.metadata["type"] = document_type
            doc.metadata["file_path"] = str(file_path)
            doc.metadata["file_name"] = file_path.name
            doc.metadata["source_type"] = "file"

        print(
            f"Successfully loaded and split into {len(split_docs)} documents from {file_path}"
        )
        return split_docs
    except Exception as e:
        print(f"Error loading content from file {file_path}: {str(e)}")
        return []


def get_files_from_directory(directory_path: str, recursive: bool = True) -> List[str]:
    """
    Get a list of all files in a directory, optionally recursively.

    Args:
        directory_path: Path to the directory
        recursive: Whether to search recursively

    Returns:
        List of file paths
    """
    file_paths = []
    directory = Path(directory_path)

    if not directory.exists() or not directory.is_dir():
        print(f"Directory does not exist or is not a directory: {directory_path}")
        return file_paths

    if recursive:
        for root, _, files in os.walk(directory):
            for file in files:
                file_paths.append(os.path.join(root, file))
    else:
        for item in directory.iterdir():
            if item.is_file():
                file_paths.append(str(item))

    return file_paths


async def process_documents(
    urls: Optional[List[str]] = None,
    directories: Optional[List[str]] = None,
    files: Optional[List[str]] = None,
    collection_name: str = "example_collection",
    document_type: Optional[str] = None,
    recursive: bool = True,
) -> None:
    """
    Process documents from URLs, directories, and files and add them to the vector collection.

    Args:
        urls: List of URLs to process
        directories: List of directories to process
        files: List of individual files to process
        collection_name: Name of the vector collection to use
        document_type: Optional type to assign to documents in metadata
        recursive: Whether to recursively process directories
    """
    documents = []

    # Process URLs
    if urls:
        for url in urls:
            print(f"\nProcessing documentation from URL: {url}")
            docs = await load_documents_from_url(url)

            # Add custom document type if specified
            if document_type and docs:
                for doc in docs:
                    doc.metadata["type"] = document_type

            if docs:
                print(f"Adding {len(docs)} documents from URL {url}")
                documents.extend(docs)
            else:
                print(f"No content was retrieved from URL {url}")

    # Process directories
    if directories:
        for directory in directories:
            print(f"\nProcessing files from directory: {directory}")
            file_paths = get_files_from_directory(directory, recursive=recursive)

            for file_path in file_paths:
                print(f"Processing file: {file_path}")
                docs = load_documents_from_file(
                    file_path, document_type or "directory_file"
                )

                if docs:
                    print(f"Adding {len(docs)} documents from file {file_path}")
                    documents.extend(docs)
                else:
                    print(f"No content was retrieved from file {file_path}")

    # Process individual files
    if files:
        for file_path in files:
            print(f"\nProcessing individual file: {file_path}")
            docs = load_documents_from_file(
                file_path, document_type or "individual_file"
            )

            if docs:
                print(f"Adding {len(docs)} documents from file {file_path}")
                documents.extend(docs)
            else:
                print(f"No content was retrieved from file {file_path}")

    if not documents:
        print("No documents were loaded. Exiting.")
        return

    # Initialize embeddings
    embeddings = OpenAIEmbeddings()

    # Ensure the vector collection exists
    try:
        # Try to get the collection first
        backend.get_vector_collection(collection_name)
        print(f"Using existing vector collection: {collection_name}")
    except Exception:
        # Create the collection if it doesn't exist
        embed_dim = 1536  # Default for OpenAI embeddings
        if hasattr(embeddings, "embedding_dim"):
            embed_dim = embeddings.embedding_dim
        backend.create_vector_collection(collection_name, dimensions=embed_dim)
        print(
            f"Created new vector collection: {collection_name} with dimensions: {embed_dim}"
        )

    # Add documents to the vector store
    print(f"Adding {len(documents)} documents to vector store...")
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


async def main() -> None:
    """Run the document processor."""
    # Example list of URLs to process
    urls = [
        "https://docs.stacks.co/reference/functions",
        "https://docs.stacks.co/reference/keywords",
    ]

    # Example directories to process
    directories = [
        "./aibtcdev-docs",
    ]

    # Example individual files to process
    files = []

    # Process the documents and add them to the vector collection
    await process_documents(
        urls=urls,
        directories=directories,
        files=files,
        collection_name="example_collection",
        recursive=True,
    )


if __name__ == "__main__":
    asyncio.run(main())

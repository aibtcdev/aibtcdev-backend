#!/usr/bin/env python
"""
Document processor for loading texts from URLs and local files, adding them to a vector database.

This utility focuses solely on ingesting documents from specified URLs and local files,
processing them, and storing them in a vector collection for later retrieval.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Union

import dotenv
from langchain_community.document_loaders import TextLoader, WebBaseLoader
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.factory import backend
from backend.models import (
    DAO,
    UUID,
    ContractStatus,
    DAOFilter,
    Extension,
    ExtensionFilter,
    HolderFilter,
    Proposal,
    ProposalFilter,
    Token,
    TokenFilter,
    Vote,
    VoteFilter,
    WalletToken,
    WalletTokenFilter,
)
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


def extract_dao_documents() -> List[Document]:
    """
    Extract DAO-related data from the database and convert it to Document objects.

    Returns:
        List of Document objects containing DAO data
    """
    documents = []
    print("\nExtracting DAO data from the database...")

    try:
        # Get all DAOs
        daos = backend.list_daos()
        print(f"Found {len(daos)} DAOs in the database")

        for dao in daos:
            # Create a document for the DAO
            dao_content = f"""
            DAO: {dao.name}
            ID: {dao.id}
            Mission: {dao.description}
            Description: {dao.description}
            Deployed: {dao.is_deployed}
            Broadcasted: {dao.is_broadcasted}
            """

            # Create a document from the DAO
            dao_doc = Document(
                page_content=dao_content,
                metadata={
                    "type": "dao",
                    "id": str(dao.id),
                    "name": dao.name or "Unnamed DAO",
                    "source_type": "database",
                    "entity_type": "dao",
                },
            )
            documents.append(dao_doc)

            # Get tokens for this DAO
            tokens = backend.list_tokens(TokenFilter(dao_id=dao.id))
            if tokens:
                print(f"Found {len(tokens)} tokens for DAO {dao.name}")

                for token in tokens:
                    token_content = f"""
                    Token: {token.name} ({token.symbol})
                    DAO: {dao.name}
                    Description: {token.description}
                    Decimals: {token.decimals}
                    Max Supply: {token.max_supply}
                    Contract: {token.contract_principal}
                    Status: {token.status}
                    """

                    token_doc = Document(
                        page_content=token_content,
                        metadata={
                            "type": "token",
                            "id": str(token.id),
                            "dao_id": str(dao.id),
                            "dao_name": dao.name or "Unnamed DAO",
                            "name": token.name or "Unnamed Token",
                            "symbol": token.symbol,
                            "source_type": "database",
                            "entity_type": "token",
                        },
                    )
                    documents.append(token_doc)

            # Get extensions for this DAO
            extensions = backend.list_extensions(ExtensionFilter(dao_id=dao.id))
            if extensions:
                print(f"Found {len(extensions)} extensions for DAO {dao.name}")

                for extension in extensions:
                    extension_content = f"""
                    Extension Type: {extension.type}
                    DAO: {dao.name}
                    Contract: {extension.contract_principal}
                    Status: {extension.status}
                    Transaction: {extension.tx_id}
                    """

                    extension_doc = Document(
                        page_content=extension_content,
                        metadata={
                            "type": "extension",
                            "id": str(extension.id),
                            "dao_id": str(dao.id),
                            "dao_name": dao.name or "Unnamed DAO",
                            "extension_type": extension.type,
                            "source_type": "database",
                            "entity_type": "extension",
                        },
                    )
                    documents.append(extension_doc)

            # Get proposals for this DAO
            proposals = backend.list_proposals(ProposalFilter(dao_id=dao.id))
            if proposals:
                print(f"Found {len(proposals)} proposals for DAO {dao.name}")

                for proposal in proposals:
                    proposal_content = f"""
                    Proposal: {proposal.title}
                    DAO: {dao.name}
                    Description: {proposal.description}
                    Status: {proposal.status}
                    Action: {proposal.action}
                    Executed: {proposal.executed}
                    Passed: {proposal.passed}
                    Met Quorum: {proposal.met_quorum}
                    Met Threshold: {proposal.met_threshold}
                    Votes For: {proposal.votes_for}
                    Votes Against: {proposal.votes_against}
                    """

                    proposal_doc = Document(
                        page_content=proposal_content,
                        metadata={
                            "type": "proposal",
                            "id": str(proposal.id),
                            "dao_id": str(dao.id),
                            "dao_name": dao.name or "Unnamed DAO",
                            "title": proposal.title,
                            "source_type": "database",
                            "entity_type": "proposal",
                        },
                    )
                    documents.append(proposal_doc)

                    # Get votes for this proposal
                    votes = backend.list_votes(VoteFilter(proposal_id=proposal.id))
                    if votes:
                        print(f"Found {len(votes)} votes for proposal {proposal.title}")

                        vote_content = f"""
                        Votes for Proposal: {proposal.title}
                        DAO: {dao.name}
                        """

                        for vote in votes:
                            vote_content += f"""
                            Vote by: {vote.address}
                            Answer: {"Yes" if vote.answer else "No"}
                            Amount: {vote.amount}
                            Reasoning: {vote.reasoning}
                            """

                        vote_doc = Document(
                            page_content=vote_content,
                            metadata={
                                "type": "votes",
                                "proposal_id": str(proposal.id),
                                "dao_id": str(dao.id),
                                "dao_name": dao.name or "Unnamed DAO",
                                "proposal_title": proposal.title,
                                "source_type": "database",
                                "entity_type": "votes",
                            },
                        )
                        documents.append(vote_doc)

            # Get wallet tokens for this DAO
            wallet_tokens = backend.list_wallet_tokens(WalletTokenFilter(dao_id=dao.id))
            if wallet_tokens:
                print(f"Found {len(wallet_tokens)} wallet tokens for DAO {dao.name}")

                wallet_token_content = f"""
                Token Holdings for DAO: {dao.name}
                """

                for wallet_token in wallet_tokens:
                    # Get the wallet
                    wallet = backend.get_wallet(wallet_token.wallet_id)
                    if wallet:
                        wallet_address = (
                            wallet.mainnet_address
                            or wallet.testnet_address
                            or "Unknown"
                        )

                        # Get the token
                        token = backend.get_token(wallet_token.token_id)
                        token_name = token.name if token else "Unknown"
                        token_symbol = token.symbol if token else "Unknown"

                        wallet_token_content += f"""
                        Wallet: {wallet_address}
                        Token: {token_name} ({token_symbol})
                        Amount: {wallet_token.amount}
                        """

                wallet_token_doc = Document(
                    page_content=wallet_token_content,
                    metadata={
                        "type": "wallet_tokens",
                        "dao_id": str(dao.id),
                        "dao_name": dao.name or "Unnamed DAO",
                        "source_type": "database",
                        "entity_type": "wallet_tokens",
                    },
                )
                documents.append(wallet_token_doc)

            # Process token holders
            holders = backend.list_holders(HolderFilter(dao_id=dao.id))
            if holders:
                print(f"Found {len(holders)} holders for DAO {dao.name}")

                # Create content for token holders
                holder_content = f"""
                Token Holders for DAO {dao.name}
                ===================================
                """

                for holder in holders:
                    # Get wallet info
                    wallet = backend.get_wallet(holder.wallet_id)
                    if not wallet:
                        continue

                    # Get token info
                    token = backend.get_token(holder.token_id)
                    if not token:
                        continue

                    holder_content += f"""
                    Wallet: {wallet.mainnet_address or wallet.testnet_address}
                    Token: {token.name} ({token.symbol})
                    Amount: {holder.amount}
                    """

                # Create document for token holders
                holder_doc = Document(
                    page_content=holder_content,
                    metadata={
                        "type": "holders",
                        "dao_id": str(dao.id),
                        "dao_name": dao.name,
                        "entity_type": "holders",
                    },
                )
                documents.append(holder_doc)

        # Split the documents if they are too large
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=4000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )

        split_docs = text_splitter.split_documents(documents)
        print(
            f"Successfully processed {len(split_docs)} documents from database DAO data"
        )
        return split_docs

    except Exception as e:
        print(f"Error extracting DAO data from database: {str(e)}")
        return []


async def process_documents(
    urls: Optional[List[str]] = None,
    directories: Optional[List[str]] = None,
    files: Optional[List[str]] = None,
    knowledge_collection_name: str = "knowledge_collection",
    dao_collection_name: str = "dao_collection",
    document_type: Optional[str] = None,
    recursive: bool = True,
    include_database: bool = False,
) -> None:
    """
    Process documents from URLs, directories, files, and database and add them to vector collections.

    URLs, directories, and files go into knowledge_collection_name.
    Database DAO data goes into dao_collection_name.

    Args:
        urls: List of URLs to process
        directories: List of directories to process
        files: List of individual files to process
        knowledge_collection_name: Collection name for URL and file documents
        dao_collection_name: Collection name for database DAO documents
        document_type: Optional type to assign to documents in metadata
        recursive: Whether to recursively process directories
        include_database: Whether to include DAO data from the database
    """
    knowledge_documents = []
    dao_documents = []

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
                knowledge_documents.extend(docs)
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
                    knowledge_documents.extend(docs)
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
                knowledge_documents.extend(docs)
            else:
                print(f"No content was retrieved from file {file_path}")

    # Process knowledge documents if any exist
    if knowledge_documents:
        print(
            f"\nProcessing {len(knowledge_documents)} knowledge documents (URLs and files)..."
        )
        embeddings = OpenAIEmbeddings()

        # Ensure the knowledge collection exists
        try:
            backend.get_vector_collection(knowledge_collection_name)
            print(f"Using existing vector collection: {knowledge_collection_name}")
        except Exception:
            embed_dim = 1536  # Default for OpenAI embeddings
            if hasattr(embeddings, "embedding_dim"):
                embed_dim = embeddings.embedding_dim
            backend.create_vector_collection(
                knowledge_collection_name, dimensions=embed_dim
            )
            print(
                f"Created new vector collection: {knowledge_collection_name} with dimensions: {embed_dim}"
            )

        # Add knowledge documents to the vector store
        print(
            f"Adding {len(knowledge_documents)} documents to {knowledge_collection_name}..."
        )
        await add_documents_to_vectors(
            collection_name=knowledge_collection_name,
            documents=knowledge_documents,
            embeddings=embeddings,
        )
        print(f"Documents added successfully to {knowledge_collection_name}!")

        # Create an index on the collection for better query performance
        print(f"Creating index on vector collection: {knowledge_collection_name}...")
        try:
            backend.create_vector_index(knowledge_collection_name)
            print(f"Index created successfully for {knowledge_collection_name}!")
        except Exception as e:
            print(f"Error creating index for {knowledge_collection_name}: {str(e)}")

    # Process DAO data from database into separate collection
    if include_database:
        print("\nProcessing DAO data from database...")
        db_docs = extract_dao_documents()
        if db_docs:
            print(
                f"Adding {len(db_docs)} documents from database to {dao_collection_name}"
            )
            dao_documents.extend(db_docs)

            # Initialize embeddings for DAO documents
            embeddings = OpenAIEmbeddings()

            # Ensure the DAO collection exists
            try:
                backend.get_vector_collection(dao_collection_name)
                print(f"Using existing vector collection: {dao_collection_name}")
            except Exception:
                embed_dim = 1536  # Default for OpenAI embeddings
                if hasattr(embeddings, "embedding_dim"):
                    embed_dim = embeddings.embedding_dim
                backend.create_vector_collection(
                    dao_collection_name, dimensions=embed_dim
                )
                print(
                    f"Created new vector collection: {dao_collection_name} with dimensions: {embed_dim}"
                )

            # Add DAO documents to the vector store
            print(f"Adding {len(dao_documents)} documents to {dao_collection_name}...")
            await add_documents_to_vectors(
                collection_name=dao_collection_name,
                documents=dao_documents,
                embeddings=embeddings,
            )
            print(f"Documents added successfully to {dao_collection_name}!")

            # Create an index on the collection for better query performance
            print(f"Creating index on vector collection: {dao_collection_name}...")
            try:
                backend.create_vector_index(dao_collection_name)
                print(f"Index created successfully for {dao_collection_name}!")
            except Exception as e:
                print(f"Error creating index for {dao_collection_name}: {str(e)}")
        else:
            print("No content was retrieved from database")

    if not knowledge_documents and not dao_documents:
        print("No documents were loaded from any source. Exiting.")
        return


async def main() -> None:
    """Run the document processor."""
    # Example list of URLs to process
    urls = [
        "https://docs.stacks.co/reference/functions",
        "https://docs.stacks.co/reference/keywords",
        "https://docs.stacks.co/reference/types",
        "https://docs.stacks.co/reference/the-stack",
        "https://raw.githubusercontent.com/aibtcdev/aibtcdev-docs/refs/heads/main/aibtc-daos/dao-extensions/README.md",
    ]

    # Example directories to process
    directories = [
        "./aibtcdev-docs",  # Replace with actual directories
        "./aibtcdev-contracts/contracts/dao",
        "./stacks-docs/press-and-top-links",
        "./stacks-docs/nakamoto-upgrade",
        "./stacks-docs/concepts",
        "./stacks-docs/example-contracts",
        "./stacks-docs/guides-and-tutorials",
        "./stacks-docs/bitcoin-theses-and-reports",
        "./stacks-docs/reference",
    ]

    # Example individual files to process
    files = []

    # Process the documents and add them to separate vector collections
    await process_documents(
        urls=urls,
        directories=directories,
        files=files,
        knowledge_collection_name="knowledge_collection",  # Collection for URLs and files
        dao_collection_name="dao_collection",  # Collection for DAO database data
        recursive=True,
        include_database=False,  # Include DAO data from the database
    )


if __name__ == "__main__":
    asyncio.run(main())

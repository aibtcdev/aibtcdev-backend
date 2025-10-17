import time
import uuid
from typing import Any, Dict, List, Optional

import vecs
from sqlalchemy import Column, DateTime, Engine, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from supabase import Client

from app.backend.abstract import AbstractBackend
from app.backend.models import (
    DAO,
    UUID,
    Agent,
    AgentBase,
    AgentCreate,
    AgentFilter,
    AgentWithWalletTokenDTO,
    Airdrop,
    AirdropBase,
    AirdropCreate,
    AirdropFilter,
    ChainState,
    ChainStateBase,
    ChainStateCreate,
    ChainStateFilter,
    DAOBase,
    DAOCreate,
    DAOFilter,
    Extension,
    ExtensionBase,
    ExtensionCreate,
    ExtensionFilter,
    Feedback,
    FeedbackBase,
    FeedbackCreate,
    FeedbackFilter,
    Holder,
    HolderBase,
    HolderCreate,
    HolderFilter,
    Key,
    KeyBase,
    KeyCreate,
    KeyFilter,
    LotteryResult,
    LotteryResultBase,
    LotteryResultCreate,
    LotteryResultFilter,
    Profile,
    ProfileBase,
    ProfileCreate,
    ProfileFilter,
    Prompt,
    PromptBase,
    PromptCreate,
    PromptFilter,
    Proposal,
    ProposalBase,
    ProposalCreate,
    ProposalFilter,
    ProposalFilterN,
    QueueMessage,
    QueueMessageBase,
    QueueMessageCreate,
    QueueMessageFilter,
    Secret,
    SecretCreate,
    SecretFilter,
    Task,
    TaskBase,
    TaskCreate,
    TaskFilter,
    TelegramUser,
    TelegramUserBase,
    TelegramUserCreate,
    TelegramUserFilter,
    Token,
    TokenBase,
    TokenCreate,
    TokenFilter,
    Vote,
    VoteBase,
    VoteCreate,
    VoteFilter,
    Wallet,
    WalletBase,
    WalletCreate,
    WalletFilter,
    WalletFilterN,
    XCreds,
    XCredsBase,
    XCredsCreate,
    XCredsFilter,
    XTweet,
    XTweetBase,
    XTweetCreate,
    XTweetFilter,
    XUser,
    XUserBase,
    XUserCreate,
    XUserFilter,
    Veto,
    VetoBase,
    VetoCreate,
    VetoFilter,
)
from app.lib.logger import configure_logger

logger = configure_logger(__name__)


Base = declarative_base()


class SecretSQL(Base):
    __tablename__ = "decrypted_secrets"
    __table_args__ = {"schema": "vault"}  # Specifies the vault schema

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text)
    secret = Column(Text, nullable=False)
    decrypted_secret = Column(Text)
    key_id = Column(String)
    nonce = Column(String)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


def sqlalchemy_to_pydantic(secret_sql: SecretSQL) -> Secret:
    """Convert a SecretSQL model to a Secret pydantic model."""
    return Secret(
        id=str(secret_sql.id),
        name=secret_sql.name,
        description=secret_sql.description,
        secret=secret_sql.secret,
        decrypted_secret=secret_sql.decrypted_secret,
        key_id=str(secret_sql.key_id) if secret_sql.key_id else None,
        nonce=bytes(secret_sql.nonce).hex() if secret_sql.nonce else None,
        created_at=secret_sql.created_at,
        updated_at=secret_sql.updated_at,
    )


def pydantic_to_sqlalchemy(secret_pydantic: SecretCreate) -> SecretSQL:
    return SecretSQL(
        name=secret_pydantic.name,
        description=secret_pydantic.description,
        secret=secret_pydantic.secret,
        key_id=secret_pydantic.key_id,
        nonce=secret_pydantic.nonce,
    )


class SupabaseBackend(AbstractBackend):
    # Upload configuration
    MAX_UPLOAD_RETRIES = 3
    RETRY_DELAY_SECONDS = 1

    def __init__(self, client: Client, sqlalchemy_engine: Engine, **kwargs):
        # super().__init__()  # If your AbstractDatabase has an __init__ to call
        self.client = client
        self.sqlalchemy_engine = sqlalchemy_engine
        self.bucket_name = kwargs.get("bucket_name")
        self.Session = sessionmaker(bind=self.sqlalchemy_engine)

        # Initialize vecs client for vector operations
        db_connection_string = kwargs.get("db_connection_string")
        self.vecs_client = (
            vecs.create_client(db_connection_string) if db_connection_string else None
        )
        self._vector_collections = {}

        try:
            with self.sqlalchemy_engine.connect():
                logger.info("SQLAlchemy connection successful!")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")

    # ---------------------------------------------------------------
    # VECTOR STORE OPERATIONS
    # ---------------------------------------------------------------
    def get_vector_collection(self, collection_name: str) -> Any:
        """Get a vector collection by name."""
        if not self.vecs_client:
            raise ValueError("Vecs client not initialized")

        if collection_name not in self._vector_collections:
            self._vector_collections[collection_name] = self.vecs_client.get_collection(
                name=collection_name
            )
        return self._vector_collections[collection_name]

    async def add_vectors(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]],
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """Add vectors to a collection."""
        collection = self.get_vector_collection(collection_name)

        if metadata is None:
            metadata = [{} for _ in documents]

        # Extract embeddings and texts
        texts = [doc.get("page_content", "") for doc in documents]
        embeddings = [doc.get("embedding") for doc in documents]

        # Ensure all documents have embeddings
        if not all(embeddings):
            raise ValueError(
                "All documents must have embeddings to be added to the vector store"
            )

        # Create record IDs - using UUIDs
        record_ids = [str(uuid.uuid4()) for _ in documents]

        # Prepare records for upsert - use embeddings instead of text
        # Also include the original text in the metadata for retrieval
        records = []
        for i in range(len(texts)):
            # Add the original text to the metadata
            enhanced_metadata = metadata[i].copy()
            enhanced_metadata["text"] = texts[i]  # Store the original text in metadata

            # Create the record tuple (id, embedding, metadata)
            records.append((record_ids[i], embeddings[i], enhanced_metadata))

        try:
            # Upsert records
            collection.upsert(records=records)
            logger.debug(
                f"Added {len(records)} vectors to collection {collection_name}"
            )
            return record_ids
        except Exception as e:
            logger.error(
                f"Failed to add vectors to collection {collection_name}: {str(e)}"
            )
            raise

    async def fetch_vectors(self, collection_name: str, ids: List[str]) -> List[Any]:
        """Fetch specific vectors by their IDs using the vecs client.

        Args:
            collection_name: Name of the collection to query
            ids: List of vector IDs to fetch

        Returns:
            List of fetched records (typically tuples of id, vector, metadata).
        """
        collection = self.get_vector_collection(collection_name)
        if not ids:
            logger.debug("fetch_vectors called with empty ID list.")
            return []

        try:
            # Assuming the vecs library provides a `fetch` method
            fetched_records = collection.fetch(ids=ids)
            logger.debug(
                f"Fetched {len(fetched_records)} vectors from collection {collection_name} for {len(ids)} requested IDs."
            )
            return fetched_records
        except Exception as e:
            logger.error(
                f"Failed to fetch vectors by ID from collection {collection_name}: {str(e)}"
            )
            raise

    async def query_vectors(
        self, collection_name: str, query_text: str, limit: int = 4, embeddings=None
    ) -> List[Dict[str, Any]]:
        """Query vectors in a collection by similarity.

        Args:
            collection_name: Name of the collection to query
            query_text: Text to search for
            limit: Maximum number of results to return
            embeddings: Embeddings model to use for encoding the query

        Returns:
            List of matching documents with metadata
        """
        if embeddings is None:
            raise ValueError("Embeddings model must be provided to query vector store")

        collection = self.get_vector_collection(collection_name)

        try:
            # Generate embedding for the query text
            query_embedding = embeddings.embed_query(query_text)

            # Query similar vectors using the embedding
            results = collection.query(
                data=query_embedding,
                limit=limit,
                include_metadata=True,
                include_value=True,
                measure="cosine_distance",
            )

            # Format results
            documents = []
            for result in results:
                # The structure depends on what was included in the query
                if len(result) >= 2:  # We have at least ID and metadata
                    # Get the metadata (last element in the tuple)
                    metadata = result[-1] if isinstance(result[-1], dict) else {}

                    # Extract the original text from metadata if available
                    page_content = metadata.get("text", "")

                    # Remove the text from metadata to avoid duplication
                    metadata_copy = metadata.copy()
                    if "text" in metadata_copy:
                        del metadata_copy["text"]

                    doc = {
                        "id": result[0],
                        "page_content": page_content,
                        "metadata": metadata_copy,
                    }
                else:
                    # Fallback if we only have the ID
                    doc = {
                        "id": result[0],
                        "page_content": "",
                        "metadata": {},
                    }

                documents.append(doc)

            logger.debug(
                f"Found {len(documents)} relevant documents for query in {collection_name}"
            )
            return documents
        except Exception as e:
            logger.error(
                f"Failed to query vectors in collection {collection_name}: {str(e)}"
            )
            raise

    def create_vector_collection(
        self, collection_name: str, dimensions: int = 1536
    ) -> Any:
        """Create a new vector collection."""
        if not self.vecs_client:
            raise ValueError("Vecs client not initialized")

        try:
            collection = self.vecs_client.create_collection(
                name=collection_name, dimension=dimensions
            )
            self._vector_collections[collection_name] = collection
            logger.info(f"Created vector collection: {collection_name}")
            return collection
        except Exception as e:
            logger.error(
                f"Failed to create vector collection {collection_name}: {str(e)}"
            )
            raise

    def create_vector_index(
        self,
        collection_name: str,
        method: str = "hnsw",
        measure: str = "cosine_distance",
    ) -> bool:
        """Create an index on a vector collection for faster queries.

        Args:
            collection_name: Name of the collection to index
            method: Index method ('auto', 'hnsw', or 'ivfflat')
            measure: Distance measure ('cosine_distance', 'l2_distance', 'max_inner_product')

        Returns:
            bool: True if index was created successfully
        """
        if not self.vecs_client:
            raise ValueError("Vecs client not initialized")

        try:
            collection = self.get_vector_collection(collection_name)
            collection.create_index(method=method, measure=measure)
            logger.info(f"Created index on vector collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(
                f"Failed to create index on vector collection {collection_name}: {str(e)}"
            )
            return False

    def delete_vector_collection(self, collection_name: str) -> bool:
        """Delete a vector collection."""
        if not self.vecs_client:
            raise ValueError("Vecs client not initialized")

        try:
            self.vecs_client.delete_collection(name=collection_name)
            if collection_name in self._vector_collections:
                del self._vector_collections[collection_name]
            logger.info(f"Deleted vector collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(
                f"Failed to delete vector collection {collection_name}: {str(e)}"
            )
            return False

    # ----------------------------------------------------------------
    # 18. PROMPTS
    # ----------------------------------------------------------------
    def create_prompt(self, new_prompt: "PromptCreate") -> "Prompt":
        """Create a new prompt."""
        payload = new_prompt.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("prompts").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from prompts insert.")
        return Prompt(**data[0])

    def get_prompt(self, prompt_id: UUID) -> Optional["Prompt"]:
        """Get a prompt by ID."""
        response = (
            self.client.table("prompts")
            .select("*")
            .eq("id", str(prompt_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Prompt(**response.data)

    def list_prompts(self, filters: Optional["PromptFilter"] = None) -> List["Prompt"]:
        """List prompts with optional filters."""
        query = self.client.table("prompts").select("*")
        if filters:
            if filters.dao_id is not None:
                query = query.eq("dao_id", str(filters.dao_id))
            if filters.agent_id is not None:
                query = query.eq("agent_id", str(filters.agent_id))
            if filters.profile_id is not None:
                query = query.eq("profile_id", str(filters.profile_id))
            if filters.is_active is not None:
                query = query.eq("is_active", filters.is_active)
        response = query.execute()
        data = response.data or []
        return [Prompt(**row) for row in data]

    def update_prompt(
        self, prompt_id: UUID, update_data: "PromptBase"
    ) -> Optional["Prompt"]:
        """Update a prompt."""
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_prompt(prompt_id)
        response = (
            self.client.table("prompts")
            .update(payload)
            .eq("id", str(prompt_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Prompt(**updated[0])

    def delete_prompt(self, prompt_id: UUID) -> bool:
        """Delete a prompt."""
        response = (
            self.client.table("prompts").delete().eq("id", str(prompt_id)).execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # CHAIN STATE
    # ----------------------------------------------------------------
    def create_chain_state(self, new_chain_state: "ChainStateCreate") -> "ChainState":
        """Create a new chain state record."""
        payload = new_chain_state.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("chain_states").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from chain_states insert.")
        return ChainState(**data[0])

    def get_chain_state(self, chain_state_id: UUID) -> Optional["ChainState"]:
        """Get a chain state record by ID."""
        response = (
            self.client.table("chain_states")
            .select("*")
            .eq("id", str(chain_state_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return ChainState(**response.data)

    def list_chain_states(
        self, filters: Optional["ChainStateFilter"] = None
    ) -> List["ChainState"]:
        """List chain state records with optional filters."""
        query = self.client.table("chain_states").select("*")
        if filters:
            if filters.network is not None:
                query = query.eq("network", filters.network)
        response = query.execute()
        data = response.data or []
        return [ChainState(**row) for row in data]

    def update_chain_state(
        self, chain_state_id: UUID, update_data: "ChainStateBase"
    ) -> Optional["ChainState"]:
        """Update a chain state record."""
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_chain_state(chain_state_id)
        response = (
            self.client.table("chain_states")
            .update(payload)
            .eq("id", str(chain_state_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return ChainState(**updated[0])

    def delete_chain_state(self, chain_state_id: UUID) -> bool:
        """Delete a chain state record."""
        response = (
            self.client.table("chain_states")
            .delete()
            .eq("id", str(chain_state_id))
            .execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    def get_latest_chain_state(
        self, network: str = "mainnet"
    ) -> Optional["ChainState"]:
        """Get the latest chain state for a given network.

        Args:
            network (str): The network to get the chain state for. Defaults to "mainnet".

        Returns:
            Optional[ChainState]: The latest chain state for the network, or None if no chain state exists.
        """
        try:
            response = (
                self.client.table("chain_states")
                .select("*")
                .eq("network", network)
                .order("block_height", desc=True)
                .limit(1)
                .execute()
            )

            # Check if we got any data back
            if not response.data or len(response.data) == 0:
                return None

            # Return the first (and only) result
            return ChainState(**response.data[0])

        except Exception as e:
            logger.error(
                f"Error getting latest chain state for network {network}: {str(e)}"
            )
            return None

    # ----------------------------------------------------------------
    # HELPER FUNCTIONS
    # ----------------------------------------------------------------
    def verify_session_token(self, token: str) -> Optional[str]:
        try:
            user = self.client.auth.get_user(token)
            return user.user.email
        except Exception:
            return None

    def upload_file(self, file_path: str, file: bytes) -> str:
        """Upload a file to Supabase storage.

        Args:
            file_path: The path where the file will be stored in the bucket
            file: The file content in bytes

        Returns:
            str: The public URL of the uploaded file

        Raises:
            ValueError: If file_path is empty or file is None
            StorageError: If upload fails or public URL cannot be generated
            Exception: For other unexpected errors
        """
        if not file_path or not file:
            raise ValueError("File path and file content are required")

        if not self.bucket_name:
            raise ValueError("Storage bucket name is not configured")

        def attempt_upload(attempt: int) -> Optional[str]:
            try:
                logger.debug(
                    f"Attempting file upload to {file_path} (attempt {attempt})"
                )
                upload_response = self.client.storage.from_(self.bucket_name).upload(
                    file_path,
                    file,
                    {"upsert": "true"},  # Override if file exists
                )

                if not upload_response:
                    raise Exception("Upload failed - no response received")

                logger.debug(f"Upload successful: {upload_response}")

                # Get public URL
                public_url = self.client.storage.from_(self.bucket_name).get_public_url(
                    file_path
                )
                if not public_url:
                    raise Exception("Failed to generate public URL")

                # Remove trailing '?' if there are no query parameters
                if public_url.endswith("?"):
                    public_url = public_url[:-1]

                return public_url

            except Exception as e:
                logger.error(f"Upload attempt {attempt} failed: {str(e)}")
                if attempt >= self.MAX_UPLOAD_RETRIES:
                    raise
                time.sleep(self.RETRY_DELAY_SECONDS * attempt)  # Exponential backoff
                return None

        # Attempt upload with retries
        last_error = None
        for attempt in range(1, self.MAX_UPLOAD_RETRIES + 1):
            try:
                if result := attempt_upload(attempt):
                    return result
            except Exception as e:
                last_error = e

        # If we get here, all retries failed
        raise Exception(
            f"Failed to upload file after {self.MAX_UPLOAD_RETRIES} attempts: {str(last_error)}"
        )

    # ----------------------------------------------------------------
    # 0. QUEUE MESSAGES
    # ----------------------------------------------------------------
    def create_queue_message(
        self, new_queue_message: "QueueMessageCreate"
    ) -> "QueueMessage":
        """Create a new queue message with deduplication logic to prevent 5x message multiplication."""

        # Check for existing unprocessed messages with same content to prevent duplicates
        if new_queue_message.dao_id and new_queue_message.message:
            try:
                # Use Supabase query to find existing unprocessed messages
                query = (
                    self.client.table("queue")
                    .select("*")
                    .eq("type", new_queue_message.type)
                    .eq("dao_id", str(new_queue_message.dao_id))
                    .eq("is_processed", False)
                )

                # Add wallet_id filter if present
                if new_queue_message.wallet_id:
                    query = query.eq("wallet_id", str(new_queue_message.wallet_id))

                response = query.execute()
                existing_data = response.data or []

                # Check for duplicate content in existing messages
                new_message_str = (
                    str(new_queue_message.message) if new_queue_message.message else ""
                )
                for existing_row in existing_data:
                    existing_message_str = str(existing_row.get("message", ""))
                    if existing_message_str == new_message_str:
                        existing_message = QueueMessage(**existing_row)
                        logger.debug(
                            f"Duplicate queue message detected for DAO {new_queue_message.dao_id}, "
                            f"type {new_queue_message.type}, returning existing message {existing_message.id}"
                        )
                        return existing_message

            except Exception as e:
                # If deduplication check fails, log warning but continue with creation
                logger.warning(
                    f"Deduplication check failed: {str(e)}, proceeding with message creation"
                )

        # No duplicate found or deduplication skipped, create new message using Supabase
        try:
            payload = new_queue_message.model_dump(exclude_unset=True, mode="json")
            response = self.client.table("queue").insert(payload).execute()
            data = response.data or []
            if not data:
                raise ValueError(
                    "No data returned from Supabase insert for queue message."
                )

            created_message = QueueMessage(**data[0])
            logger.debug(
                f"Created new queue message {created_message.id} for DAO {new_queue_message.dao_id}, type {new_queue_message.type}"
            )
            return created_message

        except Exception as e:
            logger.error(f"Failed to create queue message in Supabase: {str(e)}")
            raise

    def get_queue_message(self, queue_message_id: UUID) -> Optional["QueueMessage"]:
        response = (
            self.client.table("queue")
            .select("*")
            .eq("id", str(queue_message_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return QueueMessage(**response.data)

    def list_queue_messages(
        self, filters: Optional["QueueMessageFilter"] = None
    ) -> List["QueueMessage"]:
        query = self.client.table("queue").select("*")
        if filters:
            if filters.type is not None:
                query = query.eq("type", filters.type)
            if filters.is_processed is not None:
                query = query.eq("is_processed", filters.is_processed)
            if filters.wallet_id is not None:
                query = query.eq("wallet_id", filters.wallet_id)
            if filters.dao_id is not None:
                query = query.eq("dao_id", str(filters.dao_id))
        response = query.execute()
        data = response.data or []
        return [QueueMessage(**row) for row in data]

    def update_queue_message(
        self, queue_message_id: UUID, update_data: "QueueMessageBase"
    ) -> Optional["QueueMessage"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_queue_message(queue_message_id)

        response = (
            self.client.table("queue")
            .update(payload)
            .eq("id", str(queue_message_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return QueueMessage(**updated[0])

    def delete_queue_message(self, queue_message_id: UUID) -> bool:
        response = (
            self.client.table("queue")
            .delete()
            .eq("id", str(queue_message_id))
            .execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 0. WALLETS
    # ----------------------------------------------------------------

    def create_wallet(self, new_wallet: "WalletCreate") -> "Wallet":
        payload = new_wallet.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("wallets").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from Supabase insert for wallet.")
        return Wallet(**data[0])

    def get_wallet(self, wallet_id: UUID) -> Optional["Wallet"]:
        response = (
            self.client.table("wallets")
            .select("*")
            .eq("id", str(wallet_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Wallet(**response.data)

    def list_wallets(self, filters: Optional["WalletFilter"] = None) -> List["Wallet"]:
        query = self.client.table("wallets").select("*")
        if filters:
            if filters.profile_id:
                query = query.eq("profile_id", str(filters.profile_id))
            if filters.agent_id:
                query = query.eq("agent_id", str(filters.agent_id))
            if filters.mainnet_address:
                query = query.eq("mainnet_address", filters.mainnet_address)
            if filters.testnet_address:
                query = query.eq("testnet_address", filters.testnet_address)
        response = query.execute()
        data = response.data or []
        return [Wallet(**row) for row in data]

    def list_wallets_n(
        self, filters: Optional["WalletFilterN"] = None
    ) -> List["Wallet"]:
        """Enhanced wallets listing with support for batch operations and advanced filtering."""
        query = self.client.table("wallets").select("*")

        if filters:
            # Standard equality filters
            if filters.agent_id is not None:
                query = query.eq("agent_id", str(filters.agent_id))
            if filters.profile_id is not None:
                query = query.eq("profile_id", str(filters.profile_id))
            if filters.mainnet_address is not None:
                query = query.eq("mainnet_address", filters.mainnet_address)
            if filters.testnet_address is not None:
                query = query.eq("testnet_address", filters.testnet_address)

            # Batch filters using 'in_' operations
            if filters.ids is not None and len(filters.ids) > 0:
                id_strings = [str(wallet_id) for wallet_id in filters.ids]
                query = query.in_("id", id_strings)
            if filters.agent_ids is not None and len(filters.agent_ids) > 0:
                agent_id_strings = [str(agent_id) for agent_id in filters.agent_ids]
                query = query.in_("agent_id", agent_id_strings)
            if filters.profile_ids is not None and len(filters.profile_ids) > 0:
                profile_id_strings = [
                    str(profile_id) for profile_id in filters.profile_ids
                ]
                query = query.in_("profile_id", profile_id_strings)
            if (
                filters.mainnet_addresses is not None
                and len(filters.mainnet_addresses) > 0
            ):
                query = query.in_("mainnet_address", filters.mainnet_addresses)
            if (
                filters.testnet_addresses is not None
                and len(filters.testnet_addresses) > 0
            ):
                query = query.in_("testnet_address", filters.testnet_addresses)

        try:
            response = query.execute()
            data = response.data or []
            return [Wallet(**row) for row in data]
        except Exception as e:
            logger.error(f"Error in list_wallets_n: {str(e)}")
            # Fallback to original list_wallets if enhanced filtering fails
            if filters:
                # Convert enhanced filter to basic filter for fallback
                basic_filter = WalletFilter(
                    agent_id=filters.agent_id,
                    profile_id=filters.profile_id,
                    mainnet_address=filters.mainnet_address,
                    testnet_address=filters.testnet_address,
                )
                return self.list_wallets(basic_filter)
            else:
                return self.list_wallets()

    def update_wallet(
        self, wallet_id: UUID, update_data: "WalletBase"
    ) -> Optional["Wallet"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            # Nothing to update
            return self.get_wallet(wallet_id)
        response = (
            self.client.table("wallets")
            .update(payload)
            .eq("id", str(wallet_id))
            .execute()
        )
        updated_rows = response.data or []
        if not updated_rows:
            return None
        return Wallet(**updated_rows[0])

    def delete_wallet(self, wallet_id: UUID) -> bool:
        response = (
            self.client.table("wallets").delete().eq("id", str(wallet_id)).execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    def get_agents_with_dao_tokens(
        self, dao_id: UUID
    ) -> List["AgentWithWalletTokenDTO"]:
        """Get all agents with wallets that hold tokens for a specific DAO using models."""
        result = []

        # Step 1: Find all holders for this DAO
        holders = self.list_holders(HolderFilter(dao_id=dao_id))

        if not holders:
            return []

        # Get the DAO information once
        dao = self.get_dao(dao_id)
        if not dao:
            logger.warning(f"DAO with ID {dao_id} not found")
            return []

        # Process each holder
        for holder in holders:
            # Skip holders with no wallet_id
            if not holder.wallet_id:
                logger.warning(f"Holder {holder.id} has no wallet_id, skipping")
                continue

            # Step 2: Get the wallet
            wallet = self.get_wallet(holder.wallet_id)
            if not wallet:
                logger.warning(f"Wallet with ID {holder.wallet_id} not found")
                continue

            # Skip wallets not associated with agents
            if not wallet.agent_id:
                continue

            # Step 3: Get the agent
            agent = self.get_agent(wallet.agent_id)
            if not agent:
                logger.warning(f"Agent with ID {wallet.agent_id} not found")
                continue

            # Skip holders with no token_id
            if not holder.token_id:
                logger.warning(f"Holder {holder.id} has no token_id, skipping")
                continue

            # Step 4: Get the token
            token = self.get_token(holder.token_id)
            if not token:
                logger.warning(f"Token with ID {holder.token_id} not found")
                continue

            # Step 5: Create the DTO
            wallet_address = wallet.mainnet_address or wallet.testnet_address
            if not wallet_address:
                logger.warning(f"Wallet {wallet.id} has no address")
                continue

            # Add to results
            result.append(
                AgentWithWalletTokenDTO(
                    agent_id=agent.id,
                    wallet_id=wallet.id,
                    wallet_address=wallet_address,
                    token_id=token.id,
                    token_amount=holder.amount,
                    dao_id=dao_id,
                    dao_name=dao.name,
                )
            )

        return result

    # ----------------------------------------------------------------
    # 1. AGENTS
    # ----------------------------------------------------------------
    def create_agent(self, new_agent: "AgentCreate") -> "Agent":
        payload = new_agent.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("agents").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from Supabase insert for agent.")
        return Agent(**data[0])

    def get_agent(self, agent_id: UUID) -> Optional["Agent"]:
        response = (
            self.client.table("agents")
            .select("*")
            .eq("id", str(agent_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Agent(**response.data)

    def list_agents(self, filters: Optional["AgentFilter"] = None) -> List["Agent"]:
        query = self.client.table("agents").select("*")
        if filters:
            if filters.profile_id is not None:
                query = query.eq("profile_id", str(filters.profile_id))
            if filters.account_contract is not None:
                query = query.eq("account_contract", filters.account_contract)
            if (
                filters.account_contracts is not None
                and len(filters.account_contracts) > 0
            ):
                query = query.in_("account_contract", filters.account_contracts)
        response = query.execute()
        data = response.data or []
        return [Agent(**row) for row in data]

    def update_agent(
        self, agent_id: UUID, update_data: "AgentBase"
    ) -> Optional["Agent"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            # Nothing to update
            return self.get_agent(agent_id)
        response = (
            self.client.table("agents")
            .update(payload)
            .eq("id", str(agent_id))
            .execute()
        )
        updated_rows = response.data or []
        if not updated_rows:
            return None
        return Agent(**updated_rows[0])

    def delete_agent(self, agent_id: UUID) -> bool:
        response = (
            self.client.table("agents").delete().eq("id", str(agent_id)).execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 2. CAPABILITIES
    # ----------------------------------------------------------------
    def create_extension(self, new_ext: "ExtensionCreate") -> "Extension":
        payload = new_ext.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("extensions").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from insert for extension.")
        return Extension(**data[0])

    def get_extension(self, ext_id: UUID) -> Optional["Extension"]:
        response = (
            self.client.table("extensions")
            .select("*")
            .eq("id", str(ext_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Extension(**response.data)

    def list_extensions(
        self, filters: Optional["ExtensionFilter"] = None
    ) -> List["Extension"]:
        query = self.client.table("extensions").select("*")
        if filters:
            if filters.dao_id is not None:
                query = query.eq("dao_id", str(filters.dao_id))
            if filters.type is not None:
                query = query.eq("type", filters.type)
            if filters.status is not None:
                query = query.eq("status", str(filters.status))
            if filters.subtype is not None:
                query = query.eq("subtype", filters.subtype)
            if filters.contract_principal is not None:
                query = query.eq("contract_principal", filters.contract_principal)
        response = query.execute()
        data = response.data or []
        return [Extension(**row) for row in data]

    def update_extension(
        self, ext_id: UUID, update_data: "ExtensionBase"
    ) -> Optional["Extension"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_extension(ext_id)
        response = (
            self.client.table("extensions")
            .update(payload)
            .eq("id", str(ext_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Extension(**updated[0])

    def delete_extension(self, ext_id: UUID) -> bool:
        response = (
            self.client.table("extensions").delete().eq("id", str(ext_id)).execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 3. DAOS
    # ----------------------------------------------------------------
    def create_dao(self, new_dao: "DAOCreate") -> "DAO":
        payload = new_dao.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("daos").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned for dao insert.")
        return DAO(**data[0])

    def get_dao(self, dao_id: UUID) -> Optional["DAO"]:
        response = (
            self.client.table("daos")
            .select("*")
            .eq("id", str(dao_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return DAO(**response.data)

    def list_daos(self, filters: Optional["DAOFilter"] = None) -> List["DAO"]:
        query = self.client.table("daos").select("*")
        if filters:
            if filters.name is not None:
                query = query.eq("name", filters.name)
            if filters.is_deployed is not None:
                query = query.eq("is_deployed", filters.is_deployed)
            if filters.is_broadcasted is not None:
                query = query.eq("is_broadcasted", filters.is_broadcasted)
        response = query.execute()
        data = response.data or []
        return [DAO(**row) for row in data]

    def update_dao(self, dao_id: UUID, update_data: "DAOBase") -> Optional["DAO"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_dao(dao_id)
        response = (
            self.client.table("daos").update(payload).eq("id", str(dao_id)).execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return DAO(**updated[0])

    def delete_dao(self, dao_id: UUID) -> bool:
        response = self.client.table("daos").delete().eq("id", str(dao_id)).execute()
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 4. CONVERSATIONS
    # ----------------------------------------------------------------

    # ----------------------------------------------------------------
    # 7.5 KEYS
    # ----------------------------------------------------------------
    def create_key(self, new_key: "KeyCreate") -> "Key":
        payload = new_key.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("keys").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from key insert.")
        return Key(**data[0])

    def get_key(self, key_id: UUID) -> Optional["Key"]:
        response = (
            self.client.table("keys")
            .select("*")
            .eq("id", str(key_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Key(**response.data)

    def list_keys(self, filters: Optional["KeyFilter"] = None) -> List["Key"]:
        query = self.client.table("keys").select("*")
        if filters:
            if filters.id is not None:
                query = query.eq("id", str(filters.id))
            if filters.profile_id is not None:
                query = query.eq("profile_id", str(filters.profile_id))
            if filters.is_enabled is not None:
                query = query.eq("is_enabled", filters.is_enabled)
        response = query.execute()
        data = response.data or []
        return [Key(**row) for row in data]

    def update_key(self, key_id: UUID, update_data: "KeyBase") -> Optional["Key"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_key(key_id)
        response = (
            self.client.table("keys").update(payload).eq("id", str(key_id)).execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Key(**updated[0])

    def delete_key(self, key_id: UUID) -> bool:
        response = self.client.table("keys").delete().eq("id", str(key_id)).execute()
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 8. PROFILES
    # ----------------------------------------------------------------
    def create_profile(self, new_profile: "ProfileCreate") -> "Profile":
        payload = new_profile.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("profiles").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from profile insert.")
        return Profile(**data[0])

    def get_profile(self, profile_id: UUID) -> Optional["Profile"]:
        response = (
            self.client.table("profiles")
            .select("*")
            .eq("id", str(profile_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Profile(**response.data)

    def list_profiles(
        self, filters: Optional["ProfileFilter"] = None
    ) -> List["Profile"]:
        query = self.client.table("profiles").select("*")
        if filters:
            if filters.email is not None:
                query = query.eq("email", filters.email)
            if filters.username is not None:
                query = query.eq("username", filters.username)
            if filters.has_dao_agent is not None:
                query = query.eq("has_dao_agent", filters.has_dao_agent)
            if filters.has_completed_guide is not None:
                query = query.eq("has_completed_guide", filters.has_completed_guide)
        response = query.execute()
        data = response.data or []
        return [Profile(**row) for row in data]

    def list_profiles_by_username(self, username: str) -> List["Profile"]:
        """Get profiles by username."""
        return self.list_profiles(ProfileFilter(username=username))

    def update_profile(
        self, profile_id: UUID, update_data: "ProfileBase"
    ) -> Optional["Profile"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_profile(profile_id)
        response = (
            self.client.table("profiles")
            .update(payload)
            .eq("id", str(profile_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Profile(**updated[0])

    def delete_profile(self, profile_id: UUID) -> bool:
        response = (
            self.client.table("profiles").delete().eq("id", str(profile_id)).execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 9. PROPOSALS
    # ----------------------------------------------------------------
    def create_proposal(self, new_proposal: "ProposalCreate") -> "Proposal":
        payload = new_proposal.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("proposals").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from proposal insert.")
        return Proposal(**data[0])

    def get_proposal(self, proposal_id: UUID) -> Optional["Proposal"]:
        response = (
            self.client.table("proposals")
            .select("*")
            .eq("id", str(proposal_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Proposal(**response.data)

    def list_proposals(
        self, filters: Optional["ProposalFilter"] = None
    ) -> List["Proposal"]:
        query = self.client.table("proposals").select("*")
        if filters:
            if filters.dao_id is not None:
                query = query.eq("dao_id", str(filters.dao_id))
            if filters.status is not None:
                query = query.eq("status", str(filters.status))
            if filters.contract_principal is not None:
                query = query.eq("contract_principal", filters.contract_principal)
            if filters.proposal_id is not None:
                query = query.eq("proposal_id", filters.proposal_id)
            if filters.executed is not None:
                query = query.eq("executed", filters.executed)
            if filters.passed is not None:
                query = query.eq("passed", filters.passed)
            if filters.met_quorum is not None:
                query = query.eq("met_quorum", filters.met_quorum)
            if filters.met_threshold is not None:
                query = query.eq("met_threshold", filters.met_threshold)
            if filters.type is not None:
                query = query.eq("type", filters.type)
            if filters.tx_id is not None:
                query = query.eq("tx_id", filters.tx_id)
            if filters.has_embedding is not None:
                query = query.eq("has_embedding", filters.has_embedding)
        response = query.execute()
        data = response.data or []
        return [Proposal(**row) for row in data]

    def update_proposal(
        self, proposal_id: UUID, update_data: "ProposalBase"
    ) -> Optional["Proposal"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_proposal(proposal_id)
        response = (
            self.client.table("proposals")
            .update(payload)
            .eq("id", str(proposal_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Proposal(**updated[0])

    def delete_proposal(self, proposal_id: UUID) -> bool:
        response = (
            self.client.table("proposals").delete().eq("id", str(proposal_id)).execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 12. TASKS
    # ----------------------------------------------------------------
    def create_task(self, new_task: "TaskCreate") -> "Task":
        payload = new_task.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("tasks").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from task insert.")
        return Task(**data[0])

    def get_task(self, task_id: UUID) -> Optional["Task"]:
        response = (
            self.client.table("tasks")
            .select("*")
            .eq("id", str(task_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Task(**response.data)

    def list_tasks(self, filters: Optional["TaskFilter"] = None) -> List["Task"]:
        query = self.client.table("tasks").select("*")
        if filters:
            if filters.profile_id is not None:
                query = query.eq("profile_id", str(filters.profile_id))
            if filters.agent_id is not None:
                query = query.eq("agent_id", str(filters.agent_id))
            if filters.is_scheduled is not None:
                query = query.eq("is_scheduled", filters.is_scheduled)
        response = query.execute()
        data = response.data or []
        return [Task(**row) for row in data]

    def update_task(self, task_id: UUID, update_data: "TaskBase") -> Optional["Task"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_task(task_id)
        response = (
            self.client.table("tasks").update(payload).eq("id", str(task_id)).execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Task(**updated[0])

    def delete_task(self, task_id: UUID) -> bool:
        response = self.client.table("tasks").delete().eq("id", str(task_id)).execute()
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 13. TELEGRAM USERS
    # ----------------------------------------------------------------
    def create_telegram_user(self, new_tu: "TelegramUserCreate") -> "TelegramUser":
        payload = new_tu.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("telegram_users").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from telegram_users insert.")
        return TelegramUser(**data[0])

    def get_telegram_user(self, telegram_user_id: UUID) -> Optional["TelegramUser"]:
        response = (
            self.client.table("telegram_users")
            .select("*")
            .eq("id", str(telegram_user_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return TelegramUser(**response.data)

    def list_telegram_users(
        self, filters: Optional["TelegramUserFilter"] = None
    ) -> List["TelegramUser"]:
        query = self.client.table("telegram_users").select("*")
        if filters:
            if filters.telegram_user_id is not None:
                query = query.eq("telegram_user_id", filters.telegram_user_id)
            if filters.profile_id is not None:
                query = query.eq("profile_id", str(filters.profile_id))
            if filters.is_registered is not None:
                query = query.eq("is_registered", filters.is_registered)
        response = query.execute()
        data = response.data or []
        return [TelegramUser(**row) for row in data]

    def update_telegram_user(
        self, telegram_user_id: UUID, update_data: "TelegramUserBase"
    ) -> Optional["TelegramUser"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_telegram_user(telegram_user_id)
        response = (
            self.client.table("telegram_users")
            .update(payload)
            .eq("id", str(telegram_user_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return TelegramUser(**updated[0])

    def delete_telegram_user(self, telegram_user_id: UUID) -> bool:
        response = (
            self.client.table("telegram_users")
            .delete()
            .eq("id", str(telegram_user_id))
            .execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 14. TOKENS
    # ----------------------------------------------------------------
    def create_token(self, new_token: "TokenCreate") -> "Token":
        payload = new_token.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("tokens").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from tokens insert.")
        return Token(**data[0])

    def get_token(self, token_id: UUID) -> Optional["Token"]:
        response = (
            self.client.table("tokens")
            .select("*")
            .eq("id", str(token_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Token(**response.data)

    def list_tokens(self, filters: Optional["TokenFilter"] = None) -> List["Token"]:
        query = self.client.table("tokens").select("*")
        if filters:
            if filters.dao_id is not None:
                query = query.eq("dao_id", str(filters.dao_id))
            if filters.name is not None:
                query = query.eq("name", filters.name)
            if filters.symbol is not None:
                query = query.eq("symbol", filters.symbol)
            if filters.status is not None:
                query = query.eq("status", str(filters.status))
            if filters.contract_principal is not None:
                query = query.eq("contract_principal", filters.contract_principal)
        response = query.execute()
        data = response.data or []
        return [Token(**row) for row in data]

    def update_token(
        self, token_id: UUID, update_data: "TokenBase"
    ) -> Optional["Token"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_token(token_id)
        response = (
            self.client.table("tokens")
            .update(payload)
            .eq("id", str(token_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Token(**updated[0])

    def delete_token(self, token_id: UUID) -> bool:
        response = (
            self.client.table("tokens").delete().eq("id", str(token_id)).execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 15. VOTES
    # ----------------------------------------------------------------
    def create_vote(self, new_vote: "VoteCreate") -> "Vote":
        payload = new_vote.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("votes").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from votes insert.")
        return Vote(**data[0])

    def get_vote(self, vote_id: UUID) -> Optional["Vote"]:
        response = (
            self.client.table("votes")
            .select("*")
            .eq("id", str(vote_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Vote(**response.data)

    def list_votes(self, filters: Optional["VoteFilter"] = None) -> List["Vote"]:
        query = self.client.table("votes").select("*")
        if filters:
            if filters.wallet_id is not None:
                query = query.eq("wallet_id", str(filters.wallet_id))
            if filters.dao_id is not None:
                query = query.eq("dao_id", str(filters.dao_id))
            if filters.agent_id is not None:
                query = query.eq("agent_id", str(filters.agent_id))
            if filters.proposal_id is not None:
                query = query.eq("proposal_id", str(filters.proposal_id))
            if filters.answer is not None:
                query = query.eq("answer", filters.answer)
            if filters.address is not None:
                query = query.eq("address", filters.address)
            if filters.voted is not None:
                query = query.eq("voted", filters.voted)
            if filters.model is not None:
                query = query.eq("model", filters.model)
            if filters.tx_id is not None:
                query = query.eq("tx_id", filters.tx_id)
            if filters.profile_id is not None:
                query = query.eq("profile_id", str(filters.profile_id))
            if filters.evaluation_score is not None:
                query = query.eq("evaluation_score", filters.evaluation_score)
            if filters.flags is not None:
                query = query.eq("flags", filters.flags)

            # Batch filters for efficient querying
            if filters.wallet_ids is not None and len(filters.wallet_ids) > 0:
                wallet_id_strings = [str(wallet_id) for wallet_id in filters.wallet_ids]
                query = query.in_("wallet_id", wallet_id_strings)
            if filters.proposal_ids is not None and len(filters.proposal_ids) > 0:
                proposal_id_strings = [
                    str(proposal_id) for proposal_id in filters.proposal_ids
                ]
                query = query.in_("proposal_id", proposal_id_strings)

        response = query.execute()
        data = response.data or []
        return [Vote(**row) for row in data]

    def check_proposals_evaluated_batch(
        self, proposal_wallet_pairs: List[tuple[UUID, UUID]]
    ) -> Dict[tuple[UUID, UUID], bool]:
        """Check which proposal-wallet pairs have already been evaluated in a single query.

        Args:
            proposal_wallet_pairs: List of (proposal_id, wallet_id) tuples to check

        Returns:
            Dict mapping (proposal_id, wallet_id) tuples to True if evaluated, False otherwise
        """
        if not proposal_wallet_pairs:
            return {}

        # Extract unique proposal and wallet IDs
        proposal_ids = list(set([pair[0] for pair in proposal_wallet_pairs]))
        wallet_ids = list(set([pair[1] for pair in proposal_wallet_pairs]))

        # Query for existing votes with evaluation data
        vote_filter = VoteFilter(proposal_ids=proposal_ids, wallet_ids=wallet_ids)
        existing_votes = self.list_votes(filters=vote_filter)

        # Build lookup set of evaluated pairs
        evaluated_pairs = set()
        for vote in existing_votes:
            # Check if vote has evaluation data (indicating evaluation was performed)
            if (
                vote.evaluation_score
                or vote.evaluation
                or vote.reasoning
                or vote.confidence is not None
            ):
                evaluated_pairs.add((vote.proposal_id, vote.wallet_id))

        # Return result mapping for all requested pairs
        return {pair: pair in evaluated_pairs for pair in proposal_wallet_pairs}

    def update_vote(self, vote_id: UUID, update_data: "VoteBase") -> Optional["Vote"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_vote(vote_id)
        response = (
            self.client.table("votes").update(payload).eq("id", str(vote_id)).execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Vote(**updated[0])

    def delete_vote(self, vote_id: UUID) -> bool:
        response = self.client.table("votes").delete().eq("id", str(vote_id)).execute()
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 15. VETOS
    # ----------------------------------------------------------------
    def create_veto(self, new_veto: "VetoCreate") -> "Veto":
        payload = new_veto.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("vetos").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from vetos insert.")
        return Veto(**data[0])

    def get_veto(self, veto_id: UUID) -> Optional["Veto"]:
        response = (
            self.client.table("vetos")
            .select("*")
            .eq("id", str(veto_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Veto(**response.data)

    def list_vetos(self, filters: Optional["VetoFilter"] = None) -> List["Veto"]:
        query = self.client.table("vetos").select("*")
        if filters:
            if filters.wallet_id is not None:
                query = query.eq("wallet_id", str(filters.wallet_id))
            if filters.dao_id is not None:
                query = query.eq("dao_id", str(filters.dao_id))
            if filters.agent_id is not None:
                query = query.eq("agent_id", str(filters.agent_id))
            if filters.proposal_id is not None:
                query = query.eq("proposal_id", str(filters.proposal_id))
            if filters.address is not None:
                query = query.eq("address", filters.address)
            if filters.tx_id is not None:
                query = query.eq("tx_id", filters.tx_id)
            if filters.contract_caller is not None:
                query = query.eq("contract_caller", filters.contract_caller)
            if filters.tx_sender is not None:
                query = query.eq("tx_sender", filters.tx_sender)
            if filters.vetoer_user_id is not None:
                query = query.eq("vetoer_user_id", filters.vetoer_user_id)
            if filters.profile_id is not None:
                query = query.eq("profile_id", str(filters.profile_id))
        response = query.execute()
        data = response.data or []
        return [Veto(**row) for row in data]

    def update_veto(self, veto_id: UUID, update_data: "VetoBase") -> Optional["Veto"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_veto(veto_id)
        response = (
            self.client.table("vetos").update(payload).eq("id", str(veto_id)).execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Veto(**updated[0])

    def delete_veto(self, veto_id: UUID) -> bool:
        response = self.client.table("vetos").delete().eq("id", str(veto_id)).execute()
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 16. X_CREDS
    # ----------------------------------------------------------------
    def create_x_creds(self, new_xc: "XCredsCreate") -> "XCreds":
        payload = new_xc.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("x_creds").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from x_creds insert.")
        return XCreds(**data[0])

    def get_x_creds(self, x_creds_id: UUID) -> Optional["XCreds"]:
        response = (
            self.client.table("x_creds")
            .select("*")
            .eq("id", str(x_creds_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return XCreds(**response.data)

    def list_x_creds(self, filters: Optional["XCredsFilter"] = None) -> List["XCreds"]:
        query = self.client.table("x_creds").select("*")
        if filters:
            if filters.username is not None:
                query = query.eq("username", filters.username)
            if filters.dao_id is not None:
                query = query.eq("dao_id", str(filters.dao_id))
        response = query.execute()
        data = response.data or []
        return [XCreds(**row) for row in data]

    def update_x_creds(
        self, x_creds_id: UUID, update_data: "XCredsBase"
    ) -> Optional["XCreds"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_x_creds(x_creds_id)
        response = (
            self.client.table("x_creds")
            .update(payload)
            .eq("id", str(x_creds_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return XCreds(**updated[0])

    def delete_x_creds(self, x_creds_id: UUID) -> bool:
        response = (
            self.client.table("x_creds").delete().eq("id", str(x_creds_id)).execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 16. X_USERS
    # ----------------------------------------------------------------
    def create_x_user(self, new_xu: "XUserCreate") -> "XUser":
        payload = new_xu.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("x_users").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from x_users insert.")
        return XUser(**data[0])

    def get_x_user(self, x_user_id: str) -> Optional["XUser"]:
        response = (
            self.client.table("x_users")
            .select("*")
            .eq("id", x_user_id)
            .single()
            .execute()
        )
        if not response.data:
            return None
        return XUser(**response.data)

    def list_x_users(self, filters: Optional["XUserFilter"] = None) -> List["XUser"]:
        query = self.client.table("x_users").select("*")
        if filters:
            if filters.username is not None:
                query = query.eq("username", filters.username)
            if filters.name is not None:
                query = query.eq("name", filters.name)
            if filters.user_id is not None:
                query = query.eq("user_id", filters.user_id)
            if filters.description is not None:
                query = query.eq("description", filters.description)
            if filters.location is not None:
                query = query.eq("location", filters.location)
            if filters.profile_image_url is not None:
                query = query.eq("profile_image_url", filters.profile_image_url)
            if filters.profile_banner_url is not None:
                query = query.eq("profile_banner_url", filters.profile_banner_url)
            if filters.protected is not None:
                query = query.eq("protected", filters.protected)
            if filters.verified is not None:
                query = query.eq("verified", filters.verified)
            if filters.verified_type is not None:
                query = query.eq("verified_type", filters.verified_type)
            if filters.subscription_type is not None:
                query = query.eq("subscription_type", filters.subscription_type)
        response = query.execute()
        data = response.data or []
        return [XUser(**row) for row in data]

    def update_x_user(
        self, x_user_id: UUID, update_data: "XUserBase"
    ) -> Optional["XUser"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_x_user(x_user_id)
        response = (
            self.client.table("x_users").update(payload).eq("id", x_user_id).execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return XUser(**updated[0])

    def delete_x_user(self, x_user_id: UUID) -> bool:
        response = self.client.table("x_users").delete().eq("id", x_user_id).execute()
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 16. X_TWEETS
    # ----------------------------------------------------------------
    def create_x_tweet(self, new_xt: "XTweetCreate") -> "XTweet":
        payload = new_xt.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("x_tweets").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from x_tweets insert.")
        return XTweet(**data[0])

    def get_x_tweet(self, x_tweet_id: UUID) -> Optional["XTweet"]:
        response = (
            self.client.table("x_tweets").select("*").eq("id", x_tweet_id).execute()
        )
        data = response.data or []
        if not data:
            return None

        return XTweet(**data[0])

    def list_x_tweets(self, filters: Optional["XTweetFilter"] = None) -> List["XTweet"]:
        query = self.client.table("x_tweets").select("*")
        if filters:
            if filters.author_id is not None:
                query = query.eq("author_id", filters.author_id)
            if filters.conversation_id is not None:
                query = query.eq("conversation_id", filters.conversation_id)
            if filters.tweet_id is not None:
                query = query.eq("tweet_id", filters.tweet_id)
            if filters.is_worthy is not None:
                query = query.eq("is_worthy", filters.is_worthy)
            if filters.tweet_type is not None:
                query = query.eq("tweet_type", filters.tweet_type)
            if filters.confidence_score is not None:
                query = query.eq("confidence_score", filters.confidence_score)
            if filters.reason is not None:
                query = query.eq("reason", filters.reason)
        response = query.execute()
        data = response.data or []

        return [XTweet(**row) for row in data]

    def update_x_tweet(
        self, x_tweet_id: UUID, update_data: "XTweetBase"
    ) -> Optional["XTweet"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_x_tweet(x_tweet_id)
        response = (
            self.client.table("x_tweets").update(payload).eq("id", x_tweet_id).execute()
        )
        updated = response.data or []
        if not updated:
            return None

        return XTweet(**updated[0])

    def delete_x_tweet(self, x_tweet_id: UUID) -> bool:
        response = self.client.table("x_tweets").delete().eq("id", x_tweet_id).execute()
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 17. SECRETS
    # ----------------------------------------------------------------
    def get_secret(self, secret_id: UUID) -> Optional["Secret"]:
        """Get a secret by its ID."""
        logger.debug(f"Getting secret with ID: {secret_id}")
        try:
            with self.Session() as session:
                secret_sql = (
                    session.query(SecretSQL)
                    .filter(SecretSQL.id == secret_id)
                    .one_or_none()
                )
                if not secret_sql:
                    logger.warning(f"No secret found with ID: {secret_id}")
                    return None
                return sqlalchemy_to_pydantic(secret_sql)
        except Exception as e:
            logger.error(f"Error getting secret: {e}")
            raise

    def list_secrets(self, filters: Optional["SecretFilter"] = None) -> List["Secret"]:
        """List secrets with optional filters."""
        logger.debug(f"Listing secrets with filters: {filters}")
        try:
            with self.Session() as session:
                query = session.query(SecretSQL)
                if filters:
                    if filters.name is not None:
                        query = query.filter(SecretSQL.name == filters.name)
                    if filters.description is not None:
                        query = query.filter(
                            SecretSQL.description == filters.description
                        )
                secret_sql_list = query.all()
                return [
                    sqlalchemy_to_pydantic(secret_sql) for secret_sql in secret_sql_list
                ]
        except Exception as e:
            logger.error(f"Error listing secrets: {e}")
            raise

    # ----------------------------------------------------------------
    # HOLDERS
    # ----------------------------------------------------------------
    def create_holder(self, new_holder: "HolderCreate") -> "Holder":
        """Create a new holder record."""
        payload = new_holder.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("holders").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from holders insert.")
        return Holder(**data[0])

    def get_holder(self, holder_id: UUID) -> Optional["Holder"]:
        """Get a holder record by ID."""
        response = (
            self.client.table("holders")
            .select("*")
            .eq("id", str(holder_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Holder(**response.data)

    def list_holders(self, filters: Optional["HolderFilter"] = None) -> List["Holder"]:
        """List holder records with optional filters."""
        query = self.client.table("holders").select("*")
        if filters:
            if filters.wallet_id is not None:
                query = query.eq("wallet_id", str(filters.wallet_id))
            if filters.token_id is not None:
                query = query.eq("token_id", str(filters.token_id))
            if filters.dao_id is not None:
                query = query.eq("dao_id", str(filters.dao_id))
        response = query.execute()
        data = response.data or []
        return [Holder(**row) for row in data]

    def update_holder(
        self, holder_id: UUID, update_data: "HolderBase"
    ) -> Optional["Holder"]:
        """Update a holder record."""
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_holder(holder_id)
        response = (
            self.client.table("holders")
            .update(payload)
            .eq("id", str(holder_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Holder(**updated[0])

    def delete_holder(self, holder_id: UUID) -> bool:
        """Delete a holder record."""
        response = (
            self.client.table("holders").delete().eq("id", str(holder_id)).execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 18. FEEDBACK
    # ----------------------------------------------------------------
    def create_feedback(self, new_feedback: "FeedbackCreate") -> "Feedback":
        """Create a new feedback record."""
        payload = new_feedback.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("feedback").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from feedback insert.")
        return Feedback(**data[0])

    def get_feedback(self, feedback_id: UUID) -> Optional["Feedback"]:
        """Get a feedback record by ID."""
        response = (
            self.client.table("feedback")
            .select("*")
            .eq("id", str(feedback_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Feedback(**response.data)

    def list_feedback(
        self, filters: Optional["FeedbackFilter"] = None
    ) -> List["Feedback"]:
        """List feedback records with optional filters."""
        query = self.client.table("feedback").select("*")

        if filters:
            if filters.profile_id is not None:
                query = query.eq("profile_id", str(filters.profile_id))
            if filters.dao_id is not None:
                query = query.eq("dao_id", str(filters.dao_id))
            if filters.proposal_id is not None:
                query = query.eq("proposal_id", str(filters.proposal_id))
            if filters.is_like is not None:
                query = query.eq("is_like", filters.is_like)

            # Batch filters
            if filters.profile_ids is not None:
                query = query.in_(
                    "profile_id", [str(pid) for pid in filters.profile_ids]
                )
            if filters.proposal_ids is not None:
                query = query.in_(
                    "proposal_id", [str(pid) for pid in filters.proposal_ids]
                )

        response = query.execute()
        data = response.data or []
        return [Feedback(**item) for item in data]

    def update_feedback(
        self, feedback_id: UUID, update_data: "FeedbackBase"
    ) -> Optional["Feedback"]:
        """Update a feedback record."""
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_feedback(feedback_id)
        response = (
            self.client.table("feedback")
            .update(payload)
            .eq("id", str(feedback_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Feedback(**updated[0])

    def delete_feedback(self, feedback_id: UUID) -> bool:
        """Delete a feedback record."""
        response = (
            self.client.table("feedback").delete().eq("id", str(feedback_id)).execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 19. PROPOSALS_N
    # ----------------------------------------------------------------
    def list_proposals_n(
        self, filters: Optional["ProposalFilterN"] = None
    ) -> List["Proposal"]:
        """Enhanced proposals listing with support for batch operations and advanced filtering."""
        query = self.client.table("proposals").select("*")

        if filters:
            # Standard equality filters
            if filters.dao_id is not None:
                query = query.eq("dao_id", str(filters.dao_id))
            if filters.status is not None:
                query = query.eq("status", str(filters.status))
            if filters.contract_principal is not None:
                query = query.eq("contract_principal", filters.contract_principal)
            if filters.proposal_id is not None:
                query = query.eq("proposal_id", filters.proposal_id)
            if filters.executed is not None:
                query = query.eq("executed", filters.executed)
            if filters.passed is not None:
                query = query.eq("passed", filters.passed)
            if filters.met_quorum is not None:
                query = query.eq("met_quorum", filters.met_quorum)
            if filters.met_threshold is not None:
                query = query.eq("met_threshold", filters.met_threshold)
            if filters.type is not None:
                query = query.eq("type", filters.type)

            # Batch filters using 'in_' operations
            if filters.dao_ids is not None and len(filters.dao_ids) > 0:
                dao_id_strings = [str(dao_id) for dao_id in filters.dao_ids]
                query = query.in_("dao_id", dao_id_strings)
            if filters.proposal_ids is not None and len(filters.proposal_ids) > 0:
                query = query.in_("proposal_id", filters.proposal_ids)
            if filters.statuses is not None and len(filters.statuses) > 0:
                status_strings = [str(status) for status in filters.statuses]
                query = query.in_("status", status_strings)
            if (
                filters.contract_principals is not None
                and len(filters.contract_principals) > 0
            ):
                query = query.in_("contract_principal", filters.contract_principals)
            if filters.types is not None and len(filters.types) > 0:
                type_strings = [str(ptype) for ptype in filters.types]
                query = query.in_("type", type_strings)

            # Range filters for numeric fields
            if filters.proposal_id_gte is not None:
                query = query.gte("proposal_id", filters.proposal_id_gte)
            if filters.proposal_id_lte is not None:
                query = query.lte("proposal_id", filters.proposal_id_lte)

            # Text search filters (using ilike for case-insensitive partial matching)
            if filters.title_contains is not None:
                query = query.ilike("title", f"%{filters.title_contains}%")
            if filters.content_contains is not None:
                query = query.ilike("content", f"%{filters.content_contains}%")

        try:
            response = query.execute()
            data = response.data or []
            return [Proposal(**row) for row in data]
        except Exception as e:
            logger.error(f"Error in list_proposals_n: {str(e)}")
            # Fallback to original list_proposals if enhanced filtering fails
            if filters:
                # Convert enhanced filter to basic filter for fallback
                basic_filter = ProposalFilter(
                    dao_id=filters.dao_id,
                    status=filters.status,
                    contract_principal=filters.contract_principal,
                    proposal_id=filters.proposal_id,
                    executed=filters.executed,
                    passed=filters.passed,
                    met_quorum=filters.met_quorum,
                    met_threshold=filters.met_threshold,
                    type=filters.type,
                )
                return self.list_proposals(basic_filter)
            else:
                return self.list_proposals()

    # ----------------------------------------------------------------
    # AIRDROPS
    # ----------------------------------------------------------------

    def create_airdrop(self, new_airdrop: "AirdropCreate") -> "Airdrop":
        """Create a new airdrop record."""
        payload = new_airdrop.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("airdrops").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from airdrop insert.")
        return Airdrop(**data[0])

    def get_airdrop(self, airdrop_id: UUID) -> Optional["Airdrop"]:
        """Get an airdrop by ID."""
        response = (
            self.client.table("airdrops")
            .select("*")
            .eq("id", str(airdrop_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Airdrop(**response.data)

    def get_airdrop_by_tx_hash(self, tx_hash: str) -> Optional["Airdrop"]:
        """Get an airdrop by transaction hash."""
        response = (
            self.client.table("airdrops")
            .select("*")
            .eq("tx_hash", tx_hash)
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Airdrop(**response.data)

    def list_airdrops(
        self, filters: Optional["AirdropFilter"] = None
    ) -> List["Airdrop"]:
        """List airdrops with optional filtering."""
        query = self.client.table("airdrops").select("*")
        if filters:
            if filters.tx_hash is not None:
                query = query.eq("tx_hash", filters.tx_hash)
            if filters.block_height is not None:
                query = query.eq("block_height", filters.block_height)
            if filters.sender is not None:
                query = query.eq("sender", filters.sender)
            if filters.contract_identifier is not None:
                query = query.eq("contract_identifier", filters.contract_identifier)
            if filters.token_identifier is not None:
                query = query.eq("token_identifier", filters.token_identifier)
            if filters.success is not None:
                query = query.eq("success", filters.success)
            if filters.proposal_id is not None:
                query = query.eq("proposal_id", str(filters.proposal_id))
            # Range filters
            if filters.block_height_gte is not None:
                query = query.gte("block_height", filters.block_height_gte)
            if filters.block_height_lte is not None:
                query = query.lte("block_height", filters.block_height_lte)
            if filters.timestamp_after is not None:
                query = query.gte("timestamp", filters.timestamp_after.isoformat())
            if filters.timestamp_before is not None:
                query = query.lte("timestamp", filters.timestamp_before.isoformat())
        response = query.execute()
        data = response.data or []
        return [Airdrop(**row) for row in data]

    def update_airdrop(
        self, airdrop_id: UUID, update_data: "AirdropBase"
    ) -> Optional["Airdrop"]:
        """Update an airdrop record."""
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_airdrop(airdrop_id)
        response = (
            self.client.table("airdrops")
            .update(payload)
            .eq("id", str(airdrop_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Airdrop(**updated[0])

    def delete_airdrop(self, airdrop_id: UUID) -> bool:
        """Delete an airdrop record."""
        response = (
            self.client.table("airdrops").delete().eq("id", str(airdrop_id)).execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # LOTTERY RESULTS
    # ----------------------------------------------------------------

    def create_lottery_result(
        self, new_lottery_result: "LotteryResultCreate"
    ) -> "LotteryResult":
        """Create a new lottery result record."""
        payload = new_lottery_result.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("lottery_results").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from lottery_results insert.")
        return LotteryResult(**data[0])

    def get_lottery_result(self, lottery_result_id: UUID) -> Optional["LotteryResult"]:
        """Get a lottery result by ID."""
        response = (
            self.client.table("lottery_results")
            .select("*")
            .eq("id", str(lottery_result_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return LotteryResult(**response.data)

    def get_lottery_result_by_proposal(
        self, proposal_id: UUID
    ) -> Optional["LotteryResult"]:
        """Get a lottery result by proposal ID."""
        response = (
            self.client.table("lottery_results")
            .select("*")
            .eq("proposal_id", str(proposal_id))
            .execute()
        )
        if not response.data:
            return None
        return LotteryResult(**response.data[0])

    def list_lottery_results(
        self, filters: Optional["LotteryResultFilter"] = None
    ) -> List["LotteryResult"]:
        """List lottery results with optional filtering."""
        query = self.client.table("lottery_results").select("*")
        if filters:
            if filters.proposal_id is not None:
                query = query.eq("proposal_id", str(filters.proposal_id))
            if filters.dao_id is not None:
                query = query.eq("dao_id", str(filters.dao_id))
            if filters.bitcoin_block_height is not None:
                query = query.eq("bitcoin_block_height", filters.bitcoin_block_height)
            if filters.bitcoin_block_hash is not None:
                query = query.eq("bitcoin_block_hash", filters.bitcoin_block_hash)
        response = query.execute()
        data = response.data or []
        return [LotteryResult(**row) for row in data]

    def update_lottery_result(
        self, lottery_result_id: UUID, update_data: "LotteryResultBase"
    ) -> Optional["LotteryResult"]:
        """Update a lottery result record."""
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_lottery_result(lottery_result_id)
        response = (
            self.client.table("lottery_results")
            .update(payload)
            .eq("id", str(lottery_result_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return LotteryResult(**updated[0])

    def delete_lottery_result(self, lottery_result_id: UUID) -> bool:
        """Delete a lottery result record."""
        response = (
            self.client.table("lottery_results")
            .delete()
            .eq("id", str(lottery_result_id))
            .execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

import time
import uuid
from .abstract import AbstractBackend
from .models import (
    DAO,
    Agent,
    AgentBase,
    AgentCreate,
    AgentFilter,
    DAOBase,
    DAOCreate,
    DAOFilter,
    Extension,
    ExtensionBase,
    ExtensionCreate,
    ExtensionFilter,
    Job,
    JobBase,
    JobCreate,
    JobFilter,
    Profile,
    ProfileBase,
    ProfileCreate,
    ProfileFilter,
    Proposal,
    ProposalBase,
    ProposalCreate,
    ProposalFilter,
    Secret,
    SecretBase,
    SecretCreate,
    SecretFilter,
    Step,
    StepBase,
    StepCreate,
    StepFilter,
    Task,
    TaskBase,
    TaskCreate,
    TaskFilter,
    TelegramUser,
    TelegramUserBase,
    TelegramUserCreate,
    TelegramUserFilter,
    Thread,
    ThreadBase,
    ThreadCreate,
    ThreadFilter,
    Token,
    TokenBase,
    TokenCreate,
    TokenFilter,
    Wallet,
    WalletBase,
    WalletCreate,
    WalletFilter,
    XTweet,
    XTweetBase,
    XTweetCreate,
    XTweetFilter,
    XUser,
    XUserBase,
    XUserCreate,
    XUserFilter,
)
from lib.logger import configure_logger
from sqlalchemy import Column, DateTime, Engine, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from supabase import Client
from typing import List, Optional
from uuid import UUID

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

        try:
            with self.sqlalchemy_engine.connect() as connection:
                logger.info("SQLAlchemy connection successful!")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")

    # ---------------------------------------------------------------
    # HELPER FUNCTIONS
    # ----------------------------------------------------------------
    def verify_session_token(self, token: str) -> Optional[str]:
        try:
            user = self.client.auth.get_user(token)
            return user.user.email
        except Exception as e:
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
                    file_path, file, {"upsert": "true"}  # Override if file exists
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
        response = query.execute()
        data = response.data or []
        return [Wallet(**row) for row in data]

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
            if filters.name is not None:
                query = query.eq("name", filters.name)
            if filters.role is not None:
                query = query.eq("role", filters.role)
            if filters.goal is not None:
                query = query.eq("goal", filters.goal)
            if filters.profile_id is not None:
                query = query.eq("profile_id", str(filters.profile_id))
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
                query = query.eq("status", filters.status)
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
    def create_thread(self, new_thread: "ThreadCreate") -> "Thread":
        payload = new_thread.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("threads").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from thread insert.")
        return Thread(**data[0])

    def get_thread(self, thread_id: UUID) -> Optional["Thread"]:
        response = (
            self.client.table("threads")
            .select("*")
            .eq("id", str(thread_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Thread(**response.data)

    def list_threads(self, filters: Optional["ThreadFilter"] = None) -> List["Thread"]:
        query = self.client.table("threads").select("*")
        if filters:
            if filters.profile_id is not None:
                query = query.eq("profile_id", str(filters.profile_id))
            if filters.name is not None:
                query = query.eq("name", filters.name)
        response = query.execute()
        data = response.data or []
        return [Thread(**row) for row in data]

    def update_thread(
        self, thread_id: UUID, update_data: "ThreadBase"
    ) -> Optional["Thread"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_thread(thread_id)
        response = (
            self.client.table("threads")
            .update(payload)
            .eq("id", str(thread_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Thread(**updated[0])

    def delete_thread(self, thread_id: UUID) -> bool:
        response = (
            self.client.table("threads").delete().eq("id", str(thread_id)).execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 7. JOBS
    # ----------------------------------------------------------------
    def create_job(self, new_job: "JobCreate") -> "Job":
        payload = new_job.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("jobs").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from job insert.")
        return Job(**data[0])

    def get_job(self, job_id: UUID) -> Optional["Job"]:
        response = (
            self.client.table("jobs")
            .select("*")
            .eq("id", str(job_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Job(**response.data)

    def list_jobs(self, filters: Optional["JobFilter"] = None) -> List["Job"]:
        query = self.client.table("jobs").select("*")
        if filters:
            if filters.thread_id is not None:
                query = query.eq("thread_id", str(filters.thread_id))
            if filters.profile_id is not None:
                query = query.eq("profile_id", str(filters.profile_id))
        response = query.execute()
        data = response.data or []
        return [Job(**row) for row in data]

    def update_job(self, job_id: UUID, update_data: "JobBase") -> Optional["Job"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_job(job_id)
        response = (
            self.client.table("jobs").update(payload).eq("id", str(job_id)).execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Job(**updated[0])

    def delete_job(self, job_id: UUID) -> bool:
        response = self.client.table("jobs").delete().eq("id", str(job_id)).execute()
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
            if filters.discord_username is not None:
                query = query.eq("discord_username", filters.discord_username)
        response = query.execute()
        data = response.data or []
        return [Profile(**row) for row in data]

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
                query = query.eq("status", filters.status)
            if filters.is_deployed is not None:
                query = query.eq("is_deployed", filters.is_deployed)
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
    # 11. STEPS
    # ----------------------------------------------------------------
    def create_step(self, new_step: "StepCreate") -> "Step":
        payload = new_step.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("steps").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from step insert.")
        return Step(**data[0])

    def get_step(self, step_id: UUID) -> Optional["Step"]:
        response = (
            self.client.table("steps")
            .select("*")
            .eq("id", str(step_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Step(**response.data)

    def list_steps(self, filters: Optional["StepFilter"] = None) -> List["Step"]:
        query = self.client.table("steps").select("*").order("created_at", desc=True)
        if filters:
            if filters.job_id is not None:
                query = query.eq("job_id", str(filters.job_id))
            if filters.role is not None:
                query = query.eq("role", filters.role)
        response = query.execute()
        data = response.data or []
        return [Step(**row) for row in data]

    def update_step(self, step_id: UUID, update_data: "StepBase") -> Optional["Step"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_step(step_id)
        response = (
            self.client.table("steps").update(payload).eq("id", str(step_id)).execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Step(**updated[0])

    def delete_step(self, step_id: UUID) -> bool:
        response = self.client.table("steps").delete().eq("id", str(step_id)).execute()
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
    # 15. X_USERS
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
            if filters.realname is not None:
                query = query.eq("realname", filters.realname)
            if filters.user_id is not None:
                query = query.eq("user_id", filters.user_id)
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
            self.client.table("x_tweets")
            .select("*")
            .eq("id", x_tweet_id)
            .single()
            .execute()
        )
        if not response.data:
            return None
        return XTweet(**response.data)

    def list_x_tweets(self, filters: Optional["XTweetFilter"] = None) -> List["XTweet"]:
        query = self.client.table("x_tweets").select("*")
        if filters:
            if filters.author_id is not None:
                query = query.eq("author_id", filters.author_id)
            if filters.thread_id is not None:
                query = query.eq("thread_id", filters.thread_id)
            if filters.tweet_id is not None:
                query = query.eq("tweet_id", filters.tweet_id)
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

from abc import ABC, abstractmethod
from backend.models import (
    DAO,
    UUID,
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
)
from typing import List, Optional


class AbstractBackend(ABC):
    # ----------- HELPERS -----------
    @abstractmethod
    def verify_session_token(self, token: str) -> Optional[str]:
        pass

    @abstractmethod
    def upload_file(self, file_path: str, file: bytes) -> str:
        pass

    # ----------- SECRETS -----------
    # @abstractmethod
    # def create_secret(self, new_secret: SecretBase) -> Secret:
    #     pass

    @abstractmethod
    def get_secret(self, secret_id: UUID) -> Optional[Secret]:
        pass

    @abstractmethod
    def list_secrets(self, filters: Optional[SecretFilter] = None) -> List[Secret]:
        pass

    # @abstractmethod
    # def update_secret(
    #     self, secret_id: UUID, update_data: SecretBase
    # ) -> Optional[Secret]:
    #     pass

    # @abstractmethod
    # def delete_secret(self, secret_id: UUID) -> bool:
    #     pass

    # ----------- WALLETS ----------
    @abstractmethod
    def create_wallet(self, new_wallet: WalletCreate) -> Wallet:
        pass

    @abstractmethod
    def get_wallet(self, wallet_id: UUID) -> Optional[Wallet]:
        pass

    @abstractmethod
    def list_wallets(self, filters: Optional[WalletFilter] = None) -> List[Wallet]:
        pass

    @abstractmethod
    def update_wallet(
        self, wallet_id: UUID, update_data: WalletBase
    ) -> Optional[Wallet]:
        pass

    @abstractmethod
    def delete_wallet(self, wallet_id: UUID) -> bool:
        pass

    # ----------- AGENTS -----------
    @abstractmethod
    def create_agent(self, new_agent: AgentCreate) -> Agent:
        pass

    @abstractmethod
    def get_agent(self, agent_id: UUID) -> Optional[Agent]:
        pass

    @abstractmethod
    def list_agents(self, filters: Optional[AgentFilter] = None) -> List[Agent]:
        pass

    @abstractmethod
    def update_agent(self, agent_id: UUID, update_data: AgentBase) -> Optional[Agent]:
        pass

    @abstractmethod
    def delete_agent(self, agent_id: UUID) -> bool:
        pass

    # ----------- EXTENSIONS -----------
    @abstractmethod
    def create_extension(self, new_ext: ExtensionCreate) -> Extension:
        pass

    @abstractmethod
    def get_extension(self, ext_id: UUID) -> Optional[Extension]:
        pass

    @abstractmethod
    def list_extensions(
        self, filters: Optional[ExtensionFilter] = None
    ) -> List[Extension]:
        pass

    @abstractmethod
    def update_extension(
        self, ext_id: UUID, update_data: ExtensionBase
    ) -> Optional[Extension]:
        pass

    @abstractmethod
    def delete_extension(self, ext_id: UUID) -> bool:
        pass

    # ----------- DAOS -----------
    @abstractmethod
    def create_dao(self, new_dao: DAOCreate) -> DAO:
        pass

    @abstractmethod
    def get_dao(self, dao_id: UUID) -> Optional[DAO]:
        pass

    @abstractmethod
    def list_daos(self, filters: Optional[DAOFilter] = None) -> List[DAO]:
        pass

    @abstractmethod
    def update_dao(self, dao_id: UUID, update_data: DAOBase) -> Optional[DAO]:
        pass

    @abstractmethod
    def delete_dao(self, dao_id: UUID) -> bool:
        pass

    # ----------- THREADS -----------
    @abstractmethod
    def create_thread(self, new_thread: ThreadCreate) -> Thread:
        pass

    @abstractmethod
    def get_thread(self, thread_id: UUID) -> Optional[Thread]:
        pass

    @abstractmethod
    def list_threads(self, filters: Optional[ThreadFilter] = None) -> List[Thread]:
        pass

    @abstractmethod
    def update_thread(
        self, thread_id: UUID, update_data: ThreadBase
    ) -> Optional[Thread]:
        pass

    @abstractmethod
    def delete_thread(self, thread_id: UUID) -> bool:
        pass

    # ----------- JOBS -----------
    @abstractmethod
    def create_job(self, new_job: JobCreate) -> Job:
        pass

    @abstractmethod
    def get_job(self, job_id: UUID) -> Optional[Job]:
        pass

    @abstractmethod
    def list_jobs(self, filters: Optional[JobFilter] = None) -> List[Job]:
        pass

    @abstractmethod
    def update_job(self, job_id: UUID, update_data: JobBase) -> Optional[Job]:
        pass

    @abstractmethod
    def delete_job(self, job_id: UUID) -> bool:
        pass

    # ----------- PROFILES -----------
    @abstractmethod
    def create_profile(self, new_profile: ProfileCreate) -> Profile:
        pass

    @abstractmethod
    def get_profile(self, profile_id: UUID) -> Optional[Profile]:
        pass

    @abstractmethod
    def list_profiles(self, filters: Optional[ProfileFilter] = None) -> List[Profile]:
        pass

    @abstractmethod
    def update_profile(
        self, profile_id: UUID, update_data: ProfileBase
    ) -> Optional[Profile]:
        pass

    @abstractmethod
    def delete_profile(self, profile_id: UUID) -> bool:
        pass

    # ----------- PROPOSALS -----------
    @abstractmethod
    def create_proposal(self, new_proposal: ProposalCreate) -> Proposal:
        pass

    @abstractmethod
    def get_proposal(self, proposal_id: UUID) -> Optional[Proposal]:
        pass

    @abstractmethod
    def list_proposals(
        self, filters: Optional[ProposalFilter] = None
    ) -> List[Proposal]:
        pass

    @abstractmethod
    def update_proposal(
        self, proposal_id: UUID, update_data: ProposalBase
    ) -> Optional[Proposal]:
        pass

    @abstractmethod
    def delete_proposal(self, proposal_id: UUID) -> bool:
        pass

    # ----------- STEPS -----------
    @abstractmethod
    def create_step(self, new_step: StepCreate) -> Step:
        pass

    @abstractmethod
    def get_step(self, step_id: UUID) -> Optional[Step]:
        pass

    @abstractmethod
    def list_steps(self, filters: Optional[StepFilter] = None) -> List[Step]:
        pass

    @abstractmethod
    def update_step(self, step_id: UUID, update_data: StepBase) -> Optional[Step]:
        pass

    @abstractmethod
    def delete_step(self, step_id: UUID) -> bool:
        pass

    # ----------- TASKS -----------
    @abstractmethod
    def create_task(self, new_task: TaskCreate) -> Task:
        pass

    @abstractmethod
    def get_task(self, task_id: UUID) -> Optional[Task]:
        pass

    @abstractmethod
    def list_tasks(self, filters: Optional[TaskFilter] = None) -> List[Task]:
        pass

    @abstractmethod
    def update_task(self, task_id: UUID, update_data: TaskBase) -> Optional[Task]:
        pass

    @abstractmethod
    def delete_task(self, task_id: UUID) -> bool:
        pass

    # ----------- TELEGRAM USERS -----------
    @abstractmethod
    def create_telegram_user(self, new_tu: TelegramUserCreate) -> TelegramUser:
        pass

    @abstractmethod
    def get_telegram_user(self, telegram_user_id: UUID) -> Optional[TelegramUser]:
        pass

    @abstractmethod
    def list_telegram_users(
        self, filters: Optional[TelegramUserFilter] = None
    ) -> List[TelegramUser]:
        pass

    @abstractmethod
    def update_telegram_user(
        self, telegram_user_id: UUID, update_data: TelegramUserBase
    ) -> Optional[TelegramUser]:
        pass

    @abstractmethod
    def delete_telegram_user(self, telegram_user_id: UUID) -> bool:
        pass

    # ----------- TOKENS -----------
    @abstractmethod
    def create_token(self, new_token: TokenCreate) -> Token:
        pass

    @abstractmethod
    def get_token(self, token_id: UUID) -> Optional[Token]:
        pass

    @abstractmethod
    def list_tokens(self, filters: Optional[TokenFilter] = None) -> List[Token]:
        pass

    @abstractmethod
    def update_token(self, token_id: UUID, update_data: TokenBase) -> Optional[Token]:
        pass

    @abstractmethod
    def delete_token(self, token_id: UUID) -> bool:
        pass

    # ----------- X_CREDS -----------
    @abstractmethod
    def create_x_creds(self, new_xc: XCredsCreate) -> XCreds:
        pass

    @abstractmethod
    def get_x_creds(self, x_creds_id: UUID) -> Optional[XCreds]:
        pass

    @abstractmethod
    def list_x_creds(self, filters: Optional[XCredsFilter] = None) -> List[XCreds]:
        pass

    @abstractmethod
    def update_x_creds(
        self, x_creds_id: UUID, update_data: XCredsBase
    ) -> Optional[XCreds]:
        pass

    @abstractmethod
    def delete_x_creds(self, x_creds_id: UUID) -> bool:
        pass

    # ----------- X_USERS -----------
    @abstractmethod
    def create_x_user(self, new_xu: XUserCreate) -> XUser:
        pass

    @abstractmethod
    def get_x_user(self, x_user_id: UUID) -> Optional[XUser]:
        pass

    @abstractmethod
    def list_x_users(self, filters: Optional[XUserFilter] = None) -> List[XUser]:
        pass

    @abstractmethod
    def update_x_user(self, x_user_id: UUID, update_data: XUserBase) -> Optional[XUser]:
        pass

    @abstractmethod
    def delete_x_user(self, x_user_id: UUID) -> bool:
        pass

    # ----------- X_TWEETS -----------
    @abstractmethod
    def create_x_tweet(self, new_xt: XTweetCreate) -> XTweet:
        pass

    @abstractmethod
    def get_x_tweet(self, x_tweet_id: UUID) -> Optional[XTweet]:
        pass

    @abstractmethod
    def list_x_tweets(self, filters: Optional[XTweetFilter] = None) -> List[XTweet]:
        pass

    @abstractmethod
    def update_x_tweet(
        self, x_tweet_id: UUID, update_data: XTweetBase
    ) -> Optional[XTweet]:
        pass

    @abstractmethod
    def delete_x_tweet(self, x_tweet_id: UUID) -> bool:
        pass

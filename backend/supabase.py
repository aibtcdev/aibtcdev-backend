from .abstract import AbstractBackend
from .models import (
    Agent,
    AgentBase,
    AgentCreate,
    AgentFilter,
    Capability,
    CapabilityBase,
    CapabilityCreate,
    CapabilityFilter,
    Collective,
    CollectiveBase,
    CollectiveCreate,
    CollectiveFilter,
    Conversation,
    ConversationBase,
    ConversationCreate,
    ConversationFilter,
    Crew,
    CrewBase,
    CrewCreate,
    CrewFilter,
    Cron,
    CronBase,
    CronCreate,
    CronFilter,
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
    Schedule,
    ScheduleBase,
    ScheduleCreate,
    ScheduleFilter,
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
    Token,
    TokenBase,
    TokenCreate,
    TokenFilter,
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
from supabase import Client
from typing import List, Optional
from uuid import UUID

logger = configure_logger(__name__)


class SupabaseBackend(AbstractBackend):
    # Upload configuration
    MAX_UPLOAD_RETRIES = 3
    RETRY_DELAY_SECONDS = 1

    def __init__(self, client: Client, **kwargs):
        # super().__init__()  # If your AbstractDatabase has an __init__ to call
        self.client = client
        self.bucket_name = kwargs.get("bucket_name")

    # ----------------------------------------------------------------
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
            if filters.crew_id is not None:
                query = query.eq("crew_id", str(filters.crew_id))

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
    def create_capability(self, new_cap: "CapabilityCreate") -> "Capability":
        payload = new_cap.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("capabilities").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from insert for capability.")
        return Capability(**data[0])

    def get_capability(self, cap_id: UUID) -> Optional["Capability"]:
        response = (
            self.client.table("capabilities")
            .select("*")
            .eq("id", str(cap_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Capability(**response.data)

    def list_capabilities(
        self, filters: Optional["CapabilityFilter"] = None
    ) -> List["Capability"]:
        query = self.client.table("capabilities").select("*")
        if filters:
            if filters.collective_id is not None:
                query = query.eq("collective_id", str(filters.collective_id))
            if filters.type is not None:
                query = query.eq("type", filters.type)
            if filters.status is not None:
                query = query.eq("status", filters.status)
        response = query.execute()
        data = response.data or []
        return [Capability(**row) for row in data]

    def update_capability(
        self, cap_id: UUID, update_data: "CapabilityBase"
    ) -> Optional["Capability"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_capability(cap_id)
        response = (
            self.client.table("capabilities")
            .update(payload)
            .eq("id", str(cap_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Capability(**updated[0])

    def delete_capability(self, cap_id: UUID) -> bool:
        response = (
            self.client.table("capabilities").delete().eq("id", str(cap_id)).execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 3. COLLECTIVES
    # ----------------------------------------------------------------
    def create_collective(self, new_col: "CollectiveCreate") -> "Collective":
        payload = new_col.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("collectives").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned for collective insert.")
        return Collective(**data[0])

    def get_collective(self, col_id: UUID) -> Optional["Collective"]:
        response = (
            self.client.table("collectives")
            .select("*")
            .eq("id", str(col_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Collective(**response.data)

    def list_collectives(
        self, filters: Optional["CollectiveFilter"] = None
    ) -> List["Collective"]:
        query = self.client.table("collectives").select("*")
        if filters:
            if filters.name is not None:
                query = query.eq("name", filters.name)
        response = query.execute()
        data = response.data or []
        return [Collective(**row) for row in data]

    def update_collective(
        self, col_id: UUID, update_data: "CollectiveBase"
    ) -> Optional["Collective"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_collective(col_id)
        response = (
            self.client.table("collectives")
            .update(payload)
            .eq("id", str(col_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Collective(**updated[0])

    def delete_collective(self, col_id: UUID) -> bool:
        response = (
            self.client.table("collectives").delete().eq("id", str(col_id)).execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 4. CONVERSATIONS
    # ----------------------------------------------------------------
    def create_conversation(self, new_convo: "ConversationCreate") -> "Conversation":
        payload = new_convo.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("conversations").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from conversation insert.")
        return Conversation(**data[0])

    def get_conversation(self, convo_id: UUID) -> Optional["Conversation"]:
        response = (
            self.client.table("conversations")
            .select("*")
            .eq("id", str(convo_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Conversation(**response.data)

    def list_conversations(
        self, filters: Optional["ConversationFilter"] = None
    ) -> List["Conversation"]:
        query = self.client.table("conversations").select("*")
        if filters:
            if filters.profile_id is not None:
                query = query.eq("profile_id", str(filters.profile_id))
            if filters.name is not None:
                query = query.eq("name", filters.name)
        response = query.execute()
        data = response.data or []
        return [Conversation(**row) for row in data]

    def update_conversation(
        self, convo_id: UUID, update_data: "ConversationBase"
    ) -> Optional["Conversation"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_conversation(convo_id)
        response = (
            self.client.table("conversations")
            .update(payload)
            .eq("id", str(convo_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Conversation(**updated[0])

    def delete_conversation(self, convo_id: UUID) -> bool:
        response = (
            self.client.table("conversations")
            .delete()
            .eq("id", str(convo_id))
            .execute()
        )
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 5. CREWS
    # ----------------------------------------------------------------
    def create_crew(self, new_crew: "CrewCreate") -> "Crew":
        payload = new_crew.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("crews").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from crew insert.")
        return Crew(**data[0])

    def get_crew(self, crew_id: UUID) -> Optional["Crew"]:
        response = (
            self.client.table("crews")
            .select("*")
            .eq("id", str(crew_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Crew(**response.data)

    def list_crews(self, filters: Optional["CrewFilter"] = None) -> List["Crew"]:
        query = self.client.table("crews").select("*")
        if filters:
            if filters.name is not None:
                query = query.eq("name", filters.name)
            if filters.profile_id is not None:
                query = query.eq("profile_id", str(filters.profile_id))
            if filters.is_public is not None:
                query = query.eq("is_public", filters.is_public)
        response = query.execute()
        data = response.data or []
        return [Crew(**row) for row in data]

    def update_crew(self, crew_id: UUID, update_data: "CrewBase") -> Optional["Crew"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_crew(crew_id)
        response = (
            self.client.table("crews").update(payload).eq("id", str(crew_id)).execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Crew(**updated[0])

    def delete_crew(self, crew_id: UUID) -> bool:
        response = self.client.table("crews").delete().eq("id", str(crew_id)).execute()
        deleted = response.data or []
        return len(deleted) > 0

    # ----------------------------------------------------------------
    # 6. CRONS
    # ----------------------------------------------------------------
    def create_cron(self, new_cron: "CronCreate") -> "Cron":
        payload = new_cron.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("crons").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from cron insert.")
        return Cron(**data[0])

    def get_cron(self, cron_id: UUID) -> Optional["Cron"]:
        response = (
            self.client.table("crons")
            .select("*")
            .eq("id", str(cron_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Cron(**response.data)

    def list_crons(self, filters: Optional["CronFilter"] = None) -> List["Cron"]:
        query = self.client.table("crons").select("*")
        if filters:
            if filters.profile_id is not None:
                query = query.eq("profile_id", str(filters.profile_id))
            if filters.crew_id is not None:
                query = query.eq("crew_id", str(filters.crew_id))
            if filters.is_enabled is not None:
                query = query.eq("is_enabled", filters.is_enabled)
        response = query.execute()
        data = response.data or []
        return [Cron(**row) for row in data]

    def update_cron(self, cron_id: UUID, update_data: "CronBase") -> Optional["Cron"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_cron(cron_id)
        response = (
            self.client.table("crons").update(payload).eq("id", str(cron_id)).execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Cron(**updated[0])

    def delete_cron(self, cron_id: UUID) -> bool:
        response = self.client.table("crons").delete().eq("id", str(cron_id)).execute()
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
            if filters.conversation_id is not None:
                query = query.eq("conversation_id", str(filters.conversation_id))
            if filters.crew_id is not None:
                query = query.eq("crew_id", str(filters.crew_id))
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
            if filters.collective_id is not None:
                query = query.eq("collective_id", str(filters.collective_id))
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
    # 10. SCHEDULES
    # ----------------------------------------------------------------
    def create_schedule(self, new_sched: "ScheduleCreate") -> "Schedule":
        payload = new_sched.model_dump(exclude_unset=True, mode="json")
        response = self.client.table("schedules").insert(payload).execute()
        data = response.data or []
        if not data:
            raise ValueError("No data returned from schedule insert.")
        return Schedule(**data[0])

    def get_schedule(self, sched_id: UUID) -> Optional["Schedule"]:
        response = (
            self.client.table("schedules")
            .select("*")
            .eq("id", str(sched_id))
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Schedule(**response.data)

    def list_schedules(
        self, filters: Optional["ScheduleFilter"] = None
    ) -> List["Schedule"]:
        query = self.client.table("schedules").select("*")
        if filters:
            if filters.profile_id is not None:
                query = query.eq("profile_id", str(filters.profile_id))
            if filters.agent is not None:
                query = query.eq("agent", str(filters.agent))
            if filters.enabled is not None:
                query = query.eq("enabled", filters.enabled)
        response = query.execute()
        data = response.data or []
        return [Schedule(**row) for row in data]

    def update_schedule(
        self, sched_id: UUID, update_data: "ScheduleBase"
    ) -> Optional["Schedule"]:
        payload = update_data.model_dump(exclude_unset=True, mode="json")
        if not payload:
            return self.get_schedule(sched_id)
        response = (
            self.client.table("schedules")
            .update(payload)
            .eq("id", str(sched_id))
            .execute()
        )
        updated = response.data or []
        if not updated:
            return None
        return Schedule(**updated[0])

    def delete_schedule(self, sched_id: UUID) -> bool:
        response = (
            self.client.table("schedules").delete().eq("id", str(sched_id)).execute()
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
        query = self.client.table("steps").select("*")
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
            if filters.crew_id is not None:
                query = query.eq("crew_id", str(filters.crew_id))
            if filters.agent_id is not None:
                query = query.eq("agent_id", str(filters.agent_id))
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
            if filters.collective_id is not None:
                query = query.eq("collective_id", str(filters.collective_id))
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
        response = query.execute()
        data = response.data or []
        return [XUser(**row) for row in data]

    def update_x_user(
        self, x_user_id: str, update_data: "XUserBase"
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

    def delete_x_user(self, x_user_id: str) -> bool:
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

    def get_x_tweet(self, x_tweet_id: str) -> Optional["XTweet"]:
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
        response = query.execute()
        data = response.data or []
        return [XTweet(**row) for row in data]

    def update_x_tweet(
        self, x_tweet_id: str, update_data: "XTweetBase"
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

    def delete_x_tweet(self, x_tweet_id: str) -> bool:
        response = self.client.table("x_tweets").delete().eq("id", x_tweet_id).execute()
        deleted = response.data or []
        return len(deleted) > 0

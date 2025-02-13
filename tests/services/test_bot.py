import pytest
from backend.models import TelegramUserBase
from lib.logger import configure_logger
from services.bot import TelegramBotConfig, TelegramBotService
from telegram import Update, User
from telegram.ext import Application, ContextTypes
from unittest.mock import AsyncMock, MagicMock, patch

logger = configure_logger(__name__)


@pytest.fixture
def config():
    return TelegramBotConfig(token="test_token", admin_ids={12345}, is_enabled=True)


@pytest.fixture
def service(config):
    return TelegramBotService(config)


@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 12345
    update.effective_user.username = "test_user"
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    update.message = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    return context


@pytest.fixture
def mock_backend():
    with patch("services.bot.backend") as mock:
        mock.get_telegram_user = MagicMock()
        mock.update_telegram_user = MagicMock()
        mock.list_telegram_users = MagicMock()
        yield mock


class TestTelegramBotConfig:
    def test_from_env(self):
        with patch.dict(
            "os.environ",
            {
                "AIBTC_TELEGRAM_BOT_TOKEN": "test_token",
                "AIBTC_TELEGRAM_BOT_ENABLED": "true",
            },
        ):
            config = TelegramBotConfig.from_env()
            assert config.token == "test_token"
            assert config.is_enabled is True
            assert isinstance(config.admin_ids, set)


class TestTelegramBotService:
    def test_is_admin(self, service):
        assert service.is_admin(12345) is True
        assert service.is_admin(54321) is False

    @pytest.mark.asyncio
    async def test_start_command_no_args(
        self, service, mock_update, mock_context, mock_backend
    ):
        await service.start_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once_with(
            "Please use the registration link provided to start the bot."
        )

    @pytest.mark.asyncio
    async def test_start_command_invalid_user(
        self, service, mock_update, mock_context, mock_backend
    ):
        mock_context.args = ["invalid_id"]
        mock_backend.get_telegram_user.return_value = None

        await service.start_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once_with(
            "Invalid registration link. Please use the correct link to register."
        )

    @pytest.mark.asyncio
    async def test_start_command_success(
        self, service, mock_update, mock_context, mock_backend
    ):
        mock_context.args = ["valid_id"]
        mock_backend.get_telegram_user.return_value = True
        mock_backend.update_telegram_user.return_value = True

        await service.start_command(mock_update, mock_context)
        mock_backend.update_telegram_user.assert_called_once()
        assert (
            "Your registration has been completed successfully!"
            in mock_update.message.reply_text.call_args[0][0]
        )

    @pytest.mark.asyncio
    async def test_help_command(self, service, mock_update, mock_context):
        await service.help_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()
        assert "Available Commands" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_send_message_command_not_admin(
        self, service, mock_update, mock_context
    ):
        service.config.admin_ids = {
            54321
        }  # Different from mock_update.effective_user.id
        await service.send_message_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once_with(
            "You are not authorized to send messages."
        )

    @pytest.mark.asyncio
    async def test_send_message_command_no_args(
        self, service, mock_update, mock_context
    ):
        await service.send_message_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once_with(
            "Please provide username and message. Usage: /send <username> <message>"
        )

    @pytest.mark.asyncio
    async def test_send_message_command_user_not_found(
        self, service, mock_update, mock_context, mock_backend
    ):
        mock_context.args = ["nonexistent_user", "test message"]
        mock_backend.list_telegram_users.return_value = []

        await service.send_message_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once_with(
            "Registered user with username nonexistent_user not found."
        )

    @pytest.mark.asyncio
    async def test_list_users_command_not_admin(
        self, service, mock_update, mock_context
    ):
        service.config.admin_ids = {54321}
        await service.list_users_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once_with(
            "You are not authorized to list users."
        )

    @pytest.mark.asyncio
    async def test_list_users_command_empty(
        self, service, mock_update, mock_context, mock_backend
    ):
        mock_backend.list_telegram_users.return_value = []
        await service.list_users_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once_with(
            "No registered users found."
        )

    @pytest.mark.asyncio
    async def test_list_users_command_success(
        self, service, mock_update, mock_context, mock_backend
    ):
        mock_backend.list_telegram_users.return_value = [
            TelegramUserBase(telegram_user_id="123", username="user1"),
            TelegramUserBase(telegram_user_id="456", username="user2"),
        ]
        await service.list_users_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()
        assert "user1: 123" in mock_update.message.reply_text.call_args[0][0]
        assert "user2: 456" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_admin_command_not_admin(
        self, service, mock_update, mock_context
    ):
        service.config.admin_ids = {54321}
        await service.add_admin_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once_with(
            "You are not authorized to add admins."
        )

    @pytest.mark.asyncio
    async def test_add_admin_command_no_args(self, service, mock_update, mock_context):
        await service.add_admin_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once_with(
            "Please provide a user ID. Usage: /add_admin <user_id>"
        )

    @pytest.mark.asyncio
    async def test_add_admin_command_invalid_id(
        self, service, mock_update, mock_context
    ):
        mock_context.args = ["not_a_number"]
        await service.add_admin_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once_with(
            "Please provide a valid user ID (numbers only)."
        )

    @pytest.mark.asyncio
    async def test_add_admin_command_success(self, service, mock_update, mock_context):
        mock_context.args = ["54321"]
        await service.add_admin_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once_with(
            "Successfully added user ID 54321 as admin."
        )
        assert 54321 in service.config.admin_ids

    @pytest.mark.asyncio
    async def test_send_message_to_user(self, service, mock_backend):
        # Setup mock application
        service._app = AsyncMock(spec=Application)
        service._app.bot.send_message = AsyncMock()

        mock_backend.list_telegram_users.return_value = [
            TelegramUserBase(telegram_user_id="123", username="test_user")
        ]

        result = await service.send_message_to_user("test_profile", "test message")
        assert result is True
        service._app.bot.send_message.assert_called_once_with(
            chat_id="123", text="test message"
        )

    @pytest.mark.asyncio
    async def test_send_message_to_user_disabled(self, service):
        service.config.is_enabled = False
        result = await service.send_message_to_user("test_profile", "test message")
        assert result is False

    @pytest.mark.asyncio
    async def test_initialize(self, service):
        with patch("telegram.ext.Application.builder") as mock_builder:
            mock_app = AsyncMock(spec=Application)
            mock_builder.return_value.token.return_value.build.return_value = mock_app

            await service.initialize()

            assert service._app is not None
            mock_app.initialize.assert_called_once()
            mock_app.start.assert_called_once()
            mock_app.updater.start_polling.assert_called_once_with(
                allowed_updates=Update.ALL_TYPES
            )

    @pytest.mark.asyncio
    async def test_shutdown(self, service):
        service._app = AsyncMock(spec=Application)
        await service.shutdown()
        service._app.stop.assert_called_once()
        service._app.shutdown.assert_called_once()
        assert service._app is None

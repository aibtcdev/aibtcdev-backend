import os
import subprocess
from typing import Dict, List, Union

from app.backend.factory import backend
from app.backend.models import UUID
from app.lib.logger import configure_logger

logger = configure_logger(__name__)


class BunScriptRunner:
    """Manages TypeScript script execution using Bun runtime."""

    # Default directory configurations
    WORKING_DIR: str = "./agent-tools-ts/"
    SCRIPT_DIR: str = "src"

    @staticmethod
    def bun_run(
        wallet_id: UUID, script_path: str, script_name: str, *args: str
    ) -> Dict[str, Union[str, bool, None]]:
        """
        Run a TypeScript script using Bun with specified parameters.

        Args:
            wallet_id: The wallet id to use for script execution
            script_path: Path of the directory containing the script
            script_name: Name of the TypeScript script to run
            *args: Additional arguments to pass to the script

        Returns:
            Dict containing:
                - output: Script execution stdout if successful
                - error: Error message if execution failed, None otherwise
                - success: Boolean indicating if execution was successful
        """
        # Set up environment with wallet credentials
        wallet = backend.get_wallet(wallet_id)
        secret = backend.get_secret(wallet.secret_id)
        mnemonic = secret.decrypted_secret

        return BunScriptRunner._execute_script(
            mnemonic, script_path, script_name, *args
        )

    @staticmethod
    def bun_run_with_seed_phrase(
        seed_phrase: str, script_path: str, script_name: str, *args: str
    ) -> Dict[str, Union[str, bool, None]]:
        """
        Run a TypeScript script using Bun with specified parameters using seed phrase directly.

        Args:
            seed_phrase: The mnemonic seed phrase to use for script execution
            script_path: Path of the directory containing the script
            script_name: Name of the TypeScript script to run
            *args: Additional arguments to pass to the script

        Returns:
            Dict containing:
                - output: Script execution stdout if successful
                - error: Error message if execution failed, None otherwise
                - success: Boolean indicating if execution was successful
        """
        return BunScriptRunner._execute_script(
            seed_phrase, script_path, script_name, *args
        )

    @staticmethod
    def _execute_script(
        mnemonic: str, script_path: str, script_name: str, *args: str
    ) -> Dict[str, Union[str, bool, None]]:
        """
        Internal method to execute the script with the given mnemonic.

        Args:
            mnemonic: The mnemonic phrase to use
            script_path: Path of the directory containing the script
            script_name: Name of the TypeScript script to run
            *args: Additional arguments to pass to the script

        Returns:
            Dict containing script execution results
        """
        from app.config import config

        env = os.environ.copy()
        env["ACCOUNT_INDEX"] = "0"
        env["MNEMONIC"] = mnemonic
        env["NETWORK"] = config.network.network

        # Build script path and command
        full_script_path = f"{BunScriptRunner.SCRIPT_DIR}/{script_path}/{script_name}"
        command: List[str] = [
            "bun",
            "run",
            full_script_path,
        ]
        command.extend(args)

        # Log command execution (without sensitive data)
        safe_command = command.copy()
        logger.debug(
            f"Executing Bun command: {' '.join(safe_command)} in directory: {BunScriptRunner.WORKING_DIR}"
        )

        try:
            logger.info(f"Running script: {script_name}")
            result = subprocess.run(
                command,
                check=True,
                text=True,
                capture_output=True,
                cwd=BunScriptRunner.WORKING_DIR,
                env=env,
            )

            output = result.stdout.strip()
            logger.debug(f"Script execution output: {output}")
            logger.info(f"Successfully executed script: {script_name}")

            return {"output": output, "error": None, "success": True}
        except subprocess.CalledProcessError as e:
            stdout_output = e.stdout.strip() if e.stdout else ""
            error_output = e.stderr.strip() if e.stderr else "Unknown error occurred"

            logger.error(
                f"Script execution failed: {script_name}, exit code: {e.returncode}, error message: {error_output}"
            )

            return {
                "output": stdout_output,
                "error": error_output,
                "success": False,
            }
        except Exception as e:
            logger.exception(f"Unexpected error running script {script_name}: {str(e)}")
            return {"output": "", "error": str(e), "success": False}

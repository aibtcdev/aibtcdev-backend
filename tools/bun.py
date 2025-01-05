import os
import subprocess
from backend.factory import backend
from lib.logger import configure_logger
from typing import Dict, List, Union
from uuid import UUID

logger = configure_logger(__name__)


class BunScriptRunner:
    """Manages TypeScript script execution using Bun runtime."""

    # Default directory configurations
    WORKING_DIR: str = "./agent-tools-ts/"
    SCRIPT_DIR: str = "src"

    @staticmethod
    def bun_run(
        wallet_id: UUID, contract_name: str, script_name: str, *args: str
    ) -> Dict[str, Union[str, bool, None]]:
        """
        Run a TypeScript script using Bun with specified parameters.

        Args:
            wallet_id: The wallet id to use for script execution
            contract_name: Name of the contract directory containing the script
            script_name: Name of the TypeScript script to run
            *args: Additional arguments to pass to the script

        Returns:
            Dict containing:
                - output: Script execution stdout if successful
                - error: Error message if execution failed, None otherwise
                - success: Boolean indicating if execution was successful
        """
        # Prepare environment with account index
        wallet = backend.get_wallet(wallet_id)
        secret = backend.get_secret(wallet.secret_id)
        mnemonic = secret.decrypted_secret

        env = os.environ.copy()
        env["ACCOUNT_INDEX"] = "0"
        env["MNEMONIC"] = mnemonic
        # Construct command with script path
        command: List[str] = [
            "bun",
            "run",
            f"{BunScriptRunner.SCRIPT_DIR}/{contract_name}/{script_name}",
        ]
        command.extend(args)

        try:
            result = subprocess.run(
                command,
                check=True,
                text=True,
                capture_output=True,
                cwd=BunScriptRunner.WORKING_DIR,
                env=env,
            )
            return {"output": result.stdout.strip(), "error": None, "success": True}
        except subprocess.CalledProcessError as e:
            return {
                "output": e.stdout.strip() if e.stdout else "",
                "error": e.stderr.strip() if e.stderr else "Unknown error occurred",
                "success": False,
            }
        except Exception as e:
            return {"output": "", "error": str(e), "success": False}

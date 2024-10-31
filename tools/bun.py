import subprocess
import os

env = os.environ.copy()


class BunScriptRunner:
    working_dir = "./agent-tools-ts/"
    script_dir = "src"

    @staticmethod
    def bun_run(account_index: str, contract_name: str, script_name: str, *args):
        """Runs a TypeScript script using bun with an optional positional argument."""
        command = [
            "bun",
            "run",
            f"{BunScriptRunner.script_dir}/{contract_name}/{script_name}",
        ]

        # Append the optional argument if provided
        command.extend(args)

        # Set environment variables for the account index
        env["ACCOUNT_INDEX"] = account_index

        try:
            result = subprocess.run(
                command,
                check=True,
                text=True,
                capture_output=True,
                cwd=BunScriptRunner.working_dir,
                env=env,
            )
            return {"output": result.stdout, "error": None, "success": True}
        except subprocess.CalledProcessError as e:
            return {"output": e.stdout, "error": e.stderr, "success": False}

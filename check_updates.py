#!/usr/bin/env python3
"""
Script to check for available updates to dependencies in pyproject.toml
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path
from typing import Dict, Optional

import aiohttp

try:
    from packaging import version

    HAS_PACKAGING = True
except ImportError:
    HAS_PACKAGING = False


async def get_latest_version(
    session: aiohttp.ClientSession, package_name: str
) -> Optional[str]:
    """Get the latest version of a package from PyPI."""
    try:
        url = f"https://pypi.org/pypi/{package_name}/json"
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data["info"]["version"]
    except Exception as e:
        print(f"Error fetching {package_name}: {e}")
    return None


def update_pyproject_toml(file_path: Path, updates: Dict[str, str]) -> None:
    """Update pyproject.toml with new dependency versions."""
    try:
        with open(file_path, "r") as f:
            content = f.read()

        lines = content.split("\n")
        updated_lines = []
        in_dependencies = False

        for line in lines:
            original_line = line
            stripped_line = line.strip()

            # Check if we're entering the dependencies section
            if stripped_line == "dependencies = [":
                in_dependencies = True
                updated_lines.append(original_line)
                continue

            # Check if we're leaving the dependencies section
            if in_dependencies and stripped_line == "]":
                in_dependencies = False
                updated_lines.append(original_line)
                continue

            # Process dependency lines for updates
            if in_dependencies and stripped_line and not stripped_line.startswith("#"):
                # Extract package name from the line
                clean_line = stripped_line.strip().strip('"').strip("'").rstrip(",")

                if "==" in clean_line:
                    package_name = clean_line.split("==")[0].strip()
                    if package_name in updates:
                        # Preserve the original formatting but update the version
                        # Find the version part and replace it
                        updated_line = re.sub(
                            rf'("{package_name}==)[^"]*(")',
                            rf"\g<1>{updates[package_name]}\g<2>",
                            original_line,
                        )
                        if updated_line == original_line:
                            # Try without quotes
                            updated_line = re.sub(
                                rf"({package_name}==)[^,\s]*",
                                rf"\g<1>{updates[package_name]}",
                                original_line,
                            )
                        updated_lines.append(updated_line)
                        continue

                # If no update needed, keep original line
                updated_lines.append(original_line)
            else:
                updated_lines.append(original_line)

        # Write back to file
        updated_content = "\n".join(updated_lines)
        with open(file_path, "w") as f:
            f.write(updated_content)

    except Exception as e:
        print(f"❌ Error updating {file_path}: {e}")
        raise


def parse_pyproject_toml(file_path: Path) -> Dict[str, str]:
    """Parse pyproject.toml and extract dependencies with their versions."""
    dependencies = {}

    try:
        with open(file_path, "r") as f:
            content = f.read()

        # Find the dependencies section
        in_dependencies = False
        lines = content.split("\n")

        for line in lines:
            line = line.strip()

            # Check if we're entering the dependencies section
            if line == "dependencies = [":
                in_dependencies = True
                continue

            # Check if we're leaving the dependencies section
            if in_dependencies and line == "]":
                break

            # Process dependency lines
            if in_dependencies and line and not line.startswith("#"):
                # Remove quotes and trailing comma
                line = line.strip().strip('"').strip("'").rstrip(",")

                # Parse package name and version
                if "==" in line:
                    package, version = line.split("==", 1)
                    dependencies[package.strip()] = (
                        version.strip().strip('"').strip("'")
                    )
                elif "<=" in line:
                    # Handle version constraints like "<=0.46.0"
                    parts = line.split("<=")
                    package = parts[0].strip()
                    version_constraint = parts[1].strip().strip('"').strip("'")
                    dependencies[package] = f"<={version_constraint}"
                elif ">=" in line:
                    # Handle version constraints like ">=0.25.0"
                    parts = line.split(">=")
                    package = parts[0].strip()
                    version_constraint = parts[1].strip().strip('"').strip("'")
                    # Extract just the minimum version, ignoring additional constraints
                    if "," in version_constraint:
                        version_constraint = version_constraint.split(",")[0]
                    dependencies[package] = f">={version_constraint}"
                elif "<" in line and "<=" not in line:
                    parts = line.split("<")
                    package = parts[0].strip()
                    version_constraint = parts[1].strip().strip('"').strip("'")
                    dependencies[package] = f"<{version_constraint}"
                elif ">" in line and ">=" not in line:
                    parts = line.split(">")
                    package = parts[0].strip()
                    version_constraint = parts[1].strip().strip('"').strip("'")
                    dependencies[package] = f">{version_constraint}"
                else:
                    # Package without version specification
                    dependencies[line.strip()] = "no version specified"

    except FileNotFoundError:
        print(f"Error: {file_path} not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        sys.exit(1)

    return dependencies


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Check for available updates to dependencies in pyproject.toml"
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Automatically update pyproject.toml with latest versions",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes (only with --update)",
    )
    return parser.parse_args()


async def check_updates(auto_update: bool = False, dry_run: bool = False):
    """Main function to check for updates."""
    pyproject_path = Path("pyproject.toml")

    if not pyproject_path.exists():
        print("Error: pyproject.toml not found in current directory")
        sys.exit(1)

    print("🔍 Parsing pyproject.toml...")
    if not HAS_PACKAGING:
        print(
            "⚠️  Note: 'packaging' library not found. Version comparison may be less accurate."
        )
        print("   Install with: pip install packaging")
    dependencies = parse_pyproject_toml(pyproject_path)

    if not dependencies:
        print("No dependencies found in pyproject.toml")
        return

    print(f"📦 Found {len(dependencies)} dependencies. Checking for updates...\n")

    # Create aiohttp session for concurrent requests
    connector = aiohttp.TCPConnector(limit=10)  # Limit concurrent connections
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # Fetch latest versions concurrently
        tasks = []
        for package_name in dependencies.keys():
            task = get_latest_version(session, package_name)
            tasks.append((package_name, task))

        results = []
        for package_name, task in tasks:
            latest_version = await task
            results.append((package_name, dependencies[package_name], latest_version))

    # Sort results alphabetically
    results.sort(key=lambda x: x[0].lower())

    # Display results and collect updates
    print("📋 Dependency Update Report")
    print("=" * 60)
    print(f"{'Package':<25} {'Current':<15} {'Latest':<15} {'Status'}")
    print("-" * 60)

    updates_available = 0
    available_updates = {}  # Dict to store packages that can be updated

    for package_name, current_version, latest_version in results:
        if latest_version is None:
            status = "❌ Error"
            latest_display = "N/A"
        elif current_version == "no version specified":
            status = "⚠️  No version"
            latest_display = latest_version
        elif (
            current_version.startswith(">=")
            or current_version.startswith(">")
            or current_version.startswith("<=")
            or current_version.startswith("<")
        ):
            # For version constraints, just show the info
            status = "ℹ️  Constraint"
            latest_display = latest_version
        elif current_version == latest_version:
            status = "✅ Up to date"
            latest_display = latest_version
        else:
            # Compare versions properly if packaging is available
            update_available = False
            if HAS_PACKAGING:
                try:
                    current_ver = version.parse(current_version)
                    latest_ver = version.parse(latest_version)
                    if current_ver < latest_ver:
                        status = "🔄 Update available"
                        update_available = True
                        updates_available += 1
                    elif current_ver == latest_ver:
                        status = "✅ Up to date"
                    else:
                        status = "⬇️  Downgrade available"
                except (ValueError, TypeError):
                    # Fall back to string comparison
                    status = "🔄 Update available"
                    update_available = True
                    updates_available += 1
            else:
                # Simple string comparison fallback
                status = "🔄 Update available"
                update_available = True
                updates_available += 1

            # Store packages that can be updated (only exact versions)
            if update_available and not (
                current_version.startswith(">=")
                or current_version.startswith(">")
                or current_version.startswith("<=")
                or current_version.startswith("<")
            ):
                available_updates[package_name] = latest_version

            latest_display = latest_version

        print(f"{package_name:<25} {current_version:<15} {latest_display:<15} {status}")

    print("-" * 60)
    if updates_available > 0:
        print(f"🎯 {updates_available} package(s) may have updates available")
    else:
        print("🎉 All packages appear to be up to date!")

    # Handle auto-update functionality
    if auto_update:
        if available_updates:
            print("\n🔄 Auto-update mode enabled...")

            if dry_run:
                print("🧪 Dry run mode - showing what would be updated:")
                for pkg, new_ver in available_updates.items():
                    current_ver = dependencies[pkg]
                    print(f"  • {pkg}: {current_ver} → {new_ver}")

                if updates_available > len(available_updates):
                    skipped = updates_available - len(available_updates)
                    print(
                        f"\n⚠️  {skipped} package(s) with version constraints will be skipped"
                    )
            else:
                try:
                    print(
                        f"📝 Updating {len(available_updates)} package(s) in pyproject.toml..."
                    )
                    update_pyproject_toml(pyproject_path, available_updates)
                    print("✅ Successfully updated pyproject.toml!")

                    print("\n📦 Updated packages:")
                    for pkg, new_ver in available_updates.items():
                        current_ver = dependencies[pkg]
                        print(f"  • {pkg}: {current_ver} → {new_ver}")

                    if updates_available > len(available_updates):
                        skipped = updates_available - len(available_updates)
                        print(
                            f"\n⚠️  {skipped} package(s) with version constraints were skipped"
                        )

                    print(
                        "\n💡 Run 'uv lock' to update the lock file with new versions"
                    )

                except Exception as e:
                    print(f"❌ Failed to update pyproject.toml: {e}")
                    sys.exit(1)
        else:
            print("\n✅ No packages can be auto-updated!")
            if updates_available > 0:
                print("   (All available updates have version constraints)")
    elif not auto_update:
        print(
            "\n💡 To update a package, modify pyproject.toml and run: uv lock --upgrade-package <package-name>"
        )
        if available_updates:
            print(
                "💡 Or run this script with --update to automatically update all packages"
            )


if __name__ == "__main__":
    try:
        args = parse_arguments()

        # Validate arguments
        if args.dry_run and not args.update:
            print("❌ --dry-run can only be used with --update")
            sys.exit(1)

        asyncio.run(check_updates(auto_update=args.update, dry_run=args.dry_run))
    except KeyboardInterrupt:
        print("\n⚠️  Check interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

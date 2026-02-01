"""Custom Hatch build hook to bundle pytauri-wheel native libraries.

This hook downloads and embeds the pytauri-wheel native extension for the
target platform, making pywry fully self-contained without requiring users
to download pytauri-wheel separately.
"""

# pylint: disable=too-many-locals

from __future__ import annotations

import os
import platform
import subprocess
import sys
import tempfile
import zipfile

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


def get_platform_tag() -> str:
    """Get the platform tag for the current build target."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        # Use tags that match what pytauri-wheel publishes on PyPI
        if machine == "arm64":
            return "macosx_14_0_arm64"
        return "macosx_13_0_x86_64"
    if system == "linux":
        if machine == "aarch64":
            return "manylinux_2_35_aarch64"
        return "manylinux_2_35_x86_64"
    if system == "windows":
        if machine == "arm64":
            return "win_arm64"
        return "win_amd64"

    raise RuntimeError(f"Unsupported platform: {system}-{machine}")


def get_python_tag() -> str:
    """Get the Python version tag (e.g., cp312)."""
    return f"cp{sys.version_info.major}{sys.version_info.minor}"


class CustomBuildHook(BuildHookInterface):
    """Build hook to bundle pytauri-wheel into pywry."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Download and bundle pytauri-wheel for the target platform."""
        # Skip for non-wheel builds (sdist, editable)
        if self.target_name != "wheel":
            return

        # Skip for editable installs
        if version == "editable":
            self.app.display_info(
                "Skipping pytauri-wheel bundling for editable install"
            )
            return

        # Check if bundling is enabled (can be disabled for development)
        if os.environ.get("PYWRY_SKIP_BUNDLE", "").lower() in ("1", "true", "yes"):
            self.app.display_info(
                "Skipping pytauri-wheel bundling (PYWRY_SKIP_BUNDLE=1)"
            )
            return

        pytauri_version = os.environ.get("PYTAURI_WHEEL_VERSION", "0.8.0")
        python_tag = get_python_tag()
        platform_tag = get_platform_tag()

        self.app.display_info(
            f"Bundling pytauri-wheel {pytauri_version} for {python_tag}-{platform_tag}"
        )

        # Create vendor directory in the package
        vendor_dir = Path(self.root) / "pywry" / "_vendor" / "pytauri_wheel"
        vendor_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            try:
                subprocess.run(  # noqa: S603
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "download",
                        "--no-deps",
                        "--only-binary=:all:",
                        f"--dest={tmppath}",
                        f"--platform={platform_tag}",
                        f"--python-version={sys.version_info.major}.{sys.version_info.minor}",
                        f"--abi={python_tag}",
                        f"pytauri-wheel=={pytauri_version}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as e:
                self.app.display_error(f"Failed to download pytauri-wheel: {e.stderr}")
                raise

            # Find the downloaded wheel
            wheels = list(tmppath.glob("pytauri_wheel*.whl"))
            if not wheels:
                raise RuntimeError(f"No pytauri-wheel found in {tmppath}")

            wheel_path = wheels[0]
            self.app.display_info(f"Downloaded: {wheel_path.name}")

            # Extract the wheel (it's a zip file)
            with zipfile.ZipFile(wheel_path, "r") as whl:
                # Extract only the pytauri_wheel package contents
                for member in whl.namelist():
                    if member.startswith("pytauri_wheel/") and not member.endswith("/"):
                        # Get the relative path within pytauri_wheel/
                        rel_path = member[len("pytauri_wheel/") :]
                        if rel_path:
                            dest = vendor_dir / rel_path
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            with whl.open(member) as src, dest.open("wb") as dst:
                                dst.write(src.read())

        # Create __init__.py that re-exports from vendor location
        init_content = '''"""Vendored pytauri_wheel package."""
from pywry._vendor.pytauri_wheel.lib import builder_factory, context_factory

__all__ = ["builder_factory", "context_factory"]
'''
        (vendor_dir / "__init__.py").write_text(init_content)

        # Add vendor directory to wheel
        build_data["force_include"][str(vendor_dir)] = "pywry/_vendor/pytauri_wheel"

        self.app.display_success(
            "Bundled pytauri-wheel into pywry/_vendor/pytauri_wheel"
        )

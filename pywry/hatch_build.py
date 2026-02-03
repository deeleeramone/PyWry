"""Custom Hatch build hook to bundle pytauri-wheel native libraries.

This hook downloads and embeds the pytauri-wheel native extension for the
target platform, making pywry fully self-contained without requiring users
to download pytauri-wheel separately.

It also sets the wheel tags to make this a platform-specific wheel,
which is required since we bundle native binaries.
"""

# pylint: disable=too-many-locals

from __future__ import annotations

import os
import platform
import shutil
import sys

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


def get_wheel_platform_tag() -> str:
    """Get the platform tag for the output wheel.

    This is the tag that will be used in the wheel filename.
    We use manylinux_2_28 for Linux for broad compatibility.
    """
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        if machine == "arm64":
            return "macosx_14_0_arm64"
        return "macosx_13_0_x86_64"
    if system == "linux":
        if machine == "aarch64":
            return "manylinux_2_28_aarch64"
        return "manylinux_2_28_x86_64"
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

        python_tag = get_python_tag()
        wheel_platform_tag = get_wheel_platform_tag()
        # Set wheel tags to make this a platform-specific wheel
        # This is critical - without this, hatch generates a pure Python wheel
        build_data["tag"] = f"{python_tag}-{python_tag}-{wheel_platform_tag}"
        build_data["pure_python"] = False

        # Check if bundling is enabled (can be disabled for development)
        if os.environ.get("PYWRY_SKIP_BUNDLE", "").lower() in ("1", "true", "yes"):
            self.app.display_info(
                "Skipping pytauri-wheel bundling (PYWRY_SKIP_BUNDLE=1)"
            )
            return

        self.app.display_info(
            f"Bundling pytauri-wheel for {python_tag}-{wheel_platform_tag}"
        )

        # Create vendor directory in the package
        vendor_dir = Path(self.root) / "pywry" / "_vendor" / "pytauri_wheel"
        vendor_dir.mkdir(parents=True, exist_ok=True)

        # Find the installed pytauri_wheel package location
        import importlib.util

        spec = importlib.util.find_spec("pytauri_wheel")
        if spec is None or spec.origin is None:
            raise RuntimeError(
                "pytauri_wheel is not installed. Install it with: pip install pytauri-wheel"
            )

        pytauri_wheel_dir = Path(spec.origin).parent
        self.app.display_info(f"Found pytauri_wheel at: {pytauri_wheel_dir}")

        # Copy the entire pytauri_wheel package to vendor directory
        for item in pytauri_wheel_dir.iterdir():
            dest = vendor_dir / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

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

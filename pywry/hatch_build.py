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
import sys

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


def _get_target_architecture(system: str) -> str:
    """Detect target architecture from environment variables.

    Checks cibuildwheel environment variables for cross-compilation,
    falling back to the host machine architecture.
    """
    # _PYTHON_HOST_PLATFORM is the most reliable for cross-compilation
    # Format: macosx-14.0-arm64 or macosx-13.0-x86_64
    host_platform = os.environ.get("_PYTHON_HOST_PLATFORM", "")
    arch_map = {"arm64": "arm64", "x86_64": "x86_64", "aarch64": "aarch64"}
    for arch_key, arch_val in arch_map.items():
        if arch_key in host_platform:
            return arch_val

    # cibuildwheel sets AUDITWHEEL_ARCH for Linux builds
    if "AUDITWHEEL_ARCH" in os.environ:
        return os.environ["AUDITWHEEL_ARCH"].lower()

    # cibuildwheel sets ARCHFLAGS for macOS cross-compilation
    archflags = os.environ.get("ARCHFLAGS", "")
    for flag, arch in [("-arch arm64", "arm64"), ("-arch x86_64", "x86_64")]:
        if flag in archflags:
            return arch

    # cibuildwheel also sets CIBW_ARCHS or can be detected from wheel name
    cibw_archs = os.environ.get("CIBW_ARCHS", "").lower()
    if "arm64" in cibw_archs or "aarch64" in cibw_archs:
        return "arm64" if system == "darwin" else "aarch64"
    if "x86_64" in cibw_archs or "amd64" in cibw_archs:
        return "x86_64"

    # Fall back to host machine architecture
    return platform.machine().lower()


def _get_platform_tag_for_system(system: str, machine: str) -> str:
    """Get the platform tag for the given system and architecture."""
    if system == "darwin":
        return "macosx_14_0_arm64" if machine == "arm64" else "macosx_13_0_x86_64"
    if system == "linux":
        # Use manylinux_2_35 to match pytauri-wheel's published wheels
        return "manylinux_2_35_aarch64" if machine == "aarch64" else "manylinux_2_35_x86_64"
    if system == "windows":
        return "win_arm64" if machine in ("arm64", "aarch64") else "win_amd64"
    raise RuntimeError(f"Unsupported platform: {system}-{machine}")


def get_wheel_platform_tag() -> str:
    """Get the platform tag for the output wheel.

    This is the tag that will be used in the wheel filename.
    We use manylinux_2_28 for Linux for broad compatibility.

    Uses cibuildwheel environment variables when available to get
    the correct target architecture for cross-compilation.
    """
    system = platform.system().lower()
    machine = _get_target_architecture(system)
    return _get_platform_tag_for_system(system, machine)


def get_python_tag() -> str:
    """Get the Python version tag (e.g., cp312)."""
    return f"cp{sys.version_info.major}{sys.version_info.minor}"


class CustomBuildHook(BuildHookInterface[Any]):
    """Build hook to bundle pytauri-wheel into pywry."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Download and bundle pytauri-wheel for the target platform."""
        # Skip for non-wheel builds (sdist, editable)
        if self.target_name != "wheel":
            return

        # Skip for editable installs
        if version == "editable":
            self.app.display_info("Skipping pytauri-wheel bundling for editable install")
            return

        python_tag = get_python_tag()
        wheel_platform_tag = get_wheel_platform_tag()
        # Set wheel tags to make this a platform-specific wheel
        # This is critical - without this, hatch generates a pure Python wheel
        build_data["tag"] = f"{python_tag}-{python_tag}-{wheel_platform_tag}"
        build_data["pure_python"] = False

        # Check if bundling is enabled (can be disabled for development)
        if os.environ.get("PYWRY_SKIP_BUNDLE", "").lower() in ("1", "true", "yes"):
            self.app.display_info("Skipping pytauri-wheel bundling (PYWRY_SKIP_BUNDLE=1)")
            return

        self.app.display_info(f"Bundling pytauri-wheel for {python_tag}-{wheel_platform_tag}")

        # Create vendor directory in the package
        vendor_dir = Path(self.root) / "pywry" / "_vendor" / "pytauri_wheel"
        vendor_dir.mkdir(parents=True, exist_ok=True)

        # Copy the installed pytauri_wheel package to vendor directory
        # The build system already installs pytauri-wheel with the correct architecture
        import importlib.util
        import shutil

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

        self.app.display_success("Bundled pytauri-wheel into pywry/_vendor/pytauri_wheel")

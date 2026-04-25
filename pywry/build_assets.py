"""Convenience script for downloading CDN asset files."""

from __future__ import annotations

import gzip
import json
import re

from functools import lru_cache
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


# Package + asset paths
PACKAGE_JSON_PATH = Path(__file__).with_name("package.json")
ASSETS_DIR = Path(__file__).parent / "pywry" / "frontend" / "assets"

# NPM dependency names used for vendored browser assets
PLOTLY_PACKAGE = "plotly.js-dist"
AGGRID_PACKAGE = "ag-grid-community"
TVCHART_PACKAGE = "lightweight-charts"

# AG Grid theme files we bundle for light/dark mode switching
AGGRID_THEMES = ("quartz", "alpine", "balham", "material")
AGGRID_MODES = ("light", "dark")


def _normalize_npm_version(version_spec: str) -> str:
    """Extract a concrete semver from a package.json dependency spec."""
    match = re.search(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version_spec)
    if not match:
        raise ValueError(f"Could not parse version from dependency spec: {version_spec}")
    return match.group(0)


@lru_cache(maxsize=1)
def _asset_manifest() -> dict[str, str]:
    """Load asset package versions from package.json and build download metadata."""
    if not PACKAGE_JSON_PATH.exists():
        raise FileNotFoundError(f"Missing package manifest: {PACKAGE_JSON_PATH}")

    data = json.loads(PACKAGE_JSON_PATH.read_text(encoding="utf-8"))
    dependencies = data.get("dependencies")
    if not isinstance(dependencies, dict):
        raise ValueError("package.json must contain an object 'dependencies' field")

    missing = [
        package
        for package in (PLOTLY_PACKAGE, AGGRID_PACKAGE, TVCHART_PACKAGE)
        if package not in dependencies
    ]
    if missing:
        missing_names = ", ".join(missing)
        raise ValueError(f"Missing required asset dependency in package.json: {missing_names}")

    plotly_version = _normalize_npm_version(str(dependencies[PLOTLY_PACKAGE]))
    aggrid_version = _normalize_npm_version(str(dependencies[AGGRID_PACKAGE]))
    tvchart_version = _normalize_npm_version(str(dependencies[TVCHART_PACKAGE]))

    return {
        "plotly_version": plotly_version,
        "aggrid_version": aggrid_version,
        "tvchart_version": tvchart_version,
        "plotly_url": f"https://cdn.jsdelivr.net/npm/{PLOTLY_PACKAGE}@{plotly_version}/plotly.js",
        "aggrid_js_url": (
            f"https://cdn.jsdelivr.net/npm/{AGGRID_PACKAGE}@{aggrid_version}/"
            "dist/ag-grid-community.min.js"
        ),
        "aggrid_css_base_url": (
            f"https://cdn.jsdelivr.net/npm/{AGGRID_PACKAGE}@{aggrid_version}/styles"
        ),
        "tvchart_url": (
            f"https://cdn.jsdelivr.net/npm/{TVCHART_PACKAGE}@{tvchart_version}/"
            "dist/lightweight-charts.standalone.production.js"
        ),
    }


def ensure_assets_dir() -> None:
    """Ensure the assets directory exists."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def download_file(url: str, dest: Path, description: str) -> bool:
    """Download a file from a URL and compress it with gzip.

    Parameters
    ----------
    url : str
        The URL to download from.
    dest : Path
        The destination path (will be saved as .gz compressed).
    description : str
        Description for logging.

    Returns
    -------
    bool
        True if successful, False otherwise.
    """
    print(f"Downloading {description}...")

    try:
        with urlopen(url, timeout=60) as response:  # noqa: S310
            content = response.read()
    except URLError as e:
        print(f"  [FAIL] Failed to download {description}: {e}")
        return False
    except OSError as e:
        print(f"  [FAIL] Failed to write {description}: {e}")
        return False

    # Compress with gzip and save with .gz extension
    gz_dest = Path(str(dest) + ".gz")
    gz_dest.write_bytes(gzip.compress(content, compresslevel=9))
    original_size_kb = len(content) / 1024
    compressed_size_kb = gz_dest.stat().st_size / 1024
    ratio = (1 - compressed_size_kb / original_size_kb) * 100
    print(
        f"  [OK] Downloaded {description} "
        f"({original_size_kb:.0f} KB -> {compressed_size_kb:.0f} KB, {ratio:.0f}% smaller)"
    )
    return True


def download_plotly_js() -> bool:
    """Download Plotly.js library (full bundle with templates)."""
    manifest = _asset_manifest()
    version = manifest["plotly_version"]
    dest = ASSETS_DIR / f"plotly-{version}.js"
    gz_dest = Path(str(dest) + ".gz")
    if gz_dest.exists():
        print(f"Plotly.js already exists at {gz_dest}")
        return True
    return download_file(
        manifest["plotly_url"],
        dest,
        f"Plotly.js v{version} (full bundle)",
    )


def download_aggrid_js() -> bool:
    """Download AG Grid JS library."""
    manifest = _asset_manifest()
    version = manifest["aggrid_version"]
    dest = ASSETS_DIR / f"ag-grid-community-{version}.min.js"
    gz_dest = Path(str(dest) + ".gz")
    if gz_dest.exists():
        print(f"AG Grid JS already exists at {gz_dest}")
        return True
    return download_file(manifest["aggrid_js_url"], dest, f"AG Grid v{version}")


def download_aggrid_css() -> bool:
    """Download AG Grid CSS files."""
    manifest = _asset_manifest()
    version = manifest["aggrid_version"]

    success = True

    # Download base styles
    base_dest = ASSETS_DIR / f"ag-grid-{version}.css"
    base_gz_dest = Path(str(base_dest) + ".gz")
    if not base_gz_dest.exists():
        base_url = f"{manifest['aggrid_css_base_url']}/ag-grid.css"
        if not download_file(base_url, base_dest, "AG Grid base CSS"):
            success = False

    # Download theme-specific CSS
    for theme in AGGRID_THEMES:
        for mode in AGGRID_MODES:
            filename = f"ag-theme-{theme}-{mode}-{version}.css"
            dest = ASSETS_DIR / filename
            gz_dest = Path(str(dest) + ".gz")

            if gz_dest.exists():
                print(f"AG Grid {theme} {mode} CSS already exists")
                continue

            # AG Grid themes are packaged differently
            css_url = f"{manifest['aggrid_css_base_url']}/ag-theme-{theme}.css"
            if not download_file(css_url, dest, f"AG Grid {theme} theme"):
                success = False

    return success


def download_tvchart_js() -> bool:
    """Download TradingView Lightweight Charts JS library."""
    manifest = _asset_manifest()
    version = manifest["tvchart_version"]
    dest = ASSETS_DIR / f"lightweight-charts-{version}.standalone.production.js"
    gz_dest = Path(str(dest) + ".gz")
    if gz_dest.exists():
        print(f"Lightweight Charts JS already exists at {gz_dest}")
        return True
    return download_file(
        manifest["tvchart_url"],
        dest,
        f"Lightweight Charts v{version}",
    )


def create_placeholder_files() -> None:
    """Create placeholder files if downloads fail."""
    manifest = _asset_manifest()
    plotly_version = manifest["plotly_version"]
    aggrid_version = manifest["aggrid_version"]
    tvchart_version = manifest["tvchart_version"]

    placeholder_files = [
        (f"plotly-{plotly_version}.js.gz", b"// Plotly.js placeholder - download failed\n"),
        (
            f"ag-grid-community-{aggrid_version}.min.js.gz",
            b"// AG Grid placeholder - download failed\n",
        ),
        (
            f"ag-grid-{aggrid_version}.css.gz",
            b"/* AG Grid CSS placeholder - download failed */\n",
        ),
        (
            f"lightweight-charts-{tvchart_version}.standalone.production.js.gz",
            b"// Lightweight Charts placeholder - download failed\n",
        ),
    ]

    for filename, content in placeholder_files:
        dest = ASSETS_DIR / filename
        if not dest.exists():
            print(f"Creating placeholder for {filename}")
            dest.write_bytes(gzip.compress(content, compresslevel=9))


def download_all_assets() -> bool:
    """Download all required assets.

    Returns
    -------
    bool
        True if all assets were downloaded successfully.
    """
    ensure_assets_dir()

    try:
        manifest = _asset_manifest()
    except (FileNotFoundError, ValueError) as e:
        print(f"[FAIL] Invalid asset package manifest: {e}")
        return False

    print(
        "Using package.json dependency versions: "
        f"{PLOTLY_PACKAGE}@{manifest['plotly_version']}, "
        f"{AGGRID_PACKAGE}@{manifest['aggrid_version']}, "
        f"{TVCHART_PACKAGE}@{manifest['tvchart_version']}"
    )

    results = [
        download_plotly_js(),
        download_aggrid_js(),
        download_aggrid_css(),
        download_tvchart_js(),
    ]

    success = all(results)

    if not success:
        print("\nSome downloads failed. Creating placeholders...")
        create_placeholder_files()

    return success


def verify_assets() -> dict[str, bool]:
    """Verify that all required assets exist.

    Returns
    -------
    dict[str, bool]
        Dictionary mapping asset names to their existence status.
    """
    manifest = _asset_manifest()
    plotly_version = manifest["plotly_version"]
    aggrid_version = manifest["aggrid_version"]
    tvchart_version = manifest["tvchart_version"]

    required_assets = [
        f"plotly-{plotly_version}.js.gz",  # Full bundle with templates
        f"ag-grid-community-{aggrid_version}.min.js.gz",
        f"ag-grid-{aggrid_version}.css.gz",
        f"lightweight-charts-{tvchart_version}.standalone.production.js.gz",
    ]

    return {asset: (ASSETS_DIR / asset).exists() for asset in required_assets}


def main() -> None:
    """Main entry point for the build script."""
    print("PyWry Asset Download Script")
    print("=" * 40)

    download_all_assets()

    print("\nAsset verification:")
    status = verify_assets()
    for asset, exists in status.items():
        marker = "[OK]" if exists else "[FAIL]"
        print(f"  {marker} {asset}")

    if all(status.values()):
        print("\nAll assets are ready!")
    else:
        print("\nWarning: Some assets are missing. PyWry may not function correctly.")


if __name__ == "__main__":
    main()

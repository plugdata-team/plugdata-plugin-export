import json
import subprocess
from pathlib import Path
import platform
import os
import shutil
import argparse
import re
import sys

parser = argparse.ArgumentParser(description="Build plugins with CMake")
parser.add_argument(
    "--compiler-launcher",
    type=str,
    help="Optional compiler launcher (e.g., ccache, sccache)"
)
parser.add_argument(
    "--generator",
    choices=["ninja", "xcode", "visualstudio"],
    default="ninja",
    help="CMake generator to use: ninja (default), xcode, or visualstudio"
)
parser.add_argument(
    "--configure-only",
    action="store_true",
    help="Only run CMake configuration, skip the build step"
)

args = parser.parse_args()

# ── Sanity-check helpers ────────────────────────────────────────────────────

KNOWN_FORMATS = {"VST3", "AU", "LV2", "CLAP", "Standalone"}
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

errors = []   # fatal problems  – abort after collecting all of them
warnings = [] # non-fatal oddities

def error(msg: str):
    errors.append(f"  ERROR: {msg}")

def warn(msg: str):
    warnings.append(f"  WARNING: {msg}")

def validate_config(path: str) -> list:
    """Load and validate config.json. Returns the parsed list or exits."""
    if not os.path.isfile(path):
        print(f"FATAL: config.json not found at '{os.path.abspath(path)}'")
        sys.exit(1)

    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"FATAL: config.json is not valid JSON – {e}")
        sys.exit(1)

    if not isinstance(data, list):
        print("FATAL: config.json must contain a JSON array of plugin objects.")
        sys.exit(1)

    if len(data) == 0:
        warn("config.json contains no plugins – nothing to build.")

    return data

def validate_plugin(plugin: dict, index: int):
    prefix = f"Plugin[{index}]"

    # ── Required fields ──────────────────────────────────────────────────────
    name = plugin.get("name")
    if not name:
        error(f"{prefix}: missing required field 'name'.")
    elif not isinstance(name, str) or not name.strip():
        error(f"{prefix}: 'name' must be a non-empty string (got {name!r}).")

    path = plugin.get("path")
    if not path:
        error(f"{prefix} ({name!r}): missing required field 'path'.")
    else:
        resolved = Path(path).resolve()
        if not resolved.exists():
            error(f"{prefix} ({name!r}): plugin path does not exist: '{resolved}'")
        elif not resolved.is_file():
            error(f"{prefix} ({name!r}): plugin path exists but is not a file: '{resolved}'")

    # ── Optional but validated fields ────────────────────────────────────────
    formats = plugin.get("formats", [])
    if not isinstance(formats, list):
        error(f"{prefix} ({name!r}): 'formats' must be a list, got {type(formats).__name__}.")
    else:
        if len(formats) == 0:
            warn(f"{prefix} ({name!r}): 'formats' is empty – no build targets will be produced.")
        for fmt in formats:
            if fmt not in KNOWN_FORMATS:
                warn(f"{prefix} ({name!r}): unknown format '{fmt}'. "
                     f"Known formats are: {', '.join(sorted(KNOWN_FORMATS))}.")

    plugin_type = plugin.get("type", "")
    if plugin_type and plugin_type.lower() not in ("fx", "instrument", ""):
        warn(f"{prefix} ({name!r}): unexpected 'type' value '{plugin_type}'. "
             f"Expected 'fx' or 'instrument'.")

    version = plugin.get("version", "1.0.0")
    if not VERSION_RE.match(str(version)):
        warn(f"{prefix} ({name!r}): 'version' value '{version}' does not follow "
             f"MAJOR.MINOR.PATCH format.")

    for bool_field in ("enable_gem", "enable_sfizz", "enable_ffmpeg"):
        val = plugin.get(bool_field)
        if val is not None and not isinstance(val, bool):
            warn(f"{prefix} ({name!r}): '{bool_field}' should be a boolean, got {val!r}.")

# ── Run validation ───────────────────────────────────────────────────────────

plugins_config = validate_config("config.json")

for i, plugin in enumerate(plugins_config):
    if not isinstance(plugin, dict):
        error(f"Plugin[{i}]: expected an object, got {type(plugin).__name__}.")
        continue
    validate_plugin(plugin, i)

if warnings:
    print("Build warnings:")
    for w in warnings:
        print(w)
    print()

if errors:
    print("Build errors – cannot continue:")
    for e in errors:
        print(e)
    sys.exit(1)

# ── Continue with the rest of the build ─────────────────────────────────────

system = platform.system()
if system == "Windows":
    cmake_compiler = ["-DCMAKE_C_COMPILER=cl", "-DCMAKE_CXX_COMPILER=cl"]
else:
    cmake_compiler = []

if args.generator == "xcode":
    cmake_generator = ["-GXcode"]
elif args.generator == "visualstudio":
    cmake_generator = ["-GVisual Studio 17 2022", "-A x64"]
    cmake_compiler = []
else:
    cmake_generator = ["-GNinja"]

plugdata_dir = Path("plugdata").resolve()
builds_parent_dir = plugdata_dir.parent

plugins_dir = os.path.join("plugdata", "Plugins")
build_output_dir = os.path.join("Build")
os.makedirs(build_output_dir, exist_ok=True)

if not plugdata_dir.is_dir():
    print(f"FATAL: plugdata directory not found at '{plugdata_dir}'. "
          f"Make sure you're running this script from the repo root and that "
          f"the plugdata submodule has been initialised (git submodule update --init).")
    sys.exit(1)

for plugin in plugins_config:
    name = plugin["name"]
    zip_path = Path(plugin["path"]).resolve()
    patch = plugin["patch"]
    formats = plugin.get("formats", [])
    is_fx = plugin.get("type", "").lower() == "fx"

    build_dir = builds_parent_dir / f"{args.generator}-{name}"
    print(f"\nProcessing: {name}")

    author = plugin.get("author", False)
    version = plugin.get("version", "1.0.0")
    enable_gem = plugin.get("enable_gem", False)
    enable_sfizz = plugin.get("enable_sfizz", False)
    enable_ffmpeg = plugin.get("enable_ffmpeg", False)

    cmake_configure = [
        "cmake",
        "-GNinja",
        *cmake_generator,
        *cmake_compiler,
        f"-B{build_dir}",
        f"-DCUSTOM_PLUGIN_NAME={name}",
        f"-DCUSTOM_PLUGIN_PATCH={patch}",
        f"-DCUSTOM_PLUGIN_PATH={zip_path}",
        f"-DCUSTOM_PLUGIN_COMPANY={author}",
        f"-DCUSTOM_PLUGIN_VERSION={version}",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DENABLE_GEM={'1' if enable_gem else '0'}",
        f"-DENABLE_SFIZZ={'1' if enable_sfizz else '0'}",
        f"-DENABLE_FFMPEG={'1' if enable_ffmpeg else '0'}",
        f"-DCUSTOM_PLUGIN_IS_FX={'1' if is_fx else '0'}"
    ]

    if args.compiler_launcher:
        cmake_configure.append(f"-DCMAKE_C_COMPILER_LAUNCHER={args.compiler_launcher}")
        cmake_configure.append(f"-DCMAKE_CXX_COMPILER_LAUNCHER={args.compiler_launcher}")

    result_configure = subprocess.run(cmake_configure, cwd=plugdata_dir)
    if result_configure.returncode != 0:
        print(f"Failed cmake configure for {name}")
        continue

    if not args.configure_only:
        for fmt in formats:
            if system != "Darwin" and fmt == "AU":
                continue
            target = f"plugdata_{'fx_' if is_fx else ''}{fmt}"
            if fmt == "Standalone":
                target = "plugdata_standalone"

            cmake_build = [
                "cmake",
                "--build", str(build_dir),
                "--target", target,
                "--config Release"
            ]
            print(f"Building target: {target}")
            result_build = subprocess.run(cmake_build, cwd=plugdata_dir)
            if result_build.returncode != 0:
                print(f"Failed to build target: {target}")
            else:
                print(f"Successfully built: {target}")
            format_path = os.path.join(plugins_dir, fmt)
            target_dir = os.path.join(build_output_dir, fmt)

            if fmt == "Standalone":
                if os.path.isdir(format_path):
                    if os.path.exists(target_dir):
                        shutil.rmtree(target_dir)
                    shutil.copytree(format_path, target_dir)
            else:
                extension = ""
                if fmt == "VST3":
                    extension = ".vst3"
                elif fmt == "AU":
                    extension = ".component"
                elif fmt == "LV2":
                    extension = ".lv2"
                elif fmt == "CLAP":
                    extension = ".clap"

                plugin_filename = name + extension
                os.makedirs(target_dir, exist_ok=True)
                src = os.path.join(format_path, plugin_filename)
                dst = os.path.join(target_dir, plugin_filename)
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    if os.path.exists(dst):
                        os.remove(dst)
                    shutil.copy2(src, dst)

import os
import re
import semver
import sys

def bump_version():
    bump_type = os.environ.get("BUMP_TYPE")
    if not bump_type:
        print("BUMP_TYPE environment variable not set.", file=sys.stderr)
        sys.exit(1)

    try:
        with open("pyproject.toml", "r") as f:
            content = f.read()
    except FileNotFoundError:
        print("pyproject.toml not found.", file=sys.stderr)
        sys.exit(1)

    version_match = re.search(r"version = \"(.*?)\"", content)
    if not version_match:
        print("Could not find version in pyproject.toml.", file=sys.stderr)
        sys.exit(1)

    current_version = version_match.group(1)
    
    try:
        version_info = semver.VersionInfo.parse(current_version)
    except ValueError:
        print(f"Invalid semantic version: {current_version}", file=sys.stderr)
        sys.exit(1)

    if bump_type == "major":
        new_version = version_info.bump_major()
    elif bump_type == "minor":
        new_version = version_info.bump_minor()
    elif bump_type == "patch":
        new_version = version_info.bump_patch()
    else:
        print(f"Invalid bump type: {bump_type}", file=sys.stderr)
        sys.exit(1)

    new_version_str = str(new_version)
    new_content = content.replace(f'version = "{current_version}"', f'version = "{new_version_str}"')

    with open("pyproject.toml", "w") as f:
        f.write(new_content)

    print(f"Bumped version from {current_version} to {new_version_str}")

if __name__ == "__main__":
    bump_version()

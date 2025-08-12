#!/usr/bin/env bash
set -euo pipefail

# This script is for smoke-testing a local build of `gitscaffold` inside the `kubelingo` repo.
#
# It assumes:
# 1. This script is run from the root of the 'kubelingo' repository.
# 2. The 'gitscaffold' repository is in a sibling directory to 'kubelingo'.
#
# Example directory structure:
# my_projects/
# ├── gitscaffold/
# └── kubelingo/   <-- Run script from here

# 1) From your gitscaffold checkout, build the wheel
cd ../gitscaffold
pip install --upgrade build    # ensure latest build tooling
# Clean dist dir to ensure we only install the newly built wheel
rm -rf dist
python3 -m build --wheel --outdir dist

# 2) In the target “other” repo where you want to test
TEST_REPO=../kubelingo
cd "$TEST_REPO"

# (Optional) create and activate a fresh venv
python3 -m venv .venv && source .venv/bin/activate

# 3) Install the newly built wheel.
# Use --force-reinstall to ensure the new wheel is used, and --no-cache-dir
# to avoid potential permissions issues with the pip/uv cache.
pip install --force-reinstall --no-cache-dir ../gitscaffold/dist/gitscaffold-*.whl

# 4) Verify it’s on your PATH
which gitscaffold
gitscaffold --version

# 5) Sync local roadmap with GitHub: create missing issues and import existing ones.
gitscaffold sync docs/roadmap.md
gitscaffold import docs/roadmap.md

echo "✅ Local test complete. If everything looks good, you’re ready to publish to PyPI!"

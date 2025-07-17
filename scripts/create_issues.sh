#!/bin/bash

# Create GitHub issues for the roadmap items using gitscaffold.
# This script reads issue definitions from the project roadmap.

gitscaffold issues create --from-markdown docs/roadmap.md \
  --section "Test Coverage Improvements" \
  --section "Enhanced Validation System" \
  --section "Developer Experience"

echo "All roadmap issues have been processed by gitscaffold."

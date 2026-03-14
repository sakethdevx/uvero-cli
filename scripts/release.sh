#!/usr/bin/env bash
# Release automation script
set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 0.2.0"
    exit 1
fi

VERSION=$1

echo "🚀 Bumping version to $VERSION"

# Update pyproject.toml
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/version = \".*\"/version = \"$VERSION\"/" pyproject.toml
else
    sed -i "s/version = \".*\"/version = \"$VERSION\"/" pyproject.toml
fi

# Determine previous tag to generate changelog
PREV_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

echo "📝 Generating release notes..."
cat > RELEASE_NOTES.md <<EOF
# Uvero CLI v$VERSION

## Changes
EOF

if [ -z "$PREV_TAG" ]; then
    git log --pretty=format:"* %s" >> RELEASE_NOTES.md
else
    git log ${PREV_TAG}..HEAD --pretty=format:"* %s" >> RELEASE_NOTES.md
fi

echo "" >> RELEASE_NOTES.md
echo "## Migration Notes" >> RELEASE_NOTES.md
echo "No specific migration steps required." >> RELEASE_NOTES.md

echo "✅ Updated pyproject.toml to $VERSION"
echo "✅ Generated RELEASE_NOTES.md template"
echo ""
echo "Next steps:"
echo "1. Review and edit RELEASE_NOTES.md"
echo "2. Commit changes: git commit -am 'Bump version to $VERSION'"
echo "3. Tag release (signed): git tag -s v$VERSION -m 'Release v$VERSION'"
echo "4. Push tags: git push --tags"

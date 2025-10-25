#!/usr/bin/env bash
# Lightweight helper to download a portable tesseract build into backend/tools/tesseract
# Usage: ./scripts/get_tesseract.sh [DEST_DIR]
# By default will place files under backend/tools/tesseract

set -e
DEST=${1:-backend/tools/tesseract}
mkdir -p "$DEST"

echo "TESSERACT helper: destination=$DEST"

# Allow overriding download URL via env var. If unset, try to auto-select the latest
# UB-Mannheim release asset (prefers windows w64 installer/zip if available).
: ${TESSERACT_DOWNLOAD_URL:=}

if [ -z "$TESSERACT_DOWNLOAD_URL" ]; then
  echo "TESSERACT_DOWNLOAD_URL not set — trying to auto-detect latest UB-Mannheim release asset..."
  if command -v curl >/dev/null 2>&1; then
    JSON=$(curl -s "https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest")
  elif command -v wget >/dev/null 2>&1; then
    JSON=$(wget -qO- "https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest")
  else
    echo "curl or wget required to auto-detect UB-Mannheim release. Please set TESSERACT_DOWNLOAD_URL manually."; exit 1
  fi

  # Use Python (available on most dev machines) to pick an asset matching common Windows keywords
  if command -v python3 >/dev/null 2>&1; then
    TESSERACT_DOWNLOAD_URL=$(echo "$JSON" | python3 -c "import sys,json,re
j=json.load(sys.stdin)
assets=j.get('assets',[])
for a in assets:
    name=a.get('name','').lower()
    if any(k in name for k in ['w64','win','windows','portable','zip','exe']):
        print(a.get('browser_download_url'))
        sys.exit(0)
print('')")
  elif command -v python >/dev/null 2>&1; then
    TESSERACT_DOWNLOAD_URL=$(echo "$JSON" | python -c "import sys,json,re
j=json.load(sys.stdin)
assets=j.get('assets',[])
for a in assets:
    name=a.get('name','').lower()
    if any(k in name for k in ['w64','win','windows','portable','zip','exe']):
        print(a.get('browser_download_url'))
        sys.exit(0)
print('')")
  fi

  if [ -z "$TESSERACT_DOWNLOAD_URL" ]; then
    echo "Could not auto-detect a UB-Mannheim asset. Please set TESSERACT_DOWNLOAD_URL to a download URL (see https://github.com/UB-Mannheim/tesseract/releases)."
    exit 1
  fi
  echo "Auto-selected: $TESSERACT_DOWNLOAD_URL"
fi

TMPFILE=$(mktemp)
echo "Downloading $TESSERACT_DOWNLOAD_URL ..."
if command -v curl >/dev/null 2>&1; then
  curl -L "$TESSERACT_DOWNLOAD_URL" -o "$TMPFILE"
elif command -v wget >/dev/null 2>&1; then
  wget -O "$TMPFILE" "$TESSERACT_DOWNLOAD_URL"
else
  echo "curl or wget required to download"; exit 2
fi

# Try to unpack common archive formats
if file "$TMPFILE" | grep -iq 'Zip archive'; then
  unzip -o "$TMPFILE" -d "$DEST"
elif file "$TMPFILE" | grep -iq 'gzip compressed'; then
  tar xzf "$TMPFILE" -C "$DEST"
else
  # fallback: copy raw
  mv "$TMPFILE" "$DEST/$(basename $TESSERACT_DOWNLOAD_URL)"
fi

rm -f "$TMPFILE"

echo "Downloaded and unpacked to $DEST."

echo "If you're on Windows and the downloaded structure doesn't contain tesseract.exe, extract manually and place tesseract.exe under backend/tools/tesseract/tesseract.exe"

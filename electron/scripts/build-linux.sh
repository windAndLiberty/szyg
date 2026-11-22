#!/usr/bin/env bash
# Build the amd64 Debian desktop package from the public product and locked dependencies.
set -euo pipefail
cd "$(dirname "$0")/../.."
root=$PWD
[[ $(uname -sm) == 'Linux x86_64' ]]
work=$root/electron/dist/linux-work
mkdir -p "$work"
stage=$(mktemp -d "$work/package.XXXXXXXX")
trap 'rm -rf -- "$stage"' EXIT
desktop=$stage/opt/szyg
res=$desktop/resources
app=$res/app
version=$(node -p "require('./electron/package.json').version")
constants=./electron/openclaw/runtime-constants
claw_version=$(node -p "require('$constants').OPENCLAW_RUNTIME_VERSION")
node_version=$(node -p "require('$constants').OPENCLAW_NODE_VERSION")
claw=$res/runtime/openclaw/$claw_version
mkdir -p "$app" "$claw/app" "$res/frontend" "$res/server" "$res/browsers"

npm --prefix electron ci --no-audit
npm --prefix electron run install:electron
npm --prefix electron run audit:source
npm --prefix szyg-frontend ci --no-audit
npm --prefix szyg-frontend run build
cp -a electron/node_modules/electron/dist/. "$desktop/"
mv "$desktop/electron" "$desktop/szyg"
chmod 4755 "$desktop/chrome-sandbox"
rm -f "$res/default_app.asar"
cp -a electron/{main.js,preload.js,product.js,browser,openclaw,package.json,package-lock.json} "$app/"
mkdir "$app/assets"
cp -a electron/assets/public "$app/assets/"
npm --prefix "$app" ci --omit=dev --no-audit
cp -a szyg-frontend/dist/. "$res/frontend/"
cp electron/THIRD_PARTY_NOTICES.md "$res/"

python=$(uv python find --managed-python --no-project 3.12)
cp -a "$( "$python" -c 'import sys; print(sys.base_prefix)' )" "$res/python"
python=$res/python/bin/python3
uv export --locked --no-dev --no-emit-project --extra platforms --extra skills > "$work/backend-requirements.txt"
uv pip install --python "$python" --break-system-packages -r "$work/backend-requirements.txt"
git ls-files -z server/szyg | rsync -aR --from0 --files-from=- ./ "$res/"
cp server/{szyg_backend_entry.py,hermes_runtime_entry.py} "$res/server/"
"$python" electron/scripts/build-release-config.py config.example.yaml "$res/config.yaml"
"$python" -m playwright install chromium
"$python" -m playwright install --dry-run chromium > "$work/browser-locations.txt"
mapfile -t browsers < <(sed -n 's/^  Install location: *//p' "$work/browser-locations.txt")
[[ ${#browsers[@]} -ge 3 ]]
for browser in "${browsers[@]}"; do
  test -f "$browser/INSTALLATION_COMPLETE"
  cp -a "$browser" "$res/browsers/"
done

lock=server/vendor/hermes-agent.lock.json
tag=$(node -p "require('./$lock').tag")
checksum=$(node -p "require('./$lock').archive_sha256")
if ! echo "$checksum  $work/hermes.zip" | sha256sum -c --status; then
  curl -fLsS --retry 3 "https://codeload.github.com/NousResearch/hermes-agent/zip/refs/tags/$tag" -o "$work/hermes.zip"
fi
echo "$checksum  $work/hermes.zip" | sha256sum -c
unzip -qo "$work/hermes.zip" -d "$stage/hermes-source"
source_dir=$stage/hermes-source/hermes-agent-${tag#v}
uv export --project "$source_dir" --frozen --no-dev --no-emit-project > "$work/hermes-requirements.txt"
uv pip install --python "$python" --target "$res/hermes-site" -r "$work/hermes-requirements.txt" -r server/hermes-runtime-requirements.txt
mkdir -p "$res/server/vendor/hermes_agent"
rsync -a --exclude='.git*' --exclude='/apps' --exclude='/website' --exclude='/tests' --exclude='/docs' --exclude='.env*' "$source_dir/" "$res/server/vendor/hermes_agent/"
rm -rf -- "$stage/hermes-source"
install -m755 electron/build/linux/hermes-runtime "$res/hermes-runtime"

npm install --prefix "$work/node" --no-audit --ignore-scripts --save-exact "node-linux-x64@$node_version"
node_bin=$work/node/node_modules/node-linux-x64/bin
install -m755 "$node_bin/node" "$claw/node"
cp electron/build/linux/openclaw/package*.json "$claw/app/"
PATH="$node_bin:$PATH" npm --prefix "$claw/app" ci --omit=dev --no-audit
node electron/scripts/linux-manifest.cjs "$res"
mkdir -p "$stage/DEBIAN" "$stage/usr/bin"
ln -s /opt/szyg/szyg "$stage/usr/bin/szyg"
install -Dm644 electron/build/linux/szyg.desktop "$stage/usr/share/applications/szyg.desktop"
install -Dm644 electron/assets/public/app-icon.png "$stage/usr/share/pixmaps/szyg.png"
cat > "$stage/DEBIAN/control" <<CONTROL
Package: szyg
Version: $version
Architecture: amd64
Maintainer: YuSeTech
Depends: libc6, libgtk-3-0 | libgtk-3-0t64, libnss3, libasound2 | libasound2t64, libgbm1, libxss1, libatk-bridge2.0-0 | libatk-bridge2.0-0t64, ffmpeg
Description: Xiaoyu AI digital employee desktop
CONTROL
output="$root/electron/dist/szyg_${version}_amd64.deb"
dpkg-deb --root-owner-group -Zzstd -z3 --build "$stage" "$work/szyg.deb"
mv "$work/szyg.deb" "$output"
sha256sum "$output"

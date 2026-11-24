#!/bin/sh
# Install the opt-in tools of the full test suite on Debian or Ubuntu (x86-64) and
# write .env, which `pdm run test` loads. Used by the manual full-suite jobs of the
# CI; it runs as root or with sudo.
#
#   sh scripts/ci_full_tools.sh <tools folder>
#
# Tools: one pinned OSS CAD Suite release (Icarus Verilog, Verilator, Yosys with the
# slang plugin, SymbiYosys with suprove), Webots R2025a run headless through
# xvfb-run, Java and the MC2 jar of third_party/mc2. Every download and the jar are
# checked against their SHA-256. Downloads are kept in <tools folder>/downloads,
# which the CI caches. Run it from the repository root.
set -eu

OSS_CAD_TAG=2026-10-31
OSS_CAD_FILE=oss-cad-suite-linux-x64-20261031.tgz
OSS_CAD_SHA256=e0349f66547ca1ac9a24b5e06287d4719aa0213d431e1168eb319915340dc665
WEBOTS_FILE=webots_2025a_amd64.deb
WEBOTS_URL=https://github.com/cyberbotics/webots/releases/download/R2025a/$WEBOTS_FILE
WEBOTS_SHA256=6253d58c9b625a83ed7b62cd85a640fd0542d441c48d633a60932208b40b0657
MC2_JAR=third_party/mc2/MC2v2.0beta2.jar
MC2_SHA256=c177aa32ef7bb908bd44fa24000d40ecae620ec3ddd14d3bf5b0aa8f6a440d81

TOOLS=${1:?usage: ci_full_tools.sh <tools folder>}
mkdir -p "$TOOLS/downloads"
TOOLS=$(cd "$TOOLS" && pwd)
if [ -e .env ]; then
    echo "refused: .env exists; this script writes it" >&2
    exit 1
fi
SUDO=
[ "$(id -u)" -eq 0 ] || SUDO=sudo
export DEBIAN_FRONTEND=noninteractive

# fetch <url> <file> <sha256>: download into downloads/ unless the cached copy matches
fetch() {
    target="$TOOLS/downloads/$2"
    if ! echo "$3  $target" | sha256sum -c --status - 2>/dev/null; then
        curl -fsSL -o "$target" "$1"
        echo "$3  $target" | sha256sum -c -
    fi
}

$SUDO apt-get update
$SUDO apt-get install -y --no-install-recommends \
    ca-certificates curl g++ make xvfb xauth default-jre-headless

fetch "https://github.com/YosysHQ/oss-cad-suite-build/releases/download/$OSS_CAD_TAG/$OSS_CAD_FILE" \
    "$OSS_CAD_FILE" "$OSS_CAD_SHA256"
rm -rf "$TOOLS/oss-cad-suite"
tar -xzf "$TOOLS/downloads/$OSS_CAD_FILE" -C "$TOOLS"
SUITE="$TOOLS/oss-cad-suite/bin"
"$SUITE/yosys" -V

fetch "$WEBOTS_URL" "$WEBOTS_FILE" "$WEBOTS_SHA256"
$SUDO apt-get install -y --no-install-recommends "$TOOLS/downloads/$WEBOTS_FILE"
# The test calls NNC_WEBOTS as an executable: a wrapper gives Webots a virtual display.
cat > "$TOOLS/webots-headless" <<'EOF'
#!/bin/sh
exec xvfb-run --auto-servernum webots "$@"
EOF
chmod +x "$TOOLS/webots-headless"

{
    echo "NNC_IVERILOG=$SUITE/iverilog"
    echo "NNC_VERILATOR=$SUITE/verilator_bin"
    echo "NNC_YOSYS=$SUITE/yosys"
    echo "NNC_SBY=$SUITE/sby"
    echo "NNC_SBY_LIVE=$SUITE/sby"
    echo "NNC_WEBOTS=$TOOLS/webots-headless"
} > .env

echo "$MC2_SHA256  $MC2_JAR" | sha256sum -c -
echo "NNC_MC2_JAR=$(pwd)/$MC2_JAR" >> .env
cat .env

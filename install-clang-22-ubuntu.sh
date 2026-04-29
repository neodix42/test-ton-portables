#!/usr/bin/env bash
set -euo pipefail

fix_broken_apt_state_if_needed() {
  if  apt-get check >/dev/null 2>&1; then
    return
  fi

  echo "Detected broken apt/dpkg state. Running apt --fix-broken install..."
   apt-get -y --fix-broken install || true

  if apt-get check >/dev/null 2>&1; then
    return
  fi

  echo "Broken state persists. Clearing possible clang-22 holds and removing conflicting packages..."
  for pkg in clang-22 clang-tools-22; do
    if apt-mark showhold 2>/dev/null | grep -qx "$pkg"; then
       apt-mark unhold "$pkg"
    fi
  done

  apt-get -y remove --purge clang-tools-22 clang-22 || true
  apt-get -y --fix-broken install
}

ensure_prerequisites() {
  local -a missing_packages=()

  command -v lsb_release >/dev/null 2>&1 || missing_packages+=("lsb-release")
  command -v gpg >/dev/null 2>&1 || missing_packages+=("gnupg")
  command -v wget >/dev/null 2>&1 || missing_packages+=("wget")

  if [ "${#missing_packages[@]}" -eq 0 ]; then
    return
  fi

   apt-get update
   apt-get install -y "${missing_packages[@]}"
}

fix_broken_apt_state_if_needed
ensure_prerequisites

require_clang_22() {
  local bin="$1"
  local version_line

  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "ERROR: '$bin' is not available in PATH."
    exit 1
  fi

  version_line=$("$bin" --version 2>/dev/null | head -n1 || true)
  if ! echo "$version_line" | grep -Eq 'version[[:space:]]+22([.[:space:]]|$)'; then
    echo "ERROR: '$bin' is not clang 22."
    echo "$bin --version output:"
    "$bin" --version || true
    exit 1
  fi
}

is_clang_22() {
  local bin="$1"
  local version_line

  if ! command -v "$bin" >/dev/null 2>&1; then
    return 1
  fi

  version_line=$("$bin" --version 2>/dev/null | head -n1 || true)
  echo "$version_line" | grep -Eq 'version[[:space:]]+22([.[:space:]]|$)'
}

remove_clang_tools_22_if_installed() {
  if dpkg-query -W -f='${Status}\n' clang-tools-22 2>/dev/null | grep -q "^install ok installed$"; then
    echo "Removing clang-tools-22 to avoid dpkg file conflicts with clang-22 upgrades..."
     apt remove -y clang-tools-22
  fi
}

llvm_repo_suite_exists() {
  local repo_codename="$1"
  local release_url="https://apt.llvm.org/${repo_codename}/dists/llvm-toolchain-${repo_codename}-22/Release"

  wget -q --spider "$release_url"
}

select_llvm_repo_codename() {
  local base_codename="$1"
  local -a candidates=("$base_codename")
  local candidate

  # Ubuntu 26.04 currently may not have matching suites on apt.llvm.org.
  if [ "$base_codename" = "resolute" ]; then
    candidates+=("noble" "jammy")
  fi

  for candidate in "${candidates[@]}"; do
    if llvm_repo_suite_exists "$candidate"; then
      echo "$candidate"
      return 0
    fi
  done

  return 1
}

clang_22_available_in_default_repos() {
  local candidate

  candidate="$(apt-cache policy clang-22 2>/dev/null | awk '/Candidate:/ { print $2; exit }')"
  [ -n "$candidate" ] && [ "$candidate" != "(none)" ]
}

install_clang_22_from_llvm_repo() {
  local llvm_repo_codename

  llvm_repo_codename="$(select_llvm_repo_codename "$DISTRO_CODENAME")" || {
    echo "Unsupported LLVM repo suite for codename '$DISTRO_CODENAME'."
    echo "Checked llvm-toolchain suites for: $DISTRO_CODENAME${DISTRO_CODENAME:+, noble, jammy}"
    exit 1
  }

  if [ "$llvm_repo_codename" != "$DISTRO_CODENAME" ]; then
    echo "LLVM suite for '$DISTRO_CODENAME' is unavailable; using '$llvm_repo_codename' repository."
  fi

   mkdir -p /etc/apt/keyrings
  wget -O - https://apt.llvm.org/llvm-snapshot.gpg.key |  tee /etc/apt/keyrings/llvm.asc >/dev/null
  cat <<EOF |  tee /etc/apt/sources.list.d/llvm.sources >/dev/null
Types: deb
URIs: https://apt.llvm.org/${llvm_repo_codename}/
Suites: llvm-toolchain-${llvm_repo_codename}-22
Components: main
Signed-By: /etc/apt/keyrings/llvm.asc
EOF
   apt -y update
   apt install -y clang-22
}

DISTRO_CODENAME=$(lsb_release -cs)
DISTRO_ID="$(. /etc/os-release && echo "${ID:-}")"
DISTRO_VERSION_ID="$(. /etc/os-release && echo "${VERSION_ID:-}")"

if is_clang_22 clang; then
  echo "Default clang is already version 22, skipping package installation."
else
  remove_clang_tools_22_if_installed

  if [ "$DISTRO_CODENAME" = "jammy" ] || [ "$DISTRO_CODENAME" = "bookworm" ] || { [ "$DISTRO_ID" = "debian" ] && [ "${DISTRO_VERSION_ID%%.*}" = "12" ]; }; then
    wget https://apt.llvm.org/llvm.sh
    chmod +x llvm.sh
     ./llvm.sh 22 clang
  elif [ "$DISTRO_CODENAME" = "resolute" ]; then
     apt -y update
    if clang_22_available_in_default_repos; then
       apt install -y clang-22
    else
      echo "clang-22 is unavailable in default '$DISTRO_CODENAME' repositories; trying apt.llvm.org fallback."
      install_clang_22_from_llvm_repo
    fi
  elif [ "$DISTRO_CODENAME" = "noble" ]; then
    install_clang_22_from_llvm_repo
  else
    echo "Unsupported distribution/codename: ID=$DISTRO_ID VERSION_ID=$DISTRO_VERSION_ID CODENAME=$DISTRO_CODENAME"
    echo "Supported versions: Ubuntu 22.04 (jammy), Ubuntu 24.04 (noble), Ubuntu 26.04 (resolute), Debian 12 (bookworm)"
    exit 1
  fi
fi

 update-alternatives --install /usr/bin/clang clang /usr/bin/clang-22 200
 update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-22 200
 ln -sf /usr/bin/clang-22 /usr/bin/clang
 ln -sf /usr/bin/clang++-22 /usr/bin/clang++

require_clang_22 clang-22
require_clang_22 clang

echo "clang-22 installation complete."

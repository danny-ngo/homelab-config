import io
import os
import stat
import subprocess
import tarfile
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install.sh"


class InstallerTests(unittest.TestCase):
    def write_executable(self, path, content):
        path.write_text(textwrap.dedent(content).lstrip())
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def base_environment(self, home, fake_bin):
        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(home),
                "PATH": f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin",
            }
        )
        return environment

    def test_macos_creates_parent_and_lets_git_name_the_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            home = temporary_path / "home"
            fake_bin = temporary_path / "bin"
            log = temporary_path / "commands.log"
            brew_template = temporary_path / "brew"
            homebrew_installer = temporary_path / "homebrew-install.sh"
            home.mkdir()
            fake_bin.mkdir()

            self.write_executable(
                fake_bin / "uname",
                """
                #!/usr/bin/env bash
                printf '%s\\n' Darwin
                """,
            )
            self.write_executable(
                brew_template,
                """
                #!/usr/bin/env bash
                printf 'brew:%s\\n' "$*" >> "$INSTALLER_TEST_LOG"
                case "${1:-}" in
                  shellenv) printf '%s\\n' ':' ;;
                  list) exit 1 ;;
                  install) exit 0 ;;
                esac
                """,
            )
            self.write_executable(
                homebrew_installer,
                """
                #!/usr/bin/env bash
                cp "$INSTALLER_TEST_BREW_TEMPLATE" "$INSTALLER_TEST_FAKE_BIN/brew"
                chmod u+x "$INSTALLER_TEST_FAKE_BIN/brew"
                printf 'homebrew:installed\\n' >> "$INSTALLER_TEST_LOG"
                """,
            )
            self.write_executable(
                fake_bin / "curl",
                """
                #!/usr/bin/env bash
                output=""
                previous=""
                for argument in "$@"; do
                  if [[ "$previous" == "--output" ]]; then
                    output="$argument"
                  fi
                  previous="$argument"
                done
                cp "$INSTALLER_TEST_HOMEBREW_INSTALLER" "$output"
                """,
            )
            self.write_executable(
                fake_bin / "git",
                """
                #!/usr/bin/env bash
                printf 'git-cwd:%s\\n' "$PWD" >> "$INSTALLER_TEST_LOG"
                printf 'git:%s\\n' "$*" >> "$INSTALLER_TEST_LOG"
                if [[ "${1:-}" == "clone" ]]; then
                  mkdir -p homelab-config/.git
                  cat > homelab-config/bootstrap.sh <<'EOF'
                #!/usr/bin/env bash
                printf 'bootstrap:%s\\n' "$*" >> "$INSTALLER_TEST_LOG"
                EOF
                  exit 0
                fi
                exit 1
                """,
            )

            environment = self.base_environment(home, fake_bin)
            environment.update(
                {
                    "INSTALLER_TEST_BREW_TEMPLATE": str(brew_template),
                    "INSTALLER_TEST_FAKE_BIN": str(fake_bin),
                    "INSTALLER_TEST_HOMEBREW_INSTALLER": str(homebrew_installer),
                    "INSTALLER_TEST_LOG": str(log),
                }
            )
            result = subprocess.run(
                ["/bin/bash", str(INSTALLER), "--dry-run"],
                cwd=temporary_path,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            checkout = home / "src" / "homelab-config"
            self.assertTrue(checkout.is_dir())
            commands = log.read_text()
            self.assertIn("homebrew:installed", commands)
            self.assertIn(f"git-cwd:{home / 'src'}", commands)
            self.assertIn(
                "git:clone -- https://github.com/danny-ngo/homelab-config.git",
                commands,
            )
            self.assertNotIn("brew:install git", commands)
            self.assertIn("bootstrap:--dry-run", commands)
            self.assertIn(f"Checkout ready: {checkout}", result.stdout)

    def test_macos_reuses_matching_checkout_without_pulling(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            home = temporary_path / "home"
            fake_bin = temporary_path / "bin"
            parent = temporary_path / "Developer"
            checkout = parent / "homelab-config"
            log = temporary_path / "commands.log"
            home.mkdir()
            fake_bin.mkdir()
            (checkout / ".git").mkdir(parents=True)
            self.write_executable(
                checkout / "bootstrap.sh",
                """
                #!/usr/bin/env bash
                printf 'bootstrap:%s\\n' "$*" >> "$INSTALLER_TEST_LOG"
                """,
            )
            self.write_executable(
                fake_bin / "uname",
                """
                #!/usr/bin/env bash
                printf '%s\\n' Darwin
                """,
            )
            self.write_executable(
                fake_bin / "brew",
                """
                #!/usr/bin/env bash
                case "${1:-}" in
                  shellenv) printf '%s\\n' ':' ;;
                  list) exit 0 ;;
                esac
                """,
            )
            self.write_executable(
                fake_bin / "git",
                """
                #!/usr/bin/env bash
                printf 'git:%s\\n' "$*" >> "$INSTALLER_TEST_LOG"
                if [[ "$*" == *"rev-parse --is-inside-work-tree"* ]]; then
                  printf '%s\\n' true
                  exit 0
                fi
                if [[ "$*" == *"remote get-url origin"* ]]; then
                  printf '%s\\n' git@github.com:danny-ngo/homelab-config.git
                  exit 0
                fi
                exit 1
                """,
            )

            environment = self.base_environment(home, fake_bin)
            environment.update(
                {
                    "HOMELAB_CONFIG_PARENT": str(parent),
                    "INSTALLER_TEST_LOG": str(log),
                }
            )
            result = subprocess.run(
                ["/bin/bash", str(INSTALLER), "--check"],
                cwd=temporary_path,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            commands = log.read_text()
            self.assertNotIn("clone", commands)
            self.assertNotIn("pull", commands)
            self.assertIn("bootstrap:--check", commands)
            self.assertIn("Using existing checkout without pulling", result.stdout)

    def test_linux_downloads_temporary_checkout_and_forces_prepare_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            home = temporary_path / "home"
            fake_bin = temporary_path / "bin"
            archive = temporary_path / "homelab-config.tar.gz"
            log = temporary_path / "commands.log"
            home.mkdir()
            fake_bin.mkdir()

            bootstrap = b"""#!/usr/bin/env bash
printf 'bootstrap:%s\\n' "$*" >> "$INSTALLER_TEST_LOG"
"""
            with tarfile.open(archive, "w:gz") as tar:
                info = tarfile.TarInfo("homelab-config-main/bootstrap.sh")
                info.mode = 0o755
                info.size = len(bootstrap)
                tar.addfile(info, io.BytesIO(bootstrap))

            self.write_executable(
                fake_bin / "uname",
                """
                #!/usr/bin/env bash
                printf '%s\\n' Linux
                """,
            )
            self.write_executable(
                fake_bin / "curl",
                """
                #!/usr/bin/env bash
                output=""
                previous=""
                for argument in "$@"; do
                  if [[ "$previous" == "--output" ]]; then
                    output="$argument"
                  fi
                  previous="$argument"
                done
                cp "$INSTALLER_TEST_ARCHIVE" "$output"
                printf 'curl:%s\\n' "$*" >> "$INSTALLER_TEST_LOG"
                """,
            )

            environment = self.base_environment(home, fake_bin)
            environment.update(
                {
                    "INSTALLER_TEST_ARCHIVE": str(archive),
                    "INSTALLER_TEST_LOG": str(log),
                }
            )
            result = subprocess.run(
                ["/bin/bash", str(INSTALLER), "--dry-run"],
                cwd=temporary_path,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("bootstrap:--prepare-only --dry-run", log.read_text())
            self.assertFalse((home / "src").exists())
            self.assertIn("Running managed-node preparation", result.stdout)


if __name__ == "__main__":
    unittest.main()

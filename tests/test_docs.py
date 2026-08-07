import re
import unittest
from pathlib import Path
from urllib.parse import urlsplit

import yaml


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class DocumentationTests(unittest.TestCase):
    def test_pages_configuration_and_landing_page_exist(self):
        config = yaml.safe_load((DOCS / "_config.yml").read_text())

        self.assertEqual(config["baseurl"], "/homelab-config")
        self.assertEqual(config["repository"], "danny-ngo/homelab-config")
        self.assertEqual(
            config["header_pages"],
            [
                "bootstrap-python-flow.md",
                "runbooks/dns.md",
                "decisions/open-decisions.md",
            ],
        )
        self.assertIn("jekyll-relative-links", config["plugins"])
        self.assertTrue((DOCS / "index.md").is_file())

    def test_every_markdown_page_has_valid_front_matter(self):
        for path in DOCS.rglob("*.md"):
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text()
                self.assertTrue(text.startswith("---\n"))
                _, front_matter, _ = text.split("---\n", 2)
                metadata = yaml.safe_load(front_matter)
                self.assertEqual(metadata["layout"], "default")
                self.assertTrue(metadata["title"])

    def test_internal_document_links_have_source_targets(self):
        markdown_link = re.compile(r"\[[^]]+\]\(([^)]+)\)")
        html_link = re.compile(r"(?:href|src)=\"([^\"]+)\"")

        for path in DOCS.rglob("*"):
            if path.suffix not in {".md", ".html"}:
                continue
            pattern = markdown_link if path.suffix == ".md" else html_link
            for raw_target in pattern.findall(path.read_text()):
                target = urlsplit(raw_target)
                if target.scheme or target.netloc or not target.path:
                    continue

                resolved = (path.parent / target.path).resolve()
                if not resolved.exists() and resolved.suffix == ".html":
                    resolved = resolved.with_suffix(".md")

                with self.subTest(path=path.relative_to(ROOT), target=raw_target):
                    self.assertTrue(resolved.is_relative_to(DOCS.resolve()))
                    self.assertTrue(resolved.is_file())

    def test_docs_contain_only_allowlisted_literal_addresses(self):
        text = "\n".join(
            path.read_text()
            for path in DOCS.rglob("*")
            if path.suffix in {".md", ".html", ".yml"}
        )
        ipv4_addresses = set(
            re.findall(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])", text)
        )

        self.assertEqual(
            ipv4_addresses,
            {"1.1.1.1", "127.0.0.1", "127.0.1.1", "192.0.2.33"},
        )
        self.assertNotRegex(text, r"(?i)\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b")
        email_like_values = set(
            re.findall(r"(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", text)
        )
        self.assertEqual(email_like_values, {"systemd-zram-setup@zram0.service"})
        self.assertNotRegex(text, r"(?i)\b[\w-]+\.ts\.net\b")

        healthchecks_paths = re.findall(r"https://hc-ping\.com/([^\s<]+)", text)
        self.assertTrue(healthchecks_paths)
        for endpoint in healthchecks_paths:
            self.assertRegex(endpoint, r"^[A-Z_]+UUID$")


if __name__ == "__main__":
    unittest.main()

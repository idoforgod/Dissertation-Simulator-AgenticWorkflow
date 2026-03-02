#!/usr/bin/env python3
"""Validation for security_sensitive_file_guard.py pattern matching."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from security_sensitive_file_guard import check_sensitive_file

passed = 0
failed = 0

def test(desc, should_match, path):
    global passed, failed
    result = check_sensitive_file(path)
    matched = result is not None
    if matched == should_match:
        passed += 1
        label = f"detected: {result}" if matched else "clean"
        print(f"  PASS: {desc} ({label})")
    else:
        failed += 1
        print(f"  FAIL: {desc} — expected {'match' if should_match else 'clean'}, "
              f"got {'match: ' + str(result) if matched else 'clean'}")

print("=== Security-Sensitive File Detection ===")

# Environment files
test(".env at root", True, ".env")
test(".env in subdir", True, "config/.env")
test(".env.local", True, ".env.local")
test(".env.production", True, ".env.production")
test(".env.development", True, "app/.env.development")

# Private keys
test("PEM file", True, "certs/server.pem")
test("KEY file", True, "ssl/private.key")
test("P12 file", True, "store.p12")
test("SSH id_rsa", True, "id_rsa")
test("SSH id_ed25519", True, ".ssh/id_ed25519")

# Credential configs
test("credentials.json", True, "credentials.json")
test("secrets.yaml", True, "deploy/secrets.yaml")
test("passwords.toml", True, "config/passwords.toml")

# Cloud credentials
test("AWS credentials", True, ".aws/credentials")
test("AWS config", True, ".aws/config")
test("GCP file", True, ".gcloud/application_default_credentials.json")
test("Azure file", True, ".azure/accessTokens.json")

# Auth tokens
test(".npmrc", True, ".npmrc")
test(".pypirc", True, ".pypirc")
test(".netrc", True, ".netrc")
test(".htpasswd", True, ".htpasswd")

# K8s secrets
test("k8s secret yaml", True, "k8s/db-secret.yaml")
test("k8s secrets.yml", True, "namespace/app-secrets.yml")

# Token stores
test("token.json", True, "token.json")
test("api-key.yaml", True, "config/api-key.yaml")
test("auth_token.txt", True, "auth_token.txt")

# Service accounts
test("service_account.json", True, "firebase/service_account.json")
test("service-account-key.json", True, "gcp/service-account-key.json")

# Terraform
test(".tfstate", True, "infra/terraform.tfstate")
test(".tfvars", True, "env/prod.tfvars")

print("\n=== Safe Files (should NOT match) ===")

# Normal code files
test("Python file", False, "src/main.py")
test("JavaScript file", False, "app/index.js")
test("TypeScript file", False, "components/Button.tsx")
test("Markdown file", False, "README.md")
test("JSON config", False, "package.json")
test("YAML config", False, ".github/workflows/ci.yaml")
test("HTML file", False, "public/index.html")
test("CSS file", False, "styles/main.css")

# Files with tricky names (should NOT match)
test("environment.ts (not .env)", False, "src/environment.ts")
test("key-handler.py (not .key)", False, "handlers/key-handler.py")
test("secret-sauce.md (not secret.yaml)", False, "docs/secret-sauce.md")
test("token-parser.js (not token.json)", False, "lib/token-parser.js")
test("CLAUDE.md", False, "CLAUDE.md")
test("settings.json", False, ".claude/settings.json")

print(f"\n=== Results: {passed} passed, {failed} failed ===")
sys.exit(1 if failed else 0)

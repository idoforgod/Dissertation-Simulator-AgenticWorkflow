#!/usr/bin/env python3
"""Validation for output_secret_filter.py pattern matching + transcript parsing."""
import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from output_secret_filter import (
    scan_text, scan_decoded_variants, _mask_value, extract_last_tool_output,
    extract_from_tool_response, extract_from_file_path,
)
import base64

passed = 0
failed = 0

def test(desc, findings_count, actual):
    global passed, failed
    if len(actual) == findings_count:
        passed += 1
        print(f"  PASS: {desc} ({len(actual)} findings)")
    else:
        failed += 1
        types = [f[0] for f in actual]
        print(f"  FAIL: {desc} — expected {findings_count}, got {len(actual)}: {types}")

print("=== Pass 1: Raw text scanning ===")

# Cloud API keys
test("OpenAI key", 1, scan_text("sk-proj-abc123def456ghi789jkl012mno345pqr"))
test("Anthropic key", 1, scan_text("key: sk-ant-api03-abcdef123456789012345"))
test("AWS access key", 1, scan_text("AKIAIOSFODNN7EXAMPLE"))
test("Google API key", 1, scan_text("AIzaSyA1234567890abcdefghijklmnopqrstuvw"))

# VCS tokens
test("GitHub PAT", 1, scan_text("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"))
test("GitLab PAT", 1, scan_text("glpat-abcdefghijklmnopqrstu"))

# Messaging
test("Slack token", 1, scan_text("xoxb-123456789012-1234567890"))
test("NPM token", 1, scan_text("npm_abcdefghijklmnopqrstuvwxyz1234567890"))

# Payment
test("Stripe secret key", 1, scan_text("sk_live_" + "abcdefghijklmnopqrstuvwxyz"))

# Generic
test("Bearer token", 1, scan_text("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc123"))
test("Private key header", 1, scan_text("-----BEGIN RSA PRIVATE KEY-----"))
test("Database URI", 1, scan_text("postgres://user:p4ssw0rd@db.example.com:5432/mydb"))
test("Env assignment", 1, scan_text("SECRET_KEY=myverysecretvalue12345abc"))
test("JWT token", 1, scan_text("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N"))

# Safe content (no secrets)
test("Plain text", 0, scan_text("Hello world, this is a normal output"))
test("Short string", 0, scan_text("OK"))
test("Numbers only", 0, scan_text("12345"))
test("File listing", 0, scan_text("total 24\ndrwxr-xr-x  5 user staff 160 Mar  1 10:00 ."))

# Multiple secrets in one output
test("Multiple secrets", 2, scan_text(
    "OPENAI_KEY=sk-proj-abc123def456ghi789jkl012mno345pqr\n"
    "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"
))

print("\n=== Pass 2: Decoded variants ===")

# base64 encoded secret
encoded = base64.b64encode(b"sk-proj-abc123def456ghi789jkl012mno345pqr").decode()
test("base64 encoded OpenAI key", 1, scan_decoded_variants(f"data: {encoded}"))

# Safe base64 (no secret inside)
safe_encoded = base64.b64encode(b"Hello this is just normal text nothing secret").decode()
test("Safe base64 (no secret)", 0, scan_decoded_variants(f"data: {safe_encoded}"))

print("\n=== Masking ===")
masked = _mask_value("sk-proj-abc123def456ghi789jkl012mno345pqr")
assert masked.startswith("sk-p"), f"Mask should start with sk-p, got: {masked}"
assert "***MASKED***" in masked, f"Mask should contain ***MASKED***, got: {masked}"
assert "5pqr" in masked, f"Mask should end with 5pqr, got: {masked}"
passed += 1
print(f"  PASS: Masking format correct: {masked}")

# =========================================================================
# Integration tests: extract_last_tool_output() with actual JSONL format
# =========================================================================
print("\n=== Integration: extract_last_tool_output() ===")


def test_extract(desc, expected_contains, jsonl_lines):
    """Write mock JSONL, call extract_last_tool_output, verify result."""
    global passed, failed
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        for line in jsonl_lines:
            f.write(json.dumps(line) + "\n")
        tmp_path = f.name

    try:
        result = extract_last_tool_output(tmp_path)
        if expected_contains is None:
            if result is None:
                passed += 1
                print(f"  PASS: {desc} (None)")
            else:
                failed += 1
                print(f"  FAIL: {desc} — expected None, got: {result[:60]}")
        elif result is not None and expected_contains in result:
            passed += 1
            print(f"  PASS: {desc} (found '{expected_contains[:40]}')")
        else:
            failed += 1
            preview = result[:60] if result else "None"
            print(f"  FAIL: {desc} — expected '{expected_contains[:40]}', got: {preview}")
    finally:
        os.unlink(tmp_path)


# Test 1: Bash result with toolUseResult.stdout (actual transcript format)
test_extract(
    "Bash stdout via toolUseResult",
    "sk-proj-secret123456789012345678901234",
    [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_test1",
                        "content": "output with sk-proj-secret123456789012345678901234 inside",
                    }
                ],
            },
            "toolUseResult": {
                "stdout": "output with sk-proj-secret123456789012345678901234 inside",
                "stderr": "",
                "interrupted": False,
            },
            "sourceToolAssistantUUID": "uuid-test",
            "timestamp": "2026-03-02T10:00:00Z",
        }
    ],
)

# Test 2: Read result (message.content[].tool_result, no toolUseResult.stdout)
test_extract(
    "Read result via message.content tool_result",
    "AKIAIOSFODNN7EXAMPLE",
    [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_test2",
                        "content": "AWS_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE in config",
                    }
                ],
            },
            "sourceToolAssistantUUID": "uuid-test",
            "timestamp": "2026-03-02T10:01:00Z",
        }
    ],
)

# Test 3: Multiple entries — should return LAST one (reverse search)
test_extract(
    "Returns last tool_result (reverse search)",
    "ghp_SECOND",
    [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_first",
                        "content": "first result with ghp_FIRSTresulttokenabcdefghijklmnop",
                    }
                ],
            },
            "toolUseResult": {
                "stdout": "first result with ghp_FIRSTresulttokenabcdefghijklmnop",
                "stderr": "",
            },
            "sourceToolAssistantUUID": "uuid-test",
            "timestamp": "2026-03-02T10:00:00Z",
        },
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "analyzing..."}]},
            "timestamp": "2026-03-02T10:00:01Z",
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_second",
                        "content": "second result with ghp_SECONDresulttokenxyzabcdefghijk",
                    }
                ],
            },
            "toolUseResult": {
                "stdout": "second result with ghp_SECONDresulttokenxyzabcdefghijk",
                "stderr": "",
            },
            "sourceToolAssistantUUID": "uuid-test",
            "timestamp": "2026-03-02T10:00:02Z",
        },
    ],
)

# Test 4: assistant entry (no tool_result) — should return None
test_extract(
    "Assistant-only entries return None",
    None,
    [
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": "Just text output"},
            "timestamp": "2026-03-02T10:00:00Z",
        }
    ],
)

# Test 5: Empty transcript
test_extract("Empty transcript returns None", None, [])

# Test 6: Non-existent file
result_none = extract_last_tool_output("/tmp/nonexistent_transcript_test_12345.jsonl")
if result_none is None:
    passed += 1
    print("  PASS: Non-existent file returns None")
else:
    failed += 1
    print(f"  FAIL: Non-existent file — expected None, got: {result_none[:60]}")

# Test 7: toolUseResult with stderr only (error output)
test_extract(
    "Bash stderr contains secret",
    "sk-ant-errorkey",
    [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_err",
                        "content": "Error: invalid key sk-ant-errorkey-abcdefghijklmnopqrstuvwxyz",
                        "is_error": True,
                    }
                ],
            },
            "toolUseResult": {
                "stdout": "",
                "stderr": "Error: invalid key sk-ant-errorkey-abcdefghijklmnopqrstuvwxyz",
            },
            "sourceToolAssistantUUID": "uuid-test",
            "timestamp": "2026-03-02T10:00:00Z",
        }
    ],
)

# Test 8: Content as list of blocks (content blocks format)
test_extract(
    "Content blocks format (list of dicts)",
    "postgres://admin:secret@db",
    [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_blocks",
                        "content": [
                            {"type": "text", "text": "DB_URL=postgres://admin:secret@db.host:5432/prod"},
                        ],
                    }
                ],
            },
            "sourceToolAssistantUUID": "uuid-test",
            "timestamp": "2026-03-02T10:00:00Z",
        }
    ],
)

# =========================================================================
# Tier 1 tests: extract_from_tool_response()
# =========================================================================
print("\n=== Tier 1: extract_from_tool_response() ===")


def test_tier1(desc, expected_contains, tool_name, tool_response):
    """Test extract_from_tool_response with given inputs."""
    global passed, failed
    result = extract_from_tool_response(tool_name, tool_response)
    if expected_contains is None:
        if result is None:
            passed += 1
            print(f"  PASS: {desc} (None)")
        else:
            failed += 1
            print(f"  FAIL: {desc} — expected None, got: {result[:60]}")
    elif result is not None and expected_contains in result:
        passed += 1
        print(f"  PASS: {desc} (found '{expected_contains[:40]}')")
    else:
        failed += 1
        preview = result[:60] if result else "None"
        print(f"  FAIL: {desc} — expected '{expected_contains[:40]}', got: {preview}")


# Bash: stdout with secret
test_tier1(
    "Bash stdout extraction",
    "sk-proj-abc123def456ghi789jkl012mno345pqr",
    "Bash",
    {
        "stdout": "export KEY=sk-proj-abc123def456ghi789jkl012mno345pqr",
        "stderr": "",
        "interrupted": False,
    },
)

# Bash: stderr with secret
test_tier1(
    "Bash stderr extraction",
    "AKIAIOSFODNN7EXAMPLE",
    "Bash",
    {
        "stdout": "",
        "stderr": "Error: key AKIAIOSFODNN7EXAMPLE is invalid",
        "interrupted": False,
    },
)

# Bash: both stdout and stderr combined
test_tier1(
    "Bash stdout+stderr combined",
    "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh",
    "Bash",
    {
        "stdout": "token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh",
        "stderr": "warning: token exposed",
        "interrupted": False,
    },
)

# Read: file.content extraction
test_tier1(
    "Read file.content extraction",
    "postgres://admin:secret@db.host:5432/prod",
    "Read",
    {
        "type": "text",
        "file": {
            "filePath": "/tmp/config.env",
            "content": "DB_URL=postgres://admin:secret@db.host:5432/prod\n",
            "numLines": 1,
            "startLine": 1,
            "totalLines": 1,
        },
    },
)

# Empty tool_response ({})
test_tier1("Empty tool_response", None, "Bash", {})

# None tool_response
test_tier1("None tool_response", None, "Bash", None)

# Non-dict tool_response
test_tier1("String tool_response", None, "Bash", "not a dict")

# Bash: no stdout/stderr (e.g., noOutputExpected=True)
test_tier1(
    "Bash no output expected",
    None,
    "Bash",
    {"interrupted": False, "isImage": False, "noOutputExpected": True},
)

# Read: file with empty content
test_tier1(
    "Read empty file content",
    None,
    "Read",
    {"type": "text", "file": {"filePath": "/tmp/empty", "content": ""}},
)

# =========================================================================
# Tier 2 tests: extract_from_file_path()
# =========================================================================
print("\n=== Tier 2: extract_from_file_path() ===")


def test_tier2(desc, expected_contains, tool_input):
    """Test extract_from_file_path with given inputs."""
    global passed, failed
    result = extract_from_file_path(tool_input)
    if expected_contains is None:
        if result is None:
            passed += 1
            print(f"  PASS: {desc} (None)")
        else:
            failed += 1
            print(f"  FAIL: {desc} — expected None, got: {result[:60]}")
    elif result is not None and expected_contains in result:
        passed += 1
        print(f"  PASS: {desc} (found '{expected_contains[:40]}')")
    else:
        failed += 1
        preview = result[:60] if result else "None"
        print(f"  FAIL: {desc} — expected '{expected_contains[:40]}', got: {preview}")


# Real file with secret content
with tempfile.NamedTemporaryFile(
    mode="w", suffix=".env", delete=False, encoding="utf-8"
) as f:
    f.write("API_KEY=sk-ant-api03-abcdef123456789012345\n")
    tmp_env_path = f.name

try:
    test_tier2(
        "Read real file with secret",
        "sk-ant-api03-abcdef123456789012345",
        {"file_path": tmp_env_path},
    )
finally:
    os.unlink(tmp_env_path)

# Non-existent file
test_tier2(
    "Non-existent file returns None",
    None,
    {"file_path": "/tmp/nonexistent_tier2_test_99999.env"},
)

# Missing file_path key
test_tier2("Missing file_path key", None, {})

# Empty file_path value
test_tier2("Empty file_path value", None, {"file_path": ""})

# Directory instead of file
test_tier2("Directory path returns None", None, {"file_path": "/tmp"})

print(f"\n=== Results: {passed} passed, {failed} failed ===")
sys.exit(1 if failed else 0)

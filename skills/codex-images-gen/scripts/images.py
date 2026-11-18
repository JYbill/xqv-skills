#!/usr/bin/env python3
"""Send a single Images API request using a selected Codex provider."""

import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import uuid


IMAGE_MODEL = "gpt-6.2-sol"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", choices=(IMAGE_MODEL,), default=IMAGE_MODEL)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--n", type=int)
    parser.add_argument("--quality", choices=("low", "medium", "high", "auto"))
    parser.add_argument("--size")
    parser.add_argument("--output-format", choices=("png", "jpeg", "webp"))
    args = parser.parse_args()
    if args.n is not None and args.n < 1:
        parser.error("--n must be positive")
    return args


def main():
    args = arguments()
    config_dir = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    try:
        with (config_dir / "config.toml").open("rb") as file:
            config = tomllib.load(file)
        provider = config["model_providers"][args.provider]
        base_url = provider["base_url"].rstrip("/")
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError):
        fail("Cannot read the selected provider and base_url from config.toml.")

    parts = urllib.parse.urlsplit(base_url)
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.username or parts.password or parts.query or parts.fragment:
        fail("Provider base_url must be an HTTP(S) URL without credentials, query, or fragment.")
    if not parts.path.endswith("/v1"):
        base_url += "/v1"

    headers = dict(provider.get("http_headers", {}))
    for header, env_name in provider.get("env_http_headers", {}).items():
        if env_name not in os.environ:
            fail("A configured provider header environment variable is missing.")
        headers[header] = os.environ[env_name]
    env_key = provider.get("env_key")
    token = provider.get("experimental_bearer_token")
    if env_key:
        if env_key not in os.environ:
            fail("The configured provider key environment variable is missing.")
        if token:
            fail("Multiple provider bearer credentials configured; resolve the effective authentication first.")
        token = os.environ[env_key]
    if token:
        if any(key.lower() == "authorization" for key in headers):
            fail("Multiple provider authorization methods configured; resolve the effective authentication first.")
        headers["Authorization"] = "Bearer " + token
    if not token and not headers:
        fail("No supported provider credentials found; verify the effective authentication.")

    fields = {"model": args.model, "prompt": args.prompt}
    for name in ("n", "quality", "size", "output_format"):
        value = getattr(args, name)
        if value is not None:
            fields[name] = value

    if args.image:
        try:
            image = args.image.read_bytes()
        except OSError:
            fail("Cannot read the input image.")
        boundary = "codex-images-" + uuid.uuid4().hex
        chunks = []
        for name, value in fields.items():
            chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        mime = mimetypes.guess_type(args.image.name)[0] or "application/octet-stream"
        extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime, "")
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="input{extension}"\r\nContent-Type: {mime}\r\n\r\n'.encode() + image + b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        body = b"".join(chunks)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        endpoint = "/images/edits"
    else:
        body = json.dumps(fields, ensure_ascii=False).encode()
        headers["Content-Type"] = "application/json"
        endpoint = "/images/generations"

    query = urllib.parse.urlencode(provider.get("query_params", {}))
    url = base_url + endpoint + ("?" + query if query else "")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=600) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        fail(f"Provider returned HTTP {error.code}; response body withheld to protect credentials.")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        fail("Image request failed or returned invalid JSON; provider details withheld.")

    items = payload.get("data", []) if isinstance(payload, dict) else []
    if not isinstance(items, list) or not items:
        fail("Provider returned no image data.")
    images = []
    for item in items:
        try:
            data = base64.b64decode(item["b64_json"], validate=True)
        except (KeyError, TypeError, ValueError):
            fail("Provider did not return valid base64 image data; URL-only responses require provider-specific handling.")
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            extension = "png"
        elif data.startswith(b"\xff\xd8\xff"):
            extension = "jpg"
        elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            extension = "webp"
        else:
            fail("Provider returned an unsupported image format.")
        images.append((data, extension))

    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        prefix = uuid.uuid4().hex[:12]
        paths = []
        for index, (data, extension) in enumerate(images, 1):
            path = args.output_dir / f"image-{prefix}-{index}.{extension}"
            with path.open("xb") as file:
                file.write(data)
            paths.append(str(path.resolve()))
    except OSError:
        fail("Cannot save image output.")
    print(json.dumps({"requested": args.n or 1, "returned": len(paths), "files": paths}, ensure_ascii=False))


if __name__ == "__main__":
    main()

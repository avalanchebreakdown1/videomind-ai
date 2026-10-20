"""Local exact-request replay, retaining raw responses and provenance."""
import hashlib
import json
from pathlib import Path
from .verification_service import sha256
from .document_service import write_json


def request_key(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


class SavedModelCalls:
    def __init__(self, directory, source_hashes, prepared, evidence, identity):
        self.directory = Path(directory).resolve()
        self.calls, self.hashes, self.used = {}, {}, []
        self.loaded_bytes = 0

        def read(path):
            if not path.is_file() or path.stat().st_size > 20_000_000:
                raise ValueError("Missing or oversized saved model artifact")
            self.loaded_bytes += path.stat().st_size
            if self.loaded_bytes > 128_000_000:
                raise ValueError("Saved model artifacts exceed the 128 MB replay budget")
            self.hashes[str(path.relative_to(self.directory))] = sha256(path)
            return json.loads(path.read_text())

        manifest = read(self.directory / "manifest.json")
        if manifest.get("kind") != "educational_document" or manifest.get("source_artifacts_sha256") != source_hashes:
            raise ValueError("Saved model calls do not match current source hashes")
        if manifest.get("ollama", {}).get("digest") != identity.get("digest") or not identity.get("digest"):
            raise ValueError("Saved model calls require the same recorded model digest")
        if read(self.directory / "prepared_source.json") != prepared or read(self.directory / "evidence.json")["passages"] != evidence:
            raise ValueError("Saved model calls do not match current source passages")
        paths = sorted((self.directory / "model_calls").glob("*.request.json"))
        if len(paths) > 1200:
            raise ValueError("Too many saved model calls")
        for path in paths:
            response_path = path.with_name(path.name.replace(".request.json", ".response.json"))
            if not response_path.is_file():
                continue
            request, response = read(path), read(response_path)
            if response.get("done") is True and response.get("done_reason") != "length":
                self.calls.setdefault(request_key(request), []).append((str(response_path.relative_to(self.directory)), response))

    def take(self, request, call_number, output):
        candidates = self.calls.get(request_key(request), [])
        if not candidates:
            return None
        path, response = candidates.pop(0)
        self.used.append({"new_model_call": call_number, "original_response": path})
        write_json(output / "model_reuse.json", {"directory": str(self.directory), "used_calls": self.used,
                   "artifacts_sha256": self.hashes, "policy": "exact_request_and_model_digest"})
        return response

    def unchanged(self):
        return all((self.directory / name).is_file() and sha256(self.directory / name) == digest
                   for name, digest in self.hashes.items())

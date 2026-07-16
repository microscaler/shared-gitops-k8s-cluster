"""Restore the latest MinIO PostgreSQL backup into a disposable container."""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import time


MC_IMAGE = "minio/mc:RELEASE.2025-08-13T08-35-41Z"
POSTGRES_IMAGE = "postgres:17-alpine"


def run(*args: str, **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, text=True, **kwargs)


def kubectl_json(kubeconfig: Path, *args: str) -> dict[str, object]:
    result = run("kubectl", "--kubeconfig", str(kubeconfig), *args, capture_output=True)
    return json.loads(result.stdout)


def minio_environment(kubeconfig: Path, namespace: str) -> dict[str, str]:
    secret = kubectl_json(
        kubeconfig,
        "--namespace",
        namespace,
        "get",
        "secret",
        "minio-credentials",
        "-o",
        "json",
    )
    data = secret["data"]
    assert isinstance(data, dict)
    environment = os.environ.copy()
    environment["MINIO_USER"] = base64.b64decode(data["MINIO_ROOT_USER"]).decode()
    environment["MINIO_PASSWORD"] = base64.b64decode(
        data["MINIO_ROOT_PASSWORD"]
    ).decode()
    return environment


def latest_backup(environment: dict[str, str], endpoint: str, bucket: str) -> str:
    command = (
        f'mc alias set backup "{endpoint}" "$MINIO_USER" "$MINIO_PASSWORD" >/dev/null && '
        f'mc ls --json "backup/{bucket}/"'
    )
    result = run(
        "docker",
        "run",
        "--rm",
        "--network",
        "host",
        "--entrypoint",
        "/bin/sh",
        "-e",
        "MINIO_USER",
        "-e",
        "MINIO_PASSWORD",
        MC_IMAGE,
        "-c",
        command,
        env=environment,
        capture_output=True,
    )
    objects = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    files = [item for item in objects if item.get("type") == "file"]
    if not files:
        raise RuntimeError(f"no backup objects found in {bucket}")
    return str(max(files, key=lambda item: item["lastModified"])["key"])


def download_backup(
    environment: dict[str, str], endpoint: str, bucket: str, key: str, target: Path
) -> None:
    environment = environment | {"BACKUP_KEY": key}
    command = (
        f'mc alias set backup "{endpoint}" "$MINIO_USER" "$MINIO_PASSWORD" >/dev/null && '
        f'mc cp "backup/{bucket}/$BACKUP_KEY" /download/backup.sql.gz >/dev/null'
    )
    run(
        "docker",
        "run",
        "--rm",
        "--network",
        "host",
        "--entrypoint",
        "/bin/sh",
        "-e",
        "MINIO_USER",
        "-e",
        "MINIO_PASSWORD",
        "-e",
        "BACKUP_KEY",
        "-v",
        f"{target.parent}:/download",
        MC_IMAGE,
        "-c",
        command,
        env=environment,
    )


def verify_dump_contract(path: Path, database: str) -> None:
    found_database = found_connection = False
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            found_database |= f"CREATE DATABASE {database} " in line
            found_connection |= line.strip() == rf"\connect {database}"
    if not (found_database and found_connection):
        raise RuntimeError(
            f"backup does not contain a complete {database} database section"
        )


def extract_database_restore(path: Path, database: str, target: Path) -> None:
    """Keep global objects and only the requested database from a cluster dump."""
    marker = f'-- Database "{database}" dump'
    database_marker = re.compile(r'^-- Database ".+" dump$')
    in_database_sections = False
    in_target = False
    found_target = False

    with (
        gzip.open(path, "rt", encoding="utf-8", errors="replace") as source,
        target.open("w", encoding="utf-8") as output,
    ):
        for line in source:
            stripped = line.rstrip("\n")
            if database_marker.fullmatch(stripped):
                if in_target:
                    break
                in_database_sections = True
                in_target = stripped == marker
                found_target |= in_target
            if not in_database_sections or in_target:
                output.write(line)

    if not found_target:
        raise RuntimeError(f"backup does not contain a {database} database dump")


def restore_and_verify(path: Path, database: str) -> int:
    name = f"postgres-restore-drill-{os.getpid()}"
    password = secrets.token_urlsafe(24)
    restore_user = "restore_admin"
    run(
        "docker",
        "run",
        "--detach",
        "--rm",
        "--name",
        name,
        "-e",
        f"POSTGRES_PASSWORD={password}",
        "-e",
        f"POSTGRES_USER={restore_user}",
        POSTGRES_IMAGE,
        capture_output=True,
    )
    try:
        for _ in range(60):
            ready = subprocess.run(
                ["docker", "exec", name, "pg_isready", "-U", restore_user],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")

        with (
            path.open("rb") as source,
            tempfile.TemporaryFile(mode="w+b") as restore_log,
        ):
            process = subprocess.Popen(
                [
                    "docker",
                    "exec",
                    "-i",
                    name,
                    "psql",
                    "-U",
                    restore_user,
                    "-d",
                    restore_user,
                    "-v",
                    "ON_ERROR_STOP=1",
                ],
                stdin=subprocess.PIPE,
                stdout=restore_log,
                stderr=restore_log,
            )
            assert process.stdin is not None
            shutil.copyfileobj(source, process.stdin)
            process.stdin.close()
            if process.wait() != 0:
                restore_log.seek(0)
                errors = [
                    line.decode("utf-8", errors="replace").strip()
                    for line in restore_log
                    if b"ERROR:" in line or b"FATAL:" in line
                ]
                summary = "; ".join(errors[-5:]) or "no PostgreSQL error line captured"
                raise RuntimeError(f"restore failed: {summary}")

        result = run(
            "docker",
            "exec",
            name,
            "psql",
            "-U",
            restore_user,
            "-d",
            database,
            "-Atqc",
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'rerp'",
            capture_output=True,
        )
        table_count = int(result.stdout.strip())
        if table_count < 1:
            raise RuntimeError(
                f"restored {database} database contains no rerp schema tables"
            )
        return table_count
    finally:
        subprocess.run(
            ["docker", "rm", "--force", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kubeconfig", type=Path, required=True)
    parser.add_argument("--namespace", default="data")
    parser.add_argument("--endpoint", default="http://10.177.76.226:9000")
    parser.add_argument("--bucket", default="postgres-backups")
    parser.add_argument("--database", default="rerp")
    args = parser.parse_args()

    environment = minio_environment(args.kubeconfig, args.namespace)
    key = latest_backup(environment, args.endpoint, args.bucket)
    with tempfile.TemporaryDirectory(prefix="postgres-restore-drill-") as directory:
        backup = Path(directory) / "backup.sql.gz"
        restore_sql = Path(directory) / "restore.sql"
        download_backup(environment, args.endpoint, args.bucket, key, backup)
        verify_dump_contract(backup, args.database)
        extract_database_restore(backup, args.database, restore_sql)
        table_count = restore_and_verify(restore_sql, args.database)
    print(
        f"restore drill passed: object={key} database={args.database} tables={table_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

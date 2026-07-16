"""Validate shared-gitops inventory YAML files."""

from __future__ import annotations

import re
import sys
from pathlib import Path, PurePosixPath

import yaml

ROOT = Path(__file__).resolve().parents[3]
INVENTORY = ROOT / "gitops" / "inventory"


def _load(name: str) -> dict | list:
    path = INVENTORY / name
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def validate_clusters() -> list[str]:
    errors: list[str] = []
    data = _load("clusters.yaml")
    clusters = data.get("clusters") or []
    ids: set[str] = set()
    for c in clusters:
        cid = c.get("id")
        if not cid:
            errors.append("cluster missing id")
            continue
        if cid in ids:
            errors.append(f"duplicate cluster id: {cid}")
        ids.add(cid)
        if "git" not in c or "url" not in c["git"]:
            errors.append(f"cluster {cid}: missing git.url")
        status = c.get("status")
        if status not in {"active", "stub", "disabled"}:
            errors.append(f"cluster {cid}: invalid status {status!r}")
    for required in ("dev", "staging", "prod"):
        if required not in ids:
            errors.append(f"missing required cluster id: {required}")
    return errors


def validate_stacks() -> list[str]:
    errors: list[str] = []
    data = _load("platform-stacks.yaml")
    stacks = data.get("stacks") or []
    names: set[str] = set()
    for s in stacks:
        name = s.get("name")
        path = s.get("path")
        if not name or not path:
            errors.append(f"stack missing name/path: {s!r}")
            continue
        if name in names:
            errors.append(f"duplicate stack name: {name}")
        names.add(name)
        rel = ROOT / path.lstrip("./")
        if (
            not (rel / "kustomization.yaml").exists()
            and not (rel / "kustomization.yml").exists()
        ):
            errors.append(f"stack {name}: no kustomization.yaml under {path}")
        profile = s.get("profile")
        if profile is not None and not isinstance(profile, str):
            errors.append(f"stack {name}: profile must be a string")
    all_names = {s.get("name") for s in stacks}
    for s in stacks:
        for dep in s.get("depends_on") or []:
            if dep not in all_names:
                errors.append(f"stack {s.get('name')}: unknown depends_on {dep}")

    # Generated per-cluster stacks.yaml must match catalog ∩ enablement dirs
    sys.path.insert(0, str(ROOT / "tooling" / "src"))
    from shared_gitops.render_cluster_stacks import write_stacks

    for cluster_dir in (ROOT / "gitops" / "clusters").iterdir():
        if not cluster_dir.is_dir():
            continue
        if not (cluster_dir / "inventory" / "stacks").is_dir():
            continue
        cid = cluster_dir.name
        try:
            write_stacks(cid, cid, check=True)
        except SystemExit as exc:
            errors.append(str(exc))
    return errors


def validate_metallb() -> list[str]:
    errors: list[str] = []
    data = _load("metallb-services.yaml")
    services = data.get("services") or []
    ips: set[str] = set()
    lan_ports: set[int] = set()
    for svc in services:
        name = svc.get("name")
        lb_ip = svc.get("lb_ip")
        if not name or not lb_ip:
            errors.append(f"metallb service missing name/lb_ip: {svc!r}")
            continue
        if lb_ip in ips:
            errors.append(f"duplicate lb_ip: {lb_ip} ({name})")
        ips.add(lb_ip)
        claimed: set[int] = set()
        lan = svc.get("lan_port")
        if lan is not None:
            claimed.add(lan)
        for extra in svc.get("lan_ports") or []:
            ep = extra.get("lan_port")
            if ep is not None:
                claimed.add(ep)
        for port in claimed:
            if port in lan_ports:
                errors.append(f"duplicate lan_port: {port} ({name})")
            lan_ports.add(port)
        if not svc.get("namespace"):
            errors.append(f"service {name}: missing namespace")
        if not svc.get("ports"):
            errors.append(f"service {name}: missing ports")
    return errors


def validate_apps() -> list[str]:
    errors: list[str] = []
    data = _load("apps.yaml")
    apps = data.get("apps") or []
    ports: set[int] = set()
    ids: set[str] = set()
    for app in apps:
        aid = app.get("id")
        port = app.get("port")
        if not aid or port is None:
            errors.append(f"app missing id/port: {app!r}")
            continue
        if aid in ids:
            errors.append(f"duplicate app id: {aid}")
        ids.add(aid)
        if port in ports:
            errors.append(f"duplicate app port: {port} ({aid})")
        ports.add(port)
    return errors


def validate_product_components() -> list[str]:
    errors: list[str] = []
    data = _load("product-components.yaml")
    environment = data.get("environment")
    sources = data.get("sources") or []
    components = data.get("components") or []
    images = data.get("images") or []
    automations = data.get("automations") or []
    app_ids = {app.get("id") for app in (_load("apps.yaml").get("apps") or [])}
    dns_label = re.compile(r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$")

    if not environment or not dns_label.fullmatch(str(environment)):
        errors.append(f"product components: invalid environment {environment!r}")

    source_names: set[str] = set()
    source_urls: set[str] = set()
    for source in sources:
        name = source.get("name")
        url = source.get("url")
        branch = source.get("branch")
        if not name or not url or not branch:
            errors.append(f"product source missing name/url/branch: {source!r}")
            continue
        if not dns_label.fullmatch(name):
            errors.append(f"product source has invalid DNS label: {name!r}")
        if name in source_names:
            errors.append(f"duplicate product source name: {name}")
        source_names.add(name)
        if url in source_urls:
            errors.append(f"duplicate product source URL: {url}")
        source_urls.add(url)
        if not (url.startswith("https://") or url.startswith("ssh://")):
            errors.append(f"product source {name}: unsupported URL {url!r}")
        if url.startswith("ssh://") and not source.get("secret_ref"):
            errors.append(f"product source {name}: SSH URL requires secret_ref")

    component_names: set[str] = set()
    component_paths: set[tuple[str, str]] = set()
    for component in components:
        name = component.get("name")
        source = component.get("source")
        product = component.get("product")
        suite = component.get("suite")
        path = component.get("path")
        dependency = component.get("depends_on")
        wait = component.get("wait")
        force = component.get("force")
        if not all((name, source, product, suite, path, dependency)):
            errors.append(
                "product component missing "
                f"name/source/product/suite/path/depends_on: {component!r}"
            )
            continue
        if not dns_label.fullmatch(name):
            errors.append(f"product component has invalid DNS label: {name!r}")
        if name in component_names:
            errors.append(f"duplicate product component name: {name}")
        component_names.add(name)
        if source not in source_names:
            errors.append(f"product component {name}: unknown source {source}")
        if product not in app_ids:
            errors.append(f"product component {name}: unknown product app {product}")

        normalized = PurePosixPath(path.removeprefix("./"))
        expected_prefix = PurePosixPath(
            "deployment-configuration", "profiles", str(environment), product, suite
        )
        if ".." in normalized.parts or not (
            normalized == expected_prefix or expected_prefix in normalized.parents
        ):
            errors.append(
                f"product component {name}: path must be ./{expected_prefix} "
                f"or a child, got {path!r}"
            )
        if not isinstance(force, bool):
            errors.append(f"product component {name}: force must be a boolean")
        if not isinstance(wait, bool):
            errors.append(f"product component {name}: wait must be a boolean")
        source_path = (source, str(normalized))
        if source_path in component_paths:
            errors.append(f"duplicate product component source/path: {source_path}")
        component_paths.add(source_path)

    known_dependencies = component_names | {"stack-namespaces"}
    for component in components:
        dependency = component.get("depends_on")
        if dependency and dependency not in known_dependencies:
            errors.append(
                f"product component {component.get('name')}: unknown depends_on {dependency}"
            )

    image_names: set[str] = set()
    image_repositories: set[str] = set()
    for image in images:
        name = image.get("name")
        repository = image.get("image")
        if not name or not repository:
            errors.append(f"product image missing name/image: {image!r}")
            continue
        if not dns_label.fullmatch(name):
            errors.append(f"product image has invalid DNS label: {name!r}")
        if name in image_names:
            errors.append(f"duplicate product image name: {name}")
        image_names.add(name)
        if repository in image_repositories:
            errors.append(f"duplicate product image repository: {repository}")
        image_repositories.add(repository)
        if ":" not in repository.split("/")[0]:
            errors.append(
                f"product image {name}: expected an explicit registry port in {repository!r}"
            )

    automation_names: set[str] = set()
    for automation in automations:
        name = automation.get("name")
        source = automation.get("source")
        product = automation.get("product")
        branch = automation.get("branch")
        path = automation.get("path")
        author_name = automation.get("author_name")
        author_email = automation.get("author_email")
        if not all((name, source, product, branch, path, author_name, author_email)):
            errors.append(
                "product automation missing "
                "name/source/product/branch/path/author_name/author_email: "
                f"{automation!r}"
            )
            continue
        if not dns_label.fullmatch(name):
            errors.append(f"product automation has invalid DNS label: {name!r}")
        if name in automation_names:
            errors.append(f"duplicate product automation name: {name}")
        automation_names.add(name)
        if source not in source_names:
            errors.append(f"product automation {name}: unknown source {source}")
        if product not in app_ids:
            errors.append(f"product automation {name}: unknown product app {product}")
        normalized = PurePosixPath(path.removeprefix("./"))
        expected_prefix = PurePosixPath(
            "deployment-configuration", "profiles", str(environment), product
        )
        if ".." in normalized.parts or not (
            normalized == expected_prefix or expected_prefix in normalized.parents
        ):
            errors.append(
                f"product automation {name}: path must be ./{expected_prefix} "
                f"or a child, got {path!r}"
            )

    return errors


def main() -> int:
    errors = (
        validate_clusters()
        + validate_stacks()
        + validate_metallb()
        + validate_apps()
        + validate_product_components()
    )
    if errors:
        print("inventory validation FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("inventory validation OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

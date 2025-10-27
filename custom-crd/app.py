import os
import re
import kopf
from kubernetes import client, config


ANNOTATION_KEY = os.getenv("NO_LATEST_ANNOTATION", "nolatest.dev/warning")


def is_latest_image(image: str) -> bool:
    # digest-pinned images are fine
    if "@" in image:
        return False
    # find last path segment and check tag
    segment = image.rsplit("/", 1)[-1]
    if ":" not in segment:
        return True  # implicit latest
    tag = segment.rsplit(":", 1)[-1]
    return tag == "latest"


def detect_offenders(pod_body: dict) -> list[str]:
    offenders = []
    for c in pod_body.get("spec", {}).get("initContainers", []) or []:
        if is_latest_image(c.get("image", "")):
            offenders.append(c.get("name", "init"))
    for c in pod_body.get("spec", {}).get("containers", []) or []:
        if is_latest_image(c.get("image", "")):
            offenders.append(c.get("name", "container"))
    return offenders


def ensure_kube_config():
    # Try in-cluster first, fall back to local for dev
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()


@kopf.on.startup()
def _startup(logger, **_):
    ensure_kube_config()
    logger.info("No-Latest Image Checker controller starting up")


@kopf.on.event('', 'v1', 'pods')
def pod_event(event, body, logger, **_):
    # Only handle ADDED/MODIFIED
    etype = event.get('type')
    if etype not in {"ADDED", "MODIFIED"}:
        return

    ns = body.get('metadata', {}).get('namespace')
    name = body.get('metadata', {}).get('name')
    if not ns or not name:
        return

    # Skip terminating pods
    if body.get('metadata', {}).get('deletionTimestamp'):
        return

    offenders = detect_offenders(body)
    if not offenders:
        return

    anno_val = f"containers using :latest: {offenders}"
    annotations = (body.get('metadata', {}).get('annotations') or {})
    if annotations.get(ANNOTATION_KEY) == anno_val:
        return  # already annotated with same value

    v1 = client.CoreV1Api()
    patch = {
        "metadata": {
            "annotations": {
                ANNOTATION_KEY: anno_val,
            }
        }
    }
    try:
        v1.patch_namespaced_pod(name=name, namespace=ns, body=patch)
        logger.info(f"Annotated Pod {ns}/{name}: {anno_val}")
    except Exception as e:
        logger.exception(f"Failed to patch pod {ns}/{name}: {e}")

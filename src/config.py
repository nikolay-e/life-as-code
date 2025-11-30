import os

APP_VERSION = os.getenv("APP_VERSION", "dev")
BUILD_DATE = os.getenv("BUILD_DATE", "unknown")
VCS_REF = os.getenv("VCS_REF", "unknown")


def get_commit_short() -> str:
    return VCS_REF[:7] if VCS_REF != "unknown" else "unknown"

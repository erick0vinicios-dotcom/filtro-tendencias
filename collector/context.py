from dataclasses import dataclass, field
from datetime import datetime, timezone


def iso(moment):
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def from_unix(seconds):
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


@dataclass(frozen=True)
class Context:
    now: datetime
    shared_hosts: dict = field(default_factory=dict)

    @classmethod
    def create(cls, config):
        return cls(
            now=datetime.now(timezone.utc),
            shared_hosts=config.get("unify", {}).get("shared_hosts", {}),
        )

    @property
    def now_iso(self):
        return iso(self.now)

    def hours_since(self, moment):
        return max((self.now - moment).total_seconds() / 3600, 0.0)

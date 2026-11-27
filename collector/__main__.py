import argparse
import json
import logging
import os
import sys
import tomllib
from pathlib import Path

from collector import ranking
from collector.context import Context
from collector.errors import SourceSkipped
from collector.logs import setup_logging
from collector.sources import SOURCES

log = logging.getLogger("runner")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m collector")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--only", nargs="+", choices=sorted(SOURCES), help="roda só as fontes indicadas")
    args = parser.parse_args(argv)

    load_env_file(Path(".env"))
    config = tomllib.loads(Path(args.config).read_text(encoding="utf-8"))
    general = config.get("general", {})
    setup_logging(general.get("log_level", "INFO"))
    ctx = Context.create(config)
    raw_dir = Path(general.get("raw_dir", "data/raw"))
    raw_dir.mkdir(parents=True, exist_ok=True)

    data_dir = Path(general.get("data_dir", "data"))

    log.info("coleta iniciada em %s", ctx.now_iso)
    report, items_by_source = run_sources(config.get("sources", {}), args.only, ctx, raw_dir)
    write_json(raw_dir / "_run.json", {"started_at": ctx.now_iso, "sources": report})

    attempted = [status for status in report.values() if status["status"] in ("ok", "error")]
    failed = [status for status in attempted if status["status"] == "error"]
    skipped = [name for name, status in report.items() if status["status"] == "skipped"]
    log.info("coleta concluída: %d ok, %d com erro, %d puladas", len(attempted) - len(failed), len(failed), len(skipped))

    if not items_by_source:
        log.error("nenhuma fonte trouxe dados; latest.json e histórico mantidos como estavam")
        return 1
    if args.only:
        log.info("rodada parcial (--only); ranking não foi regerado")
        return 0
    latest = ranking.build(items_by_source, report, config, ctx, data_dir / "history")
    ranking.write_outputs(latest, ctx, data_dir)
    return 0


def load_env_file(path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        name, found, value = line.partition("=")
        if found and name.strip() and not name.lstrip().startswith("#"):
            os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


def run_sources(sources_config, only, ctx, raw_dir):
    report = {}
    items_by_source = {}
    for name, module in SOURCES.items():
        settings = sources_config.get(name, {})
        if only and name not in only:
            continue
        if not settings.get("enabled", False):
            log.info("fonte %s desligada na configuração", name)
            report[name] = {"status": "disabled", "count": 0}
            continue
        log.info("fonte %s: iniciando", name)
        try:
            items = module.collect(settings, ctx)
        except SourceSkipped as reason:
            log.warning("fonte %s pulada: %s", name, reason)
            report[name] = {"status": "skipped", "count": 0, "error": str(reason)}
            continue
        except Exception as error:
            log.exception("fonte %s falhou; seguindo para as próximas", name)
            report[name] = {"status": "error", "count": 0, "error": str(error)}
            continue
        write_json(raw_dir / f"{name}.json", {"source": name, "collected_at": ctx.now_iso, "count": len(items), "items": items})
        log.info("fonte %s: %d itens salvos em %s", name, len(items), raw_dir / f"{name}.json")
        report[name] = {"status": "ok", "count": len(items)}
        items_by_source[name] = items
    return report, items_by_source


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())

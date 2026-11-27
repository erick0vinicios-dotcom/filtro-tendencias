import argparse
import json
import logging
import sys
import tomllib
from pathlib import Path

from collector.context import Context
from collector.logs import setup_logging
from collector.sources import SOURCES

log = logging.getLogger("runner")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m collector")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--only", nargs="+", choices=sorted(SOURCES), help="roda só as fontes indicadas")
    args = parser.parse_args(argv)

    config = tomllib.loads(Path(args.config).read_text(encoding="utf-8"))
    general = config.get("general", {})
    setup_logging(general.get("log_level", "INFO"))
    ctx = Context.create(config)
    raw_dir = Path(general.get("raw_dir", "data/raw"))
    raw_dir.mkdir(parents=True, exist_ok=True)

    log.info("coleta iniciada em %s", ctx.now_iso)
    report = run_sources(config.get("sources", {}), args.only, ctx, raw_dir)
    write_json(raw_dir / "_run.json", {"started_at": ctx.now_iso, "sources": report})

    attempted = [status for status in report.values() if status["status"] != "disabled"]
    failed = [status for status in attempted if status["status"] == "error"]
    log.info("coleta concluída: %d fontes ok, %d com erro", len(attempted) - len(failed), len(failed))
    return 1 if attempted and len(failed) == len(attempted) else 0


def run_sources(sources_config, only, ctx, raw_dir):
    report = {}
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
        except Exception as error:
            log.exception("fonte %s falhou; seguindo para as próximas", name)
            report[name] = {"status": "error", "count": 0, "error": str(error)}
            continue
        write_json(raw_dir / f"{name}.json", {"source": name, "collected_at": ctx.now_iso, "count": len(items), "items": items})
        log.info("fonte %s: %d itens salvos em %s", name, len(items), raw_dir / f"{name}.json")
        report[name] = {"status": "ok", "count": len(items)}
    return report


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())

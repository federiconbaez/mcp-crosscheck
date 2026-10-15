"""Run the battery over (targets x transports), in parallel across targets."""
import concurrent.futures
import time

from . import battery, launch, wire


def run_target(target, family_dir, transports, only=None, tmp_root=None):
    """-> {check_id: {transport: {"status": pass|fail|skip|error, "detail": str, "ms": int}}}"""
    out = {}
    for transport in transports:
        dep = launch.Deployment(target, family_dir, tmp_root=tmp_root, label=transport)
        ctx = battery.Ctx(dep, transport)
        try:
            for chk in battery.CHECKS:
                if transport not in chk["transports"] or (only and chk["id"] not in only):
                    continue
                t0 = time.time()
                try:
                    chk["fn"](ctx)
                    status, detail = "pass", ""
                except battery.Skip as exc:
                    status, detail = "skip", str(exc)
                except battery.Fail as exc:
                    status, detail = "fail", str(exc)[:500]
                except wire.WireError as exc:
                    status, detail = "error", "WireError: %s" % str(exc)[:400]
                except Exception as exc:  # noqa: BLE001 - a crashing check is a result, not a crash of the run
                    status, detail = "error", "%s: %s" % (type(exc).__name__, str(exc)[:400])
                finally:
                    ctx.close_all()
                out.setdefault(chk["id"], {})[transport] = {"status": status, "detail": detail, "ms": int((time.time() - t0) * 1000)}
        finally:
            dep.close()
    return out


def run_battery(targets, family_dir, transports=("stdio", "http"), only=None, jobs=4, tmp_root=None):
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = {ex.submit(run_target, t, family_dir, transports, only, tmp_root): t for t in targets}
        for fut in concurrent.futures.as_completed(futs):
            results[futs[fut].name] = fut.result()
    return results

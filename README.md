# mcp-crosscheck

> **ES:** Validación cruzada de caja negra de los cuatro servidores de mcp-family: los lanza como procesos reales (stdio y HTTP), emite tokens con sus propias CLIs y habla JSON-RPC 2.0 crudo. Python 3 stdlib, sin red.
> Probar: `python3 -m unittest discover -s tests -t .`
>
> **EN:** Black-box cross-validation of the four mcp-family servers: launches them as real processes (stdio and HTTP), mints tokens with their own CLIs and speaks raw JSON-RPC 2.0. Python 3 stdlib, no network.
> Test: `python3 -m unittest discover -s tests -t .`
>
> **Estado / Status:** 50 tests en verde en la box (Python 3.13.5, Linux 6.12, x86_64) el 2026-10-22; **no auditado** por un tercero / **not independently audited**. Implementación didáctica, no un IdP de producción / teaching implementation, not a production IdP. Licencia / License: Apache-2.0.


Cross-validation of the four MCP servers of the *mcp-family* (`mcp-base`, `mcp-memory-first`, `mcp-auth-hardened`,
`mcp-resource-heavy`). Pure Python 3 standard library (built and tested with 3.13.5), no network, no third-party imports.
It treats the servers as **black boxes**: it never imports their code, it launches them as real processes (stdio and HTTP),
mints tokens with their own CLIs, and talks raw JSON-RPC 2.0 to them.

Three independent pieces of evidence come out of one command:

| Part | What it does | Where |
|---|---|---|
| 1. Shared black-box battery | 57 freshly written checks (lifecycle, JSON-RPC edge cases, tools, resources, prompts, capability honesty, auth, HTTP, stdio, persistence, concurrency) run against **every** server over **every** transport | `mcpcross/battery.py` |
| 2. Differential checks | 65 identical malformed/edge inputs sent to all four servers; they must answer with the **same** JSON-RPC error code (and HTTP status); stdio and HTTP must agree on JSON-RPC semantics; for each capability, "advertised" must equal "the method really works" | `mcpcross/differential.py` |
| 3. Cross-token matrix | a token minted by server S is presented to server D, for all 16 ordered pairs, on both transports, in five layers | `mcpcross/crosstoken.py` |

The result is written to `evidence/crosscheck.json` (machine readable) and `evidence/crosscheck.md` (matrix report).

## Quick start

```bash
# layout: the five projects are siblings
#   mcp-base/  mcp-memory-first/  mcp-auth-hardened/  mcp-resource-heavy/  mcp-crosscheck/
cd mcp-crosscheck
python3 -m unittest discover            # unit + integration tests (integration tests skip if siblings are missing)
python3 -m mcpcross run                 # full run, writes evidence/crosscheck.{json,md}, exit 0 = PASS, 1 = FAIL, 2 = usage error
python3 -m mcpcross list                # the 57 battery checks
./demo.sh                               # narrated demo incl. two negative controls (deliberately broken copies must FAIL)
python3 tools/mutation_sanity.py        # inject 10 bugs into temp copies of the servers; crosscheck must catch each
python3 tools/check_stdlib_only.py      # AST-based stdlib-only check
python3 tools/make_manifest.py --check  # file integrity against MANIFEST.sha256
```

Useful options of `run`: `--family-dir DIR` (default: parent of this repo), `--targets base,memory,auth,resources`,
`--transports stdio,http`, `--only XC-RPC-01,...`, `--skip battery,differential,crosstoken`, `--out DIR`, `--no-write`, `--jobs N`.

## Cross-token design (what exactly is tested)

Every member verifies HS256 tokens with `MCP_FORGE_SECRET`, issuer and audience. `mcp-auth-hardened` additionally requires a `kid`
header (unless `serve --allow-kidless`). The layers isolate **one reason** for refusal at a time:

| Layer | Configuration | Expected |
|---|---|---|
| L1 | each server has its **own** random secret, one **shared** audience, `mcp-auth-hardened` with `--allow-kidless` | only S == D accepted; every other pair rejected for the signature (nothing else can be the reason) |
| L2 | one shared secret and issuer, each server keeps its **own** audience | only S == D accepted (wrong audience; auth-hardened also says "missing kid" for kid-less foreign tokens) |
| L2b | like L2, `mcp-auth-hardened` started with `--allow-kidless` | only S == D accepted, and the reason is now purely "wrong audience" |
| L3 | shared secret + issuer + audience, `mcp-auth-hardened` with `--allow-kidless` | **all 16 pairs accepted**, and the accepted token is *usable* (`tools/list` returns tools) |
| L3s | like L3 but `mcp-auth-hardened` **strict** (no `--allow-kidless`) | all pairs accepted **except** foreign tokens presented to `mcp-auth-hardened`, which must be refused for the missing `kid` |

Each rejection is also checked for its *reason* (L1: signature, L2b: audience, L3s: kid), so a bug in one control cannot hide behind another. L3 is the positive control that proves the rejections in L1/L2/L2b are caused by the configuration under test and not by a harness bug.

## What a PASS means, and what it does not

PASS means: on this machine, with this Python, the battery, the differential cases and the matrix produced exactly the expected outcome.
It does **not** mean the servers are correct against any independent oracle: the servers, this battery and its expectations were all
written by the same author (an AI assistant) and the four servers share a common ancestor (`mcp-forge`), so agreement between them is
weaker evidence than agreement between independent implementations. Details: `AUDIT.md` ("Limits") and `SECURITY.md`.

## Layout

```
mcpcross/        wire.py (stdio/HTTP framing)  launch.py (start servers, mint tokens)  client.py  jwtkit.py
                 battery.py  differential.py  crosstoken.py  runner.py  report.py  targets.py  cli.py
tests/           unit tests (fake servers for the wire layer), logic tests, CLI tests, integration tests against the real family
tools/           check_stdlib_only.py  make_manifest.py  gen_originality.py  check_doc_refs.py  mutation_sanity.py  build_evidence.sh
evidence/        crosscheck.json/.md, test/demo/mutation/stdlib outputs (regenerate with tools/build_evidence.sh)
demo.sh demo.py  README.md  AUDIT.md  ORIGINALITY.md  SECURITY.md  MANIFEST.sha256
```

## Resumen en español

`mcp-crosscheck` valida de forma cruzada los cuatro servidores MCP de la familia (base, memory-first, auth-hardened, resource-heavy)
usando solo la biblioteca estándar de Python. Los lanza como procesos reales (stdio y HTTP), sin importar su código, y ejecuta:
(1) una batería común de 57 checks de caja negra; (2) pruebas diferenciales: las mismas entradas mal formadas deben producir los
mismos códigos de error JSON-RPC en los cuatro servidores, y las capacidades anunciadas deben coincidir con el comportamiento real;
(3) una matriz de tokens cruzados (16 pares × 2 transportes × 5 capas): con secretos distintos o audiencias distintas el token debe
ser rechazado; con secreto y audiencia compartidos (y `--allow-kidless` en auth-hardened) debe ser aceptado y utilizable.
Comando principal: `python3 -m mcpcross run` (resultado en `evidence/crosscheck.md`). Verificación paso a paso en `AUDIT.md`.
**Limitación honesta:** los servidores, la batería y sus expectativas tienen el mismo autor y los servidores comparten un ancestro, por lo
que el acuerdo entre ellos no equivale a una certificación independiente.

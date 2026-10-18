# Review record, version 1.1.0 (2026-10-17)

Team: one lead, two builders (pipeline, tests), two independent reviewers (engineering results;
security and robustness) who reviewed the code without the builders' reasoning, then two
verification reviewers and a final targeted verification. Every finding is listed with its outcome.

## Round 0: new test suite (308 tests) found 12 bugs, all fixed in 54d139f
Quoted `"false"` enabled `+SYS`; single-backslash paths silently mangled; includes deeper than 3
levels skipped the `+SYS` scan; `101 - 118` ranges rejected; envelopes included eigenmodes and
dropped the SLN warning; `.bak` copies overwritten within one second (server and Claude config);
running-`.cdb` lock bypassed by other path spellings; `list_folder` truncation flag; truncation
warning crashed `cdb_load_cases`; README missing `cdb_nodes`.

## Round 1 reviews, fixed in 02c3e97
| Finding | Severity | Outcome |
| --- | --- | --- |
| Group filter from overlapping CGRP ranges pulled in other groups' beams | Blocker | Fixed: GDIV, then structural line group, then unique beam range; ambiguous beams excluded with a warning |
| `*SYS` not recognised | Blocker | Fixed |
| Included / applied files swappable during a run | Blocker | Fixed: writes refused during a run, inputs re-hashed after it |
| BOM, `$()`, `#define`, invisible characters, include-candidate tricks | Blocker | Fixed |
| Run "ok" without checking exit code or unfinished programs | Major | Fixed (refined in round 2) |
| Eigenmodes returned as ordinary results | Major | Fixed: warning |
| No sign checks; sign convention unstated | Major | Self-test now records the observed signs; convention to be documented after the first PC run |
| Key without data treated as results | Major | Fixed |
| Extremes not concurrent | Major | Fixed: each extreme carries its row's other components |
| Self-test gaps (rotation, zero forces, envelope, titles) | Major | Fixed |
| Includes outside readable folders leaked file contents | Major | Fixed: refused |
| Orphaned sps.exe after the server ends | Major | Fixed: Windows job object, lock file |
| `write_dat_file` could plant `+SYS` files | Major | Fixed: refused |
| Legitimate input refused (`#define` blocks, `$(NAME)`, `PROG` without `+`) | Major | Fixed |
| NTFS alternate data streams, device names | Major | Fixed: refused |
| 22 minor findings (PZ vs PZZ, stale-result warning, negative DLL returns, factor decoding, fresh `.prt` detection, partial sums, caps, atomic writes, quick stop, relative folders, install.bat, Claude CLI quoting, backups, ...) | Minor | Fixed |

## Round 2 verification, fixed in 09d749a
| Finding | Severity | Outcome |
| --- | --- | --- |
| `$()` inside the first word (`+S$(Y)`) bypassed the `+SYS` rule | Blocker | Fixed |
| A missing totals line could mark every clean run "not finished" | Major | Fixed: only a missing Stop line does; exit code is a warning |
| Group rules 2 and 3 never tested on a real `.cdb` | Major | Self-test now compares all rules on the real model and prints the element codes |
| UTF-16 / UTF-32 files hid `+SYS` | Major | Fixed |
| `#define` values mentioning "system" refused | Major | Fixed |
| `+APPL`, includes after `;`, defines used before they are set, SYS past column 255, per-run job kill, lock host/start time, install.bat probe, GDIV/range disagreement, MAXIMA note, scan timing, title/sign checks made INFO | Minor | Fixed |
| `.bat` files stored with LF in git | Minor | Fixed: stored byte-for-byte with CRLF |

## Final verification (ea05c01): no blocker or major findings
Accepted, with reasons:
- A program other than this server could still change an included file between the scan and
  SOFiSTiK reading it. Detected after the run ("input changed during run"); prevention would need
  running a copy, which breaks relative includes and result file names. Outside the threat model.
- Windows reports a process that ended with exit code 259 as still running; this only makes a lock
  look busy (safe side) and the message says how to remove it.

## Acceptance test on the engineer's PC (17 Oct 2026): ALL CHECKS PASSED
SOFiSTiK 2027, Python 3.12.10. Settled: `sps.exe -B0` works, exit code 0; clean runs print no
totals line (handled); CGRP codes 0 and 100; reactions are the support's force on the structure
(+Z load gives pz < 0); load-case key scan 0.5 s; ASE keeps titles. One cosmetic fix: the report
printed "(? load cases)" because it did not count the server's `{"rows": ...}` answer.

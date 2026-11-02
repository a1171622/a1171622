"""Pictures for the engineer: utilisation plans and the assumptions (restraints, buckling lengths) on the model.

    python -m memcheck.plots --dat model.dat --results out/results.json --out out/   [--title "26016 v16"]

Writes utilisation_plan.png (one panel per floor level + the stairs, members coloured by utilisation, labelled
with member number and utilisation) and assumptions_plan.png (where the code takes lateral and twist restraints,
which members run as one continuous member, and one worked member with its moment diagram and LTB lengths).
Levels are found from the member heights (z), so the script is not tied to one project.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402

from . import members as M  # noqa: E402
from . import sofistik as S  # noqa: E402

BANDS = [0, 0.5, 0.8, 0.9, 1.0, 9]
COLS = ["#9fb7c9", "#2e8b57", "#e0a400", "#e8590c", "#c92a2a"]
CMAP = ListedColormap(COLS)
NORM = BoundaryNorm(BANDS, CMAP.N)


def _members(dat, results):
    sections, slns, sto = S.read_dat(dat)
    bdk = S.read_bdk_members(dat, sto)
    ids = {r["id"] for r in results}
    extra = [r["slns"][0] for r in results if len(r["slns"]) == 1]
    mems = {m.id: m for m in M.build_members(bdk, slns, sections, extra_slns=extra) if m.id in ids}
    return mems, sections


def _levels(mems, tol=0.3):
    """Floor levels = heights where many horizontal members sit."""
    cnt = defaultdict(int)
    for m in mems.values():
        if abs(m.pts[0][2] - m.pts[-1][2]) < 1e-3 and m.group not in (60, 61):
            cnt[round(m.pts[0][2], 1)] += 1
    lv = sorted(z for z, n in cnt.items() if n >= 20)
    return lv


def _is_horizontal(m):
    return abs(m.pts[0][2] - m.pts[-1][2]) < 1e-3


def utilisation_plan(dat, results, out, title=""):
    res = {r["id"]: r for r in results}
    mems, _ = _members(dat, results)
    levels = _levels(mems)
    stairs = [m for m in mems.values() if m.group in (60, 61)]
    n = len(levels) + (1 if stairs else 0)
    fig, axs = plt.subplots(1, n, figsize=(7.2 * n, 8.2))
    names = {0: "Level 1", 1: "Level 2", 2: "Roof"}
    for k, z in enumerate(levels):
        ax = axs[k]
        beams = [m for m in mems.values() if _is_horizontal(m) and abs(m.pts[0][2] - z) < 0.3 and m.group not in (60, 61)]
        cols = [m for m in mems.values() if not _is_horizontal(m) and m.group not in (60, 61)
                and (abs(m.pts[0][2] - z) < 0.3 or abs(m.pts[-1][2] - z) < 0.3)]
        _draw(ax, beams, res, label_min=0.6)
        # columns that end at this level, drawn as squares at their top / bottom point on this level
        for m in cols:
            p = m.pts[0] if abs(m.pts[0][2] - z) < 0.3 else m.pts[-1]
            u = res[m.id]["util"]
            ax.plot(p[0], p[1], "s", ms=6, color=CMAP(NORM(u)), mec="k", mew=0.5, zorder=4)
        top = max(beams, key=lambda m: res[m.id]["util"]) if beams else None
        hdr = f"{names.get(k, f'z = {z} m')}  (z = {z:.1f} m)"
        if top:
            hdr += f"\nhighest beam: member {top.id}, {res[top.id]['util']:.2f}"
        ax.set_title(hdr, fontsize=11)
    if stairs:
        ax = axs[-1]
        _draw(ax, stairs, res, label_min=0.3, lw=2.2)
        top = max(stairs, key=lambda m: res[m.id]["util"])
        ax.set_title(f"Stairs (plan, all heights)\nhighest: member {top.id}, {res[top.id]['util']:.2f}", fontsize=11)
    sm = plt.cm.ScalarMappable(cmap=CMAP, norm=NORM)
    sm.set_array([])
    cb = fig.colorbar(sm, ax=list(axs), orientation="horizontal", fraction=0.035, pad=0.06, boundaries=[0, 0.5, 0.8, 0.9, 1.0, 1.2], ticks=[0.25, 0.65, 0.85, 0.95, 1.1])
    cb.ax.set_xticklabels(["< 0.5", "0.5-0.8", "0.8-0.9", "0.9-1.0", "> 1.0 (fails)"])
    cb.set_label("utilisation (governing EN 1993-1-1 check, all ULS combinations)")
    fig.suptitle(f"{title}  member utilisation plan (labels: member number / utilisation; squares = columns ending at"
                 f" this level)", fontsize=13)
    p = os.path.join(out, "utilisation_plan.png")
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return p


def _draw(ax, mems, res, label_min=0.6, lw=2.6):
    for m in sorted(mems, key=lambda m: res[m.id]["util"]):
        u = res[m.id]["util"]
        xs = [p[0] for p in m.pts]
        ys = [p[1] for p in m.pts]
        ax.plot(xs, ys, "-", color=CMAP(NORM(u)), lw=lw if u < 0.8 else lw + 1.2, solid_capstyle="butt")
        if u >= label_min:
            mid = m.point_at(m.length / 2)
            ax.annotate(f"{m.id}\n{u:.2f}", (mid[0], mid[1]), fontsize=7, ha="center", va="center", zorder=5,
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=CMAP(NORM(u)), lw=0.8, alpha=0.9))
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


def assumptions_plan(dat, results, out, forces=None, beam_pos=None, worked=None, title=""):
    res = {r["id"]: r for r in results}
    mems, sections = _members(dat, results)
    levels = _levels(mems)[:2]
    fig = plt.figure(figsize=(21, 9.5))
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 0.55])
    for k, z in enumerate(levels):
        ax = fig.add_subplot(gs[:, k])
        beams = [m for m in mems.values() if _is_horizontal(m) and abs(m.pts[0][2] - z) < 0.3 and m.group not in (60, 61)]
        for m in beams:
            xs = [p[0] for p in m.pts]
            ys = [p[1] for p in m.pts]
            chained = len(m.slns) > 1
            ax.plot(xs, ys, "-", color="#1c5d99" if chained else "#8a8a8a", lw=2.4 if chained else 1.2)
            for s, kind, _ in m.restraints:
                p = m.point_at(s)
                if "DX" in kind:
                    ax.plot(p[0], p[1], "^", color="#c92a2a", ms=8, zorder=5)
                else:
                    ax.plot(p[0], p[1], "o", mfc="white", mec="#e8590c", mew=1.6, ms=7, zorder=5)
            if worked and m.id == worked:
                mid = m.point_at(m.length * 0.7)
                ax.annotate(f"member {m.id}\n(worked example)", (mid[0], mid[1]), xytext=(25, 25),
                            textcoords="offset points", fontsize=9, arrowprops=dict(arrowstyle="->"))
        ax.set_title(["Level 1", "Level 2"][k] + f" (z = {z:.1f} m): restraints the check uses", fontsize=11)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
    h = [plt.Line2D([], [], color="#1c5d99", lw=2.4, label="one continuous member (lines joined, as BDK MEMB + CONT)"),
         plt.Line2D([], [], color="#8a8a8a", lw=1.2, label="member on its own (fork ends)"),
         plt.Line2D([], [], marker="^", color="#c92a2a", ls="", ms=8,
                    label="column: holds sideways movement AND twist (ends an LTB length)"),
         plt.Line2D([], [], marker="o", mfc="white", mec="#e8590c", ls="", ms=7,
                    label="ring beam only: holds sideways movement at the beam centre, twist free")]
    fig.legend(handles=h, loc="lower left", bbox_to_anchor=(0.02, 0.0), fontsize=10, ncol=2, frameon=False)
    # worked example: diagram with the LTB lengths
    ax = fig.add_subplot(gs[0, 2])
    ax2 = fig.add_subplot(gs[1, 2])
    ax2.axis("off")
    if worked and forces and worked in mems:
        m = mems[worked]
        r = res[worked]
        lc = r["lc"]
        F = S.read_forces(forces, {lc})
        if beam_pos:
            sections_, slns, _ = S.read_dat(dat)
            bp = {int(k): v for k, v in json.load(open(beam_pos)).items()}
            F = S.remap_forces(F, bp, slns)
        rows = M.diagrams(m, F[lc])
        ax.plot([q[0] for q in rows], [q[5] for q in rows], "-", color="#1c5d99", lw=2)
        ax.axhline(0, color="k", lw=0.6)
        for s, kind, note in m.restraints:
            ax.axvline(s, color="#c92a2a" if "DX" in kind else "#e8590c", ls="-" if "DX" in kind else "--", lw=1.4)
            ax.text(s, ax.get_ylim()[1], " " + note.split(":")[0] + (" column" if "DX" in kind else " ring"),
                    fontsize=8, va="top", rotation=90)
        ax.set_xlabel("position along the member (m)")
        ax.set_ylabel("My (kNm), hogging up")
        ax.set_title(f"member {worked} ({r['section']}), LC {lc}: moment diagram", fontsize=11)
        ax.invert_yaxis()
        det = r.get("details", {})
        txt = (f"LTB length {det.get('LLT_', 0) / 1000:.2f} m between the column and the end; the ring beam inside it "
               f"is used\nas a sideways restraint in the buckling solver (Mcr = {det.get('Mcr_', 0):.0f} kNm, "
               f"chiLT = {det.get('chiLT_', 0):.2f}).\n"
               f"Lcr,z = {det.get('Lcrz_', 0) / 1000:.2f} m (between sideways restraints), "
               f"Lcr,y = {det.get('Lcry_', 0) / 1000:.2f} m (whole member, as BDK).\n"
               f"Result {r['util']:.2f} ({r['governing']}), BDK {r.get('bdk', '-')}.")
        ax2.text(0, 1, txt, fontsize=10, va="top", family="monospace")
    fig.suptitle(f"{title}  what the check assumes: restraints, continuous members, buckling lengths "
                 "(load at the shear centre, no load height)", fontsize=13)
    p = os.path.join(out, "assumptions_plan.png")
    fig.savefig(p, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return p


def bdk_comparison(results, out, title=""):
    xs, ys, lab = [], [], []
    for r in results:
        if "bdk" in r and r["bdk"] > 0.05:
            xs.append(r["bdk"])
            ys.append(r["mine_6361"])
            lab.append(r["id"])
    fig, ax = plt.subplots(figsize=(7.5, 7.5))
    ax.plot([0, 1.2], [0, 1.2], "k-", lw=0.8)
    ax.fill_between([0, 1.2], [-0.03, 1.17], [0.03, 1.23], color="#2e8b57", alpha=0.15, label="within 0.03")
    ax.scatter(xs, ys, s=14, color="#1c5d99")
    for x, y, i in zip(xs, ys, lab):
        if abs(x - y) > 0.05:
            ax.annotate(str(i), (x, y), fontsize=8, xytext=(3, 3), textcoords="offset points")
    ax.set_xlabel("BDK (SOFiSTiK) eq. 6.61/6.62")
    ax.set_ylabel("this workflow eq. 6.61/6.62")
    ax.set_xlim(0, 1.15)
    ax.set_ylim(0, 1.15)
    ax.set_aspect("equal")
    ax.legend(loc="upper left")
    ax.set_title(f"{title} member buckling check: new workflow vs BDK\n(labelled: differences above 0.05)")
    p = os.path.join(out, "bdk_comparison.png")
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dat", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--forces")
    ap.add_argument("--beam-pos")
    ap.add_argument("--worked", type=int, help="member number for the worked example panel")
    ap.add_argument("--title", default="")
    a = ap.parse_args(argv)
    results = json.load(open(a.results))["members"]
    print(utilisation_plan(a.dat, results, a.out, a.title))
    print(assumptions_plan(a.dat, results, a.out, a.forces, a.beam_pos, a.worked, a.title))
    print(bdk_comparison(results, a.out, a.title))


if __name__ == "__main__":
    main()

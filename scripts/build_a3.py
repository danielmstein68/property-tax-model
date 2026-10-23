"""Build the stand-alone Amendment 3 page: display/fl_amendment3.html

Usage:
    python scripts/build_a3.py

Two pages, "Amendment 3 results" and "Model info", cut out of display/template.html (the multi-page Florida and
Texas display): the Amendment 3 view and the About view, with the pieces of script they depend on, and only the
data they use (the two Amendment 3 runs of the policy grid, not the 338-setting menu). Nothing here is a second
copy of the logic; edit display/template.html and rebuild both.
"""

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "data" / "processed" / "results"
BRAND = ROOT / "brand" / "cle"      # CLE brand logos (SVG), from the CLE Brand & Style Guide package
LOGOS = ""


def _logo(name: str, cls: str, key: str) -> str:
    """The supplied CLE logo SVG, inlined as delivered (class renamed so the two logos' styles don't collide)."""
    svg = (BRAND / name).read_text(encoding="utf-8")
    svg = svg[svg.index("<svg"):].replace(".cls-1", f".{key}").replace('class="cls-1"', f'class="{key}"')
    svg = svg.replace('id="Layer_1"', "", 1).replace("<svg ", f'<svg class="logo {cls}" role="img" aria-label="Center for Land Economics" ', 1)
    return svg


def between(s: str, start: str, end: str, keep_end: bool = False) -> str:
    i = s.index(start)
    j = s.index(end, i + len(start))
    return s[i:j + (len(end) if keep_end else 0)]


def drop_block(s: str, start: str, end: str) -> str:
    i = s.index(start)
    j = s.index(end, i)
    return s[:i] + s[j:]


def main() -> None:
    global LOGOS
    LOGOS = _logo("CLE_Logo_Purple.svg", "logo-p", "cle-p") + _logo("CLE_Logo_White.svg", "logo-w", "cle-w")
    t = (ROOT / "display" / "template.html").read_text(encoding="utf-8")

    # ---------------- HTML ----------------
    head_end = t.index('<div class="hero">')
    head = t[:head_end].replace("<title>Property Tax Model</title>", "<title>Florida Amendment 3</title>")
    hero = ('<div class="hero">\n  <div class="hero-in">\n' + LOGOS + '\n'
            '    <nav class="views" aria-label="Pages" id="views">\n'
            '      <button data-v="a3" id="view-btn-a3">Amendment 3 results</button><button data-v="about" id="view-btn-about">Model info</button>\n'
            '    </nav>\n'
            '    <div class="eyebrow" id="eyebrow"></div>\n    <h1 id="h1"></h1>\n    <p class="lede" id="lede"></p>\n'
            '    <span class="badge" id="badge">Owners only. Renters are counted in the income groups, but the tax they pay through rent is not modelled yet.</span>\n'
            '  </div>\n</div>\n\n<div class="wrap">\n')
    a3_html = between(t, '  <div id="view-a3"', '  <div id="view-about"')
    about_html = between(t, '  <div id="view-about"', '  <footer id="foot">') .rstrip() + "\n"
    body = hero + a3_html + about_html + '  <footer id="foot"></footer>\n</div>\n\n<script>\n'
    body = body.replace("About the model →", "Model info →")
    # this page offers two rate settings and no reimbursement option: say so in the assumptions
    for old, new in [
        ("<b>Three ways local governments can respond.</b>", "<b>Two ways local governments can respond (the page's rate setting).</b>"),
        (" <i>Governments respond</i>: rates change the way Florida counties, cities and school districts changed them in comparable years since the 1990s, within the limit of 110% of the rolled-back rate.", ""),
        (" Options add state reimbursement or the state's usual offset for 29 small, rural counties (s. 218.125).", ""),
        ("<span>Year by year to 2036: values, sales, new homes, and how governments set rates; then each policy against current law.</span>",
         "<span>Year by year to 2036: values, sales, new homes, and how governments set rates; then Amendment 3 against current law.</span>"),
    ]:
        assert old in body, old
        body = body.replace(old, new)

    # ---------------- script ----------------
    js_start = t.index("<script>\n") + len("<script>\n")
    js = t[js_start:t.index("</script>", js_start)]
    pieces = []
    pieces.append(between(js, "const $ = id", "const Z = 1.645;"))
    pieces.append(between(js, "const NS = ", "// Chart 1:"))
    g = between(js, "const G = __GRID__;", "let VIEW = ")
    g = re.sub(r"const POL = \{[^\n]*\};", 'const POL = { reimb: 0, nocap: false, fc: false, mode: "none", gov: "county", group: "age_group" };', g)
    pieces.append(g)
    pieces.append('let VIEW = "a3";\n' + between(js, "const A3 = {", "function currentRun()"))
    rev = between(js, "// 1. revenue lost (all property)", "// the Policy tab: one rate response at a time")
    rev = "\n".join(l for l in rev.split("\n") if "pol-gov-tabs" not in l)
    pieces.append(rev)
    pieces.append(between(js, "const GROUP_TABS =", "\n") + "\n")
    pieces.append(between(js, "// ---------------- Amendment 3 page", "// views: 2026 today"))
    body_js = "\n".join(pieces)

    # Model info: lists the 2026 page filled from survey margins and projections; the Amendment 3 page keeps two static notes
    body_js += '''
$("reliability").innerHTML = [
  `Home values and incomes come from what households report to the Census Bureau, adjusted to 2026. Who claims a homestead exemption, each home's Save Our Homes discount and its tax district are estimated so that each area matches the property rolls; they are right for groups, not for each household.`,
  `Owners only: renters' share of property tax through rent is not modelled, nor are mobile-home owners on rented lots, non-ad valorem assessments (fire, waste, stormwater fees) or business property as households.`,
].map(t => `<li>${t}</li>`).join("");
$("p-reliability").innerHTML = [
  `Projections are one central economic scenario (the state's own forecasts through 2032, then easing). They are what-ifs, not predictions, and do not include survey sampling error, future law changes, or moving because of taxes.`,
].map(t => `<li>${t}</li>`).join("");
$("foot").textContent = `Center for Land Economics · landeconomics.org · Florida Amendment 3 · generated ${G.generated} · tax roll years 2027-2036 · 2026 property rolls, 2024 Census survey, state forecasts.`;

const VIEWS = {
  a3: { eyebrow: "Florida · Amendment 3 · November 3, 2026 ballot", h1: "What Amendment 3 would change, and for whom",
        lede: "Who gains and who pays under the proposed constitutional amendment, compared with current law on the same households and economy." },
  about: { eyebrow: "Florida Amendment 3", h1: "Model info",
        lede: "How the results are built, how well they match official figures, the assumptions behind them and what they leave out." },
};
function showView(v) {
  VIEW = v;
  $("view-a3").hidden = v !== "a3";
  $("view-about").hidden = v !== "about";
  document.querySelectorAll("#views button").forEach(b => b.setAttribute("aria-selected", b.dataset.v === v));
  $("eyebrow").textContent = VIEWS[v].eyebrow; $("h1").textContent = VIEWS[v].h1; $("lede").textContent = VIEWS[v].lede;
  if (v === "a3") renderA3();
}
$("views").addEventListener("click", e => { const b = e.target.closest("button[data-v]"); if (b) { showView(b.dataset.v); window.scrollTo(0, 0); } });
document.addEventListener("click", e => { const a = e.target.closest("[data-goto]"); if (!a) return;
  e.preventDefault(); showView(a.dataset.goto === "about" ? "about" : "a3"); window.scrollTo(0, 0); });
showView(location.hash === "#about" ? "about" : "a3");
'''

    # ---------------- data ----------------
    grid = json.loads((RES / "fl_policy_grid.json").read_text(encoding="utf-8"))
    keep = ["a3_full", "a3_full_nowait"]
    slim = {k: grid[k] for k in ["scenario", "years", "from", "generated", "current_law", "group_cols", "reimburse", "governments"]}
    slim["runs"] = {k: grid["runs"][k] for k in keep}
    slim["presets"], slim["sliders"] = [{"id": "a3_full", "label": "Whole amendment", "description": ""}], [{"id": "none"}]
    for run in slim["runs"].values():
        run.pop("neutral_nocap", None)
    sub = {
        "__GRID__": json.dumps(slim, separators=(",", ":")),
        "__FIN__": json.dumps(yaml.safe_load((ROOT / "inputs" / "fl_local_finance_fy2024.yaml").read_text(encoding="utf-8"))),
        "__REC__": json.dumps(yaml.safe_load((ROOT / "inputs" / "fl_rec_amendment3.yaml").read_text(encoding="utf-8"))),
        "__A3EX__": (RES / "fl_a3_examples.json").read_text(encoding="utf-8"),
        "__A3GOV__": (RES / "fl_a3_rec_by_government.json").read_text(encoding="utf-8"),
        "__A3RENT__": (RES / "fl_a3_rentals.json").read_text(encoding="utf-8"),
        "__A3RANGE__": (RES / "fl_a3_takeup_range.json").read_text(encoding="utf-8"),
        "__HHDEC__": (RES / "fl_household_deciles.json").read_text(encoding="utf-8"),
        "__OFFSET__": (RES / "fl_offset_taxes.json").read_text(encoding="utf-8"),
        "__VAL__": json.dumps(json.loads((RES / "fl_2026_validation.json").read_text(encoding="utf-8"))["statewide_homestead"]),
    }
    page = head + body + body_js + "</script>\n"
    for k, v in sub.items():
        page = page.replace(k, v)
    left = re.findall(r"__[A-Z0-9]+__", page)
    assert not left, f"unfilled placeholders: {set(left)}"
    dest = ROOT / "display" / "fl_amendment3.html"
    dest.write_text(page, encoding="utf-8")
    print(f"wrote {dest} ({dest.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()

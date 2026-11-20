"""
    Filename: build_combined.py
    Description:
        Builds block-p-sign.html: one page with three tabs, made from the renders
        page and the CAD viewer.

          Render            the 3D render and the build summary
          CAD & BoM         the CAD model and build guide, print list, files, parts list
          Wiring & install  the wiring diagram, level shifter, bring-up, cable routes
                            and assembly notes

        Each tab stacks sections cut from the two source pages. Each cut runs in its
        own frame, so the pages' styles and scripts never clash. Cuts that only hold
        text and tables leave out the 3D code. Links between the old pages switch tabs.

    Run (after block_p.py and build_viewer.py):
        python "Design Process/build_combined.py"
"""

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
RENDERS = ROOT / "Design Process" / "Renders" / "block-p-renders.html"
CAD = ROOT / "Hardware" / "CAD" / "block_p_viewer.html"
OUT = ROOT / "Design Process" / "block-p-sign.html"

# Old single-page links that now switch tabs.
TAB_LINKS = {
    "BhFKYkZ5V4AmjUNsZYKAa3": "cad",
    "UUrsDX5AFSufHLUw4droVF": "render",
}


class Block(str):
    """A section's HTML, plus the container it sat in on its page (or "")."""
    def __new__(cls, text, holder=""):
        block = super().__new__(cls, text)
        block.holder = holder
        return block


def split(text):
    """The page split into head, top-level blocks, and tail.

    Both source pages indent the children of <div class="wrap"> by two spaces. The
    renders page also groups its lower sections in <div ... id="detail">, indented
    four spaces inside it; those come out one by one, remembering their container.
    """
    wrap = text.index('<div class="wrap">')
    end = text.index("\n</div>", wrap)

    starts = [wrap + m.start() + 1 for m in re.finditer(r"\n  <(?:header|section|footer|div)\b", text[wrap:end])]
    bounds = starts + [end]
    blocks = []
    for piece in (text[bounds[i]:bounds[i + 1]].rstrip() for i in range(len(starts))):
        if piece.startswith("  <div"):
            opening = piece[: piece.index(">") + 1]
            inner = piece[len(opening): piece.rindex("</div>")]
            blocks += [Block(b, opening) for b in re.split(r"(?=\n    <(?:section|div)\b)", inner) if b.strip()]
        else:
            blocks.append(Block(piece))
    return text[: starts[0]], blocks, "\n" + text[end:]


def heading(block):
    found = re.search(r"<h[12][^>]*>(.*?)</h[12]>", block, re.S)
    return re.sub(r"<[^>]+>|\s+", " ", found.group(1)).strip() if found else ""


def pick(blocks, *names):
    """Blocks whose first heading starts with one of the names, in the order given."""
    chosen = []
    for name in names:
        match = [b for b in blocks if heading(b).lower().startswith(name.lower())]
        if len(match) != 1:
            raise SystemExit(f"Expected one section titled '{name}', found {len(match)}: "
                             + ", ".join(repr(heading(b)) for b in blocks))
        chosen.append(match[0])
    return chosen


def no_scripts(text):
    return re.sub(r"<script\b.*?</script>", "", text, flags=re.S)


def make(head, blocks, tail, scripts=True):
    body, holder = [], ""
    for block in blocks:
        if block.holder != holder:
            if holder:
                body.append("  </div>")
            if block.holder:
                body.append(block.holder)
            holder = block.holder
        body.append(block.rstrip() if block.holder else block)
    if holder:
        body.append("  </div>")
    page = head + "\n\n".join(body) + tail
    # Viewer heights follow the outer window, since each frame is sized to its content.
    page = page.replace("min(66vh,", "min(calc(var(--pvh,1vh)*66),").replace("min(70vh,", "min(calc(var(--pvh,1vh)*70),")
    return page if scripts else no_scripts(page)


def embed(text):
    """A string that is safe inside a <script> element."""
    return json.dumps(text).replace("</", "<\\/")


# Sections for each tab, by heading, after each page's header and 3D view.
RENDER = ['8" build']
CAD_MODEL = ["Parts to print", "Send when parts arrive", "Files", "Wire bend check"]
BOM = ["Parts list", "Changes carried into the CAD"]
WIRING = ["Power and signal wiring"]
INSTALL = ["How it goes together", "How the LEDs get power", "How the screen connects"]


def main():
    r_head, r_blocks, r_tail = split(RENDERS.read_text(encoding="utf-8"))
    c_head, c_blocks, c_tail = split(CAD.read_text(encoding="utf-8"))
    r_header = Block(r_blocks[0].replace(", with its parts list and wiring.", "."))
    r_viewer = r_blocks[1]                      # the render and its controls (no heading)
    c_header, c_viewer = c_blocks[0], c_blocks[1]

    parts = {
        "render": make(r_head, [r_header, r_viewer] + pick(r_blocks, *RENDER), r_tail),
        "cad-model": make(c_head, [c_header, c_viewer] + pick(c_blocks, *CAD_MODEL), c_tail),
        "bom": make(r_head, pick(r_blocks, *BOM), r_tail, scripts=False),
        "wiring": make(r_head, pick(r_blocks, *WIRING), r_tail, scripts=False),
        "install": make(c_head, pick(c_blocks, *INSTALL), c_tail, scripts=False),
    }

    # Every section of both pages lands in a tab, except the old "get back to this page" footer.
    used = {heading(b) for b in pick(r_blocks, *RENDER, *BOM, *WIRING) + pick(c_blocks, *CAD_MODEL, *INSTALL)}
    left = [heading(b) for b in r_blocks[2:] + c_blocks[2:] if heading(b) not in used and not b.lstrip().startswith("<footer")]
    if left:
        raise SystemExit("Sections not placed in any tab: " + ", ".join(left))

    page = PAGE.replace("__PARTS__", embed(json.dumps(parts))).replace("__LINKS__", json.dumps(TAB_LINKS))
    OUT.write_text(page, encoding="utf-8")
    print(f"{OUT.name}: {len(page) // 1024} KB")
    for name, text in parts.items():
        print(f"  {name}: {len(text) // 1024} KB")


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="claude:viewport-fit-sides" content="cover">
<title>Block P Sign</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@800&family=Source+Sans+3:wght@400;600&display=swap">
<style>
/* Shell for the three tabs. Same night-game look as the two source pages. */
:root{
  --bg:#121110; --panel:#1c1a18; --line:#3a352e; --fg:#f1ece2; --muted:#b4aa9b; --gold:#cfb991; --bright:#ffc04a;
  --display:"Big Shoulders Display","Arial Narrow",Impact,sans-serif;
  --body:"Source Sans 3","Segoe UI",system-ui,sans-serif;
  color-scheme:dark;
}
*{box-sizing:border-box;min-width:0}
html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);font:16px/1.45 var(--body)}
body{display:flex;flex-direction:column;height:100dvh;overflow:hidden}
header{flex:none;display:flex;align-items:center;gap:20px;min-height:56px;
  padding:env(safe-area-inset-top,0px) max(16px,env(safe-area-inset-right,0px)) 0 max(16px,env(safe-area-inset-left,0px));
  background:var(--panel);border-bottom:1px solid var(--line)}
.brand{font:800 24px/1 var(--display);letter-spacing:.04em;text-transform:uppercase;color:var(--gold);white-space:nowrap}
[role=tablist]{display:flex;align-self:stretch;overflow-x:auto;scrollbar-width:none}
[role=tab]{flex:none;appearance:none;border:0;background:none;color:var(--muted);font:600 15px/1 var(--body);
  min-height:44px;padding:0 14px;cursor:pointer;border-bottom:3px solid transparent}
[role=tab]:hover{color:var(--fg)}
[role=tab][aria-selected=true]{color:var(--fg);border-bottom-color:var(--gold)}
[role=tab]:focus-visible{outline:2px solid var(--gold);outline-offset:-4px}
main{position:relative;flex:1;min-height:0;overflow-y:auto;overscroll-behavior:contain}
.panel{display:block}
.panel.off{position:absolute;top:0;left:0;width:100%;height:0;overflow:hidden;visibility:hidden;pointer-events:none}
iframe{display:block;width:100%;height:240px;border:0;background:var(--bg)}
.loading{padding:48px 16px;text-align:center;color:var(--muted)}
.guide{max-width:1120px;margin:24px auto 0;padding:0 max(16px,env(safe-area-inset-left,0px));}
.guide div{display:flex;flex-wrap:wrap;align-items:center;gap:12px 20px;justify-content:space-between;
  background:var(--panel);border:1px solid var(--line);padding:16px 18px}
.guide p{margin:0;max-width:62ch}
.guide button{appearance:none;border:0;background:var(--gold);color:#17140f;font:800 18px/1 var(--display);
  letter-spacing:.04em;text-transform:uppercase;min-height:44px;padding:0 18px;cursor:pointer}
.guide button:focus-visible{outline:2px solid var(--bright);outline-offset:3px}
@media (max-width:560px){.brand{display:none}header{gap:0}[role=tab]{padding:0 10px;font-size:14px}}
</style>
</head>
<body>
<header>
  <div class="brand">Block P</div>
  <div role="tablist" aria-label="Pages">
    <button role="tab" id="tab-render" aria-controls="panel-render" aria-selected="true">Render</button>
    <button role="tab" id="tab-cad" aria-controls="panel-cad" aria-selected="false" tabindex="-1">CAD &amp; BoM</button>
    <button role="tab" id="tab-install" aria-controls="panel-install" aria-selected="false" tabindex="-1">Wiring &amp; install</button>
  </div>
</header>
<main id="main">
  <div class="loading" id="loading">Loading…</div>
  <section class="panel" id="panel-render" role="tabpanel" aria-labelledby="tab-render">
    <iframe data-part="render" title="3D render"></iframe>
  </section>
  <section class="panel off" id="panel-cad" role="tabpanel" aria-labelledby="tab-cad">
    <iframe data-part="cad-model" title="CAD model, print list and files"></iframe>
    <iframe data-part="bom" title="Parts list"></iframe>
  </section>
  <section class="panel off" id="panel-install" role="tabpanel" aria-labelledby="tab-install">
    <div class="guide"><div>
      <p>Want to see each step in 3D? The build guide steps through the model in the order you assemble it.</p>
      <button type="button" id="open-guide">Open the 3D build guide</button>
    </div></div>
    <iframe data-part="wiring" title="Power and signal wiring"></iframe>
    <iframe data-part="install" title="How it goes together"></iframe>
  </section>
</main>
<script type="application/json" id="parts">__PARTS__</script>
<script>
{
  const TAB_LINKS = __LINKS__;
  const OLD_NAMES = { sign: "render" };
  const PARTS = JSON.parse(JSON.parse(document.getElementById("parts").textContent));
  const names = ["render", "cad", "install"];
  const main = document.getElementById("main");
  const tabs = Object.fromEntries(names.map(n => [n, document.getElementById("tab-" + n)]));
  const panels = Object.fromEntries(names.map(n => [n, document.getElementById("panel-" + n)]));
  const scrolls = {};
  let current = null;

  // The claude.ai viewer opens outside sites from plain link clicks on the top page,
  // so a link clicked inside a frame is re-clicked from here.
  function openOutside(url) {
    const a = document.createElement("a");
    a.href = url; a.target = "_blank"; a.rel = "noopener"; a.hidden = true;
    document.body.appendChild(a); a.click(); a.remove();
  }

  function setup(frame) {
    let doc;
    try { doc = frame.contentDocument; } catch (e) { return; }
    if (!doc || !doc.body) return;
    const stacked = frame.previousElementSibling && frame.previousElementSibling.tagName === "IFRAME";
    const style = doc.createElement("style");
    style.textContent = "html,body{overflow:hidden!important;height:auto!important}"
      + (stacked ? ".wrap{padding-top:0!important}" : "")
      + (frame.nextElementSibling ? ".wrap{padding-bottom:24px!important}" : "");
    doc.head.appendChild(style);
    // A hidden tab's 3D scene stops drawing until its tab shows again, so only one
    // scene animates at a time.
    const win = frame.contentWindow, raf = win.requestAnimationFrame.bind(win), held = [];
    const panel = frame.closest(".panel");
    win.requestAnimationFrame = callback => {
      if (panel.classList.contains("off")) { held.push(callback); return 0; }
      return raf(callback);
    };
    frame.resume = () => { held.splice(0).forEach(callback => raf(callback)); };
    const setVh = () => doc.documentElement.style.setProperty("--pvh", main.clientHeight / 100 + "px");
    setVh();
    addEventListener("resize", setVh);
    // Each frame is as tall as its content, so the whole tab scrolls as one page.
    const wrap = doc.querySelector(".wrap") || doc.body;
    const fit = () => { frame.style.height = Math.ceil(wrap.getBoundingClientRect().height) + "px"; };
    const fitter = new ResizeObserver(fit);
    fitter.observe(wrap);
    fit();
    doc.addEventListener("click", event => {
      const link = event.target.closest && event.target.closest("a[href]");
      if (!link || event.defaultPrevented) return;
      const href = link.getAttribute("href") || "";
      const key = Object.keys(TAB_LINKS).find(k => href.includes(k));
      if (key) { event.preventDefault(); show(TAB_LINKS[key]); main.scrollTop = 0; return; }
      if (/^https?:/i.test(href)) { event.preventDefault(); openOutside(link.href); }
    });
  }

  function load(name) {
    const frames = [...panels[name].querySelectorAll("iframe")];
    return Promise.all(frames.map(frame => frame.ready || (frame.ready = new Promise(done => {
      frame.addEventListener("load", () => {
        document.getElementById("loading").hidden = true;
        setup(frame);
        done(frame);
      }, { once: true });
      frame.srcdoc = PARTS[frame.dataset.part];
    }))));
  }

  function show(name, focus) {
    if (current) scrolls[current] = main.scrollTop;
    current = name;
    load(name);
    for (const n of names) {
      const on = n === name;
      tabs[n].setAttribute("aria-selected", on);
      tabs[n].tabIndex = on ? 0 : -1;
      panels[n].classList.toggle("off", !on);
    }
    panels[name].querySelectorAll("iframe").forEach(frame => frame.resume && frame.resume());
    main.scrollTop = scrolls[name] || 0;
    if (focus) tabs[name].focus();
    if (location.hash !== "#" + name) history.replaceState(null, "", "#" + name);
  }

  document.getElementById("open-guide").addEventListener("click", async () => {
    show("cad");
    const [frame] = await load("cad");
    const doc = frame.contentDocument;
    const button = doc && doc.getElementById("mode-build");
    if (button) button.click();
    const viewer = doc && doc.getElementById("viewer");
    main.scrollTop = viewer ? Math.max(0, viewer.getBoundingClientRect().top - 120) : 0;
  });

  for (const n of names) tabs[n].addEventListener("click", () => show(n));
  document.querySelector("[role=tablist]").addEventListener("keydown", event => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    const i = names.indexOf(current);
    show(names[(i + (event.key === "ArrowRight" ? 1 : names.length - 1)) % names.length], true);
  });

  function fromHash() {
    const raw = location.hash.slice(1);
    const name = OLD_NAMES[raw] || raw;
    return names.includes(name) ? name : null;
  }
  addEventListener("hashchange", () => { const n = fromHash(); if (n && n !== current) show(n); });

  const start = fromHash() || "render";
  show(start);
  // Load the other tabs in the background once the first is up, so switching is instant.
  load(start).then(() => setTimeout(() => names.filter(n => n !== start).forEach(load), 300));
}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()

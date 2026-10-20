# Mark II-R's model document, generated from what Ballast saved: which
# sections fill themselves, which are empty, who must write the rest.
import textwrap

from ballast import governance as gv

inv = gv.load_inventory()
text, state = gv.document("MK2R", inv)
gv.OUT.mkdir(parents=True, exist_ok=True)
(gv.OUT / "MK2R.md").write_text(text + "\n")

for title, source in gv.DOC_TEMPLATE:
    print(f"{title:<40}{state[title]:>10}")
print()
lines = text.splitlines()
start = lines.index("## The model itself")
for ln in lines[start:start + 3] + lines[lines.index(
        "## Calibration and use as a probability"):][:3]:
    print("\n".join(textwrap.wrap(ln, 66, subsequent_indent="  "))
          or "")

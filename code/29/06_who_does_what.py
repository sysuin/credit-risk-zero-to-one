# Who does what at Fernhill: each role's line of defence and its part
# in the tasks of model risk and credit (R does, A answers for it,
# C is asked first, I is told).
import textwrap

from ballast import governance as gv

for line in gv.raci_lines():
    print(line)
print()
for name, line, who in gv.ROLES:
    print("\n".join(textwrap.wrap(f"{name:<8}{line}  {who}", 68,
                                  subsequent_indent=" " * 11)))
one_a = all(codes.split().count("A") == 1 for codes in gv.RACI.values())
print(f"\none role answers for each task: {one_a}")

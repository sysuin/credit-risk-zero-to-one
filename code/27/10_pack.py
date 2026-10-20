# The risk committee pack for January 2026, written by Ballast from
# what every earlier chapter saved, and saved for the meeting.
from ballast import report

text = report.pack()
print(text, end="")
lines = text.splitlines()
print(f"\n[saved to {report.save(text)}; {len(lines)} lines, widest "
      f"{max(len(s) for s in lines)}]")

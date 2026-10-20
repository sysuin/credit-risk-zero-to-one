# The monitoring pack for December 2025, written by Ballast and saved
# beside its other output.
# timeout: 600
import fernhill
from ballast import monitoring as mon

con = fernhill.connect()
text = mon.pack(con)
path = mon.save_pack(text)
print(text, end="")

# The life of application A00000004, from every table it touched.
import fernhill
from ballast.lifecycle import print_life

print_life(fernhill.connect(), "A00000004")

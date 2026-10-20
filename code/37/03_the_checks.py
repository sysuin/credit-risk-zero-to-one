# Run the verifier and count its checks, section by section.
import contextlib
import io

from fernhill import verify

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    failed = verify.main()
sections, current = [], None
for line in buf.getvalue().splitlines():
    if line and not line.startswith(" "):
        current = [line, 0, 0]
        sections.append(current)
    elif line.strip().startswith(("PASS", "FAIL")):
        current[1] += 1
        current[2] += line.strip().startswith("PASS")
print(f"{'section':<56}{'checks':>6}{'pass':>6}")
for title, n, ok in sections:
    print(f"{title[:55]:<56}{n:>6}{ok:>6}")
print(f"{'all':<56}{sum(s[1] for s in sections):>6}"
      f"{sum(s[2] for s in sections):>6}")
print("verifier exit status", failed)
print()
SHOW = ("mean bureau score, v3 minus v2",
        "take-up, minus_150 arm minus plus_150 arm",
        "latent quality, booked minus walked away",
        "declined personal applicants' true 12-month bad rate",
        "fraud accounts missing their first payment",
        "missed a payment Oct 2020-Jun 2021: holiday / none",
        "defaulted cards: utilisation 12 months before",
        "cured next month: call_first minus sms_first",
        "emergency loans ever 90 days past due",
        "internal grades unchanged at annual review")
for line in buf.getvalue().splitlines():
    body = line.strip()[6:]
    for label in SHOW:
        if body.startswith(label):
            value = body[58:].split()[0]
            if "/" not in value:
                value = f"{float(value):.3f}"
            print(f"  {label[:52]:<52}{value:>12}")

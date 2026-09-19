"""
Watches the tansik page. That page hides sections with CSS rules in its <style> block,
e.g.  .results{visibility:hidden;display:none}
When the .results rule stops hiding, you get a WhatsApp message (via the free CallMeBot API).

Setup:
    pip install requests
    Get your CallMeBot API key (see the steps in the chat), then fill in PHONE and API_KEY below.
Run on your PC (loops forever):   python tansik_watcher.py
Run once (used by GitHub Actions): python tansik_watcher.py --once
"""
import os
import re
import sys
import time
import requests

# ---------- EDIT THESE (or set them as environment variables / GitHub secrets) ----------
URL = os.environ.get("TANSIK_URL", "PASTE_THE_PAGE_ADDRESS_FROM_YOUR_BROWSER_HERE")
CSS_CLASS = "results"                      # the section to watch
CHECK_EVERY = 60                           # seconds between checks
PHONE = os.environ.get("CALLMEBOT_PHONE", "+20XXXXXXXXXX")       # your WhatsApp number with country code
API_KEY = os.environ.get("CALLMEBOT_APIKEY", "YOUR_CALLMEBOT_APIKEY")  # key the CallMeBot bot sends you
MESSAGE = "النتيجة ظهرت! Results are showing on the tansik site."
# --------------------------------

HEADERS = {"User-Agent": "Mozilla/5.0"}
KNOWN_CLASSES = ("choices", "transfer", "qodReg", "limits", "studentData", "qodResults")


def class_is_visible(html, css_class=CSS_CLASS):
    """True if the page's <style> rule for .css_class no longer hides it."""
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S | re.I))
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)  # the site injects random /*123*/ comments, drop them
    rules = {
        m.group(1): m.group(2).replace(" ", "").lower()
        for m in re.finditer(r"\.([\w-]+)\s*\{([^}]*)\}", css)
    }
    if not any(k in rules for k in KNOWN_CLASSES):
        # page didn't load properly / layout changed: don't guess, don't alert
        raise RuntimeError("Page looks different than expected (no known CSS rules found)")
    rule = rules.get(css_class)
    if rule is None:
        return True  # rule was removed entirely -> section is no longer hidden
    return not ("display:none" in rule or "visibility:hidden" in rule)


def check():
    r = requests.get(URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return class_is_visible(r.text)


def notify():
    try:
        r = requests.get(
            "https://api.callmebot.com/whatsapp.php",
            params={"phone": PHONE, "text": f"{MESSAGE}\n{URL}", "apikey": API_KEY},  # requests url-encodes this
            timeout=30,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        code = getattr(getattr(e, "response", None), "status_code", None)
        # don't re-raise the original: its message contains the full URL with your phone + key
        raise RuntimeError(f"CallMeBot request failed (HTTP status: {code})") from None


def run_once():
    """One check, then exit. Used by GitHub Actions (which runs the script fresh every few minutes)."""
    if check():
        notify()
        print("Visible! Notification sent.")
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            with open(out, "a", encoding="utf-8") as f:
                f.write("notified=true\n")
    else:
        print("Still hidden.")


def main():
    notified = False
    print(f"Watching .{CSS_CLASS} on {URL} every {CHECK_EVERY}s...")
    while True:
        try:
            if check():
                if not notified:
                    notify()
                    notified = True  # only marked once the notification actually went out
                    print("Visible! Notification sent.")
            else:
                notified = False
        except Exception as e:
            print("Check failed:", e)
        time.sleep(CHECK_EVERY)


if __name__ == "__main__":
    if "--once" in sys.argv:
        run_once()
    else:
        main()

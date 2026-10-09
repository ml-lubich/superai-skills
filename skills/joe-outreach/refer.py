"""Refer Joseph Heupler by email, through imail (Mail.app).

Run with the imail tool's python so `imail.mail` imports:
  PY=~/.local/share/uv/tools/imail-mcp/bin/python

  $PY refer.py scan [--account michaelle.lubich@gmail.com] [--limit 60] > cands.json
      Inbox messages with no reply yet, sender not in the ledger, no excluded company.
      Prints sender/subject/body so the agent can decide job vs sales and write the reply.

  $PY refer.py send ~/.config/joe-referral/queue.json
      Queue = list of {name, email, company, role, subject, body}. For each: skip if the
      email is already in the ledger or the company is excluded, else send from
      michaelle.lubich@gmail.com, cc Joe, attach his resume, and append to the ledger.
      Sent items leave the queue, so a re-run never double-sends.
"""
import datetime
import json
import re
import sys
from pathlib import Path

from imail import mail

FROM = "michaelle.lubich@gmail.com"
JOE = "jheupler@berkeley.edu"
RESUME = "/Users/mlubich/dev/resumes/resumes/resume_joseph_heupler/resume_joseph_heupler.pdf"
LEDGER = Path.home() / ".config/joe-referral/ledger.json"
SIGNOFF = "\n\nresume attached, more at josephheupler.com.\n\nmisha"
# Kept for Misha, or never contacted. Mirrors the linkedin-outreach Referral Policy.
EXCLUDED = re.compile(r"\b(mach industries|mach|anduril|echostar|dish|amd)\b|perry barrow|w3sourcing", re.I)


def ledger() -> list[dict]:
    return json.loads(LEDGER.read_text()) if LEDGER.exists() else []


def contacted(led: list[dict]) -> set[str]:
    return {x["email"].lower() for x in led if x.get("email")}


def addr(sender: str) -> str:
    m = re.search(r"<([^>]+)>", sender)
    return (m.group(1) if m else sender).strip().lower()


def sent_recipients(account: str) -> set[str]:
    """Every address we already wrote to (Sent Mail), so a stale ledger can't cause a repeat send."""
    out = mail.run_as(f'''tell application "Mail"
set out to ""
set mb to mailbox "[Gmail]/Sent Mail" of account "{account}"
repeat with i from 1 to (count of messages of mb)
 if i > 400 then exit repeat
 repeat with x in to recipients of message i of mb
  set out to out & address of x & linefeed
 end repeat
end repeat
return out
end tell''')
    return {a.strip().lower() for a in out.splitlines() if a.strip()}


def scan(account: str, limit: int) -> None:
    done = contacted(ledger()) | sent_recipients(account)
    out = []
    for m in mail.list_messages(account=account, limit=limit):
        a = addr(m["sender"])
        if a in done or EXCLUDED.search(m["sender"] + " " + m["subject"]):
            continue
        d = mail.get_message_details(account, m["index"])
        if d["was_replied_to"] or EXCLUDED.search(d["body"][:1500]):
            continue
        out.append({**m, "email": a, "body": d["body"][:1500]})
    print(json.dumps(out, indent=1, ensure_ascii=False))


def send(queue_path: str) -> None:
    qp = Path(queue_path)
    queue = json.loads(qp.read_text())
    led = ledger()
    left = []
    for q in queue:
        who = f"{q['name']} <{q['email']}>"
        if q["email"].lower() in contacted(led):
            print("SKIP already contacted", who)
            continue
        if EXCLUDED.search(q["company"] + " " + q["name"]):
            print("SKIP excluded", who)
            continue
        try:
            mail.send_message(
                to=q["email"], subject=q["subject"], body=q["body"] + SIGNOFF,
                from_addr=FROM, cc=JOE, attachments=[RESUME], is_markdown=False,
            )
        except Exception as e:  # keep it queued, report loudly, move on to the next person
            print("FAIL", who, e)
            left.append(q)
            continue
        led.append({"name": q["name"], "email": q["email"], "company": q["company"],
                    "role": q.get("role", ""), "date": str(datetime.date.today()), "channel": "email"})
        LEDGER.write_text(json.dumps(led, indent=1))  # write per send so a crash can't cause a resend
        print("SENT", who)
    qp.write_text(json.dumps(left, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "scan":
        args = sys.argv[2:]
        acct = args[args.index("--account") + 1] if "--account" in args else FROM
        lim = int(args[args.index("--limit") + 1]) if "--limit" in args else 60
        scan(acct, lim)
    elif cmd == "send" and len(sys.argv) == 3:
        send(sys.argv[2])
    else:
        sys.exit(__doc__)

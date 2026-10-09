---
name: luma
description: Automate browsing and registering for events on Luma (lu.ma), handling form filling, attendee details, real city/geo fields, custom question answers, ticket selection, and calendar confirmation using agent-browser / cua-driver or the luma CLI.
---

# Luma Event Registration & Form Automation Skill (`luma`)

Automate browsing, discovering, and registering for tech talks, hackathons, meetups, and networking events on **Luma** ([lu.ma](https://lu.ma)).

This skill drives event registration using `agent-browser` (with `cua-driver` fallback for hard bot walls/CAPTCHAs) and automatically fills in attendee details, contact info, professional profiles, and answers common screening questions.

---

## 1. Candidate / User Profile Defaults

When registering for events, use the following profile details:

- **Full Name**: Michael Lubich (First: `Michael`, Last: `Lubich`, Preferred: `Misha`)
- **Email**: `michaelle.lubich@gmail.com`
- **Phone**: `(415) 275-0094` / `4152750094`
- **Location**: San Francisco, CA (the real place written into city, location, neighborhood, and "where are you based" fields)
- **Geo**: coordinates only when the user passes them (`--geo lat,lng`). Leave coordinate fields blank otherwise.
- **LinkedIn**: [https://www.linkedin.com/in/misha-lubich/](https://www.linkedin.com/in/misha-lubich/)
- **GitHub**: [https://github.com/ml-lubich](https://github.com/ml-lubich)
- **Twitter / X**: `@mlubich` (or leave blank if optional)
- **Role / Title**: Senior Software Engineer / AI Systems Engineer
- **Company / Org**: Independent / Manaflow AI

---

## 2. Common Luma Form Question Templates

Luma event organizers often include screening or custom questions. Auto-populate these contextually:

| Question Type | Standard Response |
|---|---|
| **What do you hope to learn / get out of this event?** | "Looking forward to connecting with builders, discussing agentic architectures, and learning about recent technical developments in the space." |
| **What are you building? / Current projects** | "Building agentic engineering infrastructure, autonomous CLI/desktop orchestration tooling, and LLM automation systems." |
| **Company / Organization** | "Manaflow AI" or "Independent" |
| **How did you hear about this event?** | "Tech community / Twitter / Luma recommendations" |
| **Dietary restrictions** | "None" |
| **Are you interested in speaking / sponsoring?** | "Not at this time, attending as a participant." |

---

## 3. Automation Execution Ladder

1. **Level 1 (Fast Headless / CDP)**:
   ```bash
   agent-browser open "<luma_event_url>"
   agent-browser snapshot -i
   ```
2. **Level 2 (Interactive Headed - if Luma session / Google auth needed)**:
   ```bash
   agent-browser --headed open "<luma_event_url>"
   ```
3. **Level 3 (Desktop Fallback / Cloudflare / CAPTCHA)**:
   - Use `cua-driver` desktop computer-use tools to click "Register" or bypass Cloudflare Turnstile if CDP is intercepted.

---

## 4. Step-by-Step Registration Workflow

### Step 1: Open and Inspect the Event Page
```bash
agent-browser open "https://lu.ma/<event_slug_or_id>"
agent-browser snapshot -i
```
- Locate the primary registration button (typically labeled `"Register"`, `"Request to Join"`, or `"Get Tickets"`).
- Note whether the event is:
  - **Instant approval**: "You're in!" / Calendar invite immediately available.
  - **Host approval required**: "Approval Pending" / "Request sent to host".
  - **Paid / Ticket tier**: Select standard General Admission / Free tier unless instructed otherwise.

### Step 2: Trigger Registration Modal
```bash
# Click the registration button by element reference from the snapshot
agent-browser click @e<button_ref>
agent-browser wait 1000
agent-browser snapshot -i
```

### Step 3: Fill Attendee & Screening Fields
Map the fields based on snapshot attributes:
```bash
# Fill Name & Email
agent-browser type @e<name_ref> "Michael Lubich"
agent-browser type @e<email_ref> "michaelle.lubich@gmail.com"

# Optional / Additional fields
agent-browser type @e<phone_ref> "4152750094"
agent-browser type @e<linkedin_ref> "https://www.linkedin.com/in/misha-lubich/"

# Real place. Do not invent a city.
agent-browser type @e<city_or_location_ref> "San Francisco, CA"
```

City, location, neighborhood, and "where are you based" all get the profile location. A different place is an explicit override:

```bash
luma register "https://lu.ma/<event_slug_or_id>" --location "Austin, TX" --geo "30.2672,-97.7431"
```

`--geo` is only for a coordinates / lat,lng field. If the user did not pass coordinates, leave that field empty.

Any other question whose label contains `?` and is not in the table above still gets an answer, built from the real profile (name, title, company, location, bio). Do not skip it, and do not substitute a made-up place. Short unlabeled extras (coupon codes, promo fields) stay empty.
- For radio buttons / checkboxes (e.g. Terms & Conditions, Code of Conduct), click the corresponding element reference:
```bash
agent-browser click @e<checkbox_ref>
```

### Step 4: Submit Registration
```bash
agent-browser click @e<submit_ref>
agent-browser wait 2000
```

### Step 5: Verification & Confirmation
Always verify the result:
1. Re-snapshot the page (`agent-browser snapshot -i`).
2. Confirm success indicators:
   - `"You're Going!"` or `"Registered"`
   - `"Approval Pending"` or `"Request Submitted"`
   - `"Add to Calendar"` button visible
3. Clean up the browser when done:
   ```bash
   agent-browser close
   ```

---

## 5. Clean-up & Safety Rules

- Machine is shared by multiple agent sessions: **Always close `agent-browser` when done.**
- Never attempt payments or input credit card information without explicit user direction.
- Do not bypass gated paid tickets.

# SitePilot - Complete Project Documentation

Consolidated project documentation.

---

## Source: README.md

# SitePilot AI — Project Media & Sales Contacts (V7)

Full React + FastAPI + PostgreSQL + self-hosted Ollama project, updated from the Client Experience Release V6.

Read **CONTACTS_AND_MEDIA_V7_GUIDE.md** for changes, setup, API endpoints, security rules and verification caveats. Do not add real `.env` files or database backups to source control.


---

## Source: AUTH_FLOW_V7_1_GUIDE.md

# SitePilot V7.1 — Buyer Sign-in & Sales Invitations

This release was built against the **user-provided SitePilot_Latest_Update7.zip**, not an earlier template. It retains the original application functionality. It is **not a production authentication system** yet: phone numbers are not verified using OTP and there is no password-reset email/SMS service or rate limiting.

## Root causes

1. JWT verifies an **already established buyer session**. It does not create a password account. `/api/v1/buyer/auth/login` checks `BuyerCredential` using `(project_id, normalized_phone, password_hash)`. Older visits from the `/api/v1/leads` flow have JWTs but no corresponding password credential unless claimed during the valid session. Wrong project/password also produces HTTP 401.
2. The booking UI rejected **existing-account sign-in** if the name was blank and if *optional* contact consent was unchecked. This release fixes that bug.
3. The previous seed script creates only an initial `SalesUser`. There was no public sales signup by design; this release adds **invitation-only activation**, with invitations issued by the sales head.
4. Running `python -m app.seed` does not update the password of any sales account already present in PostgreSQL. Changing `DEMO_SALES_PASSWORD` alone will not update existing credentials.

## Files changed

- `backend/sitepilot_backend/app/main.py` — head-only team list and invitations, invite acceptance endpoint, V7.1 build label
- `backend/sitepilot_backend/app/models.py` — `SalesInvitation` table; only a hash of the secret code is stored
- `backend/sitepilot_backend/app/sales_account_admin.py` — development-only account listing and password reset through hidden terminal input
- `backend/sitepilot_backend/tests/test_sales_invitation.py` — API tests for invitation security and buyer legacy session claim
- `backend/sitepilot_backend/tests/test_chat_runtime_v3.py` and `test_chat_runtime_v51.py` — updated build-label expectations
- `frontend/src/routes/book.tsx` — sign-in no longer incorrectly needs name or consent
- `frontend/src/routes/buyer.visits.tsx` — create-account / sign-in tabs and clear legacy-booking messaging
- `frontend/src/routes/sales.tsx` — invited new executive can activate account from the existing sign-in screen
- `frontend/src/routes/sales.admin.tsx` — head-only "Sales team · invite a new executive" panel
- `frontend/src/lib/sitepilot-api.ts` and `frontend/src/lib/sales-auth.tsx` — API client and authorized role types

## Install over your working V7 folder (small patch recommended)

1. **Backup your database** and the existing project folder first. Keep the existing `.env` confidential.
2. Stop the current FastAPI and frontend processes (`Ctrl+C`).
3. Extract the PATCH ZIP **into the parent folder that already contains `sitepilot_m6`**, replacing matching source files. Do not delete your existing frontend `node_modules` or backend `.venv`.
4. Open `sitepilot_m6/backend/sitepilot_backend` in a VS Code terminal and activate its current virtual environment.
5. Run `python -m app.seed` **on your local development database only** to create the new `sales_invitations` table. This does not replace existing user passwords or delete appointments. Use formal migrations instead for production.
6. Run `python -m pytest -q` and start the backend: `python -m uvicorn app.main:app --reload --port 8000`.
7. Open your existing frontend folder, run `npm run build` and then `npm run dev`.
8. Check `http://127.0.0.1:8000/health` for `"build": "sitepilot-auth-flow-v7.1"`. Hard-refresh the browser.

## Buyer workflow

- `/buyer/visits`: select the **same project** used when registering; switch between **Sign in** and **Create account**.
- Buyer accounts are project-scoped. New account registration does not automatically import older lead bookings.
- To link a **legacy booking**, return to `/buyer/visits` in the **same browser session** that still has the original valid buyer JWT and use **Secure session**. You must know the session token; phone ownership alone is not proof.
- If the legacy JWT has expired or the browser session was cleared, an OTP-based identity verification or manual, identity-verified support process is required. The app intentionally does not attach previous bookings merely because a phone number matches.
- Booking page `/book`: existing-account **Sign in** now only requires phone + password; **Create account** requires name, phone and password (10+ characters). Follow-up consent is optional.

## Sales account activation

1. Seeded sales head signs in at `/sales` with the **stored** database password, not necessarily the current `.env` seed value.
2. Visit **Projects, facts & slots**. At the top, the sales head sees **Sales team · invite a new executive**.
3. Enter the new executive's display name and email. Copy the secret code (shown **once**, valid 48 hours) and share it privately.
4. The executive visits `/sales` → **New sales executive? Activate an invitation**, enters matching email, code, and a new password (12+ characters).
5. After successful activation, switch to **Sign in** and log in normally. Other sales staff cannot invite colleagues, and public signup is unavailable.

**Note:** The project-specific salesperson contact card (`ProjectSalesperson`) is separate from the staff login account (`SalesUser`). Adding a public contact does not create a login.

## Fix a pre-existing local demo sales password

If you have changed the demo password in `.env` after seeding, the password **stored in PostgreSQL** will still be the previous one. From the backend directory:

```powershell
python -m app.sales_account_admin list
python -m app.sales_account_admin reset-password --email reviewer@example.test
```

Use the actual email returned by the `list` command instead of assuming the example. The reset script will prompt twice for a fresh password **without echoing it**. This script is **disabled in production**. Restart or refresh the sales page and log in with the new password.

## Tests / limitations

- `python -m pytest -q`: **106 passed** in the isolated Linux/SQLite environment while building the patch.
- All **78** frontend TS/TSX source files passed a TypeScript parser syntax check.
- Frontend build, PostgreSQL live test, buyer UI in a browser, and the running Ollama integration still require verification on your Windows machine.
- This patch does not implement buyer phone OTP, password recovery, staff invite email delivery, invite resend UI, authentication rate limiting, or production database migrations. Do not put real client information into public demo accounts.

## Secrets

Your uploaded ZIP contained a real `.env` file and installed dependencies. The provided patch and full-source ZIP intentionally exclude `.env`, `.venv`, `node_modules`, and caches. Rotate any secrets exposed outside your machine (database password, JWT signing key and demo account password) before public deployment.


---

## Source: CHANGELOG_V5.md

# V5 engineering change log

| Area | Change | Failure behavior |
|---|---|---|
| Ollama | Reuse centralized allowed-host/redirect-safe HTTP JSON transport | `LocalAgentUnavailable`; no untrusted body propagated |
| Conversation memory | Load latest 10 rows by **authenticated lead_id** | Missing history simply yields first-turn conversation |
| Contextual reply | JSON-schema `acknowledgement` and `follow_up_question` | Malformed/unsafe response discarded; backend template returned |
| Fact retrieval | Select explicitly approved revisions by relevant fact key | Unapproved revisions never read into answer; unknown information acknowledged |
| Booking/handoff | Deterministic protected backend path unchanged | No unconfirmed booking or autonomous human handoff |
| Chat UI | V5 build indicator and lightweight response-origin hint | Prior messages remain unchanged and readable |
| Tests | New policy, scope, memory, safety and API regression cases | 88 offline backend tests passed; local live model not tested |

## Inference boundary

```
Buyer (authenticated JWT)  -> FastAPI /buyer/conversations/messages
                                     |
                            PostgreSQL message history (same lead only)
                                     |
                            SitePilot intent decision (Ollama)
                                     |
           +-------------------------+----------------------------+
           |                         |                            |
   booking / handoff          approved project facts      general / hesitation
       backend only              backend only              local JSON dialogue
           |                         |                            |
      slots/actions          approved revision data         validation gate
           |                         |                            |
           +-------------------------+----------------------------+
                                     |
                            persist assistant answer
                                     |
                                 React chat
```

The validation gate is intentionally conservative, not a proof that natural-language hallucinations are impossible. Product claims must be rendered from approved server-owned data and should be reviewed before customer use.


---

## Source: CHAT_CONTEXT_FIX_README.md

# SitePilot chat context and language fix

## Why the same response appeared

The original local agent classifies the message with Qwen/Ollama, then intentionally disregards the model's `reply` and selects a backend-owned safe template. If the local model returned `general` for a clearly expressed family concern, that path produced the generic English assistance text. A message such as `Kya aap hindi me baat kr skte h?` also kept the UI's `en` setting and so returned the same English text.

## What's fixed

- Grounded family-decision hesitation: an explicit family member plus a negative opinion is recognized even if the model labels it `general`. Recorded evidence must be a literal substring of the buyer message.
- Contextual family response in English, Hindi and Gujarati. No claims about real property facts or guaranteed outcomes.
- Romanized Hindi and Gujarati language-switch requests and native Hindi/Gujarati scripts detected even if the UI selector is English.
- Chat now updates the language selector when the backend reports a language change, preserving it for subsequent messages.
- Structured Ollama classification, verified facts, explicit booking confirmation, human handoff and endpoint allowlist are preserved.

## Verification

`cd backend/sitepilot_backend` then `python -m pytest -q`: 56 passed (50 existing plus 6 regression tests).

These tests exercise decision normalization and response-policy logic offline; live Ollama inference and the frontend build have **not** been verified in this environment.

## Install without losing local data

1. Make a backup of your current source. Extract this ZIP to a new directory.
2. Preserve your local `backend/sitepilot_backend/.env` file. **Do not post it or commit it.** The ZIP contains only a sanitized `.env.example`.
3. Use your existing PostgreSQL database. No migration is required for this fix.
4. In backend directory: activate your venv, `python -m pip install -r requirements.txt`, `python -m pytest -q`, then `uvicorn app.main:app --reload --port 8000`.
5. In frontend directory: `npm ci` and `npm run dev`.
6. Hard-refresh the chat page. Send `I found this property very good and I am interested in this but my wife is not happy with this property`; expect a non-pushy family question. Send `Kya aap hindi me baat kr skte h?`; expect a Hindi response and the selector to change to Hindi.

For further unrecognized concerns, the response may still be generic. This update fixes the observed defects rather than claiming unconstrained full conversational intelligence. The local model's generated factual assertions remain blocked pending a more sophisticated fact-grounded generation layer.


---

## Source: CHAT_RUNTIME_V3_FIX.md

# SitePilot Chat Runtime V3 — corrected reply behavior

## Why earlier screenshots still showed generic text
The chat UI restores stored conversation messages from PostgreSQL on page load. Replies stored before a code fix are **historical records** and cannot be retroactively rewritten. The old generic responses alone do not establish whether the corrected backend was used for a *new* request. Also, a previous ZIP only patched the sales-head authorization tests; it did not add an end-to-end version indicator.

## Changes
- `/health` now identifies the running build as `chat-runtime-v3`.
- The chat UI displays the backend build. If it shows `older backend` or `unreachable`, check `VITE_API_BASE_URL` and restart the correct backend.
- The UI explicitly labels restored conversation history and asks you to send a new message to test changes.
- Explicit language-switch requests use deterministic localized acknowledgement even when Ollama fails; no local-model call is needed for that simple control request.
- A buyer's explicit disagreement with a family member is honored even when Ollama mistakenly assigns `project_facts`; booking and human-handoff requests retain priority.
- Family-concern grounding is applied in the HTTP endpoint as a defense in depth.
- Offline backend suite now passes 60 tests, including HTTP tests of language switch and family hesitation.

## Apply locally
1. Stop the old FastAPI process (Ctrl+C in its terminal), and stop the old frontend dev server. Be sure neither remains running at ports 8000 or 8081.
2. Extract the supplied ZIP into a NEW folder. **Do not run the previous folder.**
3. Copy only your privately stored backend `.env` to the new `sitepilot_m6/backend/sitepilot_backend/.env`; do not share or commit it. Keep your existing PostgreSQL database. No migration or re-seeding is needed for this patch.
4. From `sitepilot_m6/backend/sitepilot_backend`, create/activate `.venv` and install `requirements.txt` if needed. Run `python -m pytest -q`, then `python -m uvicorn app.main:app --reload --port 8000`.
5. Open `http://127.0.0.1:8000/health` and verify the JSON includes `"build":"chat-runtime-v3"`.
6. In the NEW `sitepilot_m6/frontend` directory, run `npm ci`, then `npm run dev`. Use the port shown by the terminal (can be 8081). Ensure your `.env.local` `VITE_API_BASE_URL` points at `http://127.0.0.1:8000`.
7. Reload the browser. You should see `Backend build: chat-runtime-v3`. Previously saved generic replies remain in PostgreSQL. Send **new** messages to validate this version:
   - `I am interested in one of your projects but my wife is not happy with the project`
   - `Kya aap hindi me baat kr skte h?`
8. If the build displays old/unreachable, run `Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object OwningProcess` from PowerShell and identify which app owns the port. Also check frontend `.env.local`.

## Scope and limitations
- No secrets are included; don't post `.env` contents or JWT tokens.
- Offline backend suite: **60 passed**.
- Frontend build and live Ollama/PostgreSQL browser journey are **not verified in this environment**.
- Replies remain policy-controlled templates. This is a targeted correctness fix, not a fully open-ended generative conversation engine.


---

## Source: CHAT_RUNTIME_V4_FIX.md

# SitePilot AI — Chat Runtime V4 (school concern + explicit English switching)

This release builds on Chat Runtime V3; it does not change the PostgreSQL schema or booking API.

## Fixes

1. A buyer's explicit `Reply in english` or `Please continue in English` overrides the previously selected Hindi/Gujarati response language. The server sends `response_language: "en"`; the existing frontend updates its language selector accordingly. A language-switch acknowledgement does not require Ollama.
2. A clearly stated school-distance/travel concern is classified as an **explicit location objection**, even when the model returned `general` or `project_facts`, and receives a targeted acknowledgement and follow-up rather than the generic project options menu.
3. All three language templates for school-distance concerns refrain from inventing a school's location, commute time, amenities, or suitability.
4. `/health` and chat responses identify the backend as `chat-runtime-v4`; the frontend build indicator expects the same string.

## How to upgrade

* Extract to a new directory; copy your **private** `.env` to `backend/sitepilot_backend/.env`. Do not commit this file.
* Use your existing local PostgreSQL database; **no migration or re-seed is needed**.
* Stop old FastAPI and frontend processes. Start both applications **from this release's directories**. Existing browser chat history from PostgreSQL will remain unchanged; send new messages to verify behavior.
* Verify `http://127.0.0.1:8000/health` includes `"build":"chat-runtime-v4"`.
* Re-run `python -m pytest -q` from `backend/sitepilot_backend`; offline suite result in the build environment: **69 passed**.

### Suggested live test

1. Select Hindi. Send `My wife is worried because the school is too far away and our child is only five years old.` Expect a Hindi response acknowledging school access, and a `location` concern without unsupported distance claims.
2. Send `Reply in english`. Expect an English acknowledgement and dropdown switching to English.
3. Send `What if the school is 30 minutes away?` The current assistant remains template/policy-driven; more nuanced multi-turn memory and contextual reasoning are **not** part of this targeted patch.

## Verification limits

The 69 Python tests use a test database and mocked local-model behavior. Live Ollama inference on the user's computer, a complete frontend production build, and PostgreSQL concurrency remain unverified here.


---

## Source: CHAT_RUNTIME_V5_1_FIX.md

# SitePilot AI — V5.1 Latest-Message Routing Fix

**Base:** SitePilot Chat Runtime V5 contextual agent. **Backend build:** `chat-runtime-v5.1`.

This is a targeted bug fix, not a new foundation-model training run. It does not require schema migrations, re-seeding, reinstalling Ollama, or deleting prior conversations.

## Confirmed failure

A local V5 screenshot demonstrated two problems:

1. After a family concern, the question **“What project details are verified?”** was incorrectly answered using family context. The current message had been classified as `general`, allowing the contextual dialogue writer to borrow an irrelevant older topic.
2. **“My home loan is pending.”** received a generic menu because the current financing hesitation was not reliably recognized and unsafe/off-topic model drafts could fall back to a generic template.

## Changes

- `app/agent.py`: deterministic latest-message routing for verified project-fact requests and explicitly pending loans. Older context cannot override these intents. The financing fallback now acknowledges a pending loan without promising approval.
- `app/agent.py`: approved-fact answers use **only sales-head-approved fact revisions**, never seed/demo pricing or unreviewed project registration values. For a broad fact-summary question, all published approved revisions are listed; otherwise only query-relevant revisions are used. With none approved, the reply clearly says so.
- `app/conversation.py`: a fact request is not eligible for freeform conversation drafting even if the intent model mistakenly labels it `general`. A finance-specific off-topic English draft is rejected and replaced with the safe financing response. The composer is explicitly instructed to prioritize the latest message.
- `app/main.py`: enforces those routing guards after classification, including when model classification is erroneous, and sets the backend build tag to `chat-runtime-v5.1`.
- `frontend/src/routes/chat.tsx`: adjusts the version indicator to expect V5.1.
- `tests/test_chat_runtime_v51.py`: adds regression checks for exact reported messages, historical family context, approved-only facts, loan classification, and off-topic model output.

## Install on Windows

**Option A — Full ZIP:** Extract into a new folder. Copy your private backend `.env` from V5 (not an old example). Use the existing PostgreSQL database. Run frontend and backend from the *new* project directory.

**Option B — Small patch ZIP:** Copy the following paths from the patch into the corresponding *V5* source folder, preserving subfolders:

- `backend/sitepilot_backend/app/agent.py`
- `backend/sitepilot_backend/app/conversation.py`
- `backend/sitepilot_backend/app/main.py`
- `backend/sitepilot_backend/tests/test_chat_runtime_v51.py`
- `backend/sitepilot_backend/tests/test_chat_runtime_v3.py`
- `frontend/src/routes/chat.tsx`

Stop both old servers before restarting. Run:

```powershell
# From backend/sitepilot_backend (with .venv active)
python -m pytest -q
python -m uvicorn app.main:app --reload --port 8000

# From frontend (second terminal)
npm run dev
```

Open `http://127.0.0.1:8000/health` and confirm `"build":"chat-runtime-v5.1"`. Open the frontend, hard-refresh, and send *new* messages. Previously saved chat history remains visible and is not rewritten.

## Acceptance prompts

1. `My wife is not happy with the property.` — should acknowledge a family decision concern.
2. `What project details are verified?` — should show **only** approved revisions, or say none have been published. It should not continue talking about the wife.
3. `My home loan is pending.` — should acknowledge financing uncertainty, avoid approval guarantees, and avoid unrelated family discussion.
4. `I would like to book a site visit.` — should still use the backend-owned slot/confirmation flow.

To diagnose new messages, inspect the chat API response's `reply_strategy`, `grounding_status`, `hesitation`, and `build`. These diagnostic fields are not proof of live-model quality.

## Verification and limitations

- **92 local offline backend tests passed**, using mocked local model responses and isolated SQLite test databases.
- A live request to your Ollama model, a PostgreSQL concurrency test, and the full frontend browser/build verification still require your Windows environment.
- The narrow fact-intent and finance-topic guards are heuristic. They prevent the two demonstrated failures, but cannot guarantee every conversational reply is relevant, accurate or non-hallucinatory.
- Existing demo project data is illustrative. Approve *actual* property facts through the sales-head workflow before providing a real buyer with verified information.
- No real credentials are included in the ZIP. Never share `.env`, tokens or customer data.


---

## Source: CHAT_RUNTIME_V5_GUIDE.md

# SitePilot AI — V5: context-aware local agent

**Base:** Chat Runtime V4. **Build tag:** `chat-runtime-v5`.

This is a complete source ZIP, not the final two-document assignment submission. SitePilot remains a FastAPI + PostgreSQL + React application. The private open-weight LLM is **Qwen2.5 1.5B via Ollama**, combined with the previously trained synthetic-data intent classifier. No Gemini/OpenAI API key is needed.

## What changed

- **Context-aware conversation drafting:** For ordinary or hesitation conversations, V5 makes a second, structured Ollama call with up to 10 recent messages from the *authenticated buyer's own lead*. Recent history is bounded to 2,600 characters. The model generates an acknowledgement and at most one question; it does **not** get an open-ended ability to answer property facts or execute actions.
- **Persistent memory:** Message history remains in the existing PostgreSQL `messages` table. It is read on every chat turn and is scoped by buyer authentication. No new schema or migration is required. This is a bounded conversation window, **not** lifelong memory or model fine-tuning.
- **Structured validation:** The backend accepts only the two allowed JSON fields, validates language/script, length, at most one question, and known unsafe property or action claims. Rejected output uses existing backend templates. This validator is defense in depth; pattern matching **cannot guarantee** that every hallucination is caught.
- **Protected actions:** Property facts, booking options, booking confirmation and human handoffs still use backend-owned endpoints and approved records. A model-generated statement cannot commit an appointment, submit a handoff, or publish a sales fact. Responses provide `reply_strategy` and `context_turns_used` for diagnostics.
- **Approved-fact relevance:** Queries that refer to an approved fact key such as `parking` can retrieve its exact sales-head-approved value from PostgreSQL. Pending or rejected revisions remain excluded.
- **UI:** Displays `Backend build: chat-runtime-v5`; newly generated contextual replies carry a small provenance caption. Previous chat history is unchanged.

## Windows local setup (no Docker required)

1. Download and extract this ZIP into a new folder. Use the included `sitepilot_m6` directory as the project root.
2. Install Ollama; from a new PowerShell terminal run:

   ```powershell
   ollama pull qwen2.5:1.5b
   ollama run qwen2.5:1.5b
   ```

   Enter `/bye` to exit interactive chat. The Ollama service normally stays available at `http://127.0.0.1:11434`.
3. Ensure your **existing** local PostgreSQL database is running. From the previous project, copy your **private** `backend/sitepilot_backend/.env` to the new backend. Do not commit it; do not delete or overwrite your existing PostgreSQL data. Review `DATABASE_URL`, `JWT_SECRET`, `SITEPILOT_MODEL_URL`, `SITEPILOT_MODEL`, and role settings. If you are starting a brand-new demo database, `python -m app.seed` initializes it; **do not run seed/migrations unnecessarily on an existing populated database**.
4. Run in the backend directory:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   python -m pytest -q
   python -m app.preflight
   python -m app.v5_smoke
   python -m uvicorn app.main:app --reload --port 8000
   ```

   If a virtual environment already exists in the extracted directory, reuse it instead of creating another.
5. In another terminal, from `frontend`:

   ```powershell
   Copy-Item .env.example .env.local
   # Set VITE_API_BASE_URL=http://127.0.0.1:8000 in .env.local
   npm ci
   npm run dev
   ```

6. Confirm `http://127.0.0.1:8000/health` reports `"build": "chat-runtime-v5"`. Open the frontend `/chat`. Old messages from PostgreSQL remain visible as history; send **new** messages to test V5.

## Suggested acceptance conversation (same buyer session)

1. `I like the apartment, but my wife is worried about school travel.` — expect acknowledgement of the family concern, not an unsupported school-distance claim.
2. `What if the trip takes half an hour every day?` — expect a context-specific question about acceptable school travel, not the generic project menu. A contextual draft should return `"reply_strategy":"local_model_contextual"` in the chat API response.
3. `Kya aap hindi me baat kr skte h?` — expect the established deterministic Hindi switch.
4. `स्कूल बहुत दूर हो तो क्या करें?` — expect a Hindi response; if model output is unsafe or invalid, the server template is used.
5. `Reply in english` — expect deterministic English acknowledgement.
6. `What is the confirmed possession date?` — expect only approved information or explicit uncertainty; the model must not invent an answer.
7. `I want to book a site visit.` — expect actual slot offers, an **explicit buyer confirmation** step, and no autonomous booking.
8. Test `/sales/admin` fact approval. Pending revisions must remain absent from buyer-visible facts.

## Diagnostics

The chat API response adds:

- `reply_strategy = local_model_contextual`: validated local-model dialogue was used.
- `reply_strategy = server_template_fallback`: local draft was unavailable or failed validation; earlier safe template used.
- `reply_strategy = server_controlled`: a booking, fact, language preference or handoff pathway was handled by FastAPI.
- `context_turns_used`: number of recent buyer-scoped stored messages used for contextual drafting (0 for non-contextual replies).

**Two model calls** are used for conversational requests: classification and then limited-purpose drafting. Small local models may respond slowly. `SITEPILOT_MODEL_TIMEOUT=35` applies to each call. Do not expose Ollama publicly; configure private model hosting and `SITEPILOT_MODEL_ALLOWED_HOSTS` when deploying.

## Verification scope and limitations

- **Offline backend tests** cover model transport mocks, per-buyer context isolation, historical message window, multilingual rules, refusal of unsafe claims, project facts and booking controls.
- **Not verified in the build environment:** live Ollama inference with the user's installed model, the frontend production build (npm cache unavailable), live PostgreSQL concurrency test, and full browser E2E testing.
- The model has **not** been retrained or fine-tuned in V5; the existing trained lightweight intent classifier remains part of the system.
- Response policy uses lexical checks and deterministic routing, **not formal factual entailment**. Treat the assistant as a demo until tested with real conversations, adversarial prompts, and approved project data.
- Existing local chat records and prior unsafe replies are not automatically rewritten or deleted.
- Real buyer messages sent to a deployed model host would leave the FastAPI process; keep inference on a trusted private network and define an appropriate retention/privacy policy.


---

## Source: CONTACTS_AND_MEDIA_V7_GUIDE.md

# SitePilot AI — Project Images & Sales Contact Release

**Build:** `sitepilot-contact-media-v7`  
**Based on:** SitePilot Client Experience Release V6.  
**Status:** Backend regression and acceptance tests passed; frontend source parses, but full npm/browser build must run on your Windows machine.

## What has changed

1. **Add project** — The Sales Workspace > **Projects, facts & slots** > **Add new project** form now supports an *optional* project photo and name, title, phone and email for the first project salesperson. The project and contact are created as drafts; contact information and photographs **are not public until a sales head reviews them**. More contacts and photos can be added later.
2. **Manage project photographs** — Upload up to eight JPEG, PNG or WebP images per project, up to **3 MB each** (minimum 100 × 100 pixels, maximum 8 megapixels). FastAPI decodes and re-encodes the photos as JPEG to strip metadata and reject nonimage payloads. Files are stored in the PostgreSQL `project_images` table (not an ephemeral local web-server directory). The sales head can approve or hide each photograph. The most recently uploaded **approved** photograph becomes the public project-card and project-detail image. If no approved photo exists, the interface uses a clearly marked illustrative image or placeholder.
3. **Add/edit salesperson details** — Each project can have multiple sales contact cards. An authenticated salesperson may add/edit name, role/title, phone, email and active status. **Changes reset approval**, preventing unreviewed contact information from being shown to buyers. Sales-head approval is required for public visibility. These contact cards are **public-facing directory entries**, not new staff login accounts.
4. **Talk to salesperson** — When the buyer clicks the chat handoff button, the project’s **approved, active** contacts appear as phone and email links, and a signed-in enquiry is still recorded in the sales handoff queue. This is **not** a live chat, guaranteed instant callback, or automatic assignment to a specific employee. If buyers have not yet created an enquiry, the button can display approved contacts without claiming that a callback was requested.
5. **Footer** — Replaced the screenshot’s illustrative-demo disclaimer with a **Contact SitePilot** section. It displays official contact details set through environment variables, falling back to an approved project sales contact. If none have been published, it shows an enquiry link rather than fictional contact details.
6. **Project details** — Approved project salesperson cards are also visible on public project pages, with accessible phone and email actions.

## Your local Windows setup

1. Back up your **existing PostgreSQL `sitepilot` database** before updating; do **not** delete it. Close the old frontend and backend servers.
2. Extract the new ZIP into a separate directory (keep V6 as a rollback copy). Copy your existing **private** `backend/sitepilot_backend/.env` into the new backend directory. **Never upload that file to GitHub.**
3. Backend: from `backend/sitepilot_backend`, activate your Python virtual environment, run `python -m pip install -r requirements.txt` to install the new `python-multipart` and Pillow dependencies; then run `python -m app.seed` **only on your local development database**. It runs SQLAlchemy `create_all`, adding the new `project_salespeople` and `project_images` tables without deleting old rows. For production deployment, use versioned migrations and a tested rollback plan instead of a seed command.
4. Run `python -m pytest -q`. Start FastAPI with `python -m uvicorn app.main:app --reload --port 8000`.
5. Frontend: from `frontend`, run `npm ci`, `npm run build` and `npm run dev`. Confirm `/health` returns build `sitepilot-contact-media-v7`.
6. In the sales workspace, **Add new project**, fill the first salesperson’s details and optionally select a photo. The new project stays a draft until its required RERA registration and another project fact are reviewed and the sales head publishes it. On a published project, the sales head must **separately approve** photos and contacts for buyers to see them.
7. Click **Talk to salesperson** on the buyer chat, then open the public project page to verify approved contact details. Inspect the homepage footer: it displays real approved contact details, not the former disclaimer.

Optional site-wide contact details in your private `.env`:

```dotenv
SITEPILOT_PUBLIC_CONTACT_PHONE=+91YOUR_OFFICIAL_PHONE
SITEPILOT_PUBLIC_CONTACT_EMAIL=office@yourcompany.example
```

If both are empty, the footer uses an approved, active contact from a published project. **Do not copy example phone numbers or emails into your public site**; enter genuine business-owned details and ensure the salespeople agree to public listing.

## API additions

- `GET /api/v1/contact` — site-wide public phone/email or approved-project fallback.
- `GET /api/v1/projects/{project_id}/salespeople` — approved contacts of a published project.
- `GET /api/v1/sales/projects/{project_id}/salespeople` — all contacts, authorized sales only.
- `POST /api/v1/sales/projects/{project_id}/salespeople` — draft contact.
- `PATCH /api/v1/sales/projects/{project_id}/salespeople/{id}` — edit contact, resets approval.
- `PATCH /api/v1/sales/projects/{project_id}/salespeople/{id}/approval` — sales head only.
- `GET /api/v1/sales/projects/{project_id}/images` — authorized media list.
- `POST /api/v1/sales/projects/{project_id}/images` — multipart upload (`file`).
- `GET /api/v1/sales/projects/{project_id}/images/{id}/file` — authenticated preview.
- `PATCH /api/v1/sales/projects/{project_id}/images/{id}/approval` — sales head only.
- `GET /api/v1/projects/{project_id}/images/{id}` — approved media of published projects only.
- Existing `POST /api/v1/buyer/handoff` and `GET /api/v1/buyer/handoff` now include `salespeople` cards when available.

## Verification and limits

- Backend regression suite: **102 passing tests** on isolated SQLite databases, including four new contact/photo/privacy acceptance tests.
- Updated frontend source: TypeScript and TSX **syntax parsing succeeded**; **full npm/TypeScript/Vite build could not be performed** here because network access to npm is unavailable and the offline cache lacks `ajv`. Run `npm ci && npm run build` on Windows.
- Live local PostgreSQL, real Ollama and browser UI remain unverified in this environment.
- Storing media in PostgreSQL is acceptable for this small demo; production-scale media should use durable object storage plus image moderation, caching and retention controls. No third-party upload/storage service is required for the local demo.
- Public contact cards are manually approved; this release does not verify actual ownership of phone numbers or email addresses.
- The existing demonstration buyer-authentication limitations (no OTP, rate limiting or recovery) and mock reminder delivery remain unchanged.


---

## Source: LOCAL_AI_MILESTONE_README.md

# SitePilot AI — Local Agent Milestone (independent of Milestone 7)

## What this is

This release removes dependency on the Gemini service and replaces it with a **custom SitePilot agent**:

1. An optional local open-weight conversational/classification model served by **Ollama**, no remote API key.
2. A small **supervised Naive Bayes intent classifier actually trained** on 138 synthetic, labeled examples (`training/examples.jsonl`). Its learned vocabulary and category counts are saved in `training/intent_model.json` and provide an offline fallback without Ollama.
3. SitePilot's existing backend-owned response templates, approved facts, hesitation evidence checks, human handoff, available-slot lookup, and transactional booking workflow.

**Important distinction:** We have trained the small intent classifier, **not trained an LLM from scratch or fine-tuned the open-weight model**. Ollama runs a third-party pretrained open-weight model locally. No proprietary model weights are included in this ZIP. Performance has not been validated on real buyers. A trained intent classifier is not equivalent to a conversational generative model.

## Windows local setup (NO Docker, NO Gemini key)

Install [Ollama](https://ollama.com/download/windows) on Windows. Open PowerShell:

```powershell
ollama pull qwen2.5:1.5b
ollama list
```

Normally Ollama runs its own background service. If it is not running:

```powershell
ollama serve
```

Test the local model:

```powershell
ollama run qwen2.5:1.5b "Reply with one sentence"
```

Then in `backend/sitepilot_backend`, use your existing Python virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set your **own local database credentials** in the `DATABASE_URL` (never commit this file). The new local-agent settings are:

```dotenv
SITEPILOT_MODEL_URL=http://127.0.0.1:11434
SITEPILOT_MODEL=qwen2.5:1.5b
SITEPILOT_MODEL_TIMEOUT=35
SITEPILOT_ALLOW_CLASSIFIER_FALLBACK=true
```

Remove all `GEMINI_API_KEY` and `GEMINI_MODEL` entries; they are not used. PostgreSQL continues to be a local service, **not Docker**.

```powershell
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

In the frontend directory:

```powershell
npm ci
npm run dev
```

Set `VITE_API_BASE_URL=http://127.0.0.1:8000` in `frontend/.env.local` if needed.

### Training the local classifier

The labeled data is synthetic and separated from buyer data. To retrain:

```powershell
python training/train_intent.py
python training/evaluate_intent.py
pytest -q
```

Retraining rebuilds the artifact from example labels. Adding more verified and diverse examples requires evaluation. **Do not silently train on personal buyer chats.** If no Ollama model is running, the system explicitly returns `ai_status: local_classifier`, not `local_model`.

### Tool policy

- The locally running model only classifies intent and explicit hesitation evidence; it is **not granted database credentials, web search, arbitrary SQL, or file access**.
- Approved project facts remain backend-owned; unapproved model prose is ignored.
- Bookings require buyer confirmation and a backend transaction. The model cannot confirm bookings.
- Missing/invalid model output triggers the trained, limited classifier when enabled; the frontend should present this as **limited assistance**, not a fully conversational AI.
- Human handoff is always available.
- The local model HTTP endpoint is restricted to `localhost` / loopback so private buyer messages cannot be sent to arbitrary remote servers by misconfiguration.

## Machine limitations

The intended development laptop has limited RAM. `qwen2.5:1.5b` is a small starting point rather than a performance guarantee. Response time will depend heavily on CPU/RAM; model download requires internet and available disk space. Do not advertise 2-minute response times without measuring them.

## Validation performed here

39 automated Python tests passed against the SQLite test harness. The separately held-out synthetic classifier smoke evaluation scored 8/10; this is NOT an estimate of real-world accuracy. **Live Ollama inference, local PostgreSQL concurrency, and frontend compilation have NOT been verified here.**

## Deployment

A public cloud deployment of FastAPI will NOT be able to call Ollama on your laptop at `127.0.0.1`. Deploy a model server privately alongside the backend or use a CPU/GPU machine accessible through a secure private network and revise the loopback restriction with formal network controls. A free web host may not be able to run an LLM. This is a material new deployment dependency.


---

## Source: RELEASE_HARDENING_NOTES.md

# SitePilot AI — Deployment-preparation hardening pass

**Baseline:** SitePilot_Local_AI_Agent_Integrated.zip. Existing Lovable UI and FastAPI API contracts are preserved.

## Changes made

1. **Private Ollama hosting:** `SITEPILOT_MODEL_URL` accepts an exact hostname listed in `SITEPILOT_MODEL_ALLOWED_HOSTS`, so a cloud FastAPI service can contact its private inference service. By default, only localhost is permitted. Nonlocal HTTP requires `SITEPILOT_ALLOW_PRIVATE_HTTP=true`, appropriate only on trusted private networking; HTTPS is preferred when available. Redirects are rejected rather than followed. Never expose Ollama directly to the internet.
2. **No schema DDL on application import:** Removed `Base.metadata.create_all()` from `app/main.py` import. Use `python -m app.seed` for a **new local/demo database**. For production upgrades use migrations (not implemented); do not rely on `create_all` as a migration strategy. Seed scripts must not be run against a database with live customer data without review.
3. **Health checks:** `/health` is a liveness endpoint; `/ready` runs a read-only `SELECT 1` and returns HTTP 503 when the database is unavailable. The model can be separately checked via the preflight CLI.
4. **Fail-closed AI behavior:** In production the trained classifier fallback is disabled by default unless explicitly enabled via `SITEPILOT_ALLOW_CLASSIFIER_FALLBACK=true`. This avoids implying normal AI assistance when the language model is offline.
5. **Preflight:** `python -m app.preflight` checks PostgreSQL and model availability without printing credentials or modifying data.
6. **Regression tests:** Added strict model URL tests, readiness tests and production fallback tests. Adjusted the existing mocked Ollama test to use the redirect-rejecting request opener.

## Run locally (Windows, no Docker)

From `backend/sitepilot_backend`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Set DATABASE_URL, JWT_SECRET, demo credentials; keep .env private.
# Start your installed PostgreSQL and Ollama. Pull model once:
ollama pull qwen2.5:1.5b
python -m app.seed             # ONLY for empty / local demo database
python -m app.preflight        # Does not mutate database
python -m pytest -q
uvicorn app.main:app --reload --port 8000
```

Frontend (separate terminal):

```powershell
cd frontend
Copy-Item .env.example .env.local
npm ci
npm run build
npm run dev
```

## Deploying the 4 components

- **Frontend** — HTTPS-hosted React application. Configure API base URL, exact CORS origin.
- **FastAPI** — set `APP_ENV=production`, a long random `JWT_SECRET`, cloud `DATABASE_URL`, private model hostname, and explicit `CORS_ORIGINS`. Run with a production ASGI server, not `--reload`.
- **PostgreSQL** — persistent managed database. Backups, least-privilege credentials, TLS and migrations required for production readiness. Do **not** rely on the local Windows `localhost` URL.
- **Ollama** — separate private service with adequate RAM and model weights installed. Use an exact internal hostname and allowlist. Cloud/private HTTP may be enabled only within trusted isolated networking; prefer HTTPS when available.

Example configuration (placeholders, **not** secrets):

```dotenv
APP_ENV=production
DATABASE_URL=postgresql+psycopg://DB_USER:DB_PASSWORD@DB_HOST:5432/DB_NAME
JWT_SECRET=GENERATE_A_LONG_RANDOM_SECRET
CORS_ORIGINS=https://YOUR_FRONTEND_DOMAIN
SITEPILOT_MODEL_URL=http://ollama.railway.internal:11434
SITEPILOT_MODEL_ALLOWED_HOSTS=ollama.railway.internal
SITEPILOT_ALLOW_PRIVATE_HTTP=true
SITEPILOT_MODEL=qwen2.5:1.5b
SITEPILOT_ALLOW_CLASSIFIER_FALLBACK=false
```

The example `ollama.railway.internal` is an **illustrative hostname**, not a claimed provisioned service. Substitute the actual internal hostname when deployed.

## Verification status and unresolved work

- Python backend suite: **50 passing tests** in this environment. Includes offline/mock tests, not a live model accuracy claim.
- **Not verified here:** live Ollama inference, user's local PostgreSQL, concurrent PostgreSQL booking test, frontend `npm ci`/production build, full browser journey, hosted deployment.
- **Not addressed by this patch:** authentication rate limiting, database migrations, production staff identity lifecycle, comprehensive vulnerability assessment, or real outbound reminders. Avoid claiming a production-ready system until these are completed and tested.
- Before GitHub: rotate previously exposed credentials, scan `.git` history for secrets, and keep `.env`/`.env.local` excluded.


---

## Source: RELEASE_V6_GUIDE.md

# SitePilot AI — Client Experience Release (build `sitepilot-release-v6`)

This is a **source-code update** to the V5.1 SitePilot AI project. It is **not** yet a deployed or fully browser-verified assignment submission.

## Summary of changes

| Area | What changed |
|---|---|
| AI response delay | Fast deterministic routing for explicit booking, approved-facts, handoff, language-switch, and pending-loan messages; common family concerns skip the separate model classification call. Other nuanced messages may still call Ollama twice. Model keep-alive and shorter generation budgets are configured. API now exposes `latency_ms` for fresh chat replies. |
| Buyer chat | Removed internal concern classification/evidence labels from buyer-facing bubbles; still available securely in the sales workspace. Improved handoff acknowledgement and displayed handoff status. Removed intrusive debug wording. |
| Buyer bookings | Password-backed account registration or sign-in on booking; separate `/buyer/visits` screen to review and cancel confirmed appointments. Existing valid buyer sessions can be password-secured, but **not** recovered from phone number alone. |
| Handoff queue | Buyer sees an understandable acknowledgement; authorized sales users can accept a handoff. Assigned handoffs leave the unassigned queue. This is not instant live chat or a working SMS/callback service. |
| Sales projects | Sales users can create private draft projects from **Projects, facts & slots**, propose fact revisions, and manage slots. Only the configured sales-head account can approve facts and publish/unpublish a draft. Publication requires an approved RERA-registration fact and another approved project fact. |
| Public catalog | Project cards and details read published projects and approved fact revisions from the API. New published projects become visible without editing the original hardcoded two-project array. Illustrative images are identified as such. |
| Dashboard | AI response timing is labeled as an automated chat metric, not a human sales-call metric. |

## Local Windows upgrade

1. **Back up your local database first** (pgAdmin Backup is suitable for a local demo). Stop your old React and FastAPI processes.
2. Extract this ZIP to a **new folder**. Keep your old source unchanged for rollback.
3. Copy only your **private** `backend/sitepilot_backend/.env` into the new backend folder. Never include real secrets in the ZIP or GitHub. Keep your PostgreSQL, JWT and Ollama settings.
4. From `backend/sitepilot_backend`, use your Python virtual environment, run `python -m pip install -r requirements.txt` and then `python -m app.seed` **only for your local development database**. This performs SQLAlchemy `create_all` for the new `buyer_credentials` table and preserves existing rows; it may also seed missing demo data/slots. For production, use controlled migrations instead.
5. Run `python -m pytest -q` and `python -m app.preflight`, then `python -m uvicorn app.main:app --reload --port 8000`.
6. From `frontend`, run `npm ci`, then `npm run dev`. Use the address Vite prints (often port 8081 in your environment).
7. Visit `http://127.0.0.1:8000/health`; expect `{"status":"ok","api":"v1","build":"sitepilot-release-v6"}`.
8. Open your frontend in a fresh browser tab. Reload both servers if an earlier build remains visible.

**New account table:** `buyer_credentials` is additive. No existing lead or booking table is deleted. Accounts are scoped to a phone **and a specific project**. Existing bookings that were made without an account can be secured **only while that buyer's valid session remains available**. There is no insecure phone-only recovery.

## Acceptance checklist

- [ ] New buyer selects a published project, day and available slot.
- [ ] Buyer creates account (phone, name, password >= 10 characters), confirms booking, and receives a booking reference.
- [ ] Buyer opens **My visits / Sign in** using the same phone/password/project, sees the booking, cancels it, and sees cancelled status.
- [ ] A second buyer attempting the same confirmed slot gets a conflict. Test the provided PostgreSQL concurrency script against a dedicated test database.
- [ ] Buyer clicks **Talk to a person** and sees a clear request status; salesperson accepts from sales lead detail. No immediate live chat is falsely promised.
- [ ] Sales executive adds a new **draft** project; it is not in the public list.
- [ ] Sales executive proposes project facts; sales head approves them, including applicable RERA registration; sales head publishes the project.
- [ ] Newly published project appears on the public homepage and booking project selector; add a future 45-minute visit time from sales admin.
- [ ] Test facts, English/Hindi/Gujarati, school/family concerns, loan questions and natural conversation. Check `latency_ms` on fresh chat API responses.
- [ ] Run `npm run build` on the local machine and check every browser route/mobile layout.

## API endpoints added

- `POST /api/v1/buyer/auth/register`, `POST /api/v1/buyer/auth/login`, `POST /api/v1/buyer/auth/claim`
- `GET /api/v1/buyer/handoff`
- `POST /api/v1/sales/leads/{lead_id}/handoff/accept`
- `GET /api/v1/sales/projects`, `POST /api/v1/sales/projects`, `PATCH /api/v1/sales/projects/{project_id}/publication`

Previously existing buyer bookings/cancellation, fact revision review and `POST /api/v1/sales/slots` are reused.

## Verification and honest limitations

- **98 backend tests passed** together on SQLite, including 6 new release tests. Live PostgreSQL/Ollama and simultaneous booking races remain unverified in this environment.
- **78 frontend TS/TSX source files parsed with no syntax diagnostics.** A full TypeScript, Vite or browser build was **not** verified because dependency installation timed out here. You must run `npm ci && npm run build` locally.
- This is a **demonstration** account system: no phone OTP/number verification, password-reset flow, login throttling, durable refresh token rotation or account audit history yet. Add these before public customer rollout.
- No real salesperson messaging, WhatsApp, email, SMS or automated callbacks. Handoff is a **queue workflow** that staff must attend to; reminders use a mock outbox.
- Some existing demo projects and images are illustrative. New public fact details use approved revisions, not the seed price fields, but real client data must be vetted before launch.
- The quick-routing layer reduces avoidable calls but does **not** establish a particular latency target. Natural answers on Qwen2.5 1.5B can still be slower than server templates and may require further real-data evaluation.
- Session tokens are stored in browser sessionStorage for the demo. Implement hardened cookie-based sessions, rate limiting, monitoring and formal migrations for production.
- This does not complete the final assignment's **TDD/deployment.md** package or deployment milestones.


---

## Source: UI_REQUIREMENTS_REVIEW.md

# SitePilot AI — UX and requirement review

## Screen review

| Surface | Observation from submitted screenshots/source | Release change | Unverified or future work |
|---|---|---|---|
| Buyer chat | Generic/overly cautious answers; hesitation evidence and internal build labels shown to buyers | Shorter friendly templates, focused response routing, hide evidence from buyer view; sales evidence retained; context-aware Ollama kept | Live model speed and natural-dialogue quality must be tested |
| Human handoff | "Request recorded; availability not guaranteed" sounded like a refusal | Clear request-sent status and buyer-visible queue state; sales executive can accept handoff | Human response and actual call/chat are still manual |
| Visit calendar | Date/slot selection backed by API; cancellation wasn't easily recoverable after browser close | Account sign-in during booking and a My Visits list/cancel view; slots remain server-locked | No password reset or SMS verification; real booking UI testing pending |
| Sales overview | Pending handoffs and 0.2-min response KPI lacked precise meaning | Pending means unassigned; response KPI labeled automated-chat first reply; links to add project | No measured human-outreach SLA yet |
| Sales admin | Previously two hardcoded projects and prototype wording | Dynamic project selector, add draft, fact approval, publish/unpublish, add slot, enable/disable, reminders view | Sales-head approval identity still configured by email; enterprise RBAC not implemented |
| Homepage and details | Old mock catalog had hardcoded prices/RERA/amenities | Published API catalog and approved fact sheet; sample imagery disclosed | Asset management for newly created projects not implemented |
| Mobile/accessibility | Existing responsive CSS and semantic controls | Sign-in action exposed, controls labeled, confirmations explicit | Full manual mobile / keyboard / screenreader audit outstanding |

## Requirements traceability

- **Capture/deduplicate leads:** Lead capture works; duplicate candidates can be reviewed from the sales API. **Automatic verified deduplication/merge is not implemented** because unauthenticated phone-only reattachment would allow account takeover.
- **AI responses (English/Hindi/Gujarati):** Existing local model + language logic preserved; fast routing bypasses model for explicit actions. Real-world quality still unverified.
- **Hesitation Decoder:** Evidence stored buyer-scoped; not shown as psychological profiling to the buyer. Sales workspace remains evidence-based.
- **Visit booking:** Slot visibility, transactional booking, idempotency, cancellation, status and confirmation. Real PostgreSQL concurrency script awaits local run.
- **Handoff:** Queue, request tracking and sales acceptance available; no live messaging or guaranteed callback.
- **Admin project facts:** Drafts, review workflow, approved-only publication and slot creation/management.
- **Consent:** Buyer chooses optional contact consent; cancellation suppresses reminder outbox. For regulated rollout, implement a stronger communication consent ledger.
- **Reminders:** Mock outbox; not a live notification provider.
- **RERA safeguards:** Project fact publishing requires approved registration reference and another approved fact. Staff must verify the actual project registration externally.

## Security notes

Do not upload `.env` or live customer data. Rotate any previously pasted secrets. Avoid production deployment before rate limiting, OTP/email verification, password reset, encrypted session handling, audit logging, proper database migrations, verified RERA/properties and a review of all sales access rights.


---

## Source: V7_2_RELIABILITY_FIX.md

# SitePilot V7.2 — Buyer account and conversation reliability

## The defects confirmed in V7.1

1. **Chat:** A short follow-up such as “She is concerned about cost” did not match the fast intent router, so the assistant could call Ollama and fall back to an irrelevant generic message. A model result could lose the buyer's stated budget concern.
2. **Buyer registration:** Account creation correctly returned HTTP 409 when that project/phone already had an account, but the **My site visits** page left the buyer in the registration form without guiding them to sign in. Changing a password in the browser's registration form does not reset an existing account.
3. **Misleading status banner:** The chat frontend compared `/health.build` against an older fixed build string, so the message “SitePilot is updating its chat service” appeared even when the API was healthy.

## V7.2 changes

- An **explicit budget concern** (e.g. “She is concerned about cost”, “The flat is too expensive”, “Price is a concern for my wife”) is classified from the latest message, with literal evidence. It does not require Ollama and does not invent property prices.
- **Price requests** (e.g. “What is the price?” or “How much does the apartment cost?”) remain in the approved-facts path, never the budget-hesitation path. Unapproved seed pricing is not presented as a verified quote.
- Backend-owned responses acknowledge concerns specifically in English/Hindi/Gujarati. Explicit **family disagreement** and **pending-loan** concerns also use this fast path instead of an extra speculative Ollama draft.
- My site visits switches **Create account → Sign in** after a duplicate-account response, preserves the entered phone and selected project, and clears the attempted password.
- Booking flow provides the same duplicate-account explanation.
- A **local development-only** buyer password repair command resets a verified existing account's password without removing the lead or its bookings. No public phone-only reset endpoint was added.
- Chat shows a banner only when the backend health check cannot be reached, not just because a build label changed.
- `/health.build` identifies this version as `sitepilot-reliability-v7.2`.

## Upgrade existing V7.1 project safely (Windows)

1. **Back up PostgreSQL** (and your V7.1 project) before any source upgrade.
2. Stop FastAPI and the frontend dev server (`Ctrl+C`).
3. Extract **SitePilot_V7_2_Reliability_Patch.zip** to the directory that contains your existing `sitepilot_m6` folder; allow matching source files to be overwritten. Do **not** replace `.env`, `.venv`, `node_modules` or the PostgreSQL database.
4. In `sitepilot_m6/backend/sitepilot_backend` activate your existing virtual environment and run:

   ```powershell
   python -m pytest -q
   python -m uvicorn app.main:app --reload --port 8000
   ```

5. In `sitepilot_m6/frontend` run `npm run build` and `npm run dev`. Verify the browser accesses the new frontend, then hard-refresh.
6. Check `http://127.0.0.1:8000/health`: `build` should be `sitepilot-reliability-v7.2`.
7. **Send NEW messages**, because earlier messages and replies are persisted in PostgreSQL:
   - “My wife is not happy with this property.”
   - “She is concerned about cost.” — Expect a specific budget reply, no generic menu, no model wait.
   - “What is the price?” — Expect approved facts only, or a clear statement that the price is unverified.
8. In **My site visits**, use a project/phone that is already registered, click Create account and submit a different password. You should be switched to **Sign in**; the original password is still the password until reset. Then log in and confirm existing bookings still appear.

No database schema change, reseeding, Ollama reinstallation or npm dependency reinstall is required for this patch.

## If you no longer remember the registered buyer password

**For your LOCAL development database ONLY**, after independently confirming account ownership, run this from `backend/sitepilot_backend`:

```powershell
python -m app.buyer_account_admin list --project project-1
python -m app.buyer_account_admin reset-password --project project-1 --phone YOUR_TEST_PHONE --verified-owner
```

Use the phone registered for **that exact project**. Enter a **new password of at least 12 characters** when prompted (your input is hidden). The command preserves existing bookings. It is disabled when `APP_ENV=production`.

**Production:** Do not publish this command through an API and do not offer a public password reset by phone number alone. A real customer reset requires OTP or verified staff identity checks plus audit controls and rate limiting.

## What was verified here

- Backend automated suite: **111 passed**, including new budget, price, duplicate, booking-retention, and local password-reset tests, with simulated Ollama and SQLite fixtures.
- All 78 frontend TypeScript/TSX source files: TypeScript transpilation syntax check passed.
- **Not verified in this environment:** `npm run build`, local PostgreSQL integration/concurrency, and live Windows Ollama/browser journey. npm dependencies were not cached.

If a *new* chat message still returns generic text, inspect Network → the `/api/v1/buyer/conversations/messages` response for `reply_strategy`, `ai_status`, `latency_ms`, `hesitation`, and `build`. Hide bearer tokens and personal data before sharing. These fields identify the failing layer precisely.



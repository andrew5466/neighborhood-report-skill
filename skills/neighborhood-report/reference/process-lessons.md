# Process lessons

What the first runs taught, kept here so the skill doesn't relearn it. Client details stay in the vault.

## Lite vs. full, measured

| | Full bubble report (first run, 2026-10-11) | Lite map (first run, 2026-10-14) |
|---|---|---|
| Input | A brief with gaps | A shortlist document that already held every fact with a source |
| Shortlist to first private page | Most of a day (the tool was built during the run) | 32 min, of which ~10 min was a stalled agent swarm |
| Build (data to published page) | Hours | ~14 min |
| Each change the agent asked for | Review rounds | 2 to 4 min |
| Review cost | Code review: 4.06M tokens (a fork) + ~180k | One facts audit; swarm 755k tokens, mostly wasted |
| Page size | ~747 KB | 260 KB without photos, ~1 MB with 6 photos |

## Keep

1. **Priorities first.** Each card leads with the client's own top three, in the client's order.
2. **The shortlist document is the brief.** Don't re-ask what it already says.
3. **Show minutes and distances, not scores.** "4 min walk to the sand" is clearer and easier to defend than a score ring.
4. **Collapsed cards.** Number, name and price until tapped; one open at a time.
5. **No agent opinion on a client page.** No "agent's pick", no "best building", no restated brief. The client decides.
6. **Honest flags.** Red for a miss, a gold Confirm for anything unverified, and a source conflict shown as a Confirm, never silently resolved.
7. **One independent facts check** (listings and card copy against the source). It caught wording that read as a safety claim ("security", "CCTV" → "staffed entry", "cameras listed"), a third-party source label, and over-specific claims.

## Fix

1. **Agent swarms and the network.** Helper agents are denied network access by the security harness and can't ask the user to approve it. They also take only the user's latest message as the request. Network steps (OpenStreetMap, routing, photo downloads, Matrix) run in the main session. Use at most two read-only helper agents (facts, photo URLs), launched after the user's go message.
2. **Hand-written card copy is the slowest step.** Draft `cards.json` from `listings.json` (unverified → Confirm, the shortlist's cons → flags), then edit.
3. **Re-test only what changed.** Copy-only edits republish without the browser check; layout edits get one look.
4. **Headless Chrome can't render below 500 px wide.** Check phone width in the browser pane's Mobile mode.
5. **The security hook can fail on long `python3 - <<EOF` heredocs.** Write the script to a file and run it.

## Client responses

Outside viewers (an email invite) hold view level and can't write the page's data store unless invited as Editor, which would also let them change the page. So Interested / Pass opens a **comment** pinned to that home (publish with `{"comments": {"composer_only": true}}`; invite the client as **Commenter**), and **Copy my picks** covers clients without a sign-in. The agent reads the comments with ArtifactComments and files them in the client's note.

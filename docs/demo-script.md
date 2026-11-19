# Demo script (narrated walkthrough, about 90 seconds)

For recording a voiced version of `docs/demo/walkthrough.gif`. Start the dashboard first (`make api & make web`) and open http://localhost:5173 in light mode at about 1200 px wide. Read at a normal pace; each block is roughly one screen.

---

**1. Runs list (0:00–0:12)**
> This is Examiner. It tests a bank's chatbot against the actual regulation text. Here's the same pack of 127 scenarios, about disputes, fees and liability under Regulation E, run against three versions of a bot. The plain one passes about 20 percent. The guarded one passes 90.

*Point at the Overall column for Naive and Guarded.*

**2. Naive scorecard (0:12–0:24)**
> Open the naive run. It's rarely outright wrong, but it dodges. Ask about a fee and it says "check with your bank". Disclosure, meaning it actually gave the fact the customer asked for, is about a third. Every failure below lists the rule it breaks.

*Scroll to the Scenarios table.*

**3. Guarded scorecard (0:24–0:32)**
> The guarded version is grounded on the bank's own fee schedule and its Reg E disclosure, with rules against promising refunds or claiming it took an action it can't take.

**4. Diff (0:32–0:52)**
> The diff is where you'd look after any change to the bot. One tick per scenario: the top row is before, the bottom row is after. Fixed 90, broke 1. The ringed one is the regression. Click it and you get both transcripts side by side. Here the guarded bot said only the payee has to send the notice, but the regulation puts that on the payee or the bank.

*Click the ringed tick.*

**5. A finding (0:52–1:10)**
> Every failure leads with why it failed, in the judge's words, then the conversation, the verdict for each of three rubrics, and the cited paragraph of the regulation, word for word, linked to the official eCFR. The judge grades against that text, not a summary of it.

*Scroll to "Rules cited".*

**6. Labeling (1:10–1:28)**
> The judge is a model, so you need a number for how far to trust it. This is the labeling screen. It's blind: no judge verdict anywhere. I read the transcript against the same rubric the judge used and press Y or N. Those labels give Cohen's kappa per rubric on the calibration page.

*Press nothing: the dashboard saves real labels. Or start the API on a copy of examiner.db first.*

**Close (1:28–1:35)**
> It's built on Inspect, it costs about two dollars a run, and the whole design log is in the repo.

---

Keep it honest when recording:

- Say the kappa is in progress until the calibration set is labeled.
- Don't call the bank real; Meridian is fictional.
- Don't call any of this legal advice.

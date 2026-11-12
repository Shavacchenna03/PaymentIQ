# Hard Questions (PaymentIQ)

1. Q: The data is synthetic. Why should I trust the results?
   A: You should not trust the numbers as facts about banks. The patterns were committed first (tag ground-truth-declared), and the test was whether methods recovered magnitudes and avoided traps. 12 of 14 estimates were within 2 SE, and the 2 misses are reported.
2. Q: Did you just find what you planted?
   A: The traps were designed to fool simple analysis. The raw comparison got the wrong bank; only controls and the right outcome fixed it.
3. Q: What were your two scorecard misses?
   A: Large-bank peak effect (z 2.34) and the 2G effect (z 2.10). Plausible causes are the Kestrel evening outage and the derived first-attempt flag; I did not test either.
4. Q: What did not work?
   A: A biased latency regression, customer segmentation (ARI 0.064), and the scoring model. I reported all three.
5. Q: Why is revenue small?
   A: A PSP earns a fee, not the payment amount. At 0.5 percent take rate, +5 points is about 7,900 rupees over six months. I argued for the work on experience and safety grounds.
6. Q: How reliable are your journeys?
   A: The domain rule has 346 merged journeys and about 676 split intents out of 280,000. Recovered value is 2.9 percent below truth.
7. Q: Is the A/B test real?
   A: No, it is simulated with an assumed effect. It shows power, false-positive rate and guardrail behaviour.
8. Q: Why is the duplicate-debit rate high?
   A: I inflated it to 3 percent of timeouts for statistical power. Real rates are lower.
9. Q: What would you do first with real data?
   A: Build the metric dictionary, check data quality (timezones, duplicates), and slice by bank before trusting any aggregate.
10. Q: What is the one thing you would fix?
    A: The incident rule uses same-block hindsight; I would build a trailing-window live version.

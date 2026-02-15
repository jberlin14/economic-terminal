# Yield Curve Theory

## HIGH-LEVEL

The yield curve plots Treasury yields across maturities (3M to 30Y). Normally it slopes upward — longer bonds pay more because investors demand compensation for time/inflation risk. When it inverts (short rates above long rates), it historically signals recession within 12-18 months.

The 10Y-2Y spread is the classic indicator. The 10Y-3M spread is a stronger recession predictor (NY Fed probability model). Both matter but capture different dynamics — 10Y-2Y reflects market expectations of Fed policy path; 10Y-3M reflects the immediate carry cost of being in short-term instruments.

Key insight: the yield curve is not causing recession — it's reflecting that markets expect the Fed will need to cut rates aggressively, which only happens when the economy deteriorates.

## RIGOROUS

### Expectations Hypothesis
Long-term rates equal the average of expected future short-term rates plus a term premium:

(1+y_n)^n = (1+y_1)(1+f_1,2)(1+f_2,3)...(1+f_n-1,n)

Where f = forward rates implied by the curve. If the 2Y yield is 5% and the 10Y is 4%, markets are pricing in that short rates will average below 4% over the next 10 years — i.e., significant rate cuts are expected.

### Term Premium
The compensation investors demand for holding longer-duration bonds instead of rolling short-term bonds. Components:
- **Inflation risk premium**: Uncertainty about future inflation eroding real returns
- **Duration risk premium**: Longer bonds have greater price sensitivity to rate changes
- **Supply/demand premium**: Government issuance patterns, central bank purchases, foreign official sector demand

The term premium is unobservable and estimated via models (ACM, Kim-Wright). When the term premium is compressed (due to QE, foreign buying, or flight to quality), the yield curve can invert even without recession expectations. This is the "this time is different" argument — partially valid but dangerous to rely on.

### Curve Shape Taxonomy
- **Normal (steep)**: 10Y-2Y > 100bp. Healthy expansion, markets pricing growth and gradual rate normalization.
- **Flat**: 10Y-2Y near 0bp (±25bp). Late cycle — Fed has tightened enough to compress the curve. Growth expectations dimming.
- **Inverted**: 10Y-2Y < 0bp. Markets pricing rate cuts ahead. Historically precedes recession by 6-18 months.
- **Deeply inverted**: 10Y-2Y < -50bp. Aggressive recession pricing. 2006-07 (-20bp) preceded severe recession; 2022-23 (-100bp) was deepest since 1980s.

### Steepening vs Flattening Dynamics
- **Bull steepener** (front end falling faster than back end): Fed cutting or expected to cut. Risk-off signal — economy weakening, Fed responding. Often occurs AT the onset of recession.
- **Bear steepener** (back end rising faster than front end): Term premium expanding or inflation expectations rising. Can signal fiscal concerns (excess supply), inflation re-acceleration, or foreign selling.
- **Bull flattener** (back end falling faster than front end): Flight to quality. Long bonds rallying as growth fears intensify. Classic pre-recession move.
- **Bear flattener** (front end rising faster than back end): Fed tightening aggressively. Short rates following Fed, long rates restrained by growth concerns. Classic late-cycle pattern.

### The Uninversion Signal
Critical nuance: the yield curve uninverting is NOT an "all clear." Historically, recession typically begins AFTER the curve re-steepens, not while it's inverted. The steepening happens because the front end drops (Fed cutting in response to economic weakness) while the long end holds steady or falls less.

Sequence: Normal → Flattening (late cycle) → Inversion (recession signal) → Uninversion/Steepening (recession arriving) → Steep normal (recovery, accommodation)

### Term Spread and the Real Economy
The yield curve affects the real economy through:
1. **Bank profitability**: Banks borrow short and lend long. An inverted curve compresses net interest margins → banks tighten lending standards → credit contraction
2. **Carry trade**: Investors who fund at short rates and invest at long rates face negative carry when the curve inverts → position unwinding, reduced risk appetite
3. **Corporate cost of capital**: Companies choosing between short-term commercial paper and long-term bonds. Inversion makes short-term funding more expensive, squeezing working capital.

### Breakeven Inflation
The spread between nominal Treasury yields and TIPS (Treasury Inflation-Protected Securities) yields at the same maturity. Approximates the market's inflation expectation:

Breakeven = Nominal yield - TIPS real yield

5Y breakeven reflects medium-term inflation expectations. 10Y breakeven reflects longer-term expectations. The 5Y5Y forward breakeven (expected inflation from year 5 to year 10) is the Fed's preferred measure of long-term inflation expectations.

When breakevens diverge from actual inflation, it signals either:
- Market mispricing (opportunity)
- Inflation expectations becoming unanchored (policy crisis)
- Liquidity distortions in TIPS market (technical, not fundamental)

### Indicator Triggers
- **10Y-2Y spread < 0**: Classical inversion. Every recession since 1960 preceded by inversion. Two false positives (1966, 1998 — both followed by significant slowdowns even without official recession).
- **10Y-3M spread < 0**: Stronger predictor. NY Fed recession probability model uses this exclusively. <0 for 3+ months → ~60% recession probability within 12 months.
- **Inversion depth > 50bp**: Severe signal. Only occurred before deep recessions (1980, 2007-09, 2022-23 TBD).
- **Curve steepening > 50bp in 3 months after inversion**: Recession imminent. The "uninversion steepener" is the danger signal, not the all-clear.

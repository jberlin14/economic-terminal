# Signal Interpretation Framework

## Purpose
This framework maps specific market conditions to theoretical interpretations. When you observe a signal in the data, apply the relevant theory to explain WHY it matters and WHAT it implies.

## Yield Curve Signals

**10Y-2Y spread inverts (< 0)**
- Theory: Expectations hypothesis → markets pricing aggressive rate cuts ahead (yield_curve.md)
- Context: Check term premium — if compressed by QE/foreign buying, the signal is weaker
- Forward: Recession typically begins 6-18 months AFTER inversion, often AFTER curve re-steepens
- Watch: Credit spreads (if also widening → signal confirmed), Sahm Rule (approaching trigger?)

**Curve steepening rapidly after inversion**
- Theory: Bull steepener = front end falling as Fed cuts or markets price cuts → recession arriving, NOT averted
- Bear steepener = back end rising → term premium expanding → fiscal concern OR inflation re-acceleration
- Distinguish by checking: are front-end rates falling (bull) or back-end rates rising (bear)?

**Real yields deeply positive (>2%)**
- Theory: Restrictive monetary stance (monetary_policy.md) → policy actively restraining growth
- Forward: Economy will slow unless real yields decline; the question is whether the Fed eases or growth breaks first
- Watch: Credit conditions, loan demand, business investment

## Inflation Signals

**Core CPI/PCE declining but shelter sticky**
- Theory: Shelter lag (inflation.md) → CPI shelter lags market rents by 12-18 months
- Forward: If market rents have peaked, shelter CPI will mechanically decline — this is ALREADY determined by past data
- Implication: "Last mile" inflation concern may be overstated if the remaining inflation is concentrated in lagging shelter

**Headline above core (energy/food driving)**
- Theory: Cost-push inflation (inflation.md) → doesn't require rate hikes to resolve, resolves with supply normalization
- Risk: If cost-push persists, second-round effects through wage demands can convert it to demand-pull
- Watch: Wage growth (are workers demanding compensation for higher costs?) and inflation expectations (are they moving?)

**Inflation expectations unanchoring (breakevens rising, Michigan survey elevated)**
- Theory: Loss of credibility (central_bank_independence.md) → self-fulfilling dynamics
- Urgency: This is the scenario the Fed fears most. Requires aggressive rate response.
- Watch: 5Y5Y forward breakeven (the Fed's preferred long-term measure)

## Labor Market Signals

**Unemployment rising from cycle lows**
- Theory: Sahm Rule threshold (business_cycles.md) → 0.5pp above 12M low = recession begun
- Theory: Beveridge curve (labor_markets.md) → is this vacancies normalizing (soft landing) or firing cycle beginning?
- Distinguish by: JOLTS quits rate (falling = anxiety), initial claims trajectory (rising = firing cycle)

**Payroll growth decelerating toward zero**
- Theory: Late-cycle deceleration → firms stop hiring before they start firing
- Theory: Labor hoarding (labor_markets.md) → employment appears stable until it suddenly isn't
- Watch: Average weekly hours (cut before headcount), temp employment (leading indicator)

**Wage growth > productivity growth + 2%**
- Theory: Wage-price spiral risk (inflation.md) → unit labor costs rising → inflationary
- Policy: Fed needs to see this slow before cutting rates
- Watch: ECI trend, productivity growth, real wage growth

## FX Signals

**Dollar strengthening broadly (DXY rising)**
- Theory: Interest rate differential (fx_and_trade.md) → US rates higher than peers attracts capital
- OR: Safe-haven demand (dollar_smile) → global risk-off episode
- Distinguish by: Is the VIX also elevated? (risk-off) Are EM currencies selling off? (risk-off) Or is it just rate-differential driven?

**EM currencies weakening sharply**
- Theory: Sudden stop / original sin (fx_and_trade.md) → capital flight from EM
- Risk: Self-reinforcing cycle → depreciation → higher import costs → inflation → rate hikes → growth collapse → more depreciation
- Watch: EM sovereign CDS, local currency bond yields, reserve adequacy

**Yen strengthening rapidly**
- Theory: Carry trade unwind (fx_and_trade.md) → risk-off signal, global deleveraging
- The yen strengthens when carry trades unwind because short-yen positions are closed
- Historically correlates with equity market drawdowns and credit spread widening

## Credit Signals

**Credit spreads widening from tight levels**
- Theory: Minsky moment risk (business_cycles.md) → transition from speculative to Ponzi finance
- Context: Widening FROM tight matters more than the absolute level — it signals sentiment shift
- Watch: Is widening concentrated in HY (junk) or broad-based (IG too)? HY-only = idiosyncratic. Broad = systemic.

**Credit spreads tight while curve inverted**
- Theory: Conflicting signals → curve says recession, credit says no stress
- Resolution: Either (a) credit is complacent and will catch up, or (b) the inversion is term-premium-driven, not recession-driven
- Historical: In 2006-07, credit spreads stayed tight for months after inversion. Then widened explosively.

## Geopolitical Signals

**Tariff announcements / trade escalation**
- Theory: Inflationary + growth-negative (trade_policy.md) → stagflationary impulse
- First-order: protected sector stocks up, consumer/import-dependent stocks down
- Second-order: retaliation hits US exporters, uncertainty depresses investment
- Watch: CPI components (tariff pass-through appears in 1-3 months), business investment, PMI new orders

**Sanctions escalation**
- Theory: Commodity supply disruption (sanctions.md) → energy/metals price spikes
- FX impact: sanctioned currency collapses, safe-haven currencies strengthen
- Credit: counterparty risk repricing for banks with exposure
- Watch: oil prices, natural gas (European pricing), sanctioned country's currency, EM contagion

**Central bank independence threatened**
- Theory: Time inconsistency (central_bank_independence.md) → inflation expectations unanchor
- Market response: long-term yields rise (inflation premium), currency weakens, equity risk premium rises
- This is one of the most market-destructive political events — Erdogan's Turkey (2021-23) is the case study

## Indicator Interpretation Rules

**CPI/PCE (index-level data)**
- ALWAYS compute and discuss YoY% change, NOT raw index values. A CPI index of 315 means nothing; 3.2% YoY tells the story.
- Core vs headline: core strips food/energy volatility. Core is what the Fed targets. Headline is what consumers feel.
- MoM annualized: multiply monthly change by 12 for run-rate. 3-month annualized reveals trend better than single month.

**Employment (PAYEMS, NFP)**
- Payrolls are backward-looking and heavily revised. The first print is often wrong by 50-100K.
- Net payroll changes <100K/month in a 160M labor force = stall speed, even if positive.
- Watch the household survey (from which unemployment is derived) vs establishment survey (payrolls) — divergences signal turning points.

**Initial Claims (ICSA)**
- Claims below 225K = historically healthy. Above 250K sustained = labor market softening. Above 300K = recession signal.
- Single-week spikes (hurricanes, seasonal quirks) are noise. Use the 4-week moving average.
- Continuing claims (CCSA) trend matters more — rising continuing claims = people can't find new jobs.

**GDP (A191RL1Q225SBEA)**
- SAAR (Seasonally Adjusted Annual Rate) is the standard. A 2% SAAR print doesn't mean 2% growth that quarter — it means "if this quarter repeated 4 times."
- GDP is heavily revised across 3 releases (advance, second, third). Don't overweight the advance estimate.
- Real vs nominal: real GDP strips inflation. In high-inflation periods, nominal GDP can grow while real GDP contracts.

**VIX**
- VIX below 15 = complacency/risk-on. 15-25 = normal uncertainty. 25-35 = elevated fear. Above 35 = crisis territory.
- VIX term structure: contango (front < back) = normal. Backwardation (front > back) = panic/hedging demand.
- VIX is a measure of EXPECTED volatility, not realized. High VIX means options are expensive, not necessarily that markets are falling.

**Credit Spreads (OAS)**
- IG OAS below 100bps = extremely tight, complacent. 100-150 = normal. 150-200 = mild stress. Above 200 = significant risk-off.
- HY OAS below 350bps = tight. 400-500 = normal. Above 600 = stress. Above 800 = distressed.
- The ratio HY/IG matters: if HY widens but IG doesn't, it's idiosyncratic. Both widening = systemic.

## Regime Transitions

**RISK_ON → CAUTIOUS**
- Early warning signals appearing. Theory says: watch for confirmation vs. false alarm
- Key question: are leading indicators (curve, claims, PMI) deteriorating, or is this a mid-cycle scare?

**CAUTIOUS → RISK_OFF**
- Multiple stress signals confirming. Theory says: position for recession but timing is uncertain
- Historical playbooks matter here — is this more like 2007 (slow build to crisis) or 2019 (scare that resolves)?

**RISK_OFF → CRISIS**
- Systemic stress. Theory says: Minsky dynamics may be in play — watch for credit contagion
- Policy response speed is critical — the Fed's lender-of-last-resort function determines severity
- Watch: are credit markets functioning? Can firms roll over debt? Are money markets stressed?

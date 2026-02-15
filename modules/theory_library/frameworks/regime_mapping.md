# Regime Mapping Framework

## Purpose
Maps current market regime and indicator conditions to the theoretical frameworks that should guide interpretation. This is the bridge between raw data and theoretical analysis.

## Regime: RISK_ON
**Theoretical lens**: Mid-cycle expansion
- Apply: business_cycles.md (cycle positioning), monetary_policy.md (is policy neutral or still accommodative?)
- Key question: are there late-cycle signals forming beneath the surface?
- Watch for: credit growth outpacing GDP (Minsky buildup), yield curve flattening (late-cycle transition), wage growth accelerating (Phillips curve pressure)
- Incentive analysis: Firms are investing, consumers are spending. The incentive is to chase returns. Complacency builds.

## Regime: CAUTIOUS
**Theoretical lens**: Late cycle / early warning
- Apply: yield_curve.md (inversion signals), business_cycles.md (leading vs lagging divergence), labor_markets.md (is the labor market cracking?)
- Key question: is this a genuine late-cycle transition or a mid-cycle scare?
- Distinguish using: Sahm Rule trajectory, credit spread direction, PMI trend, initial claims trajectory
- Apply trade_policy.md and sanctions.md if geopolitical news is driving the caution
- Incentive analysis: The Fed faces asymmetric risk — overtightening into weakness is harder to reverse than undertightening. Smart money starts hedging.

## Regime: RISK_OFF
**Theoretical lens**: Pre-recession / active stress
- Apply: business_cycles.md (recession typology — financial crisis vs. policy-induced vs. exogenous?), monetary_policy.md (will the Fed cut fast enough?), fiscal_policy.md (is fiscal response coming?)
- Key question: what type of recession is forming, and how severe?
- Apply inflation.md carefully: if inflation is still above target, the Fed faces a policy dilemma (cut to support growth vs. hold to fight inflation)
- Apply fx_and_trade.md: dollar strength in risk-off tightens conditions for EM (contagion channel)
- Apply central_bank_independence.md: political pressure to cut rates intensifies
- Incentive analysis: Firms shift from investment to cash preservation. Workers accept lower wage growth to keep jobs. Politicians demand stimulus. The transition from RISK_OFF to CRISIS depends on whether policy responds fast enough.

## Regime: CRISIS
**Theoretical lens**: Systemic stress / financial instability
- Apply: business_cycles.md (Minsky dynamics — are we in the Ponzi finance unwind?), monetary_policy.md (liquidity trap risk, unconventional tools)
- Apply fiscal_policy.md: crisis-level fiscal response likely, debt sustainability secondary to stabilization
- Apply sanctions.md if the crisis has geopolitical origins
- Apply supply_chain_risk.md if supply disruption is involved
- Key question: is the financial system functioning? Can credit flow? Are money markets operational?
- Incentive analysis: All actors shift to survival mode. Normal incentives break down. Government intervention reshapes market structure. The winners are determined by policy choices (who gets bailed out, who doesn't).

## Theme-Specific Theory Selection

### When inflation is the dominant theme
Load: inflation.md, monetary_policy.md, central_bank_independence.md
If trade/tariff related: also trade_policy.md
If energy related: also energy_security.md
Focus the signal_interpretation.md sections on: inflation signals, Fed reaction function

### When labor market is the dominant theme
Load: labor_markets.md, business_cycles.md, monetary_policy.md
Focus on: Sahm Rule, Beveridge curve, Phillips curve link to inflation
The labor market is where the cycle turns — this is where the theoretical framework is most predictive

### When FX is the dominant theme
Load: fx_and_trade.md, monetary_policy.md (rate differentials), great_power_competition.md (if USD/CNY or geopolitical driven)
If EM stress: also sanctions.md (if relevant), energy_security.md (commodity currencies)

### When geopolitics is the dominant theme
Load: great_power_competition.md, supply_chain_risk.md, sanctions.md, energy_security.md
Also: trade_policy.md (tariffs/trade war), central_bank_independence.md (political pressure on central banks)
This is where the incentive-driven analysis is most valuable — who benefits, who loses, who is forced to act

### When fiscal policy is the dominant theme
Load: fiscal_policy.md, monetary_policy.md (fiscal-monetary interaction), central_bank_independence.md (fiscal dominance risk)
Focus on: debt sustainability arithmetic (r vs. g), term premium dynamics, crowding out assessment

### When credit markets are the dominant theme
Load: business_cycles.md (Minsky), yield_curve.md (credit/curve interaction), monetary_policy.md (transmission mechanism)
Focus on: is credit stress idiosyncratic or systemic? Is the banking channel impaired?

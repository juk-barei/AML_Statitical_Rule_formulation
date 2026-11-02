# Rules for AML

## Rules
Each rule should have its ratio of contribution to the overall score since some rules don't represent the specific fraudulent group as well as the others.

**Note:** Exact number like 15 mins, 95%, 7 days, or 8 are just made up for now since we should do statistical analysis of old illicit addresses to define the exact correct value for each formula.

### 1. Pass-Through Speed (S1)

**The Rule:** score the risk score of the category between [0-1] wallets where:
- (the average holding time is under 15 minutes) **AND**
- (the ratio of outgoing to incoming volume is 95% or higher.)
The high scoring should be based on how fast the account clearing the large amount of money.

**Variables needed after having the addresses**: transaction id, amount of each in-transaction, amount of each out-transaction, timestamp of each in-transaction, timestamp of out-transaction.

**REASONING:** If the new amount comes into the address does not stay for long, it is likely that it is for hopping for money laundering rather than normal business usage. But it is not clear that is for money laundering yet cuz ppl that do business and use TRON as transaction platform. So determine the ratio amount getting out with amount coming in within the timeframe will better determine if it is really an act of laundering money or not. 95% is the number i got from the paper 1 (fistful of bitcoin). Legitimate users will not likely spend the most of the money they just received within 15 minutes except users do gambling on bitcoin like Satosi dice but we are on Tron chain so it is ok, I guess. Not ideal reasoning but it kinda works since those money laundering(ML) are mostly automated code scripts.

**Note**: create the 15 mins could be misleading for some legitimate users, but if we lower down to 3 mins instead, it will guarantee automated script or bot activity (which fits 99% to our target fraud ppl). But it would also cap out ppl doing the Money laundering. So it is the problem of high precision(3 mins is surely bot doing ML) and high recall(15 mins to detect human doing ML / bad actors are able to exploit the 3 mins rules easily given 15 mins is harder to figure out). **Maybe we can add one more condition to create 2 time ranges corresponding to different risk scoring to improve the rule**.


### 2. Temporal Burstines (S2)
    
**The Rule:** score risk between [0-1] where:
- (a wallet's total operational lifetime <= **7 days**) **AND**
- (its maximum 1-hour transaction volume(in+out) accounts for **75%** or more of its total lifetime volume).


**Variables needed after having the addresses**: transaction id, amount of each in-transaction, amount of each out-transaction, timestamp of each in-transaction, timestamp of out-transaction, wallet_first_seen_date, current_date.

**REASONING:** Criminals routinely abandon TRON addresses quickly to evade blacklists or frozen Tether (USDT) actions. Hence, I created the first condition. But newly created account will be affected but this rule. Second condition is built in the assumption that if  max of the 1-hour transaction-volume-amount(by comparing all 1-hour amount), is most of overall amount, that means it operates actively in that one-hour the most, kinda signal account created for one time usage. Putting this with the 1st condition, the account fits perfectly to the 2 conditions is the account abandoned  with most actively in 1-hour window. What we need to account further on this rule is the case of new users use it for one time and leave or do little transactions for one time. Still adding it with other rules will help us scope the illicit wallet better than a standalone rule by itself.

### 3. Topology: Spraying & Funneling (S3)

**The Rule:** Identifies Fan-Out (out-degree > **7**) or Fan-In (in-degree >= **7**) within a **1.5-hour** window where the Coefficient of Variation of the transaction amounts is under **0.05**. Score it between [0-1].

**Variables needed after having the addresses**: transaction id, amount of each in-transaction, amount of each out-transaction, timestamp of each in-transaction, timestamp of out-transaction, wallet_first_seen_date, current_date.

**REASONING**: one wallet usually interact with up to 5 wallets in an hour. so I set safe amount up to 7 for busy users (and it is just assumption number). I put up to 1.5 hours because those illicit users can manipulate their density of distribution (split money to many addresses) to outplay the patterns I just raised. Coefficient of Variation(std/mean) is sth AI told me I should put. Basically, it measures the variation of amount between addresses, because human using the transaction tends to have high variations as we can't predict what we buy or sell, but bots will have rules of how much to split between accounts equally(the rule has covered) or with some patterns of difference(this one the rule hasn't covered).

### **4. TRON Gas Co-Occurrence (S4)

**The Rule:** Calculates the Jaccard Index of addresses funding TRX gas versus addresses receiving USDT. Triggers if $J$ is **0.50** or higher.

**Variables needed after having the addresses**: type of currency received, type of currency sent, addresses of each in-transaction, addresses of each out-transaction.

**REASONING**: This rule is specific to TRON's TRC-20 architecture. Moving USDT requires native TRX to cover energy and bandwidth fees. So, criminals will send TRX to an address to make sure the transfer can be complete as the TRC-20 requires TRX for energy and bandwidth to call the transfer() function. Say you enter w address to the system, it will filters:
1. the set of address sent to w in TRX
2. the set of address w sent to in USTD.
Then do Jaccard Index calculation.

**Note:** Other than flagging it to users that address is risky, we should also flag the sets of sender to the wallet as well. But we will have to check if those senders to track other mule addresses the senders sent to in order to process USTD on other addresses.

### **5. Seed Proximity (S5)

**The Rule:** Assigns a decaying risk score betwween [0-1] based on network distance from a known illicit seed, such as a sanctioned entity, darknet market, or scam address. The  formula is:
- (10*2^(1-d)) if 0<d<=4.
- 0 if d>4.

**Variables needed after having the addresses**: address-in, address-out, database of illicit addresses on TRON.

**REASONING:** Basically checks address with the past illict address from the records we downloaded from different sources. Formula is assigning the risk score based on how far is the interact of the input address to the illicit address found.

**Note**: Idk how to make it go to range [0-1] yet. Maybe we don't need to convert to [0-1] in the first place.

### Overall: 
- Rule 1 Checks transaction velocity and holding time.
- Rule 2 Checks wallet lifetime and volume concentration.
- Rule 3 Checks structural fan-in / fan-out degrees && transfer amount dispersion 
- Rule 4 Checks TRX gas funder overlap (Jaccard Index).
- Rule 5 Checks topological hop distance to blacklisted seeds.
## Risk score
each rule works independently but they are combined at the end to form a risk score.
If A is the input address,and 1<={w1,w2,w3,w4,w5}<=3 are weight of each rule (priority of each rule)
Weight sum of all rule scores: S(A) =  w1*S1 + w2*S2 + w3*S3+ w4*S4 + w5*S5. 
**Risk score formula**: R(A) = min(10,S(A)).

**Note**: 0<=S(A)<=15.

### **6. How consistent is in and out transaction
**The Rule:**  Score risk between $[0, 1]$ for wallets where:
- (the transaction count $N \ge 5$ within an operational session) AND
- (the Coefficient of Variation of Inter-Arrival Times is under 0.15).

**Variables needed after having the addresses**: transaction_id, direction (IN/OUT), timestamp of each in-transaction, timestamp of each out-transaction, total transaction count.

**REASONING:** Human behavior on-chain is naturally stochastic (irregular). Humans open wallets, copy addresses, sign transactions, and pause to read screens. Consequently, human inter-arrival times (Delta t) follow heavy-tailed or Poisson distributions with high variance. For ppl that do the ML they will set a fixed interval that they find safe to evade the bot while trying to maximize their process to do more hopping. Hence, the process will be deterministic or randomly deterministic(try to make some random time interval for doing transaction while also trying to maintain efficiency).  

**Note**: 
- This rule actually complements the rule 1. If the criminal figures out rule number 1 that we try to evade the 3 minutes rule for bot detection, then they can program the bot to wait a fixed interval like 6 minutes between hops.
- The rule has not covered the randomly deterministic case yet.

### Overall: 
- Rule 1 Checks transaction velocity and holding time.
- Rule 2 Checks wallet lifetime and volume concentration.
- Rule 3 Checks structural fan-in / fan-out degrees && transfer amount dispersion 
- Rule 4 Checks TRX gas funder overlap (Jaccard Index).
- Rule 5 Checks topological hop distance to blacklisted seeds.
- Rule 6 checks the consistency of how address send or receive transaction.

## Risk score
each rule works independently but they are combined at the end to form a risk score.
If A is the input address,and 1<={w1,w2,w3,w4,w5,w6}<=3 are weight of each rule (priority of each rule)
Weight sum of all rule scores: S(A) =  w1*S1 + w2*S2 + w3*S3+ w4*S4 + w5*S5 + w6*s6. 
**Risk score formula**: R(A) = min(10,S(A)).
**Note**: 0<=S(A)<=15.


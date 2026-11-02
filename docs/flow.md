# Flow 
These are just draft idea of flow only. No details yet. Further change can be made.

## Info: 
Our seed dataset has: 
- 4 csv files
- Not complete all features yet. (needs aggregation)

## Parameters:
- Scores ($s_0 - s_6$) calculated from each rule
- Weights ($w_0 - w_6$): how influence is each score(of each rule) factor to overall risk score. This could be calculated from 

## Main steps  for score formulation
There are 2 main parts:
1. Hypothesis testing: to know if that hypothesis can be used.
2. Tuning threshold: tune the threshold based on the pattern in the seed data.

### Hypothesis Testing

1. Understand the distribution of the data. Each hypothesis will be in different distribution but we will try to assume normal distribution. Before we can even assume that, we need to:
    - plot the Q-Q plot/
    - if Q-Q plot has problem, then we do the Sharpio Wiki Test
2. 2-sample test: Test the licit users pattern and illicit users pattern form the seed data we got with the same sample size and  variables.
    - Ex: We test pattern of `holding time of money` in licit users(n=1000 rows) and illicit users(sample out 1000 rows)

This is to see if the pattern of that variable are different. Then we can prove that our hypothesis is worth implementing. 

We may use non-parametric test like  Mann-Whiteney U test or the Kolmogorov-Smirnov Test since there could be extreme outlier in our sample.

### Tuning Threshold
1. Use ROC or PR curves.
2. Measure the tradeoff Type 1 or Type 2 error.
3. Choose threshold that maximize our target metric (95% precision, 95% accuracy...).

## Main steps for weights calculation($w_0,w_1,..,w_6$)
**Note**:  1<=$w_i$<=3
There are 3 ways we can do it:
1. ML Method: Logistic Regression based on past data (seed data). But our dataset could be too small for capstone 1. (maybe plan for capstone 2?)
2. Statistical method: Mutual Information / Information Gain. Set weight proportionally to their Mutual Information.
3. Optimization: Grid Search from ROC-AUC/PR-AUC.
=> Idk which one to choose.

## Normalize and combine scores
Normalize the score to [0,1] range then do the combining of weights and Score from each rule.
$S = sum(s_i * w_i), i=[1,2,..,6]$



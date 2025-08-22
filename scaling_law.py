import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Your data
data = {
    'questions': [250, 500, 750, 1000],
    'cost': [0.64, 1.59, 3.55, 6.61],
    'gpus': [1, 1, 2, 4],
    'time_minutes': [47.2, 117.5, 131.1, 122.0]
}

df = pd.DataFrame(data)
df['cost_per_question'] = df['cost'] / df['questions']

# Generate fitted curves
questions_range = np.linspace(200, 1100, 100)
linear_fit = 0.006 * questions_range
quadratic_fit = 0.000006 * questions_range**2
power_law_fit = 0.000065 * questions_range**1.5

# Set up the plotting style
# plt.style.use('seaborn-v0_8')  # or just 'seaborn' if you have older version
plt.style.use('default')
plt.rcParams.update({'font.size': 14})
fig = plt.figure(figsize=(15, 12))

# 1. Main scaling chart
plt.subplot(2, 2, 1)
plt.plot(questions_range, power_law_fit, 'purple', linestyle='--', linewidth=2, label='Power Law (q^1.5)')
plt.plot(questions_range, quadratic_fit, 'blue', linestyle=':', linewidth=2, label='Quadratic (q²)')
plt.plot(questions_range, linear_fit, 'gray', linestyle='-.', linewidth=2, label='Linear')
plt.scatter(df['questions'], df['cost'], color="#4487FB", s=100, zorder=5, 
           edgecolors="#3972D5", linewidth=2, label='Actual Data')

plt.xlabel('Number of Questions')
plt.ylabel('Cost ($)')
plt.title('Questions vs Cost with Scaling Models')
plt.legend()
plt.grid(True, alpha=0.3)

# 2. Cost per question
plt.subplot(2, 2, 2)
plt.plot(df['questions'], df['cost_per_question'], 'o-', color='#e67e22', 
         linewidth=3, markersize=8, markerfacecolor='#d35400')
plt.xlabel('Number of Questions')
plt.ylabel('Cost per Question ($)')
plt.title('Cost Per Question vs Scale')
plt.grid(True, alpha=0.3)

# 3. GPU scaling
plt.subplot(2, 2, 3)
plt.bar(df['questions'], df['gpus'], color='#27ae60', alpha=0.7, width=125)
plt.xlabel('Number of Questions')
plt.ylabel('Number of GPUs Required')
plt.title('GPU Requirements vs Workload')

# 4. Processing time
plt.subplot(2, 2, 4)
plt.plot(df['questions'], df['time_minutes'], 'o-', color='#8e44ad', 
         linewidth=3, markersize=8, markerfacecolor='#7d3c98')
plt.xlabel('Number of Questions')
plt.ylabel('Processing Time (minutes)')
plt.title('Processing Time vs Workload')
plt.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()

# Print analysis
print("=== Scaling Law Analysis ===")
print("\nOriginal Data:")
for i, row in df.iterrows():
    print(f"{row['questions']} questions: ${row['cost']:.2f} (${row['cost_per_question']:.4f}/q), "
          f"{row['time_minutes']:.1f}min, {row['gpus']} GPUs")

print("\nScaling Analysis:")
print("Questions vs Cost ratios:")
for i in range(1, len(df)):
    prev_row = df.iloc[i-1]
    curr_row = df.iloc[i]
    question_ratio = curr_row['questions'] / prev_row['questions']
    cost_ratio = curr_row['cost'] / prev_row['cost']
    print(f"{prev_row['questions']} → {curr_row['questions']}: "
          f"Q ratio = {question_ratio:.2f}, Cost ratio = {cost_ratio:.2f}")

print(f"\nOverall scaling (250 → 1000): "
      f"{df.iloc[-1]['cost']/df.iloc[0]['cost']:.1f}x cost for "
      f"{df.iloc[-1]['questions']/df.iloc[0]['questions']:.0f}x questions")

# Optional: Create a single focused plot
plt.figure(figsize=(10, 6))
plt.plot(questions_range, power_law_fit, 'purple', linestyle='--', linewidth=2, label='Power Law (q^1.5)')
plt.plot(questions_range, quadratic_fit, 'blue', linestyle=':', linewidth=2, label='Quadratic (q²)')
plt.plot(questions_range, linear_fit, 'gray', linestyle='-.', linewidth=2, label='Linear')
plt.scatter(df['questions'], df['cost'], color="#4487FB", s=120, zorder=5, 
           edgecolors="#3972D5", linewidth=2, label='Actual Data')

plt.xlabel('Number of Questions', fontsize=12)
plt.ylabel('Cost ($)', fontsize=12)
plt.title('AI Platform Scaling Law: Questions vs Cost', fontsize=14, fontweight='bold')
plt.legend(fontsize=11)
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

# Calculate R-squared for each fit
from sklearn.metrics import r2_score

actual_costs = df['cost'].values
questions = df['questions'].values

# Evaluate fits at actual data points
linear_pred = 0.006 * questions
quadratic_pred = 0.000006 * questions**2
power_law_pred = 0.000065 * questions**1.5

r2_linear = r2_score(actual_costs, linear_pred)
r2_quadratic = r2_score(actual_costs, quadratic_pred)
r2_power_law = r2_score(actual_costs, power_law_pred)

print(f"\nModel Fit Quality (R²):")
print(f"Linear: {r2_linear:.3f}")
print(f"Quadratic: {r2_quadratic:.3f}")
print(f"Power Law: {r2_power_law:.3f}")
print(f"\nBest fit: {'Power Law' if r2_power_law == max(r2_linear, r2_quadratic, r2_power_law) else 'Quadratic' if r2_quadratic == max(r2_linear, r2_quadratic, r2_power_law) else 'Linear'}")
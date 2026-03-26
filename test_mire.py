#%%
import matplotlib.pyplot as plt
import pandas as pd
#%%
csvfile = open('/home/gaim01/PyProjects/servicePlacementDataset/Simulations/Sim_20260326_131852/user_counts_log.csv', newline='')

data = csv.reader(csvfile, delimiter=',', quotechar='|')
print(next(data))  # Print the header row

#%%
file_path = '/home/gaim01/PyProjects/servicePlacementDataset/Simulations/Sim_20260326_131852/user_counts_log.csv'
df = pd.read_csv(file_path, header=None)

x = df.iloc[:, 0]
y = df.iloc[:, 1]

plt.figure(figsize=(10, 6))
plt.plot(x, y, label='User Counts')

plt.xlabel('Iteration')
plt.ylabel('Number of users')
plt.title('User Counts Over Iterations')
plt.legend()
plt.grid(True)

plt.show()




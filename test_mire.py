#%%
import matplotlib.pyplot as plt
import pandas as pd
import os


#%%
folder_path = '/home/gaim01/PyProjects/servicePlacementDataset/Simulations_official/Sim_small85_two_apps_per_node'

file_name = 'user_counts_log.csv'
image_name = 'user_count_graph.png'


file_path = f"{folder_path}/{file_name}"
full_path_image = os.path.join(folder_path, image_name)

df = pd.read_csv(file_path)

x = df.iloc[:, 0]
y = df.iloc[:, 1]

plt.figure(figsize=(10, 6))
plt.plot(x, y, label='User Counts')

plt.xlabel('Iteration')
plt.ylabel('Number of users')
plt.title('User Counts Over Iterations')
plt.legend()
plt.grid(False)

plt.savefig(full_path_image)
plt.show()

# %%
plt.savefig(full_path_image)
# %%

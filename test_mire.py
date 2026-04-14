#%%
import matplotlib.pyplot as plt
import pandas as pd
import os

#%%
# folder_path = '/home/gaim01/PyProjects/servicePlacementDataset/Simulations_official/Sim_small85_two_apps_per_node'
folder_path = '/Users/mireia/PyProjects/servicePlacementDataset/Simulations_official/Sim_small85_two_apps_per_node'

file_name = 'user_counts_log.csv'
image_name = 'user_count_graph.png'


file_path = f"{folder_path}/{file_name}"
full_path_image = os.path.join(folder_path, image_name)

df = pd.read_csv(file_path)

x = df.iloc[:, 0]
y = df.iloc[:, 1]

 #%%
 # EVOLUTION OF USERS
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

#%%
# HISTOGRAM OF MOVE_USER ACTIONS
move_user_counts = df[df['Action'] == 'move_user'].shape[0]
plt.figure(figsize=(6, 4))
plt.bar(['move_user'], [move_user_counts], color='blue')
plt.xlabel('Action')
plt.ylabel('Count')
plt.title('Count of move_user Actions')
plt.grid(False)
# plt.savefig(os.path.join(folder_path, 'move_user_count.png'))
plt.show()


# %%

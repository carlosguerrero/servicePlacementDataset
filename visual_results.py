#%%
import matplotlib.pyplot as plt
import pandas as pd
import os
from pathlib import Path

#%%
path_mac = Path('/Users/mireia/PyProjects/servicePlacementDataset/Simulations_official/Sim_small85_two_apps_per_node')
# path_linux = Path('/home/gaim01/PyProjects/servicePlacementDataset/Simulations_official/Sim_small85_two_apps_per_node')
path_linux = Path('/home/gaim01/PyProjects/servicePlacementDataset/Simulations_raw/Sim_20260416_131422')

BIN_SIZE = 50

def main() -> None:
    folder_path = path_mac if path_mac.exists() else path_linux
    file_name = 'user_counts_log.csv'
    image_name = 'user_count_graph.png'

    file_path = f"{folder_path}/{file_name}"
    full_path_image = os.path.join(folder_path, image_name)

    df = pd.read_csv(file_path)

    x = df.iloc[:, 0]
    y = df.iloc[:, 1]

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

    # Keep a second save for backwards-compatibility with older manual usage
    plt.savefig(full_path_image)

    # Action histograms
    plot_action_histogram(df, ['move_user'], BIN_SIZE, 'violet')
    plot_action_histogram(df, ['remove_user'], BIN_SIZE, 'lightgray')
    plot_action_histogram(df, ['new_user'], BIN_SIZE, 'lightgreen')
    plot_action_histogram(df, ['increase_request_ratio', 'decrease_request_ratio'], BIN_SIZE, 'lightcoral')


# %%
def plot_action_histogram(df, actions_list, bin_size, colour='lightblue'):
    """Plots a histogram of specified actions per iteration packs."""

    df['Pack'] = df['Iteration'] // bin_size
    
    filtered_df = df[df['Action'].isin(actions_list)]
    action_by_pack = filtered_df.groupby("Pack").size()
    
    all_packs = range(df['Pack'].min(), df['Pack'].max() + 1)
    action_by_pack = action_by_pack.reindex(all_packs, fill_value=0)

    plt.figure(figsize=(10, 6))

    plt.bar(action_by_pack.index, action_by_pack.values, color=colour, edgecolor='black')
    
    actions_str = ", ".join(actions_list)
    plt.xlabel(f'Iteration Packs (Groups of {bin_size})')
    plt.ylabel('Total Count of Actions')
    plt.title(f'Actions ({actions_str}) per {bin_size} Iterations')

    plt.xticks(action_by_pack.index, [f"{i*bin_size}-{(i*bin_size)+bin_size-1}" for i in action_by_pack.index])
    plt.ylim(0, bin_size) 
    
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.show()

# %%
if __name__ == "__main__":
    main()

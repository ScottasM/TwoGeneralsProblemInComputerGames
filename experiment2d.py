import random
from collections import defaultdict, deque
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


ROWS = 40
COLS = 40
SIM_TIME = 10000
PACKET_INTERVAL = 1
PACKET_LOSS = 0.20
RANDOM_SEED = 42444
first_arrival = {}
random.seed(RANDOM_SEED)

ORIGIN = (0, 0)
FINAL = (ROWS - 1, COLS - 1)

packet_id = 0
event_queue = deque()

received_packets = defaultdict(set)          
arrival_time = {}                            

packets_sent = defaultdict(int)            
packets_received = defaultdict(int)          
packets_lost = defaultdict(int)      
duplicates = defaultdict(int)       
packet_birth_time = {}  

#simulation
for current_time in range(SIM_TIME):

    #generate packet at start
    if current_time % PACKET_INTERVAL == 0:
        packet_id += 1
        received_packets[ORIGIN].add(packet_id)
        packet_birth_time[packet_id] = current_time
        event_queue.append((current_time, packet_id, ORIGIN, None))  #None = no previous node

    for _ in range(len(event_queue)):
        time, pid, (r, c), prev = event_queue.popleft()

        if time != current_time:
            event_queue.append((time, pid, (r, c)))
            continue

        if True:#retransmit in all directions
            neighbors = [(r+1,c), (r-1,c), (r,c+1), (r,c-1)]
        else: neighbors = [(r+1,c), (r,c+1)]

        for nr, nc in neighbors:
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                # do NOT go back where we came from
                if prev is not None and (nr, nc) == prev:
                    continue
                if nr < ROWS and nc < COLS:
                    packets_sent[(r, c)] += 1

                    if random.random() > PACKET_LOSS:
                        packets_received[(nr, nc)] += 1

                        if pid not in received_packets[(nr, nc)]:
                            received_packets[(nr, nc)].add(pid)
                            event_queue.append((current_time + 1, pid, (nr, nc), (r, c)))

                            if (nr, nc) == FINAL and pid not in arrival_time:
                                arrival_time[pid] = (current_time + 1) - packet_birth_time[pid]

                            if (nr, nc, pid) not in first_arrival:
                                first_arrival[(nr, nc, pid)] = (current_time + 1) - packet_birth_time[pid]
                        else:
                            duplicates[(nr, nc)] += 1
                    else:
                        packets_lost[(r, c)] += 1


records = []
for r in range(ROWS):
    for c in range(COLS):
        dist = r + c
        seen = len(received_packets[(r, c)])
        reach_pct = (seen / packet_id * 100) if packet_id else 0

        records.append({
            "row": r,
            "col": c,
            "distance": dist,
            "packets_seen": seen,
            "reach_pct": reach_pct,
            "packets_sent": packets_sent[(r, c)],
            "duplicates": duplicates[(r, c)]
        })

df = pd.DataFrame(records)


pdr = len(received_packets[FINAL]) / packet_id if packet_id else 0
mean_delay = np.mean(list(arrival_time.values())) if arrival_time else None
median_delay = np.median(list(arrival_time.values())) if arrival_time else None

total_sent = sum(packets_sent.values())
total_received = sum(packets_received.values())
total_duplicates = sum(duplicates.values())

print("===== GLOBAL METRICS =====")
print(f"Total packets generated: {packet_id}")
print(f"Packets received at destination: {len(received_packets[FINAL])}")
print(f"Packet Delivery Ratio (PDR): {pdr:.3f}")
print(f"Mean delay: {mean_delay}")
print(f"Median delay: {median_delay}")
print(f"Total transmissions: {total_sent}")
print(f"Total successful receptions: {total_received}")
print(f"Total duplicate receptions: {total_duplicates}")
print(f"Transmission efficiency: {total_received / total_sent:.3f}")

# 2. Heatmap: packets seen
heatmap_seen = np.zeros((ROWS, COLS))
for _, row in df.iterrows():
    heatmap_seen[int(row["row"]), int(row["col"])] = row["packets_seen"]

plt.figure()
plt.imshow(heatmap_seen, vmin=0, vmax=SIM_TIME)
plt.colorbar(label="Packets Seen")
plt.title("Packets Seen per Node")
plt.xlabel("Column")
plt.ylabel("Row")
plt.show()

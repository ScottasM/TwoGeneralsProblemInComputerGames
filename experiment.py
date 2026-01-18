import threading
import time
import random
import math
import queue
import matplotlib.pyplot as plt

# ------------------------------------------------------------
#CONFIGURATION
SIMULATION_TIME = 20.0      
TICK_RATE = 0.6             
SEND_INTERVAL = 0.6          
RECV_INTERVAL = 0.01          

MIN_PING = 0.02
MAX_PING = 0.06

PACKET_DROP = 0.3
OUTAGE_START = 5
OUTAGE_END = 8

MODE = "Acknowledgement"  #Raw | Acknowledgement | Prediction
RANDOM_SEED = 58
STEP_MODE = True #only for acknowledgement mode, it basically sends positions in steps instead of constantly simulating movement

# ------------------------------------------------------------
#INTERNAL STATE
random.seed(RANDOM_SEED)

network_queue = queue.Queue()
start_time = time.time()

sx, sy = 0.0, 0.0
vx, vy = 1.0, 0.0

rx, ry = 0.0, 0.0
last_received_time = 0.0
last_received_packet = None

next_seq = 1
awaiting_ack = {}

sent_packets = 0
received_packets = 0
dropped_packets = 0
retransmitted_packets = 0
last_received_seq = -1


errors = []
error_history = []
velocity_change_times = []

lock = threading.Lock()
running = True

# ------------------------------------------------------------
#PACKET
def make_packet(seq, t, x, y, vx, vy):
    return {
        "seq": seq,
        "time": t,
        "x": x,
        "y": y,
        "vx": vx,
        "vy": vy,
    }
#------------------------------------
#Network SEND
def send_packet(packet, simtime, candrop = True):
    """Send a packet with simulated network delay in a separate thread."""
    def delayed_send(pkt, send_time):
        global dropped_packets, received_packets

        #simulate outage
        if OUTAGE_START < send_time <= OUTAGE_END:
            with lock:
                dropped_packets += 1
            return

        if(candrop):
            #simulate random drop
            if random.random() < PACKET_DROP:
                with lock:
                    dropped_packets += 1
                return
        
        

        delay = random.uniform(MIN_PING, MAX_PING)
        time.sleep(delay)
        with lock:
            received_packets += 1
            network_queue.put(pkt)

    threading.Thread(target=delayed_send, args=(packet, simtime), daemon=True).start()

#------------------------------------------------------------
#receiver
def process_packet(packet, simtime):
    global rx, ry, last_received_packet, last_received_time, last_received_seq

    #ignore packates with seq numbers older than the last one received  
    if MODE == "Acknowledgement":
        seq = packet["seq"]
        if seq <= last_received_seq:
            return  # drop out-of-order packet
        last_received_seq = seq

    last_received_packet = packet
    last_received_time = packet["time"]   # sender time

    if MODE == "Acknowledgement":
        ack_up_to = packet["seq"]
        to_delete = [s for s in awaiting_ack if s <= ack_up_to]
        for s in to_delete:
            del awaiting_ack[s]

#------------------------------------------------------------
#prediction
def update_prediction(simtime):
    global rx, ry
    if last_received_packet is None:
        return

    dt = simtime - last_received_packet["time"]  #sender timestamp
    rx = last_received_packet["x"] + last_received_packet["vx"] * dt
    ry = last_received_packet["y"] + last_received_packet["vy"] * dt

#------------------------------------------------------------
#sender logic
def sender_thread():
    global sx, sy, vx, vy, sent_packets, retransmitted_packets, next_seq

    next_send = 0.0
    next_physics = 0.0
    next_velocity_change = 500
    last_physics = 0

    while running:
        simtime = time.time() - start_time

        stepped = False
        if simtime >= next_physics:
            dt = simtime - last_physics
            last_physics = simtime
            with lock:
                if(STEP_MODE):
                    sx += vx
                    sy += vy
                else:
                    sx+=vx*dt
                    sy+=vy*dt

            if STEP_MODE:
                stepped = True
                next_physics += random.uniform(TICK_RATE/2,TICK_RATE*2)
            else:
                next_physics += TICK_RATE

        if simtime >= next_velocity_change:
            with lock:
                angle = random.random() * 2 * math.pi
                vx = math.cos(angle)
                vy = math.sin(angle)
                velocity_change_times.append(simtime)
                next_velocity_change += random.uniform(3.0, 4.0)

        if simtime >= next_send or (STEP_MODE == True and stepped == True):
            with lock:
                if MODE == "Acknowledgement":
                    pkt = make_packet(next_seq, simtime, sx, sy, vx, vy)
                    awaiting_ack[next_seq] = pkt
                    next_seq += 1
                else:
                    pkt = make_packet(0, simtime, sx, sy, vx, vy)

                sent_packets += 1
                send_packet(pkt, simtime,True)
                next_send += SEND_INTERVAL

        if MODE == "Acknowledgement":
            with lock:
                
                for seq, pkt in list(awaiting_ack.items()):
                    if simtime - pkt["time"] >= 0.2:
                        pkt["time"] = simtime
                        retransmitted_packets += 1
                        send_packet(pkt, simtime,False)

        time.sleep(0.01)

# ------------------------------------------------------------
#RECEIVER THREAD
def receiver_thread():
    global rx, ry

    while running:
        simtime = time.time() - start_time

        try:
            packet = network_queue.get_nowait()
            with lock:
                process_packet(packet, simtime)
        except queue.Empty:
            pass

        with lock:
            if MODE == "Prediction":
                update_prediction(simtime)
            elif last_received_packet:
                rx = last_received_packet["x"]
                ry = last_received_packet["y"]

# ------------------------------------------------------------
#MAIN SIMULATION
send_thr = threading.Thread(target=sender_thread)
recv_thr = threading.Thread(target=receiver_thread)

send_thr.start()
recv_thr.start()

while (time.time() - start_time) < SIMULATION_TIME:
    with lock:
        simtime = time.time() - start_time
        err = math.dist((sx, sy), (rx, ry))
        errors.append(err)
        error_history.append((simtime, err))
    time.sleep(0.01)

running = False
send_thr.join()
recv_thr.join()


time.sleep(1)

# ------------------------------------------------------------
#RESULTS
average_error = sum(errors)/len(errors)
max_error = max(errors)
delivery_rate = received_packets / sent_packets * 100 if sent_packets else 0
retransmission_ratio = retransmitted_packets / sent_packets * 100 if sent_packets else 0

print("\n--- SIMULATION COMPLETE ---")
print(f"Mode: {MODE}")
print(f"Packets sent:           {sent_packets}")
print(f"Packets received:       {received_packets}")
print(f"Packets dropped:        {dropped_packets}")
print(f"Retransmitted packets:  {retransmitted_packets}")
print(f"Delivery rate:          {delivery_rate:.2f}%")
print(f"Retransmission ratio:   {retransmission_ratio:.2f}%")
print(f"Average error:          {average_error:.3f}")
print(f"Max error:              {max_error:.3f}")

# ------------------------------------------------------------
#PLOT WITH TEXT PANEL
times = [t for t, e in error_history]
errs = [e for t, e in error_history]

fig = plt.figure(figsize=(14, 6))

#----------------------------------
#Left plot
ax1 = fig.add_subplot(1, 2, 1)
ax1.plot(times, errs, label='Error')
ax1.axvspan(OUTAGE_START, OUTAGE_END, color='red', alpha=0.2, label='Outage')

first = True
for t in velocity_change_times:
    if first:
        ax1.axvline(x=t, color='blue', linestyle='--', alpha=0.7,
                    label="Velocity Change")
        first = False
    else:
        ax1.axvline(x=t, color='blue', linestyle='--', alpha=0.7)

ax1.set_xlabel('Time (s)')
ax1.set_ylabel('Position Error')
ax1.set_title(f'Position Error Over Time')
ax1.grid(True)
ax1.legend()

#----------------------------------
#Right-side text
ax2 = fig.add_subplot(1, 2, 2)
ax2.axis('off')

info = (
    f"Mode: {MODE}\n"
    f"Packets sent:           {sent_packets}\n"
    f"Packets received:       {received_packets}\n"
    f"Packets dropped:        {dropped_packets}\n"
    f"Retransmitted packets:  {retransmitted_packets}\n"
    f"Delivery rate:          {delivery_rate:.2f}%\n"
    f"Average error:          {average_error:.3f}\n"
    f"Max error:              {max_error:.3f}\n"

)

if STEP_MODE:
    info += f"Step and send interval:    {TICK_RATE/2:.4f} - {TICK_RATE*2:.4f}\n"
else : info+=    f"Send interval:          {SEND_INTERVAL:.3f}\n"

ax2.text(0.0, 0.5, info, fontsize=11, va='center', family='monospace')

plt.tight_layout()
plt.show()

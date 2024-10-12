# %%
from skyfield.api import load, wgs84, EarthSatellite
from datetime import datetime, UTC
import numpy as np
import socket
import os 
import subprocess as sub
import time
celestrak_satnogs = "https://celestrak.org/NORAD/elements/gp.php?GROUP=satnogs&FORMAT=tle"
celestrak_ham = "https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=tle"
output_dir = ""
date_format = "%Y%m%dT%H%M%S"
station = wgs84.latlon(57.014,9.986,20)
ts = load.timescale()
with open(".secret", "r") as f:
    rotator_ip = f.readline().rstrip()



def update_tle(filter):
    time = datetime.now(UTC).strftime(date_format) + "/"
    if not os.path.isdir(output_dir + time):
        os.umask(0)
        os.makedirs(output_dir + time)
    satellites = load.tle_file(celestrak_satnogs,filename=output_dir + time + "tle.txt",reload=True)
    satellites.extend(load.tle_file(celestrak_ham, filename=output_dir + time + "ham_tle.txt", reload=True))
    sats_by_name = {sat.name: sat for sat in satellites}
    for key in filter:
        filter[key][0] = sats_by_name[key]
    return filter, output_dir + time


def find_passes(filter: dict):
    starttime = ts.utc(datetime.now(tz=UTC))
    
    time_extension = 120/86400
    pass_list = []

    for key in filter:
        sat: EarthSatellite = filter[key][0]
        tt, events = sat.find_events(station, starttime, starttime +1 , 5)
        
        idx_start = np.argwhere(events == 0)
        idx_end = np.argwhere(events == 2)

        # Only take whole passes
        if idx_start[-1] > idx_end[-1]:
            idx_start = idx_start[:-1]

        for idx, val in enumerate(idx_start):
            pass_list.append([tt[val]-time_extension,
                              tt[idx_end[idx]]+time_extension,
                              key])
    # Sort pass list
    keep = []
    discard = []
    for idx, entry in enumerate(pass_list):
        start, end, key = entry
        for j, entry_cmp in enumerate(pass_list[idx+1:]):
            start_cmp, end_cmp, key_cmp = entry_cmp
            if start < start_cmp and end < start_cmp:
                pass
            elif start > end_cmp and end > end_cmp:
                pass
            else:
                if filter[key][2] < filter[key_cmp][2]:
                    discard.append(idx+j+1)
                else:
                    discard.append(idx)
                    break
        if idx not in discard:
            keep.append(entry)
    return sorted(keep)

class rotator():
    def __init__(self):
        self.socket = socket.socket()
        self.cur_az = 0
        self.cur_el = 0
        self.threshold = 1
    
    def connect(self, ip, port = 4533):
        self.socket.connect((ip, port))

    def _get_pos(self):
        self.socket.send("p\n".encode())
        r = self.socket.recv(1024)
        msg = r.decode().split()
        self.cur_az = float(msg[0])
        self.cur_el = float(msg[1])

    def _set_pos(self, az, el):
        msg = f"P{az:3.2f} {el:3.2f}\n"
        self.socket.send(msg.encode())
        r = self.socket.recv(1024)

    def _stop(self):
        self.socket.send("S".encode())
        r = self.socket.recv(1024)

    def track(self, sat):
        set_az, set_el = 0,0
        log = []
        diff = sat - station
        while set_el <=0:
            el, az, dist = diff.at(ts.utc(datetime.now(UTC))).altaz()
            set_el = el.degrees
            time.sleep(1)
        
        while set_el >= 1:
            self._get_pos()
            time = datetime.now(UTC)
            el, az, dist = diff.at(ts.utc(time)).altaz()
            set_el, set_az = el.degrees, az.degrees
            log.append(np.array([time.timestamp(), az, set_az, el, set_el]))
            if abs(self.cur_el - set_el) > self.threshold:
                self._set_pos(set_az,set_el)
            elif abs(self.cur_az - set_az) > self.threshold:
                self._set_pos(set_az,set_el)
            time.sleep(1)
        self._stop()
        return np.array(log)



# %%
if __name__ == "__main__":

    def main():
        rotorian = rotator()
        rotorian.connect(rotator_ip)
        my_sats = {
            "SONATE-2": [None, int(437.025e6), 4],
            "VZLUSAT-2": [None, int(437.325e6), 2],
            "UVSQ-SAT": [None, int(437.02e6), 3],
        }
        while True:
            my_sats, active_path = update_tle(my_sats)
            passes = find_passes(my_sats)
            for start,end,key in passes:
                time_now = datetime.now(UTC)
                start_time = start.utc_datetime()[0]
                if time_now < start_time:
                    diff = (start_time - time_now).total_seconds()
                    print(f"Next pass for {key} in {diff} seconds.")
                    time.sleep(diff)
                else:
                    continue
                
                sat, freq, _ = my_sats[key]
                radio_process = sub.Popen(["python3","satellite_tracker.py", "-f",str(freq), "-p", active_path + key])
                log = rotorian.track(sat)
                radio_process.kill()
                np.savetxt(active_path + key + "_station.csv", log)


main()

# HAM Tracker
This software interacts with the AAU Satlab ground station, and autotrack the specified satellites in main via `rotctl` interface.  

TLE and upcoming passes are updated daily.  


## Structure
```
├── main_tracker.py
├── sniffer.grc
├── LICENSE
├── README.md
└── .gitignore
```
- `main_tracker.py` main program, containing rotor controller.  
- `sniffer.grc` gnuradio script, to automatically save IQ samples from a USRP B210 SDR.
# Motor Overflow cheat sheet

A quick reference for people already set up. If you're starting out, read the
[README](../README.md) and [setup guide](SETUP_INSTRUCTIONS.md) first.

## What each file does

| File | What it does |
| --- | --- |
| `motor_overflow9.py` | The full experiment: setup, questionnaires, calibration, a 30 s resting baseline, then the four conditions. Sends the markers and writes every CSV. |
| `motor_execution.py` | Runs the ME condition alone, with one trial at each distance and no marker hardware. |
| `bbtk_trigger.py` | Sends markers through the BBTK module, and groups recorded marker times into trials. Can also list ports or decode a file. |
| `trigger_test.py` | Sends test markers without running the task. |
| `media\ao_video_*.mp4` | The eight action-observation videos (2 hand models × 2 hands × 2 target sizes). Not included: [add your own](../README.md#add-the-videos). |
| `media\bell.wav`, `media\nimbl_logo.png` | The trial bell and welcome-screen logo. The task runs without them. |
| `spike2\Motor_Overflow_Config_v4.s2cx` | The Spike2 recording configuration: two EMG channels plus channel 32, `Trig`. |
| `spike2\mo_label_export.s2s` | Run after a session. Labels the markers `1a 1b 1c … 8c` by their spacing and writes a report. |
| `spike2\smrx_to_mat.s2s` | Optional. Exports every `.smrx` file in a folder to MATLAB `.mat` files. |

## Command Prompt

Run these commands from the `motor_overflow` folder on the task computer. If `py` is
not recognised, use `python`. If the BBTK is not on `COM12`, add `--port COMn` to any
`trigger_test.py` command.

```
cd path\to\motor_overflow
```

### Setup (once per computer)

| Command | What it does |
| --- | --- |
| `py -m pip install pygame-ce opencv-python pyserial` | Installs the three packages the task needs. |
| `py -c "import serial; print(serial.Serial)"` | Checks pyserial is the right package. It should print `serial.serialwin32.Serial`. |
| `py -m pip uninstall -y serial pyserial` then `py -m pip install pyserial` | Fixes a computer where the wrong `serial` package was installed. |
| `devmgmt.msc` | Opens Device Manager. Find the BBTK's COM port and set its Latency Timer to 1 ms (Port Settings → Advanced). |

### Checks without hardware

| Command | What it does |
| --- | --- |
| `py bbtk_trigger.py ports` | Lists every COM port. Compare the list with the BBTK plugged in and unplugged to identify it. |
| `py trigger_test.py --mock --mode single` | Simulates the test and prints what would have been sent, with timings. |
| `py bbtk_trigger.py decode <file>` | Groups marker times from a file into trials. The first column must be the time in ms. A complete block shows `triplets: 8`. |

### Test markers (BBTK connected, Spike2 sampling)

| Command | What it does |
| --- | --- |
| `py trigger_test.py --mode single` | Sends 5 markers, 2 s apart. Expect 5 markers on `Trig`, all `AA`. |
| `py trigger_test.py --mode trial --trials 3` | Sends 3 simulated trials. Expect 9 markers in three groups. |
| `py trigger_test.py --mode block` | Sends one simulated block of 8 trials (about 2.5 min). Save the Spike2 file as `bench_mo_ME_S_b1.smrx` and run `mo_label_export.s2s` on it. Expect `1a 1b 1c … 8c`, block 1, size S. |
| `Ctrl+C` | Stops the test. |

### Running the task

| Command or key | What it does |
| --- | --- |
| `py motor_overflow9.py` | Starts the experiment. On the first screen, the status should read `BBTK answered on COMn`. |
| `set MO_TRIGGER_MOCK=1` | Simulates the BBTK on the next run in this window, for practice only. The setup screen shows MOCK MODE in red. |
| `set MO_TRIGGER_MOCK=` | Turns simulation off in this window. |
| `Esc` | Quits the task and releases the COM port. |
| `Shift+R` | On a Trial Complete or Block Complete screen, redoes the current block from trial 1. A confirmation screen shows what to save the current recording as. Trials already run stay in the data, marked `discarded` = 1. |
| `Shift+S` | Skips to the next screen. A skipped trial writes **no** data. A skipped question saves a placeholder answer, so use this for testing only. |

## Recording computer

Once per computer: Edit → Preferences → Sampling → tick **Use rear connector for
events**.

For every session:

1. Load `spike2\Motor_Overflow_Config_v4.s2cx`, then choose Sample → Start.
2. At **Baseline Complete**, stop, save as `{pid}_mo_REST.smrx`, and start a new file.
3. At each **Block Complete**, stop, save as `{pid}_mo_{COND}_{S|L}_b{n}.smrx`, and
   start a new file before the participant taps Continue.
4. After the session, run `spike2\mo_label_export.s2s` (Script → Run) on the 16 block
   files.

That makes 17 files per session. For example, `012_mo_AO_L_b2.smrx` is participant
012, condition AO, large target, block 2. Block sizes are in the participant's
`mo_session` CSV.

## Cable

Use the straight DB25 cable supplied with the BBTK, plugged into the rear Digital
Inputs connector on the Micro1401. Only the strobe signal reaches the 1401 (BBTK line
8, pin 23), so every marker reads `AA` and the labelling script tells them apart by
spacing.

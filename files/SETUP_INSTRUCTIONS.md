# Motor Overflow setup guide

This guide takes you from an empty setup to a finished recording session. It
assumes no background in this field, but you will need the equipment listed
below. Unfamiliar terms are defined in the [README](../README.md#terms).

To try the task without any of this equipment, see
[Try it](../README.md#try-it) in the README.

## 1. What the system does

The task computer runs the experiment while the recording computer records muscle
activity (EMG). To line the two up afterwards, the task sends three time stamps,
called **markers**, into the recording during each trial:

| Marker | Moment | Spacing |
| --- | --- | --- |
| a | The participant's finger lands on the X, and a short rest starts | — |
| b | The trial clock starts. This is t = 0 in the task's CSV file | 2200 ms after a |
| c | The closing bell rings and the trial ends | 15 000 ms after b |

The cable carries only the timing of a marker, not a code, so every marker reads
the same value in Spike2: `AA`. A script run after the session tells them apart by
their spacing, then labels them `1a 1b 1c … 8c` (trial number + letter).

Each condition (ME, AO, KMI, VMI) has four blocks of 8 trials, with one target
size per block. Sizes alternate: Small, Large, Small, Large, or the reverse. Each
block is recorded to **its own Spike2 file**:

- 8 trials × 3 markers = **24 markers per block file**
- 4 conditions × 4 blocks = **16 block files per session**
- **1 additional rest file**, holding calibration and a 30 s resting baseline,
  named `{pid}_mo_REST.smrx`. Its two markers, 15 s apart, sit 7.5 s and 22.5 s
  into the rest and mark out the 15 s baseline.

If the marker hardware fails mid-session, the task carries on and records that
the markers were not sent. The task's timing, touch handling, trial order and
questionnaires do not depend on it.

### Equipment

| Item | Purpose |
| --- | --- |
| Windows touchscreen computer | Runs the task |
| Second Windows computer with Spike2 | Records the data |
| CED Micro1401 and an EMG amplifier (a CED 1902 in this setup) | Pick up and digitise the muscle signals |
| Black Box ToolKit (BBTK) USB TTL module, with its USB and DB25 cables | Sends the markers |

### How a marker travels

BBTK output line 8 connects to the 1401's Data Available input (Digital Input pin
23). The line normally sits high. To send a marker, Python sends `80` (line up),
then `00` (line down), and the 1401 records a marker at that drop. One screen
frame later, the line goes back up, ready for the next marker.

## 2. File guide

### Task computer: the `motor_overflow` folder

| File | What it is | When it is used |
| --- | --- | --- |
| `motor_overflow9.py` | The task. It shows the Trigger Setup screen, sends the markers, and records each trial's `trig_ok` result and `spike2_file` in the task CSV. | Every session |
| `bbtk_trigger.py` | The marker connection and decoder. The task imports it, so it must stay in the same folder. | Automatically, and for checks |
| `trigger_test.py` | Sends test markers without running the task. `--mode single` sends 5 markers, `--mode trial` sends simulated trials, and `--mode block` sends one simulated block (about 2.5 min). `--mock` needs no hardware. | Once before your first participant, and if the cable is ever in doubt |
| `media\` | The bell sound and the logo, plus the eight `ao_video_*.mp4` videos you add (see A1). This folder must stay beside `motor_overflow9.py`. | By the task |
| `motor_execution.py` | Runs the ME condition alone, with one trial at each distance and no marker hardware. It must stay beside `motor_overflow9.py`. | Optional |

### Recording computer: the `spike2` folder

| File | What it is | When it is used |
| --- | --- | --- |
| `Motor_Overflow_Config_v4.s2cx` | The recording configuration: two EMG channels plus channel 32, `Trig`, for markers. | Load before every session |
| `mo_label_export.s2s` | The labelling script. It groups markers into trials by spacing, adds a `Labels` channel to each file, and writes `{name}_labels_report.txt`. It skips files ending `_partial`. | After recording |
| `smrx_to_mat.s2s` | Exports every `.smrx` file in a folder to a MATLAB `.mat` file beside it, overwriting any `.mat` with the same name. The recordings are not changed. | Optional, after recording |

## 3. Part A: Task computer

### A1. Install (once per computer)

1. Install Python 3.14 for Windows from python.org, with "Add to PATH" and the
   `py` launcher ticked.
2. Download this repository and put the `motor_overflow` folder wherever you like.
   The task saves its data inside that folder, so choose somewhere with enough
   space and regular backups.
3. Open **Command Prompt** and go to the folder:

   ```
   cd path\to\motor_overflow
   ```

4. Install the packages the task needs:

   ```
   py -m pip install pygame-ce opencv-python pyserial
   ```

   Do not install a package called plain `serial`. It is unrelated and breaks
   pyserial.

5. Add the eight hand videos to the `media` folder. They are not included in this
   repository, so you need to record your own. The README explains
   [what to record and how to name the files](../README.md#add-the-videos).

If `py` is not recognised, use `python` in every command below.

### A2. Find the BBTK's COM port

A COM port is the name Windows gives the BBTK's connection. Plug the BBTK into the
task computer, then use either of these:

- **Device Manager → Ports (COM & LPT):** look for the USB serial or Black Box
  entry, such as `COM3`.
- **Command Prompt:** run `py bbtk_trigger.py ports` to list every port.

The task tries `COM12` first. If your BBTK is on another port, the Trigger Setup
screen lists the available ports as buttons, so you can tap the right one without
editing any code.

While in Device Manager, open the port's **Port Settings → Advanced** and set
**Latency Timer** to 1 ms. Otherwise, the USB driver can delay markers by up to
16 ms.

### A3. Practice run without hardware (optional)

Add the videos first. Otherwise, each AO trial stops at a **Video Not Found** screen,
and the check below won't work.

```
set MO_TRIGGER_MOCK=1
py motor_overflow9.py
```

The setup screen shows **MOCK MODE** in red. Run through a session with the mouse,
using an ID you won't give a real participant, such as 998. Afterwards,
`mo_task\998_rh_mo_task.csv` should have 128 rows, each with `trig_ok = 1`.

Then delete that ID's files from every `mo_*` folder. Otherwise, the task won't let
you use that ID again.

## 4. Part B: Hardware

```
Task computer USB-A → BBTK (USB-B) → DB25 cable → CED Micro1401 rear digital connector
```

Signals flow from the BBTK into the 1401. Nothing else links the two computers, so
the 1401 is the only shared clock. The EMG amplifier connects to the 1401 as usual,
and the marker cable does not touch it.

### B1. The cable

Use the DB25 male-to-female cable supplied with the BBTK, plugged into the rear
Digital Inputs connector. The two devices' pin layouts differ, so only the strobe
signal gets through: BBTK line 8 reaches pin 23 (Data Available). As a result,
**every marker arrives at the right time with the same value, `AA`**. This is
expected, and nothing needs changing.

### B2. Optional: use an Event channel

The rear connector also carries event inputs (Edit → Preferences → Sampling →
*Use rear connector for events*). BBTK line 8 pulses low for 5 ms at every marker
and lands on 1401 pin 9, while lines 1–3 land on pins 2–4.

If one of those pins is an event input on your 1401, a falling-edge **Event-**
channel titled `Trig` on that port records the same pulses. To find out, add Event
channels on every event port, run `py trigger_test.py --mode single`, and see which
one responds. If one does, you can use it instead of the Digital Marker channel,
and the script will label it the same way.

## 5. Part C: Recording computer

Copy the `spike2` folder anywhere on the recording computer.

### C1. Preferences (once per computer)

**Edit → Preferences → Sampling:** tick **Use rear connector for events**.

### C2. Load the supplied configuration

1. In Spike2, choose **File → Load Configuration…** →
   `Motor_Overflow_Config_v4.s2cx`.
2. Choose **Sample → Sampling Configuration…** → **Channels** tab, and confirm:

   | Ch | Title | Type | Port | Rate |
   | --- | --- | --- | --- | --- |
   | 1 | FDI_L (left hand) | Waveform | ADC 2 | 2000 Hz |
   | 2 | FDI_R (right hand) | Waveform | ADC 1 | 2000 Hz |
   | 31 | Keyboard | Marker | — | — |
   | 32 | Trig | Digital Marker | Rear Digital Input | Max 100/s |

3. Make sure your EMG cables go to the ports shown, or change the ports here and
   choose **File → Save Configuration**.

The maximum rate of 100/s only sets aside memory. The real rate is under one marker
per second.

### Display

After your first recording, right-click the **Trig** channel → **Draw Mode** and
choose a mode that shows the marker code as text, so each marker appears as `AA`.
After the labelling script has run, the `Labels` channel shows `1a 1b 1c`. Save the
configuration again.

## 6. Part D: Test the markers (before your first participant)

Turn on both computers and connect the cable. Load the configuration in Spike2, and
open Command Prompt in the `motor_overflow` folder on the task computer. If the BBTK
is not on `COM12`, add `--port COMn` to each command.

| Step | Do | Passes when |
| --- | --- | --- |
| 1 | In Spike2, choose Sample → Start. On the task computer, run `py trigger_test.py --mode single` | Exactly 5 markers on `Trig`, 2 s apart, all `AA` |
| 2 | Start a new recording. Run `py trigger_test.py --mode trial --trials 3` | 3 groups of 3 markers, spaced 2.2 s then 15 s |
| 3 | Start a new recording. Run `py trigger_test.py --mode block` (about 2.5 min). Stop, then save as `bench_mo_ME_S_b1.smrx` in a folder of its own | 24 markers on `Trig` |
| 4 | In Spike2, open `mo_label_export.s2s`, choose Script → Run, answer No, and pick that folder | The report shows `block: 1`, `size: S`, `triplets: 8`, `labels: numbered 1-8`, `unmatched: 0`, and the `Labels` channel reads `1a 1b 1c … 8c` |

Step 4 also tests the script's `VERIFY` lines, which use Spike2 functions that were
not confirmed against the documentation. If the script stops with an error, check
the call on that line against Spike2 Help (press F1 on the function name) and fix
it. Once the test passes, delete the `UNTESTED` line from the script's header.

## 7. Part E: Running a session

1. Turn on the 1401 and the EMG amplifier. Plug the BBTK into the task computer.
2. In Spike2, choose File → Load Configuration → `Motor_Overflow_Config_v4.s2cx`.
3. On the task computer, run `py motor_overflow9.py`. The **Trigger Setup** screen
   appears.
4. Check the status line is green: **BBTK answered on COMn — now check Spike2**. If
   it is red, it says why. Tap the correct port button, or fix the cause and tap
   **Rescan**.
5. **Start sampling in Spike2.**
6. Tap **Test Pulse** two or three times, a second apart. Each tap should add one
   marker on `Trig`, reading `AA`.
7. Tap **Continue** and hand over the touchscreen.
8. **Record the resting baseline to its own file.**
   1. Sampling runs through calibration into the **Resting Baseline** instructions.
      Tap Continue.
   2. On the rest screen, have the participant rest both hands off to the side.
      **You**, not the participant, then tap **Begin**.
   3. The button turns grey for 30 s. No timer is shown, and the task sends two
      markers 15 s apart.
   4. At **Baseline Complete**, choose Sample → Stop, then **File → Save As** →
      `{pid}_mo_REST.smrx`.
   5. Start sampling a new file before the participant taps **Continue**.
9. **Record each block to its own file, 16 in total.** At every **Block Complete**
   screen:
   1. Choose Sample → Stop, then **File → Save As** →
      `{pid}_mo_{COND}_{S|L}_b{n}.smrx`. For example, `012_mo_ME_S_b1.smrx` is
      participant 012, condition ME, small target, block 1.
   2. Start sampling a new file **before** the participant taps Continue, because the
      next trial or instructions follow straight away. Between blocks in a condition,
      Continue stays locked for a 15 s rest and shows a countdown.

   Each participant's block sizes are in their `mo_session` CSV (`{cond}_block_seq`),
   so note them down before the session. A hand code after the ID, as in
   `012_rh_mo_ME_S_b1.smrx`, is also accepted. Do not press keys in Spike2.
10. After a condition's 4th block, the questionnaires follow. The new file can keep
    sampling through them, as no markers are sent. After the very last block, stop
    and save that file.
11. Close the task. This releases the COM port.

Each block file should contain 24 markers in groups of three, spaced 2.2 s then
15 s. The rest file holds your test pulses, perhaps one extra marker from when the
task opened the port, and finally the two baseline markers.

If a Trial Complete screen shows **Trigger link lost — tell the experimenter**, note
the trial and let the session finish. Then see Part G.

### If something goes wrong

**To redo a block** (for example, the participant misunderstood or an EMG sensor came
off), press `Shift+R` on any Trial Complete or Block Complete screen of that block.
Before tapping Redo Block on the confirmation screen:

1. Stop sampling.
2. Save the recording as `{pid}_mo_{COND}_{S|L}_b{n}_try{k}_partial.smrx`. The screen
   shows the exact name. If you already saved it under the normal name, rename it.
3. Start a new file.

The block restarts at trial 1 and is recorded under the normal name. When analysing
the task data, keep rows with `discarded` = 0.

**If the task crashes:**

1. Stop sampling and save as `{pid}_mo_{COND}_{S|L}_b{n}_partial.smrx`. The labelling
   script skips this file.
2. To rerun the same ID, move that ID's files out of every `mo_*` folder in
   `motor_overflow` and into an archive folder.
3. Restart the whole session with a new Spike2 file.

## 8. Part F: After recording, label the markers

1. Put the block `.smrx` files in one folder (16 per session). Leave out
   `{pid}_mo_REST.smrx`. It has no trials, so the script would report it as failed.
2. In Spike2, choose File → Open → `mo_label_export.s2s`, then **Script → Run**.
3. At the first question, choose Yes for one file or No for a whole folder.
4. When the summary appears, read the Log window and each
   `{name}_labels_report.txt`.

The script produces the following for each file:

| Output | Content |
| --- | --- |
| `Labels` channel, saved into the `.smrx` | One label per matched marker, reading `1a 1b 1c 2a … 8c`. Each carries the codes `[letter, block, trial, 0]`, where letter is 1 = a, 2 = b, 3 = c, and block comes from the file name (0 if the name has no `_b{n}`). Re-running replaces this channel. |
| `{name}_labels_report.txt` | The participant, condition, block and size read from the file name, with anything missing flagged CHECK. Also the marker and trial counts, label status, any unmatched markers, and the a→b and b→c timings. |

To read the report:

| Report says | Meaning | What to do |
| --- | --- | --- |
| 8 triplets, `labels: numbered 1-8` | Every trial was labelled | Nothing |
| 8 triplets, some unmatched | Test pulses, or the marker from opening the port | Nothing |
| Not 8 triplets, `labels: CHECK` | A marker was lost, or a trial's timing fell outside the expected range. Trials are numbered in the order found, so every number after a lost trial is one too low | See Part G |
| "no Trig channel" or "neither a marker nor an event channel" | The wrong configuration was loaded, or the channel was renamed | Load the supplied configuration or rename the channel to `Trig`, then re-run |

## 9. Part G: The data and how it joins

### Marker columns in `{pid}_{hand}_mo_task.csv` (one row per trial)

| Column | Meaning |
| --- | --- |
| `spike2_file` | The Spike2 file this trial belongs in, such as `012_mo_ME_L_b2` |
| `block_index`, `trial_in_block` | Block 1–4 within the condition, and trial 1–8 within the block |
| `trig_ok` | 1 if all three markers were sent, otherwise 0 |

### Matching Spike2 recordings to the CSV files

- The Spike2 file name, without `.smrx`, equals `spike2_file` in the task CSV. Use it
  to match the two.
- On the `Labels` channel, code 1 is the marker letter (1 = a, 2 = b, 3 = c), code 2
  equals `block_index`, and code 3 equals `trial_in_block`. Every `b` item is the
  moment a trial's clock started.
- The `Trig` channel holds every raw marker, including test pulses and strays.
- Use a→b as the rest baseline and b→c as the trial when choosing EMG time windows.

### Recovering a trial with missing markers

Each unmatched marker in the report points to a broken trial. Use the timing to work
out which marker survived. For example, a pair about 17.2 s apart means that trial's
b was lost. Count the good trials before it to find its position.

Rows with `trig_ok = 0` show which trial's markers the task never sent. The task does
not record its own marker times, so the gaps in the recording are the only way to
place a broken trial.

## 10. Part H: Troubleshooting

| Problem | Fix |
| --- | --- |
| Setup screen says `COM12 not found` | Tap the BBTK's port in the list, or replug it and tap Rescan |
| Setup screen says `in use by another program` | Close the other program, such as an old task window or a terminal, then tap Rescan |
| Setup screen says `pyserial not installed` | Run `py -m pip install pyserial` |
| Setup screen says `wrong 'serial' package installed` | Run `py -m pip uninstall -y serial pyserial`, then `py -m pip install pyserial` |
| No markers on `Trig` for test pulses | Check that the cable is in the Digital **Input** connector, channel 32 is present, and sampling has started |
| Every marker reads `AA` | This is expected. See Part B1 |
| Report shows 0 triplets, though markers are visible | The channel is not titled `Trig`, or timing constants were changed in only one file. The Log shows the first gaps next to the ranges they must fall in |
| Report shows some triplets missing | A stray or missing pulse. See Part G |
| Task shows `Video Not Found` | The videos are not included in this repository, so [add your own](../README.md#add-the-videos) to the `media` folder. The screen names the file it expected |
| Task won't start: `ModuleNotFoundError: bbtk_trigger` | Put `bbtk_trigger.py` beside `motor_overflow9.py` |
| Task won't start: `AssertionError` | The trial timing constants no longer match. `REST_MS + BEGIN_MS` must equal 2200, and `TRIAL_SECONDS × 1000` must equal 15000. Change all three files together or restore the values |

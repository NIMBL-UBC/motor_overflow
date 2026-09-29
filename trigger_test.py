"""Bench tool: sends digital markers to Spike2 through the BBTK without running
the task. Run from a Command Prompt in this folder while Spike2 is sampling.

    py trigger_test.py [--port COM12] [--mock] [--mode single|trial|block] [--trials N]

single   5 test markers, 2 s apart. Look for 5 markers on Trig.
trial    N trials (default 3): a, +2200 ms b, +15000 ms c, then
         a 5 s gap.
block    one block: 8 trials, 3 s between them (about 2.5 minutes). Save the
         Spike2 file and run mo_label_export.s2s on it: the report must show
         8 triplets, labelled 1a 1b 1c ... 8c. Each block of the study is
         recorded to its own Spike2 file, so this is what one file looks like.

Ctrl+C stops it and puts the line up. --mock uses the fake port and prints
every write at the end so the timing can be checked without hardware.
"""

import argparse
import os
import sys
import time

# The marker code shared with the main task.
import bbtk_trigger as bt


def wait_ms(trig, ms, t0):
    """Sleep in 1 ms steps, servicing the trigger so the line goes back up on time."""
    end = t0 + ms / 1000.0
    while True:
        trig.service()
        now = time.perf_counter()
        if now >= end:
            return
        time.sleep(min(0.001, end - now))


# Sends one marker and prints when it went out, or why it failed.
def send(trig, label, start, tag=""):
    t = trig.pulse(label)
    stamp = (time.perf_counter() - start) * 1000.0
    what = f"{label}{tag}"
    if t is None:
        print(f"{stamp:10.1f} ms  {what}  FAILED: {trig.error}")
    else:
        print(f"{stamp:10.1f} ms  {what}")
    return time.perf_counter()


# Mode 'single': five test markers, two seconds apart.
def run_single(trig, start):
    for i in range(5):
        t = send(trig, "test", start, f" {i + 1}")
        if i < 4:
            wait_ms(trig, 2000, t)


# Modes 'trial' and 'block': markers a, b and c with the same gaps as a real trial.
def run_trials(trig, start, n_trials, gap_ms, block=None):
    for k in range(n_trials):
        tag = f" block {block}, trial {k + 1}" if block else f" trial {k + 1}"
        t = send(trig, "a", start, tag)
        wait_ms(trig, bt.AB_NOMINAL_MS, t)
        t = send(trig, "b", start, tag)
        wait_ms(trig, bt.BC_NOMINAL_MS, t)
        t = send(trig, "c", start, tag)
        if k < n_trials - 1:
            wait_ms(trig, gap_ms, t)
    return t


# Reads the options typed at the Command Prompt, connects to the box and runs the chosen mode.
def main():
    # The options that can be typed after the file name.
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default=bt.DEFAULT_PORT)
    ap.add_argument("--mock", action="store_true", help="no hardware; use the fake port")
    ap.add_argument("--mode", choices=("single", "trial", "block"), default="single")
    ap.add_argument("--trials", type=int, default=3, help="trials for --mode trial")
    args = ap.parse_args()

    if args.mock:
        os.environ[bt.MOCK_ENV] = "1"
    # Connect to the BBTK box. Stop here if that fails.
    trig = bt.Trigger()
    ok, msg = trig.open(args.port)
    print(("mock port" if trig.mock else "port") + f": {msg}")
    if ok and not trig.answered:
        print("WARNING: the module did not answer the ## ping. Markers may not be going out.")
    if not ok:
        print("ports seen:", trig.list_ports() or "none")
        return 1

    # How many markers Spike2 should show when this finishes.
    n_expected = {"single": 5, "trial": 3 * args.trials,
                  "block": 3 * bt.TRIALS_PER_BLOCK}[args.mode]
    print(f"mode {args.mode}: {n_expected} markers. Ctrl+C to stop.")
    fake = trig._ser if trig.mock else None
    # Send the markers. Ctrl+C stops early. The marker line is always reset at the end.
    start = time.perf_counter()
    try:
        if args.mode == "single":
            run_single(trig, start)
        elif args.mode == "trial":
            run_trials(trig, start, args.trials, 5000)
        else:
            run_trials(trig, start, bt.TRIALS_PER_BLOCK, 3000)
        wait_ms(trig, bt.PULSE_MIN_MS + 5, time.perf_counter())
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        trig.close()

    # Summary. In mock mode, also list every command that would have been sent to the box.
    if trig.failed:
        print(f"link failed during the run: {trig.error}")
    if fake is not None:
        print("\nFakeSerial write log (ms since epoch, bytes):")
        for t_ms, data in fake.writes:
            print(f"{t_ms - trig.epoch * 1000.0:10.1f}  {data!r}")
        print(f"{len(fake.writes)} writes")
    print("done")
    return 0


# Only run main() when this file is started directly.
if __name__ == "__main__":
    sys.exit(main())

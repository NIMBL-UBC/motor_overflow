# The Motor Execution condition on its own, with no trigger link: handedness,
# participant ID, calibration, then one ME trial at each calibrated distance.
# Everything else comes from motor_overflow9.py, so fixes there apply here too.

import motor_overflow9 as mo

# show the seconds left during each trial
mo.SHOW_COUNTDOWN = True

# The study runs four trials at each distance, shuffled together. Here there is
# one of each. Nothing is being compared across the two, so the order is written
# down rather than counterbalanced; swap the names to run them the other way.
TRIAL_SIZES = ["Small", "Large"]

CONDITION = "ME"
LABEL     = "Motor Execution"
# the study's ME instructions say eight trials; this runs two
INSTRUCTION = tuple(line.replace("Eight trials.", "Two trials.") for line in mo.ME_INSTRUCTION)

handedness = mo.screen_handedness()
mo.configure_active_side(handedness)

pid_raw    = mo.screen_text_input("Enter Participant ID", "(001 – 999)", mo.validate_pid, max_len=3)
pid        = f"{int(pid_raw):03d}"

calib_instruction = (mo.CALIBRATION_INSTRUCTION_RH if handedness == "rh"
                     else mo.CALIBRATION_INSTRUCTION_LH)

# Calibration runs again and again until the experimenter is happy with it. The
# instruction screen sits inside the loop on purpose: tapping Begin forces the
# hand off the glass before calibration starts watching the screen again.
while True:
    mo.screen_instructions(calib_instruction, "Begin", title="Calibration Instructions",
                           side=mo.button_side(handedness))
    peak_dist, large_amp, small_amp, angle = mo.run_calibration(pid, handedness)
    if mo.screen_calib_results(peak_dist, large_amp, small_amp, angle, handedness) != "redo":
        break

mo.screen_instructions(INSTRUCTION, title=LABEL, side=mo.button_side(handedness))

# The two columns run_condition would have filled in are left as they are: there
# is no condition order here, and no block for these trials to sit in.
# size_position stays 1 throughout because each distance runs exactly once.
amps = {"Small": small_amp, "Large": large_amp}

for i, size in enumerate(TRIAL_SIZES, 1):
    mo.BLOCK_CTX["trial_index"]   = i
    mo.BLOCK_CTX["size_position"] = 1

    mo.run_task_block(pid, handedness, CONDITION, amps[size], angle, LABEL, size)

    # the trial rings its own bell as its timer expires; this is just the pause after
    mo.screen_trial_complete(handedness, LABEL, i, len(TRIAL_SIZES))

mo.screen_task_complete()

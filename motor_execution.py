
# Runs the Motor Execution task on its own, with no marker box: hand, participant ID,
# calibration, then one trial at each target distance. All the screens come from
# motor_overflow9.py, so changes there apply here too.
import motor_overflow9 as mo

# Show the seconds left during each trial.
mo.SHOW_COUNTDOWN = True

# One Small trial, then one Large. Swap them to run the other way round.
TRIAL_SIZES = ["Small", "Large"]

# The condition name saved in the data, and the title shown on screen.
CONDITION = "ME"
LABEL     = "Motor Execution"
# The standard instructions, with the line about blocks changed to say two trials.
INSTRUCTION = tuple("Two trials, one at each target distance."
                    if line.startswith("Four blocks of eight trials.") else line
                    for line in mo.ME_INSTRUCTION)

# Ask which hand the participant uses, and lay the screen out for that hand.
handedness = mo.screen_handedness()
mo.configure_active_side(handedness)

# Ask for the participant ID and pad it to three digits (7 becomes 007).
pid_raw    = mo.screen_text_input("Enter Participant ID", "(001 – 999)", mo.validate_pid, max_len=3)
pid        = f"{int(pid_raw):03d}"

# Calibration measures how far the participant can comfortably reach. It repeats until
# the experimenter accepts the result.
calib_instruction = (mo.CALIBRATION_INSTRUCTION_RH if handedness == "rh"
                     else mo.CALIBRATION_INSTRUCTION_LH)

while True:
    mo.screen_instructions(calib_instruction, "Begin", title="Calibration Instructions",
                           side=mo.button_side(handedness))
    peak_dist, large_amp, small_amp, angle = mo.run_calibration(pid, handedness)
    if mo.screen_calib_results(peak_dist, large_amp, small_amp, angle, handedness) != "redo":
        break

mo.screen_instructions(INSTRUCTION, title=LABEL, side=mo.button_side(handedness))

# The two target distances worked out from calibration.
amps = {"Small": small_amp, "Large": large_amp}

# Run each trial, with a pause screen after it. The trial number is saved with its data.
for i, size in enumerate(TRIAL_SIZES, 1):
    mo.BLOCK_CTX["trial_index"]    = i
    mo.BLOCK_CTX["block_index"]    = 1
    mo.BLOCK_CTX["trial_in_block"] = i
    mo.BLOCK_CTX["size_position"]  = 1

    mo.run_task_block(pid, handedness, CONDITION, amps[size], angle, LABEL, size)

    mo.screen_trial_complete(handedness, LABEL, i, len(TRIAL_SIZES))

# Final thank-you screen.
mo.screen_task_complete()

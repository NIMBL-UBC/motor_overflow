"""Digital-marker link between the Motor Overflow task and Spike2.

The task sends one marker on the Black Box Toolkit TTL module at three moments
in every trial: when the finger first lands on the X (a), when the trial clock
starts (b) and when the closing bell rings (c). The module's DB25 cable runs
straight into the CED 1401's rear Digital Input connector, and Spike2 records
each marker on a Digital Marker channel.

That straight cable carries only the strobe. BBTK line 8 lands on 1401 pin 23
(Data Available) and the 1401 records a marker each time that line falls. The
data lines do not reach the bits the 1401 reads, so every marker has the same
code (typically AA). That means markers are told apart by their order and
spacing: a, then b about 2.2 s later, then c about 15 s after that. The
decoder at the bottom of this file does that grouping, and
spike2/mo_label_export.s2s is a line-for-line port of it.

A marker is two serial writes with nothing in between: line up ("80"), then
line down ("00"). The fall is the marker. service(), which the task calls once
per frame, puts the line back up once it has been down for PULSE_MIN_MS, ready
for the next marker.

Nothing in the pulse path ever waits. A serial failure switches the link off
and is written down; it never raises into the task.

Needs only the standard library plus pyserial (for real hardware). Set the
environment variable MO_TRIGGER_MOCK=1 to run without hardware.

Command line:
    py bbtk_trigger.py ports            list COM ports
    py bbtk_trigger.py decode <file>    decode marker times, print a report
"""

# Tools from Python's built-in library that this file uses.
import csv
import os
import sys
import time
from datetime import datetime

# Timing settings, in milliseconds (1000 ms = 1 second). These must match the timings
# in motor_overflow9.py and in the Spike2 script. If you change one, change them all.
#   AB_NOMINAL_MS: marker a to marker b (the 2 s rest plus 0.2 s of 'Begin')
#   BC_NOMINAL_MS: marker b to marker c (one 15 s trial)
#   AB_WINDOW_MS / BC_WINDOW_MS: how far those gaps may drift and still count as a trial
#   PULSE_MIN_MS: how long each marker signal is held before it is reset
#   TEST_PULSE_GAP_MS: test markers on the setup screen are limited to one per second
AB_NOMINAL_MS = 2200
BC_NOMINAL_MS = 15000
AB_WINDOW_MS  = (2150, 2350)
BC_WINDOW_MS  = (14950, 15250)
PULSE_MIN_MS  = 5
TEST_PULSE_GAP_MS = 1000
# The USB port the BBTK box is normally on, and the study layout: 8 trials per block,
# 4 blocks per session. Setting MO_TRIGGER_MOCK to 1 runs everything without the box.
DEFAULT_PORT  = "COM12"
TRIALS_PER_BLOCK = 8
BLOCKS_PER_SESSION = 4
MOCK_ENV = "MO_TRIGGER_MOCK"

# Connection speed and the short text commands the BBTK box understands (from its manual).
# 'RR' resets it. '##' asks 'are you there?' and it replies 'XX'.
# '80' raises the marker line and '00' drops it. Spike2 records a marker when it drops.
BAUD = 115200
CMD_RESET  = b"RR"
CMD_PING   = b"##"
PING_REPLY = b"XX"
LINE_UP    = b"80"
LINE_DOWN  = b"00"
RESET_WAIT_S = 0.1


# Turns a technical error into a short message the experimenter can act on.
def _plain_reason(port, exc):
    """A short, plain-English reason an open() failed, for the setup screen.
    The full exception text is kept separately in Trigger.error_detail."""
    text = str(exc)
    low = text.lower()
    if "filenotfound" in low or "cannot find" in low or "no such file" in low:
        return f"{port} not found. Check the USB cable, or tap the port below."
    if "permission" in low or "access is denied" in low:
        return f"{port} is in use by another program. Close it and tap Rescan."
    if "timeout" in low:
        return f"{port} did not answer. Unplug the BBTK, plug it back in, tap Rescan."
    text = text.split("\n")[0].strip()
    if len(text) > 70:
        text = text[:67].rstrip() + "..."
    return f"{port}: {text}" if text else f"{port}: {type(exc).__name__}"


# A pretend BBTK box, used when running without the real hardware.
class FakeSerial:
    """Stands in for serial.Serial in tests and in mock mode.

    Every write is kept in `writes` as (perf_counter ms, bytes) so a test, or a
    person checking a mock run, can see exactly what would have reached the
    module and when."""

    def __init__(self, port=None, baudrate=BAUD, timeout=None, write_timeout=None,
                 fail_open=False, fail_after_writes=None, clock=time.perf_counter,
                 silent=False):
        if fail_open:
            raise OSError(f"could not open port {port!r}")
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.is_open = True
        self.writes = []
        self._fail_after = fail_after_writes
        self._clock = clock
        self._silent = silent
        self._inbox = b""

    def write(self, data):
        if not self.is_open:
            raise OSError("port is closed")
        if self._fail_after is not None and len(self.writes) >= self._fail_after:
            raise OSError("simulated write failure")
        self.writes.append((self._clock() * 1000.0, bytes(data)))
        if bytes(data) == CMD_PING and not self._silent:
            self._inbox += PING_REPLY
        return len(data)

    def read(self, size=1):
        out, self._inbox = self._inbox[:size], self._inbox[size:]
        return out

    def reset_input_buffer(self):
        self._inbox = b""

    def flush(self):
        pass

    def close(self):
        self.is_open = False


# Everything to do with sending markers to Spike2.
class Trigger:
    """The BBTK strobe line. open() once, pulse() at each marker, service() every frame."""

    # Starting values when the marker link is first set up. Nothing is connected yet.
    def __init__(self, clock=time.perf_counter, serial_factory=None):
        self._clock = clock
        self.mock = os.environ.get(MOCK_ENV) == "1"
        if serial_factory is not None:
            self._factory = serial_factory
        elif self.mock:
            self._factory = FakeSerial
        else:
            self._factory = None
        self._ser = None
        self.enabled = False
        self.failed = False
        self.error = ""
        self.error_detail = ""
        self.port = None
        self.answered = False
        self.epoch = clock()
        self.epoch_wallclock = datetime.now().isoformat(timespec="milliseconds")
        self._down = False
        self._down_at = 0.0
        self._last_test = None
        self.n_test = 0
        self.counts = {}


    def open(self, port):
        """Open `port`, reset the module and put the line up. Returns
        (ok, message). Never raises.

        After the reset the module is pinged (## -> XX). No answer still
        opens the link, because markers may well still go out, but `answered`
        is False and the message says so. The reset wait and the ping read
        (at most the 1 s port timeout) are the only blocking waits anywhere
        in this module; they happen on the setup screen, never in a trial.

        RR drops every line, strobe included, so the 1401 may record one
        marker while the port is being opened. Nothing follows it at the a->b
        spacing, so the decoder leaves it unmatched."""
        self.close()
        # Unless the pretend box is in use, load the add-on that talks to USB ports, with a
        # clear message if it is missing.
        factory = self._factory
        if factory is None:
            try:
                import serial
            except ImportError:
                self.enabled = False
                self.error = "pyserial not installed (py -m pip install pyserial)"
                return False, self.error
            factory = getattr(serial, "Serial", None)
            if factory is None:
                self.enabled = False
                self.error = ("wrong 'serial' package installed - run: "
                              "py -m pip uninstall -y serial pyserial && py -m pip install pyserial")
                return False, self.error
        try:
            # Connect, reset the box, check it answers, then raise the marker line ready for use.
            ser = factory(port, BAUD, timeout=1, write_timeout=0.05)
            ser.write(CMD_RESET)
            time.sleep(RESET_WAIT_S)
            if hasattr(ser, "reset_input_buffer"):
                ser.reset_input_buffer()
            ser.write(CMD_PING)
            reply = ser.read(2) if hasattr(ser, "read") else b""
            ser.write(LINE_UP)
        except Exception as exc:
            self.enabled = False
            self.error_detail = f"{type(exc).__name__}: {exc}"
            self.error = _plain_reason(port, exc)
            return False, self.error
        # Connected. Remember the port and whether the box answered.
        self._ser = ser
        self.port = port
        self.enabled = True
        self.failed = False
        self.error = ""
        self._down = False
        self.answered = PING_REPLY in reply
        if self.answered:
            return True, f"BBTK answered on {port}"
        return True, (f"{port} opened but the BBTK did not answer - wrong port, "
                      "or module out of sync: unplug it, plug it back in, tap Rescan")

    def close(self):
        """Put the line up and close the port. Safe to call any number of times."""
        ser, self._ser = self._ser, None
        self.enabled = False
        if ser is None:
            return
        try:
            if getattr(ser, "is_open", True):
                try:
                    ser.write(LINE_UP)
                    ser.flush()
                except Exception:
                    pass
                ser.close()
        except Exception:
            pass
        self._down = False


    # Sends one command to the box. If that fails, markers are switched off for the rest of
    # the session and the reason is saved. The task itself carries on.
    def _write(self, data):
        try:
            self._ser.write(data)
            return True
        except Exception as exc:
            self.enabled = False
            self.failed = True
            self.error_detail = f"{type(exc).__name__}: {exc}"
            self.error = f"link lost on {self.port}: {type(exc).__name__}"
            return False

    def pulse(self, label=""):
        """Send one marker. Returns ms since epoch of the fall, or None if
        nothing was sent. `label` (a, b, c, test) is only counted.

        Two writes, back to back: line up, then line down. If the line is
        still down from the previous marker the first write puts it back up,
        so the second is always a fresh fall."""
        if not self.enabled or self._ser is None:
            return None
        if not self._write(LINE_UP):
            return None
        if not self._write(LINE_DOWN):
            return None
        now = self._clock()
        self._down = True
        self._down_at = now
        self.counts[label] = self.counts.get(label, 0) + 1
        return round((now - self.epoch) * 1000.0, 1)

    def service(self):
        """Call once per frame: puts the line back up once it has been down
        long enough."""
        if not self._down:
            return
        if (self._clock() - self._down_at) * 1000.0 >= PULSE_MIN_MS:
            if self.enabled and self._ser is not None:
                self._write(LINE_UP)
            self._down = False

    def test_pulse(self):
        """A marker for the setup screen, no more than one per second."""
        now = self._clock()
        if self._last_test is not None and (now - self._last_test) * 1000.0 < TEST_PULSE_GAP_MS:
            return False
        if self.pulse("test") is None:
            return False
        self._last_test = now
        self.n_test += 1
        return True


    # Lists the USB ports on this computer, for the setup screen.
    def list_ports(self):
        if self.mock:
            return [("MOCK", "FakeSerial")]
        try:
            from serial.tools import list_ports
        except ImportError:
            return []
        try:
            return [(p.device, p.description) for p in list_ports.comports()]
        except Exception:
            return []



# The rest of this file is a checking tool, used after a session. It groups the
# recorded markers into trials of three (a, b, c) using the gaps between them.
def decode(times):
    """Group marker times (ms) into (a, b, c) triplets by spacing.

    A marker followed by one AB_WINDOW_MS later and another BC_WINDOW_MS
    after that makes one trial. Returns (triplets, unmatched), where unmatched
    is the sorted list of times that did not form a trial. A marker that does
    not start a triplet is skipped on its own, so one stray or missing marker
    costs one trial, not every label after it. Test pulses fall out as
    unmatched because nothing follows them at 2.2 s."""
    m = sorted(float(t) for t in times)
    ab_lo, ab_hi = AB_WINDOW_MS
    bc_lo, bc_hi = BC_WINDOW_MS
    i = 0
    triplets = []
    unmatched = []
    while i < len(m):
        if (i + 2 < len(m)
                and ab_lo <= m[i + 1] - m[i] <= ab_hi
                and bc_lo <= m[i + 2] - m[i + 1] <= bc_hi):
            triplets.append((m[i], m[i + 1], m[i + 2]))
            i += 3
        else:
            unmatched.append(m[i])
            i += 1
    return triplets, unmatched


def assign_positions(triplets):
    """(block, trial) for each triplet, by count. Block 1-4 for a full session
    (the task CSV), block 0 for a single-block file (one Spike2 file per block),
    all zeros when the count is neither (the report then says the positions
    were not assigned). Labels are block + letter for a session (1a ... 4c)
    and trial + letter for a single block (1a ... 8c), as the Spike2 script
    writes them."""
    n = len(triplets)
    if n == TRIALS_PER_BLOCK * BLOCKS_PER_SESSION:
        return [(k // TRIALS_PER_BLOCK + 1, k % TRIALS_PER_BLOCK + 1) for k in range(n)]
    if n == TRIALS_PER_BLOCK:
        return [(0, k + 1) for k in range(n)]
    return [(0, 0)] * n


# True if the number of trials found matches a full session (32) or one block (8).
def positions_assigned(triplets):
    n = len(triplets)
    return n in (TRIALS_PER_BLOCK * BLOCKS_PER_SESSION, TRIALS_PER_BLOCK)


# The smallest, average and largest of a list of numbers.
def _stats(values):
    if not values:
        return None
    return min(values), sum(values) / len(values), max(values)


def report(times):
    """Decode and return the report as a list of text lines."""
    triplets, unmatched = decode(times)
    positions = assign_positions(triplets)
    ab = [b - a for a, b, _ in triplets]
    bc = [c - b for _, b, c in triplets]
    lines = [
        f"markers:     {len(times)}",
        f"triplets:    {len(triplets)}",
        f"unmatched:   {len(unmatched)}",
    ]
    if unmatched:
        lines.append("unmatched (ms): " + ", ".join(f"{t:.1f}" for t in unmatched))
    for name, vals in (("a->b", ab), ("b->c", bc)):
        st = _stats(vals)
        if st:
            lines.append(f"{name} ms:    min {st[0]:.1f}  mean {st[1]:.1f}  max {st[2]:.1f}")
    if positions_assigned(triplets):
        kind = "session (4 blocks x 8)" if len(triplets) == 32 else "single block (8)"
        lines.append(f"positions:   assigned, {kind}")
        lines.append("labels:      " + " ".join(
            f"{b or t}{l}" for (b, t) in positions for l in "abc"))
    else:
        lines.append("positions:   UNASSIGNED (expected 32 or 8 triplets)")
    return lines


def load_marks(path):
    """Marker times (ms) from either a *_mo_task.csv (trig_a_ms, trig_b_ms,
    trig_c_ms flattened in row order) or a file whose first column is the
    time in ms, such as a Spike2 text export of the Trig channel. Any other
    columns (the marker code, which is always the same) are ignored."""
    with open(path, newline="", encoding="utf-8") as f:
        text = f.read()
    rows = list(csv.reader(text.splitlines()))
    if rows and "trig_a_ms" in rows[0]:
        header = rows[0]
        cols = [header.index(f"trig_{k}_ms") for k in "abc"]
        times = []
        for row in rows[1:]:
            for j in cols:
                if j < len(row) and row[j].strip():
                    times.append(float(row[j]))
        return times
    times = []
    for row in rows:
        if not row:
            continue
        try:
            times.append(float(row[0].strip()))
        except ValueError:
            continue
    return times


# Runs when this file is started from the Command Prompt:
#   py bbtk_trigger.py ports           lists the USB ports
#   py bbtk_trigger.py decode <file>   checks a file of marker times
def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("ports", "decode"):
        print("usage: py bbtk_trigger.py ports | decode <file>")
        return 2
    if argv[0] == "ports":
        ports = Trigger().list_ports()
        if not ports:
            print("no COM ports found (is pyserial installed? is the BBTK plugged in?)")
        for dev, desc in ports:
            print(f"{dev}\t{desc}")
        return 0
    if len(argv) < 2:
        print("usage: py bbtk_trigger.py decode <file>")
        return 2
    marks = load_marks(argv[1])
    for line in report(marks):
        print(line)
    return 0


# Only run main() when this file is started directly, not when another file uses it.
if __name__ == "__main__":
    sys.exit(main())

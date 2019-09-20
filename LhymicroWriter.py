import threading
import time

from K40Controller import K40Controller
from LaserCommandConstants import *
from LaserSpeed import LaserSpeed
from ThreadConstants import *
from path import *

COMMAND_RIGHT = b'B'
COMMAND_LEFT = b'T'
COMMAND_TOP = b'L'
COMMAND_BOTTOM = b'R'
COMMAND_ANGLE = b'M'
COMMAND_ON = b'D'
COMMAND_OFF = b'U'

STATE_DEFAULT = 0
STATE_CONCAT = 1
STATE_COMPACT = 2

distance_lookup = [
    b'',
    b'a', b'b', b'c', b'd', b'e', b'f', b'g', b'h', b'i', b'j', b'k', b'l', b'm',
    b'n', b'o', b'p', b'q', b'r', b's', b't', b'u', b'v', b'w', b'x', b'y',
    b'|a', b'|b', b'|c', b'|d', b'|e', b'|f', b'|g', b'|h', b'|i', b'|j', b'|k', b'|l', b'|m',
    b'|n', b'|o', b'|p', b'|q', b'|r', b'|s', b'|t', b'|u', b'|v', b'|w', b'|x', b'|y', b'|z'
]


def lhymicro_distance(v):
    dist = b''
    if v >= 255:
        zs = int(v / 255)
        v %= 255
        dist += (b'z' * zs)
    if v >= 52:
        return dist + b'%03d' % v
    return dist + distance_lookup[v]


class LaserThread(threading.Thread):
    def __init__(self, project):
        threading.Thread.__init__(self)
        self.project = project
        self.controller = project.controller
        self.element_list = None
        self.limit_buffer = True
        self.buffer_max = 20 * 30
        self.buffer_size = -1
        self.state = THREAD_STATE_UNSTARTED
        self.autohome = self.project.autohome
        self.autobeep = self.project.autobeep
        self.autostart = self.project.autostart
        self.element_list = None
        self.project("writer", self.state)

    def start_element_producer(self):
        if self.state != THREAD_STATE_ABORT:
            self.state = THREAD_STATE_STARTED
            self.project("writer", self.state)
            self.start()

    def refresh_element_list(self):
        self.element_list = [e for e in self.project.flat_elements()]
        self.project("progress", (0, len(self.element_list)))

    def pause(self):
        self.state = THREAD_STATE_PAUSED
        self.project("writer", self.state)

    def resume(self):
        self.state = THREAD_STATE_STARTED
        self.project("writer", self.state)

    def abort(self, *args):
        self.state = THREAD_STATE_ABORT
        self.project("writer", self.state)

    def thread_pause_check(self, *args):
        while (self.limit_buffer and self.buffer_size > self.buffer_max) or \
                self.state == THREAD_STATE_PAUSED:
            # Backend is full. Or we are paused. We're waiting.
            time.sleep(0.1)
            if self.state == THREAD_STATE_ABORT:
                raise StopIteration  # abort called.
        if self.state == THREAD_STATE_ABORT:
            raise StopIteration  # abort called.

    def run(self):
        command_index = 0
        self.controller.autostart = self.autostart
        self.project("progress", (0, len(self.element_list)))

        self.project["buffer", self.update_buffer_size] = self
        self.project["abort", self.abort] = self
        self.project.writer.on_plot = self.thread_pause_check
        try:
            if self.element_list is None:
                raise StopIteration
            self.project("progress", (0, len(self.element_list)))
            for element_index, element in enumerate(self.element_list):
                self.thread_pause_check()
                self.project("progress", (element_index + 1, len(self.element_list)))
                for e in element.generate():
                    command, values = e
                    command_index += 1
                    self.thread_pause_check()
                    self.project("command", command_index)
                    self.project.writer.command(command, values)
        except StopIteration:
            pass  # We aborted the loop.
        # Final listener calls.
        self.project.writer.on_plot = None
        self.project["abort", self.abort] = None
        if self.state == THREAD_STATE_ABORT:
            return  # Must no do anything else. Just die as fast as possible.
        if self.autohome:
            self.project.writer.command(COMMAND_HOME, 0)
        if self.project.writer.autolock:
            self.project.writer.command(COMMAND_UNLOCK, 0)
        self.element_list = None
        self.project["buffer", self.update_buffer_size] = None
        if self.autobeep:
            print('\a')  # Beep.
        self.controller.autostart = True
        self.state = THREAD_STATE_FINISHED
        self.project("writer", self.state)

    def update_buffer_size(self, size):
        self.buffer_size = size


class LhymicroWriter:
    def __init__(self, project, board="M2", current_x=0, current_y=0, controller=None):
        self.project = project
        if controller is None:
            self.controller = K40Controller(project)
        else:
            self.controller = controller
        self.thread = LaserThread(project)
        self.autolock = True
        self.board = board
        if self.board is None:
            self.board = "M2"
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.rotary = False
        self.state = STATE_DEFAULT
        self.is_on = False
        self.is_left = False
        self.is_top = False
        self.is_relative = False
        self.raster_step = 0
        self.speed = 30
        self.d_ratio = None
        self.default_SnP = None

        self.current_x = current_x
        self.current_y = current_y
        self.next_x = current_x
        self.next_y = current_y
        self.max_x = current_x
        self.max_y = current_y
        self.min_x = current_x
        self.min_y = current_y
        self.start_x = current_x
        self.start_y = current_y
        self.on_plot = None

    def refresh_elements(self):
        self.thread.refresh_element_list()

    def open(self):
        try:
            self.controller.open()
        except AttributeError:
            pass
        self.reset_modes()
        self.state = STATE_DEFAULT

    def close(self):
        self.to_default_mode()
        try:
            self.controller.close()
        except AttributeError:
            pass

    def group_plots(self, start_x, start_y, generate):
        last_x = start_x
        last_y = start_y
        last_on = 0
        dx = 0
        dy = 0
        x = None
        y = None

        for event in generate:
            try:
                x = event[0]
                y = event[1]
                on = event[2]
            except IndexError:
                on = 1
            if x == last_x + dx and y == last_y + dy and on == last_on:
                last_x = x
                last_y = y
                continue

            yield last_x, last_y, last_on
            if self.on_plot is not None:
                self.on_plot(last_x, last_y, last_on)
            dx = x - last_x
            dy = y - last_y
            if abs(dx) > 1 or abs(dy) > 1:
                # An error here means the plotting routines are flawed and plotted data more than a pixel apart.
                # The bug is in the code that wrongly plotted the data, not here.
                raise ValueError("dx(%d) or dy(%d) exceeds 1" % (dx, dy))
            last_x = x
            last_y = y
            last_on = on
        yield last_x, last_y, last_on
        if self.on_plot is not None:
            self.on_plot(last_x, last_y, last_on)

    def command(self, command, values):
        if command == COMMAND_LASER_OFF:
            self.up()
        elif command == COMMAND_LASER_ON:
            self.down()
        elif command == COMMAND_RAPID_MOVE:
            self.to_default_mode()
            sx, sy, x, y = values
            self.move(x, y)
        elif command == COMMAND_SHIFT:
            x, y = values
            sx = self.current_x
            sy = self.current_y
            self.up()
            if self.state == STATE_COMPACT:
                for x, y, on in self.group_plots(sx, sy, Line.plot_line(sx, sy, x, y)):
                    self.move(x, y)
            else:
                self.move(x, y)
        elif command == COMMAND_MOVE:
            x, y = values
            sx = self.current_x
            sy = self.current_y
            if self.state == STATE_COMPACT:
                for x, y, on in self.group_plots(sx, sy, Line.plot_line(sx, sy, x, y)):
                    self.move(x, y)
            else:
                self.move(x, y)
        elif command == COMMAND_CUT:
            x, y = values
            sx = self.current_x
            sy = self.current_y
            self.down()
            for x, y, on in self.group_plots(sx, sy, Line.plot_line(sx, sy, x, y)):
                self.move_absolute(x, y)
        elif command == COMMAND_HSTEP:
            self.v_switch()
        elif command == COMMAND_VSTEP:
            self.h_switch()
        elif command == COMMAND_HOME:
            self.home()
        elif command == COMMAND_LOCK:
            self.lock_rail()
        elif command == COMMAND_UNLOCK:
            self.unlock_rail()
        elif command == COMMAND_PLOT:
            path = values
            if len(path) == 0:
                return
            first_point = path.first_point
            self.move_absolute(first_point[0], first_point[1])
            sx = self.current_x
            sy = self.current_y
            for x, y, on in self.group_plots(sx, sy, path.plot()):
                if on == 0:
                    self.up()
                else:
                    self.down()
                self.move_absolute(x, y)
        elif command == COMMAND_CUT_QUAD:
            cx, cy, x, y, = values
            sx = self.current_x
            sy = self.current_y
            self.down()
            for x, y, on in self.group_plots(sx, sy, QuadraticBezier.plot_quad_bezier(sx, sy, cx, cy, x, y)):
                self.move_absolute(x, y)
        elif command == COMMAND_CUT_CUBIC:
            c1x, c1y, c2x, c2y, ex, ey = values
            sx = self.current_x
            sy = self.current_y
            self.down()
            for x, y, on in self.group_plots(sx, sy, CubicBezier.plot_cubic_bezier(sx, sy, c1x, c1y, c2x, c2y, ex, ey)):
                self.move_absolute(x, y)
        elif command == COMMAND_SET_SPEED:
            speed = values
            self.set_speed(speed)
        elif command == COMMAND_SET_STEP:
            step = values
            self.set_step(step)
        elif command == COMMAND_SET_D_RATIO:
            d_ratio = values
            self.set_d_ratio(d_ratio)
        elif command == COMMAND_SET_DIRECTION:
            x_dir, y_dir = values
            self.is_left = x_dir < 0
            self.is_top = y_dir < 0
        elif command == COMMAND_SET_INCREMENTAL:
            self.is_relative = True
        elif command == COMMAND_SET_ABSOLUTE:
            self.is_relative = False
        elif command == COMMAND_SET_POSITION:
            x, y = values
            self.current_x = x
            self.current_y = y
        elif command == COMMAND_MODE_COMPACT:
            self.to_compact_mode()
        elif command == COMMAND_MODE_DEFAULT:
            self.to_default_mode()
        elif command == COMMAND_MODE_CONCAT:
            self.to_concat_mode()

    def move(self, x, y):
        if self.is_relative:
            self.move_relative(x, y)
        else:
            self.move_absolute(x, y)

    def move_absolute(self, x, y):
        self.move_relative(x - self.current_x, y - self.current_y)

    def move_relative(self, dx, dy):
        if abs(dx) == 0 and abs(dy) == 0:
            return
        dx = int(round(dx))
        dy = int(round(dy))
        if self.state == STATE_DEFAULT:
            self.controller += b'I'
            if dx != 0:
                self.move_x(dx)
            if dy != 0:
                self.move_y(dy)
            self.controller += b'S1P\n'
            if not self.autolock:
                self.controller += b'IS2P\n'
        elif self.state == STATE_COMPACT:
            if dx != 0 and dy != 0 and abs(dx) != abs(dy):
                for x, y, on in self.group_plots(self.current_x, self.current_y,
                                                 Line.plot_line(self.current_x, self.current_y,
                                                                self.current_x + dx, self.current_y + dy)
                                                 ):
                    self.move_absolute(x, y)
            elif abs(dx) == abs(dy):
                self.move_angle(dx, dy)
            elif dx != 0:
                self.move_x(dx)
            else:
                self.move_y(dy)
        elif self.state == STATE_CONCAT:
            if dx != 0:
                self.move_x(dx)
            if dy != 0:
                self.move_y(dy)
            self.controller += b'N'
        self.check_bounds()
        self.project("position", (self.current_x, self.current_y, self.current_x - dx, self.current_y - dy))

    def move_xy_line(self, delta_x, delta_y):
        """Strictly speaking if this happens it is because of a bug.
        Nothing should feed the writer this data. It's invalid.
        All moves should be diagonal or orthogonal."""
        """Zingl-Bresenham line draw algorithm"""
        dx = abs(delta_x)
        dy = -abs(delta_y)

        if delta_x > 0:
            sx = 1
        else:
            sx = -1
        if delta_y > 0:
            sy = 1
        else:
            sy = -1
        err = dx + dy  # error value e_xy
        x0 = 0
        y0 = 0
        while True:  # /* loop */
            if x0 == delta_x and y0 == delta_y:
                break
            mx = 0
            my = 0
            e2 = 2 * err
            if e2 >= dy:  # e_xy+e_y < 0
                err += dy
                x0 += sx
                mx += sx
            if e2 <= dx:  # e_xy+e_y < 0
                err += dx
                y0 += sy
                my += sy
            if abs(mx) == abs(my):
                self.move_angle(mx, my)
            elif mx != 0:
                self.move_x(mx)
            else:
                self.move_y(my)

    def set_speed(self, speed=None):
        change = False
        if self.speed != speed:
            change = True
            self.speed = speed
        if not change:
            return
        if self.state == STATE_COMPACT:
            # Compact mode means it's currently slowed. To make the speed have an effect, compact must be exited.
            self.to_concat_mode()
            self.to_compact_mode()

    def set_d_ratio(self, d_ratio=None):
        change = False
        if self.d_ratio != d_ratio:
            change = True
            self.d_ratio = d_ratio
        if not change:
            return
        if self.state == STATE_COMPACT:
            # Compact mode means it's currently slowed. To make the speed have an effect, compact must be exited.
            self.to_concat_mode()
            self.to_compact_mode()

    def set_step(self, step=None):
        change = False
        if self.raster_step != step:
            change = True
            self.raster_step = step
        if not change:
            return
        if self.state == STATE_COMPACT:
            # Compact mode means it's currently slowed. To make the speed have an effect, compact must be exited.
            self.to_concat_mode()
            self.to_compact_mode()

    def down(self):
        if self.is_on:
            return False
        if self.state == STATE_DEFAULT:
            self.controller += b'I'
            self.controller += COMMAND_ON
            self.controller += b'S1P\n'
            if not self.autolock:
                self.controller += b'IS2P\n'
        elif self.state == STATE_COMPACT:
            self.controller += COMMAND_ON
        elif self.state == STATE_CONCAT:
            self.controller += COMMAND_ON
            self.controller += b'N'
        self.is_on = True
        return True

    def up(self):
        if not self.is_on:
            return False
        if self.state == STATE_DEFAULT:
            self.controller += b'I'
            self.controller += COMMAND_OFF
            self.controller += b'S1P\n'
            if not self.autolock:
                self.controller += b'IS2P\n'
        elif self.state == STATE_COMPACT:
            self.controller += COMMAND_OFF
        elif self.state == STATE_CONCAT:
            self.controller += COMMAND_OFF
            self.controller += b'N'
        self.is_on = False
        return True

    def to_default_mode(self):
        if self.state == STATE_CONCAT:
            self.controller += b'S1P\n'
            if not self.autolock:
                self.controller += b'IS2P\n'
        elif self.state == STATE_COMPACT:
            self.controller += b'FNSE-\n'
            self.reset_modes()
        self.state = STATE_DEFAULT

    def to_concat_mode(self):
        self.to_default_mode()
        self.controller += b'I'
        self.state = STATE_CONCAT

    def to_compact_mode(self):
        self.to_concat_mode()
        if self.d_ratio is not None:
            speed_code = LaserSpeed.get_code_from_speed(self.speed, self.raster_step, self.board, d_ratio=self.d_ratio)
        else:
            speed_code = LaserSpeed.get_code_from_speed(self.speed, self.raster_step, self.board)
        try:
            speed_code = bytes(speed_code)
        except TypeError:
            speed_code = bytes(speed_code, 'utf8')
        self.controller += speed_code
        self.controller += b'N'
        self.declare_directions()
        self.controller += b'S1E'
        self.state = STATE_COMPACT

    def h_switch(self):
        if self.is_left:
            self.controller += COMMAND_RIGHT
        else:
            self.controller += COMMAND_LEFT
        self.is_left = not self.is_left
        if self.is_top:
            self.current_y -= self.raster_step
        else:
            self.current_y += self.raster_step

    def v_switch(self):
        if self.is_top:
            self.controller += COMMAND_BOTTOM
        else:
            self.controller += COMMAND_TOP
        self.is_top = not self.is_top
        if self.is_left:
            self.current_x -= self.raster_step
        else:
            self.current_x += self.raster_step

    def home(self):
        self.to_default_mode()
        self.controller += b'IPP\n'
        old_x = self.current_x
        old_y = self.current_y
        self.current_x = 0
        self.current_y = 0
        self.reset_modes()
        self.state = STATE_DEFAULT
        self.project("position", (self.current_x, self.current_y, old_x, old_y))

    def lock_rail(self):
        self.to_default_mode()
        self.controller += b'IS1P\n'

    def unlock_rail(self, abort=False):
        self.to_default_mode()
        self.controller += b'IS2P\n'

    def abort(self):
        self.controller += b'I\n'

    def check_bounds(self):
        self.min_x = min(self.min_x, self.current_x)
        self.min_y = min(self.min_y, self.current_y)
        self.max_x = max(self.max_x, self.current_x)
        self.max_y = max(self.max_y, self.current_y)

    def reset_modes(self):
        self.is_on = False
        self.is_left = False
        self.is_top = False

    def move_x(self, dx):
        if dx > 0:
            self.move_right(dx)
        else:
            self.move_left(dx)

    def move_y(self, dy):
        if dy > 0:
            self.move_bottom(dy)
        else:
            self.move_top(dy)

    def move_angle(self, dx, dy):
        if abs(dx) != abs(dy):
            raise ValueError('abs(dx) must equal abs(dy)')
        if dx > 0:  # Moving right
            if self.is_left:
                self.controller += COMMAND_RIGHT
                self.is_left = False
        else:  # Moving left
            if not self.is_left:
                self.controller += COMMAND_LEFT
                self.is_left = True
        if dy > 0:  # Moving bottom
            if self.is_top:
                self.controller += COMMAND_BOTTOM
                self.is_top = False
        else:  # Moving top
            if not self.is_top:
                self.controller += COMMAND_TOP
                self.is_top = True
        self.current_x += dx
        self.current_y += dy
        self.check_bounds()
        self.controller += COMMAND_ANGLE + lhymicro_distance(abs(dy))

    def declare_directions(self):
        if self.is_top:
            self.controller += COMMAND_TOP
        else:
            self.controller += COMMAND_BOTTOM
        if self.is_left:
            self.controller += COMMAND_LEFT
        else:
            self.controller += COMMAND_RIGHT

    def move_right(self, dx=0):
        self.current_x += dx
        self.is_left = False
        self.controller += COMMAND_RIGHT
        if dx != 0:
            self.controller += lhymicro_distance(abs(dx))
            self.check_bounds()

    def move_left(self, dx=0):
        self.current_x -= abs(dx)
        self.is_left = True
        self.controller += COMMAND_LEFT
        if dx != 0:
            self.controller += lhymicro_distance(abs(dx))
            self.check_bounds()

    def move_bottom(self, dy=0):
        self.current_y += dy
        self.is_top = False
        self.controller += COMMAND_BOTTOM
        if dy != 0:
            self.controller += lhymicro_distance(abs(dy))
            self.check_bounds()

    def move_top(self, dy=0):
        self.current_y -= abs(dy)
        self.is_top = True
        self.controller += COMMAND_TOP
        if dy != 0:
            self.controller += lhymicro_distance(abs(dy))
            self.check_bounds()

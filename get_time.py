#!/usr/bin/env python3
"""When run as a program, gets the total Python runtime of all simulations
in logfile"""
import sys
import os

class ClockTime:
    """A helper class for dealing with clock time math and str/int
    conversions

    Example usage:
        # string initialization
        t1 = ClockTime('11:44') # 11 minutes and 44 seconds
        # integer conversion
        t1.value # 704 (seconds)

        # integer initialization
        t1 = ClockTime(704)
        # string conversion
        str(t1)  # '11:44'

        # Basic math
        t2 = ClockTime('5:05')
        t3 = t1 + t2        # ClockTime('16:49')
        t3 / t2             # ClockTime('3'); always does floor division
        t3.value / t2.value # true division: 3.308...
        t3 * t2             # ClockTime('85:33:38')
        t3 - t2             # ClockTime('11:44')

        # Math also works with int and string types
        t3 + 10         # 16:59
        t3 * 2          # 33:38
        t3 / 2          # 8:24
        t3.value / 2    # true division: 504.5
        t3 - '5:05'     # 11:44
        t3 % '5:05'     # 1:34
    """
    def __init__(self, value=None):
        int_type = type(int())
        str_type = type(str())
        val_type = type(value)
        if value is None:
            self.value = 0
        elif isinstance(value, ClockTime):
            self.value = value.value
        elif val_type == str_type:
            self.value = ClockTime.str_to_time(value)
        elif val_type == int_type:
            self.value = value
        else:
            raise ValueError("Invalid argument type: " + str(value))

    @staticmethod
    def str_to_time(strtime):
        """Converts a string like "1:00[:00]" to seconds since 0:00[:00]"""
        conversions = 1, 60, 3600
        times = list(map(int, strtime.split(":")))
        times.reverse()
        conversions = conversions[:len(times)]
        time_total = 0
        for time, conv in zip(times, conversions):
            time_total += time * conv
        return time_total

    @staticmethod
    def time_to_str(time):
        """Converts number of seconds to a human-readable time string"""
        conversions = 3600, 60, 1
        parts = []
        printed = False # print 00 when
        for conv in conversions:
            if printed:
                parts.append("{:02d}".format(int(time/conv)))
                time = time % conv
            elif time >= conv:
                parts.append(str(int(time/conv)))
                time = time % conv
                printed = True
        if not parts:
            return "0"
        return ":".join(parts)

    def __str__(self):
        return ClockTime.time_to_str(self.value)

    def __repr__(self):
        return "ClockTime('"+self.__str__()+"')"

    def __add__(self, other):
        return ClockTime(self.value + ClockTime(other).value)

    def __sub__(self, other):
        return ClockTime(self.value - ClockTime(other).value)

    def __mul__(self, other):
        if isinstance(other, float):
            return ClockTime(int(self.value * other))
        return ClockTime(self.value * ClockTime(other).value)

    def __div__(self, other):
        """For Python 2 compatibility, result is truncated to int"""
        if isinstance(other, float):
            return ClockTime(int(self.value / other))
        return ClockTime(int(self.value / ClockTime(other).value))

    def __truediv__(self, other):
        """Not actually true division. Converts result to integer"""
        return self.__div__(other)

    def __floordiv__(self, other):
        """Same as __truediv__, since both convert to integer"""
        return self.__truediv__(other)

    def __mod__(self, other):
        if isinstance(other, float):
            return ClockTime(int(self.value % other))
        return ClockTime(self.value % ClockTime(other).value)

    def __gt__(self, value):
        return self.value > ClockTime(value).value

    def __ge__(self, value):
        return self.value >= ClockTime(value).value

    def __lt__(self, value):
        return self.value < ClockTime(value).value

    def __le__(self, value):
        return self.value < ClockTime(value).value

    def __eq__(self, value):
        return self.value == ClockTime(value).value

def _main():
    def usage():
        print("Usage:", sys.argv[0], "[logfile]", file=sys.stderr)

    if len(sys.argv) == 1:
        infile = 'results.log'
    else:
        infile = sys.argv[1]

    if not os.path.exists(infile):
        print("Error: No such file or directory:", infile, file=sys.stderr)
        usage()
        sys.exit(1)
    elif os.path.isdir(infile):
        print("Error:", infile, "is a directory", file=sys.stderr)
        usage()
        sys.exit(2)

    expr = re.compile(r'(\d+\.\d+)')
    with open(infile) as file_obj:
        times = [expr.search(line).group(1) for line in file_obj]

    tot_time = sum(map(float, times))

    print("Total running time: {:.2f} seconds {!s}".format(tot_time, ClockTime(int(tot_time))))

if __name__ == '__main__':
    import re
    _main()

from grove.grove_i2c_motor_driver import MotorDriver
from grove.grove_optical_rotary_encoder import GroveOpticalRotaryEncoder

from multiprocessing.connection import Listener

motor = MotorDriver()
self.encoder = GroveOpticalRotaryEncoder(5)

address = ('localhost', 6000)     # family is deduced to be 'AF_INET'
listener = Listener(address,)
conn = listener.accept()
print('connection accepted from ' + str(listener.last_accepted))
try:
    while True:
        msg = conn.recv()
        # do something with msg
        motor.set_speed(float(msg))
finally:
    motor.set_speed(0)
    listener.close()

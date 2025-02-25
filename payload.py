import pyIR
import sys


def getRem(pin=29, remotefile="BENQ_remote"):
    rec = pyIR.Receiver(pin)
    rec.addRemote(pyIR.loadRemote(remotefile))
    print(rec.listen())
    

if __name__ == "__main__":
    args = sys.argv
    if len(args) == 1:
        getRem()
    elif len(args) == 2:
        getRem(pin=args[1])
    elif len(args) == 3:
        getRem(pin=args[1], remotefile=args[2])
    else:
        raise NameError("nah")

